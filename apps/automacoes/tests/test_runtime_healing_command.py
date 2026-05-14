from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class RuntimeHealingCommandTests(TestCase):
    def test_runtime_self_heal_command(self):
        output = StringIO()

        call_command("runtime_self_heal", stdout=output)

        self.assertIn("Self-healing runtime executado", output.getvalue())
