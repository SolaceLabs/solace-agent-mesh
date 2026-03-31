import logging

from solace_agent_mesh.shared.api.pagination import PaginationParams
from sqlalchemy.orm import Session

from ..database import generate_uuidv7
from .entity import OutboxEventEntity
from .models import (
    CreateOutboxEventModel,
    OutboxEventModel,
    UpdateOutboxEventModel,
)

log = logging.getLogger(__name__)


class OutboxEventRepository:

    def create_event(self, session: Session, data: CreateOutboxEventModel) -> OutboxEventEntity:
        event = OutboxEventModel(
            id=generate_uuidv7(),
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            event_type=data.event_type,
            payload=data.payload,
            status=data.status,
            next_retry_at=data.next_retry_at,
        )
        session.add(event)
        session.flush()
        return OutboxEventEntity.model_validate(event)

    def create_events_batch(self, session: Session, events: list[CreateOutboxEventModel]) -> list[OutboxEventEntity]:
        db_events = []
        for data in events:
            event = OutboxEventModel(
                id=generate_uuidv7(),
                entity_type=data.entity_type,
                entity_id=data.entity_id,
                event_type=data.event_type,
                payload=data.payload,
                status=data.status,
                next_retry_at=data.next_retry_at,
            )
            session.add(event)
            db_events.append(event)
        session.flush()
        return [OutboxEventEntity.model_validate(e) for e in db_events]

    def get_pending_events(self, session: Session, now_ms: int, limit: int = 50) -> list[OutboxEventEntity]:
        rows = (
            session.query(OutboxEventModel)
            .filter(
                OutboxEventModel.status == "pending",
                OutboxEventModel.next_retry_at <= now_ms,
            )
            .order_by(OutboxEventModel.created_time.asc())
            .limit(limit)
            .all()
        )
        return [OutboxEventEntity.model_validate(r) for r in rows]

    def has_pending_event(
        self, session: Session, entity_type: str, entity_id: str, event_type: str
    ) -> bool:
        return (
            session.query(OutboxEventModel)
            .filter(
                OutboxEventModel.entity_type == entity_type,
                OutboxEventModel.entity_id == entity_id,
                OutboxEventModel.event_type == event_type,
                OutboxEventModel.status == "pending",
            )
            .first()
            is not None
        )

    def update_event(self, session: Session, event_id: str, data: UpdateOutboxEventModel) -> OutboxEventEntity:
        event = session.query(OutboxEventModel).filter(OutboxEventModel.id == event_id).first()
        if event is None:
            raise ValueError(f"Outbox event not found: {event_id}")

        update_fields = data.model_dump(exclude_none=True)
        for field, value in update_fields.items():
            setattr(event, field, value)
        session.flush()
        return OutboxEventEntity.model_validate(event)

    def get_event_by_id(self, session: Session, event_id: str) -> OutboxEventEntity | None:
        event = session.query(OutboxEventModel).filter(OutboxEventModel.id == event_id).first()
        if event is None:
            return None
        return OutboxEventEntity.model_validate(event)

    def get_events_paginated(
        self,
        session: Session,
        pagination: PaginationParams,
        status_filter: str | None = None,
        entity_type_filter: str | None = None,
    ) -> tuple[list[OutboxEventEntity], int]:
        query = session.query(OutboxEventModel)

        if status_filter:
            query = query.filter(OutboxEventModel.status == status_filter)
        if entity_type_filter:
            query = query.filter(OutboxEventModel.entity_type == entity_type_filter)

        total_count = query.count()

        offset = (pagination.page_number - 1) * pagination.page_size
        results = (
            query.order_by(OutboxEventModel.created_time.desc())
            .offset(offset)
            .limit(pagination.page_size)
            .all()
        )

        return [OutboxEventEntity.model_validate(r) for r in results], total_count

    def bulk_deduplicate_events(self, session: Session, event_ids: list[str]) -> set[str]:
        if not event_ids:
            return set()

        events = (
            session.query(OutboxEventModel)
            .filter(
                OutboxEventModel.id.in_(event_ids),
                OutboxEventModel.status == "pending",
            )
            .order_by(OutboxEventModel.created_time.desc())
            .all()
        )

        groups: dict[tuple[str, str], list[OutboxEventModel]] = {}
        for event in events:
            key = (event.entity_type, event.entity_id)
            groups.setdefault(key, []).append(event)

        deduplicated_ids: set[str] = set()
        for group_events in groups.values():
            if len(group_events) <= 1:
                continue
            for older in group_events[1:]:
                older.status = "skipped"
                older.error_message = "Deduplicated by newer event (bulk)"
                deduplicated_ids.add(older.id)

        if deduplicated_ids:
            session.flush()
        return deduplicated_ids

    def deduplicate_stale_events(
        self, session: Session, event_id: str, entity_type: str, entity_id: str
    ) -> bool:
        pending_events = (
            session.query(OutboxEventModel)
            .filter(
                OutboxEventModel.entity_type == entity_type,
                OutboxEventModel.entity_id == entity_id,
                OutboxEventModel.status == "pending",
            )
            .order_by(OutboxEventModel.created_time.desc())
            .all()
        )
        if len(pending_events) <= 1:
            return True

        latest_id = pending_events[0].id
        if event_id != latest_id:
            return False

        for older in pending_events[1:]:
            older.status = "skipped"
            older.error_message = "Deduplicated by newer event"
        session.flush()
        return True

    def cleanup_old_events(self, session: Session, older_than_ms: int) -> int:
        count = (
            session.query(OutboxEventModel)
            .filter(
                OutboxEventModel.status.in_(["completed", "error", "skipped"]),
                OutboxEventModel.updated_time < older_than_ms,
            )
            .delete(synchronize_session=False)
        )
        session.flush()
        return count
