"""Storage layer for the API service."""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from typing import Protocol as TypingProtocol

from sqlalchemy import JSON, Column, delete
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select


class ExtractedCriterion(TypingProtocol):
    """Protocol for extracted criteria returned by the pipeline."""

    text: str
    criterion_type: str
    confidence: float


class Protocol(SQLModel, table=True):  # type: ignore[call-arg]
    """Protocol record persisted for API requests."""

    id: str = Field(primary_key=True)
    title: str
    document_text: str
    nct_id: str | None = None
    condition: str | None = None
    phase: str | None = None


class Criterion(SQLModel, table=True):  # type: ignore[call-arg]
    """Criterion record persisted for API requests."""

    id: str = Field(primary_key=True)
    protocol_id: str = Field(foreign_key="protocol.id")
    text: str
    criterion_type: str
    confidence: float
    snomed_codes: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class HitlEdit(SQLModel, table=True):  # type: ignore[call-arg]
    """HITL edit record for tracking reviewer changes."""

    id: str = Field(primary_key=True)
    criterion_id: str = Field(foreign_key="criterion.id")
    action: str
    snomed_code_added: str | None = None
    snomed_code_removed: str | None = None
    field_mapping_added: str | None = None
    field_mapping_removed: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IdCounter(SQLModel, table=True):  # type: ignore[call-arg]
    """Simple counter table for stable prefixed identifiers."""

    key: str = Field(primary_key=True)
    value: int = 0


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[2] / ".data" / "api_service.db"
)


def _database_url() -> str:
    return os.getenv("API_SERVICE_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")


@lru_cache
def get_engine() -> Engine:
    """Create or return the cached database engine."""
    db_path = DEFAULT_DB_PATH
    if "API_SERVICE_DB_URL" not in os.environ:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        _database_url(),
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    """Initialize the database tables."""
    SQLModel.metadata.create_all(get_engine())


def reset_storage() -> None:
    """Clear all stored data (used for tests and demos)."""
    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def _next_id(session: Session, key: str, prefix: str) -> str:
    counter = session.get(IdCounter, key)
    if counter is None:
        counter = IdCounter(key=key, value=0)
        session.add(counter)
        session.flush()
    counter.value += 1
    session.add(counter)
    session.flush()
    return f"{prefix}-{counter.value}"


class Storage:
    """Repository wrapper around SQLModel sessions."""

    def __init__(self, engine: Engine) -> None:
        """Initialize the storage with a database engine."""
        self._engine = engine

    def create_protocol(
        self,
        *,
        title: str,
        document_text: str,
        nct_id: str | None = None,
        condition: str | None = None,
        phase: str | None = None,
    ) -> Protocol:
        """Persist a protocol record and return it."""
        with Session(self._engine) as session:
            protocol_id = _next_id(session, "protocol", "proto")
            protocol = Protocol(
                id=protocol_id,
                title=title,
                document_text=document_text,
                nct_id=nct_id,
                condition=condition,
                phase=phase,
            )
            session.add(protocol)
            session.commit()
            session.refresh(protocol)
            return protocol

    def get_protocol(self, protocol_id: str) -> Protocol | None:
        """Fetch a protocol by ID."""
        with Session(self._engine) as session:
            return session.get(Protocol, protocol_id)

    def list_criteria(self, protocol_id: str) -> list[Criterion]:
        """List criteria for a protocol."""
        with Session(self._engine) as session:
            statement = (
                select(Criterion)
                .where(Criterion.protocol_id == protocol_id)  # type: ignore[arg-type]
                .order_by(Criterion.id)
            )
            return list(session.exec(statement))

    def replace_criteria(
        self, *, protocol_id: str, extracted: Iterable[ExtractedCriterion]
    ) -> list[Criterion]:
        """Replace criteria for a protocol with extracted entries."""
        with Session(self._engine) as session:
            session.exec(
                delete(Criterion).where(
                    Criterion.protocol_id == protocol_id  # type: ignore[arg-type]
                )
            )
            stored: list[Criterion] = []
            for item in extracted:
                criterion_id = _next_id(session, "criterion", "crit")
                criterion = Criterion(
                    id=criterion_id,
                    protocol_id=protocol_id,
                    text=item.text,
                    criterion_type=item.criterion_type,
                    confidence=item.confidence,
                    snomed_codes=[],
                )
                session.add(criterion)
                stored.append(criterion)
            session.commit()
            return stored

    def update_criterion(
        self,
        *,
        criterion_id: str,
        text: str | None,
        criterion_type: str | None,
    ) -> Criterion | None:
        """Update a criterion's text/type and return the updated row."""
        with Session(self._engine) as session:
            criterion = session.get(Criterion, criterion_id)
            if criterion is None:
                return None
            if text is not None:
                criterion.text = text
            if criterion_type is not None:
                criterion.criterion_type = criterion_type
            session.add(criterion)
            session.commit()
            session.refresh(criterion)
            return criterion

    def get_criterion(self, criterion_id: str) -> Criterion | None:
        """Fetch a criterion by ID."""
        with Session(self._engine) as session:
            return session.get(Criterion, criterion_id)

    def set_snomed_codes(
        self, *, criterion_id: str, snomed_codes: list[str]
    ) -> Criterion | None:
        """Set SNOMED codes for a criterion."""
        with Session(self._engine) as session:
            criterion = session.get(Criterion, criterion_id)
            if criterion is None:
                return None
            criterion.snomed_codes = snomed_codes
            session.add(criterion)
            session.commit()
            session.refresh(criterion)
            return criterion

    def create_hitl_edit(
        self,
        *,
        criterion_id: str,
        action: str,
        snomed_code_added: str | None = None,
        snomed_code_removed: str | None = None,
        field_mapping_added: str | None = None,
        field_mapping_removed: str | None = None,
        note: str | None = None,
    ) -> HitlEdit:
        """Persist a HITL edit record."""
        with Session(self._engine) as session:
            edit_id = _next_id(session, "hitl_edit", "edit")
            edit = HitlEdit(
                id=edit_id,
                criterion_id=criterion_id,
                action=action,
                snomed_code_added=snomed_code_added,
                snomed_code_removed=snomed_code_removed,
                field_mapping_added=field_mapping_added,
                field_mapping_removed=field_mapping_removed,
                note=note,
            )
            session.add(edit)
            session.commit()
            session.refresh(edit)
            return edit

    def list_hitl_edits(self, criterion_id: str) -> list[HitlEdit]:
        """List all HITL edits for a criterion."""
        with Session(self._engine) as session:
            statement = (
                select(HitlEdit)
                .where(HitlEdit.criterion_id == criterion_id)  # type: ignore[arg-type]
                .order_by(HitlEdit.created_at)
            )
            return list(session.exec(statement))
