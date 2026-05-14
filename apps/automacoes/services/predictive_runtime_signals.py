from __future__ import annotations

from statistics import mean
from django.utils import timezone

from apps.automacoes.services.runtime_trend_analytics import RuntimeTrendAnalyticsService


class PredictiveRuntimeSignalsService:
    """
    Predictive operational signals built on top of historical runtime snapshots.

    Read-only and SQLite-safe:
    - no writes
    - no raw SQL
    - no vendor-specific features
    """

    @classmethod
    def build_dashboard(cls) -> dict:
        trends = RuntimeTrendAnalyticsService.build_dashboard(limit=50)

        risk = cls.runtime_risk_score(trends)
        stability = cls.stability_index(trends)
        warnings = cls.predictive_warnings(trends, risk, stability)

        return {
            "risk": risk,
            "stability": stability,
            "warnings": warnings,
            "failure_forecast": cls.failure_forecast(trends),
            "alert_acceleration": cls.alert_acceleration(trends),
            "generated_at": timezone.now(),
        }

    @classmethod
    def runtime_risk_score(cls, trends: dict) -> dict:
        summary = trends.get("summary", {})
        score_trend = trends.get("score_trend", {})
        alert_trend = trends.get("alert_trend", {})
        failure_trend = trends.get("failure_trend", {})
        scheduler_trend = trends.get("scheduler_trend", {})
        anomalies = trends.get("anomalies", [])

        risk = 0

        latest_score = float(summary.get("latest_score") or 0)
        if latest_score < 60:
            risk += 35
        elif latest_score < 85:
            risk += 20

        if score_trend.get("direction") == "degrading":
            risk += 20

        if alert_trend.get("direction") == "degrading":
            risk += 15

        if failure_trend.get("direction") == "degrading":
            risk += 20

        if scheduler_trend.get("direction") == "degrading":
            risk += 15

        risk += min(len(anomalies) * 8, 24)
        risk = max(0, min(100, int(risk)))

        return {
            "score": risk,
            "level": cls._risk_level(risk),
            "label": cls._risk_label(risk),
        }

    @classmethod
    def stability_index(cls, trends: dict) -> dict:
        series = trends.get("series", {})
        scores = [float(v or 0) for v in series.get("runtime_score", [])]

        if not scores:
            return {
                "score": 0,
                "label": "Sem histórico",
                "level": "unknown",
            }

        avg_score = mean(scores)
        volatility = max(scores) - min(scores)
        stability = round(max(0, min(100, avg_score - (volatility * 0.5))), 2)

        if stability >= 85:
            level = "stable"
            label = "Stable"
        elif stability >= 70:
            level = "watch"
            label = "Watch"
        elif stability >= 50:
            level = "at_risk"
            label = "At Risk"
        else:
            level = "critical"
            label = "Critical"

        return {
            "score": stability,
            "label": label,
            "level": level,
        }

    @classmethod
    def predictive_warnings(cls, trends: dict, risk: dict, stability: dict) -> list[dict]:
        warnings = []

        if risk.get("score", 0) >= 75:
            warnings.append({
                "severity": "critical",
                "title": "Risco operacional crítico",
                "message": "O runtime apresenta sinais combinados de degradação relevante.",
            })
        elif risk.get("score", 0) >= 50:
            warnings.append({
                "severity": "warning",
                "title": "Runtime em observação",
                "message": "Há sinais preditivos que justificam acompanhamento operacional.",
            })

        if stability.get("level") in {"at_risk", "critical"}:
            warnings.append({
                "severity": "warning",
                "title": "Estabilidade reduzida",
                "message": "O histórico recente indica instabilidade operacional.",
            })

        failure = trends.get("failure_trend", {})
        if failure.get("direction") == "degrading":
            warnings.append({
                "severity": "warning",
                "title": "Tendência de falhas crescente",
                "message": "O número de falhas recentes está aumentando.",
            })

        alerts = trends.get("alert_trend", {})
        if alerts.get("direction") == "degrading":
            warnings.append({
                "severity": "warning",
                "title": "Tendência de alertas crescente",
                "message": "O volume de alertas ativos indica possível degradação futura.",
            })

        return warnings

    @classmethod
    def failure_forecast(cls, trends: dict) -> dict:
        failure = trends.get("failure_trend", {})
        direction = failure.get("direction", "stable")

        if direction == "degrading":
            return {
                "direction": direction,
                "label": "Falhas em crescimento",
                "risk": "elevated",
            }

        if direction == "improving":
            return {
                "direction": direction,
                "label": "Falhas em redução",
                "risk": "low",
            }

        return {
            "direction": "stable",
            "label": "Falhas estáveis",
            "risk": "normal",
        }

    @classmethod
    def alert_acceleration(cls, trends: dict) -> dict:
        series = trends.get("series", {})
        alerts = [float(v or 0) for v in series.get("active_alerts", [])]

        if len(alerts) < 3:
            return {
                "accelerating": False,
                "label": "Sem dados suficientes",
            }

        last_delta = alerts[-1] - alerts[-2]
        previous_delta = alerts[-2] - alerts[-3]
        accelerating = last_delta > previous_delta and last_delta > 0

        return {
            "accelerating": accelerating,
            "label": "Alertas acelerando" if accelerating else "Sem aceleração de alertas",
        }

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "moderate"
        return "low"

    @staticmethod
    def _risk_label(score: int) -> str:
        if score >= 75:
            return "CRITICAL"
        if score >= 50:
            return "AT RISK"
        if score >= 25:
            return "WATCH"
        return "STABLE"
