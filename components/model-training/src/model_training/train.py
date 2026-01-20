# components/model-training/src/model_training/train.py
from typing import Optional
from transformers import Trainer, TrainingArguments, DataCollatorForLanguageModeling, PreTrainedModel, PreTrainedTokenizer
from datasets import Dataset

def train_model(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizer,
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
