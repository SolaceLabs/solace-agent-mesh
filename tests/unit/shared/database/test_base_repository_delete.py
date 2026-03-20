"""
Unit tests for BaseRepository.delete().

All tests use SQLite in-memory. The behaviours under test (relationship expiry,
cascade walking, with_for_update() invocation) are SQLAlchemy ORM-layer
concerns — they run in Python before any SQL is sent, so SQLite covers all
dialects.

Two concrete behaviours are tested:

1. with_for_update() is issued on the SELECT that fetches the row to delete.
2. uselist=True relationship collections are expired before session.delete()
   so SQLAlchemy re-fetches them before walking the cascade, preventing the
   same-session staleness bug where a child added after the collection was
   first accessed would be invisible to the cascade and block the DELETE.
"""

import uuid
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, String, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship

from solace_agent_mesh.shared.database.base_repository import BaseRepository
from solace_agent_mesh.shared.exceptions.exceptions import EntityNotFoundError

# ---------------------------------------------------------------------------
# Minimal in-memory models
# ---------------------------------------------------------------------------

_Base = declarative_base()


class _ParentModel(_Base):
    __tablename__ = "parents"
    id = Column(String, primary_key=True)
    # uselist=True — should be expired before cascade
    children = relationship("_ChildModel", cascade="all, delete-orphan", back_populates="parent")
    # uselist=False (scalar many-to-one) — should NOT be expired
    owner_id = Column(String, ForeignKey("owners.id"), nullable=True)
    owner = relationship("_OwnerModel", back_populates="parents")


class _ChildModel(_Base):
    __tablename__ = "children"
    id = Column(String, primary_key=True)
    parent_id = Column(String, ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    parent = relationship("_ParentModel", back_populates="children")


class _OwnerModel(_Base):
    __tablename__ = "owners"
    id = Column(String, primary_key=True)
    parents = relationship("_ParentModel", back_populates="owner")


class _ParentEntity(BaseModel):
    id: str


class _ParentRepository(BaseRepository[_ParentModel, _ParentEntity]):
    @property
    def entity_name(self) -> str:
        return "Parent"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(e)
    yield e
    _Base.metadata.drop_all(e)


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def repo():
    return _ParentRepository(_ParentModel, _ParentEntity)


def _new_parent():
    return _ParentModel(id=str(uuid.uuid4()))


def _new_child(parent_id):
    return _ChildModel(id=str(uuid.uuid4()), parent_id=parent_id)


def _new_owner():
    return _OwnerModel(id=str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeleteNotFound:

    def test_raises_for_nonexistent_id(self, repo, db):
        """EntityNotFoundError is raised when the row does not exist."""
        with pytest.raises(EntityNotFoundError):
            repo.delete(db, "nonexistent-id")

    def test_raises_after_already_deleted(self, repo, db):
        """A second delete on the same ID raises EntityNotFoundError."""
        parent = _new_parent()
        db.add(parent)
        db.flush()
        parent_id = parent.id

        repo.delete(db, parent_id)
        db.flush()

        with pytest.raises(EntityNotFoundError):
            repo.delete(db, parent_id)


class TestDeleteCascade:

    def test_deletes_parent_with_no_children(self, repo, db):
        """A parent with no children is removed from the session after delete."""
        parent = _new_parent()
        db.add(parent)
        db.flush()
        parent_id = parent.id

        repo.delete(db, parent_id)
        db.flush()

        assert db.get(_ParentModel, parent_id) is None

    def test_deletes_parent_and_its_children(self, repo, db):
        """Children are cascade-deleted along with the parent."""
        parent = _new_parent()
        child1 = _new_child(parent.id)
        child2 = _new_child(parent.id)
        db.add_all([parent, child1, child2])
        db.flush()
        parent_id, child1_id, child2_id = parent.id, child1.id, child2.id

        repo.delete(db, parent_id)
        db.flush()

        assert db.get(_ParentModel, parent_id) is None
        assert db.get(_ChildModel, child1_id) is None
        assert db.get(_ChildModel, child2_id) is None

    def test_deletes_parent_when_child_added_after_collection_was_cached(self, repo, db):
        """Same-session staleness: child added after collection was first accessed is still deleted.

        This is the core regression test. Without session.expire() on the
        children collection, the ORM would walk the cached empty list during
        the cascade and miss the child added afterwards, leaving an orphaned FK
        row that would block the parent DELETE on databases with strict FK
        enforcement (MySQL).
        """
        parent = _new_parent()
        db.add(parent)
        db.flush()

        # Access the collection now — SQLAlchemy caches an empty list.
        assert parent.children == []

        # Add a child in the same session AFTER the collection was cached.
        child = _new_child(parent.id)
        db.add(child)
        db.flush()

        # The cached collection still shows [] — but expire() forces a re-fetch
        # before the cascade walks it, so the child is included and deleted.
        repo.delete(db, parent.id)
        db.flush()

        assert db.get(_ParentModel, parent.id) is None
        assert db.get(_ChildModel, child.id) is None


class TestDeleteOrmBehaviour:

    def test_with_for_update_is_called_on_fetch_query(self, repo, db):
        """with_for_update() must be called on the query that fetches the row.

        This is a code-path assertion: the lock is issued as part of the
        SELECT, not separately. A regression here would mean the row is
        fetched without a lock before the DELETE.
        """
        parent = _new_parent()
        db.add(parent)
        db.flush()

        wfu_called = []
        original_query = db.query

        def tracking_query(model):
            q = original_query(model)

            class _TrackingQuery:
                def filter(self_, *args, **kwargs):
                    fq = q.filter(*args, **kwargs)

                    class _TrackingFilter:
                        def with_for_update(self__):
                            wfu_called.append(True)
                            return fq.with_for_update()

                        def first(self__):
                            return fq.first()

                    return _TrackingFilter()

            return _TrackingQuery()

        with patch.object(db, "query", side_effect=tracking_query):
            repo.delete(db, parent.id)

        assert wfu_called, "with_for_update() was not called on the fetch query"

    def test_only_collection_relationships_are_expired(self, repo, db):
        """Only uselist=True collections are expired; scalar refs are not.

        Expiring scalar (many-to-one / one-to-one) relationships would be
        unnecessary and could trigger unwanted lazy-loads. Only collections
        can suffer the staleness problem this fix addresses.
        """
        owner = _new_owner()
        parent = _new_parent()
        parent.owner_id = owner.id
        db.add_all([owner, parent])
        db.flush()

        expired_keys = []
        original_expire = db.expire

        def tracking_expire(instance, attrs=None):
            if attrs:
                expired_keys.extend(attrs)
            return original_expire(instance, attrs)

        with patch.object(db, "expire", side_effect=tracking_expire):
            repo.delete(db, parent.id)

        # uselist=True — must be expired so the cascade re-fetches it
        assert "children" in expired_keys, "children collection was not expired before cascade"
        # uselist=False — must NOT be expired (scalar ref, not a child collection)
        assert "owner" not in expired_keys, "scalar relationship 'owner' should not be expired"
