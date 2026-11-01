from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.users import User
from app.schemas.copilot import CopilotRequest, CopilotResponse
from app.services.copilot import answer_chat, erp_context

router = APIRouter(prefix="/copilot", tags=["copilot"])
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_current_user)]


@router.post("/chat", response_model=CopilotResponse)
def chat(payload: CopilotRequest, db: Db, actor: Actor) -> CopilotResponse:
    history = [item.model_dump() for item in payload.history]
    context = erp_context(db, str(actor.role), payload.message.strip(), history, actor.id)
    try:
        answer, provider = answer_chat(payload.message.strip(), history, context)
        return CopilotResponse(answer=answer, provider=provider)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
