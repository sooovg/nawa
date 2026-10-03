"""Owner directive of 2026-09-30 (ADR-0003, R-02): NAWA is an original system; no external model or
external baseline is a condition for progress. These checks keep ROADMAP.md and AGENTS.md from drifting back."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
EXTERNAL = re.compile(r"qwen|llama|mistral|gemma|smollm|phi-\d|open[- ]weight|مفتوح(?:ة)? الأوزان|نماذج مفتوحة", re.I)


def status(tid: str) -> str:
    m = re.search(rf"^\| {re.escape(tid)} \| (\w+) \|", ROADMAP, flags=re.M)
    assert m, tid
    return m[1]


def test_goal_is_an_original_system_in_both_files() -> None:
    assert "الهدف هو ابتكار وبناء نظام أصلي" in ROADMAP
    assert "ابتكار وبناء نظام أصلي" in AGENTS
    for text in (ROADMAP, AGENTS):
        assert "لا توجد مهمة إلزامية لتشغيل" in text
        assert "ADR-0003" in text


def test_external_model_tasks_are_superseded() -> None:
    assert status("P1-04") == "SUPERSEDED"
    assert status("P1-05") == "SUPERSEDED"


def test_no_gate_definition_requires_an_external_model() -> None:
    phases = ROADMAP[ROADMAP.index("# 4. مراحل التنفيذ والبوابات"):ROADMAP.index("# 5. قواعد Git")]
    for m in re.finditer(r"^### (G\d+)[^\n]*\n(.*?)(?=^#{2,3} |\Z)", phases, flags=re.M | re.S):
        assert not EXTERNAL.search(m[2]), f"{m[1]} mentions an external/open-weight model as a condition"


def test_optional_track_b_tasks_are_marked_not_gate_conditions() -> None:
    assert "المهام P5-05..P5-08 **ليست شرطًا لـ G5**" in ROADMAP
    t3 = re.search(r"^\| T3 \|.*$", ROADMAP, flags=re.M)[0]
    assert "اختياري" in t3 and "لا شرط لأي بوابة" in t3


def test_baseline_means_internal_reference() -> None:
    assert "كلمة baseline في هذه الخارطة تعني مرجعًا داخليًا لـ NAWA" in ROADMAP


def test_agent_count_is_not_fixed() -> None:
    assert "176" not in AGENTS
    assert "عدد الوكلاء متغير" in AGENTS


def test_reference_core_default_config_is_pinned() -> None:
    """ADR-0007 D4: no P4 technique is adopted by silently changing the reference core default."""
    import pytest
    pytest.importorskip("torch")
    from nawa.model import DecoderConfig
    assert DecoderConfig.from_yaml(ROOT / "configs/base_model.yaml").config_hash() == "918f4cf4877c0cca"


def test_track_s_packages_import_no_external_model_libraries() -> None:
    """ADR-0007 D4, ADR-0008 D2 / AGENTS.md §3: Track S code (model, training, tokenizer, efficiency, and the P6
    packages) is written from scratch. P6 packages that do not exist yet are checked once they are created."""
    import ast
    banned = {"transformers", "huggingface_hub", "tokenizers", "sentencepiece", "tiktoken", "peft", "accelerate",
              "datasets", "safetensors", "timm", "vllm", "llama_cpp", "bitsandbytes", "xformers"}
    for pkg in ("model", "training", "tokenizer", "efficiency",
                "retrieval", "tools", "reasoning", "verification", "abstention", "routing", "pipeline", "memory"):
        for path in sorted((ROOT / "src/nawa" / pkg).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
                for name in names:
                    assert name.split(".")[0] not in banned, f"{path.relative_to(ROOT)} imports {name}"


P6_PACKAGES = ("retrieval", "tools", "reasoning", "verification", "abstention", "routing", "pipeline",
               "memory")  # memory: P7-05 under ADR-0009 D2 (no external model, no network, no Hugging Face)
P6_BANNED = {
    # external models as generator, verifier, judge or reviewer (OD-10)
    "openai", "anthropic", "cohere", "mistralai", "litellm", "langchain", "langchain_core", "llama_index",
    "sentence_transformers", "google", "vertexai", "groq", "together", "replicate",
    # network access (search and external APIs are P6-02a, BLOCKED on OD-11)
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp", "websockets", "ftplib", "smtplib",
}


def _imports(path: Path) -> list[str]:
    import ast
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            out.append(node.module or "")
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in {
                "__import__", "import_module"} and node.args and isinstance(node.args[0], ast.Constant):
            out.append(str(node.args[0].value))
    return out


def test_p6_packages_use_no_external_model_and_no_network() -> None:
    """ADR-0008 D2: P6 code-only work uses no external model (OD-10) and no network (OD-11). Packages that do not
    exist yet are checked once they are created."""
    for pkg in P6_PACKAGES:
        for path in sorted((ROOT / "src/nawa" / pkg).rglob("*.py")):
            for name in _imports(path):
                assert name.split(".")[0] not in P6_BANNED, f"{path.relative_to(ROOT)} imports {name}"


def test_p6_import_rule_is_not_vacuous(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("import importlib\nfrom urllib.request import urlopen\nimport openai\n"
                   "m = importlib.import_module('requests')\n", encoding="utf-8")
    assert {n.split(".")[0] for n in _imports(bad)} >= {"urllib", "openai", "requests"}


def test_memory_package_exists_and_is_covered_by_the_import_rules() -> None:
    """ADR-0009 D2: the first P7 task that creates a package extends both import rules to it (non-vacuous)."""
    files = sorted((ROOT / "src/nawa/memory").glob("*.py"))
    assert {f.name for f in files} >= {"types.py", "store.py", "orchestrator.py", "policy.py", "consolidation.py",
                                      "forgetting.py", "provenance.py", "isolation.py", "replay.py"}
    assert "memory" in P6_PACKAGES
    imported = {n.split(".")[0] for f in files for n in _imports(f)}
    assert imported and not imported & P6_BANNED and "huggingface_hub" not in imported
