from joinpilot.agent.prompts import load_prompt
from joinpilot.agent.requirement import (
    describe_tables,
    fallback_parse,
    parse_requirement,
)
from joinpilot.llm.factory import UnavailableProvider
from joinpilot.llm.fake import FakeProvider
from joinpilot.profiling.models import ProjectProfile

REQUIREMENT = "Open receivables by customer and aging bucket, plus 2026 revenue by product group."


def test_prompt_files_render_with_their_placeholders() -> None:
    prompt = load_prompt("parse_requirement").render(requirement="R", tables="T")
    assert prompt.purpose == "parse_requirement"
    assert "Do not invent tables" in prompt.system
    assert "R" in prompt.user and "$" not in prompt.user


def test_table_description_shows_at_most_two_examples_per_column(
    sap_profile: ProjectProfile,
) -> None:
    text = describe_tables(sap_profile)
    assert "KNA1 (1000 rows)" in text
    kunnr = next(line for line in text.splitlines() if line.startswith("- KNA1"))
    assert kunnr.count("'0000") == 2


def test_model_answer_is_validated_against_known_tables(sap_profile: ProjectProfile) -> None:
    fake = FakeProvider().on(
        "parse_requirement",
        lambda p: {
            "summary": "Receivables aging and revenue",
            "entities": ["customer", "receivable"],
            "measures": [{"name": "open amount", "description": "sum of DMBTR"}],
            "dimensions": ["aging bucket"],
            "filters": [{"field": "year", "operator": "=", "value": "2026"}],
            "relevant_tables": ["bsid", "KNA1", "INVENTED"],
        },
    )
    parsed, warnings = parse_requirement(REQUIREMENT, sap_profile, fake)
    assert parsed.relevant_tables == ["BSID", "KNA1"]
    assert parsed.source == "llm"
    assert warnings == ["The model named a table that does not exist and it was ignored: INVENTED"]
    assert REQUIREMENT in fake.calls[0].user


def test_without_a_model_keywords_still_give_a_usable_parse(sap_profile: ProjectProfile) -> None:
    parsed, warnings = parse_requirement(REQUIREMENT, sap_profile, UnavailableProvider("no key"))
    assert parsed.source == "fallback"
    assert {"customer", "receivable", "sales order"} <= set(parsed.entities)
    assert [f.value for f in parsed.filters] == ["2026"]
    assert {"aging bucket", "product group"} <= set(parsed.dimensions)
    assert {m.name for m in parsed.measures} >= {"revenue", "open amount"}
    assert len(parsed.relevant_tables) == 6
    assert "no key" in warnings[0]


def test_fallback_handles_requirements_with_no_keywords(sap_profile: ProjectProfile) -> None:
    parsed = fallback_parse("Something entirely different", sap_profile)
    assert parsed.entities == [] and parsed.filters == []
