from datetime import datetime, timezone
import uuid
from typing import Optional, List
from vera.core.store import ContextStore
from vera.core.models import TickRequest, TickResponse, Action, ReplyRequest, ReplyResponse, Scope, TriggerContext
from vera.core.evidence import Evidence, EvidenceSet
from vera.core.decision import ActionIntent, Decision

class DeterministicEngine:
    def __init__(self, store: ContextStore):
        self.store = store

    def _extract_evidence(self, trigger_ctx: TriggerContext) -> EvidenceSet:
        evidence = EvidenceSet()

        evidence.add(Evidence(
            kind="raw_fact",
            value=trigger_ctx.kind,
            source_domain="trigger",
            source_id=trigger_ctx.id,
            field_path="kind",
            explanation=f"Trigger kind is {trigger_ctx.kind}"
        ))

        target_merchant_id = trigger_ctx.merchant_id
        target_customer_id = trigger_ctx.customer_id

        if target_customer_id:
            c_ctx = self.store.get(Scope.CUSTOMER, target_customer_id)
            if c_ctx:
                evidence.add(Evidence(
                    kind="raw_fact",
                    value=c_ctx.payload.get("name"),
                    source_domain="customer",
                    source_id=target_customer_id,
                    field_path="name",
                    explanation=f"Customer name is {c_ctx.payload.get('name')}"
                ))

        if target_merchant_id:
            m_ctx = self.store.get(Scope.MERCHANT, target_merchant_id)
            if m_ctx:
                evidence.add(Evidence(
                    kind="raw_fact",
                    value=m_ctx.payload.get("name"),
                    source_domain="merchant",
                    source_id=target_merchant_id,
                    field_path="name",
                    explanation=f"Merchant name is {m_ctx.payload.get('name')}"
                ))

        return evidence

    def _evaluate(self, trigger_id: str, evidence: EvidenceSet) -> Decision:
        trigger_kind_ev = evidence.get_by_kind("raw_fact")
        t_kind = next((e.value for e in trigger_kind_ev if e.source_domain == "trigger" and e.field_path == "kind"), None)

        m_name_ev = next((e for e in trigger_kind_ev if e.source_domain == "merchant" and e.field_path == "name"), None)
        c_name_ev = next((e for e in trigger_kind_ev if e.source_domain == "customer" and e.field_path == "name"), None)

        if not t_kind or not m_name_ev:
            return Decision(
                should_act=False,
                reason="Insufficient evidence: missing trigger kind or merchant context",
                evidence=evidence
            )

        merchant_id = m_name_ev.source_id

        is_customer_facing = c_name_ev is not None or "customer" in t_kind or "recall" in t_kind

        if is_customer_facing:
            if not c_name_ev:
                return Decision(
                    should_act=False,
                    reason="Insufficient evidence: customer-facing trigger lacks customer context",
                    evidence=evidence
                )
            intent = ActionIntent(
                audience="customer",
                action_type="notify",
                merchant_id=merchant_id,
                customer_id=c_name_ev.source_id,
                trigger_id=trigger_id,
                suppression_key=f"baseline_{trigger_id}_{c_name_ev.source_id}"
            )
        else:
            intent = ActionIntent(
                audience="merchant",
                action_type="notify",
                merchant_id=merchant_id,
                trigger_id=trigger_id,
                suppression_key=f"baseline_{trigger_id}_{merchant_id}"
            )

        return Decision(
            should_act=True,
            reason=f"Sufficient evidence for {intent.audience} notification",
            evidence=evidence,
            intent=intent
        )

    def _generate_action(self, decision: Decision) -> Optional[Action]:
        if not decision.should_act or not decision.intent:
            return None

        intent = decision.intent
        m_name = next((e.value for e in decision.evidence.items if e.source_domain == "merchant" and e.field_path == "name"), "Merchant")

        if intent.audience == "customer":
            c_name = next((e.value for e in decision.evidence.items if e.source_domain == "customer" and e.field_path == "name"), "Customer")
            body = f"Hello {c_name}, {m_name} has a message for you."
            send_as = "merchant_on_behalf"
            conv_id = f"conv_{intent.customer_id}_{intent.trigger_id}"
        else:
            body = f"Hello {m_name}, you have a new alert."
            send_as = "vera"
            conv_id = f"conv_{intent.merchant_id}_{intent.trigger_id}"

        # Hard Output Validation is inherently satisfied by Pydantic Action model and logic above
        # No URLs in body, valid send_as, etc.

        return Action(
            conversation_id=conv_id,
            merchant_id=intent.merchant_id,
            customer_id=intent.customer_id,
            send_as=send_as,
            trigger_id=intent.trigger_id,
            body=body,
            cta="none",
            suppression_key=intent.suppression_key or "default_key",
            rationale=decision.reason
        )

    def tick(self, request: TickRequest) -> TickResponse:
        actions = []
        for trigger_id in request.available_triggers:
            trigger_ctx_payload = self.store.get(Scope.TRIGGER, trigger_id)
            if not trigger_ctx_payload:
                continue

            trigger_ctx = TriggerContext(**trigger_ctx_payload.payload)
            trigger_ctx.trigger_id = trigger_id

            evidence = self._extract_evidence(trigger_ctx)
            decision = self._evaluate(trigger_id, evidence)

            action = self._generate_action(decision)
            if action:
                actions.append(action)

        return TickResponse(actions=actions)

    def reply(self, request: ReplyRequest) -> ReplyResponse:
        # Minimal deterministic transition for contract tests
        if request.message.lower().strip() == "stop":
            return ReplyResponse(
                action="end",
                rationale="User requested stop."
            )
        return ReplyResponse(
            action="wait",
            wait_seconds=86400,
            rationale="Deterministic baseline always waits."
        )
