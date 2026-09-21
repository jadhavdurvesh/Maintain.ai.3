from sqlalchemy.orm import Session

from . import models


def _key(key: str, organization_id: int | None = None) -> str:
    return f"org:{organization_id}:{key}" if organization_id is not None else key


def get_setting(db: Session, key: str, organization_id: int | None = None) -> str | None:
    row = db.query(models.AppSetting).filter_by(key=_key(key, organization_id)).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: str, organization_id: int | None = None) -> None:
    scoped_key = _key(key, organization_id)
    row = db.query(models.AppSetting).filter_by(key=scoped_key).first()
    if row:
        row.value = value
    else:
        db.add(models.AppSetting(key=scoped_key, value=value))
    db.commit()


def delete_setting(db: Session, key: str, organization_id: int | None = None) -> None:
    row = db.query(models.AppSetting).filter_by(key=_key(key, organization_id)).first()
    if row:
        db.delete(row)
        db.commit()
