from django.core.management.base import BaseCommand

from apps.automacoes.services.runtime_metrics import RuntimeMetricsService


class Command(BaseCommand):
    help = "Captures a persisted runtime metrics snapshot for Ops Center trend analysis."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="manual",
            help="Snapshot source label. Examples: manual, scheduler_tick, ops_center.",
        )

    def handle(self, *args, **options):
        source = options.get("source") or "manual"
        snapshot = RuntimeMetricsService.create_snapshot(source=source)

        self.stdout.write(
            self.style.SUCCESS(
                "Runtime metrics snapshot captured: "
                f"id={snapshot.id}, score={snapshot.runtime_score}, "
                f"status={snapshot.runtime_status}, source={snapshot.source}"
            )
        )
