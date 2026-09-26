from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import ValidationError
from vera.core.store import ContextStore
from vera.core.engine import DeterministicEngine
from vera.core.models import ContextPayload, TickRequest, ReplyRequest, ContextResponse

app = FastAPI()
store = ContextStore()
engine = DeterministicEngine(store)

@app.get("/v1/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/v1/metadata")
def metadata():
    return {"name": "Vera Baseline", "version": "0.1.0"}

@app.post("/v1/context")
def context(payload: ContextPayload, response: Response):
    res = store.push(payload)
    if not res.accepted:
        response.status_code = 409
    return res.model_dump(exclude_none=True)

@app.post("/v1/tick")
def tick(request: TickRequest):
    return engine.tick(request)

@app.post("/v1/reply")
def reply(request: ReplyRequest):
    return engine.reply(request)
