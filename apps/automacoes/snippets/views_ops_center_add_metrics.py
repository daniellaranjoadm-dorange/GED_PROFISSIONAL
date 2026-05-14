# Add near imports:
from apps.automacoes.services.runtime_metrics import RuntimeMetricsService

# Add to ops_center / partial context:
"metrics": RuntimeMetricsService.trend_summary(limit=24),
