from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import settings_store
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from .. import models


def require_admin(current: CurrentUser):
    if current.role != models.UserRole.admin.value:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="administrator access required")

router = APIRouter(prefix="/api/settings", tags=["settings"])

GEMINI_KEY_NAME = "gemini_api_key"


class ApiKeyIn(BaseModel):
    api_key: str


@router.get("/gemini-key")
def get_gemini_key_status(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    value = settings_store.get_setting(db, GEMINI_KEY_NAME, current.organization_id)
    return {
        "configured": bool(value),
        "last4": value[-4:] if value else None,
    }


@router.post("/gemini-key")
def set_gemini_key(payload: ApiKeyIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current)
    settings_store.set_setting(db, GEMINI_KEY_NAME, payload.api_key.strip(), current.organization_id)
    return {"saved": True}


@router.delete("/gemini-key")
def clear_gemini_key(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(current)
    settings_store.delete_setting(db, GEMINI_KEY_NAME, current.organization_id)
    return {"deleted": True}
