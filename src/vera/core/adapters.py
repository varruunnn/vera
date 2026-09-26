from typing import Dict, Type, Protocol
from vera.core.evidence import DecisionEvidenceSet, Evidence
from vera.core.models import TriggerContext

class TriggerEvidenceAdapter(Protocol):
    def extract(self, trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
        pass

class GenericTriggerAdapter:
    def extract(self, trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
        payload = trigger_ctx.payload or {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)):
                evidence.add(Evidence("RAW_FACT", value, "trigger", trigger_ctx.id, f"payload.{key}", f"Trigger payload {key} is {value}"))

class PerformanceSignalAdapter:
    def extract(self, trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
        payload = trigger_ctx.payload or {}
        metric = payload.get("metric_or_topic", "performance")
        evidence.add(Evidence("DERIVED_FACT", metric, "trigger", trigger_ctx.id, "performance_signal", "Performance signal topic"))

class ReminderAdapter:
    def extract(self, trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
        payload = trigger_ctx.payload or {}
        due_date = payload.get("due_date")
        if due_date:
            evidence.add(Evidence("RAW_FACT", due_date, "trigger", trigger_ctx.id, "payload.due_date", "Reminder due date"))
        service = payload.get("service_due")
        if service:
            evidence.add(Evidence("RAW_FACT", service, "trigger", trigger_ctx.id, "payload.service_due", "Service due"))

class TrendAdapter:
    def extract(self, trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
        payload = trigger_ctx.payload or {}
        season = payload.get("season")
        if season:
            evidence.add(Evidence("RAW_FACT", season, "trigger", trigger_ctx.id, "payload.season", "Seasonal trend"))

# Simple registry
ADAPTERS: Dict[str, TriggerEvidenceAdapter] = {
    "perf_dip": PerformanceSignalAdapter(),
    "perf_spike": PerformanceSignalAdapter(),
    "recall_due": ReminderAdapter(),
    "chronic_refill_due": ReminderAdapter(),
    "appointment_tomorrow": ReminderAdapter(),
    "category_seasonal": TrendAdapter()
}

def apply_trigger_adapter(trigger_ctx: TriggerContext, evidence: DecisionEvidenceSet) -> None:
    adapter = ADAPTERS.get(trigger_ctx.kind, GenericTriggerAdapter())
    adapter.extract(trigger_ctx, evidence)
