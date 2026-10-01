"""P3-01/P3-02: tokenizer candidates (written from scratch) and their measurement (ADR-0006)."""

from __future__ import annotations

import copy
import random
from pathlib import Path

import pytest

from nawa.tokenizer import corpus as C
from nawa.tokenizer import fingerprint, from_dict, load, save
from nawa.tokenizer import metrics as M
from nawa.tokenizer.bpe import BPETokenizer
from nawa.tokenizer.byte import ByteTokenizer
from nawa.tokenizer.pretok import arabic, default, split_arabic_word
from nawa.tokenizer.unigram import UnigramTokenizer

TRAIN = C.training_corpus(5)[:300]
EDGE = ["", " ", "\n\n\t ", "a", "ب", "😀", "e\u0301", "مي\u200cخواهم", "مَرْحَبًا", "x_1 = __init__(2**10)",
        "  leading and trailing  ", "١٢٣٤٥٦ 123456", "\u202eRTL override", "ﻻ ﷺ", "中文 日本語 한국어", "\x00\x07"]


def _rand_text(rng: random.Random) -> str:
    pools = [(0x20, 0x7E), (0x0600, 0x06FF), (0x0300, 0x036F), (0x4E00, 0x4E50), (0x1F600, 0x1F64F), (0x2000, 0x206F)]
    out = []
    for _ in range(rng.randint(0, 40)):
        lo, hi = rng.choice(pools)
        c = rng.randint(lo, hi)
        out.append(chr(c))
    return "".join(out)


@pytest.fixture(scope="module")
def toks() -> dict[str, object]:
    return {
        "byte": ByteTokenizer(),
        "bpe": BPETokenizer.train(TRAIN, 600),
        "bpe_arabic": BPETokenizer.train(TRAIN, 600, pretok="arabic", name="bpe_arabic"),
        "unigram": UnigramTokenizer.train(TRAIN, 600),
        "unigram_arabic": UnigramTokenizer.train(TRAIN, 600, pretok="arabic", name="unigram_arabic"),
    }


# ---- pre-tokenizers -----------------------------------------------------------------------------

def test_pretokenizers_are_lossless_on_random_unicode() -> None:
    rng = random.Random(0)
    for _ in range(500):
        t = _rand_text(rng)
        assert "".join(default(t)) == t and "".join(arabic(t)) == t
    for t in EDGE:
        assert "".join(default(t)) == t and "".join(arabic(t)) == t


def test_tashkeel_and_zwnj_stay_inside_words() -> None:
    assert default(" مَرْحَبًا") == [" مَرْحَبًا"] and default("مي\u200cخواهم") == ["مي\u200cخواهم"]


@pytest.mark.parametrize("word,parts", [
    (" وبالكتاب", [" وبال", "كتاب"]),
    ("يكتبونها", ["يكتبون", "ها"]),
    ("ولد", ["ولد"]),            # stem would be shorter than 3 letters: not split
    ("والد", ["و", "الد"]),      # known over-split of a clitic look-alike (the reason P3-02 measures precision)
    ("كتب", ["كتب"]),
    ("school", ["school"]),
])
def test_arabic_clitic_split(word: str, parts: list[str]) -> None:
    assert split_arabic_word(word) == parts and "".join(parts) == word


# ---- candidates ---------------------------------------------------------------------------------

def test_every_candidate_round_trips_exactly(toks: dict) -> None:
    rng = random.Random(1)
    samples = EDGE + [_rand_text(rng) for _ in range(300)] + C.rare_unicode(77, 20) + C.code(78, 5)
    for name, tok in toks.items():
        for t in samples:
            assert tok.decode(tok.encode(t)) == t, (name, t)


def test_lone_surrogates_are_rejected_not_corrupted(toks: dict) -> None:
    for tok in toks.values():
        with pytest.raises(UnicodeEncodeError):
            tok.encode("a\ud800b")


def test_vocab_sizes_and_ids_in_range(toks: dict) -> None:
    for name, tok in toks.items():
        assert tok.vocab_size <= (256 if name == "byte" else 600)
        ids = tok.encode(" ".join(TRAIN[:20]))
        assert ids and min(ids) >= 0 and max(ids) < tok.vocab_size


def test_bpe_learns_the_most_frequent_pair_first() -> None:
    tok = BPETokenizer.train(["aaaa bbb aaaa", "aaaa"], 257)
    assert tok.merges[0] == (ord("a"), ord("a")) and tok.encode("aaaa") == [256, 256]


def test_unigram_uses_byte_fallback_for_unseen_characters() -> None:
    tok = UnigramTokenizer.train(["abc abc abd"] * 5, 300)
    ids = tok.encode("ب")
    assert ids == list("ب".encode("utf-8")) and tok.decode(ids) == "ب"


def test_training_is_deterministic(toks: dict) -> None:
    assert fingerprint(BPETokenizer.train(TRAIN, 600)) == fingerprint(toks["bpe"])
    assert fingerprint(UnigramTokenizer.train(TRAIN, 600)) == fingerprint(toks["unigram"])
    assert fingerprint(BPETokenizer.train(C.training_corpus(6)[:300], 600)) != fingerprint(toks["bpe"])


def test_save_load_identity_and_no_overwrite(toks: dict, tmp_path: Path) -> None:
    for name, tok in toks.items():
        p = tmp_path / f"{name}.json"
        save(tok, p)
        back = load(p)
        assert fingerprint(back) == fingerprint(tok)
        for t in EDGE + TRAIN[:5]:
            assert back.encode(t) == tok.encode(t)
        with pytest.raises(FileExistsError):
            save(tok, p)
    with pytest.raises(ValueError):
        from_dict({"type": "wordpiece"})


def test_learned_candidates_compress_arabic_better_than_bytes(toks: dict) -> None:
    docs = C.arabic(123, 10)
    byte = M.compression(toks["byte"], docs)["bytes_per_token"]
    for name in ("bpe", "bpe_arabic", "unigram", "unigram_arabic"):
        assert M.compression(toks[name], docs)["bytes_per_token"] > 2 * byte


# ---- corpus and metrics -------------------------------------------------------------------------

def test_corpus_is_deterministic_and_heldout_is_unseen() -> None:
    assert C.training_corpus(5) == C.training_corpus(5)
    cfg = M.load_config()
    ho = M.heldout(cfg)
    train = set(C.training_corpus(cfg["train_seed"]))
    assert not any(d in train for docs in ho["categories"].values() for d in docs)


def test_morph_gold_includes_clitic_lookalike_stems() -> None:
    words = C.morph_words(3, 3000)
    assert all("".join(w.morphemes) == w.text for w in words)
    lookalike = [w for w in words if len(w.morphemes) == 1 and w.text[0] in "وفبلكس" and len(w.text) >= 4]
    assert lookalike, "segmenters that split on surface letters must be penalised"


def test_boundary_metric_on_known_cases() -> None:
    byte = ByteTokenizer()
    w = C.Word("ابن", ("ا", "بن"))
    assert M.token_char_boundaries(byte, "ابن") == {1, 2}
    assert M.morphology(byte, [w]) == {"boundary_precision": 0.5, "boundary_recall": 1.0, "boundary_f1": 0.6667}


def test_noise_pairs_cover_every_kind() -> None:
    kinds = {k for k, _, _ in C.noisy_pairs(1, 25)}
    assert kinds == {"tashkeel", "tatweel", "typo", "repeat", "arabizi"}


def test_evaluate_small_config_meets_correctness_criteria() -> None:
    cfg = copy.deepcopy(M.load_config())
    cfg["vocab_size"] = 512
    cfg["heldout"].update(docs_per_category=8, morph_words=200, noisy_pairs=25, seq_docs=5)
    rep = M.evaluate(cfg)
    assert rep["criteria"] == M.CRITERIA and rep["passed"], rep["checks"]
    assert rep["selection"].startswith("none") and set(rep["results"]) == {c["name"] for c in cfg["candidates"]}
