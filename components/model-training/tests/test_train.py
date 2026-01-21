# components/model-training/tests/test_train.py
from unittest.mock import patch, MagicMock
from model_training.train import train_model

@patch("model_training.train.Trainer")
@patch("model_training.train.DataCollatorForLanguageModeling")
def test_train_model(mock_data_collator_cls, mock_trainer_cls):
    model = MagicMock()
    tokenizer = MagicMock()
    train_dataset = MagicMock()
    output_dir = "models/test_model"
    
    mock_trainer = MagicMock()
    mock_trainer_cls.return_value = mock_trainer
    
    train_model(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        output_dir=output_dir,
        num_epochs=1,
        batch_size=2
    )
    
    # Check Trainer initialization
    mock_trainer_cls.assert_called_once()
    call_kwargs = mock_trainer_cls.call_args.kwargs
    assert call_kwargs["model"] == model
    assert call_kwargs["train_dataset"] == train_dataset
    assert call_kwargs["args"].output_dir == output_dir
    assert call_kwargs["args"].num_train_epochs == 1
    
    # Check Trainer methods called
    mock_trainer.train.assert_called_once()
    mock_trainer.save_model.assert_called_once_with(output_dir)
