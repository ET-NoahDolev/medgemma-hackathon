from shared.models import (
    EvidenceSpan,
    FieldMapping,
    build_criterion,
    build_field_mapping,
    build_hitl_edit,
    build_protocol,
)


class TestEvidenceSpan:
    def test_evidence_span_has_required_fields(self) -> None:
        span = EvidenceSpan(start_char=0, end_char=50, source_doc_id="doc-1")

        assert span.start_char == 0
        assert span.end_char == 50
        assert span.source_doc_id == "doc-1"


class TestCriterion:
    def test_criterion_has_evidence_spans_field(self) -> None:
        crit = build_criterion()

        assert hasattr(crit, "evidence_spans")
        assert isinstance(crit.evidence_spans, list)


class TestProtocol:
    def test_protocol_has_nct_id(self) -> None:
        proto = build_protocol(nct_id="NCT12345678")

        assert proto.nct_id == "NCT12345678"

    def test_protocol_has_condition(self) -> None:
        proto = build_protocol(condition="Melanoma")

        assert proto.condition == "Melanoma"

    def test_protocol_has_phase(self) -> None:
        proto = build_protocol(phase="Phase 2")

        assert proto.phase == "Phase 2"


class TestHitlEdit:
    def test_hitl_edit_tracks_snomed_added(self) -> None:
        edit = build_hitl_edit(snomed_code_added="371273006")

        assert edit.snomed_code_added == "371273006"

    def test_hitl_edit_tracks_snomed_removed(self) -> None:
        edit = build_hitl_edit(snomed_code_removed="371273006")

        assert edit.snomed_code_removed == "371273006"

    def test_hitl_edit_has_field_mapping_changes(self) -> None:
        field_mapping_json = '{"field":"demographics.age","relation":">=","value":"18"}'
        edit = build_hitl_edit(field_mapping_added=field_mapping_json)

        assert edit.field_mapping_added == field_mapping_json


class TestFieldMapping:
    def test_field_mapping_to_string(self) -> None:
        fm = build_field_mapping(field="demographics.age", relation=">=", value="18")

        result = fm.to_string()
        # Should be JSON format
        assert result.startswith("{")
        assert '"field":"demographics.age"' in result
        assert '"relation":">="' in result
        assert '"value":"18"' in result

    def test_field_mapping_from_string_json(self) -> None:
        """Test deserialization from JSON format."""
        json_str = '{"field":"demographics.age","relation":">=","value":"18"}'
        fm = FieldMapping.from_string(json_str)

        assert fm.field == "demographics.age"
        assert fm.relation == ">="
        assert fm.value == "18"

    def test_field_mapping_from_string_legacy(self) -> None:
        """Test backward compatibility with pipe-delimited format."""
        fm = FieldMapping.from_string("demographics.age|>=|18")

        assert fm.field == "demographics.age"
        assert fm.relation == ">="
        assert fm.value == "18"

    def test_field_mapping_round_trip(self) -> None:
        """Test that serialization and deserialization work correctly."""
        original = build_field_mapping(field="test.field", relation=">", value="100")
        serialized = original.to_string()
        deserialized = FieldMapping.from_string(serialized)

        assert deserialized.field == original.field
        assert deserialized.relation == original.relation
        assert deserialized.value == original.value

    def test_field_mapping_with_pipe_in_value(self) -> None:
        """Test that values containing pipe characters are handled correctly."""
        fm = FieldMapping(field="test.field", relation="=", value="value|with|pipes")
        serialized = fm.to_string()
        deserialized = FieldMapping.from_string(serialized)

        assert deserialized.value == "value|with|pipes"
