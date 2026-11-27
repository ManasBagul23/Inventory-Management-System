from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

from .models import Movement, Notification, Product, Supplier


class InventoryWorkflowTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.buyer = users.objects.create_user("buyer", password="test-buyer-password", is_staff=True)
        self.vendor = users.objects.create_user("vendor")
        self.other = users.objects.create_user("other")
        self.supplier = Supplier.objects.create(user=self.vendor, name="Vendor")
        Supplier.objects.create(user=self.other, name="Other")
        self.item = Product.objects.create(sku="TEST-01", name="Bearing", stock=5)
        self.client.force_login(self.buyer)

    def post(self, path, data):
        return self.client.post("/api/" + path, data, content_type="application/json")

    def test_stock_change_and_audit_are_consistent(self):
        action = f"products/{self.item.pk}/movement/"
        self.assertEqual(self.post(action, {"delta": -6, "note": "Shipment"}).status_code, 409)
        self.assertFalse(Movement.objects.exists())
        self.assertEqual(self.post(action, {"delta": -3, "note": "Shipment"}).status_code, 201)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 2)
        self.assertEqual(Movement.objects.get().delta, -3)
        self.client.force_login(self.vendor)
        self.assertEqual(self.post(action, {"delta": 1, "note": "Receipt"}).status_code, 403)

    def test_quote_transitions_and_notification_delivery(self):
        response = self.post("quotations/", {"product": self.item.id, "supplier": self.supplier.id, "quantity": 2})
        self.assertEqual(response.status_code, 201)
        quote_id = response.json()["id"]
        self.assertEqual(self.post(f"quotations/{quote_id}/accept/", {}).status_code, 409)
        call_command("process_notifications")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/workspace/").json()["quotations"], [])
        self.assertEqual(self.post(f"quotations/{quote_id}/quote/", {"price": "10.25"}).status_code, 404)
        self.client.force_login(self.vendor)
        request_notice = self.client.get("/api/workspace/").json()["notifications"][0]["id"]
        self.assertEqual(self.post(f"notifications/{request_notice}/read/", {}).status_code, 200)
        self.assertEqual(self.post(f"quotations/{quote_id}/quote/", {"price": "10.25"}).status_code, 200)
        self.assertEqual(self.post(f"quotations/{quote_id}/quote/", {"price": "10.25"}).status_code, 409)
        self.client.force_login(self.buyer)
        self.assertEqual(self.post(f"notifications/{request_notice}/read/", {}).status_code, 404)
        self.assertEqual(self.post(f"quotations/{quote_id}/accept/", {}).status_code, 200)
        call_command("process_notifications")
        call_command("process_notifications")
        self.assertEqual(Notification.objects.count(), 3)
        quote = self.client.get("/api/workspace/").json()["quotations"][0]
        self.assertEqual((quote["status"], quote["unit_price"]), ("accepted", "10.25"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 5)

    def test_session_requires_csrf_and_serves_role_after_login(self):
        client = Client(enforce_csrf_checks=True)
        credentials = {"username": "buyer", "password": "test-buyer-password"}
        csrf = client.get("/api/session/").json()["csrf"]
        rejected = client.post("/api/session/", credentials, content_type="application/json")
        self.assertEqual(rejected.status_code, 403)
        signed_in = client.post("/api/session/", credentials, content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(signed_in.json()["role"], "buyer")
        self.assertEqual(client.get("/api/workspace/").status_code, 200)
