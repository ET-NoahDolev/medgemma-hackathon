# components/model-training/src/model_training/train.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol

try:
    from transformers import (  # type: ignore[import-not-found]
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments as _HfTrainingArguments,
    )
except ImportError:  # pragma: no cover
    Trainer: Any = object  # type: ignore[assignment, no-redef]
    DataCollatorForLanguageModeling: Any = object  # type: ignore[assignment, no-redef]
    _HfTrainingArguments: Any | None = None  # type: ignore[assignment, no-redef]

from model_training.dataset import Dataset


class _HasDevice(Protocol):
    device: Any


@dataclass
class TrainingArguments:
    """Fallback TrainingArguments for tests when transformers isn't installed."""

    output_dir: str
    num_train_epochs: int
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    learning_rate: float
    warmup_steps: int
    logging_steps: int
    save_steps: int
    fp16: bool

def train_model(
    model: Any,
    tokenizer: Any,
    train_dataset: Dataset,
    output_dir: str,
    num_epochs: int = 3,
    batch_size: int = 4,
    eval_dataset: Optional[Dataset] = None,
    learning_rate: float = 2e-4,
) -> None:
    """Fine-tune the model using the provided dataset.

    Args:
        model: The model to train (with LoRA applied).
        tokenizer: The tokenizer.
        train_dataset: Training dataset.
        output_dir: Directory to save the model.
        num_epochs: Number of training epochs.
        batch_size: Batch size per device.
        eval_dataset: Optional evaluation dataset.
        learning_rate: Learning rate.
    """
    if _HfTrainingArguments is not None:
        training_args: Any = _HfTrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=4,
            learning_rate=learning_rate,
            warmup_steps=100,
            logging_steps=10,
            save_steps=500,
            fp16=True,
        )
    else:
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=4,
            learning_rate=learning_rate,
            warmup_steps=100,
            logging_steps=10,
            save_steps=500,
            fp16=True,
        )

    data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )

    trainer.train()
    trainer.save_model(output_dir)


