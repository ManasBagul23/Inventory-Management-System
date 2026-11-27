import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from stock.models import Notification, NotificationJob


class Command(BaseCommand):
    help = "Deliver queued notifications. Use --watch to poll continuously."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        while True:
            job_ids = list(NotificationJob.objects.filter(processed_at=None).order_by("pk").values_list("pk", flat=True)[:100])
            for job_id in job_ids:
                with transaction.atomic():
                    claimed = NotificationJob.objects.filter(pk=job_id, processed_at=None).update(processed_at=now())
                    if claimed:
                        Notification.objects.get_or_create(job_id=job_id)
            if job_ids:
                continue
            if not options["watch"]:
                return
            time.sleep(2)
