# NAWA evaluation suites (P1-02)

Code: `src/nawa/evaluation/suites/<suite>.py`. Each module provides `generate(rng, n, split)`, `score(item, output)`, and `oracle(item)`.
Build the public splits:

```bash
python -m nawa.evaluation.build --split dev   --out eval/build
python -m nawa.evaluation.build --split calib --out eval/build
```

`eval/build/` is git-ignored. The splits are regenerated deterministically from public seeds (`dev=1001`, `calib=2002`). The `frozen` split is built under P1-03 from a secret random seed and a private factual bank, is stored only in the private HF repo `vuuuv/nawa-eval`, and is pinned in Git by `eval/FROZEN.sha256`.

## Design principles

- **Verifiable gold.** Every item has a machine-checkable answer. Numbers are computed, code is executed against tests computed from a reference solution, and context answers come from a generated context.
- **Fictional entities.** Context-based suites use invented towns, rivers, and people built from syllables (`synth.py`). A model cannot answer from memory, so a correct answer must come from the context, and a wrong one is a hallucination.
- **No overlap.** Items are de-duplicated by `content_hash` (a hash of the messages). calib excludes dev, and frozen excludes dev and calib.
- **Taxonomy-linked failures.** Every failed item carries an FT-xx id from `docs/failure_taxonomy.md`.
- **Tests guard the scorers.** The oracle must score 100%, and noise answers (empty, random, "42") must score at most 5% (0% for tool_use). See `tests/test_eval_suites.py`.

## Suites

| Suite | Items dev/calib/frozen | What it measures | Per-item fields | Failure ids |
|---|---|---|---|---|
| faithfulness | 30/15/30 | Answering from a numbered context that holds two similar towns, then citing the supporting sentence `[n]` | `correct`, `hallucinated`, `citation_correct` | FT-12, FT-07, FT-13 |
| abstention | 15/8/15 twin pairs (×2 items) | The same question with and without evidence. The unanswerable twin keeps a *distractor* town that has the asked attribute. | `correct`, `abstained`, `answerable` | FT-13, FT-14 |
| factual | 30/15/30 | Closed-book questions on stable facts, scored against an authored answer key with aliases. dev/calib come from `factual_bank.yaml`; frozen comes from a private bank. | `correct`, `abstained`, `hallucinated` | FT-11, FT-13 |
| reasoning_math | 30/15/30 | Multi-step Arabic word problems with integer answers. The answer is taken from the final `الجواب:` line. | `correct` | FT-03 |
| code | 20/10/20 | Python functions run against hidden tests in `sandbox.py`. 20% of items are fake-package traps, where the model must not import the package and must either flag it or solve without it. | `correct`, `kind` | FT-04 |
| tool_use | 24/12/24 (balanced) | Picking a tool: calculator / search / python / none | `correct`, `predicted` | FT-16, FT-06 |
| robustness | 24/12/24 | A prompt injection inside the context, a false premise, and sycophancy under wrong pushback | `correct`, `kind` | FT-10, FT-05, FT-08 |
| arabic | 30/18/30 | The same context QA asked in MSA, Gulf, Egyptian, Levantine, Arabizi, and code-switched registers | `correct`, `register` | FT-15 |
| regression_general | 25/15/25 | Format following, word counting, sorting, extraction, unit conversion, comparison | `correct`, `kind` | FT-09 |
| domain | — | **BLOCKED (P1-02a) until the owner picks the first domain (OD-01)** | — | — |

## Suite metrics (computed by `eval/report.py`, P1-07)

- `accuracy` = the mean of `correct`, for every suite.
- `hallucination_rate` = the mean of `hallucinated`, meaning the model answered (did not abstain) and was wrong. This applies to faithfulness, factual, and abstention (the unanswerable twins), and is the basis of **T1**.
- `abstention_recall` = the share of unanswerable abstention twins where the model correctly abstained (**T2**).
- `answerable_accuracy` = accuracy on the answerable twins. **T2** limits how much this may drop.
- `citation_accuracy` = the mean of `citation_correct` on faithfulness. It is reported separately from answer accuracy, as **T6** requires.
- Per-register accuracy for `arabic`, and per-kind accuracy for `robustness`, `code`, and `regression_general`.

## Known limitations

- Scoring is lenient string matching after Arabic normalisation. Answers written as number words, such as "خمسة وأربعون ألفًا", count as misses.
- The synthetic templates are shared across splits, so frozen is held-out in values and entities, but not in templates.
- The factual bank was authored by the bootstrap agent and is `agent_authored_pending_human_review`.
- `sandbox.py` provides process-level isolation only (see its docstring). A stronger sandbox is planned in P6-02.
- The suites are small (about 240 dev items), which is enough to establish baselines. Confidence intervals must be reported.
