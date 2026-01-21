# components/evaluation/src/evaluation/export.py
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class TrainingExample:
    """Training example for LoRA fine-tuning."""
    criterion_text: str
    criterion_type: str
    snomed_codes: List[str]
    field_mapping: Optional[str]


def export_training_data(examples: List[TrainingExample], output_path: Path) -> None:
    """Export training examples to JSONL file.

    Args:
        examples: List of training examples.
        output_path: Path to output JSONL file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [json.dumps(asdict(ex)) for ex in examples]
    output_path.write_text("\n".join(lines) + "\n")


def export_from_database(db_path: str, output_path: Path) -> int:
    """Export accepted HITL edits as training data.

    Args:
        db_path: Path to SQLite database.
        output_path: Path to output JSONL file.

    Returns:
        Number of examples exported.
    """
    from sqlalchemy import create_engine
    from sqlmodel import Session, select

    # Import storage models (api-service is now a proper dependency)
    from api_service.storage import Criterion, HitlEdit

    engine = create_engine(f"sqlite:///{db_path}")
    examples: List[TrainingExample] = []

    with Session(engine) as session:
        # Get all accepted edits
        edits = session.exec(
            select(HitlEdit).where(HitlEdit.action == "accept")
        ).all()

        criterion_ids = {e.criterion_id for e in edits}

        for crit_id in criterion_ids:
            # Type ignore because session.get returns Optional[Criterion]
            criterion = session.get(Criterion, crit_id)
            if criterion:
                examples.append(
                    TrainingExample(
                        criterion_text=criterion.text,
                        criterion_type=criterion.criterion_type,
                        snomed_codes=criterion.snomed_codes,
                        field_mapping=None,  # TODO: extract from edits
                    )
                )

    export_training_data(examples, output_path)
    return len(examples)
