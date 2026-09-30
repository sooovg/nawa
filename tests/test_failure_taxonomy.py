"""P1-01: failure taxonomy completeness and format."""

from nawa.evaluation.taxonomy import by_name, load_taxonomy

REQUIRED_BY_P1_01 = {  # ROADMAP P1-01 list, in order
    "fabricated_source", "wrong_number", "calculation_error", "hallucinated_api", "false_premise_accepted",
    "stale_knowledge", "entity_conflation", "sycophancy", "context_loss", "prompt_injection_followed", "overconfidence",
}
KNOWN_SUITES = {"faithfulness", "abstention", "factual", "reasoning_math", "code", "tool_use",
                "domain", "robustness", "arabic", "regression_general", "multimodal"}


def test_all_required_categories_present() -> None:
    names = {c.name_en for c in load_taxonomy().values()}
    assert REQUIRED_BY_P1_01 <= names


def test_ids_are_sequential_and_unique() -> None:
    ids = list(load_taxonomy())
    assert ids == [f"FT-{i:02d}" for i in range(1, len(ids) + 1)]


def test_each_category_is_complete_and_maps_to_known_suites() -> None:
    for c in load_taxonomy().values():
        assert c.name_ar and c.definition and c.detection, c.id
        assert set(c.suites) <= KNOWN_SUITES, (c.id, c.suites)


def test_lookup_by_name() -> None:
    assert by_name("prompt_injection_followed").id == "FT-10"
