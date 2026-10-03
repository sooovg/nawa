"""Memory kinds, the memory item record and the extended registry (ROADMAP P7-05, ADR-0009).

Five core kinds, as named by the owner on 2026-10-03, plus one transient input buffer:

| Kind | Owner's name | ROADMAP P7-05 word it covers |
|---|---|---|
| ``CONVERSATION`` | ذاكرة المحادثة: سياق الحوار الحالي | working (dialogue), episodic |
| ``USER_PERSISTENT`` | الذاكرة الدائمة للمستخدم: ما وافق المستخدم على حفظه | personal/project |
| ``TASK`` | ذاكرة المهام: أهداف المهمة وخطواتها وحالتها | working (task) |
| ``KNOWLEDGE`` | ذاكرة المعرفة: حقائق موثقة بمصدر وثقة | semantic |
| ``PROCEDURAL`` | ذاكرة الخبرة والإجراءات: ما تعلمه النظام من تنفيذ المهام | procedural |
| ``SENSORY`` | الذاكرة الحسية وأنماطها: تسجيل لحظي مؤقت للمدخلات | (input buffer, short TTL) |

The owner's list also names more than two hundred other memories, many of them not software (immune cells, DDR4,
holographic storage, telepathy). ``REGISTRY`` gives every requested name an explicit status so nothing is silently
claimed: implemented as a core kind or buffer, an alias of core kinds, a store capability, a domain tag on synthetic
knowledge, deferred behind a named blocker, not applicable to a software memory, or rejected because it conflicts with
forgetting or privacy. ``tests/test_memory_types.py`` checks the registry against the requested list and checks that
every capability it claims is exercised.

Times are logical ticks (integer seconds from a fixed synthetic epoch), never the wall clock, so runs are
reproducible. Code-only scope: synthetic users only; OD-12 must be decided before any real memory.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from enum import Enum

from nawa.memory.provenance import Provenance
from nawa.memory.mutability import KnowledgeMutability
from nawa.verification.states import VerificationState

EPOCH = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)  # fixed synthetic epoch for tick → ISO rendering


def iso(tick: int) -> str:
    """Render a logical tick as an ISO-8601 UTC timestamp (deterministic; no wall clock)."""
    return (EPOCH + _dt.timedelta(seconds=int(tick))).strftime("%Y-%m-%dT%H:%M:%SZ")


class MemoryKind(str, Enum):
    CONVERSATION = "conversation"
    USER_PERSISTENT = "user_persistent"
    TASK = "task"
    KNOWLEDGE = "knowledge"
    PROCEDURAL = "procedural"
    SENSORY = "sensory"


CORE_KINDS = (MemoryKind.CONVERSATION, MemoryKind.USER_PERSISTENT, MemoryKind.TASK, MemoryKind.KNOWLEDGE,
              MemoryKind.PROCEDURAL)
DURABLE_KINDS = frozenset({MemoryKind.USER_PERSISTENT, MemoryKind.KNOWLEDGE, MemoryKind.PROCEDURAL})


class Modality(str, Enum):
    TEXT = "text"
    VISUAL = "visual"
    AUDIO = "audio"
    TACTILE = "tactile"
    MULTISENSORY = "multisensory"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


# Default retention in logical seconds. Design parameters of the store, not evaluation thresholds.
SENSORY_TTL = 10            # short-term: "احتفاظ محدود لمدة ثوانٍ"
CONVERSATION_TTL = 3600     # one synthetic session; end_session() forgets earlier
DEFAULT_TTL = {MemoryKind.SENSORY: SENSORY_TTL, MemoryKind.CONVERSATION: CONVERSATION_TTL}


@dataclass(frozen=True)
class MemoryItem:
    """One stored memory. Every item has an owner, a project, provenance, a confidence and logical timestamps."""

    item_id: str
    kind: MemoryKind
    owner: str
    project: str
    content: str
    provenance: Provenance
    confidence: float
    created_at: int
    updated_at: int
    version: int = 1
    expires_at: int | None = None
    modality: Modality | None = None
    tags: tuple[str, ...] = ()
    consent: bool = False
    verification_state: VerificationState | None = None
    fact_key: tuple[str, ...] | None = None          # (subject, attribute) or (subject, relation, object)
    task_status: TaskStatus | None = None
    steps: tuple[str, ...] = ()
    due_at: int | None = None                        # prospective memory: when a task should be done
    read_only: bool = False
    mutability: KnowledgeMutability | None = None       # P7-06: STABLE/CHANGING/UNKNOWN for knowledge records

    @property
    def epistemic(self) -> str | None:
        """KNOWLEDGE only: 'fact' when the verification state is SUPPORTED, otherwise 'belief'."""
        if self.kind is not MemoryKind.KNOWLEDGE:
            return None
        return "fact" if self.verification_state is VerificationState.SUPPORTED else "belief"

    @property
    def timestamp(self) -> str:
        return iso(self.updated_at)

    def to_record(self) -> dict:
        return {
            "item_id": self.item_id, "kind": self.kind.value, "owner": self.owner, "project": self.project,
            "content": self.content, "provenance": self.provenance.to_record(),
            "confidence": round(float(self.confidence), 6), "created_at": self.created_at,
            "updated_at": self.updated_at, "version": self.version, "expires_at": self.expires_at,
            "modality": self.modality.value if self.modality else None, "tags": list(self.tags),
            "consent": self.consent,
            "verification_state": self.verification_state.value if self.verification_state else None,
            "fact_key": list(self.fact_key) if self.fact_key else None,
            "task_status": self.task_status.value if self.task_status else None, "steps": list(self.steps),
            "due_at": self.due_at, "read_only": self.read_only,
            "mutability": self.mutability.value if self.mutability else None,
        }

    @classmethod
    def from_record(cls, r: dict) -> "MemoryItem":
        return cls(
            item_id=r["item_id"], kind=MemoryKind(r["kind"]), owner=r["owner"], project=r["project"],
            content=r["content"], provenance=Provenance.from_record(r["provenance"]),
            confidence=float(r["confidence"]), created_at=int(r["created_at"]), updated_at=int(r["updated_at"]),
            version=int(r["version"]), expires_at=r["expires_at"],
            modality=Modality(r["modality"]) if r["modality"] else None, tags=tuple(r["tags"]),
            consent=bool(r["consent"]),
            verification_state=VerificationState(r["verification_state"]) if r["verification_state"] else None,
            fact_key=tuple(r["fact_key"]) if r["fact_key"] else None,
            task_status=TaskStatus(r["task_status"]) if r["task_status"] else None, steps=tuple(r["steps"]),
            due_at=r["due_at"], read_only=bool(r["read_only"]),
            mutability=KnowledgeMutability(r["mutability"]) if r.get("mutability") else None,
        )


# ---------------------------------------------------------------------------------------------------------------
# Extended registry
# ---------------------------------------------------------------------------------------------------------------

class RegistryStatus(str, Enum):
    CORE = "core"                    # one of the five core kinds
    BUFFER = "buffer"                # the transient sensory buffer, by modality
    ALIAS = "alias"                  # another name for one or more core kinds
    FEATURE = "feature"              # a store capability (see CAPABILITIES), exercised by a test
    DOMAIN_TAG = "domain_tag"        # a topic tag on synthetic KNOWLEDGE/PROCEDURAL items
    DEFERRED = "deferred"            # needs a named decision or gate first
    NOT_APPLICABLE = "not_applicable"  # not a memory a software system can have; not claimed
    REJECTED = "rejected"            # conflicts with forgetting, deletion or privacy rules


# Store capabilities that registry FEATURE entries may claim. tests/test_memory_types.py exercises each one.
CAPABILITIES = frozenset({
    "short_term_ttl", "long_term", "volatile_in_process", "persist_to_disk", "erase", "update_with_provenance",
    "read_only", "mutable", "direct_read", "sequential_scan", "content_search", "associative_recall", "read_cache",
    "private_acl", "project_scope", "logical_time", "metamemory", "belief_vs_fact", "attribute_key", "relation_key",
    "version_history", "prospective_due", "fusion", "inverted_index",
})


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    status: RegistryStatus
    targets: tuple[str, ...]
    note: str = ""


def _k(*kinds: MemoryKind) -> tuple[str, ...]:
    return tuple(k.value for k in kinds)


C, U, T, K, P, S = (MemoryKind.CONVERSATION, MemoryKind.USER_PERSISTENT, MemoryKind.TASK, MemoryKind.KNOWLEDGE,
                    MemoryKind.PROCEDURAL, MemoryKind.SENSORY)
R = RegistryStatus

_ENTRIES: list[RegistryEntry] = [
    # core kinds
    RegistryEntry("ذاكرة المحادثة", R.CORE, _k(C)),
    RegistryEntry("الذاكرة الدائمة للمستخدم", R.CORE, _k(U), "explicit consent required"),
    RegistryEntry("ذاكرة المهام", R.CORE, _k(T)),
    RegistryEntry("ذاكرة المعرفة", R.CORE, _k(K), "source, confidence and verification state required"),
    RegistryEntry("ذاكرة الخبرة والإجراءات", R.CORE, _k(P)),
    # sensory buffer
    RegistryEntry("الذاكرة الحسية", R.BUFFER, tuple(m.value for m in Modality), "TTL seconds"),
    RegistryEntry("الذاكرة البصرية", R.BUFFER, (Modality.VISUAL.value,), "synthetic payloads only"),
    RegistryEntry("الذاكرة السمعية", R.BUFFER, (Modality.AUDIO.value,), "synthetic payloads only"),
    RegistryEntry("الذاكرة النصية", R.BUFFER, (Modality.TEXT.value,)),
    RegistryEntry("الذاكرة اللمسية", R.BUFFER, (Modality.TACTILE.value,), "synthetic payloads only"),
    RegistryEntry("الذاكرة متعددة الحواس", R.FEATURE, ("fusion",), "fuses sensory items of one event"),
    RegistryEntry("المخزن المؤقت", R.ALIAS, _k(S), "transient buffer between components"),
    # aliases of core kinds
    RegistryEntry("الذاكرة العاملة", R.ALIAS, _k(T, C), "temporary information during a task"),
    RegistryEntry("الذاكرة التصريحية", R.ALIAS, _k(K, C)),
    RegistryEntry("الذاكرة الصريحة", R.ALIAS, _k(K, C), "synonym of declarative"),
    RegistryEntry("الذاكرة الوعية", R.ALIAS, _k(K, C), "declarative"),
    RegistryEntry("الذاكرة العرضية", R.ALIAS, _k(C)),
    RegistryEntry("الذاكرة الحدثية", R.ALIAS, _k(C), "synonym of episodic"),
    RegistryEntry("الذاكرة العرضية للوكيل", R.ALIAS, _k(C)),
    RegistryEntry("الذاكرة الاسترجاعية", R.ALIAS, _k(C, T), "recall of past events and tasks"),
    RegistryEntry("الذاكرة السياقية", R.ALIAS, _k(C), "current dialogue context"),
    RegistryEntry("الذاكرة الدلالية", R.ALIAS, _k(K)),
    RegistryEntry("الذاكرة الدلالية للوكيل", R.ALIAS, _k(K)),
    RegistryEntry("الذاكرة الخارجية", R.ALIAS, _k(K), "this store is memory outside the model weights (P7-06)"),
    RegistryEntry("الذاكرة الخارجية الاصطناعية", R.ALIAS, _k(K)),
    RegistryEntry("الذاكرة التقنية", R.ALIAS, _k(K), "knowledge from synthetic documents"),
    RegistryEntry("الذاكرة السيرية", R.ALIAS, _k(U), "consent required"),
    RegistryEntry("الذاكرة الدلالية الشخصية", R.ALIAS, _k(U), "consent required"),
    RegistryEntry("ذاكرة الفرد", R.ALIAS, _k(U), "consent required"),
    RegistryEntry("الذاكرة غير التصريحية", R.ALIAS, _k(P), "stored explicitly with provenance, never implicit"),
    RegistryEntry("الذاكرة الضمنية", R.ALIAS, _k(P), "synonym of non-declarative"),
    RegistryEntry("الذاكرة اللاوعية", R.ALIAS, _k(P)),
    RegistryEntry("الذاكرة الإجرائية", R.ALIAS, _k(P)),
    RegistryEntry("ذاكرة الإجراءات", R.ALIAS, _k(P)),
    # capabilities
    RegistryEntry("الذاكرة قصيرة المدى", R.FEATURE, ("short_term_ttl",)),
    RegistryEntry("الذاكرة قصيرة المدى للوكيل", R.FEATURE, ("short_term_ttl",)),
    RegistryEntry("الذاكرة طويلة المدى", R.FEATURE, ("long_term",)),
    RegistryEntry("الذاكرة طويلة المدى للوكيل", R.FEATURE, ("long_term",)),
    RegistryEntry("الذاكرة التطلعية", R.FEATURE, ("prospective_due",)),
    RegistryEntry("الذاكرة الفوقية", R.FEATURE, ("metamemory",)),
    RegistryEntry("ذاكرة المعتقدات", R.FEATURE, ("belief_vs_fact",)),
    RegistryEntry("ذاكرة المشروع", R.FEATURE, ("project_scope",)),
    RegistryEntry("ذاكرة السمة", R.FEATURE, ("attribute_key",)),
    RegistryEntry("ذاكرة العلاقة", R.FEATURE, ("relation_key",)),
    RegistryEntry("ذاكرة التغير", R.FEATURE, ("version_history",)),
    RegistryEntry("الذاكرة الترابطية", R.FEATURE, ("associative_recall",)),
    RegistryEntry("الذاكرة المحتوى-العنوانية", R.FEATURE, ("content_search",)),
    RegistryEntry("الذاكرة متسلسلة الوصول", R.FEATURE, ("sequential_scan",)),
    RegistryEntry("الذاكرة التسلسلية", R.FEATURE, ("sequential_scan",)),
    RegistryEntry("الذاكرة ذات الوصول المباشر", R.FEATURE, ("direct_read",)),
    RegistryEntry("الذاكرة المباشرة", R.FEATURE, ("direct_read",)),
    RegistryEntry("الذاكرة العشوائية", R.FEATURE, ("direct_read",), "random access by id"),
    RegistryEntry("الذاكرة المتطايرة", R.FEATURE, ("volatile_in_process",)),
    RegistryEntry("الذاكرة غير المتطايرة", R.FEATURE, ("persist_to_disk",)),
    RegistryEntry("الذاكرة الخطية", R.FEATURE, ("sequential_scan",), "linear ordered scan"),
    RegistryEntry("الذاكرة غير الخطية", R.FEATURE, ("inverted_index",), "token index, not a linear scan"),
    RegistryEntry("الذاكرة الخاصة", R.FEATURE, ("private_acl",)),
    RegistryEntry("الذاكرة القابلة للمسح", R.FEATURE, ("erase",)),
    RegistryEntry("الذاكرة القابلة للتعديل", R.FEATURE, ("update_with_provenance",)),
    RegistryEntry("الذاكرة المتغيرة", R.FEATURE, ("mutable",)),
    RegistryEntry("الذاكرة الثابتة", R.FEATURE, ("read_only",), "read-only items still obey deletion"),
    RegistryEntry("الذاكرة غير المتغيرة", R.FEATURE, ("read_only",)),
    RegistryEntry("الذاكرة المخبئية", R.FEATURE, ("read_cache",), "purged on every write and forget"),
    RegistryEntry("الذاكرة الزمنية", R.FEATURE, ("logical_time",)),
]

_DOMAINS = {
    "الذاكرة الثقافية": "cultural", "الذاكرة التاريخية": "historical", "الذاكرة السياسية": "political",
    "الذاكرة الدينية": "religious", "الذاكرة الأسطورية": "mythological", "الذاكرة الشعبية": "folk",
    "الذاكرة الفنية": "art", "الذاكرة الموسيقية": "music", "الذاكرة اللغوية": "linguistic",
    "الذاكرة المعمارية": "architectural", "الذاكرة الحضرية": "urban", "الذاكرة البيئية": "environmental",
    "الذاكرة المناخية": "climate", "الذاكرة الجيولوجية": "geological", "الذاكرة الفلكية": "astronomical",
    "الذاكرة الكونية": "cosmic", "الذاكرة الزمنية العميقة": "deep_time", "الذاكرة القانونية": "legal",
    "الذاكرة الاقتصادية": "economic", "الذاكرة المالية": "financial", "الذاكرة التجارية": "commercial",
    "الذاكرة الصناعية": "industrial", "الذاكرة العسكرية": "military", "الذاكرة الاستخباراتية": "intelligence",
    "الذاكرة الأمنية": "security", "الذاكرة الطبية": "medical", "الذاكرة السريرية": "clinical",
    "الذاكرة التمريضية": "nursing", "الذاكرة الصيدلانية": "pharmaceutical", "الذاكرة الهندسية": "engineering",
    "الذاكرة البرمجية": "software", "الذاكرة الشبكية": "networking", "الذاكرة المهنية": "professional",
}
_ENTRIES += [RegistryEntry(n, R.DOMAIN_TAG, (f"domain:{s}",), "tag on synthetic items; real content needs OD-03"
                           + ("; health or personal data also needs OD-12" if s in {"medical", "clinical",
                              "nursing", "pharmaceutical"} else ""))
             for n, s in _DOMAINS.items()]

_DEFERRED = {
    "الذاكرة الجماعية": ("OD-12",), "الذاكرة الجماعية للذكاء الاصطناعي": ("OD-12", "OD-10"),
    "الذاكرة المشتركة": ("OD-12",), "ذاكرة الشركة": ("OD-12",), "الذاكرة المتطايرة التنظيمية": ("OD-12",),
    "الذاكرة الدائمة التنظيمية": ("OD-12",), "ذاكرة المعاملات": ("OD-12",), "الذاكرة الاجتماعية": ("OD-12",),
    "الذاكرة الانفعالية": ("OD-12",), "الذاكرة المكانية": ("OD-12",),
    "الذاكرة الموزعة": ("OD-11", "OD-12"), "الذاكرة السحابية": ("OD-11", "OD-12"),
    "التهيئة": ("G5",), "التكييف الكلاسيكي": ("G5",), "التعود": ("G5",), "التحسس": ("G5",),
    "ذاكرة هوبفيلد": ("P4",),
}
_DEFERRED_NOTE = {
    "OD-12": "sharing between users, or storing emotions or locations, is a privacy decision",
    "OD-11": "needs network and a provider", "OD-10": "shared memory with external AI systems",
    "G5": "implicit behaviour change needs a trained model and must stay traceable (G7 provenance)",
    "P4": "an architecture choice, adopted only after measurement",
}
_ENTRIES += [RegistryEntry(n, R.DEFERRED, b, "; ".join(_DEFERRED_NOTE[x] for x in b)) for n, b in _DEFERRED.items()]

_NA = {
    "biological": ["الذاكرة الجينية", "الذاكرة اللاجينية", "الذاكرة المناعية", "الذاكرة المناعية التكيفية",
                   "خلايا B الذاكرة", "خلايا T الذاكرة", "خلايا T الذاكرة المركزية", "خلايا T الذاكرة المستجيبة",
                   "المناعة الفطرية المدربة", "الذاكرة الطبيعية", "ذاكرة الخلايا القاتلة الطبيعية",
                   "الذاكرة المنقولة حديثي الولادة", "الذاكرة الحركية", "الذاكرة الجمعية اللاواعية"],
    "physical_storage": ["الذاكرة الهولوغرافية", "الذاكرة الهولوغرافية متعددة المواضع",
                         "الذاكرة الهولوغرافية متحدة المحور", "ذاكرة إكسيتون-بولاريتون الهولوغرافية",
                         "الذاكرة الكمومية", "الذاكرة الضوئية", "الذاكرة المغناطيسية", "الذاكرة المغناطيسية الحديدية",
                         "ذاكرة تغير الطور", "ذاكرة تغير المقاومة", "الذاكرة السبينية", "الذاكرة الطوبولوجية",
                         "الذاكرة فائقة التوصيل", "الذاكرة العصبية الاصطناعية", "الذاكرة العضوية",
                         "الذاكرة البوليمرية", "الذاكرة الجزيئية", "الذاكرة الجزيئية الكبيرة", "الذاكرة الذرية",
                         "الذاكرة النانوية", "الذاكرة الحيوية المدمجة", "الذاكرة الجزيئية الحيوية",
                         "الذاكرة الهجينة الحيوية", "الذاكرة الوراثية الاصطناعية", "الذاكرة اللاجينية الاصطناعية",
                         "الذاكرة المناعية الاصطناعية", "ذاكرة الشكل", "ذاكرة نقطة العودة", "ذاكرة الصدى",
                         "تأثيرات الذاكرة في الزجاج", "ذاكرة انتقال موت", "ذاكرة PRAM", "الذاكرة الميكانيكية",
                         "الذاكرة في السوائل اللزجة", "ذاكرة النبضة الزمنية", "الذاكرة الحاسوبية الكمومية",
                         "الذاكرة الضوئية الكمومية", "الذاكرة المغناطيسية الكمومية", "الذاكرة الطبيعية الخارجية"],
    "computer_hardware": ["الذاكرة الديناميكية", "الذاكرة الساكنة", "الذاكرة الفيزيائية", "الذاكرة المنطقية",
                          "الذاكرة الافتراضية", "الذاكرة القابلة للبرمجة", "المستوى الأول", "المستوى الثاني",
                          "المستوى الثالث", "السجلات", "المكدس", "الكومة", "ذاكرة الوصول العشوائي",
                          "ذاكرة الوصول العشوائي الساكنة", "ذاكرة الوصول العشوائي الديناميكية",
                          "ذاكرة الوصول العشوائي المتزامنة", "ذاكرة الوصول العشوائي EDO",
                          "ذاكرة الوصول العشوائي ECC", "DDR1", "DDR2", "DDR3", "DDR4", "DDR5", "ذاكرة القراءة فقط",
                          "PROM", "EPROM", "EEPROM", "ذاكرة الفلاش", "NAND", "NOR", "القرص الصلب",
                          "قرص الحالة الصلبة", "الأشرطة المغناطيسية"],
    "deployment": ["الذاكرة الطرفية", "الذاكرة المدمجة"],
    "speculative": ["الذاكرة المرفوعة", "الذاكرة القابلة للتنزيل", "الذاكرة العصبية المباشرة",
                    "الذاكرة الرقمية للدماغ", "الذاكرة التخاطرية", "الذاكرة البُعدية", "الذاكرة الأكوانية"],
}
_NA_NOTE = {
    "biological": "a biological memory; NAWA does not have or simulate it",
    "physical_storage": "a physical storage medium or material effect, not a memory kind of this software",
    "computer_hardware": "computer hardware or OS memory handled by the runtime, not a NAWA memory kind",
    "deployment": "a deployment topology question for P8/P10, not a memory kind",
    "speculative": "no such capability exists; NAWA does not claim it",
}
_ENTRIES += [RegistryEntry(n, R.NOT_APPLICABLE, (cat,), _NA_NOTE[cat]) for cat, names in _NA.items() for n in names]

_ENTRIES += [
    RegistryEntry("الذاكرة الأبدية", R.REJECTED, ("forgetting",), "memory that never perishes conflicts with deletion"),
    RegistryEntry("الذاكرة المطلقة", R.REJECTED, ("forgetting",), "memory that never forgets conflicts with deletion"),
    RegistryEntry("الذاكرة المثالية", R.REJECTED, ("sensory_ttl", "OD-12"),
                  "verbatim permanent capture of inputs conflicts with buffer TTL and privacy"),
    RegistryEntry("الذاكرة الفوتوغرافية", R.REJECTED, ("sensory_ttl", "OD-12"),
                  "verbatim permanent capture of inputs conflicts with buffer TTL and privacy"),
]

REGISTRY: dict[str, RegistryEntry] = {}
for _e in _ENTRIES:
    if _e.name in REGISTRY:
        raise ValueError(f"duplicate registry entry: {_e.name}")
    REGISTRY[_e.name] = _e

DOMAIN_TAGS = frozenset(e.targets[0] for e in _ENTRIES if e.status is R.DOMAIN_TAG)


def lookup(name: str) -> RegistryEntry:
    """Status of a requested memory name. Unknown names raise KeyError rather than being guessed."""
    return REGISTRY[name.strip()]


__all__ = ["CAPABILITIES", "CORE_KINDS", "DEFAULT_TTL", "DOMAIN_TAGS", "DURABLE_KINDS", "EPOCH", "MemoryItem",
           "MemoryKind", "Modality", "REGISTRY", "RegistryEntry", "RegistryStatus", "TaskStatus", "iso", "lookup"]
