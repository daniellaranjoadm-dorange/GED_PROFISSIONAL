from django.core.management.base import BaseCommand

from apps.automacoes.services.runtime_retention import RuntimeRetentionService


class Command(BaseCommand):
    help = "Apply SQLite-safe runtime retention policies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Retention window in days.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be deleted.",
        )

    def handle(self, *args, **options):
        result = RuntimeRetentionService.cleanup_all(
            days=options["days"],
            dry_run=options["dry_run"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Runtime retention completed: deleted={result['total_deleted']} dry_run={result['dry_run']}"
            )
        )
