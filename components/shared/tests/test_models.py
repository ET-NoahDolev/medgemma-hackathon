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
        edit = build_hitl_edit(field_mapping_added="demographics.age|>=|18")

        assert edit.field_mapping_added == "demographics.age|>=|18"


class TestFieldMapping:
    def test_field_mapping_to_string(self) -> None:
        fm = build_field_mapping(field="demographics.age", relation=">=", value="18")

        assert fm.to_string() == "demographics.age|>=|18"

    def test_field_mapping_from_string(self) -> None:
        fm = FieldMapping.from_string("demographics.age|>=|18")

        assert fm.field == "demographics.age"
        assert fm.relation == ">="
        assert fm.value == "18"
