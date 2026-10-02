"""Rule-based question decomposer (ROADMAP P6-03, ADR-0008).

Splits a *structured* question into ordered sub-questions (:class:`SubTask`). **Lexical rules only: it does not
understand meaning.** Open decomposition with a model is P6-03a (BLOCKED until G5).

Rules, in order:

1. **Code blocks.** Every fenced block (three backticks ... three backticks) becomes its own ``CODE`` sub-question,
   holding the code. Nothing inside a block is split.
2. **Independent parts.** The rest is split at ``?`` ``؟`` ``;`` ``؛`` ``!`` line breaks and at a full stop that is not
   between two digits (so ``3.5`` and ``٣٫٥`` stay whole). Parts do not depend on each other.
3. **Sequential pieces.** Inside a part, the connectors ``ثم`` / ``وبعد ذلك`` / ``بعد ذلك`` / ``then`` / ``and then``
   (as whole words) split it again; every piece depends on the piece before it.
4. **Kind.** A piece holding an arithmetic expression (digits joined by ``+ - * / × ÷ ^ −``, with optional decimals and
   parentheses) is ``ARITHMETIC`` and carries the expression; otherwise it is ``TEXT``. Arabic-Indic digits count.
5. **Empty pieces** (only spaces or punctuation) are dropped; they hold no question.

Not done (stated, tested): the conjunction ``و`` is never a split point (it is a prefix and cannot be told apart from a
word's first letter by rules); references such as "the result" are not resolved; a sentence with two questions joined
by a comma is one sub-question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from nawa.evaluation.normalize import normalize_digits

MAX_CHARS = 4000


class Kind(str, Enum):
    ARITHMETIC = "ARITHMETIC"
    CODE = "CODE"
    TEXT = "TEXT"


@dataclass(frozen=True)
class SubTask:
    task_id: str
    text: str
    kind: Kind
    depends_on: tuple[str, ...] = ()
    expression: str | None = None     # ARITHMETIC only
    code: str | None = None           # CODE only

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not re.fullmatch(r"t\d+", self.task_id):
            raise ValueError("task_id must look like 't1'")
        if not isinstance(self.kind, Kind):
            raise ValueError("kind must be a Kind")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        object.__setattr__(self, "depends_on", tuple(self.depends_on))
        if (self.kind is Kind.ARITHMETIC) != (self.expression is not None):
            raise ValueError("expression is set exactly for ARITHMETIC sub-questions")
        if (self.kind is Kind.CODE) != (self.code is not None):
            raise ValueError("code is set exactly for CODE sub-questions")

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "text": self.text, "kind": self.kind.value,
                "depends_on": list(self.depends_on), "expression": self.expression, "code": self.code}


_FENCE = re.compile(r"```[^\n`]*\n(.*?)```", re.S)
_PART = re.compile(r"[?؟;؛!\n]+|(?<![0-9٠-٩])\.|\.(?![0-9٠-٩])")
_SEQ = re.compile(r"(?<!\w)(?:and then|then|وبعد ذلك|بعد ذلك|ثم)(?!\w)", re.I)
_NUM = r"\(*\s*[0-9٠-٩]+(?:[.٫][0-9٠-٩]+)?\s*\)*"
_EXPR = re.compile(rf"{_NUM}(?:\s*[+\-*/×÷^−]\s*{_NUM})+")
_PLACEHOLDER = "\u0000CODE{}\u0000"
_CONTENT = re.compile(r"\w")


def find_expression(text: str) -> str | None:
    """The first arithmetic expression in ``text`` (digits normalised to ASCII, ``^`` to ``**``), or ``None``."""
    m = _EXPR.search(text)
    if not m:
        return None
    expr = re.sub(r"\s+", " ", normalize_digits(m.group(0))).strip()
    expr = expr.replace("٫", ".").replace("^", "**")
    # balance: drop unmatched leading "(" / trailing ")" picked up by the greedy number pattern
    while expr.count("(") > expr.count(")") and expr.startswith("("):
        expr = expr[1:].lstrip()
    while expr.count(")") > expr.count("(") and expr.endswith(")"):
        expr = expr[:-1].rstrip()
    return expr


def decompose(question: str) -> list[SubTask]:
    if not isinstance(question, str):
        raise ValueError("question must be a string")
    if len(question) > MAX_CHARS:
        raise ValueError(f"question longer than {MAX_CHARS} characters")
    codes: list[str] = []

    def keep(m: re.Match) -> str:
        codes.append(m.group(1))
        return "\n" + _PLACEHOLDER.format(len(codes) - 1) + "\n"

    text = _FENCE.sub(keep, question)
    out: list[SubTask] = []
    for part in _PART.split(text):
        prev: str | None = None
        for piece in _SEQ.split(part):
            piece = re.sub(r"\s+", " ", piece).strip(" ,،:")
            code_ref = re.fullmatch(r"\x00CODE(\d+)\x00", piece)
            if code_ref:
                tid = f"t{len(out) + 1}"
                out.append(SubTask(tid, codes[int(code_ref.group(1))].strip() or "(empty code)", Kind.CODE,
                                   (prev,) if prev else (), code=codes[int(code_ref.group(1))]))
                prev = tid
                continue
            if not _CONTENT.search(piece.replace("\x00", "")):
                continue
            tid = f"t{len(out) + 1}"
            expr = find_expression(piece)
            out.append(SubTask(tid, piece, Kind.ARITHMETIC if expr else Kind.TEXT, (prev,) if prev else (),
                               expression=expr))
            prev = tid
    return out
