# components/evaluation/tests/test_export.py
import pytest
import json
from pathlib import Path
from evaluation.export import export_training_data, TrainingExample


class TestExportTrainingData:
    def test_exports_jsonl_format(self, tmp_path):
        output = tmp_path / "train.jsonl"
        examples = [
            TrainingExample(
                criterion_text="Age >= 18",
                criterion_type="inclusion",
                snomed_codes=["371273006"],
                field_mapping="demographics.age|>=|18",
            )
        ]

        export_training_data(examples, output)

        assert output.exists()
        line = output.read_text().strip()
        data = json.loads(line)
        assert data["criterion_text"] == "Age >= 18"

    def test_each_line_is_valid_json(self, tmp_path):
        output = tmp_path / "train.jsonl"
        examples = [
            TrainingExample(criterion_text=f"Criterion {i}", criterion_type="inclusion", snomed_codes=[], field_mapping=None)
            for i in range(5)
        ]

        export_training_data(examples, output)

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 5
        for line in lines:
            json.loads(line)  # Should not raise

    def test_includes_all_required_fields(self, tmp_path):
        output = tmp_path / "train.jsonl"
        examples = [
            TrainingExample(
                criterion_text="Pregnant",
                criterion_type="exclusion",
                snomed_codes=["77386006"],
                field_mapping="conditions.pregnancy|=|true",
            )
        ]

        export_training_data(examples, output)

        data = json.loads(output.read_text().strip())
        assert "criterion_text" in data
        assert "criterion_type" in data
        assert "snomed_codes" in data
        assert "field_mapping" in data
