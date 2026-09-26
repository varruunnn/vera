from datetime import datetime, timezone
import uuid
from typing import Optional, List, Dict, Any
from vera.core.store import ContextStore
from vera.core.models import TickRequest, TickResponse, Action, ReplyRequest, ReplyResponse, Scope, TriggerContext, ContextPayload
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

        # Conversation Evidence
        # Assuming conversation_id is passed or constructed (we can construct it based on scope)
        conv_id = f"conv_{target_customer_id or target_merchant_id}_{trigger_ctx.id}"
        conv_ctx = self.store.get(Scope.CONVERSATION, conv_id)
        if conv_ctx:
            # We store the dict in payload
            c_state = conv_ctx.payload

            evidence.add(Evidence("RAW_FACT", c_state.get("status"), "conversation", conv_id, "state.status", "Current conversation status"))

            opt_out = c_state.get("opt_out", False)
            evidence.add(Evidence("RAW_FACT", opt_out, "conversation", conv_id, "state.opt_out", "User opted out of conversation"))

            pos_intent = c_state.get("positive_intent", False)
            evidence.add(Evidence("RAW_FACT", pos_intent, "conversation", conv_id, "state.positive_intent", "User showed positive intent"))

            last_intent = c_state.get("last_intent")
            if last_intent:
                evidence.add(Evidence("DERIVED_FACT", last_intent, "conversation", conv_id, "intent.last_intent", "Detected intent from latest reply"))

            last_reply = c_state.get("last_reply")
            if last_reply:
                evidence.add(Evidence("RAW_FACT", last_reply, "conversation", conv_id, "recent_messages.last_reply", "Latest reply text"))

        return evidence

    def _evaluate(self, trigger_id: str, evidence: DecisionEvidenceSet) -> Decision:
        # Check conversation first
        conv_opt_out = False
        conv_pos_intent = False
        conv_status = "NEW"
        conv_intent = None

        for e in evidence.get_by_domain("conversation"):
            if e.field_path == "state.opt_out" and e.value is True:
                conv_opt_out = True
            elif e.field_path == "state.positive_intent" and e.value is True:
                conv_pos_intent = True
            elif e.field_path == "state.status":
                # Handle Enum stringification if needed
                conv_status = e.value.value if hasattr(e.value, "value") else str(e.value).replace("ConversationStatus.", "")
            elif e.field_path == "intent.last_intent":
                conv_intent = e.value.value if hasattr(e.value, "value") else str(e.value).replace("Intent.", "")

        # Handle Opt Out
        if conv_opt_out or conv_intent == "OPT_OUT":
            return Decision(False, "User opted out", evidence)

        # Handle Auto Reply loops
        if conv_intent == "AUTO_REPLY":
            if conv_status in ("WAITING", "TERMINAL"):
                return Decision(False, "Auto-reply loop detected", evidence)

        # Handle Questions / Uncertainty
        if conv_intent in ("QUESTION", "UNCERTAINTY", "UNRELATED", "NEGATIVE_INTENT"):
            return Decision(False, f"Received {conv_intent.lower()}, pausing outreach", evidence)

        if conv_status not in ("NEW", "OUTREACH", "QUALIFYING") and not conv_pos_intent and conv_intent not in ("POSITIVE_INTENT", "ACTION_REQUEST"):
            return Decision(False, "Already engaged, waiting for resolution", evidence)

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

            if conv_pos_intent or conv_intent in ("POSITIVE_INTENT", "ACTION_REQUEST"):
                intent = ActionIntent("customer", "execute_action", merchant_id, trigger_id, c_name_ev.source_id, f"baseline_{trigger_id}_{c_name_ev.source_id}")
                strategy = MessageStrategy("customer", "Confirm Execution", "helpful", ["Confirm action executed"], [], [], "none")
            else:
                intent = ActionIntent("customer", "notify", merchant_id, trigger_id, c_name_ev.source_id, f"baseline_{trigger_id}_{c_name_ev.source_id}")
                strategy = MessageStrategy("customer", "Inform customer", "helpful", ["merchant has message"], [], [], "none")
        else:
            if conv_pos_intent or conv_intent in ("POSITIVE_INTENT", "ACTION_REQUEST"):
                intent = ActionIntent("merchant", "execute_action", merchant_id, trigger_id, None, f"baseline_{trigger_id}_{merchant_id}")
                strategy = MessageStrategy("merchant", "Confirm Execution", "professional", ["Confirm action executed"], [], [], "none")
            else:
                intent = ActionIntent("merchant", "notify", merchant_id, trigger_id, None, f"baseline_{trigger_id}_{merchant_id}")
                strategy = MessageStrategy("merchant", "Alert merchant", "professional", ["trigger occurred"], [], [], "none")

        if conv_pos_intent or conv_intent in ("POSITIVE_INTENT", "ACTION_REQUEST"):
            return Decision(True, "Execute requested action", evidence, intent, strategy)

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
        from vera.core.models import ConversationState, ConversationStatus, Intent
        from vera.core.classifier import IntentClassifier

        # Load conversation state
        conv_payload = self.store.get(Scope.CONVERSATION, request.conversation_id)
        if conv_payload:
            state = ConversationState(**conv_payload.payload)
            next_version = conv_payload.version + 1
        else:
            state = ConversationState(conversation_id=request.conversation_id)
            next_version = 1

        # Classify
        classifier = IntentClassifier()
        intent = classifier.classify(request.message)

        # Update basic state
        if request.message == state.last_reply:
            state.consecutive_similar_replies += 1
        else:
            state.consecutive_similar_replies = 0

        state.last_reply = request.message
        state.reply_count += 1
        state.last_intent = intent

        if intent == Intent.OPT_OUT:
            state.opt_out = True
            state.status = ConversationStatus.OPTED_OUT

        elif intent in (Intent.POSITIVE_INTENT, Intent.ACTION_REQUEST):
            state.positive_intent = True
            if state.status == ConversationStatus.QUALIFYING:
                state.status = ConversationStatus.ACTION_REQUESTED
            else:
                state.status = ConversationStatus.ENGAGED

        elif intent == Intent.AUTO_REPLY:
            if state.consecutive_similar_replies >= 1:
                state.status = ConversationStatus.WAITING
        else:
            if not state.opt_out:
                state.status = ConversationStatus.ENGAGED

        # Save back to store before evidence extraction
        self.store.push(ContextPayload(scope=Scope.CONVERSATION, context_id=state.conversation_id, version=next_version, payload=state.model_dump()))

        # Now we need to call deterministic engine.
        # But wait, reply request does not contain trigger_id explicitly.
        # Usually it's encoded in the conversation_id: e.g. conv_c_001_trg_1
        # We can extract it, but for a true reply we might just want to respond
        # to the intent without re-evaluating the trigger.
        # However, the user instructed: "5. call the same deterministic decision engine; 6. produce the official external response"
        # So we should call _evaluate on the trigger_id.

        parts = request.conversation_id.split("_")
        if len(parts) >= 3 and parts[-2].startswith("trg"):
            trigger_id = parts[-2] + "_" + parts[-1]
            # E.g. conv_c_001_trg_001 -> parts are ['conv', 'c', '001', 'trg', '001']
            # Wait, better way to extract trigger ID: we can just look up the trigger context if we know it.
            # Actually, standard format in evaluate_baseline.py: conv_id = f"conv_{target_customer_id or target_merchant_id}_{trigger_ctx.id}"
            pass

        # Instead of parsing, we can just find any trigger in the store that matches the conversation_id, but the instruction expects _evaluate.
        # Let's simplify and just find the trigger by iterating or parsing.
        trigger_id = None
        for t in self.store.get_by_scope(Scope.TRIGGER):
            if request.conversation_id.endswith(t.context_id):
                trigger_id = t.context_id
                break

        if not trigger_id:
            # Fallback simple handling if no trigger found
            if state.status == ConversationStatus.OPTED_OUT:
                return ReplyResponse(action="end", rationale="User opted out.")
            return ReplyResponse(action="wait", wait_seconds=86400, rationale="No active trigger found.")

        trigger_ctx_payload = self.store.get(Scope.TRIGGER, trigger_id)
        trigger_ctx = TriggerContext(**trigger_ctx_payload.payload)
        trigger_ctx.id = trigger_id

        # We need `now` for evidence. We can use request.received_at or a default.
        now = request.received_at or "2026-04-26T10:00:00Z"
        evidence = self._extract_evidence(trigger_ctx, now)
        decision = self._evaluate(trigger_id, evidence)

        if not decision.should_act:
            if state.status == ConversationStatus.OPTED_OUT:
                return ReplyResponse(action="end", rationale=decision.reason)
            return ReplyResponse(action="wait", wait_seconds=86400, rationale=decision.reason)

        action = self._generate_action(decision, use_gemini=False)
        if action:
            state.last_action = action.intent if hasattr(action, 'intent') else "sent"
            self.store.push(ContextPayload(scope=Scope.CONVERSATION, context_id=state.conversation_id, version=next_version+1, payload=state.model_dump()))
            if "execute" in action.rationale.lower():
                return ReplyResponse(action="send", body="Executing your request now.", cta="none", rationale=action.rationale)
            return ReplyResponse(action="send", body=action.body, cta=action.cta, rationale=action.rationale)

        return ReplyResponse(action="wait", wait_seconds=86400, rationale="No action generated.")
