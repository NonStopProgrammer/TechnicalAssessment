from llm.guardrails.citation_verifier import strip_unverified_citations, verify_citations
from llm.guardrails.numeric_consistency import check_numeric_consistency
from llm.guardrails.pii_redaction import RegexPiiRedactor
from llm.guardrails.topical_rail import KeywordTopicalRail


def test_verify_citations_splits_verified_and_unverified():
    result = verify_citations(["doc_a::1@v1", "doc_x::9@v1"], {"doc_a::1@v1"})

    assert result.verified == ["doc_a::1@v1"]
    assert result.unverified == ["doc_x::9@v1"]
    assert not result.all_verified


def test_strip_unverified_citations_flags_but_keeps_the_rest():
    flagged = strip_unverified_citations("Rate is 4.5% [doc_x::9@v1].", ["doc_x::9@v1"])
    assert "UNVERIFIED CITATION" in flagged


def test_regex_pii_redactor_masks_email_and_pan():
    result = RegexPiiRedactor().redact("Contact jane.doe@example.com, PAN ABCDE1234F")

    assert result.has_pii
    assert "jane.doe@example.com" not in result.redacted_text
    assert "ABCDE1234F" not in result.redacted_text


def test_redact_dict_recurses_into_nested_structures():
    redactor = RegexPiiRedactor()
    redacted = redactor.redact_dict({"note": "email me at a@b.com", "nested": {"note": "call 9876543210"}})

    assert "a@b.com" not in redacted["note"]
    assert "9876543210" not in redacted["nested"]["note"]


def test_numeric_consistency_flags_unexplained_number():
    result = check_numeric_consistency("We reviewed 42 transactions.", {"total_transactions": 40})
    assert not result.is_consistent
    assert "42" in result.unexplained_numbers


def test_numeric_consistency_passes_when_narrative_matches_stats():
    result = check_numeric_consistency("We reviewed 40 transactions this quarter.", {"total_transactions": 40})
    assert result.is_consistent


def test_keyword_topical_rail_accepts_compliance_question():
    assert KeywordTopicalRail().is_in_scope("What is the Basel III capital adequacy requirement?")


def test_keyword_topical_rail_rejects_off_topic_question():
    assert not KeywordTopicalRail().is_in_scope("What's a good recipe for lasagna?")
