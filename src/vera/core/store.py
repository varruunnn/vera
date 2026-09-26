from datetime import datetime, timezone
import threading
from typing import Dict, Tuple, Optional

from vera.core.models import ContextPayload, ContextResponse

class ContextStore:
    def __init__(self) -> None:
        # Key: (scope, context_id)
        self._store: Dict[Tuple[str, str], ContextPayload] = {}
        self._lock = threading.RLock()

    def push(self, data: ContextPayload) -> ContextResponse:
        key = (data.scope, data.context_id)

        with self._lock:
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

    def get(self, scope: str, context_id: str) -> Optional[ContextPayload]:
        with self._lock:
            return self._store.get((scope, context_id))

    def get_by_scope(self, scope: str) -> list[ContextPayload]:
        with self._lock:
            return [v for k, v in self._store.items() if k[0] == scope]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
