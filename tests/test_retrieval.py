"""P6-01: chunker, lexical index, metadata filters, lexical reranker (ADR-0008).

Pass/fail criteria, written before the run:

R1. Chunker invariants on 300 seeded synthetic texts (Arabic and Latin) and on hand-written edge cases:
    - every chunk equals ``text[start:end]``;
    - no chunk is empty or longer than ``max_chars``;
    - with ``overlap=0``, every non-space character is in exactly one chunk, in order;
    - no chunk spans a blank line.
    Hand-written boundaries:
    - a decimal point (Latin or Arabic-Indic) never ends a sentence;
    - ``؟ ؛ ! … .`` end sentences;
    - a hard cut never separates a letter from its harakat, a ZWJ sequence or a variation selector.
R2. BM25 scores and ranking equal an independently written brute-force computation (1e-12) on seeded random corpora
    and queries. A chunk that shares no term is never returned.
R3. Ordering and determinism:
    - results and the manifest do not depend on document input order;
    - equal scores are ordered by chunk id;
    - two builds are byte-identical.
R4. Repetition and duplicates:
    - the score rises with term frequency but stays below ``idf·(k1+1)``;
    - exact and normalisation-equivalent duplicate chunks are indexed once and listed, never dropped silently;
    - a filter falls back to a passing duplicate.
R5. Unicode and synthetic Arabic: harakat, tatweel, hamza forms, Arabic-Indic digits, NFC/NFD and the ``ال`` prefix
    match as the analyzer documents.
R6. Rebuild and verify:
    - save → load → identical results;
    - ``verify`` against a rebuild is empty;
    - every tampering is detected: file content, postings, a document's text, its metadata, the settings.
R7. Metadata only filters and never changes a score; freshness needs an explicit date (no wall clock).
R8. The reranker only reorders (checked), puts phrase matches first, and is deterministic. Retrieved chunks work as
    P6-04 evidence end to end.

Synthetic text only (invented words); no real data or books; no network; no retrieval-quality claim.
"""

from __future__ import annotations

import json
import math
import random
import unicodedata
from collections import Counter

import pytest

from nawa.abstention import Action, decide
from nawa.retrieval import (Document, Filter, LexicalIndex, LexicalReranker, SourceQuality, analyze, apply_reranker,
                            chunk_document, to_evidence, verify)
from nawa.retrieval.index import B, K1
from nawa.verification import QuoteChecker, TextClaim, VerificationState, check

AR = ["سَلْمور", "قِنْطار", "بَرْزان", "المِرْفاد", "تولين", "زَهْران", "كُوفار", "الدِّرْميس", "نَعْسال", "ميرون"]
LA = ["valmor", "quintel", "borzan", "teliva", "marfad", "zorwin", "kufar", "nesral", "dormis", "loquen"]
ENDS = [".", "؟", "!", "؛", ".", "…"]


def synth_text(rng: random.Random) -> str:
    words = AR if rng.random() < 0.5 else LA
    paras = []
    for _ in range(rng.randint(1, 3)):
        sents = []
        for _ in range(rng.randint(1, 6)):
            w = [rng.choice(words) for _ in range(rng.randint(1, 14))]
            if rng.random() < 0.2:
                w.insert(rng.randrange(len(w) + 1), rng.choice(["3.5", "٣.٥", "12"]))
            if rng.random() < 0.05:
                w.append("x" * rng.randint(30, 90))            # a word longer than max_chars
            sents.append(" ".join(w) + rng.choice(ENDS))
        paras.append(" ".join(sents))
    return "\n\n".join(paras)


def synth_corpus(rng: random.Random, n: int) -> list[Document]:
    return [Document(f"d{i:03d}", synth_text(rng), source=f"syn:{i}", published=f"2026-0{1 + i % 9}-1{i % 10}",
                     quality=list(SourceQuality)[i % 4]) for i in range(n)]


# ==== R1 chunker ====================================================================================================
def check_chunk_invariants(doc: Document, max_chars: int, overlap: int) -> None:
    chunks = chunk_document(doc, max_chars, overlap)
    text = doc.text
    for c in chunks:
        assert c.text == text[c.start:c.end] and c.text and len(c.text) <= max_chars
        assert c.text == c.text.strip() and "\n\n" not in c.text.replace("\r", "")
    assert [c.chunk_id for c in chunks] == [f"{doc.doc_id}#{i}" for i in range(len(chunks))]
    assert [c.start for c in chunks] == sorted(c.start for c in chunks)
    covered = Counter(i for c in chunks for i in range(c.start, c.end) if not text[i].isspace())
    nonspace = [i for i, ch in enumerate(text) if not ch.isspace()]
    assert set(covered) == set(nonspace)
    if overlap == 0:
        assert all(v == 1 for v in covered.values())
        assert all(a.end <= b.start for a, b in zip(chunks, chunks[1:]))
    assert chunks == chunk_document(doc, max_chars, overlap)


def test_chunker_invariants_on_synthetic_texts() -> None:
    rng = random.Random(0)
    for i in range(300):
        doc = Document(f"t{i}", synth_text(rng))
        check_chunk_invariants(doc, rng.choice([8, 20, 40, 120, 400]), rng.choice([0, 0, 1, 2]))


def sentences_of(text: str, max_chars: int = 400) -> list[str]:
    return [c.text for c in chunk_document(Document("x", text), max_chars)]


def test_sentence_boundaries() -> None:
    assert sentences_of("القيمة ٣.٥ متر. والثانية 2.75 كم؟ نعم؛ ربما… لا!", 17) == [
        "القيمة ٣.٥ متر.", "والثانية 2.75 كم؟", "نعم؛ ربما… لا!"]
    assert sentences_of("نعم؛لا!بلى…كلا؟هو.", 8) == ["نعم؛لا!", "بلى…كلا؟", "هو."]   # no spaces: marks alone end
    assert sentences_of("a b. c d.\n\ne f.", 400) == ["a b. c d.", "e f."]          # paragraphs never merge
    assert sentences_of("", 40) == [] and sentences_of(" \n\n \t ", 40) == []
    assert sentences_of("v1.2 is out. ok", 400) == ["v1.2 is out. ok"]
    assert sentences_of("aaa bbb ccc ddd", 8) == ["aaa bbb", "ccc ddd"]           # long sentence: split at spaces


def test_sentence_units_directly() -> None:
    """Found by surviving mutations: packing can hide a wrong split, so check the sentence units themselves."""
    from nawa.retrieval.chunker import _sentences
    t = "القيمة ٣.٥ متر. والثانية 2.75 كم؟ نعم؛ ربما… لا!"
    assert [t[s:e] for s, e, _ in _sentences(t)] == ["القيمة ٣.٥ متر.", "والثانية 2.75 كم؟", "نعم؛", "ربما…", "لا!"]
    t2 = "abc  \n\n  def  "
    assert [(t2[s:e], p) for s, e, p in _sentences(t2)] == [("abc", 0), ("def", 1)]
    assert sentences_of(t2) == ["abc", "def"]


def test_overlap_repeats_the_last_sentences_within_a_paragraph() -> None:
    doc = Document("o", "aa bb. cc dd. ee ff. gg hh.\n\nii jj.")
    assert [c.text for c in chunk_document(doc, 13, 0)] == ["aa bb. cc dd.", "ee ff. gg hh.", "ii jj."]
    assert [c.text for c in chunk_document(doc, 13, 1)] == ["aa bb. cc dd.", "cc dd. ee ff.", "ee ff. gg hh.",
                                                           "ii jj."]
    check_chunk_invariants(doc, 13, 1)


def test_hard_cuts_respect_marks_joiners_and_selectors() -> None:
    harakat = "بَ" * 30                                     # letter + fatha, 60 code points, one word
    family = "\U0001F468\u200d\U0001F469\u200d\U0001F467" * 6
    heart = "\u2764\ufe0f" * 20
    for word in (harakat, family, heart, unicodedata.normalize("NFD", "é" * 40)):
        doc = Document("w", word)
        for m in (8, 9, 11):
            chunks = chunk_document(doc, m)
            check_chunk_invariants(doc, m, 0)
            for a, b in zip(chunks, chunks[1:]):
                nxt, prev = word[b.start], word[a.end - 1]
                assert not unicodedata.combining(nxt) and nxt not in "\u200d\ufe0f" and prev != "\u200d"


def test_input_validation() -> None:
    for bad in ("", "a#b", "a b", 3):
        with pytest.raises(ValueError):
            Document(bad, "x")                       # type: ignore[arg-type]
    for date in ("2026-1-1", "2026-02-30", "yesterday", 20260101):
        with pytest.raises(ValueError):
            Document("d", "x", published=date)       # type: ignore[arg-type]
    for kw in ({"max_chars": 7}, {"max_chars": True}, {"overlap": -1}, {"overlap": 9}):
        with pytest.raises(ValueError):
            chunk_document(Document("d", "x"), **kw)
    with pytest.raises(ValueError, match="as_of"):
        Filter(max_age_days=30)
    with pytest.raises(ValueError):
        LexicalIndex([Document("d", "x"), Document("d", "y")])
    with pytest.raises(ValueError):
        LexicalIndex([Document("d", "x")]).search("x", k=0)


# ==== R2 BM25 vs brute force ========================================================================================
def brute_bm25(index: LexicalIndex, query: str) -> list[tuple[str, float]]:
    texts = [analyze(c.text) for c in index.chunks]
    n = len(texts)
    avg = sum(map(len, texts)) / n
    out = []
    for c, toks in zip(index.chunks, texts):
        s, hit = 0.0, False
        for q in sorted(set(analyze(query))):
            df = sum(q in t for t in texts)
            tf = toks.count(q)
            if tf:
                hit = True
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(toks) / avg))
        if hit:
            out.append((c.chunk_id, s))
    return sorted(out, key=lambda x: (-x[1], x[0]))


def test_bm25_matches_brute_force() -> None:
    rng = random.Random(1)
    for _ in range(40):
        docs = synth_corpus(rng, rng.randint(1, 12))
        ix = LexicalIndex(docs, max_chars=rng.choice([40, 120, 400]))
        for _ in range(5):
            q = " ".join(rng.choice(AR + LA + ["absent"]) for _ in range(rng.randint(1, 4)))
            got = [(h.chunk_id, h.score) for h in ix.search(q, k=10_000)]
            want = brute_bm25(ix, q)
            assert [g[0] for g in got] == [w[0] for w in want]
            assert all(math.isclose(g[1], w[1], rel_tol=0, abs_tol=1e-12) for g, w in zip(got, want))
    assert LexicalIndex(synth_corpus(random.Random(2), 3)).search("absentword") == []


# ==== R3 ordering and determinism ===================================================================================
def test_order_independence_ties_and_byte_identical_builds() -> None:
    rng = random.Random(3)
    docs = synth_corpus(rng, 10)
    a, b = LexicalIndex(docs), LexicalIndex(list(reversed(docs)))
    assert a.to_json() == b.to_json() == LexicalIndex(docs).to_json()
    for q in ("سلمور قنطار", "valmor kufar", "مرفاد"):
        assert a.search(q) == b.search(q)
    ties = LexicalIndex([Document("b", "zorwin teliva"), Document("a", "zorwin quintel"), Document("c", "zorwin x")])
    hits = ties.search("zorwin")
    assert len({h.score for h in hits}) == 1 and [h.doc_id for h in hits] == ["a", "b", "c"]


# ==== R4 repetition and duplicates ==================================================================================
def test_term_frequency_saturates() -> None:
    base = [Document("z", "loquen dormis")]
    scores = []
    for tf in range(1, 12):
        ix = LexicalIndex(base + [Document("t", " ".join(["valmor"] * tf + ["pad"] * (12 - tf)))])
        scores.append(ix.search("valmor")[0].score)
        assert scores[-1] < ix.idf("valmor") * (K1 + 1)
    assert all(x < y for x, y in zip(scores, scores[1:]))


def test_duplicates_indexed_once_listed_and_filter_fallback() -> None:
    docs = [Document("a", "نهر الزيتون طويل.", published="2019-01-01", quality=SourceQuality.UNVERIFIED),
            Document("b", "نَهْرُ الزَّيْتُونِ طَوِيلٌ.", published="2026-09-01", quality=SourceQuality.PRIMARY),
            Document("c", "نهر الزيتون طويل.")]
    ix = LexicalIndex(docs)
    assert ix.duplicates == [("b#0", "a#0"), ("c#0", "a#0")] and len(ix.chunks) == 1
    assert ix.manifest()["duplicates"] == [["b#0", "a#0"], ["c#0", "a#0"]]
    plain = ix.search("نهر")
    fresh = ix.search("نهر", flt=Filter(max_age_days=365, as_of="2026-10-02"))
    best = ix.search("نهر", flt=Filter(min_quality=SourceQuality.PRIMARY))
    assert [h.chunk_id for h in plain] == ["a#0"] and [h.chunk_id for h in fresh] == ["b#0"] == [h.chunk_id for h in best]
    assert fresh[0].score == plain[0].score and fresh[0].text == docs[1].text
    keep_all = LexicalIndex(docs, dedupe=False).search("نهر")
    assert len(keep_all) == 3 and len({h.score for h in keep_all}) == 1


# ==== R5 Unicode and synthetic Arabic ===============================================================================
def test_arabic_and_unicode_normalisation() -> None:
    assert analyze("سَلْمُـــور") == analyze("سلمور")                      # harakat, tatweel
    assert analyze("أمير إمرة آمنة") == analyze("امير امرة امنة")           # hamza forms
    assert analyze("رقم ١٢٣") == analyze("رقم 123")                       # Arabic-Indic digits
    assert analyze("مدرسة") == analyze("مدرسه")                           # ta marbuta
    assert analyze(unicodedata.normalize("NFD", "Café")) == analyze("café")
    assert analyze("المرفاد") == ["مرفاد"] and analyze("الجو") == ["الجو"]   # strip_al only above four letters
    assert analyze("المرفاد", strip_al=False) == ["المرفاد"]
    ix = LexicalIndex([Document("a", "زار سامِر المِرْفادَ الكبير.")])
    assert [h.chunk_id for h in ix.search("مرفاد")] == ["a#0"]


# ==== R6 rebuild and verify =========================================================================================
def test_save_load_verify_and_tampering() -> None:
    docs = synth_corpus(random.Random(4), 6)
    ix = LexicalIndex(docs, max_chars=120)
    saved = ix.to_json()
    loaded = LexicalIndex.from_json(saved, docs)
    assert loaded.search("valmor سلمور") == ix.search("valmor سلمور") and verify(saved, ix) == []

    d = json.loads(saved)
    term = sorted(d["postings"])[0]
    d["postings"][term][0][1] += 1
    assert "file_sha256 does not match the content" in LexicalIndex.check_json(json.dumps(d))
    with pytest.raises(ValueError, match="corrupt"):
        LexicalIndex.from_json(json.dumps(d), docs)

    changed = [Document(docs[0].doc_id, docs[0].text + " نعسال.", docs[0].source, docs[0].published,
                        docs[0].quality)] + docs[1:]
    with pytest.raises(ValueError, match="does not match"):
        LexicalIndex.from_json(saved, changed)
    meta = [Document(docs[0].doc_id, docs[0].text, docs[0].source, docs[0].published, SourceQuality.PRIMARY
                     if docs[0].quality is not SourceQuality.PRIMARY else SourceQuality.UNKNOWN)] + docs[1:]
    assert "corpus_sha256 differs" in verify(saved, LexicalIndex(meta, max_chars=120))
    assert "settings differs" in verify(saved, LexicalIndex(docs, max_chars=400))
    m = ix.manifest()
    assert m["settings"]["k1"] == K1 and m["settings"]["b"] == B and m["n_chunks"] == len(m["chunks"])


# ==== R7 metadata ===================================================================================================
def test_filters_never_change_scores_and_need_explicit_dates() -> None:
    docs = [Document("old", "kufar nesral", published="2020-01-01", quality=SourceQuality.PRIMARY),
            Document("new", "kufar teliva", published="2026-09-30", quality=SourceQuality.SECONDARY),
            Document("undated", "kufar dormis", quality=SourceQuality.UNVERIFIED),
            Document("future", "kufar loquen", published="2027-01-01", quality=SourceQuality.PRIMARY)]
    ix = LexicalIndex(docs)
    allhits = {h.chunk_id: h.score for h in ix.search("kufar")}
    cases = {Filter(max_age_days=30, as_of="2026-10-02"): {"new#0"},
             Filter(min_quality=SourceQuality.SECONDARY): {"old#0", "new#0", "future#0"},
             Filter(as_of="2026-10-02"): {"old#0", "new#0", "undated#0"},
             Filter(as_of="2026-10-02", exclude_future=False): set(allhits),
             Filter(min_quality=SourceQuality.PRIMARY, max_age_days=10_000, as_of="2026-10-02"): {"old#0"}}
    for flt, want in cases.items():
        hits = ix.search("kufar", flt=flt)
        assert {h.chunk_id for h in hits} == want
        assert all(h.score == allhits[h.chunk_id] for h in hits)
    assert docs[0].age_days("2026-01-01") == 2192 and docs[2].age_days("2026-01-01") is None


# ==== R8 reranker and P6-04 integration =============================================================================
def test_reranker_reorders_only_and_puts_phrases_first() -> None:
    ix = LexicalIndex([Document("a", "zorwin zorwin zorwin kufar kufar kufar"),       # both terms, no phrase
                       Document("b", "kufar zorwin pad pad pad pad pad pad"),           # the phrase, lower BM25
                       Document("c", "zorwin alone here")])
    hits = ix.search("kufar zorwin")
    assert [h.chunk_id for h in hits] == ["a#0", "b#0", "c#0"]
    out = apply_reranker(LexicalReranker(), "kufar zorwin", hits)
    assert [h.chunk_id for h in out] == ["b#0", "a#0", "c#0"]
    assert out == apply_reranker(LexicalReranker(), "kufar zorwin", list(reversed(hits)))

    class Dropper:
        name = "dropper"

        def rerank(self, query, hits):
            return list(hits)[1:]

    class Forger:
        name = "forger"

        def rerank(self, query, hits):
            return [type(h)(h.chunk_id, h.doc_id, h.score + 1, h.matched, h.text) for h in hits]

    for bad in (Dropper(), Forger()):
        with pytest.raises(ValueError):
            apply_reranker(bad, "kufar zorwin", hits)


def test_retrieved_chunks_serve_as_evidence() -> None:
    docs = [Document("s1", "بلغ ارتفاع برج قنطار ثلاثمئة متر. افتتح البرج في الربيع.", source="synthetic:s1"),
            Document("s2", "نهر بَرْزان يجري شمالًا.", source="synthetic:s2")]
    ix = LexicalIndex(docs, max_chars=40)
    hits = ix.search("ارتفاع برج قنطار", k=1)
    ev = to_evidence(ix, hits)
    assert ev[0].evidence_id == "s1#0" and ev[0].source == "synthetic:s1"
    claim = TextClaim("t", "بلغ ارتفاع برج قنطار ثلاثمئة متر", (ev[0].evidence_id,))
    rep = check([claim], ev, checkers=[QuoteChecker()])
    assert rep.verdict.state is VerificationState.SUPPORTED and decide(rep).action is Action.ANSWER_WITH_CITATIONS
    none = to_evidence(ix, ix.search("مدينة غائبة"))
    assert none == [] and decide(check([TextClaim("t", "x y z")], none)).action is Action.ABSTAIN


def test_package_states_it_is_not_a_final_rag_system() -> None:
    import nawa.retrieval as r
    assert "Not a final RAG system" in (r.__doc__ or "")
