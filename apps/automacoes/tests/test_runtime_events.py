from django.test import TestCase

from apps.automacoes.services.runtime_events import RuntimeEventStreamService


class RuntimeEventStreamServiceTests(TestCase):
    def test_build_stream_returns_list(self):
        events = RuntimeEventStreamService.build_stream()
        self.assertIsInstance(events, list)

    def test_summary_returns_expected_keys(self):
        summary = RuntimeEventStreamService.summary()

        self.assertIn("total", summary)
        self.assertIn("critical", summary)
        self.assertIn("error", summary)
        self.assertIn("warning", summary)
        self.assertIn("info", summary)
        self.assertIn("updated_at", summary)

    def test_normalize_severity(self):
        self.assertEqual(RuntimeEventStreamService._normalize_severity("critical"), "CRITICAL")
        self.assertEqual(RuntimeEventStreamService._normalize_severity("error"), "ERROR")
        self.assertEqual(RuntimeEventStreamService._normalize_severity("warning"), "WARNING")
        self.assertEqual(RuntimeEventStreamService._normalize_severity("anything"), "INFO")
