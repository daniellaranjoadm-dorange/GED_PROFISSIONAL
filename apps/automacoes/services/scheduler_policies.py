from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerPolicy:
    name: str
    interval_minutes: int
    enabled: bool = True
    allow_concurrent: bool = False
    timeout_minutes: int = 120


DEFAULT_POLICIES = {
    "health_scan": SchedulerPolicy(
        name="health_scan",
        interval_minutes=15,
        timeout_minutes=15,
    ),
    "km_reindex": SchedulerPolicy(
        name="km_reindex",
        interval_minutes=1440,
        timeout_minutes=240,
        allow_concurrent=False,
    ),
}


def obter_policy(job_name: str) -> SchedulerPolicy:
    return DEFAULT_POLICIES.get(
        job_name,
        SchedulerPolicy(name=job_name, interval_minutes=60),
    )
