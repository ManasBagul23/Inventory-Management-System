import json
import mimetypes
import re
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_safe

from .models import Movement, Notification, NotificationJob, Product, Quotation, Supplier

FRONTEND = settings.BASE_DIR / "frontend" / "dist"


@require_safe
def index(request):
    page = FRONTEND / "index.html"
    if not page.is_file():
        return HttpResponse("Build the React frontend first. See README.md.", status=503)
    return FileResponse(page.open("rb"), content_type="text/html")


@require_safe
def asset(request, name):
    path = FRONTEND / "assets" / name
    if not re.fullmatch(r"[\w-]+\.(?:css|js)", name, flags=re.ASCII) or not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), content_type=mimetypes.guess_type(path)[0])


def error(message, status):
    return JsonResponse({"error": message}, status=status)


def csrf_failure(request, reason=""):
    return error("Session verification failed. Reload and try again.", 403)


def api(method, role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != method:
                response = error("Method not allowed.", 405)
                response["Allow"] = method
                return response
            if role and not request.user.is_authenticated:
                return error("Sign in to continue.", 401)
            request.supplier = None
            if role and not request.user.is_staff:
                request.supplier = Supplier.objects.filter(user=request.user).first()
                if role == "buyer" or request.supplier is None:
                    return error("You do not have access to this action.", 403)
            if method == "POST":
                try:
                    request.data = json.loads(request.body or "{}")
                    if not isinstance(request.data, dict):
                        raise ValueError
                except (ValueError, UnicodeError):
                    return error("Expected a JSON object.", 400)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


def session_data(request):
    user = request.user
    role = None
    if user.is_authenticated:
        if user.is_staff:
            role = "buyer"
        elif Supplier.objects.filter(user=user).exists():
            role = "supplier"
    return {"role": role, "username": user.get_username() if role else None, "csrf": get_token(request)}


def session(request):
    if request.method == "GET":
        return JsonResponse(session_data(request))
    return change_session(request)


@api("POST")
def change_session(request):
    if request.data.get("action") == "logout":
        logout(request)
        return JsonResponse(session_data(request))
    username = request.data.get("username")
    password = request.data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return error("Enter a username and password.", 400)
    user = authenticate(request, username=username, password=password)
    if user is None or not (user.is_staff or Supplier.objects.filter(user=user).exists()):
        return error("Invalid username or password.", 401)
    login(request, user)
    return JsonResponse(session_data(request))


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def text_field(value, limit):
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= limit else ""


@api("GET", "member")
def workspace(request):
    quotes = Quotation.objects.select_related("product", "supplier").order_by("-id")
    products = []
    movements = []
    suppliers = []
    if request.supplier:
        quotes = quotes.filter(supplier=request.supplier)
    else:
        products = list(Product.objects.order_by("sku").values("id", "sku", "name", "stock"))
        suppliers = list(Supplier.objects.order_by("name").values("id", "name"))
        movements = list(Movement.objects.order_by("-id").values("id", "product__sku", "delta", "note", "created_at")[:20])
    notices = Notification.objects.filter(job__recipient=request.user).order_by("-id")
    return JsonResponse({
        "products": products,
        "suppliers": suppliers,
        "movements": movements,
        "quotations": [{
            "id": quote.id, "product": quote.product.name, "sku": quote.product.sku,
            "supplier": quote.supplier.name, "quantity": quote.quantity,
            "status": quote.status, "unit_price": quote.unit_price,
            "can_accept": quote.buyer_id == request.user.id and quote.status == Quotation.Status.QUOTED,
        } for quote in quotes],
        "notifications": list(notices.values("id", "job__message", "read", "created_at")[:30]),
    })


@api("POST", "buyer")
def product(request):
    sku = text_field(request.data.get("sku"), 32).upper()
    name = text_field(request.data.get("name"), 120)
    if not sku or len(sku) > 32 or not name:
        return error("Enter a SKU and product name within the field limits.", 400)
    try:
        item = Product.objects.create(sku=sku, name=name)
    except IntegrityError:
        return error("That SKU already exists.", 409)
    return JsonResponse({"id": item.id}, status=201)


@api("POST", "buyer")
@transaction.atomic
def movement(request, identifier):
    delta = request.data.get("delta")
    note = text_field(request.data.get("note"), 160)
    if not integer(delta, -1_000_000, 1_000_000) or not delta or not note:
        return error("Enter a non-zero stock change and a reason.", 400)
    changed = Product.objects.filter(
        pk=identifier, stock__gte=max(0, -delta), stock__lte=2_147_483_647 - max(0, delta),
    ).update(stock=F("stock") + delta)
    if not changed:
        if not Product.objects.filter(pk=identifier).exists():
            return error("Product not found.", 404)
        return error("This change exceeds the available stock or stock limit.", 409)
    Movement.objects.create(product_id=identifier, user=request.user, delta=delta, note=note)
    return JsonResponse({"ok": True}, status=201)


@api("POST", "buyer")
def quotation(request):
    product_id = request.data.get("product")
    supplier_id = request.data.get("supplier")
    quantity = request.data.get("quantity")
    if not all(integer(value, 1, 1_000_000_000) for value in (product_id, supplier_id, quantity)):
        return error("Select a product and supplier and enter a positive quantity.", 400)
    supplier = Supplier.objects.filter(pk=supplier_id).first()
    if supplier is None or not Product.objects.filter(pk=product_id).exists():
        return error("Product or supplier not found.", 404)
    with transaction.atomic():
        quote = Quotation.objects.create(
            product_id=product_id, supplier=supplier, buyer=request.user, quantity=quantity,
        )
        NotificationJob.objects.create(recipient=supplier.user, message=f"Quotation #{quote.id} requested.")
    return JsonResponse({"id": quote.id}, status=201)


@api("POST", "member")
@transaction.atomic
def quotation_action(request, identifier, action):
    quotes = Quotation.objects.filter(pk=identifier)
    if action == "quote" and request.supplier:
        quotes = quotes.filter(supplier=request.supplier)
        try:
            raw_price = request.data.get("price")
            if not isinstance(raw_price, str) or len(raw_price) > 16:
                raise InvalidOperation
            price = Decimal(raw_price)
            if not price.is_finite() or not 0 < price <= Decimal("99999999.99") or price.as_tuple().exponent < -2:
                raise InvalidOperation
        except InvalidOperation:
            return error("Enter a positive price with up to two decimal places.", 400)
        changed = quotes.filter(status=Quotation.Status.REQUESTED).update(status=Quotation.Status.QUOTED, unit_price=price)
        if changed:
            NotificationJob.objects.create(recipient_id=quotes.values_list("buyer_id", flat=True).get(), message=f"Quotation #{identifier} is ready to review.")
    elif action == "accept" and request.user.is_staff:
        quotes = quotes.filter(buyer=request.user)
        changed = quotes.filter(status=Quotation.Status.QUOTED).update(status=Quotation.Status.ACCEPTED)
        if changed:
            supplier_user = quotes.values_list("supplier__user_id", flat=True).get()
            NotificationJob.objects.create(recipient_id=supplier_user, message=f"Quotation #{identifier} was accepted.")
    else:
        return error("You do not have access to this action.", 403)
    if not changed:
        return error("Invalid quotation state.", 409) if quotes.exists() else error("Quotation not found.", 404)
    return JsonResponse({"ok": True})


@api("POST", "member")
def read_notification(request, identifier):
    if not Notification.objects.filter(pk=identifier, job__recipient=request.user).update(read=True):
        return error("Notification not found.", 404)
    return JsonResponse({"ok": True})
