import pytest

from grounding_service.umls_client import FieldMappingSuggestion, propose_field_mapping


class TestFieldMappingAge:
    def test_age_greater_than(self) -> None:
        mappings = propose_field_mapping("Age > 18 years")
        assert len(mappings) >= 1
        assert mappings[0].field == "demographics.age"
        assert mappings[0].relation == ">"
        assert mappings[0].value == "18"

    def test_age_greater_equal(self) -> None:
        mappings = propose_field_mapping("Age >= 65")
        assert mappings[0].relation == ">="
        assert mappings[0].value == "65"

    def test_age_less_than(self) -> None:
        mappings = propose_field_mapping("Age < 75 years old")
        assert mappings[0].relation == "<"
        assert mappings[0].value == "75"

    def test_age_range(self) -> None:
        mappings = propose_field_mapping("Age 18-65 years")
        assert len(mappings) == 2


class TestFieldMappingBMI:
    def test_bmi_less_than(self) -> None:
        mappings = propose_field_mapping("BMI < 30")
        assert mappings[0].field == "vitals.bmi"
        assert mappings[0].relation == "<"
        assert mappings[0].value == "30"

    def test_bmi_decimal(self) -> None:
        mappings = propose_field_mapping("BMI <= 30.5")
        assert mappings[0].value == "30.5"


class TestFieldMappingECOG:
    def test_ecog_status(self) -> None:
        mappings = propose_field_mapping("ECOG performance status 0-1")
        assert mappings[0].field == "performance.ecog"

    def test_ecog_ps(self) -> None:
        mappings = propose_field_mapping("ECOG PS <= 2")
        assert mappings[0].field == "performance.ecog"
        assert mappings[0].relation == "<="
        assert mappings[0].value == "2"


class TestFieldMappingConditions:
    def test_pregnant(self) -> None:
        mappings = propose_field_mapping("Not pregnant or breastfeeding")
        assert any(m.field == "conditions.pregnancy" for m in mappings)

    def test_gender(self) -> None:
        mappings = propose_field_mapping("Female patients only")
        assert mappings[0].field == "demographics.sex"
        assert mappings[0].value.lower() == "female"


class TestFieldMappingNoMatch:
    def test_unrecognized_returns_empty(self) -> None:
        mappings = propose_field_mapping("Histologically confirmed melanoma")
        assert mappings == []

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            propose_field_mapping("")


def test_output_types() -> None:
    mappings = propose_field_mapping("Age > 18 years")
    assert all(isinstance(m, FieldMappingSuggestion) for m in mappings)
