"""
Celery configuration for DigitalBazar project.
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("digitalbazar")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# Periodic tasks (Celery Beat)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    "process-pending-payouts": {
        "task": "apps.orders.tasks.process_pending_payouts",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    "generate-daily-sales-reports": {
        "task": "apps.orders.tasks.generate_daily_sales_report",
        "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    "cleanup-expired-downloads": {
        "task": "apps.orders.tasks.cleanup_expired_downloads",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "update-product-stats": {
        "task": "apps.orders.tasks.update_product_statistics",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
