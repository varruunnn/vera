from datetime import datetime, timezone
from typing import Dict, Tuple

from vera.core.models import ContextPayload, ContextResponse

class ContextStore:
    def __init__(self) -> None:
        # Key: (scope, context_id)
        self._store: Dict[Tuple[str, str], ContextPayload] = {}

    def push(self, data: ContextPayload) -> ContextResponse:
        key = (data.scope, data.context_id)
        
        if key in self._store:
            current_version = self._store[key].version
            if data.version <= current_version:
                return ContextResponse(
                    accepted=False,
                    reason="stale_version",
                    current_version=current_version
                )
                
        self._store[key] = data
        return ContextResponse(
            accepted=True,
            ack_id=f"ack_{data.context_id}_v{data.version}",
            stored_at=datetime.now(timezone.utc).isoformat()
        )

    def get(self, scope: str, context_id: str) -> ContextPayload | None:
        return self._store.get((scope, context_id))

    def clear(self) -> None:
        self._store.clear()
