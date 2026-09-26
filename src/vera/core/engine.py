from datetime import datetime, timezone
import uuid
from typing import Optional, List, Dict, Any
from vera.core.store import ContextStore
from vera.core.models import TickRequest, TickResponse, Action, ReplyRequest, ReplyResponse, Scope, TriggerContext
from vera.core.evidence import Evidence, DecisionEvidenceSet
from vera.core.decision import ActionIntent, Decision, MessageStrategy

class DeterministicEngine:
    def __init__(self, store: ContextStore):
        self.store = store

    def _extract_evidence(self, trigger_ctx: TriggerContext, now_iso: str) -> DecisionEvidenceSet:
        evidence = DecisionEvidenceSet()

        # Trigger Evidence
        evidence.add(Evidence("RAW_FACT", trigger_ctx.kind, "trigger", trigger_ctx.id, "kind", "Trigger kind"))
        evidence.add(Evidence("RAW_FACT", trigger_ctx.scope, "trigger", trigger_ctx.id, "scope", "Trigger scope"))

        from vera.core.adapters import apply_trigger_adapter
        apply_trigger_adapter(trigger_ctx, evidence)

        if trigger_ctx.expires_at:
            evidence.add(Evidence("RAW_FACT", trigger_ctx.expires_at, "trigger", trigger_ctx.id, "expires_at", "Trigger expiration time"))
            try:
                trigger_time = datetime.fromisoformat(trigger_ctx.expires_at.replace("Z", "+00:00"))
                now_time = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                is_expired = now_time > trigger_time
            except ValueError:
                is_expired = False
            evidence.add(Evidence("DERIVED_FACT", is_expired, "trigger", trigger_ctx.id, "is_expired", "Has the trigger expired?"))

        target_merchant_id = trigger_ctx.merchant_id
        target_customer_id = trigger_ctx.customer_id

        # Customer Evidence
        if target_customer_id:
            c_ctx = self.store.get(Scope.CUSTOMER, target_customer_id)
            if c_ctx:
                payload = c_ctx.payload
                name = payload.get("identity", {}).get("name")
                opt_in = payload.get("preferences", {}).get("reminder_opt_in", False)

                evidence.add(Evidence("RAW_FACT", name, "customer", target_customer_id, "identity.name", "Customer name"))
                evidence.add(Evidence("RAW_FACT", opt_in, "customer", target_customer_id, "preferences.reminder_opt_in", "Customer opt-in status"))
                evidence.add(Evidence("DERIVED_FACT", bool(opt_in), "customer", target_customer_id, "is_contactable", "Is customer contactable via opt-in?"))

        # Merchant Evidence
        if target_merchant_id:
            m_ctx = self.store.get(Scope.MERCHANT, target_merchant_id)
            if m_ctx:
                payload = m_ctx.payload
                name = payload.get("identity", {}).get("name")
                cat_slug = payload.get("category_slug")
                sub_status = payload.get("subscription", {}).get("status")

                evidence.add(Evidence("RAW_FACT", name, "merchant", target_merchant_id, "identity.name", "Merchant name"))
                evidence.add(Evidence("RAW_FACT", sub_status, "merchant", target_merchant_id, "subscription.status", "Merchant subscription status"))

                if sub_status == "expired":
                    evidence.add(Evidence("DERIVED_FACT", False, "merchant", target_merchant_id, "is_active_subscriber", "Merchant subscription is expired"))
                else:
                    evidence.add(Evidence("DERIVED_FACT", True, "merchant", target_merchant_id, "is_active_subscriber", "Merchant is active"))

                if cat_slug:
                    evidence.add(Evidence("RAW_FACT", cat_slug, "merchant", target_merchant_id, "category_slug", "Category of merchant"))

        return evidence

    def _evaluate(self, trigger_id: str, evidence: DecisionEvidenceSet) -> Decision:
        t_scope = next((e.value for e in evidence.get_by_kind("RAW_FACT") if e.source_domain == "trigger" and e.field_path == "scope"), None)
        is_expired = next((e.value for e in evidence.get_by_kind("DERIVED_FACT") if e.source_domain == "trigger" and e.field_path == "is_expired"), False)

        if is_expired:
            return Decision(False, "Trigger has expired", evidence)

        m_name_ev = next((e for e in evidence.get_by_kind("RAW_FACT") if e.source_domain == "merchant" and e.field_path == "identity.name"), None)

        if not m_name_ev:
            return Decision(False, "Missing merchant context", evidence)

        merchant_id = m_name_ev.source_id

        is_active = next((e.value for e in evidence.get_by_kind("DERIVED_FACT") if e.source_domain == "merchant" and e.field_path == "is_active_subscriber"), True)
        if not is_active:
            return Decision(False, "Merchant subscription is expired", evidence)

        if t_scope == "customer":
            is_contactable = next((e.value for e in evidence.get_by_kind("DERIVED_FACT") if e.source_domain == "customer" and e.field_path == "is_contactable"), None)
            c_name_ev = next((e for e in evidence.get_by_kind("RAW_FACT") if e.source_domain == "customer" and e.field_path == "identity.name"), None)

            if not c_name_ev:
                return Decision(False, "Missing customer context", evidence)

            if is_contactable is False:
                return Decision(False, "Customer has not opted in", evidence)

            intent = ActionIntent("customer", "notify", merchant_id, trigger_id, c_name_ev.source_id, f"baseline_{trigger_id}_{c_name_ev.source_id}")
            strategy = MessageStrategy("customer", "Inform customer", "helpful", ["merchant has message"], [], [], "none")
        else:
            intent = ActionIntent("merchant", "notify", merchant_id, trigger_id, None, f"baseline_{trigger_id}_{merchant_id}")
            strategy = MessageStrategy("merchant", "Alert merchant", "professional", ["trigger occurred"], [], [], "none")

        return Decision(True, "Valid context and constraints met", evidence, intent, strategy)

    def _generate_action(self, decision: Decision, use_gemini: bool = False, use_verifier: bool = False, verifier_failures: list = None) -> Optional[Action]:
        if not decision.should_act or not decision.intent or not decision.strategy:
            return None

        intent = decision.intent
        m_name = next((e.value for e in decision.evidence.items if e.source_domain == "merchant" and e.field_path == "identity.name"), "Merchant")

        if intent.audience == "customer":
            c_name = next((e.value for e in decision.evidence.items if e.source_domain == "customer" and e.field_path == "identity.name"), "Customer")
            fallback_body = f"Hello {c_name}, {m_name} has a message for you."
            send_as = "merchant_on_behalf"
            conv_id = f"conv_{intent.customer_id}_{intent.trigger_id}"
        else:
            fallback_body = f"Hello {m_name}, you have a new alert."
            send_as = "vera"
            conv_id = f"conv_{intent.merchant_id}_{intent.trigger_id}"

        body = fallback_body
        cta = decision.strategy.cta

        if use_gemini:
            from vera.core.composer import GeminiComposer
            from vera.core.verifier import OutputVerifier

            composer = GeminiComposer()
            output = composer.compose(decision)

            if output:
                if use_verifier:
                    verifier = OutputVerifier()
                    v_result = verifier.verify(output, decision.evidence)
                    if v_result.is_valid:
                        body = output.body
                        cta = output.cta_text
                    else:
                        if verifier_failures is not None:
                            verifier_failures.extend(v_result.failures)
                else:
                    body = output.body
                    cta = output.cta_text
            else:
                if verifier_failures is not None:
                    verifier_failures.append("Composer failed or timed out")

        return Action(
            conversation_id=conv_id,
            merchant_id=intent.merchant_id,
            customer_id=intent.customer_id,
            send_as=send_as,
            trigger_id=intent.trigger_id,
            body=body,
            cta=cta,
            suppression_key=intent.suppression_key or "default_key",
            rationale=decision.reason
        )

    def tick(self, request: TickRequest, use_gemini: bool = False, use_verifier: bool = False, verifier_failures_dict: dict = None) -> TickResponse:
        actions = []
        for trigger_id in request.available_triggers:
            trigger_ctx_payload = self.store.get(Scope.TRIGGER, trigger_id)
            if not trigger_ctx_payload:
                continue

            trigger_ctx = TriggerContext(**trigger_ctx_payload.payload)
            trigger_ctx.id = trigger_id

            evidence = self._extract_evidence(trigger_ctx, request.now)
            decision = self._evaluate(trigger_id, evidence)

            v_fails = []
            action = self._generate_action(decision, use_gemini=use_gemini, use_verifier=use_verifier, verifier_failures=v_fails)
            if verifier_failures_dict is not None and v_fails:
                verifier_failures_dict[trigger_id] = v_fails

            if action:
                actions.append(action)

        return TickResponse(actions=actions)

    def reply(self, request: ReplyRequest) -> ReplyResponse:
        if request.message.lower().strip() == "stop":
            return ReplyResponse(action="end", rationale="User requested stop.")
        return ReplyResponse(action="wait", wait_seconds=86400, rationale="Deterministic baseline always waits.")
