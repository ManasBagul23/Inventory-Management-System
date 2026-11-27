from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stock.models import Movement, Product, Supplier


class Command(BaseCommand):
    help = "Create demo buyers, suppliers and stock in a local development database."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo accounts are available only with INVENTORY_DEBUG=1.")
        users = get_user_model()
        accounts = {}
        for name in ("buyer", "supplier", "supplier2"):
            user, created = users.objects.get_or_create(username=name, defaults={"is_staff": name == "buyer"})
            if not created and not user.check_password("inventory-demo"):
                raise CommandError(f"The username {name} already belongs to a different account.")
            if created:
                user.set_password("inventory-demo")
                user.save(update_fields=["password"])
            accounts[name] = user
        for username, name in [("supplier", "Northline Supply"), ("supplier2", "Meridian Industrial")]:
            Supplier.objects.get_or_create(user=accounts[username], defaults={"name": name})
        for sku, name, stock in [("VAL-014", "Pressure valve", 42), ("BRG-6204", "Sealed bearing", 18), ("FLT-050", "Intake filter", 7)]:
            product, created = Product.objects.get_or_create(sku=sku, defaults={"name": name, "stock": stock})
            if created:
                Movement.objects.create(product=product, user=accounts["buyer"], delta=stock, note="Opening stock")
        self.stdout.write(self.style.SUCCESS("Demo accounts and starting stock are ready."))
