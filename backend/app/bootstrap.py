from .database import SessionLocal
from . import models

BOOTSTRAP_ORG_ID = 1


def ensure_bootstrap_organization():
    """Guarantees org id=1 exists — every table with an organization_id
    column defaults to it, so local/desktop mode (REQUIRE_AUTH=false) always
    has somewhere for that data to point, with zero setup. Must be called
    by anything that writes to the database before auth exists yet
    (the API on startup, and the standalone seed script)."""
    db = SessionLocal()
    try:
        if not db.get(models.Organization, BOOTSTRAP_ORG_ID):
            db.add(models.Organization(id=BOOTSTRAP_ORG_ID, name="Default Organization"))
            db.commit()
    finally:
        db.close()
