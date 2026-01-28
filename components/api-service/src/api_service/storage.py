"""Storage layer for the API service."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, cast
from typing import Protocol as TypingProtocol

from shared.models import Protocol as SharedProtocol
from sqlalchemy import JSON, Column, LargeBinary, delete, func, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Field, Session, SQLModel, col, create_engine, select


class ExtractedCriterion(TypingProtocol):
    """Protocol for extracted criteria returned by the pipeline."""

    text: str
    criterion_type: str
    confidence: float
    entity: str | None
    relation: str | None
    value: str | None
    unit: str | None


class Protocol(SQLModel, table=True):
    """Protocol record persisted for API requests."""

    id: str = Field(primary_key=True)
    title: str
    document_text: str
    pdf_bytes: bytes | None = Field(
        default=None, sa_column=Column(LargeBinary, nullable=True)
    )
    nct_id: str | None = None
    condition: str | None = None
    phase: str | None = None
    source: str | None = None
    registry_id: str | None = None
    registry_type: str | None = None
    # pending, extracting, grounding, completed, failed
    processing_status: str = Field(default="pending")
    progress_message: str | None = None
    processed_count: int = Field(default=0)
    total_estimated: int = Field(default=0)


class Criterion(SQLModel, table=True):
    """Criterion record persisted for API requests."""

    id: str = Field(primary_key=True)
    protocol_id: str = Field(foreign_key="protocol.id", index=True)
    text: str
    criterion_type: str
    confidence: float
    entity: str | None = None
    relation: str | None = None
    value: str | None = None
    unit: str | None = None
    umls_concept: str | None = None
    umls_id: str | None = None
    computed_as: str | None = None
    triplet_confidence: float | None = None
    grounding_confidence: float | None = None
    logical_operator: str | None = Field(
        default=None, description="AND/OR operator for multiple conditions"
    )
    hitl_status: str = Field(default="pending")
    hitl_entity: str | None = None
    hitl_relation: str | None = None
    hitl_value: str | None = None
    hitl_unit: str | None = None
    hitl_umls_concept: str | None = None
    hitl_umls_id: str | None = None
    hitl_snomed_code: str | None = None
    hitl_approved_at: datetime | None = None
    hitl_approved_by: str | None = None
    snomed_codes: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    grounding_terms: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="All grounding terms from AI grounding result",
    )
    evidence_spans: list[dict[str, object]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class HitlEdit(SQLModel, table=True):
    """HITL edit record for tracking reviewer changes."""

    id: str = Field(primary_key=True)
    criterion_id: str = Field(foreign_key="criterion.id", index=True)
    action: str
    snomed_code_added: str | None = None
    snomed_code_removed: str | None = None
    field_mapping_added: str | None = None
    field_mapping_removed: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[2] / ".data" / "api_service.db"
)


def _database_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("API_SERVICE_DB_URL")
        or f"sqlite:///{DEFAULT_DB_PATH}"
    )


@lru_cache
def get_engine() -> Engine:
    """Create or return the cached database engine."""
    db_path = DEFAULT_DB_PATH
    if "DATABASE_URL" not in os.environ and "API_SERVICE_DB_URL" not in os.environ:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        _database_url(),
        connect_args={"check_same_thread": False},
    )


def init_db() -> None:
    """Initialize the database tables."""
    # Ensure all models are registered in metadata
    # Reference models to trigger registration
    _ = Protocol, Criterion, HitlEdit

    engine = get_engine()
    try:
        SQLModel.metadata.create_all(engine)
    except OperationalError:
        # Tables may already exist (e.g. after reset_storage or parallel tests)
        pass
    _ensure_sqlite_protocol_progress_columns(engine)


def _ensure_sqlite_protocol_progress_columns(engine: Engine) -> None:
    """Ensure expected columns exist on the Protocol table for SQLite.

    SQLModel's `create_all()` does not add columns to existing tables. During
    local development, the persisted SQLite DB can drift behind the model
    definition, causing runtime 500s when selecting `Protocol` rows.
    """
    if engine.dialect.name != "sqlite":
        return

    with engine.connect() as conn:
        try:
            rows = conn.execute(text("PRAGMA table_info(protocol)")).fetchall()
        except OperationalError:
            # Table might not exist yet (should be rare because create_all runs first).
            return

        # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
        existing = {row[1] for row in rows}

        # NOTE: SQLite supports ADD COLUMN but has limitations; keep this minimal and
        # additive.
        migrations: list[str] = []
        if "pdf_bytes" not in existing:
            migrations.append(
                "ALTER TABLE protocol ADD COLUMN pdf_bytes BLOB NULL"
            )
        if "processing_status" not in existing:
            migrations.append(
                "ALTER TABLE protocol ADD COLUMN processing_status "
                "TEXT NOT NULL DEFAULT 'pending'"
            )
        if "progress_message" not in existing:
            migrations.append(
                "ALTER TABLE protocol ADD COLUMN progress_message "
                "TEXT NULL"
            )
        if "processed_count" not in existing:
            migrations.append(
                "ALTER TABLE protocol ADD COLUMN processed_count "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "total_estimated" not in existing:
            migrations.append(
                "ALTER TABLE protocol ADD COLUMN total_estimated "
                "INTEGER NOT NULL DEFAULT 0"
            )

        for statement in migrations:
            try:
                conn.execute(text(statement))
            except OperationalError:
                # If a concurrent process added the column first, ignore.
                continue
        conn.commit()

        _ensure_sqlite_criterion_columns(conn)


def _ensure_sqlite_criterion_columns(conn: Connection) -> None:
    try:
        rows = conn.execute(text("PRAGMA table_info(criterion)")).fetchall()
    except OperationalError:
        return

    existing = {row[1] for row in rows}
    column_statements = [
        ("entity", "ALTER TABLE criterion ADD COLUMN entity TEXT NULL"),
        ("relation", "ALTER TABLE criterion ADD COLUMN relation TEXT NULL"),
        ("value", "ALTER TABLE criterion ADD COLUMN value TEXT NULL"),
        ("unit", "ALTER TABLE criterion ADD COLUMN unit TEXT NULL"),
        ("umls_concept", "ALTER TABLE criterion ADD COLUMN umls_concept TEXT NULL"),
        ("umls_id", "ALTER TABLE criterion ADD COLUMN umls_id TEXT NULL"),
        ("computed_as", "ALTER TABLE criterion ADD COLUMN computed_as TEXT NULL"),
        (
            "triplet_confidence",
            "ALTER TABLE criterion ADD COLUMN triplet_confidence REAL NULL",
        ),
        (
            "grounding_confidence",
            "ALTER TABLE criterion ADD COLUMN grounding_confidence REAL NULL",
        ),
        (
            "hitl_status",
            "ALTER TABLE criterion ADD COLUMN hitl_status "
            "TEXT NOT NULL DEFAULT 'pending'",
        ),
        ("hitl_entity", "ALTER TABLE criterion ADD COLUMN hitl_entity TEXT NULL"),
        ("hitl_relation", "ALTER TABLE criterion ADD COLUMN hitl_relation TEXT NULL"),
        ("hitl_value", "ALTER TABLE criterion ADD COLUMN hitl_value TEXT NULL"),
        ("hitl_unit", "ALTER TABLE criterion ADD COLUMN hitl_unit TEXT NULL"),
        (
            "hitl_umls_concept",
            "ALTER TABLE criterion ADD COLUMN hitl_umls_concept TEXT NULL",
        ),
        ("hitl_umls_id", "ALTER TABLE criterion ADD COLUMN hitl_umls_id TEXT NULL"),
        (
            "hitl_snomed_code",
            "ALTER TABLE criterion ADD COLUMN hitl_snomed_code TEXT NULL",
        ),
        (
            "hitl_approved_at",
            "ALTER TABLE criterion ADD COLUMN hitl_approved_at TEXT NULL",
        ),
        (
            "hitl_approved_by",
            "ALTER TABLE criterion ADD COLUMN hitl_approved_by TEXT NULL",
        ),
        (
            "logical_operator",
            "ALTER TABLE criterion ADD COLUMN logical_operator TEXT NULL",
        ),
        (
            "grounding_terms",
            (
                "ALTER TABLE criterion ADD COLUMN grounding_terms "
                "TEXT NOT NULL DEFAULT '[]'"
            ),
        ),
    ]

    migrations = [
        statement for column, statement in column_statements if column not in existing
    ]

    for statement in migrations:
        try:
            conn.execute(text(statement))
        except OperationalError:
            continue
    conn.commit()


def reset_storage() -> None:
    """Clear all stored data (used for tests and demos)."""
    if os.getenv("ALLOW_STORAGE_RESET") != "1":
        raise RuntimeError(
            "reset_storage() requires ALLOW_STORAGE_RESET=1 environment variable. "
            "This function destroys all data and should only be used in tests."
        )
    # Ensure all models are registered in metadata before dropping
    _ = Protocol, Criterion, HitlEdit
    # Clear engine cache to ensure fresh engine for tests
    get_engine.cache_clear()
    engine = get_engine()
    # Drop all tables, ignoring errors if tables don't exist
    try:
        SQLModel.metadata.drop_all(engine)
    except OperationalError:
        # Tables might not exist yet, which is fine
        pass
    init_db()


def _generate_id(prefix: str) -> str:
    """Generate a unique identifier with prefix.

    Uses UUID4 for concurrency-safe distributed ID generation.

    Args:
        prefix: Prefix for the ID (e.g., "proto", "crit", "edit").

    Returns:
        A unique identifier in the format "{prefix}-{uuid}".

    Examples:
        >>> _generate_id("proto")
        'proto-550e8400-e29b-41d4-a716-446655440000'
    """
    return f"{prefix}-{uuid.uuid4().hex}"


def _norm_opt(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned if cleaned else None


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
        pdf_bytes: bytes | None = None,
        nct_id: str | None = None,
        condition: str | None = None,
        phase: str | None = None,
        source: str | None = None,
        registry_id: str | None = None,
        registry_type: str | None = None,
    ) -> Protocol:
        """Persist a protocol record and return it."""
        with Session(self._engine) as session:
            protocol_id = _generate_id("proto")
            protocol = Protocol(
                id=protocol_id,
                title=title.strip(),
                document_text=document_text,
                pdf_bytes=pdf_bytes,
                nct_id=_norm_opt(nct_id),
                condition=_norm_opt(condition),
                phase=_norm_opt(phase),
                source=_norm_opt(source),
                registry_id=_norm_opt(registry_id),
                registry_type=_norm_opt(registry_type),
                processing_status="pending",
                processed_count=0,
            )
            session.add(protocol)
            session.commit()
            session.refresh(protocol)
            return protocol

    def create_protocol_from_shared(
        self, shared: SharedProtocol, document_text: str, pdf_bytes: bytes | None = None
    ) -> Protocol:
        """Create a Protocol from a shared Protocol model and document text."""
        with Session(self._engine) as session:
            protocol_id = _generate_id("proto")
            protocol = Protocol(
                id=protocol_id,
                title=shared.title.strip(),
                document_text=document_text,
                pdf_bytes=pdf_bytes,
                nct_id=_norm_opt(getattr(shared, "nct_id", None)),
                condition=_norm_opt(getattr(shared, "condition", None)),
                phase=_norm_opt(getattr(shared, "phase", None)),
                source=_norm_opt(getattr(shared, "source", None)),
                registry_id=_norm_opt(getattr(shared, "registry_id", None)),
                registry_type=_norm_opt(getattr(shared, "registry_type", None)),
                processing_status="pending",
                processed_count=0,
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
            # Keep full models for simplicity; revisit partial selects if needed later.
            statement = (
                select(Criterion)
                .where(cast(Any, Criterion.protocol_id) == protocol_id)
                .order_by(Criterion.id)
            )
            return list(session.exec(statement))

    def count_criteria(self, protocol_id: str) -> int:
        """Return count of criteria for a protocol without loading all rows."""
        with Session(self._engine) as session:
            result = session.exec(
                select(func.count(col(Criterion.id))).where(
                    cast(Any, Criterion.protocol_id) == protocol_id
                )
            ).one()
            return int(result)

    def replace_criteria(
        self, *, protocol_id: str, extracted: Iterable[ExtractedCriterion]
    ) -> list[Criterion]:
        """Replace criteria for a protocol with extracted entries."""
        with Session(self._engine) as session:
            session.exec(
                delete(Criterion).where(cast(Any, Criterion.protocol_id) == protocol_id)
            )
            stored: list[Criterion] = []
            for item in extracted:
                criterion_id = _generate_id("crit")
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

    def update_criterion_hitl(
        self, *, criterion_id: str, updates: dict[str, object]
    ) -> Criterion | None:
        """Update HITL-related fields on a criterion."""
        with Session(self._engine) as session:
            criterion = session.get(Criterion, criterion_id)
            if criterion is None:
                return None
            for key, value in updates.items():
                if hasattr(criterion, key):
                    setattr(criterion, key, value)
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

    def add_snomed_code(self, criterion_id: str, code: str) -> Criterion | None:
        """Add a SNOMED code to a criterion."""
        with Session(self._engine) as session:
            criterion = session.get(Criterion, criterion_id)
            if criterion is None:
                return None
            if code not in criterion.snomed_codes:
                criterion.snomed_codes = [*criterion.snomed_codes, code]
                session.add(criterion)
                session.commit()
                session.refresh(criterion)
            return criterion

    def remove_snomed_code(self, criterion_id: str, code: str) -> Criterion | None:
        """Remove a SNOMED code from a criterion."""
        with Session(self._engine) as session:
            criterion = session.get(Criterion, criterion_id)
            if criterion is None:
                return None
            if code in criterion.snomed_codes:
                criterion.snomed_codes = [
                    existing for existing in criterion.snomed_codes if existing != code
                ]
                session.add(criterion)
                session.commit()
                session.refresh(criterion)
            return criterion

    def list_protocols(
        self, skip: int = 0, limit: int = 20
    ) -> tuple[list[Protocol], int]:
        """List protocols with pagination."""
        with Session(self._engine) as session:
            total = session.exec(select(func.count(col(Protocol.id)))).one()
            # Order by title for consistent ordering (UUIDs are not ordered)
            statement = (
                select(Protocol).offset(skip).limit(limit).order_by(Protocol.title)
            )
            protocols = list(session.exec(statement))
            return protocols, int(total)

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
            edit_id = _generate_id("edit")
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
                .where(cast(Any, HitlEdit.criterion_id) == criterion_id)
                .order_by(cast(Any, HitlEdit.created_at))
            )
            return list(session.exec(statement))

    def update_protocol_status(
        self,
        *,
        protocol_id: str,
        processing_status: str | None = None,
        progress_message: str | None = None,
        processed_count: int | None = None,
        total_estimated: int | None = None,
    ) -> Protocol | None:
        """Update protocol processing status and counts."""
        with Session(self._engine) as session:
            protocol = session.get(Protocol, protocol_id)
            if protocol is None:
                return None

            if processing_status is not None:
                protocol.processing_status = processing_status
            if progress_message is not None:
                protocol.progress_message = progress_message
            if processed_count is not None:
                protocol.processed_count = processed_count
            if total_estimated is not None:
                protocol.total_estimated = total_estimated

            session.add(protocol)
            session.commit()
            session.refresh(protocol)
            return protocol

    def add_criterion_streaming(
        self, *, protocol_id: str, text: str, criterion_type: str, confidence: float
    ) -> Criterion:
        """Add a single criterion during streaming extraction."""
        with Session(self._engine) as session:
            criterion_id = _generate_id("crit")
            criterion = Criterion(
                id=criterion_id,
                protocol_id=protocol_id,
                text=text,
                criterion_type=criterion_type,
                confidence=confidence,
                snomed_codes=[],
            )
            session.add(criterion)
            session.commit()
            session.refresh(criterion)
            return criterion

    def create_criterion_detail(
        self,
        *,
        protocol_id: str,
        text: str,
        criterion_type: str,
        confidence: float,
        entity: str | None = None,
        relation: str | None = None,
        value: str | None = None,
        unit: str | None = None,
        umls_concept: str | None = None,
        umls_id: str | None = None,
        computed_as: str | None = None,
        triplet_confidence: float | None = None,
        grounding_confidence: float | None = None,
        logical_operator: str | None = None,
        grounding_terms: list[dict[str, object]] | None = None,
        snomed_codes: list[str] | None = None,
        evidence_spans: list[dict[str, object]] | None = None,
    ) -> Criterion:
        """Create a criterion record with detailed extraction fields."""
        with Session(self._engine) as session:
            criterion_id = _generate_id("crit")
            criterion = Criterion(
                id=criterion_id,
                protocol_id=protocol_id,
                text=text,
                criterion_type=criterion_type,
                confidence=confidence,
                entity=entity,
                relation=relation,
                value=value,
                unit=unit,
                umls_concept=umls_concept,
                umls_id=umls_id,
                computed_as=computed_as,
                triplet_confidence=triplet_confidence,
                grounding_confidence=grounding_confidence,
                logical_operator=logical_operator,
                grounding_terms=grounding_terms or [],
                snomed_codes=snomed_codes or [],
                evidence_spans=evidence_spans or [],
            )
            session.add(criterion)
            session.commit()
            session.refresh(criterion)
            return criterion
