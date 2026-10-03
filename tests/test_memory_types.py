"""P7-05 memory kinds and the extended registry (ADR-0009).

``REQUESTED`` is every distinct memory name in the owner's P7-05 request of 2026-10-03, in order of first appearance
(repeated names appear once). Every requested name must have an explicit registry status, and every capability the
registry claims must be exercised below, so no memory type is claimed without working code.
"""

from __future__ import annotations

import pytest

from memory_support import ALPHA, BETA, new_store, put, pv
from nawa.memory import MemoryKind, Modality, Principal, TaskStatus
from nawa.memory import consolidation
from nawa.memory.types import CAPABILITIES, CORE_KINDS, DOMAIN_TAGS, REGISTRY, RegistryStatus, lookup
from nawa.verification.states import VerificationState

REQUESTED = """
ذاكرة المحادثة|الذاكرة الدائمة للمستخدم|ذاكرة المهام|ذاكرة المعرفة|ذاكرة الخبرة والإجراءات|الذاكرة الحسية|الذاكرة البصرية
|الذاكرة السمعية|الذاكرة النصية|الذاكرة اللمسية|الذاكرة متعددة الحواس|الذاكرة العاملة|الذاكرة قصيرة المدى
|الذاكرة طويلة المدى|الذاكرة التصريحية|الذاكرة الصريحة|الذاكرة العرضية|الذاكرة الحدثية|الذاكرة الدلالية|الذاكرة السيرية
|الذاكرة الدلالية الشخصية|الذاكرة غير التصريحية|الذاكرة الضمنية|الذاكرة الإجرائية|التهيئة|التكييف الكلاسيكي|التعود
|التحسس|الذاكرة الانفعالية|الذاكرة المكانية|الذاكرة التطلعية|الذاكرة الاسترجاعية|الذاكرة الحركية|الذاكرة الجماعية
|الذاكرة الثقافية|الذاكرة التاريخية|الذاكرة السياسية|الذاكرة الدينية|الذاكرة الأسطورية|الذاكرة الشعبية|الذاكرة الفنية
|الذاكرة الموسيقية|الذاكرة اللغوية|الذاكرة المعمارية|الذاكرة الحضرية|الذاكرة البيئية|الذاكرة المناخية
|الذاكرة الجيولوجية|الذاكرة الفلكية|الذاكرة الكونية|الذاكرة الزمنية العميقة|الذاكرة الجينية|الذاكرة اللاجينية
|الذاكرة المناعية|الذاكرة المناعية التكيفية|خلايا B الذاكرة|خلايا T الذاكرة|خلايا T الذاكرة المركزية
|خلايا T الذاكرة المستجيبة|المناعة الفطرية المدربة|الذاكرة الطبيعية|ذاكرة الخلايا القاتلة الطبيعية
|الذاكرة المنقولة حديثي الولادة|الذاكرة الهولوغرافية|الذاكرة الهولوغرافية متعددة المواضع
|الذاكرة الهولوغرافية متحدة المحور|ذاكرة إكسيتون-بولاريتون الهولوغرافية|الذاكرة الكمومية|الذاكرة الضوئية
|الذاكرة المغناطيسية|الذاكرة المغناطيسية الحديدية|ذاكرة تغير الطور|ذاكرة تغير المقاومة|الذاكرة السبينية
|الذاكرة الطوبولوجية|الذاكرة فائقة التوصيل|الذاكرة العصبية الاصطناعية|الذاكرة العضوية|الذاكرة البوليمرية
|الذاكرة الجزيئية|الذاكرة الجزيئية الكبيرة|الذاكرة الذرية|الذاكرة النانوية|الذاكرة الحيوية المدمجة
|الذاكرة الجزيئية الحيوية|الذاكرة الهجينة الحيوية|الذاكرة الوراثية الاصطناعية|الذاكرة اللاجينية الاصطناعية
|الذاكرة المناعية الاصطناعية|ذاكرة الشكل|ذاكرة نقطة العودة|ذاكرة الصدى|تأثيرات الذاكرة في الزجاج|ذاكرة انتقال موت
|ذاكرة PRAM|الذاكرة الميكانيكية|الذاكرة في السوائل اللزجة|ذاكرة السمة|ذاكرة العلاقة|ذاكرة التغير|ذاكرة النبضة الزمنية
|ذاكرة هوبفيلد|الذاكرة الترابطية|الذاكرة المحتوى-العنوانية|الذاكرة متسلسلة الوصول|الذاكرة ذات الوصول المباشر
|الذاكرة العشوائية|الذاكرة المتطايرة|الذاكرة غير المتطايرة|الذاكرة الديناميكية|الذاكرة الساكنة|الذاكرة الخطية
|الذاكرة غير الخطية|الذاكرة الفيزيائية|الذاكرة المنطقية|الذاكرة الافتراضية|الذاكرة المشتركة|الذاكرة الخاصة
|الذاكرة الموزعة|الذاكرة السحابية|الذاكرة الطرفية|الذاكرة المدمجة|الذاكرة القابلة للبرمجة|الذاكرة القابلة للمسح
|الذاكرة القابلة للتعديل|الذاكرة الثابتة|الذاكرة المخبئية|المستوى الأول|المستوى الثاني|المستوى الثالث|السجلات
|المخزن المؤقت|المكدس|الكومة|ذاكرة الوصول العشوائي|ذاكرة الوصول العشوائي الساكنة|ذاكرة الوصول العشوائي الديناميكية
|ذاكرة الوصول العشوائي المتزامنة|ذاكرة الوصول العشوائي EDO|ذاكرة الوصول العشوائي ECC|DDR1|DDR2|DDR3|DDR4|DDR5
|ذاكرة القراءة فقط|PROM|EPROM|EEPROM|ذاكرة الفلاش|NAND|NOR|القرص الصلب|قرص الحالة الصلبة|الأشرطة المغناطيسية
|الذاكرة قصيرة المدى للوكيل|الذاكرة طويلة المدى للوكيل|الذاكرة الدلالية للوكيل|الذاكرة العرضية للوكيل
|الذاكرة السياقية|الذاكرة الفوقية|ذاكرة الإجراءات|ذاكرة المعتقدات|ذاكرة المشروع|الذاكرة المهنية|ذاكرة الفرد
|ذاكرة الشركة|الذاكرة المتطايرة التنظيمية|الذاكرة الدائمة التنظيمية|ذاكرة المعاملات|الذاكرة الخارجية
|الذاكرة الاجتماعية|الذاكرة التقنية|الذاكرة الطبيعية الخارجية|الذاكرة المرفوعة|الذاكرة القابلة للتنزيل
|الذاكرة الجماعية للذكاء الاصطناعي|الذاكرة الخارجية الاصطناعية|الذاكرة العصبية المباشرة|الذاكرة الرقمية للدماغ
|الذاكرة الوعية|الذاكرة اللاوعية|الذاكرة الجمعية اللاواعية|الذاكرة التخاطرية|الذاكرة الزمنية|الذاكرة البُعدية
|الذاكرة الأكوانية|الذاكرة الأبدية|الذاكرة المطلقة|الذاكرة المثالية|الذاكرة الفوتوغرافية|الذاكرة الحاسوبية الكمومية
|الذاكرة الضوئية الكمومية|الذاكرة المغناطيسية الكمومية|الذاكرة القانونية|الذاكرة الاقتصادية|الذاكرة المالية
|الذاكرة التجارية|الذاكرة الصناعية|الذاكرة العسكرية|الذاكرة الاستخباراتية|الذاكرة الأمنية|الذاكرة الطبية
|الذاكرة السريرية|الذاكرة التمريضية|الذاكرة الصيدلانية|الذاكرة الهندسية|الذاكرة البرمجية|الذاكرة الشبكية
|الذاكرة التسلسلية|الذاكرة المباشرة|الذاكرة المتغيرة|الذاكرة غير المتغيرة
"""
NAMES = [n.strip() for n in REQUESTED.replace("\n", "").split("|") if n.strip()]


def test_requested_list_has_no_duplicates_after_dedup_and_is_fully_registered() -> None:
    assert len(NAMES) == len(set(NAMES)) == 213
    assert set(NAMES) == set(REGISTRY), {"missing": sorted(set(NAMES) - set(REGISTRY)),
                                          "extra": sorted(set(REGISTRY) - set(NAMES))}


def test_the_five_core_kinds_are_the_owners_five() -> None:
    core = {e.name: e.targets for e in REGISTRY.values() if e.status is RegistryStatus.CORE}
    assert core == {"ذاكرة المحادثة": ("conversation",), "الذاكرة الدائمة للمستخدم": ("user_persistent",),
                    "ذاكرة المهام": ("task",), "ذاكرة المعرفة": ("knowledge",),
                    "ذاكرة الخبرة والإجراءات": ("procedural",)}
    assert [k.value for k in CORE_KINDS] == ["conversation", "user_persistent", "task", "knowledge", "procedural"]


def test_every_registry_entry_is_well_formed() -> None:
    kinds = {k.value for k in MemoryKind}
    for e in REGISTRY.values():
        assert e.targets, e
        if e.status in (RegistryStatus.CORE, RegistryStatus.ALIAS):
            assert set(e.targets) <= kinds, e
        elif e.status is RegistryStatus.BUFFER:
            assert set(e.targets) <= {m.value for m in Modality}, e
        elif e.status is RegistryStatus.FEATURE:
            assert set(e.targets) <= CAPABILITIES, e
        elif e.status is RegistryStatus.DOMAIN_TAG:
            assert e.targets[0] in DOMAIN_TAGS, e
        elif e.status is RegistryStatus.DEFERRED:
            assert set(e.targets) <= {"OD-10", "OD-11", "OD-12", "G5", "P4"} and e.note, e
        else:
            assert e.note, e          # NOT_APPLICABLE and REJECTED always say why


def test_no_rejected_or_not_applicable_name_is_claimed_as_working() -> None:
    for name in ("الذاكرة المطلقة", "الذاكرة الأبدية", "الذاكرة التخاطرية", "DDR4", "خلايا T الذاكرة"):
        assert lookup(name).status in (RegistryStatus.REJECTED, RegistryStatus.NOT_APPLICABLE)
    assert lookup("الذاكرة المطلقة").status is RegistryStatus.REJECTED       # conflicts with forgetting
    assert lookup("الذاكرة الجماعية").targets == ("OD-12",)                 # sharing waits for the privacy policy
    with pytest.raises(KeyError):
        lookup("ذاكرة غير مطلوبة")


@pytest.mark.parametrize("tag", sorted(DOMAIN_TAGS))
def test_every_domain_tag_filters_synthetic_knowledge(tag) -> None:
    st = new_store()
    hit = put(st, ALPHA, MemoryKind.KNOWLEDGE, "brelto fact", tags=(tag,))
    put(st, ALPHA, MemoryKind.KNOWLEDGE, "brelto other")
    assert [h.item.item_id for h in st.search(ALPHA, "brelto", tags=(tag,))] == [hit.item_id]


# ------------------------------------------------------------------------------------- capability exercises
def _cap_short_term_ttl(st):
    s = put(st, ALPHA, MemoryKind.SENSORY, "brief", modality=Modality.TEXT)
    st.clock.advance(9)
    ok = st.read(ALPHA, s.item_id) is not None
    st.clock.advance(1)
    return ok and st.read(ALPHA, s.item_id) is None


def _cap_long_term(st):
    u = put(st, ALPHA, MemoryKind.USER_PERSISTENT, "long")
    st.clock.advance(10**7)
    return st.read(ALPHA, u.item_id) is not None and u.expires_at is None


def _cap_volatile(st):
    put(st, ALPHA, MemoryKind.CONVERSATION, "in process only")
    return st.directory is None and new_store().scan(ALPHA) == []


def _cap_persist(st, tmp_path):
    a = new_store(tmp_path)
    it = put(a, ALPHA, MemoryKind.USER_PERSISTENT, "kept on disk")
    return new_store(tmp_path).read(ALPHA, it.item_id) == it


def _cap_erase(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "erase me")
    st.forget(ALPHA, it.item_id)
    return st.read(ALPHA, it.item_id) is None and st.log.entries[-1].id == it.item_id


def _cap_update(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "v1")
    return st.update(ALPHA, it.item_id, "v2", provenance=pv("synthetic:t/2", 0)).content == "v2"


def _cap_read_only(st):
    from nawa.memory import PolicyViolation
    it = put(st, ALPHA, MemoryKind.PROCEDURAL, "fixed", read_only=True)
    try:
        st.update(ALPHA, it.item_id, "x", provenance=pv("synthetic:t/2", 0))
    except PolicyViolation:
        return True
    return False


def _cap_mutable(st):
    it = put(st, ALPHA, MemoryKind.TASK, "goal")
    return st.update(ALPHA, it.item_id, "goal", provenance=pv("synthetic:t/3", 0),
                     task_status=TaskStatus.IN_PROGRESS).task_status is TaskStatus.IN_PROGRESS


def _cap_direct_read(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "direct")
    return st.read(ALPHA, it.item_id) == it


def _cap_sequential(st):
    a = put(st, ALPHA, MemoryKind.CONVERSATION, "first")
    st.clock.advance(1)
    b = put(st, ALPHA, MemoryKind.CONVERSATION, "second")
    return [it.item_id for it in st.scan(ALPHA)] == [a.item_id, b.item_id]


def _cap_content_search(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "dorvel salvek")
    return [h.item.item_id for h in st.search(ALPHA, "salvek")] == [it.item_id]


def _cap_associative(st):
    a = put(st, ALPHA, MemoryKind.KNOWLEDGE, "qisto is heavy", fact_key=("qisto", "weight"))
    b = put(st, ALPHA, MemoryKind.KNOWLEDGE, "the colour is grey", fact_key=("qisto", "colour"))
    put(st, ALPHA, MemoryKind.KNOWLEDGE, "unrelated yorin", fact_key=("yorin", "x"))
    return [h.item.item_id for h in st.associate(ALPHA, a.item_id)] == [b.item_id]


def _cap_cache(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "cached")
    st.read(ALPHA, it.item_id)
    filled = bool(st.dump_state()["cache"]["user_alpha|project_default"])
    put(st, ALPHA, MemoryKind.CONVERSATION, "any write invalidates")
    return filled and not st.dump_state()["cache"]["user_alpha|project_default"]


def _cap_private(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "mine")
    return st.read(BETA, it.item_id) is None and st.acl(ALPHA, it.item_id)["readers"] == ["user_alpha"]


def _cap_project(st):
    it = put(st, Principal("user_alpha", "project_x"), MemoryKind.TASK, "project goal")
    return st.read(ALPHA, it.item_id) is None and st.read(Principal("user_alpha", "project_x"), it.item_id) == it


def _cap_logical_time(st):
    st.clock.advance(5)
    a = put(st, ALPHA, MemoryKind.CONVERSATION, "early kavun")
    st.clock.advance(5)
    put(st, ALPHA, MemoryKind.CONVERSATION, "late kavun")
    return [h.item.item_id for h in st.search(ALPHA, "kavun", until=5)] == [a.item_id]


def _cap_metamemory(st):
    put(st, ALPHA, MemoryKind.KNOWLEDGE, "a fact")
    put(st, ALPHA, MemoryKind.KNOWLEDGE, "a belief", verification_state=VerificationState.UNCERTAIN)
    m = st.introspect(ALPHA)
    return m["items"] == 2 and m["facts"] == 1 and m["beliefs"] == 1 and m["with_provenance"] == 2


def _cap_belief(st):
    b = put(st, ALPHA, MemoryKind.KNOWLEDGE, "maybe nupra", verification_state=VerificationState.UNCERTAIN)
    return b.epistemic == "belief" and st.search(ALPHA, "nupra", facts_only=True) == []


def _cap_attribute(st):
    return put(st, ALPHA, MemoryKind.KNOWLEDGE, "mirsel colour blue", fact_key=("mirsel", "colour")).fact_key == (
        "mirsel", "colour")


def _cap_relation(st):
    return put(st, ALPHA, MemoryKind.KNOWLEDGE, "mirsel near tobrak",
               fact_key=("mirsel", "near", "tobrak")).fact_key == ("mirsel", "near", "tobrak")


def _cap_versions(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "v1")
    st.update(ALPHA, it.item_id, "v2", provenance=pv("synthetic:t/2", 0))
    return [v.version for v in st.versions(ALPHA, it.item_id)] == [1, 2]


def _cap_prospective(st):
    t = put(st, ALPHA, MemoryKind.TASK, "call later", due_at=50)
    early = st.due_tasks(ALPHA)
    st.clock.advance(50)
    return early == [] and [x.item_id for x in st.due_tasks(ALPHA)] == [t.item_id]


def _cap_fusion(st):
    put(st, ALPHA, MemoryKind.SENSORY, "flash", modality=Modality.VISUAL, tags=("event:e",))
    put(st, ALPHA, MemoryKind.SENSORY, "buzz", modality=Modality.TACTILE, tags=("event:e",))
    created, _ = consolidation.apply(st, ALPHA)
    return [c.modality for c in created] == [Modality.MULTISENSORY]


def _cap_index(st):
    it = put(st, ALPHA, MemoryKind.CONVERSATION, "fendra glomir")
    return it.item_id in st.dump_state()["tokens"]["user_alpha|project_default"]["glomir"]


EXERCISES = {
    "short_term_ttl": _cap_short_term_ttl, "long_term": _cap_long_term, "volatile_in_process": _cap_volatile,
    "persist_to_disk": _cap_persist, "erase": _cap_erase, "update_with_provenance": _cap_update,
    "read_only": _cap_read_only, "mutable": _cap_mutable, "direct_read": _cap_direct_read,
    "sequential_scan": _cap_sequential, "content_search": _cap_content_search,
    "associative_recall": _cap_associative, "read_cache": _cap_cache, "private_acl": _cap_private,
    "project_scope": _cap_project, "logical_time": _cap_logical_time, "metamemory": _cap_metamemory,
    "belief_vs_fact": _cap_belief, "attribute_key": _cap_attribute, "relation_key": _cap_relation,
    "version_history": _cap_versions, "prospective_due": _cap_prospective, "fusion": _cap_fusion,
    "inverted_index": _cap_index,
}


def test_every_capability_has_an_exercise() -> None:
    assert set(EXERCISES) == set(CAPABILITIES)
    claimed = {c for e in REGISTRY.values() if e.status is RegistryStatus.FEATURE for c in e.targets}
    assert claimed <= set(EXERCISES)


@pytest.mark.parametrize("cap", sorted(CAPABILITIES))
def test_capability_works(cap, tmp_path) -> None:
    fn = EXERCISES[cap]
    st = new_store()
    assert (fn(st, tmp_path) if cap == "persist_to_disk" else fn(st)) is True


@pytest.mark.parametrize("modality", list(Modality))
def test_every_sensory_modality_is_a_transient_buffer(modality) -> None:
    st = new_store()
    it = put(st, ALPHA, MemoryKind.SENSORY, "synthetic signal", modality=modality)
    assert it.expires_at == 10 and it.provenance.source_ref.startswith("synthetic:")
