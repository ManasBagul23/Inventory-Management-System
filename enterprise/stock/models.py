from django.conf import settings
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=120)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Product(models.Model):
    sku = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    stock = models.PositiveIntegerField(default=0)


class Movement(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    delta = models.IntegerField()
    note = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)


class Quotation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        QUOTED = "quoted", "Quoted"
        ACCEPTED = "accepted", "Accepted"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationJob(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=240)
    processed_at = models.DateTimeField(null=True)


class Notification(models.Model):
    job = models.OneToOneField(NotificationJob, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
