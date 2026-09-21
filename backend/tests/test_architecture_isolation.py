import os
os.environ.setdefault("REQUIRE_AUTH", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.deps import CurrentUser, visible_machine_ids
from app.routers.machines import _get_machine_for_restore


def make_db():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_technician_visibility_is_assignment_scoped():
    db = make_db()
    org = models.Organization(name="Org")
    db.add(org)
    db.flush()
    a = models.Machine(machine_code="A", name="A", organization_id=org.id, archived=False)
    b = models.Machine(machine_code="B", name="B", organization_id=org.id, archived=False)
    db.add_all([a, b])
    db.flush()
    tech = models.User(username="tech", role=models.UserRole.technician, organization_id=org.id, active=True)
    db.add(tech)
    db.flush()
    db.add(models.UserMachineAssignment(user_id=tech.id, machine_id=a.id))
    db.commit()
    current = CurrentUser(tech.id, org.id, "tech", "technician")
    assert visible_machine_ids(db, current) == [a.id]


def test_archived_machines_are_excluded_from_normal_visibility():
    db = make_db()
    org = models.Organization(name="Org")
    db.add(org)
    db.flush()
    live = models.Machine(machine_code="A", name="A", organization_id=org.id, archived=False)
    archived = models.Machine(machine_code="B", name="B", organization_id=org.id, archived=True)
    db.add_all([live, archived])
    db.commit()
    current = CurrentUser(None, org.id, "admin", "admin")
    assert visible_machine_ids(db, current) == [live.id]
    assert visible_machine_ids(db, current, include_archived=True) == [live.id, archived.id]


def test_restore_lookup_can_reach_archived_machine():
    db = make_db()
    org = models.Organization(name="Org")
    db.add(org)
    db.flush()
    machine = models.Machine(machine_code="A", name="A", organization_id=org.id, archived=True)
    db.add(machine)
    db.commit()
    current = CurrentUser(None, org.id, "admin", "admin")
    assert _get_machine_for_restore(db, machine.id, current).archived is True


def test_advanced_artifact_is_tenant_scoped():
    db = make_db()
    org1 = models.Organization(name="One")
    org2 = models.Organization(name="Two")
    db.add_all([org1, org2])
    db.flush()
    db.add(models.MLAdvancedArtifact(
        organization_id=org1.id,
        model_type="temporal_gbdt",
        model_version=1,
        artifact=b"{}",
        n_samples=1,
        n_positive=0,
        active=True,
        trained_at=datetime.utcnow(),
    ))
    db.commit()
    assert db.query(models.MLAdvancedArtifact).filter_by(
        organization_id=org2.id, active=True
    ).first() is None
