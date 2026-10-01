# NAWA — ROADMAP.md

## خارطة الطريق الموحدة: من الصفر إلى نظام قابل للإصدار

**الإصدار:** 1.0.0-unified

**الاسم:** NAWA — Native Arabic Weighted Architecture

**القاعدة المركزية:** كل إنجاز يحدّث هذه الخارطة فورًا. لا يُعاد تنفيذ مهمة لها Task ID أو مخرج مسجل. المقياس المجمّد هو الحكم، لا الانطباع ولا انخفاض loss.

---

# 0. كيف تُستخدم الخارطة

## ترتيب القراءة

كل وكيل يقرأ بالترتيب:

1. `AGENTS.md`.
2. هذا الملف كاملًا.
3. قسم `STATUS` وسجل التغييرات.
4. المهمة ذات أقل ID غير منجزة.
5. ملفات المخرج والـ PR المشار إليها.

## دورة المهمة

```text
اعثر على Task ID
→ افحص عدم التكرار
→ احجزه
→ نفذ
→ اختبر
→ قيّم
→ سجل التجربة
→ حدّث هذه الخارطة
→ افتح PR
→ أغلق المهمة بعد المراجعة
```

## المساران

### S — NAWA Core من الصفر

مسار السيادة: نواة وTokenizer وتدريب مملوكة، لا تُدخل أوزان نماذج أخرى إلى الناتج الأساسي، ولا تعتمد النسخة النهائية على API خارجي.

### B — مسار اختياري عند الحاجة التقنية فقط

مسار **اختياري**، ليس شرطًا لأي بوابة، ولا يُفتح إلا عند حاجة تقنية محددة وموثقة: تشغيل محلي أو خاص، اختبار تقنية أو معمارية، أو مكوّن يجب أن يعمل دون مزود خارجي. كل نموذج مفتوح الأوزان يُستخدم أو يُرفض يُسجَّل في `configs/model_registry.yaml` مع الأسئلة الستة في ADR-0003، ويفرض ذلك `tests/test_model_registry.py`. الناتج يبقى `nawa-practical-baseline` ولا يُسمى NAWA Core.

**سبب الفصل:** لا يوجد تعارض بين البناء من الصفر واستخدام أداة خارجية إذا كان لكل منهما lineage وقياس واسم وmanifest مستقل، ولم تصبح الأداة الخارجية شرطًا للتقدم.

## هدف NAWA ومعنى المرجع (ADR-0003)

- **الهدف هو ابتكار وبناء نظام أصلي**، لا مقارنة النماذج ولا التفوق في جدول مقارنة. NAWA لا يجب أن يشبه أي نموذج موجود.
- **لا توجد مهمة إلزامية لتشغيل Qwen أو أي نموذج مفتوح الأوزان**، ولا يوجد baseline خارجي شرطًا لإغلاق أي بوابة أو للانتقال إلى أي مرحلة.
- **كلمة baseline في هذه الخارطة تعني مرجعًا داخليًا لـ NAWA** ما لم يُذكر خلاف ذلك صراحة: مراجع التقييم التافهة (`oracle` و`always_abstain`، P1-07)، والنواة المرجعية لـ NAWA (P3-04/P3-05)، والنواة وحدها دون طبقات النظام (ablation "model only" في P6-09)، والإصدار المقبول السابق من NAWA (T5 وP9-06).
- **لا ينتظر العمل أي نموذج خارجي.** النماذج الخارجية أدوات تطوير مساعدة (مراجعة، تصميم، اختبار خصمي) ضمن حوكمة ADR-0003، ولا تكون مصدر الحكم ولا شرطًا للتقدم.

## قواعد تشغيل معتمدة من المالك (2026-09-30)

- **التنفيذ المتتابع:** ينفذ الوكيل دائمًا أعلى مهمة غير منجزة وغير محجوبة، دون انتظار أمر مستقل لكل مهمة.
- **قرارات المالك لا توقف المشروع كله:** القرار الجوهري غير المحدد يُسجَّل في §2.4 بوصفه `OWNER DECISION REQUIRED`، ويستمر العمل المستقل عنه.
- **إغلاق البوابات بالترتيب:** يجوز تنفيذ مهام مرحلة لا تعتمد على قرار معلّق. أما **إغلاق** بوابة فيتطلب إغلاق كل البوابات السابقة لها. ولا تبدأ مرحلة تعتمد مخرجاتها على بوابة سابقة غير مغلقة (مثل البيانات والتدريب).
- **الدمج:** يجوز للوكيل دمج الـ PR الذي فتحه بعد نجاح CI (تفويض المالك بتاريخ 2026-09-30). قاعدة استقلال الحكم (`AGENTS.md` §6) باقية: البوابة التي يغلقها قياس أجراه الوكيل نفسه تُعلَّم `PENDING_REVIEW` حتى يراجعها المالك.
- **إصلاح الخارطة:** يُصلح الوكيل التعارضات الداخلية في هذه الخارطة بشرط ألا يغير هدف المشروع ولا المسارات المعمارية، وألا يخفض أي معيار، وألا يحذف مهمة أو نتيجة، وأن يسجل كل تعديل في §12 أو في ADR.
- **مستودع GitHub العام:** وضع مؤقت موثق (ADR-0001 C1). لا تُوضع فيه أسرار ولا بيانات خاصة ولا أوزان ولا مجموعة `frozen`.
- **النماذج الخارجية (توجيه المالك 2026-09-30، ADR-0003):** لا تُستخدم النماذج مفتوحة الأوزان افتراضيًا، ولا تُنتظر نتائجها قبل متابعة أهداف NAWA. لا قرار يعتمد على نموذج واحد. لا تُرسل مجموعة `frozen` ولا بيانات المستخدم ولا أسراره إلى أي نموذج خارجي. لا تُستخدم مخرجات نموذج خارجي للتدريب أو التقطير قبل فحص شروطه وتسجيل القرار (OD-10).

---

# 1. تعريف النجاح والحدود

## 1.1 تعريف NAWA

NAWA ليس وزنًا فقط:

```text
Core Model
+ Tokenizer
+ Sparse/Task Experts
+ Router
+ Retrieval
+ Tools
+ Reasoning Runtime
+ Verification
+ Calibrated Abstention
+ Memory
+ Continual Learning
+ Runtime/Compression
+ Evaluation/Lineage
```

## 1.2 هدف التفرد

التفرد ليس في ادعاء “أقوى ألف مرة من الجميع”، بل في نظام يحقق، على اختبارات معلنة ومغلقة:

- أخطاء أقل في الادعاءات غير المدعومة.
- امتناعًا صحيحًا بدل التخمين.
- استشهادًا قابلًا للفحص.
- اختيارًا صحيحًا للأدوات.
- قدرة أعلى لكل معلمة وGB وFLOP وواط.
- تفوقًا عربيًا موثقًا في المجال الأول.
- قابلية إعادة الإنتاج والتراجع.

## 1.3 الأهداف الابتدائية

المرجع في T1 وT2 وT5 داخلي (انظر §0 "معنى المرجع"). تُثبَّت تعريفات الأهداف في `P1-06`، وتُثبَّت أرقامها على أول نواة NAWA مدربة على نص حقيقي في `P1-06a` (ADR-0004). يُسمح برفع الهدف فقط دون خفضه:

| الرمز | الهدف الابتدائي المقترح | ملاحظة |
|---|---|---|
| T1 | خفض الهلوسة النسبية ≥ 50% مقابل baseline نفسه | على `faithfulness` و`factual` |
| T2 | امتناع صحيح ≥ 80% في نقص الدليل مع عدم خفض الإجابات الصحيحة أكثر من 5% نسبيًا | يمنع الامتناع الدائم |
| T3 | مطابقة أو تجاوز نموذج أكبر 4–8× في المجال الأول | اختياري: مؤشر كفاءة لا شرط لأي بوابة (ADR-0003)؛ يُقاس فقط عند حاجة موثقة |
| T4 | نسخة محلية بذاكرة ≤ 3GB وقياس سرعة مستهدف على CPU | يُثبت بعد معرفة العتاد |
| T5 | لا تراجع عام أكبر من 3% نسبيًا | `regression_general` |
| T6 | دقة الاستشهاد ومطابقة الادعاء تُقاسان منفصلتين | لا يكفي وجود رابط |

---

# 2. الحالة الحالية

> هذه الخانة هي سجل العمل الحي. كل وكيل يحدّثها مع كل مهمة. لا تستخدم ملف حالة موازيًا إلا إذا كان يطابقها آليًا.

## 2.1 حالة البوابات

> البوابة Gn تُغلق المرحلة Pn، وتعريفها الملزم في §4. قيمة الحالة الإضافية `PENDING_REVIEW` معناها أن الأدلة مكتملة وأن البوابة تنتظر مراجعة مستقلة.

| البوابة | الحالة | آخر تحديث | الدليل |
|---|---|---|---|
| G0 الميثاق والحدود وCI مبدئي (P0) | IN_PROGRESS | 2026-09-30 | P0-05 وP0-06 وP0-08 منجزة؛ CI يعمل (`d34f3f1`)؛ مستودعات HF خاصة؛ الميثاق والنطاق الأول والميزانية بانتظار المالك؛ انظر §2.3 |
| G1 القياس والمرجع الداخلي (P1) | PENDING_REVIEW | 2026-09-30 | كل شروط G1 في §4 لها دليل: مراجع P1-07 ونواة P3-05 محفوظة (EXP-0008..0010)؛ frozen له hash ومكان خاص (P1-03)؛ لا بيانات تدريب نصية بعد، وسجلات Atlas المشتقة من التقييم ممنوعة من التدريب (P1-08)؛ أمر إعادة التقرير موجود (P1-07). P1-01..P1-03 وP1-06 وP1-07 وP1-08 منجزة؛ P1-04 وP1-05 SUPERSEDED؛ P1-02a محجوبة بـ OD-01 وليست شرطًا لـ G1؛ P1-06a شرط لـ G5 (ADR-0004). تنتظر مراجعة المالك (§0: قاعدة استقلال الحكم) |
| G2 أطلس الإخفاقات ومصنع البيانات (P2) | IN_PROGRESS | 2026-10-01 | P2-02 منجزة (`verify.py`، EXP-0016). P2-05 منجزة (أدوات التنظيف، EXP-0018)؛ P2-03 منجزة (توائم الامتناع، EXP-0019)؛ P2-04 منجزة (أزواج التفضيل، EXP-0021)؛ كشف التسرب الجزئي إلى frozen ينتظر P2-05a. ADR-0005: مهام الكود P2-02..P2-05 غير محجوبة (أدوات واختبارات على مدخلات اصطناعية، لا بيانات تدريب ولا رفع)؛ P2-01 وP2-06..P2-08 BLOCKED بقرارات المالك؛ شروط G2 لم تتغير، ولا تُغلق قبل G0 وG1 |
| G3 Tokenizer ونواة مرجعية (P3) | IN_PROGRESS | 2026-09-30 | P3-04..P3-08 منجزة: decoder مرجعي + XOR/tiny LM + trainer كامل + device support + numerical verification (266 اختبارًا)؛ باقي الـ Tokenizer (P3-01..P3-03) ويحتاج مدونة عربية مرخصة (مشروطة بـ P2/G2)؛ لا يُغلق G3 قبل G0–G2 |
| G4 دراسات الكفاءة والابتكار (P4) | PLANNED | — | — |
| G5 تدريب النواة (P5) | PLANNED | — | — |
| G6 نظام الاستدلال والتحقق (P6) | PLANNED | — | — |
| G7 الخبراء والمحولات والذاكرة (P7) | PLANNED | — | — |
| G8 الضغط والكفاءة (P8) | PLANNED | — | — |
| G9 التعلم المستمر ومقاومة الانحدار (P9) | PLANNED | — | — |
| G10 الإصدار 1.0 — تعريف 100% (P10) | PLANNED | — | — |

## 2.2 سجل المهام

الحالات المسموحة: `PLANNED`, `CLAIMED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `DONE`, `REJECTED`, `SUPERSEDED`.

| Task ID | الحالة | المالك | المخرج/الدليل | آخر تحديث |
|---|---|---|---|---|
| P0-01 | BLOCKED | bootstrap-agent | `PROJECT_CHARTER.md` مسودة كاملة البنية؛ تنتظر OD-01 وOD-02 وOD-03 وOD-04 وOD-09 | 2026-09-30 |
| P0-02 | BLOCKED | bootstrap-agent | `ARCHITECTURE.md` يغطي مكونات §1.1 ويعرّف Core مقابل Runtime (`tests/test_governance_docs.py`)؛ الاعتماد ينتظر OD-09 | 2026-09-30 |
| P0-03 | DONE | bootstrap-agent | `SUCCESS_CRITERIA.md`: T1–T6 مطابقة رقميًا لـ §1.3 (`test_success_criteria_carries_every_roadmap_target_number`)؛ التثبيت الرقمي النهائي في P1-06 | 2026-09-30 |
| P0-04 | DONE | bootstrap-agent | `SECURITY.md` و`RISK_REGISTER.md` (15 خطرًا، `test_risk_register_is_well_formed`) | 2026-09-30 |
| P0-05 | DONE | bootstrap-agent | بنية المستودع، `AGENTS.md`، `.gitignore`؛ `tests/test_repository_structure.py` (30 اختبارًا ناجحًا) | 2026-09-30 |
| P0-06 | DONE | bootstrap-agent | 8 مستودعات HF خاصة وفارغة تحت `vuuuv`؛ `configs/hf_repos.yaml`؛ `tests/test_config_loading.py` (5 اختبارات ناجحة) | 2026-09-30 |
| P0-07 | BLOCKED | — | السقوف تنتظر OD-05 | 2026-09-30 |
| P0-07a | DONE | bootstrap-agent | `configs/budget.yaml` بسقوف `null` وعتبة 80%؛ `src/nawa/budget.py` يمنع العمل على GPU والعمل المدفوع؛ اختباران | 2026-09-30 |
| P0-08 | DONE | bootstrap-agent | `ROADMAP.md` وسجل الحالة و`.github/CODEOWNERS` و`ci.yml`؛ CI نجح على `d34f3f1`؛ `main` محمي (PR إلزامي، فحص `test`، منع force push والحذف، enforce_admins) | 2026-09-30 |
| R-01 | DONE | bootstrap-agent | اتساق الخارطة: ADR-0002، `tests/test_roadmap_consistency.py` | 2026-09-30 |
| R-02 | DONE | agent-R-02 | مواءمة الخارطة و`AGENTS.md` مع توجيه المالك: نظام أصلي، لا baseline خارجي شرطًا؛ ADR-0003؛ `configs/model_registry.yaml`؛ `tests/test_model_registry.py` و`tests/test_original_system_policy.py` | 2026-09-30 |
| R-04 | DONE | agent-R-04 | فك حلقة اعتمادية P1-06: فصلها إلى P1-06 (تعريفات، شرط G1) وP1-06a (أرقام على أول نواة نصية، شرط G5)؛ ADR-0004؛ `tests/test_roadmap_consistency.py` | 2026-09-30 |
| R-03 | DONE | agent-R-03 | `docs/multi_model_review.md`، `src/nawa/review.py` (ReviewRole، ModelEntry، ModelRegistry، ReviewRecord، DisagreementRecord، ReviewLog، check_payload، can_decide)؛ `tests/test_multi_model_review.py` (46 اختبارًا بعد إصلاح المراجعة)؛ EXP-0015؛ PR #17 | 2026-10-01 |
| P1-01 | DONE | bootstrap-agent | `docs/failure_taxonomy.md`: FT-01..FT-16، منها 11 فئة تطلبها P1-01؛ `src/nawa/evaluation/taxonomy.py`؛ `tests/test_failure_taxonomy.py` (4 اختبارات) | 2026-09-30 |
| P1-02 | DONE | bootstrap-agent | 9 مجموعات في `src/nawa/evaluation/suites/` + `eval/suites/README.md` + `factual_bank.yaml`؛ dev=243 وcalib=128 عنصرًا؛ `tests/test_eval_suites.py` (15 اختبارًا) | 2026-09-30 |
| P1-02a | BLOCKED | — | مجموعة `domain` تنتظر OD-01 (المجال الأول) | 2026-09-30 |
| P1-03 | DONE | bootstrap-agent | frozen v1: 243 عنصرًا في HF `vuuuv/nawa-eval` الخاص (tag `frozen-v1`، commit `5eb6594`)؛ `eval/FROZEN.sha256`، `eval/frozen_item_hashes.txt`، `eval/frozen_manifest.yaml`؛ `tests/test_frozen_eval.py` (5 اختبارات) | 2026-09-30 |
| P1-04 | SUPERSEDED | agent-R-02 | ألغاها المالك (ADR-0003): لا مقارنة إلزامية مع نماذج خارجية. التقارير الثلاثة الجزئية محفوظة دون اعتماد في `eval/reports/` (EXP-0001..EXP-0003)، وتشغيل 1.5B أُوقف قبل اكتماله (EXP-0004). لا تُستخدم نتائجها في أي هدف أو بوابة | 2026-09-30 |
| P1-05 | SUPERSEDED | agent-R-02 | دُمجت في P3-04/P3-05: المرجع الداخلي هو نواة NAWA المرجعية نفسها، فلا حاجة لمهمة موازية (ADR-0003) | 2026-09-30 |
| P1-06 | DONE | agent-P1-06 | تعريفات T1–T6 مثبتة في `eval/targets.yaml` (schema v2): المقياس، والعتبة (أرقام §1.3 دون تغيير)، ونوع المرجع، ومصدر التقييم؛ T1 مشروط بـ T2؛ مدقّق `nawa.evaluation.targets`؛ الأرقام في P1-06a (ADR-0004) | 2026-09-30 |
| P1-06a | PLANNED | — | تثبيت أرقام T1 وT2 وT5 وT6 على أول نواة NAWA مدربة على نص حقيقي؛ تنتظر أول مرشح من P5؛ شرط لـ G5 (ADR-0004) | 2026-09-30 |
| P1-07 | DONE | bootstrap-agent | `eval/run_eval.py`، `eval/report.py`، `eval/targets.yaml`، `src/nawa/evaluation/{runner,report}.py`؛ `make eval` و`make report` و`make repro`؛ `tests/test_eval_runner.py` (10 اختبارات) | 2026-09-30 |
| P1-08 | DONE | agent-P1-08 | أول 224 سجلًا في Atlas، كلها متحققة حتميًا وممنوعة من التدريب، ومثبتة ببصمة في `data_pipeline/atlas/manifest.yaml` (البيانات خارج Git)؛ `nawa.atlas` (schema، ingest، validate)؛ إصلاح تصنيف الامتناع إلى FT-13 | 2026-09-30 |
| R-05 | DONE | agent-R-05 | تحديد مهام P2 القابلة للتنفيذ قبل إغلاق G0/G1 وفق قاعدة §0: كود فقط، دون بيانات تدريب أو رفع؛ ADR-0005 (ACCEPTED بتوجيه المالك 2026-10-01)؛ `tests/test_roadmap_consistency.py`؛ PR #18 | 2026-10-01 |
| P2-01 | BLOCKED | — | `mine.py` يحتاج نموذجًا نصيًا: نواة NAWA نصية (P5) أو أدوات خارجية مصرحًا بها (OD-10)؛ مسار تشغيلات التقييم الحتمي مغطى في P1-08 (ADR-0005) | 2026-10-01 |
| P2-02 | DONE | agent-P2-02 | `src/nawa/data_verify.py` و`data_pipeline/atlas/verify.py` و`configs/verification.yaml`: تحقق مستقل بأربع طرق (حساب، تنفيذ في sandbox، مصدر مرخص، مراجعة خبير بشري) وبوابة أهلية التدريب (G2 ودفعات التقييم وبصمات frozen)؛ `tests/test_data_verify.py` (40 اختبارًا)؛ EXP-0016 | 2026-10-01 |
| P2-03 | DONE | agent-P2-03 | `src/nawa/data/twins.py`: منشئ ومدقق توائم الامتناع (سفن خيالية، قوالب ومحث نظام مستقلان عن التقييم، مشتت يملك الخاصية المسؤول عنها)؛ `tests/test_twins.py` (24 اختبارًا)؛ EXP-0019 | 2026-10-01 |
| P2-04 | DONE | agent-P2-04 | `src/nawa/data/preference.py`: schema ومنشئ ومدقق أزواج التفضيل (`judge` حتمي، و`rejected_failure` من FT-01/02/07/12/13/14)، و`from_model_outputs` للمخرجات الحقيقية لاحقًا (P2-01 أو P5)؛ `tests/test_preference.py` (23 اختبارًا)؛ EXP-0020 (FAILED) ثم EXP-0021 | 2026-10-01 |
| P2-05 | DONE | agent-P2-05 | `src/nawa/data/` (clean، pii، dedup، decontam، quality، provenance، pipeline) و`configs/data_pipeline.yaml`؛ `tests/test_data_pipeline.py` (31 اختبارًا)؛ EXP-0017 (FAILED: quality recall 0.35) ثم EXP-0018 (كل المعايير محققة) | 2026-10-01 |
| P2-05a | PLANNED | — (Eval role فقط) | فهرس n-gram مُجزّأ (hashed) لنص frozen في `nawa-eval` الخاص، يقرؤه `ContaminationIndex` عبر `extra_index_files` لكشف التسرب الجزئي إلى frozen دون إدخال نصه إلى Git أو إلى الوكيل؛ شرط لـ "صفر تسرب معروف إلى frozen" في G2 | 2026-10-01 |
| P2-06 | BLOCKED | — | طبقات البيانات تحتاج مصادر حقيقية مرخصة (OD-03) والمجال الأول (OD-01) (ADR-0005) | 2026-10-01 |
| P2-07 | BLOCKED | — | `DATA_SOURCES.md` و`LICENSES.md` وdata cards تنتظر OD-03 (ADR-0005) | 2026-10-01 |
| P2-08 | BLOCKED | — | رفع `nawa-data:v1` ينتظر OD-03 واعتماد الحقوق (G2) (ADR-0005) | 2026-10-01 |
| P3-01..P3-03 | PLANNED | — | — | — |
| P3-04 | DONE | agent-P3-04 | `src/nawa/model/{config,layers,decoder}.py` (نواة decoder مرجعية من الصفر، مكوّنات قابلة للتبديل لتجارب P4)؛ `configs/base_model.yaml`؛ `tests/test_reference_decoder.py` (49 اختبارًا)؛ EXP-0006 | 2026-09-30 |
| P3-05 | DONE | agent-P3-05 | `src/nawa/training/sanity.py` (XOR + tiny character LM على مصدر ماركوف عربي اصطناعي بإنتروبيا محسوبة بدقة)؛ `make sanity`؛ `tests/test_sanity_training.py` (9 اختبارات)؛ EXP-0007 (FAILED) وEXP-0008 وEXP-0009 (PASSED) | 2026-09-30 |
| P3-06 | DONE | agent-P3-06 | `src/nawa/training/trainer.py` (Trainer، TrainerConfig، CheckpointState، DeviceWrapper، scheduler، optimizer، gradient accumulation، mixed precision، metrics، budget guard)؛ `Makefile` (`make train`)؛ `tests/test_trainer.py` (35 اختبارًا)؛ EXP-0012 | 2026-09-30 |
| P3-07 | DONE | agent-P3-07 | `src/nawa/training/trainer.py` (DistributedConfig، DeviceWrapper: GPU auto-detect، CUDA fallback، DDP wrap/unwrap، barrier، should_save/should_log، init/cleanup_distributed)؛ `tests/test_device_support.py` (28 اختبارًا، 1 تخطي)؛ EXP-0013 | 2026-09-30 |
| P3-08 | DONE | agent-P3-08 | `tests/test_numerical_verification.py` (19 اختبارًا: determinism, checkpoint resume identity, gradient accumulation equivalence, numerical stability, checkpoint integrity, integration)؛ EXP-0014 | 2026-09-30 |
| P4-01..P4-08 | PLANNED | — | — | — |
| P5-01..P5-10 | PLANNED | — | — | — |
| P6-01..P6-09 | PLANNED | — | — | — |
| P7-01..P7-08 | PLANNED | — | — | — |
| P8-01..P8-08 | PLANNED | — | — | — |
| P9-01..P9-08 | PLANNED | — | — | — |
| P10-01..P10-08 | PLANNED | — | — | — |

> عند تفصيل مهمة، لا تغير ID مستعملًا. أضف subtask مثل `P2-03a` أو ADR يشرح إعادة النطاق.

## 2.3 تقارير إنجاز المهام

### P0-05 + P0-06 + P0-08 — تأسيس المستودع وربط HF وحماية main (2026-09-30)

- **Task ID:** P0-05، P0-06 (ومساهمات جزئية في P0-01..P0-04 وP0-08)
- **Owner:** bootstrap-agent
- **Status:** P0-05 DONE، P0-06 DONE، والبقية حسب §2.2
- **Scope:** إنشاء مستودع Git وملفات التأسيس الصغيرة ومستودعات HF الخاصة الفارغة. لا تدريب ولا بيانات ولا أوزان.
- **Files created:** `AGENTS.md`، `ROADMAP.md` (من `NAWA-AGENTS.md` و`NAWA-ROADMAP.md`)، `README.md`، `PROJECT_CHARTER.md`، `ARCHITECTURE.md`، `SUCCESS_CRITERIA.md`، `SECURITY.md`، `CONTRIBUTING.md`، `LICENSE` (placeholder)، `pyproject.toml`، `Makefile`، `.gitignore`، `.pre-commit-config.yaml`، `.secrets.baseline`، `.github/workflows/ci.yml`، `.github/CODEOWNERS`، `configs/hf_repos.yaml`، `src/nawa/{__init__,config}.py`، `tests/test_repository_structure.py`، `tests/test_config_loading.py`، `docs/decisions/ADR-0001-bootstrap-open-issues.md`، و`.gitkeep` في `training/ eval/ scripts/ experiments/ data_pipeline/`
- **Files modified:** `ROADMAP.md` (§2.1، §2.2، §2.3، §12 فقط)
- **Tests executed:** `python -m pytest` و`detect-secrets-hook --baseline .secrets.baseline` و`pre-commit run --all-files`
- **Test results:** 35 passed / 0 failed؛ detect-secrets نظيف؛ جميع hooks الـ pre-commit نجحت
- **Metrics:** لا يوجد. مرحلة تأسيس بلا نموذج.
- **Git commit:** `d34f3f1374bdc036474c22bf53da667ef1082567` على `main` (`chore: initialize NAWA project structure`)؛ CI `test`: success
- **HF repository/revision:** `vuuuv/nawa-data`، `vuuuv/nawa-eval` (dataset)؛ `vuuuv/nawa-core`، `vuuuv/nawa-practical-baseline`، `vuuuv/nawa-verifier`، `vuuuv/nawa-gguf`، `vuuuv/nawa-adapters` (model)؛ `vuuuv/nawa-demo` (space، static). جميعها `private=true` وفارغة، ولم يُرفع إليها شيء.
- **Dataset version:** لا يوجد
- **Known limitations:** انظر ADR-0001: C1 مستودع GitHub عام، C2 وجود `vuuuv/nawa` سابقًا، C3 ملفات قالب Space، C4 وC5 تعارضات داخل الخارطة، C6 `RISK_REGISTER.md` و`budget.yaml` غير منشأين.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P1-01 (`docs/failure_taxonomy.md`). المهام P0-01 وP0-03 وP0-07 مجمدة بانتظار قرارات المالك.
- **Duplicate-work check:** المستودع البعيد `sooovg/nawa` كان فارغًا (size 0، بلا commits). مستودعات HF الثمانية لم تكن موجودة قبل الإنشاء. لا فروع ولا PRs سابقة.

### P0-02 + P0-03 + P0-04 + P0-07a — وثائق الحوكمة وحارس الميزانية (2026-09-30)

- **Task ID:** P0-02 (BLOCKED)، P0-03 (DONE)، P0-04 (DONE)، P0-07a (DONE)، P0-07 (BLOCKED)
- **Owner:** bootstrap-agent
- **Scope:** ربط وثائق P0 بالخارطة باختبارات آلية، وسجل المخاطر، وإطار الميزانية دون أرقام المالك.
- **Files created:** `RISK_REGISTER.md`، `configs/budget.yaml`، `src/nawa/budget.py`، `tests/test_governance_docs.py`
- **Files modified:** `PROJECT_CHARTER.md` (سطر الميزانية)، `tests/test_repository_structure.py` (ملفات مطلوبة)، `ROADMAP.md`
- **Tests executed:** `python -m pytest`، `pre-commit run --all-files`
- **Test results:** 49 passed / 0 failed
- **Metrics:** n/a
- **Git commit:** PR لهذه المهام (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **Known limitations:** P0-01 وP0-02 وP0-07 تنتظر قرارات المالك في §2.4؛ لذلك لا يمكن إغلاق G0.
- **Roadmap section updated:** §2.2، §2.3، §4 (P0-07a)، §12
- **Next unblocked task:** P1-01
- **Duplicate-work check:** لم يسبق إنشاء `RISK_REGISTER.md` ولا `budget.yaml`؛ هذه المهام لم تُحجز في أي فرع آخر.

### P1-01 — تصنيف الإخفاقات (2026-09-30)

- **Task ID:** P1-01
- **Owner:** bootstrap-agent
- **Status:** DONE
- **Scope:** تصنيف الإخفاقات بمعرفات ثابتة قابلة للقراءة الآلية، لتستخدمه مجموعات التقييم والأطلس.
- **Files created:** `docs/failure_taxonomy.md`، `src/nawa/evaluation/{__init__,taxonomy}.py`، `tests/test_failure_taxonomy.py`
- **Files modified:** `ROADMAP.md`
- **Tests executed:** `python -m pytest`، `pre-commit run --all-files`
- **Test results:** 53 passed / 0 failed
- **Metrics:** 16 فئة (FT-01..FT-16)؛ الفئات الـ 11 المطلوبة في P1-01 كلها موجودة
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **Known limitations:** FT-12..FT-16 إضافات تقيسها مجموعات AGENTS §10 مباشرة؛ الإضافة لا تغير أي معيار.
- **Roadmap section updated:** §2.2، §2.3، §12
- **Next unblocked task:** P1-02
- **Duplicate-work check:** لم يكن الملف موجودًا، ولا فرع أو PR سابق للمهمة P1-01.

### P1-02 — مجموعات التقييم (2026-09-30)

- **Task ID:** P1-02
- **Owner:** bootstrap-agent
- **Status:** DONE (9 من 10 مجموعات؛ `domain` في P1-02a وهي BLOCKED)
- **Scope:** مولدات ومقيّمات حتمية لتسع مجموعات تقييم بإجابات قابلة للتحقق الآلي، مع sandbox لتنفيذ الكود.
- **Files created:** `src/nawa/evaluation/{normalize,schema,synth,sandbox,build}.py`، `src/nawa/evaluation/suites/*.py` (9 مجموعات + `_context.py`)، `eval/suites/README.md`، `eval/suites/factual_bank.yaml`، `tests/test_eval_suites.py`
- **Files modified:** `.gitignore` (`eval/build/`)، `ROADMAP.md`
- **Tests executed:** `python -m pytest`، `pre-commit run --all-files`، بناء dev وcalib
- **Test results:** 68 passed / 0 failed؛ الـ oracle يحقق 100% في كل المجموعات؛ الضوضاء ≤ 5%
- **Metrics:** dev: 243 عنصرًا، calib: 128 عنصرًا، بلا تداخل (content_hash)
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** dev/calib تُبنى حتميًا من البذرتين 1001 و2002 (غير محفوظة في Git)
- **Known limitations:** المطابقة نصية متساهلة؛ القوالب مشتركة بين الأقسام؛ بنك factual يحتاج مراجعة بشرية؛ sandbox على مستوى العملية فقط.
- **Roadmap section updated:** §2.2، §2.3، §2.4 (OD-01)، §4 (P1-02a)، §12
- **Next unblocked task:** P1-03
- **Duplicate-work check:** لم تكن توجد مجموعات تقييم أو فرع سابق لها.

### P1-03 — فصل التقييم وتجميد frozen (2026-09-30)

- **Task ID:** P1-03
- **Owner:** bootstrap-agent (Eval role)
- **Status:** DONE
- **Scope:** فصل dev/calib/frozen، وبناء frozen من بذرة سرية تُستخدم مرة واحدة، وتثبيته بالـ hash، ورفعه إلى HF خاص، وحارس دور Eval.
- **Files created:** `src/nawa/evaluation/frozen.py`، `eval/FROZEN.sha256`، `eval/frozen_item_hashes.txt`، `eval/frozen_manifest.yaml`، `tests/test_frozen_eval.py`
- **Files modified:** `ROADMAP.md`
- **Tests executed:** `python -m pytest`؛ `NAWA_ROLE=eval python -m nawa.evaluation.frozen verify` على نسخة نُزّلت من HF
- **Test results:** 73 passed / 0 failed؛ النسخة المنزلة من `frozen-v1` تطابق `FROZEN.sha256`
- **Metrics:** frozen: 243 عنصرًا؛ التقاطع مع dev (243) وcalib (128) صفر
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** `vuuuv/nawa-eval` (dataset، private)، الفرع `dev`، الـ tag `frozen-v1`، الـ commit `5eb6594823f88b2bd998a1387adc2f5505cf53cd`؛ لا شيء على `main`
- **Dataset version:** eval frozen v1
- **Known limitations:** البذرة غير محفوظة عمدًا، فالمرجع هو الملف المثبت بالـ hash. بنك factual الخاص كتبه الوكيل ويحتاج مراجعة بشرية. الوكيل نفسه أدى دور Eval في البناء (RISK-08).
- **Roadmap section updated:** §2.2، §2.3، §12
- **Next unblocked task:** P1-07 (المشغّل والتقرير)، ثم P1-04
- **Duplicate-work check:** لم يكن في `nawa-eval` سوى `.gitattributes`، ولم يكن يوجد `FROZEN.sha256`.

### P1-07 — مشغّل التقييم والتقرير (2026-09-30)

- **Task ID:** P1-07
- **Owner:** bootstrap-agent
- **Status:** DONE
- **Scope:** مشغّل تقييم بثلاث واجهات (oracle، always_abstain، hf)، وتقرير بفواصل ثقة Wilson 95% وسجل نسب كامل، وملف أهداف آلي، وأمر إعادة إنتاج واحد.
- **Files created:** `eval/run_eval.py`، `eval/report.py`، `eval/targets.yaml`، `src/nawa/evaluation/runner.py`، `src/nawa/evaluation/report.py`، `tests/test_eval_runner.py`
- **Files modified:** `Makefile` (`eval`، `report`، `repro`)، `ROADMAP.md`
- **Tests executed:** `python -m pytest`، `make repro`، تجربة دخان على Qwen2.5-0.5B (`--limit 2`، غير محفوظة)
- **Test results:** 83 passed / 0 failed؛ oracle يحقق 100% على 243 عنصرًا؛ always_abstain يحقق abstention_recall 100% وanswerable_accuracy 0%، فيسقط في T2
- **Metrics:** لا أرقام baseline بعد (P1-04)
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** dev (243)
- **Known limitations:** التقرير يحفظ المقاييس المجمعة فقط، والتنبؤات تبقى في `eval/runs/` المتجاهل. ملاحظة للمهمة P1-06: T1 وحده يمكن التحايل عليه بالامتناع الدائم (0% هلوسة)، فيجب قراءته مع الدقة ومع T2. أتمتة `make gate` لم تُنفذ بعد وتبقى رافضة.
- **Roadmap section updated:** §2.2، §2.3، §12
- **Next unblocked task:** P1-04
- **Duplicate-work check:** لم يكن يوجد مشغّل أو تقرير سابق، وكانت أهداف `make eval/repro` تُرجع not_implemented.

### R-02 — مواءمة المشروع مع هدف النظام الأصلي، وإلغاء P1-04 (2026-09-30)

- **Task ID:** R-02 (DONE)؛ P1-04 وP1-05 (SUPERSEDED)
- **Owner:** agent-R-02
- **Status:** DONE
- **Scope:** تنفيذ توجيهي المالك (16:27 و16:35 +03): هدف NAWA ابتكار وبناء نظام أصلي لا مقارنة النماذج؛ لا مهمة إلزامية لأي نموذج مفتوح الأوزان؛ لا baseline خارجي شرطًا لأي بوابة؛ المرجع داخلي؛ النماذج الخارجية أدوات تطوير لا مصدر حكم. لم يُغيَّر أي رقم في T1–T6، ولم تُحذف أي مهمة أو نتيجة.
- **Files created:** `docs/decisions/ADR-0003-original-system-and-model-use-policy.md`، `configs/model_registry.yaml`، `tests/test_model_registry.py`، `tests/test_original_system_policy.py`، `eval/reports/README.md`
- **Files modified:** `ROADMAP.md` (§0، §1.3، §2.1، §2.2، §2.3، §2.4، §3.1، §4 P1 وG1 وP5، §11، §12)، `AGENTS.md` (§1، §2.4، §3، §6، §8، §10، §13)، `PROJECT_CHARTER.md`، `SUCCESS_CRITERIA.md`، `eval/targets.yaml` (T3: OPTIONAL)، `eval/run_eval.py` (`--task-id` إلزامي مع `--save-report`)، `src/nawa/evaluation/runner.py` (خيار `--dtype`)، `tests/test_eval_runner.py` (حالة T3)
- **Files preserved without use:** `eval/reports/*.json` (3 تقارير P1-04 جزئية)، `experiments/log.jsonl` EXP-0001..EXP-0003؛ EXP-0004 (تشغيل 1.5B الموقوف) وEXP-0005 (سجل الإلغاء)
- **Tests executed:** `python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`
- **Test results:** 94 passed / 0 failed
- **Metrics:** لا شيء. نتائج P1-04 الملغاة لا تُستخدم في أي هدف أو بوابة، بتوجيه المالك.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **Known limitations:** R-03 (منظومة المراجعة متعددة النماذج) مخطط ولم يُنفَّذ. OD-10 مفتوح. P1-06 ينتظر P3-05.
- **Roadmap section updated:** §0، §1.3، §2.1، §2.2، §2.3، §2.4، §3.1، §4، §11، §12
- **Next unblocked task:** P3-04 (Transformer decoder مرجعي من الصفر)، ثم P3-05
- **Duplicate-work check:** لا يوجد فرع أو PR سابق لـ R-02؛ P1-05 مدمجة في P3-04/P3-05 لمنع العمل الموازي.

### P3-04 — نواة decoder مرجعية من الصفر (2026-09-30)

- **Task ID:** P3-04
- **Owner:** agent-P3-04
- **Status:** DONE
- **Scope:** نواة Transformer decoder مرجعية لـ NAWA مكتوبة من الصفر (المسار S): embeddings، normalization، attention، MLP، positional، block، lm_head، model. لا أوزان خارجية ولا تحميل لأي نموذج. كل خيار معماري حقل مُتحقَّق منه في `DecoderConfig` بـ `config_hash` ثابت، كي تغيّر تجارب P4 خيارًا واحدًا في كل مرة. هذه **مرجع داخلي** وليست الحجم ولا المعمارية النهائية؛ الإعدادات الافتراضية لا تدّعي أنها الأفضل.
- **المكونات:** `RMSNorm` و`LayerNorm` مكتوبتان صراحة؛ RoPE أو positional متعلَّم أو بدونه؛ attention سببي مكتوب صراحة (scores ← mask ← softmax ← مجموع موزون) مع دعم grouped-query heads؛ MLP من نوع SwiGLU أو GELU بعدد معاملات متقارب؛ block بترتيب pre-norm؛ lm_head مربوط بالـ embeddings اختياريًا؛ تهيئة N(0, 0.02) مع تصغير إسقاطات residual بمعامل 1/√(2·n_layers)؛ توليد greedy أو بالعيّنة بمولّد قابل لإعادة الإنتاج، دون KV cache (مؤجل إلى P4-05/P8-04).
- **Files created:** `src/nawa/model/__init__.py`، `src/nawa/model/config.py`، `src/nawa/model/layers.py`، `src/nawa/model/decoder.py`، `configs/base_model.yaml`، `tests/test_reference_decoder.py`
- **Files modified:** `pyproject.toml` (extra اختياري `model` = `torch>=2.2`)، `.github/workflows/ci.yml` (تثبيت torch CPU و`NAWA_REQUIRE_TORCH=1` كي يفشل CI ولا يتخطى الاختبارات إذا غاب torch)، `ARCHITECTURE.md` (سطر الحالة)، `experiments/log.jsonl` (EXP-0006)، `ROADMAP.md`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`
- **Test results:** 143 passed / 0 failed (94 سابقة + 49 جديدة). تشمل: السببية في 12 تركيبة (norm × mlp × positional)؛ مطابقة attention للمرجع المستقل `F.scaled_dot_product_attention`؛ تكافؤ GQA مع MHA بأوزان k/v مكررة؛ مطابقة RMSNorm وLayerNorm للصيغة؛ اعتماد درجات RoPE على الإزاحة النسبية وحفظها للطول؛ مطابقة عدد المعاملات للصيغة المغلقة `expected_num_parameters` في 24 تركيبة؛ gradcheck بدقة float64؛ وصول تدرج غير صفري لكل معامل؛ استبعاد `ignore_index` من الخسارة؛ الحتمية بالبذرة؛ رفض الإعدادات غير الصالحة.
- **فشل مسجَّل أثناء التطوير:** اختبار RoPE فشل أولًا بحد تسامح 1e-9. السبب أن جداول cos/sin مخزنة بدقة float32، والفرق النسبي المقاس نحو 2e-8. ضُبط الحد على 1e-6 ووُثق السبب داخل الاختبار. لم يُغيَّر سلوك الكود.
- **Metrics (EXP-0006، `configs/base_model.yaml`, seed 42, CPU بنواتين، torch 2.14.0+cpu، Python 3.14.3):** config_hash `918f4cf4877c0cca`؛ المعاملات 3,229,952 (منها 3,164,416 خارج الـ embeddings) وتطابق الصيغة المغلقة؛ خسارة التهيئة 5.6431 مقابل ln(256)=5.5452؛ زمن forward بحجم 8×128 نحو 56.9 ms. هذه أرقام صحة وتشغيل، لا أرقام جودة.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء (لا أوزان مدربة)
- **Dataset version:** لا شيء
- **Known limitations:** `vocab_size=256` placeholder بمستوى البايت حتى يُختار الـ tokenizer (P3-03). لا KV cache ولا kernel مدمج. لا تدريب؛ إثبات التعلم (XOR وtiny LM) هو P3-05. PyTorch مكتبة tensors/autograd فقط ولا يُحمَّل منها أي نموذج. أجرى الوكيل القياس بنفسه، فالمراجعة المستقلة مطلوبة قبل إغلاق G3 (قاعدة استقلال الحكم).
- **Roadmap section updated:** §2.1 (G3)، §2.2، §2.3، §12
- **Next unblocked task:** P3-05 (XOR وtiny character LM على هذه النواة، CPU محلي). بعد وجود نموذج NAWA يُنتج أخطاء، تصبح P1-08 ممكنة من إخفاقاته هو.
- **Duplicate-work check:** لا يوجد `src/nawa/model/` سابق، ولا فرع أو PR لـ P3-04 (فُحصت الفروع البعيدة الثمانية وPRs #1–#8، وكلها مدموجة). P1-05 مدمجة في هذه المهمة بقرار ADR-0003، فلم تُنشأ نسخة موازية.

### P3-05 — XOR وtiny character LM لإثبات صحة التدريب (2026-09-30)

- **Task ID:** P3-05
- **Owner:** agent-P3-05
- **Status:** DONE
- **Scope:** إثبات أن نواة P3-04 تتعلم، على CPU محلي، ببيانات يولّدها NAWA بنفسه (لا بيانات خارجية، ولا سؤال ترخيص). حارس الميزانية يُستدعى قبل التشغيل (`cpu_local`). حلقة تدريب مصغّرة خاصة بهذه المهمة فقط؛ المدرّب الكامل هو P3-06.
- **التصميم:** (1) XOR كتسلسل `a b =` ← `a xor b`. (2) مصدر ماركوف من الرتبة الثانية على 28 حرفًا عربيًا والمسافة، جدوله مسحوب من Dirichlet ببذرة ثابتة. تُحسب معدلات الإنتروبيا H0 وH1 وH2 بدقة من التوزيع المستقر، فالحد الأمثل معروف مسبقًا. ولأن H0≈H1 بينما H2 أقل بنحو 0.94 نات، فإن النجاح لا يكون إلا باستخدام سياق الحرفين عبر attention. مرجع داخلي إضافي: مقدّر عدّ order-2 بتنعيم add-0.5 على البيانات نفسها.
- **المعايير المسجلة قبل التشغيل (`CRITERIA`):** دقة XOR = 100% لكل بذرة؛ خسارة التحقق ≤ H2 + 0.05؛ خسارة التحقق ≤ H1 − 0.10. لم تُغيَّر بعد الفشل.
- **Files created:** `src/nawa/training/__init__.py`، `src/nawa/training/sanity.py`، `tests/test_sanity_training.py`
- **Files modified:** `Makefile` (`make sanity`)، `experiments/log.jsonl` (EXP-0007..EXP-0009)، `ROADMAP.md`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`؛ `python -m nawa.training.sanity` (مرتان، ببذور مختلفة)
- **Test results:** 152 passed / 0 failed في 28.7 ثانية (143 سابقة + 9 جديدة). تثبت الاختبارات أن H2 المحسوبة بالصيغة تطابق مقدّرًا غير منحاز (2.3763 مقابل 2.3776)، وأن التوزيع المستقر نقطة ثابتة، وأن XOR يُتعلم بدقة 100%، وأن النموذج يتجاوز H1 في تشغيل قصير داخل CI.
- **Metrics:**

| التجربة | الحالة | البذرة | الرموز المرئية | H1 | H2 | مرجع العدّ | خسارة التحقق | الفجوة عن H2 | الهامش تحت H1 | XOR |
|---|---|---|---|---|---|---|---|---|---|---|
| EXP-0007 | FAILED | 42 | 3.07M | 3.3137 | 2.3776 | — | 2.6192 | 0.2416 | 0.6945 | — |
| EXP-0008 | PASSED | 42 | 12.29M | 3.3137 | 2.3776 | 2.3829 | 2.4133 | 0.0357 | 0.9004 | 100% (بذور 0–2) |
| EXP-0009 | PASSED | 7 | 12.29M | 3.3115 | 2.3933 | 2.3920 | 2.4124 | 0.0191 | 0.8991 | 100% (بذرتا 3–4) |

  النموذج: 102,528 معاملًا (d_model=64، طبقتان، 4 رؤوس)، config_hash `f7ed143b5dd98f46`، نحو 134 ثانية على CPU بنواتين (266 ثانية في EXP-0009 بسبب تشغيل متزامن). تكلفة صفرية، بلا GPU.
- **الفشل والتشخيص (EXP-0007):** تجاوز شرط H1 وسقط في شرط الفجوة. الفرضية الأولى كانت أن البيانات (200 ألف حرف) لا تكفي، و**نقضها القياس**: مقدّر العدّ على الحجم نفسه يبلغ 2.426. السبب الفعلي نقص التدريب (3.07 مليون رمز، وخسارة التدريب ما زالت 2.52). الإصلاح: رفع الرموز المرئية إلى 12.3 مليون (3000 خطوة × 64 × 64) والبيانات إلى 2 مليون حرف، دون تغيير المعايير أو النموذج. اختبار CI القصير فشل أيضًا في محاولته الأولى (400 خطوة، حد أشد مما تسمح به الخطوات)؛ ضُبط إلى 600 خطوة بحدود مأخوذة من منحنى EXP-0007 المقاس، وهو اختبار دخان وليس المعيار المسجل.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء (لا تُحفظ أوزان؛ النماذج تُعاد بأمر واحد)
- **Dataset version:** مصدر اصطناعي يُولَّد من الكود ببذرة (`MarkovSource.make(k=29, seed)`)
- **Reproduce:** `make sanity` (EXP-0008)؛ `python -m nawa.training.sanity --xor-seeds 3 4 --lm-seed 7` (EXP-0009)
- **Known limitations:** المصدر اصطناعي، والنجاح فيه يثبت صحة التدريب لا القدرة اللغوية. EXP-0007 استخدمت أداة أخذ عينات سابقة (التوزيع نفسه، وتسلسل مختلف)، فلا يُعاد توليد تسلسلها بالضبط (مسجل في السجل). الوكيل أجرى القياس بنفسه، فشرط G3 يحتاج مراجعة مستقلة.
- **تعارض مُبلَغ عنه (دون تغيير صامت):** تنتظر P1-06 المهمة P3-05 شكليًا. لكن نموذج P3-05 لا يعمل إلا على مفردات اصطناعية من 29 رمزًا، ولا يستطيع الإجابة عن مجموعات P1-02، فلا يصلح مرجعًا لتثبيت T1–T6. مرجع P1-06 الفعلي يحتاج نواة مدربة على نص حقيقي (بعد P2 وP3-03 وP5). يحتاج هذا تصحيح اعتمادية P1-06 في ADR مستقل، ولم يُعدَّل هنا.
- **Roadmap section updated:** §2.1 (G3)، §2.2، §2.3، §12
- **Next unblocked task:** P3-06 (`training/trainer.py`: optimizer، scheduler، checkpoint، resume، metrics، على CPU). تسبقها P3-01..P3-03 بالمعرف، لكنها تحتاج مدونة عربية مرخصة، وهذه مشروطة بـ P2 (§0 "إغلاق البوابات بالترتيب"). حالة P3-01..P3-03 لم تُغيَّر.
- **Duplicate-work check:** لا يوجد فرع أو PR لـ P3-05، ولا `src/nawa/training/` سابق. P1-05 المدمجة غطتها P3-04 وهذه المهمة.

### R-04 — فك حلقة اعتمادية P1-06 (2026-09-30)

- **Task ID:** R-04 (DONE)؛ P1-06 (أُعيد تحديد نطاقها، PLANNED)؛ P1-06a (جديدة، PLANNED)
- **Owner:** agent-R-04
- **Status:** DONE
- **Scope:** تنفيذ طلب المالك (17:37 +03) بإصلاح التعارض الذي أبلغت عنه P3-05. P1-06 كانت تنتظر P3-05، لكن نموذج P3-05 اصطناعي ولا يقرأ مجموعات التقييم. والمرجع النصي الحقيقي لا يوجد قبل P5، وP5 تنتظر إغلاق G1، فتنشأ حلقة. الحل: P1-06 تثبّت التعريفات وتبقى شرطًا لـ G1، وP1-06a تثبّت الأرقام وتصبح شرطًا جديدًا لـ G5. لم يُخفض أي هدف، ولم تُحذف أي مهمة، ولم يُغيَّر أي معرف.
- **Files created:** `docs/decisions/ADR-0004-p1-06-dependency.md`
- **Files modified:** `ROADMAP.md` (§1.3، §2.1 G1، §2.2، §2.3، §4 P1 وG5، §12)، `eval/targets.yaml` (تعليقات الحالة و`baseline_reference` وT6 فقط؛ لا عتبات)، `SUCCESS_CRITERIA.md` (مسار التثبيت)، `PROJECT_CHARTER.md` (سطر واحد)، `tests/test_roadmap_consistency.py`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`
- **Test results:** 153 passed / 0 failed (اختبار جديد: `test_p1_06_is_not_circular_and_anchoring_is_a_g5_condition`)
- **Metrics:** لا شيء. تغيير حوكمة.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Known limitations:** ADR-0003 لم يُعدَّل لأنه قرار مقبول؛ ADR-0004 يعدّل صف P1-06 فيه. `configs/model_registry.yaml` يذكر P1-06 في سجلات تاريخية SUPERSEDED، وتُركت كما هي.
- **Roadmap section updated:** §1.3، §2.1، §2.2، §2.3، §4، §12
- **Next unblocked task:** P1-06 (تثبيت تعريفات T1–T6؛ تعتمد على P1-07 المنجزة)، ثم P1-08 وP3-06.
- **Duplicate-work check:** لا يوجد ADR أو فرع أو PR سابق يعالج اعتمادية P1-06. P1-06a مهمة فرعية جديدة وليست نسخة من مهمة موجودة.

### P1-06 — تثبيت تعريفات T1–T6 (2026-09-30)

- **Task ID:** P1-06
- **Owner:** agent-P1-06
- **Status:** DONE (تعريفات فقط؛ الأرقام في P1-06a حسب ADR-0004 وتعليمات المالك)
- **Scope:** تثبيت أربعة عناصر لكل هدف: المقياس (مفتاح التقرير والمجموعات)، والعتبة (أرقام §1.3 كما هي)، ونوع المرجع، ومصدر التقييم. مصدر التقييم واحد لكل الأهداف: `run_eval.py`، مع dev للتطوير، وcalib للمعايرة، وfrozen للبوابة بدور Eval فقط. أنواع المرجع كلها داخلية أو مطلقة: `model_only_core` وT1 وT2 وT5 مرتبطة به، و`previous_release` وT5 من الإصدار الثاني، و`absolute` وT6، و`hardware_target` وT4. T3 وحده `optional_indicator` (ADR-0003). لم يُثبَّت أي رقم مرجعي، وبقيت حقول `anchor` و`baseline_reference` و`min_citation_accuracy` و`min_claim_accuracy` فارغة لـ P1-06a.
- **سد ثغرة T1:** وفق ADR-0004 D3، يحتاج نجاح T1 الآن أيضًا إلى نجاح شرط دقة الإجابة في T2. الدليل: `always_abstain` يحقق هلوسة 0% ودقة إجابة 0% على dev وcalib. يُحفظ الحكم الخام في `pass_unguarded` للشفافية.
- **Files created:** `src/nawa/evaluation/targets.py`، `tests/test_target_definitions.py`
- **Files modified:** `eval/targets.yaml` (schema v2)، `src/nawa/evaluation/report.py` (`compare`: شرط T1)، `SUCCESS_CRITERIA.md` (جدول T1–T6)، `ROADMAP.md`، `experiments/log.jsonl` (EXP-0010)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`
- **Test results:** 170 passed / 0 failed. الاختبارات الجديدة (17) ترفض: تخفيف أي عتبة من العتبات الخمس، وتثبيت رقم قبل P1-06a، ومرجعًا غير داخلي لهدف بوابة، والمعايرة على frozen، وحذف شرط T1، وجعل T3 إلزاميًا، وحذف أي هدف. وتقبل رفع العتبة، وتعيد قياس المرجعين التافهين وتطابقهما مع الأرقام المسجلة.
- **Metrics (EXP-0010، المراجع التافهة، commit `e41af10`):** dev (243 عنصرًا، split `b457cabe4c8dde5e`) وcalib (128 عنصرًا، split `80484b78d2f758d9`). `oracle`: كل مقاييس T تساوي 1.0، والهلوسة 0.0. `always_abstain`: الهلوسة 0.0، والامتناع 1.0، ودقة الإجابة 0.0، وT5 وT6 تساوي 0.0. هذه أرقام حدود للمقاييس، وليست مراجع لتثبيت الأهداف.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء (لم يُستخدم frozen)
- **Known limitations:** سرعة T4 ما زالت محجوبة بقرار OD-06. عتبتا T6 تنتظران P1-06a. `compare` لا يقيّم T4 وT6 بعد، لأن تقييمهما مطلق ويُضاف مع أرقامهما في P1-06a.
- **Roadmap section updated:** §2.1 G1، §2.2، §2.3، §12
- **Next unblocked task:** P1-08 (تسجيل أول حالات فشل في Atlas)، ثم P3-06 وفق ترتيب الخارطة.
- **Duplicate-work check:** لا يوجد فرع أو PR سابق لـ P1-06. `eval/targets.yaml` وسّعته هذه المهمة بدل إنشاء ملف أهداف جديد.

### P1-08 — أول حالات فشل في Atlas بإجابات متحققة (2026-09-30)

- **Task ID:** P1-08
- **Owner:** agent-P1-08
- **Status:** DONE
- **Scope:** بناء Atlas بمواصفات `AGENTS.md` §9، وتسجيل أول حالات الفشل مع إجاباتها المتحققة. المصدر الوحيد المتاح اليوم، دون نموذج خارجي ودون نواة نصية، هو المرجع الداخلي `always_abstain` (P1-07) على dev. لم يُشغَّل أي نموذج خارجي. `oracle` لا يفشل، فلا سجلات له.
- **اكتشاف وإصلاح أثناء المهمة:** مصححات المجموعات كانت تعطي الامتناع على سؤال قابل للإجابة فئة المجموعة الافتراضية. مثال ذلك FT-03 (خطأ حساب) لامتناع في reasoning_math، وFT-15 وFT-09 وFT-10 وFT-05 وFT-08 وFT-16 وFT-06 في مجموعات أخرى. وكان 16 فشلًا في code بلا فئة أصلًا. في تشغيل `always_abstain` بلغ الخطأ 133 تصنيفًا خاطئًا و16 فشلًا بلا فئة من 224. الإصلاح في `suites.attribute_abstention`، ويطبقه `runner`: الامتناع الخاطئ على سؤال قابل للإجابة يُصنف FT-13 (امتناع زائد)، والفئة الأصلية تُحفظ في `failure_suite_default` للتتبع. `correct` لم يتغير، ولم يتغير أي مقياس من مقاييس T1–T6، والاختبار `test_recorded_trivial_references_match_a_fresh_run` يثبت ذلك.
- **قواعد Atlas:** الفئة لا بد أن تكون من `docs/failure_taxonomy.md`، والفشل بلا فئة يُرفض ولا تُخمَّن له فئة. حالة `verified` تعني فحصًا حتميًا مستقلًا: الإجابة المرجعية تُصحَّح صحيحة، والمخرج السيئ يُصحَّح خاطئًا. **السجلات المشتقة من التقييم ممنوعة من التدريب** (`train_eligible: false`) لمنع التسرب، و`content_hash` يمكّن P2-05 من استبعادها. frozen وتشغيلات `--limit` مرفوضة. الملفات تُضاف ولا يُكتب فوقها. المراجع مسجَّل كـ `automated:deterministic-scorer (no human review yet)`، لأن أحدًا لم يراجعها يدويًا.
- **Files created:** `src/nawa/atlas.py`، `data_pipeline/atlas/README.md`، `data_pipeline/atlas/manifest.yaml`، `tests/test_atlas.py`. ملف السجلات `data_pipeline/atlas/incoming/2026-09-30-dev-always-abstain.jsonl` بيانات، فلا يدخل Git. يثبّته `manifest.yaml` بالبصمة `dd89a101…`، ويعيد CI إنتاجه ويتحقق منه.
- **Files modified:** `src/nawa/evaluation/suites/__init__.py`، `src/nawa/evaluation/runner.py`، `eval/suites/README.md`، `ROADMAP.md`، `experiments/log.jsonl` (EXP-0011)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `python -m nawa.atlas validate data_pipeline/atlas/incoming/*.jsonl`، `pre-commit run --all-files`، `detect-secrets-hook`
- **Test results:** 184 passed / 0 failed (14 اختبارًا جديدًا). السجلات: 224 صالحة.
- **Metrics (EXP-0011):** التشغيل `dev-always-abstain-20260930T150139Z` على commit `5f7913b` (نظيف). عدد السجلات 224، كلها verified وكلها FT-13، موزعة على المجموعات: faithfulness 30، وfactual 30، وreasoning_math 30، وarabic 30، وregression_general 25، وtool_use 24، وrobustness 24، وcode 16، وabstention 15. العدد 243 − 224 = 19 عنصرًا نجح فيها الامتناع، وهي 15 توأمًا بلا دليل و4 فخاخ حزم وهمية.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **فشلان في CI مسجَّلان:**
  1. المحاولة الأولى على PR #13 فشلت في `test_committed_atlas_is_valid_and_reproducible`. السبب أن `.gitignore` يستثني `*.jsonl`، فلم يُرفع ملف السجلات، بينما نجح الاختبار محليًا لأن الملف موجود على القرص.
  2. أضفت استثناءً في `.gitignore` لمسار Atlas، ففشلت المحاولة الثانية في `test_no_weight_or_dataset_files`، لأن سياسة المستودع أن البيانات لا تدخل Git. كان الاستثناء التفافًا على السياسة، ورفضه الاختبار عن حق. وفي هذه المحاولة نفسها دُفع commit مع أن فحص الأسرار أبلغ عن إنذارات كاذبة من البصمات: خطأ في تسلسل أوامري، لأنني فصلت الأوامر بـ `;` بدل `&&`.
  - **الإصلاح:** عكس الاستثناء، وإزالة الملف من Git بـ `git rm --cached` دون force push، وتثبيت الدفعة ببصمة حتمية في `manifest.yaml` يعيد CI إنتاجها. الملف بقي في تاريخ الفرع (commit `a50bf3f`)، ولن يصل إلى `main` لأن الدمج squash. هو عناصر dev عامة ولا يحتوي أسرارًا.
- **HF:** لم يُرفع شيء. رفع البيانات إلى `nawa-data` مكانه P2-08 بعد OD-03. كما أن موصل HF في هذه الجلسة لا يملك أداة رفع، ولا توجد بيانات اعتماد محفوظة. **OWNER ACTION REQUIRED عند P2-08.**
- **Known limitations:** كل السجلات من نمط فشل واحد (امتناع زائد) لمرجع تافه، فهي تثبت خط الإدخال والتحقق لا تنوع الأخطاء. أول إخفاقات متنوعة لنواة NAWA تأتي بعد وجود نواة نصية، أو عبر P2-01 (`mine.py`). علامات الامتناع (`ABSTAIN_MARKERS`) قد تصنّف إجابة خاطئة تحتوي عبارة مثل "غير موجود" على أنها امتناع. لا توجد مراجعة بشرية بعد.
- **Roadmap section updated:** §2.1 G1 (PENDING_REVIEW)، §2.2، §2.3، §12
- **Next unblocked task:** P3-06 (المدرّب الكامل: optimizer وscheduler وcheckpoint وresume على CPU). ومراجعة المالك لـ G1.
- **Duplicate-work check:** لا يوجد `data_pipeline/atlas/` ولا فرع أو PR سابق لـ P1-08. P2-01 (`mine.py`) وP2-02 (`verify.py`) مهمتان مختلفتان: هذه المهمة تبني السجل والتحقق الحتمي من تشغيلات التقييم فقط.

### P3-06 — المدرّب الكامل: optimizer وscheduler وcheckpoint وresume (2026-09-30)

- **Task ID:** P3-06
- **Owner:** agent-P3-06
- **Status:** DONE
- **Scope:** بناء `training/trainer.py` — مدرّب كامل لـ NAWA (المسار S): optimizer (AdamW/SGD)، scheduler (warmup + cosine/linear/constant)، checkpoint save/load مع كامل الحالة (model، optimizer، scheduler، RNG، step، config hash)، resume من checkpoint، gradient accumulation، mixed precision (fp32/fp16/bf16 مع fallback آمن على CPU)، metrics tracking (loss، LR، grad norm، tokens)، budget guard، DeviceWrapper (تجريد جهاز قابل للتوسعة في P3-07). لا أوزان خارجية ولا بيانات خارجية.
- **التصميم:** `TrainerConfig` (dataclass frozen) يخزّن كل المعاملات ويتحقق منها. `CheckpointState` يلتقط كل ما يلزم لإعادة الإنتاج. `make_scheduler` يبني LambdaLR بدالة warmup وcosine/linear/constant. `DeviceWrapper` يدير الجهاز وautocast. `Trainer` يدمج كل ذلك في حلقة تدريب واحدة. CLI entry point لاختبار الدخان.
- **Files created:** `src/nawa/training/trainer.py`، `tests/test_trainer.py`
- **Files modified:** `Makefile` (هدف `train` مُنفّذ)، `experiments/log.jsonl` (EXP-0012)، `ROADMAP.md`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`
- **Test results:** 219 passed / 0 failed (184 سابقة + 35 جديدة). تشمل: التحقق من 9 إعدادات غير صالئة، round-trip التكوين، warmup وcosine وlinear وconstant، ثبات constant بعد warmup، warmup صفر، انخفاض loss، تتبع metrics، حساب tokens مع accumulation، gradient accumulation، checkpoint save/load round-trip، resume من checkpoint، رفض تكوين مختلف، كمال حالة checkpoint، capture/restore RNG، DeviceWrapper CPU وfp32 nullcontext وfp16 fallback، budget guard، AdamW وSGD، summary، CLI smoke test.
- **Metrics (EXP-0012، `configs/base_model.yaml`، seed 42، CPU بنواتين، torch 2.14.1+cpu، Python 3.14.3):** config_hash `918f4cf4877c0cca`؛ smoke test نجح في 5 خطوات على بيانات اصطناعية. هذه أرقام صحة وتشغيل، لا أرقام جودة.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء (لا أوزان مدربة)
- **Dataset version:** لا شيء (بيانات اصطناعية من الكود)
- **Known limitations:** DeviceWrapper يدعم جهازًا واحدًا فقط (P3-07 يضيف multi-GPU/DDP). لا تحقق عددي رسمي لاستئناف checkpoint (P3-08). لا KV cache ولا kernel مدمج. لا تدريب على نص حقيقي (يحتاج P2 وP3-01..P3-03). الوكيل أجرى القياس بنفسه، فشرط G3 يحتاج مراجعة مستقلة.
- **Roadmap section updated:** §2.1 G3، §2.2، §2.3، §12
- **Next unblocked task:** P3-07 (دعم CPU/GPU/multi-GPU) أو P3-08 (تحقق عددي واختبارات checkpoint resume). كلاهما ضمن P3 ولا يحتاج G2.
- **Duplicate-work check:** لا يوجد `src/nawa/training/trainer.py` سابق، ولا فرع أو PR لـ P3-06. P3-05 كانت حلقة مصغّرة خاصة بالـ sanity check، وهذا المدرّب هو البنية التحتية الكاملة.

### P3-07 — دعم CPU/GPU/multi-GPU (2026-09-30)

- **Task ID:** P3-07
- **Owner:** agent-P3-07
- **Status:** DONE
- **Scope:** توسيع `DeviceWrapper` (من P3-06) لدعم CPU، GPU واحد (auto-detect)، وmulti-GPU عبر DDP. إضافة `DistributedConfig` للتحقق من mode/world_size/rank/backend. عدم ربط الكود بجهاز واحد: كل المسارات قابلة للتبديل.
- **التصميم:** `DistributedConfig` (dataclass frozen) يتحقق من صحة الإعداد. `DeviceWrapper` يوسّع ليدعم: auto-detect CUDA، fallback آمن إلى CPU مع تحذير، `wrap_model`/`unwrap_model` لـ DDP، `barrier` للتزامن، `should_save`/`should_log` لـ rank-0 فقط، `init_distributed`/`cleanup_distributed` ثابتتان. Trainer يدمج `DistributedConfig` ويستخدم `unwrap_model` في checkpoint.
- **Files modified:** `src/nawa/training/trainer.py` (DistributedConfig، DeviceWrapper موسّع، Trainer يقبل distributed)، `ROADMAP.md`
- **Files created:** `tests/test_device_support.py`، `experiments/log.jsonl` (EXP-0013)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`
- **Test results:** 247 passed / 0 failed / 1 skipped (184 + 35 + 28 جديدة؛ 1 تخطي: CUDA not available). تشمل: DistributedConfig defaults وddp valid وnon-zero rank و5 حالات غير صالحة وround-trip؛ DeviceWrapper CPU default وexplicit CPU وmove no-op وCUDA fallback وfp32 nullcontext وbf16 fallback وbarrier no-op وshould_save true/false وwrap_model no DDP without process group وunwrap strips DDP وunwrap passes through non-DDP؛ Trainer accepts distributed config وsummary includes distributed info وcheckpoint uses unwrapped model وtrain loop respects should_log؛ init_distributed noop وcleanup safe.
- **Metrics (EXP-0013):** لا يوجد GPU؛ التجربة على CPU. هذه أرقام صحة وتشغيل.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Known limitations:** لا اختبار DDP فعلي متعدد العمليات (يحتاج torchrun أو mp.spawn). DDP paths مختبرة عبر عدم تهيئة process group. CUDA path غير مختبر (لا GPU). الوكيل أجرى القياس بنفسه.
- **Roadmap section updated:** §2.1 G3، §2.2، §12
- **Next unblocked task:** P3-08 (تحقق عددي، seeds ثابتة، استكمال من checkpoint، اختبارات unit/integration/numerical)
- **Duplicate-work check:** لا يوجد فرع أو PR سابق لـ P3-07. DeviceWrapper من P3-06 كان single-device فقط؛ هذا التوسيع يضيف GPU وDDP.

### P3-08 — التحقق العددي واختبارات checkpoint resume (2026-09-30)

- **Task ID:** P3-08
- **Owner:** agent-P3-08
- **Status:** DONE
- **Scope:** اختبارات رسمية لشروط G3 العددية: نفس البذرة تعطي نفس النتائج، الاستئناف من checkpoint يعطي مسارًا متطابقًا، تراكم التدرجات عدديًا مكافئ للباتش الكبير، الحسابات مستقرة، وحدة checkpoint كاملة، واختبار تكاملي.
- **Files created:** `tests/test_numerical_verification.py`، `experiments/log.jsonl` (EXP-0014)
- **Files modified:** `ROADMAP.md`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`
- **Test results:** 266 passed / 0 failed / 1 skipped (247 + 19 جديدة؛ 1 تخطي: CUDA not available). تشمل: same seed identical weights، different seed different weights، same config same seed identical trajectory، different seed different trajectory، resume identical continuation، resume restores optimizer state، resume restores scheduler state، resume restores step count، resume restores RNG state، loss finite throughout، grad norm non-negative، LR positive، gradient accumulation numerical equivalence، checkpoint all required fields، checkpoint config hash matches model، checkpoint model config saved، full pipeline train→checkpoint→resume→eval، forward deterministic، backward deterministic.
- **فشل مسجَّل أثناء التطوير:** اختبار تراكم التدرجات فشل أولًا لأن `zero_grad` كان يُستدعى بين الميكرو-باتشات، ممسحًا التدرجات المتراكمة. الإصلاح: نقل `zero_grad` قبل الحلقة. لم يُغيَّر سلوك الكود؛ صُحِّح الاختبار.
- **Metrics (EXP-0014):** 30 خطوة تدريب على CPU بنواتين. هذه أرقام صحة وتشغيل.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Known limitations:** جميع الاختبارات على CPU (لا GPU). اختبار الاستئناف يستخدم batch_fn معتمدة على الخطوة (step-seeded) بدلًا من generator متقدم، لأن الـ Trainer لا يلتقط حالة batch_fn. الوكيل أجرى القياس بنفسه.
- **Roadmap section updated:** §2.1 G3، §2.2، §12
- **Next unblocked task:** لا توجد مهام P3 غير محجوبة متبقية (P3-01..P3-03 تحتاج مدونة عربية مرخصة مشروطة بـ P2/G2). R-03 (منظومة المراجعة متعددة النماذج) مخططة. المهام التالية غير المحجوبة هي في P2 (أطلس الإخفاقات ومصنع البيانات) لكنها تحتاج إغلاق G0 وG1 أولاً.
- **Duplicate-work check:** لا يوجد فرع أو PR سابق لـ P3-08. P3-06 وP3-07 بنتا البنية التحتية، وهذه المهمة تضيف التحقق العددي الرسمي.

### R-03 — منظومة المراجعة متعددة النماذج (2026-10-01)

- **Task ID:** R-03
- **Owner:** agent-R-03
- **Status:** DONE
- **Scope:** بناء منظومة المراجعة متعددة النماذج أثناء التطوير (ADR-0003 D1): سجل أدوار، تشغيل معزول، تسجيل الخلافات، ومنع القرار المعتمد على نموذج واحد.
- **التصميم:** `ReviewRole` (enum: reviewer، designer، tester، error_hunter، doc_writer)؛ `ModelEntry` و`ModelRegistry` (تسجيل نماذج خارجية مع أدوارها)؛ `ReviewRecord` (سجل مراجعة واحد)؛ `DisagreementRecord` (خلاف مع حل)؛ `ReviewLog` (سجل إلحاقي مع استمرارية)؛ `check_payload` (فحص أمان الحمولات: توكنات HF/GitHub/OpenAI، مراجع frozen، مسارات محظورة، تعيينات بيانات اعتماد)؛ `can_decide` (بوابة قرار: لا قرار بنموذج واحد).
- **Files created:** `docs/multi_model_review.md`، `src/nawa/review.py`، `tests/test_multi_model_review.py`، `experiments/log.jsonl` (EXP-0015)
- **Files modified:** `ROADMAP.md`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`
- **Test results:** 307 passed / 0 failed / 1 skipped (266 + 41 جديدة؛ 1 تخطي: CUDA not available). تشمل: ReviewRole من str وinvalid وvalues؛ ModelEntry creation وround_trip؛ ModelRegistry empty وregister/get وduplicate rejected وrequire unregistered وrequire role not authorized/authorized وround_trip؛ ReviewRecord creation وround_trip وmake_review؛ Disagreement creation وresolve وinvalid method وdeferred not resolved؛ ReviewLog add review/disagreement وresolve not found وmultiple models وreviews by model وsummary وpersistence؛ check_payload safe/HF/GitHub/OpenAI/frozen/env/credential/dict/list؛ can_decide no reviews/single no check/single with check/multiple/same model twice.
- **فشل مسجَّل أثناء التطوير:** ماسح الأسرار في `test_repository_structure.py` اكتشف توكنات وهمية في `test_multi_model_review.py`. الإصلاح: تقصير التوكنات الوهمية تحت حد الماسح وتخفيض حد Payload checker للأمان. لم يتغير سلوك الكود.
- **مراجعة PR #17 وإصلاحها (agent-R-05، 2026-10-01):** وجدت المراجعة ملاحظة جوهرية واحدة. كانت `can_decide` تسمح بقرار عند اتفاق نموذجين دون أي فحص حتمي، وهذا يخالف ADR-0003 D4 الذي ينص على أن المراجعة المستقلة يجب أن يتبعها فحص حتمي أو اختبار منفذ أو قياس. ولم تكن الدالة تمنع أن يكون النموذج المنتج هو المراجع الوحيد. أُصلح ذلك: صار الفحص الحتمي شرطًا دائمًا، وأُضيف المعامل `producer_model`، ومعامل `registry` اختياري يرفض المراجع غير المسجل لدوره. كما صار `ModelEntry` يرفض `authorized_by` غير `owner` (OD-10) والأدوار غير المعروفة. وصُحِّحت `docs/multi_model_review.md`: أُزيلت دالة `register_model` غير الموجودة، ووُضّح الفرق عن `configs/model_registry.yaml`. وأُضيفت 6 اختبارات واستُبدل اختبار واحد، فصار عدد الاختبارات 46، والنتيجة الكاملة 312 passed / 0 failed / 1 skipped.
- **Metrics (EXP-0015):** لا يوجد تدريب. هذه مهمة حوكمة.
- **Git commit:** PR #17، squash `f3794a7` على `main` (2026-10-01؛ دمجه agent-R-05 بعد المراجعة والإصلاح ونجاح CI)
- **HF repository/revision:** لا شيء
- **Known limitations:** السجل فارغ افتراضيًا؛ المزودون يُضافون عند حل OD-10. `check_payload` يستخدم أنماط regex ولا يلتقط كل أنواع الأسرار. لا تشغيل فعلي لنماذج خارجية — المنظومة توفر الإطار فقط.
- **Roadmap section updated:** §2.2، §12
- **Next unblocked task:** لا توجد مهام غير محجوبة متبقية. كل مهام P3 مكتملة (P3-01..P3-03 تحتاج P2/G2). P2 تحتاج إغلاق G0 وG1. G1 تنتظر مراجعة المالك. G0 تنتظر قرارات المالك (OD-01..OD-05، OD-09).
- **Duplicate-work check:** لا يوجد `src/nawa/review.py` سابق، ولا فرع أو PR لـ R-03. ADR-0003 D1 يصف السياسة؛ هذه المهمة تبني الكود الإطار.

### R-05 — نطاق مهام P2 القابلة للتنفيذ قبل إغلاق G0/G1 (2026-10-01)

- **Task ID:** R-05
- **Owner:** agent-R-05
- **Status:** DONE (دُمج بـ squash بتوجيه المالك، 2026-10-01 07:05 +03)
- **Scope:** إصلاح تعارض داخلي: تقرير P3-08 على `main` وتقرير R-03 في PR #17 المفتوح يقولان إن كل P2 تحتاج إغلاق G0 وG1، فلا توجد مهمة غير محجوبة. أما قاعدة §0 فتسمح بتنفيذ مهام المرحلة التي لا تعتمد على قرار معلّق، وتمنع فقط بدء مخرجات تعتمد على بوابة غير مغلقة، مثل البيانات والتدريب. الحل في ADR-0005: فصل صف P2 إلى ثماني مهام. مهام الكود P2-02..P2-05 غير محجوبة بحدود صارمة، ومهام إنتاج البيانات P2-01 وP2-06..P2-08 BLOCKED بقرارات محددة. لم يُغيَّر أي هدف أو معيار أو شرط بوابة أو معرف، ولم تُحذف أي مهمة أو نتيجة.
- **Files created:** `docs/decisions/ADR-0005-p2-code-scope.md`
- **Files modified:** `ROADMAP.md` (§2.1 G2، §2.2، §2.3، §4 P2، §12)، `tests/test_roadmap_consistency.py`
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`
- **Test results:** بعد دمج PR #17 وحل التعارض: 313 passed / 0 failed / 1 skipped (312 على `main` + 1 جديد). وقبل الدمج: 267 passed / 0 failed / 1 skipped (266 سابقة + 1 جديد: `test_p2_code_scope_split_keeps_data_production_blocked_and_g2_unchanged`؛ التخطي: CUDA not available). اختبار طفرة: جعل P2-06 PLANNED أو خفض شرط الـ 200 مثال في G2 يُفشل الاختبار. pre-commit وdetect-secrets نظيفان.
- **Metrics:** لا شيء. تغيير حوكمة.
- **Git commit:** PR #18، squash `d1c4b3f` على `main`؛ دُمج بعد PR #17، وحُلّ تعارض §2.3 و§12 يدويًا بالإبقاء على تقريري R-03 وR-05 وعلى الإصدارين 1.15.0 و1.16.0
- **HF repository/revision:** لا شيء
- **Known limitations:** كان ADR-0005 بحالة PROPOSED لأنه يعكس استنتاجًا سجله وكيلان سابقان، ثم صار ACCEPTED بتوجيه المالك بدمج PR #18. نص تقرير P3-08 بقي كما هو ولم يُعَد كتابة التاريخ. PR #17 (R-03) عدّل المواضع نفسها في §2.3 و§12؛ دُمج أولًا (`f3794a7`) ثم حُلّ التعارض هنا. رقم الإصدار 1.15.0 وEXP-0015 محجوزان لـ R-03، فاستخدمت هذه المهمة 1.16.0.
- **فحص الأسرار والصلاحيات (OWNER ACTION REQUIRED):** المتغيران `GITHUB_TOKEN` و`HF_TOKEN` غير موجودين كمتغيرات بيئة خام في جلسة هذا الوكيل. الوصول يتم عبر مدير أسرار المنصة، الذي يحقن المصادقة عبر proxy دون كشف القيمة. تحقق الوكيل من الوصول دون طباعة أي قيمة: GitHub يقرأ ويكتب في `sooovg/nawa`، وHF يقرأ مستودعات `vuuuv/nawa-*` الثمانية الخاصة. لكن توكن HF المسجل fine-grained على كامل حساب `vuuuv`، وليس على مستودعات NAWA وحدها. وهو يمنح كذلك `inference.endpoints.write` و`job.write` و`user.billing.read`. يوصى بأن يقصره المالك على مستودعات `vuuuv/nawa-*` بصلاحية `repo.content.read` و`repo.write` فقط (AGENTS.md §11).
- **Roadmap section updated:** §2.1، §2.2، §2.3، §4، §12
- **Next unblocked task:** P2-02 (`verify.py`). ومراجعة المالك لـ G1 (تبقى PENDING_REVIEW).
- **Duplicate-work check:** لا يوجد ADR أو فرع أو PR سابق يعالج نطاق P2. الفروع البعيدة الثلاثة عشر كلها لمهام مدمجة، باستثناء `agent/R-03-multi-model-review` (PR #17، مفتوح، CI ناجح)، ونطاقه مختلف ولم يُلمس. لا يوجد `data_pipeline/atlas/verify.py` ولا `mine.py`.

### P2-02 — التحقق المستقل من أمثلة البيانات `verify.py` (2026-10-01)

- **Task ID:** P2-02
- **Owner:** agent-P2-02
- **Status:** DONE
- **Scope:** تنفيذ قاعدة P2-02: لا يدخل أي مثال إلى التدريب قبل تحقق مستقل. المهمة كود فقط ضمن حدود ADR-0005 D2: لا بيانات خارجية، ولا بيانات تدريب، ولا قراءة لـ frozen (البصمات فقط)، ولا رفع إلى HF. لم يُستخدم أي نموذج خارجي.
- **التصميم:** النتيجة ثلاثية: `verified` (جرى الفحص وثبت الادعاء)، و`rejected` (جرى الفحص وثبت خطؤه)، و`unverified` (تعذّر الفحص أو لم يكن مستقلًا). لا تخمين في أي حالة. الطرق الأربع:
  1. **حساب:** مقيّم حسابي آمن بالكسور الدقيقة عبر `ast`، دون `eval`. يرفض الأسماء والاستدعاءات وأي بنية غير حسابية، ويقيّد الأس. يدعم الأرقام العربية و`×` و`÷`، والتسامح يُعلن صراحة.
  2. **تنفيذ:** يُشغَّل الكود مع اختبارات في sandbox الموجود (P1-02)، والشبكة معطلة فيه. يُرفض الاختبار إذا كتبه المنتج نفسه أو خلا من أي `assert`.
  3. **مصدر مرخص:** يجب أن تكون الإجابة كلمة كاملة داخل اقتباس حرفي من مصدر مثبت ببصمة sha256، وأن يكون ترخيصه في `approved_licenses`. هذه القائمة **فارغة حتى OD-03**، فلا يُعتمد أي نص غير مرخص.
  4. **مراجعة خبير:** يجب أن يكون المراجع بشريًا مسمى (`human:<id>`) وغير المنتج. النموذج أو الأداة الآلية لا يكون خبيرًا معتمدًا (ADR-0003 D4).
- **أهلية التدريب** (`train_eligibility`) قرار مستقل وأشد. تُرفض الحالات التالية بالترتيب: غير المتحقق منه، والمشتق من dev أو calib أو frozen، وما تطابق بصمته بصمة frozen، وكل شيء ما دامت G2 ليست DONE. وتُقرأ حالة G2 آليًا من §2.1. سجلات Atlas من P1-08 تبقى `verified` بطريقتها الحتمية، وممنوعة دائمًا من التدريب.
- **Files created:** `src/nawa/data_verify.py`، `data_pipeline/atlas/verify.py`، `configs/verification.yaml`، `tests/test_data_verify.py`
- **Files modified:** `data_pipeline/atlas/README.md`، `experiments/log.jsonl` (EXP-0016)، `ROADMAP.md` (§2.1 G2، §2.2، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، `python -m nawa.data_verify bench --seed 2026` و`--seed 7 --n 40`
- **Test results:** 353 passed / 0 failed / 1 skipped (313 على `main` + 40 جديدة؛ التخطي: CUDA not available). pre-commit وdetect-secrets نظيفان.
- **Metrics (EXP-0016، `configs/verification.yaml` hash `0ec8a778fb26d727`):** معايير سُجلت قبل التشغيل في `CRITERIA`: صفر تحقق كاذب، ودقة حالة 1.0. البذرة 2026: 165 حالة، دقة 1.0، صفر تحقق كاذب. البذرة 7 (n=40): 330 حالة (120 verified، و100 rejected، و110 unverified كما هو متوقع)، دقة 1.0، صفر تحقق كاذب. في الحالتين لم تصبح أي حالة مؤهلة للتدريب، لأن G2 مفتوحة.
- **Git commit:** PR #19، squash `97f9d87` على `main`
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء. حالات المقياس اصطناعية يولدها الكود ببذرة، والترخيص `BENCH_LICENSE` يُمرَّر داخل المقياس فقط ولا يُكتب في الإعداد.
- **Known limitations:** المقياس اصطناعي وكتبه الوكيل نفسه، فهو يثبت تنفيذ القواعد لا جودة التحقق على ادعاءات حقيقية. مطابقة الاقتباس نصية بعد التطبيع، ولا تفهم إعادة الصياغة. التحقق من المصدر يثبت وجود الإجابة في الاقتباس، لا أن الاقتباس يدعم الادعاء كله؛ مطابقة الادعاء مكانها P6-04. الـ sandbox على مستوى العملية فقط (P6-02). لم يُضف هدف `make` جديد. الوكيل أجرى القياس بنفسه.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P2-05 (أدوات التنظيف وPII وdedup وdecontamination وprovenance وlicense وquality، كود فقط، ADR-0005 D3).
- **Duplicate-work check:** لا يوجد `verify.py` سابق ولا فرع أو PR لـ P2-02. `nawa.atlas` (P1-08) يتحقق من سجلات التقييم بإعادة التصحيح، و`verify_atlas_record` يعيد استخدام ذلك دون نسخه. `src/nawa/verification/` مخصص لمتحقق وقت التشغيل (P6-04) ولم يُلمس.

### P2-05 — أدوات التنظيف وPII وdedup وdecontamination وprovenance وlicense وquality (2026-10-01)

- **Task ID:** P2-05
- **Owner:** agent-P2-05
- **Status:** DONE
- **Scope:** كود فقط ضمن ADR-0005 D2: لا مدونة خارجية، ولا بيانات تدريب، ولا قراءة لـ frozen (بصماته فقط)، ولا رفع إلى HF، ولا نموذج خارجي.
- **الخطوات** (`src/nawa/data/pipeline.py`):
  1. **تنظيف:** NFC، وتحويل أشكال العرض العربية إلى حروفها، وحذف محارف التحكم وzero-width وBOM ومحارف الاتجاه المخفية (Trojan Source)، وحذف التطويل. يُبقى التشكيل وZWNJ، ويُعلَّم الـ mojibake.
  2. **PII:** استبدال بعلامة نوعية مثل `[EMAIL]`. الأنواع: بريد، وهاتف (مع الأرقام العربية)، وIBAN (mod-97)، وبطاقة (Luhn)، وهوية أو إقامة سعودية (checksum)، وIPv4، ورموز وصول. التقارير تحمل النوع والموضع فقط، لا القيمة.
  3. **لغة وجودة:** وسم لغة بحسب نسبة الحروف العربية واللاتينية، ودرجة جودة قاعدية قابلة للتفسير (رموز، أسطر مكررة، تكرار محرف، تنوع كلمات، mojibake).
  4. **ترخيص:** القائمة المعتمدة واحدة في `configs/verification.yaml` (فارغة حتى OD-03)، فالسياسة الملتزمة ترفض كل شيء بسبب الترخيص.
  5. **Decontamination:** تداخل 8-gram مع dev وcalib المبنيين من الكود، وبصمات عناصر frozen، وملف فهرس n-gram مجزّأ اختياري (P2-05a). `eval_texts(["frozen"])` يرفض صراحة.
  6. **Dedup:** تام بـ sha256 للنص المطبّع، وقريب بـ MinHash/LSH، ثم تأكيد كل زوج بـ Jaccard الحقيقي، فلا يؤثر LSH في الدقة. يُبقى الأول.
  7. **Provenance:** كل سجل محفوظ يحمل حقول G2 (source/license/language/domain/quality/date/hash/processing_version) ويُتحقق منه، و`train_eligible` دائمًا false (القرار لـ P2-02).
  لا يُحذف شيء بصمت: كل مدخل ينتهي في `kept` أو في `dropped` مع السبب، ولا نص في `dropped`.
- **Files created:** `src/nawa/data/{__init__,clean,pii,dedup,decontam,quality,provenance,pipeline}.py`، `configs/data_pipeline.yaml`، `tests/test_data_pipeline.py`
- **Files modified:** `data_pipeline/atlas/README.md`، `experiments/log.jsonl` (EXP-0017، EXP-0018)، `ROADMAP.md` (§2.1، §2.2، §2.3، §4 P2-05a، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، `python -m nawa.data.pipeline bench --seed 2026` و`--seed 7`
- **Test results:** 384 passed / 0 failed / 1 skipped (353 على `main` + 31 جديدة). pre-commit وdetect-secrets نظيفان.
- **Metrics:** المعايير سُجلت قبل التشغيل في `CRITERIA`: استرجاع PII = 1.0 لكل نوع، وصفر مستندات بإيجابية كاذبة، واسترجاع dedup ≥ 0.95 بدقة 1.0، واسترجاع decontamination = 1.0 بلا إيجابيات كاذبة، واسترجاع الجودة = 1.0 بلا إيجابيات كاذبة، وتطابق تام للترخيص، وصفر محارف مخفية متبقية.
  - **EXP-0017 — FAILED:** استرجاع الجودة 0.35، لأن العقوبة الثابتة لكل علامة أبقت النصوص الرديئة ذات العلامة الواحدة فوق 0.5 حتى في القيم القصوى. سُجل الفشل ولم تُغيَّر المعايير. الإصلاح: كل مكوّن يتناسب مع مقدار تجاوزه للعتبة، والدرجة حاصل ضرب المكونات.
  - **EXP-0018:** كل المعايير محققة على البذرة 2026 والبذرة 7 (لم تُستخدم أثناء الإصلاح)، 460 سجلًا لكل منهما. النتائج في كل بذرة: 140 PII محذوفة (20 لكل نوع)، و40 تكرارًا، و20 تلوثًا، و20 نصًا رديئًا، و20 بلا ترخيص. `configs/data_pipeline.yaml` hash `e9cdde2a615833d7`.
- **Git commit:** PR #20، squash `d16a414` على `main`
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء. المقياس اصطناعي يولده الكود ببذرة، وقيم PII فيه مولدة وقت التشغيل ولا تُحفظ.
- **Known limitations:**
  - المقياس اصطناعي وكتبه الوكيل نفسه، فهو يثبت تنفيذ القواعد لا الأداء على مدونة حقيقية.
  - لا كشف لأسماء الأشخاص أو العناوين أو المعرّفات الحرة.
  - كشف التسرب الجزئي إلى frozen غير ممكن قبل P2-05a؛ الآن يُكشف التطابق التام لبصمة العنصر، والتداخل مع القوالب المشتركة عبر dev وcalib.
  - وسم اللغة يعتمد على نوع الحروف فقط ولا يفرّق بين العربية والفارسية.
  - MinHash بلغة Python الخالصة مناسب للأحجام الصغيرة فقط.
  - الوكيل أجرى القياس بنفسه.
- **Roadmap section updated:** §2.1، §2.2 (P2-05 وP2-05a)، §2.3، §4، §12
- **Next unblocked task:** P2-03 (توائم الامتناع، كود فقط، ADR-0005). P2-05a تحتاج Eval role ولا يبدؤها وكيل التطوير.
- **Duplicate-work check:** لا يوجد فرع أو PR أو وحدة سابقة للتنظيف أو PII أو dedup. `nawa.review.check_payload` (R-03) يفحص حمولات المراجعة الخارجية، و`content_hash` في التقييم يزيل تكرار عناصر التقييم؛ كلاهما لم يُنسخ ولم يُعدَّل. التطبيع يعيد استخدام `nawa.evaluation.normalize`، والـ sandbox لم يُستخدم هنا.

### P2-03 — توائم الامتناع (2026-10-01)

- **Task ID:** P2-03
- **Owner:** agent-P2-03
- **Status:** DONE
- **Scope:** كود فقط ضمن ADR-0005 D2: سياقات يولدها الكود، ولا بيانات تدريب، ولا قراءة لـ frozen، ولا رفع إلى HF، ولا نموذج خارجي.
- **التصميم** (`src/nawa/data/twins.py`): التوأمان يشتركان في السؤال نفسه.
  - **التوأم القابل للإجابة:** سياقه يحتوي جملة الدليل، وهدفه `<الإجابة> [k]`، حيث k رقم جملة الدليل.
  - **التوأم غير القابل للإجابة:** سياقه هو السياق نفسه مع حذف جملة الدليل وحدها، وهدفه `غير موجود في السياق` مع بيان الناقص: الكيان وأي خاصية لم تُذكر.
  - **المشتت:** كيان آخر يملك الخاصية المسؤول عنها بقيمة مختلفة، ويبقى في السياقين.
  - `check_pair` يفرض 14 شرطًا، منها: السؤال واحد، والفرق جملة الدليل فقط، والاستشهاد يشير إليها، ولا تسرّب للقيمة في الامتناع، والامتناع بلا استشهاد ومع سبب، ولا `train_eligible`. وأمر `build` يرفض كتابة أي زوج معيب.
- **الفصل عن التقييم (RISK-01):** مجموعة التقييم (P1-02) تستخدم بلدات من `SYLLABLES`. أما التوائم فتستخدم:
  - كيانًا مختلفًا (سفن خيالية) وخصائص مختلفة.
  - قوالب جمل وأسئلة ومحث نظام مختلفة.
  - أسماء مبنية حصرًا من حروف ساكنة لا ترد في مقاطع التقييم، فلا يمكن أن يطابق اسم توأم اسمًا في التقييم.
- **Files created:** `src/nawa/data/twins.py`، `tests/test_twins.py`
- **Files modified:** `data_pipeline/atlas/README.md`، `experiments/log.jsonl` (EXP-0019)، `ROADMAP.md` (§2.1، §2.2، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، `python -m nawa.data.twins bench --seed 2026` و`--seed 7`، واختبار طفرة يدوي: تعطيل فحص التسرب أفشل 3 اختبارات.
- **Test results:** 408 passed / 0 failed / 1 skipped (384 على `main` + 24 جديدة). pre-commit وdetect-secrets نظيفان.
- **Metrics (EXP-0019، 200 زوج لكل بذرة، البذرتان 2026 و7):** كل المعايير محققة.
  - نسبة الأزواج السليمة التي تمر: 1.0.
  - نسبة كشف الأزواج المفسدة: 1.0، على 11 نوعًا من الإفساد.
  - مدقق الامتناع في P1-02 يحكم بصحة كل الأهداف: 1.0.
  - الضابط الإيجابي: فهرس P2-05 يكشف 20 من 20 عنصر امتناع من dev.
  - صفر تداخل 8-gram مع dev وcalib، وصفر تصادم أسماء، وصفر PII، وصفر أزواج مكررة.
  - ملاحظة: أُضيف معياران (اتفاق مدقق التقييم والضابط الإيجابي) بعد تشغيل استكشافي أول نجح. هذه الإضافة ترفع المعيار ولا تخفضه.
- **Git commit:** PR #21، squash `c6702a6` على `main`
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء، فلم يُلتزم أي ملف بيانات.
- **Known limitations:**
  - **فجوة لـ G2:** طرق P2-02 الأربع لا تغطي البيانات الاصطناعية الصحيحة بالبناء، فلن تصبح التوائم مؤهلة للتدريب حتى بعد G2 دون قرار. الخيارات: طريقة `construction` بقرار ADR، أو مراجعة بشرية لعينة.
  - قالب الأسئلة محدود (5 خصائص وقالب واحد لكل خاصية)، ولا يشمل الامتناع الجزئي ولا تعدد الأدلة. هذه الحالات تحتاج توسعة لاحقة.
  - الحروف الساكنة المتاحة للأسماء ثمانية فقط، فالأسماء متشابهة الصوت.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P2-04 (أزواج التفضيل: جواب مؤسس مقابل جواب مهلوس، كود فقط، ADR-0005).
- **Duplicate-work check:** مجموعة `abstention` في التقييم (P1-02) أداة قياس لا منشئ بيانات. التوائم لا تنسخ قوالبها ولا أسماءها، ويُعاد استخدام مدققها فقط للتحقق من الاتساق. لا يوجد فرع أو PR سابق لـ P2-03.

### P2-04 — أزواج التفضيل: جواب مؤسس مقابل جواب مهلوس (2026-10-01)

- **Task ID:** P2-04
- **Owner:** agent-P2-04
- **Status:** DONE
- **Scope:** النطاق وفق ADR-0005: schema ومنشئ ومدقق فقط. الأزواج الحقيقية تحتاج مخرجات نموذج (P2-01 أو P5)، فلم تُنتج. لا بيانات تدريب، ولا قراءة لـ frozen، ولا رفع إلى HF، ولا نموذج خارجي.
- **التصميم** (`src/nawa/data/preference.py`):
  - **الزوج:** `{prompt, chosen, rejected, rejected_failure}`، وتُقرأ رموز الفشل من `docs/failure_taxonomy.md` نفسها.
  - **`judge`:** يحكم حتميًا على أي رد من السؤال والمرجع، ويعيد إما "صحيح" وإما أول فشل ينطبق. يغطي FT-01 (استشهاد بجملة غير موجودة)، وFT-12 (استشهاد لا يدعم الجواب أو غيابه)، وFT-07 (قيمة المشتت)، وFT-02 (رقم خاطئ)، وFT-13 (امتناع زائد)، وFT-14 (تخمين بدل الامتناع).
  - **المنشئ:** يشتق 6 أو 7 أزواج من كل توأم من P2-03، وكل رد مرفوض فيه فشل معروف.
  - **`check_pair`:** يعيد الحكم على الطرفين ويشترط أن يكون المختار صحيحًا وأن يفشل المرفوض بالرمز المعلن نفسه. فالزوج المقلوب أو الموسوم خطأ يُرفض، وأمر `build` يرفض كتابة أي زوج معيب.
  - **`from_model_outputs`:** مدخل المخرجات الحقيقية لاحقًا. لا يعيد زوجًا إلا إذا كان أحد المخرجات صحيحًا وآخر فاشلًا، ويعيد `None` بدل التخمين.
- **Files created:** `src/nawa/data/preference.py`، `tests/test_preference.py`
- **Files modified:** `data_pipeline/atlas/README.md`، `experiments/log.jsonl` (EXP-0020، EXP-0021)، `ROADMAP.md` (§2.1، §2.2، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، `python -m nawa.data.preference bench` على البذور 2026 و7 و99، واختبار طفرة يدوي: تعطيل فحص FT-01 أفشل 9 اختبارات.
- **Test results:** 431 passed / 0 failed / 1 skipped (408 على `main` + 23 جديدة). pre-commit وdetect-secrets نظيفان.
- **Metrics:** المعايير سُجلت قبل التشغيل في `CRITERIA`.
  - **EXP-0020 — FAILED:** على البذرة 7 كانت نسبة الأزواج الصحيحة 0.9992. السبب أن الرقم الخاطئ العشوائي (163) طابق طول سفينة المشتت، فصار الرد المرفوض خلط كيانات (FT-07) لا رقمًا خاطئًا. المدقق كشف الوسم الخاطئ. الإصلاح في المنشئ: الرقم الخاطئ يُختار من قيم لا ترد في السياق أبدًا. المعايير لم تُغيَّر.
  - **EXP-0021:** كل المعايير محققة على البذور 2026 و7 و99 (البذرة 99 لم تُستخدم أثناء الإصلاح)، بـ 1287 و1280 و1283 زوجًا.
    - نسبة الأزواج الصحيحة 1.0، ونسبة كشف الأزواج المفسدة 1.0 على 6 أنواع من الإفساد.
    - مدقق التقييم يحكم بصحة كل الردود المختارة (1.0)، وبخطأ كل الردود المرفوضة التي يقيسها (1.0؛ FT-07/02/13/14، لأنه لا يفحص الاستشهاد).
    - دقة اختيار الزوج من مخرجات مخلوطة 1.0، وصفر تداخل مع التقييم، وصفر أزواج مؤهلة للتدريب.
- **Git commit:** PR لهذه المهمة (squash)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **Known limitations:**
  - الأزواج الاصطناعية ترث محدودية قوالب P2-03، ولا تمثل أخطاء نموذج حقيقي.
  - `judge` يقتصر على صيغة سؤال السياق في التوائم. أسئلة الحساب والكود تحتاج محكّمات أخرى عبر P2-02.
  - تبقى فجوة G2 المسجلة في P2-03: لا طريقة تحقق في P2-02 للبيانات الاصطناعية الصحيحة بالبناء.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** انتهت كل مهام الكود غير المحجوبة في P2 (P2-02 وP2-03 وP2-04 وP2-05). المرشح التالي P3-01 وP3-02: أدوات تدريب Tokenizer وقياسه، كود فقط. أما اختيار الـ Tokenizer (P3-03) فيحتاج مدونة مرخصة (OD-03). وP2-05a تحتاج Eval role.
- **Duplicate-work check:** لا يوجد فرع أو PR أو وحدة سابقة لأزواج التفضيل. يُعاد استخدام توائم P2-03 ومدقق الامتناع في P1-02 دون نسخهما.

## 2.4 قرارات المالك المطلوبة (OWNER DECISION REQUIRED)

| ID | القرار | يحجب | الحالة |
|---|---|---|---|
| OD-01 | المجال الأول (first domain) | P1-02a (مجموعة `domain`)، T3، اعتماد الميثاق (G0) | OPEN |
| OD-02 | ترخيص كود المشروع | P0-01، G0 | OPEN (مؤقتًا: جميع الحقوق محفوظة) |
| OD-03 | ترخيص الأوزان والبيانات المستقبلية | P0-01، P2-07 | OPEN |
| OD-04 | معنى "خاص بي" / امتلاك NAWA | P0-01، G0 | OPEN |
| OD-05 | سقف ساعات GPU والتكلفة المالية | P0-07، G0، أي عمل مدفوع أو على GPU | OPEN |
| OD-06 | عتاد الهدف لقياس سرعة T4 | تثبيت T4 في P1-06 | OPEN |
| OD-07 | ظهور مستودع GitHub (عام حاليًا) | لا شيء؛ وضع مؤقت مقبول بتعليمات المالك | ACCEPTED_TEMPORARY |
| OD-08 | مصير مستودع HF القديم `vuuuv/nawa` (عام) | لا شيء | OPEN |
| OD-09 | اعتماد الميثاق والمعمارية | G0 | OPEN |
| OD-10 | المزودون والنماذج الخارجية المصرح بها كأدوات تطوير، وهل يجوز استخدام مخرجاتها بيانات تدريب | استخدام مخرجات خارجية في التدريب أو التقطير فقط (P5-08) | OPEN |

---

# 3. بنية المستودعات

## 3.1 Git: nawa

```text
nawa/
├── AGENTS.md
├── ROADMAP.md
├── STATUS.md                       # اختياري؛ يزامن آليًا مع هذه الخانة
├── README.md
├── PROJECT_CHARTER.md
├── ARCHITECTURE.md
├── SUCCESS_CRITERIA.md
├── SECURITY.md
├── RISK_REGISTER.md
├── CONTRIBUTING.md
├── LICENSE
├── pyproject.toml
├── Makefile
├── .gitignore
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
├── .github/workflows/evaluation.yml
├── .github/CODEOWNERS
├── configs/
│   ├── base_model.yaml
│   ├── model_ternary.yaml
│   ├── model_hybrid.yaml
│   ├── tokenizer.yaml
│   ├── budget.yaml
│   ├── hf_repos.yaml
│   ├── model_registry.yaml         # تبرير كل نموذج مفتوح الأوزان (ADR-0003)
│   ├── data_version.yaml
│   ├── model_version.yaml
│   ├── epistemic.yaml
│   ├── runtime.yaml
│   └── train_*.yaml
├── src/nawa/
│   ├── core/
│   ├── tokenizer/
│   ├── model/
│   ├── training/
│   ├── evaluation/
│   ├── reasoning/
│   ├── routing/
│   ├── retrieval/
│   ├── verification/
│   ├── abstention/
│   ├── memory/
│   ├── tools/
│   ├── multimodal/
│   ├── learning/
│   ├── safety/
│   └── runtime/
├── data_pipeline/
│   ├── ingest/
│   ├── clean/
│   ├── deduplicate/
│   ├── provenance/
│   ├── contamination/
│   ├── atlas/
│   ├── synth/
│   └── build_release.py
├── training/
├── eval/
├── compress/
├── scripts/
├── tests/
├── docs/
│   ├── decisions/
│   ├── experiments/
│   ├── errors/
│   ├── data_cards/
│   ├── claims.md
│   ├── failure_taxonomy.md
│   └── model_card_template.md
├── experiments/log.jsonl
└── space/
```

## 3.2 Hugging Face

```text
<owner>/nawa-data                 # datasets المعتمدة
<owner>/nawa-eval                 # dev/calib/frozen
<owner>/nawa-core                 # Core weights/adapters
<owner>/nawa-practical-baseline   # مسار B فقط
<owner>/nawa-verifier              # متحقق مستقل
<owner>/nawa-gguf                  # نسخ مضغوطة
<owner>/nawa-adapters              # محولات المجالات
<owner>/nawa-demo                 # Space بعد بوابة الإصدار
```

اليوم الأول: أنشئها خاصة وفارغة، واربطها في `configs/hf_repos.yaml`. لا تُرفع أوزان أو بيانات قبل أن توجد بوابة تسمح بذلك.

---

# 4. مراحل التنفيذ والبوابات

## P0 — الميثاق، الملكية، والحدود

**المدة:** قبل أي تدريب.

### المهام

- **P0-01 [Git]** إنشاء `PROJECT_CHARTER.md`: معنى “خاص بي”، المساران S/B، حدود البيانات والأوزان، الترخيص، النطاق الأول، ما يجوز نشره.
- **P0-02 [Git]** اعتماد `ARCHITECTURE.md` وتعريف Core مقابل Runtime.
- **P0-03 [Git]** تثبيت `SUCCESS_CRITERIA.md` مع الأهداف الأولية T1–T6.
- **P0-04 [Git]** إنشاء `RISK_REGISTER.md` و`SECURITY.md`.
- **P0-05 [Git]** إنشاء بنية المستودع و`AGENTS.md` و`.gitignore`.
- **P0-06 [HF]** إنشاء المستودعات الخاصة، ثم تسجيل `repo_id` في `configs/hf_repos.yaml`.
- **P0-07 [Git]** تحديد `configs/budget.yaml`: ساعات GPU، الذاكرة، التكلفة، والحد عند 80%.
  - **P0-07a [Git]** إطار الميزانية وحارسها: `configs/budget.yaml` بسقوف فارغة حتى OD-05، و`src/nawa/budget.py` يمنع العمل على GPU والعمل المدفوع ما دام السقف فارغًا.
- **P0-08 [Git]** إنشاء `ROADMAP.md` وسجل الحالة وCODEOWNERS.

### G0 — لا عبور قبل

- الميثاق معتمد.
- النطاق الأول محدد.
- مسارا S وB مفصولان.
- صلاحيات محدودة.
- مستودعات HF خاصة.
- CI مبدئي يعمل.

---

## P1 — القياس أولًا والمرجع الداخلي

> **ترتيب التنفيذ الفعلي** (بسبب الاعتماديات، ودون تغيير المعرفات): P1-01 ← P1-02 ← P1-03 ← P1-07 ← P1-06 ← P1-08؛ وP1-06a بعد أول مرشح من P5 (ADR-0004). P1-04 وP1-05 أصبحتا SUPERSEDED (ADR-0003).

**القاعدة:** لا تدريب كبير قبل وجود مرجع داخلي واختبار مجمد.

### المهام

- **P1-01 [Git]** إنشاء `docs/failure_taxonomy.md`، ويشمل: مصدر مختلق، رقم خاطئ، حساب، API وهمية، افتراض خاطئ، معلومة قديمة، خلط كيانات، مجاراة الخطأ، فقدان سياق، prompt injection، وثقة زائدة.
- **P1-02 [Git]** بناء حزم `eval/suites/`: faithfulness، abstention، factual، reasoning_math، code، tool_use، domain، robustness، arabic، regression_general (الأسماء كما في `AGENTS.md` §10).
  - **P1-02a [Git]** مجموعة `domain` للمجال الأول. محجوبة حتى OD-01.
- **P1-03 [Git→HF]** فصل `dev/calib/frozen`، حساب `eval/FROZEN.sha256`، ورفع frozen إلى `nawa-eval` خاص. Eval role فقط يلمسه.
- **P1-04 [Git]** ~~تشغيل عدة نماذج مفتوحة بأحجام مختلفة في مسار B~~ — **SUPERSEDED (ADR-0003)**: ليست مهمة إلزامية. أي تشغيل لنموذج مفتوح لاحقًا يحتاج حاجة تقنية موثقة ومدخلًا في `configs/model_registry.yaml`.
- **P1-05 [Git]** ~~بناء baseline لنموذج Decoder صغير يعمل محليًا~~ — **SUPERSEDED**: دُمجت في P3-04/P3-05، فنواة NAWA المرجعية هي المرجع الداخلي.
- **P1-06 [Git]** تثبيت **تعريفات** T1–T6 في `eval/targets.yaml` و`SUCCESS_CRITERIA.md`: المقياس، والمجموعات، والقسم (dev/calib لا frozen)، والاتجاه، والعتبة، ونوع المرجع الداخلي لكل هدف؛ وتسجيل أرقام المراجع التافهة الموجودة (P1-07). يُعرَّف T1 مع دقة الإجابة في T2 كي لا يمر الامتناع الدائم. لا تُضبط العتبات باستخدام frozen (ADR-0004).
  - **P1-06a [Git]** تثبيت **أرقام** T1 وT2 وT5 وT6 على أول نواة NAWA مدربة على نص حقيقي (مرجع "model only"، P6-09)، على dev/calib وبواسطة Eval role، وكتابة `run_id` في `baseline_reference`. تنتظر أول مرشح من P5، وهي شرط لـ G5 (ADR-0004). يُرفع الهدف ولا يُخفض.
- **P1-07 [Git]** إنشاء `eval/run_eval.py`, `report.py`, `targets.yaml` وأمر إعادة إنتاج واحد.
- **P1-08 [Git]** تسجيل أول حالات فشل في Atlas مع إجابات متحققة.

### G1

- أرقام المرجع الداخلي محفوظة (مراجع P1-07 ونواة P3-05). لا يُشترط أي baseline خارجي (ADR-0003).
- frozen له hash ومكان خاص.
- لا تسرب بين train/eval.
- يوجد أمر يعيد التقرير.

---

## P2 — أطلس الإخفاقات ومصنع البيانات

**الهدف:** جعل كل فشل مصدرًا لتحسين واختبار، لا مجرد شكوى.

> **نطاق التنفيذ قبل إغلاق G0/G1 (ADR-0005):** مهام الكود P2-02 ← P2-05 ← P2-03 ← P2-04 غير محجوبة، بشرط ألا تستورد بيانات خارجية، وألا تنتج بيانات تدريب، وألا تقرأ frozen، وألا ترفع شيئًا إلى HF. أما P2-01 وP2-06 وP2-07 وP2-08 فمحجوبة بقرارات OD-01 وOD-03 وOD-10 أو بغياب نواة نصية. شروط G2 لم تتغير.

### المهام

- **P2-01 [Git]** `data_pipeline/atlas/mine.py`: تشغيل نماذج على أسئلة واسعة والتقاط الاختلافات والفشل.
- **P2-02 [Git]** `verify.py`: لا يدخل المثال التدريب قبل تحقق مستقل: حساب، تنفيذ، مصدر مرخص، أو مراجعة خبرة.
- **P2-03 [Git]** بناء توائم الامتناع: نسخة بدليل يجيب ويستشهد، ونسخة بلا دليل يمتنع ويشرح الناقص.
- **P2-04 [Git]** بناء أزواج التفضيل: جواب مؤسس مقابل جواب مهلوس.
- **P2-05 [Git]** تنظيف، PII، dedup، decontamination، provenance، license، quality score.
- **P2-05a [HF]** (Eval role فقط) فهرس n-gram مجزّأ لنص frozen في `nawa-eval` الخاص لكشف التسرب الجزئي، دون نقل نص frozen إلى Git.
- **P2-06 [Git]** طبقات البيانات: language، Arabic، reasoning، math، code، knowledge، planning، tool use، verification، multilingual، synthetic، adversarial، private.
- **P2-07 [Git]** `DATA_SOURCES.md`, `LICENSES.md`, data cards، وmanifest مع hashes.
- **P2-08 [HF]** رفع `nawa-data:v1` بعد اعتماد الحقوق، وتسجيل revision في `configs/data_version.yaml`.

### G2

- 200 مثال على الأقل مُراجع يدويًا في البداية.
- صفر تسرب معروف إلى frozen.
- كل record يحمل source/license/language/domain/quality/date/hash/processing_version.
- لا بيانات غير مرخصة.

---

## P3 — Tokenizer ونواة مرجعية قابلة لإعادة الإنتاج

### المهام

- **P3-01 [Git]** اختبار BPE وUnigram وbyte-aware وArabic-aware experimental.
- **P3-02 [Git]** قياس الضغط، طول السلسلة، العربية الصرفية، code، Unicode النادر، العربي-الإنجليزي، والنص المشوش.
- **P3-03 [Git]** اختيار Tokenizer بالقياس وتسجيل ADR، لا بالذوق.
- **P3-04 [Git]** بناء Transformer decoder مرجعي من الصفر: embeddings، normalization، attention، MLP، positional، block، lm_head، model.
- **P3-05 [Git]** بناء XOR وtiny character LM للتأكد من صحة التدريب.
- **P3-06 [Git]** `training/trainer.py`, optimizer، scheduler، checkpoint، distributed abstraction، precision، gradient، resume، metrics.
- **P3-07 [Git]** دعم CPU، GPU واحد، multi-GPU، مع عدم ربط الكود بجهاز واحد.
- **P3-08 [Git]** تحقق عددي، seeds ثابتة، استكمال من checkpoint، واختبارات unit/integration/numerical.

### G3

- XOR ينجح.
- tiny LM يتعلم.
- checkpoint يُستأنف بنتيجة متطابقة ضمن هامش موثق.
- baseline Transformer يعمل على العتاد المتاح.

---

## P4 — دراسات الكفاءة والابتكار، لا افتراضات غير مختبرة

كل تقنية أدناه **فرضية تجريبية** وليست حقيقة مضمونة. تُقبل فقط إذا تجاوزت baseline على benchmark محدد.

### المهام

- **P4-01 [Git]** scaling curves: Tiny/Small/Medium وربط parameters/tokens/compute/loss/quality/memory/latency.
- **P4-02 [Git]** مقارنة Dense مقابل Sparse MoE مقابل Hybrid على quality/active parameters/FLOP/memory/latency.
- **P4-03 [Git]** اختبار الأوزان الثلاثية `{−1,0,+1}` بأسلوب QAT/التكميم التدريجي. لا تفترض تفوقًا؛ fallback إلى 4-bit إذا فشل.
- **P4-04 [Git]** اختبار Attention + convolution/hybrid blocks. لا تعتمد 1:2 أو أي نسبة قبل ablation.
- **P4-05 [Git]** اختبار weight sharing، low-rank، sparsity، speculative decoding، KV cache، compilation.
- **P4-06 [Git]** لكل تجربة ملف config، commit، seed، hardware، metrics، failure، conclusion.
- **P4-07 [Git]** `docs/ablations.md` يوضح ما نجح وما فشل.
- **P4-08 [HF]** رفع checkpoints التجريبية إلى `nawa-core` فرع `dev` فقط إذا كانت قابلة لإعادة الإنتاج، مع manifest.

### قرار تقني

لا يصبح NAWA “ternary” أو “hybrid” أو “MoE” رسميًا إلا بعد أن تثبت بوابة مستقلة أن الاختيار يحسن trade-off دون تدهور غير مقبول. يمكن أن يكون الناتج هجينًا أو dense إذا أثبت القياس أنه أفضل.

### G4

- scaling curves موجودة.
- كل ادعاء معماري له ablation.
- لا تقنية مفروضة بسبب اسمها أو شهرتها.

---

## P5 — تدريب النواة

### مسار S — Core من الصفر

- **P5-01 [Git]** pretraining تدريجي: لغة عامة، معرفة عالية الجودة، reasoning، code/math، long context، corpus عربي/خاص مرخص.
- **P5-02 [Git]** كل مرحلة لها dataset revision وcheckpoint وeval مستقل.
- **P5-03 [Git]** تدرج الأحجام بدل القفز إلى نموذج ضخم.
- **P5-04 [Git]** تسجيل ساعات GPU والتكلفة ومعدل البيانات والـ loss والقدرة.

### مسار B — اختياري عند حاجة تقنية موثقة (ADR-0003)

> المهام P5-05..P5-08 **ليست شرطًا لـ G5**. تُنفذ فقط إذا ظهرت حاجة تقنية محددة ومسجلة في `configs/model_registry.yaml`. P5-06 وP5-07 يمكن تطبيقهما على نواة NAWA نفسها دون أي نموذج خارجي.

- **P5-05 [Git]** SFT/LoRA على نموذج مفتوح مسموح الترخيص.
- **P5-06 [Git]** DPO أو preference optimization على أزواج Atlas.
- **P5-07 [Git]** GRPO أو RL فقط بعد وجود verifier واختبارات قوية، مع مراقبة reward hacking والامتناع الدائم.
- **P5-08 [Git]** تقطير من معلم مسموح إلى نموذج أصغر، وتسجيل المعلم والترخيص والمخرجات.
- **P5-09 [HF]** دفع المرشحين إلى `nawa-core/dev` أو `nawa-practical-baseline/dev`، لا `main`.
- **P5-10 [Git]** `experiments/log.jsonl` و`docs/experiments/EXP-xxxx.md` لكل تجربة.

### G5

- تحسن مقاس على dev.
- عدم استخدام frozen أثناء التطوير.
- تقييم frozen مرة واحدة لكل candidate بواسطة Eval role.
- P1-06a منجزة: T1–T6 مثبتة رقميًا على أول نواة نصية قبل الحكم على أي candidate (ADR-0004).
- لا تراجع T5.
- lineage كامل.

---

## P6 — نظام الاستدلال والتحقق

**هذه هي نواة التميز العملية.**

### المهام

- **P6-01 [Git]** `src/nawa/retrieval`: embeddings، index، chunker، reranker، freshness، source quality.
- **P6-02 [Git]** `src/nawa/tools`: calculator، Python sandbox، file inspector، approved search/API، permissions، audit.
- **P6-03 [Git]** `src/nawa/reasoning`: planner، decomposer، candidate generator، self-consistency، state، budget.
- **P6-04 [Git]** `src/nawa/verification`: claim extraction، citation، fact checker، contradiction، uncertainty، confidence، consensus.
- **P6-05 [Git]** `src/nawa/abstention`: أجب واستشهد / ابحث / نفذ أداة / اطلب توضيح / امتنع.
- **P6-06 [Git]** `src/nawa/routing`: تصنيف المهمة، اختيار الخبير، التصعيد، fallback، trace.
- **P6-07 [Git]** pipeline:

```text
Question
→ classify
→ decide retrieve/tool/reason
→ generate candidates
→ verify claims
→ contradiction check
→ confidence/calibration
→ answer/revise/clarify/abstain
```

- **P6-08 [Git]** حالات التحقق:

```text
SUPPORTED
PARTIALLY_SUPPORTED
UNCERTAIN
CONTRADICTED
INSUFFICIENT_EVIDENCE
```

- **P6-09 [Git]** تقييم ablation: model فقط، +RAG، +tool، +verifier، +abstention، النظام الكامل.

### قاعدة مهمة

المتحقق ليس نسخة من المولد فقط. استخدم قواعد حتمية للحساب، تنفيذًا للكود، فحص مصادر، ومراجعة مستقلة حيث يلزم.

### G6

- تحقق واضح الادعاء مقابل الدليل.
- امتنع النظام عند نقص الدليل دون انهيار في التغطية.
- لا يمر ادعاء غير مدعوم بصمت في الوضع الدقيق.
- المخاطر والتغطية مقاسة بمنحنى risk–coverage.

---

## P7 — الخبراء، المحولات، والذاكرة

### المهام

- **P7-01 [Git]** adapters أو خبراء: العربية، البرمجة، الرياضيات، الوثائق/OCR، البحث، التخطيط، السلامة.
- **P7-02 [Git]** كل خبير له هدف وبيانات واختبارات وحدود وقرار استدعاء.
- **P7-03 [Git]** router يختار النواة أو adapter أو عدة خبراء.
- **P7-04 [Git]** isolation test: إضافة خبير لا تكسر السابق.
- **P7-05 [Git]** memory: working، episodic، semantic، procedural، personal/project، consolidation، forgetting، provenance.
- **P7-06 [Git]** لا تُحشر المعرفة المتغيرة في weights؛ المعرفة المتغيرة تبقى في retrieval/memory القابلة للتحديث والحذف.
- **P7-07 [HF]** رفع adapters إلى `nawa-adapters` مع config وبطاقة وإصدار.
- **P7-08 [Git]** اختبارات الذاكرة: تذكر صحيح، نسيان/حذف، عدم تسريب بين المستخدمين، ومصدر كل memory.

### G7

- كل adapter يحسن ميدانه.
- لا تدهور عام أكبر من T5.
- router موثق وقابل للرجوع.
- الذاكرة لا تسرب بيانات ولا تغير الحقائق بلا provenance.

---

## P8 — ضغط وكفاءة قصوى

### المهام

- **P8-01 [Git]** distillation من إجابات النظام المتحققة، مع اختبارات عدم فقدان التحقق.
- **P8-02 [Git]** quantization: FP16/INT8/4-bit/GGUF عند ملاءمتها؛ ternary فقط إن أثبتتها P4.
- **P8-03 [Git]** pruning/sparsity/weight sharing إن لم تضر.
- **P8-04 [Git]** speculative decoding، KV optimization، compile، batching.
- **P8-05 [Git]** `compress/bench_speed.py`: جدول الحجم/الذاكرة/السرعة/القدرة/الهلوسة.
- **P8-06 [Git]** قياس capability/parameter وcapability/GB وcapability/FLOP وcapability/watt.
- **P8-07 [HF]** رفع `nawa-gguf` أو artifacts المضغوطة مع أسماء واضحة وبطاقة مقارنة.
- **P8-08 [Git]** لا تقبل نسخة مضغوطة بفقد جودة يتجاوز العتبة المثبتة.

### G8

- نسخة صغيرة قابلة للتشغيل.
- benchmark reproducible.
- لا تدهور verification/abstention غير معلن.
- جدول trade-off منشور داخليًا.

---

## P9 — التعلم المستمر ومقاومة الانحدار

### المهام

- **P9-01 [Git]** استقبال بلاغات الأخطاء إلى Atlas.
- **P9-02 [Git]** التحقق ثم تحويل الفشل إلى test/data/preference.
- **P9-03 [Git]** replay لتجنب catastrophic forgetting.
- **P9-04 [Git]** drift monitoring للبيانات والأداء.
- **P9-05 [Git]** كل دورة snapshot لا `model_latest.pt` بلا lineage.
- **P9-06 [Git]** قبول/رفض إصدار بناء على frozen قديم وجديد.
- **P9-07 [HF]** إصدار v1.1 وما بعده فقط بعد بوابة.
- **P9-08 [Git]** rollback موثق ومختبر.

### G9

كل إصدار أحدث أصلب من السابق أو موثق بوضوح ما الذي تحسن وما الذي تراجع ولماذا قُبل.

---

## P10 — الوسائط المتعددة، الأمان، والإصدار

### المهام

- **P10-01 [Git]** إضافة modality واحدة كل مرة: وثائق/صور، ثم صوت، ثم جداول/فيديو إن لزم.
- **P10-02 [Git]** benchmark مستقل لكل modality.
- **P10-03 [Git]** red team: hallucination، prompt injection، مصادر مضللة، تجاوز صلاحيات، PII، أدوات خطرة، أسئلة عربية ولهجات، سياق طويل.
- **P10-04 [Git]** `docs/red_team_v1.md`؛ كل كسر يدخل Atlas.
- **P10-05 [Git]** `docs/claims.md` بكل ادعاءات الإصدار وأوامر إعادة الإنتاج.
- **P10-06 [Git]** Model Card template ومعلومات الاستخدام المقصود، القيود، البيانات، التدريب، النتائج، الترخيص.
- **P10-07 [Git→HF]** `space/` يعرض الإجابة والمصادر والثقة وقرار الامتناع، بعد اختبار أمني.
- **P10-08 [HF]** وسم Git `v1.0.0` يطابق HF `v1.0`، ثم public فقط بموافقة المالك.

### G10 — تعريف 100%

- G0–G9 خضراء.
- تقرير red-team.
- كل claim قابل لإعادة الإنتاج.
- artifacts والـ hashes متطابقة.
- rollback جاهز.
- Model Card صادق.
- لا يوجد ادعاء عام غير مدعوم.

---

# 5. قواعد Git وHF خلال كل مرحلة

| العمل | Git | HF |
|---|---|---|
| كود/اختبار/وثيقة/إعداد صغير | نعم | لا |
| تجربة ونتيجة صغيرة | نعم | لا |
| dataset كبيرة | manifest/hash فقط | نعم |
| frozen eval | hash فقط | مستودع خاص |
| checkpoint وسيط | لا | dev خاص |
| candidate | metadata وhash | dev أو release candidate |
| وزن معتمد | tag وmanifest | main بعد gate |
| Model Card | template ومراجعة | نسخة الإصدار |
| Space | الكود أولًا | النشر بعد gate |

كل إصدار يجب أن يربط:

```text
Git tag
Dataset revision
Model revision
Config hash
sha256
Eval report
```

---

# 6. جدول الموارد والزمن

هذا تقدير تخطيطي لا وعد زمني:

| المستوى | الاستخدام |
|---|---|
| CPU/جهاز تطوير | XOR، tokenizer، tiny LM، unit tests |
| GPU واحد | LoRA، SFT، verifier، تجارب صغيرة |
| عدة GPU | pretraining أكبر ومسوح scaling |
| تخزين HF خاص | artifacts وdatasets والإصدارات |

الترتيب الواقعي:

- P0: أيام قليلة.
- P1: أسبوع إلى أسبوعين.
- P2: أسبوعان إلى ثلاثة.
- P3–P4: حسب العتاد والنتائج.
- P5–P6: عدة أسابيع إلى أشهر.
- P7–P10: دورات مستمرة.

لا تُشترى حوسبة كبيرة قبل أن تثبت P1 وP2 أن البيانات والمقياس صالحان.

---

# 7. سجل التجارب والقرارات

## 7.1 سجل تجربة إلزامي

`experiments/log.jsonl`:

```text
{
  "experiment_id": "EXP-0001",
  "task_id": "P3-05",
  "track": "S",
  "git_commit": "...",
  "data_revision": "...",
  "data_sha256": "...",
  "config_hash": "...",
  "seed": 42,
  "hardware": "...",
  "software": "...",
  "metrics": {},
  "failure_cases": [],
  "artifact": null,
  "conclusion": "...",
  "next_action": "..."
}
```

## 7.2 ADR

أي تغيير في النطاق، المعمارية، tokenizer، metric، الترخيص، مسار S/B، أو سياسة النشر يحتاج:

```text
docs/decisions/ADR-<number>-<slug>.md
```

لا تُخفى القرارات داخل commit message فقط.

---

# 8. قائمة منع التكرار

قبل تنفيذ أي شيء شغّل أو افحص:

```text
هل Task ID موجود؟
هل له فرع أو PR؟
هل المخرج موجود؟
هل التجربة مسجلة؟
هل artifact مرفوع؟
هل يوجد commit أحدث؟
هل توجد مهمة متداخلة؟
هل هذه مجرد إعادة تقييم أم تغيير جديد؟
```

إذا كان العمل موجودًا:

- لا تعِد تشغيله بلا سبب.
- اربط المهمة بالمخرج الموجود.
- نفذ فقط gap محددًا.
- سجّل `SUPERSEDED` أو `DONE` بدل نسخة ثانية.

---

# 9. تعريف الادعاء الكبير

أي عبارة مثل “أفضل”، “أصغر”، “أقوى”، “أقل هلوسة” لا تُقبل إلا بالصورة التالية:

```text
Task:
Baseline:
Dataset + revision:
Metric definition:
Compute budget:
Model size:
Our score:
Baseline score:
Confidence/uncertainty:
Reproduce command:
Git tag:
HF revision:
Limitations:
```

الرقم `1000×` هدف بحثي محتمل في مهمة ضيقة، وليس وعدًا شاملًا. إذا ثبت تفوق استثنائي فليُعلن في benchmark المحدد فقط.

---

# 10. بعد الإصدار: الأطلس الحي

```text
بلاغ خطأ
→ تحقق مستقل
→ Atlas
→ اختبار regression
→ data/preference إن كان صالحًا
→ تدريب أو تعديل نظام
→ تقييم قديم + جديد
→ إصدار v1.x
→ تحديث ROADMAP
```

ممنوع تعديل frozen القديمة؛ تُضاف نسخة جديدة مع hash جديد، وتبقى المقارنة التاريخية ممكنة.

---

# 11. أول أمر تنفيذي

لا يبدأ أي وكيل بكتابة نموذج كبير. يبدأ بالترتيب:

1. إنشاء Git وهيكل المستودع.
2. وضع `AGENTS.md` و`ROADMAP.md` و`PROJECT_CHARTER.md`.
3. حماية `main` وتشغيل CI وحارس الملفات الكبيرة والأسرار.
4. إنشاء HF repos خاصة وربطها.
5. بناء eval والمرجع الداخلي.
6. بناء Atlas وخط البيانات.
7. بعدها فقط يبدأ التدريب أو اختبار الابتكارات.

**كل وكيل يعمل نقطة ما، يحدّث هذه الخارطة بما عمله قبل أن يقول إنه انتهى.**

---

# 12. سجل التغييرات

| الإصدار | التاريخ | التغيير | المهام/الأدلة |
|---|---|---|---|
| 1.0.0-unified | 2026-09-30 | دمج خارطة المشروع، دستور الوكلاء، مساري S/B، Atlas، gates، frozen eval، Git/HF، وعدم التكرار | الحزمة المرفقة + الخارطة السابقة |
| 1.0.1 | 2026-09-30 | تفصيل صف P0 إلى مهام فردية، تحديث G0، إضافة §2.3 تقارير الإنجاز. لم تُعدَّل الأهداف ولا المعرفات. | P0-05، P0-06، ADR-0001 |
| 1.0.2 | 2026-09-30 | تسجيل commit التأسيس `d34f3f1`، ونجاح CI، وحماية `main`، وإغلاق P0-08. | P0-08 |
| 1.1.0 | 2026-09-30 | اتساق الخارطة: مواءمة §2.1 مع بوابات §4 وإضافة G10؛ مواءمة نطاقات §2.2 مع قوائم §4 (P3 وP4 وP5 وP6)؛ إضافة §2.4 لسجل قرارات المالك؛ إضافة قواعد التشغيل المعتمدة في §0؛ إضافة `RISK_REGISTER.md` إلى §3.1؛ توحيد أسماء مجموعات التقييم في P1-02؛ ترتيب تنفيذ P1. لم تُحذف أي مهمة، ولم يُغيَّر أي هدف أو معيار. | ADR-0002، PR لمهمة R-01 |
| 1.1.1 | 2026-09-30 | P0-03 وP0-04 وP0-07a منجزة؛ P0-01 وP0-02 وP0-07 محجوبة بقرارات المالك؛ إضافة المهمة الفرعية P0-07a. | P0-02..P0-07a |
| 1.2.0 | 2026-09-30 | تفصيل صفوف P1 إلى مهام فردية؛ P1-01 منجزة. | P1-01 |
| 1.3.0 | 2026-09-30 | P1-02 منجزة لتسع مجموعات؛ إضافة المهمة الفرعية P1-02a (`domain`) وهي BLOCKED بقرار OD-01. | P1-02 |
| 1.4.0 | 2026-09-30 | P1-03 منجزة: frozen v1 خاص على HF (`frozen-v1`) ومثبت بالـ hash في Git. | P1-03 |
| 1.5.0 | 2026-09-30 | P1-07 منجزة: المشغّل والتقرير وملف الأهداف وأمر `make repro`. بقي `make gate` رافضًا: رسالته أصبحت تنسب الفحص الآلي للبوابات إلى P10-05، ولم تُحذف أي مهمة. | P1-07 |
| 1.6.0 | 2026-09-30 | توجيه المالك (ADR-0003): هدف NAWA نظام أصلي لا مقارنة نماذج؛ baseline تعني مرجعًا داخليًا؛ P1-04 وP1-05 SUPERSEDED (التقارير محفوظة دون اعتماد)؛ T3 اختياري وليس شرطًا لأي بوابة (الرقم باقٍ)؛ مهام P5 للمسار B اختيارية؛ إضافة R-02 وR-03 وOD-10 و`configs/model_registry.yaml`. لم يُخفض أي معيار ولم تُحذف أي مهمة أو نتيجة. | R-02، ADR-0003 |
| 1.7.0 | 2026-09-30 | P3-04 منجزة: نواة decoder مرجعية من الصفر (المسار S)؛ G3 أصبحت IN_PROGRESS؛ تفصيل صف P3 إلى P3-01..P3-03 وP3-04 وP3-05..P3-08 دون تغيير أي معرف. لم يُغيَّر أي هدف أو معيار. | P3-04، EXP-0006 |
| 1.8.0 | 2026-09-30 | P3-05 منجزة (EXP-0007 FAILED، وEXP-0008 وEXP-0009 PASSED بمعايير مسجلة مسبقًا)؛ تفصيل P3-05..P3-08 إلى P3-05 وP3-06..P3-08؛ الإبلاغ عن تعارض اعتمادية P1-06 دون تغييرها. لم يُغيَّر أي هدف أو معيار. | P3-05 |
| 1.9.0 | 2026-09-30 | R-04: فك حلقة اعتمادية P1-06. P1-06 أصبحت تثبيت تعريفات T1–T6 (تعتمد على P1-07، شرط G1)، وأُضيفت P1-06a لتثبيت الأرقام على أول نواة نصية (شرط جديد لـ G5). لم يُخفض أي هدف، ولم تُحذف أي مهمة، ولم يُغيَّر أي معرف. | R-04، ADR-0004 |
| 1.10.0 | 2026-09-30 | P1-06 منجزة: تعريفات T1–T6 (المقياس، والعتبة دون تغيير، ونوع المرجع، ومصدر التقييم) في `eval/targets.yaml` schema v2 مع مدقّق؛ نجاح T1 مشروط بـ T2؛ لا أرقام مرجعية قبل P1-06a. | P1-06 |
| 1.11.0 | 2026-09-30 | P1-08 منجزة: Atlas بـ 224 سجلًا متحققًا ممنوعًا من التدريب؛ إصلاح تصنيف الامتناع إلى FT-13 دون تغيير أي مقياس T؛ G1 أصبحت PENDING_REVIEW. | P1-08 |
| 1.12.0 | 2026-09-30 | P3-06 منجزة: مدرّب كامل (optimizer/scheduler/checkpoint/resume/gradient accumulation/mixed precision/metrics/budget guard)؛ تفصيل P3-06..P3-08 إلى P3-06 وP3-07..P3-08؛ `make train` مُنفّذ. لم يُغيَّر أي هدف أو معيار. | P3-06، EXP-0012 |
| 1.13.0 | 2026-09-30 | P3-07 منجزة: DistributedConfig وDeviceWrapper (GPU auto-detect، CUDA fallback، DDP wrap/unwrap، barrier، rank-0 save/log)؛ تفصيل P3-07..P3-08 إلى P3-07 وP3-08. لم يُغيَّر أي هدف أو معيار. | P3-07، EXP-0013 |
| 1.14.0 | 2026-09-30 | P3-08 منجزة: تحقق عددي (determinism، checkpoint resume identity، gradient accumulation equivalence، numerical stability، checkpoint integrity، integration)؛ 19 اختبارًا. لم يُغيَّر أي هدف أو معيار. | P3-08، EXP-0014 |
| 1.15.0 | 2026-10-01 | R-03 منجزة: منظومة المراجعة متعددة النماذج (ADR-0003 D1) — سجل أدوار، سجل نماذج، سجل مراجعات، تسجيل خلافات، فحص أمان الحمولات، بوابة قرار (لا قرار بنموذج واحد، والفحص الحتمي شرط دائم بعد إصلاح المراجعة)؛ 46 اختبارًا. لم يُغيَّر أي هدف أو معيار. | R-03، EXP-0015 |
| 1.16.0 | 2026-10-01 | R-05: فصل صف P2 إلى P2-01..P2-08. مهام الكود P2-02..P2-05 غير محجوبة وفق §0، ومهام إنتاج البيانات P2-01 وP2-06..P2-08 BLOCKED؛ تصحيح استنتاج "لا مهمة غير محجوبة". لم يُغيَّر أي هدف أو معيار أو شرط بوابة. الإصدار 1.15.0 محجوز لـ R-03 (PR #17). | R-05، ADR-0005 |
| 1.17.0 | 2026-10-01 | P2-02 منجزة: `verify.py` (حساب، تنفيذ، مصدر مرخص، خبير بشري) وبوابة أهلية التدريب؛ G2 صارت IN_PROGRESS؛ لا ترخيص معتمد قبل OD-03. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P2-02، EXP-0016 |
| 1.18.0 | 2026-10-01 | P2-05 منجزة: أدوات التنظيف وPII وdedup وdecontamination وprovenance وlicense وquality (EXP-0017 FAILED ثم EXP-0018). إضافة P2-05a (فهرس n-gram مجزّأ لـ frozen، Eval role فقط). لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P2-05، EXP-0017، EXP-0018 |
| 1.19.0 | 2026-10-01 | P2-03 منجزة: منشئ ومدقق توائم الامتناع، مفصول عن قوالب التقييم وأسمائه (EXP-0019). سُجلت فجوة G2: P2-02 لا يغطي البيانات الاصطناعية الصحيحة بالبناء. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P2-03، EXP-0019 |
| 1.20.0 | 2026-10-01 | P2-04 منجزة: schema ومنشئ ومدقق أزواج التفضيل، ومدخل للمخرجات الحقيقية (EXP-0020 FAILED ثم EXP-0021). اكتملت مهام الكود غير المحجوبة في P2. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P2-04، EXP-0020، EXP-0021 |

> يُضاف كل تغيير لاحق هنا في نفس PR الذي يغير الخارطة.
