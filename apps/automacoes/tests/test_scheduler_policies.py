from django.test import SimpleTestCase

from apps.automacoes.services.scheduler_policies import obter_policy


class SchedulerPoliciesTests(SimpleTestCase):
    def test_obter_policy_km_reindex(self):
        policy = obter_policy("km_reindex")

        self.assertEqual(policy.name, "km_reindex")
        self.assertFalse(policy.allow_concurrent)
        self.assertEqual(policy.interval_minutes, 1440)

    def test_obter_policy_default(self):
        policy = obter_policy("job_novo")

        self.assertEqual(policy.name, "job_novo")
        self.assertEqual(policy.interval_minutes, 60)
