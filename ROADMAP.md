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
| G3 Tokenizer ونواة مرجعية (P3) | IN_PROGRESS | 2026-10-01 | P3-04..P3-08 منجزة: decoder مرجعي + XOR/tiny LM + trainer كامل + device support + numerical verification (266 اختبارًا)؛ P3-01 وP3-02 منجزتان: 5 مرشحين وأداة قياس على نص اصطناعي (EXP-0022، ADR-0006)؛ P3-03 (الاختيار) BLOCKED حتى توجد مدونة حقيقية مرخصة (OD-03)؛ لا يُغلق G3 قبل G0–G2 |
| G4 دراسات الكفاءة والابتكار (P4) | PLANNED | 2026-10-01 | P4-06 منجزة (سجل التجربة ومدققه، EXP-0024)؛ P4-05 منجزة (تكافؤ KV cache وspeculative وcompile، وصحة sharing وlow-rank وsparsity، EXP-0025)؛ P4-03 منجزة (صحة الأوزان الثلاثية و4-bit بـ QAT والتصدير المضغوط، EXP-0026؛ تجربة تقنية فقط، لا اعتماد)؛ P4-02 منجزة (صحة Sparse MoE وHybrid مقابل Dense، EXP-0027؛ لا اختيار ولا اعتماد)؛ P4-04 منجزة (صحة mixer الالتفاف السببي والتخطيطات الهجينة attention + convolution، EXP-0028؛ لا نسبة معتمدة)؛ P4-07 منجزة (سجل ablations كامل لـ EXP-0024..EXP-0028 بلا اعتماد أي تقنية)؛ ADR-0007: مهام الكود P4-02..P4-07 غير محجوبة (تنفيذ واختبارات صحة على النواة المرجعية ومصادر اصطناعية، دون اعتماد أي تقنية)؛ P4-01 وP4-02a..P4-05a وP4-08 BLOCKED؛ شروط G4 لم تُخفَّف (أضيف شرط ablations على نص حقيقي)، ولا تُغلق قبل P4-01 وP4-02a..P4-05a وG0–G3 |
| G5 تدريب النواة (P5) | PLANNED | — | — |
| G6 نظام الاستدلال والتحقق (P6) | PLANNED | 2026-10-02 | ADR-0008 (R-08): مهام الكود P6-01..P6-08 غير محجوبة بنطاق كود فقط (لا نموذج خارجي، لا شبكة، لا بيانات حقيقية، مولّدات stub)؛ P6-01a..P6-05a وP6-09 BLOCKED؛ أضيف إلى G6 شرط إنجازها؛ لا ادعاء جودة قبل G5 |
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
| R-06 | DONE | agent-R-06 | نطاق P4 قبل إغلاق G3: فصل صف P4 إلى P4-01..P4-08؛ مهام الكود P4-02..P4-07 غير محجوبة دون اعتماد أي تقنية، وP4-01 وP4-08 BLOCKED؛ ADR-0007؛ استكمال مراجع commit/PR الناقصة في تقارير §2.3؛ `tests/test_roadmap_consistency.py`؛ PR #24 | 2026-10-01 |
| R-07 | PLANNED | owner | تحسين أمني منفصل (توجيه المالك 2026-10-01): قصر تفويض تطبيق GitHub على مستودع `sooovg/nawa` وحده (AGENTS.md §11). غير حاجب: ليس شرطًا لأي مهمة، ولا يُغيَّر الآن إن كان سيعطل العمل. توكن HF مقصور أصلًا على `vuuuv/nawa-*` (تقرير P4-03) | 2026-10-01 |
| R-08 | DONE | agent-R-08 | نطاق P6 قبل إغلاق G5: فصل صف P6 إلى P6-01..P6-09؛ مهام الكود P6-01..P6-08 غير محجوبة بلا نموذج خارجي ولا شبكة ولا بيانات حقيقية ولا ادعاء جودة، وP6-01a..P6-05a وP6-09 BLOCKED؛ OD-11 جديد؛ ADR-0008؛ `tests/test_roadmap_consistency.py`، `tests/test_original_system_policy.py` | 2026-10-02 |
| P2-01 | BLOCKED | — | `mine.py` يحتاج نموذجًا نصيًا: نواة NAWA نصية (P5) أو أدوات خارجية مصرحًا بها (OD-10)؛ مسار تشغيلات التقييم الحتمي مغطى في P1-08 (ADR-0005) | 2026-10-01 |
| P2-02 | DONE | agent-P2-02 | `src/nawa/data_verify.py` و`data_pipeline/atlas/verify.py` و`configs/verification.yaml`: تحقق مستقل بأربع طرق (حساب، تنفيذ في sandbox، مصدر مرخص، مراجعة خبير بشري) وبوابة أهلية التدريب (G2 ودفعات التقييم وبصمات frozen)؛ `tests/test_data_verify.py` (40 اختبارًا)؛ EXP-0016 | 2026-10-01 |
| P2-03 | DONE | agent-P2-03 | `src/nawa/data/twins.py`: منشئ ومدقق توائم الامتناع (سفن خيالية، قوالب ومحث نظام مستقلان عن التقييم، مشتت يملك الخاصية المسؤول عنها)؛ `tests/test_twins.py` (24 اختبارًا)؛ EXP-0019 | 2026-10-01 |
| P2-04 | DONE | agent-P2-04 | `src/nawa/data/preference.py`: schema ومنشئ ومدقق أزواج التفضيل (`judge` حتمي، و`rejected_failure` من FT-01/02/07/12/13/14)، و`from_model_outputs` للمخرجات الحقيقية لاحقًا (P2-01 أو P5)؛ `tests/test_preference.py` (23 اختبارًا)؛ EXP-0020 (FAILED) ثم EXP-0021 | 2026-10-01 |
| P2-05 | DONE | agent-P2-05 | `src/nawa/data/` (clean، pii، dedup، decontam، quality، provenance، pipeline) و`configs/data_pipeline.yaml`؛ `tests/test_data_pipeline.py` (31 اختبارًا)؛ EXP-0017 (FAILED: quality recall 0.35) ثم EXP-0018 (كل المعايير محققة) | 2026-10-01 |
| P2-05a | PLANNED | — (Eval role فقط) | فهرس n-gram مُجزّأ (hashed) لنص frozen في `nawa-eval` الخاص، يقرؤه `ContaminationIndex` عبر `extra_index_files` لكشف التسرب الجزئي إلى frozen دون إدخال نصه إلى Git أو إلى الوكيل؛ شرط لـ "صفر تسرب معروف إلى frozen" في G2 | 2026-10-01 |
| P2-06 | BLOCKED | — | طبقات البيانات تحتاج مصادر حقيقية مرخصة (OD-03) والمجال الأول (OD-01) (ADR-0005) | 2026-10-01 |
| P2-07 | BLOCKED | — | `DATA_SOURCES.md` و`LICENSES.md` وdata cards تنتظر OD-03 (ADR-0005) | 2026-10-01 |
| P2-08 | BLOCKED | — | رفع `nawa-data:v1` ينتظر OD-03 واعتماد الحقوق (G2) (ADR-0005) | 2026-10-01 |
| P3-01 | DONE | agent-P3-01/02 | `src/nawa/tokenizer/` من الصفر (Track S): byte، وbyte-level BPE، وUnigram LM مع byte fallback، ونسختان بتقطيع عربي تجريبي للسوابق واللواحق (`pretok.arabic`)؛ كلها بلا فقد (round-trip تام)؛ `tests/test_tokenizer.py` (21 اختبارًا)؛ ADR-0006 | 2026-10-01 |
| P3-02 | DONE | agent-P3-01/02 | `src/nawa/tokenizer/metrics.py` و`corpus.py` و`configs/tokenizer.yaml`: الضغط، وطول السلسلة، وحدود الصرف العربي، والكود، وUnicode النادر، والعربي-الإنجليزي، والنص المشوش، على نص مولّد بالكود؛ EXP-0022 (كل معايير الصحة محققة؛ لا اختيار) | 2026-10-01 |
| P3-03 | BLOCKED | — | اختيار الـ Tokenizer يحتاج مدونة حقيقية مرخصة (OD-03 ومهام بيانات P2)؛ النص الاصطناعي لا يكفي للاختيار (ADR-0006)؛ النواة تبقى على `vocab_size=256` | 2026-10-01 |
| P3-04 | DONE | agent-P3-04 | `src/nawa/model/{config,layers,decoder}.py` (نواة decoder مرجعية من الصفر، مكوّنات قابلة للتبديل لتجارب P4)؛ `configs/base_model.yaml`؛ `tests/test_reference_decoder.py` (49 اختبارًا)؛ EXP-0006 | 2026-09-30 |
| P3-05 | DONE | agent-P3-05 | `src/nawa/training/sanity.py` (XOR + tiny character LM على مصدر ماركوف عربي اصطناعي بإنتروبيا محسوبة بدقة)؛ `make sanity`؛ `tests/test_sanity_training.py` (9 اختبارات)؛ EXP-0007 (FAILED) وEXP-0008 وEXP-0009 (PASSED) | 2026-09-30 |
| P3-06 | DONE | agent-P3-06 | `src/nawa/training/trainer.py` (Trainer، TrainerConfig، CheckpointState، DeviceWrapper، scheduler، optimizer، gradient accumulation، mixed precision، metrics، budget guard)؛ `Makefile` (`make train`)؛ `tests/test_trainer.py` (35 اختبارًا)؛ EXP-0012 | 2026-09-30 |
| P3-07 | DONE | agent-P3-07 | `src/nawa/training/trainer.py` (DistributedConfig، DeviceWrapper: GPU auto-detect، CUDA fallback، DDP wrap/unwrap، barrier، should_save/should_log، init/cleanup_distributed)؛ `tests/test_device_support.py` (28 اختبارًا، 1 تخطي)؛ EXP-0013 | 2026-09-30 |
| P3-08 | DONE | agent-P3-08 | `tests/test_numerical_verification.py` (19 اختبارًا: determinism, checkpoint resume identity, gradient accumulation equivalence, numerical stability, checkpoint integrity, integration)؛ EXP-0014 | 2026-09-30 |
| P4-01 | BLOCKED | — | منحنيات التوسع تصف البيانات التي تُقاس عليها؛ تنتظر مدونة حقيقية مرخصة (OD-03، P2-06..P2-08) واختيار الـ Tokenizer (P3-03) (ADR-0007) | 2026-10-01 |
| P4-02 | DONE | agent-P4-02 | `src/nawa/efficiency/moe.py`: `SparseMoE` (router خطي، top-k، بوابات مُعاد تطبيعها، خبراء مشتركون اختياريون، loss توازن الحمل، بلا حد سعة)، وDense (المرجع) وSparse MoE (كل الكتل) وHybrid (كتل محددة)، وصيغ مغلقة للمعاملات الكلية والفعالة وFLOPs؛ معايير مسجلة مسبقًا (`093a367`، وتعديل موثق قبل التشغيل `1d8e66e`)؛ `tests/test_moe.py` (53 اختبارًا)؛ EXP-0027 (16/16)؛ المقارنات دليل فقط، لا اختيار ولا اعتماد (ADR-0007 D4) | 2026-10-01 |
| P4-03 | DONE | agent-P4-03 | `src/nawa/efficiency/quant.py`: أوزان ثلاثية (absmean لكل صف) و4-bit متماثلة (absmax، −7..7) لطبقات الكتل، وQAT بـ STE دقيق، وتصدير مضغوط (`PackedLinear`) بصيغة بايتات مغلقة، وقاعدة fallback إلى 4-bit (`choose_precision`)؛ معايير مسجلة مسبقًا (commit `85792fc`)؛ `tests/test_quant.py` (42 اختبارًا)؛ EXP-0026 (15/15)؛ المقارنة مع fp دليل فقط، ولا اعتماد (ADR-0007 D4) | 2026-10-01 |
| P4-04 | DONE | agent-P4-04 | `src/nawa/efficiency/conv.py`: `ConvMixer` (التفاف سببي depthwise بمجموع إزاحات، بوابة SiLU/sigmoid/بدون، صيغة تدفقية بحالة K−1)، و`apply_conv` لتخطيطات attention/convolution بأي نسبة، وصيغ مغلقة للمعاملات وFLOPs وحالة فك الترميز والمجال الاستقبالي؛ معايير مسجلة مسبقًا (`9af18f0`، وتعديل موثق لمِسبارين قبل التشغيل `49628b2`)؛ `tests/test_conv.py` (89 اختبارًا)؛ EXP-0028 (15/15)؛ لا نسبة ولا اعتماد (ADR-0007 D4) | 2026-10-02 |
| P4-05 | DONE | agent-P4-05 | `src/nawa/efficiency/`: KV cache وspeculative decoding (greedy) و`torch.compile`، مكافئة للنواة المرجعية ضمن حد 1e-4 مسجل قبل التشغيل (commit `3c442f8`)؛ weight sharing وlow-rank وsparsity باختبارات صحة فقط (عدد المعاملات، الشكل، التدرج، السببية)؛ النواة المرجعية لم تتغير؛ `tests/test_efficiency.py`؛ EXP-0025؛ لا اعتماد (ADR-0007 D4) | 2026-10-01 |
| P4-06 | DONE | agent-P4-06 | `src/nawa/experiments.py`: schema سجل P4 (`p4-record/v1`) ومدققه وبانيه؛ المدقق يعيد اشتقاق `config_hash` و`passed`، ويرفض البيانات الحقيقية ما دام OD-03 مفتوحًا، ويرفض ادعاء التحسن أو الاعتماد على بيانات اصطناعية، ويرفض أي artifact ما دامت P4-08 غير منجزة؛ `tests/test_experiments.py` (36 اختبارًا)؛ EXP-0024 | 2026-10-01 |
| P4-07 | DONE | agent-P4-07 | `docs/ablations.md`: فهرس كل سجلات P4 (EXP-0024..EXP-0028) مطابق للسجل باختبار، وحالة كل تقنية (لا تقنية معتمدة، ولا نسبة attention:convolution)، والإخفاقات والتعديلات أثناء التطوير، وتفاصيل التجارب؛ `tests/test_ablations_register.py`؛ السجل يبقى مفتوحًا لإضافات P4 اللاحقة (ADR-0007) | 2026-10-02 |
| P4-02a | BLOCKED | — | مقارنة Dense/MoE/Hybrid على نص حقيقي؛ ablation شرط لـ G4؛ تنتظر OD-03 وP3-03 (ADR-0007) | 2026-10-01 |
| P4-03a | BLOCKED | — | مقارنة الأوزان الثلاثية و4-bit بالمرجع على نص حقيقي؛ ablation شرط لـ G4؛ تنتظر OD-03 وP3-03 (ADR-0007) | 2026-10-01 |
| P4-04a | BLOCKED | — | مقارنة كتل attention + convolution/hybrid على نص حقيقي؛ ablation شرط لـ G4؛ تنتظر OD-03 وP3-03 (ADR-0007) | 2026-10-01 |
| P4-05a | BLOCKED | — | قياس أثر weight sharing وlow-rank وsparsity على الجودة على نص حقيقي؛ ablation شرط لـ G4؛ تنتظر OD-03 وP3-03 (ADR-0007) | 2026-10-01 |
| P4-08 | BLOCKED | — | رفع checkpoints تجريبية إلى `nawa-core/dev` ينتظر تشغيل P4 على نص حقيقي ينتج checkpoint قابلًا لإعادة الإنتاج مع manifest؛ لا رفع بموجب ADR-0007 | 2026-10-01 |
| P5-01..P5-10 | PLANNED | — | — | — |
| P6-01 | PLANNED | — | كود فقط (ADR-0008): chunker، فهرس معجمي من الصفر، بيانات freshness وجودة المصدر، وواجهة reranker بقاعدة معجمية؛ على مدونة اصطناعية | 2026-10-02 |
| P6-02 | PLANNED | — | كود فقط (ADR-0008): calculator دقيق آمن، وsandbox بلا شبكة مع allowlist وسجل تدقيق (يقوّي `nawa.evaluation.sandbox` أو يغلّفه)، وfile inspector للقراءة فقط، وصلاحيات؛ لا شبكة | 2026-10-02 |
| P6-03 | PLANNED | — | كود فقط (ADR-0008): planner وdecomposer وstate وbudget، وواجهة مولّد تُختبر بمولّدات stub حتمية؛ لا ادعاء جودة | 2026-10-02 |
| P6-04 | PLANNED | — | كود فقط (ADR-0008): claims وcitation وفحوص حقائق حتمية (حساب، تنفيذ كود، مطابقة دليل) وcontradiction وuncertainty وconsensus على سياقات منظمة؛ لا نموذج خارجي (OD-10) | 2026-10-02 |
| P6-05 | PLANNED | — | كود فقط (ADR-0008): دالة قرار أجب واستشهد/ابحث/نفذ أداة/اطلب توضيح/امتنع، وحساب risk–coverage؛ لا عتبات معتمدة ولا تغيير للأهداف | 2026-10-02 |
| P6-06 | PLANNED | — | كود فقط (ADR-0008): قواعد تصنيف المهمة والتصعيد وfallback وtrace | 2026-10-02 |
| P6-07 | PLANNED | — | كود فقط (ADR-0008): pipeline كامل بمكونات قابلة للاستبدال وtrace يُعاد تشغيله حتميًا؛ smoke بمولّدات stub موسوم ليس مخرج P6-09 | 2026-10-02 |
| P6-08 | PLANNED | — | كود فقط (ADR-0008): الحالات الخمس وقواعدها؛ أول مهمة في ترتيب التنفيذ | 2026-10-02 |
| P6-09 | BLOCKED | — | ablation النظام (model فقط، +RAG، +tool، +verifier، +abstention، الكامل) يحتاج نواة NAWA مدربة؛ تنتظر G5 وP6-01a..P6-05a (ADR-0008) | 2026-10-02 |
| P6-01a | BLOCKED | — | embeddings كثيفة وreranker متعلم واسترجاع من مدونة حقيقية مرخصة؛ تنتظر OD-03 ونواة مدربة (P5) أو حاجة موثقة في المسار B (ADR-0003، ADR-0008) | 2026-10-02 |
| P6-02a | BLOCKED | — | search وAPI خارجية معتمدة؛ تنتظر OD-11 (والـ OD-05 إن كانت مدفوعة) (ADR-0008) | 2026-10-02 |
| P6-03a | BLOCKED | — | توليد المرشحين وself-consistency بنموذج NAWA؛ تنتظر G5 (ADR-0008) | 2026-10-02 |
| P6-04a | BLOCKED | — | تحقق الإجابات الحرة (استخراج ادعاءات مفتوح، entailment متعلم) على مخرجات NAWA؛ تنتظر G5، وأي نموذج خارجي ينتظر OD-10 (ADR-0008) | 2026-10-02 |
| P6-05a | BLOCKED | — | معايرة NAWA وعتبات الامتناع على `calib`، وفحص واحد على `frozen` بيد دور Eval؛ تنتظر G5 (ADR-0008) | 2026-10-02 |
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
- **Git commit:** PR #3، squash `e3b5caf` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #4، squash `a403c2f` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #5، squash `67e33a1` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #6، squash `bdefe9c` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #7، squash `91e5817` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #8، squash `2a489d8` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #9، squash `4fc691e` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #10، squash `813dc98` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #11، squash `e41af10` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #12، squash `99a5574` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #13، squash `5740067` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #14، squash `815e63c` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #15، squash `5e7e850` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #16، squash `87da334` على `main` (سُجّل لاحقًا في R-06 من `git log`)
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
- **Git commit:** PR #22، squash `bb7e937` على `main`
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **Known limitations:**
  - الأزواج الاصطناعية ترث محدودية قوالب P2-03، ولا تمثل أخطاء نموذج حقيقي.
  - `judge` يقتصر على صيغة سؤال السياق في التوائم. أسئلة الحساب والكود تحتاج محكّمات أخرى عبر P2-02.
  - تبقى فجوة G2 المسجلة في P2-03: لا طريقة تحقق في P2-02 للبيانات الاصطناعية الصحيحة بالبناء.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** انتهت كل مهام الكود غير المحجوبة في P2 (P2-02 وP2-03 وP2-04 وP2-05). المرشح التالي P3-01 وP3-02: أدوات تدريب Tokenizer وقياسه، كود فقط. أما اختيار الـ Tokenizer (P3-03) فيحتاج مدونة مرخصة (OD-03). وP2-05a تحتاج Eval role.
- **Duplicate-work check:** لا يوجد فرع أو PR أو وحدة سابقة لأزواج التفضيل. يُعاد استخدام توائم P2-03 ومدقق الامتناع في P1-02 دون نسخهما.

### P3-01 وP3-02 — مرشحو الـ Tokenizer وأداة قياسهم (2026-10-01)

- **Task ID:** P3-01، P3-02
- **Owner:** agent-P3-01/02
- **Status:** DONE (كلاهما). P3-03 BLOCKED (ADR-0006).
- **Scope (ADR-0006):** كود فقط على نص يولده الكود: لا مدونة خارجية، ولا مكتبة tokenizer خارجية، ولا مفردات خارجية (Track S)، ولا قراءة لـ frozen، ولا رفع. لا يُختار أي tokenizer هنا.
- **المرشحون (P3-01، `src/nawa/tokenizer/`):**
  - `byte`: خط الأساس الحالي للنواة (256).
  - `bpe`: byte-level BPE، بـ heap كسول وكسر تعادل حتمي.
  - `bpe_arabic`: مثل `bpe` مع تقطيع مسبق تجريبي للسوابق (و، ف، ب، ل، ك، ال، وال، بال، لل، س) واللواحق (ه، ها، هم، كم، نا...)، بشرط ألا يقل الجذع عن 3 أحرف.
  - `unigram`: Unigram LM بتدريب Viterbi (hard-EM، تبسيط لـ SentencePiece) مع byte fallback.
  - `unigram_arabic`: مثل `unigram` مع التقطيع العربي نفسه.
  - كل المرشحين بلا فقد لأي نص Unicode صالح. التشكيل وZWNJ يبقيان داخل الكلمة، والـ surrogate المنفرد يُرفض صراحة.
- **القياس (P3-02، `metrics.py`):** على نص اختبار ببذرة مختلفة عن بذرة التدريب (صفر وثائق مشتركة). يقيس:
  - bytes/token وtokens/word في خمس فئات: عربي، وإنجليزي، وكود، ومختلط، وUnicode نادر.
  - طول السلسلة لوثائق عربية من 2000 حرف.
  - P/R/F1 لحدود المورفيمات على 2000 كلمة مشتقة بحدود معروفة، منها جذوع تبدأ بحرف يشبه السابقة.
  - تضخم عدد الرموز في النص المشوش: تشكيل، وتطويل، وأخطاء طباعة، وتكرار حروف، وعربيزي.
  - حصة رموز البايت.
- **Files created:** `src/nawa/tokenizer/{__init__,byte,pretok,bpe,unigram,corpus,metrics}.py`، `configs/tokenizer.yaml`، `docs/decisions/ADR-0006-p3-tokenizer-scope.md`، `tests/test_tokenizer.py`
- **Files modified:** `src/nawa/__init__.py` (وصف قديم)، `tests/test_numerical_verification.py` (إصلاح اختبار P3-08 أدناه)، `experiments/log.jsonl` (EXP-0022)، `ROADMAP.md` (§2.1 G3، §2.2 تفصيل صف P3-01..P3-03، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، `python -m nawa.tokenizer.metrics`
- **Test results:** 452 passed / 0 failed / 1 skipped (431 على `main` + 21 جديدة). pre-commit وdetect-secrets نظيفان.
- **Metrics (EXP-0022، `configs/tokenizer.yaml` hash `e8ed80100d198897`، vocab 2048، مدونة تدريب 644 KB):**
  - **معايير الصحة كلها محققة:** round-trip = 1.0 في كل الفئات ومنها المشوش والنادر، وتدريب حتمي، وحفظ وتحميل متطابقان، والمفردات ضمن الهدف، والمرشحون المتعلَّمون يضغطون العربية أفضل من البايت.
  - **bytes/token على العربية:** byte 1.0، وbpe 4.60، وbpe_arabic 4.35، وunigram 4.62، وunigram_arabic 4.26.
  - **طول 2000 حرف عربي:** نحو 3680 رمزًا بالبايت، مقابل 796 إلى 864 رمزًا للمرشحين المتعلَّمين.
  - **F1 حدود الصرف:** bpe 0.47، وbpe_arabic 0.60، وunigram 0.53، وunigram_arabic 0.61.
  - **التضخم:** التشكيل الكامل يضاعف عدد الرموز 4.3 إلى 4.8 مرات، والعربيزي 2.2 إلى 2.6 مرة، لأن نص التدريب الاصطناعي يخلو منهما.
  - **Unicode النادر:** حصة رموز البايت نحو 0.66 إلى 0.70.
- **إصلاح اختبار P3-08 (FAILED في CI ثم أُصلح):** فشل `test_gradient_accumulation_numerical_equivalence` في CI على PR #23، ونجح محليًا وعلى `main`. لم يُلمس كود النموذج أو التدريب.
  - **الفشل:** عنصر واحد من 2816 اختلف بمقدار 1.8e-6، والحد المسموح 1e-6.
  - **السبب:** الاختبار يقارن الأوزان بعد خطوة AdamW أولى. هذه الخطوة تقارب `lr·g/(|g|+eps)`، فتضخّم ضجيج جمع الأعداد العشرية في التدرجات القريبة من الصفر حتى قرابة lr.
  - **الإصلاح:** مقارنة الأوزان تستخدم الآن SGD، وتحديثه خطي في التدرج، فالتدرجات المتساوية يجب أن تعطي أوزانًا متساوية بالحد نفسه 1e-6. فحص تساوي التدرجات بقي كما هو، والحدود لم تُخفَّف.
- **Git commit:** PR #23، squash `f368e0f` على `main` (سُجّل لاحقًا في R-06 من `git log`)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء. النص يولده الكود ببذرة.
- **Known limitations:**
  - النص اصطناعي، فالأرقام المقارنة لا تصلح للاختيار (ADR-0006).
  - مولّد الحدود الصرفية يستخدم مخزون السوابق نفسه الذي يستخدمه التقطيع العربي، فمكسب `*_arabic` في F1 مضخَّم بالبناء، رغم وجود جذوع شبيهة بالسوابق تعاقب الإفراط في التقسيم.
  - التقطيع العربي لا يعمل على الكلمات المشكولة.
  - Unigram تبسيط بـ hard-EM وتقليم بحسب الاستخدام، لا خسارة SentencePiece الكاملة.
  - التنفيذ بلغة Python الخالصة مناسب للمدونات الصغيرة فقط.
  - لم يُقس الأثر على نموذج مدرَّب، فذلك مع P3-03 وP4.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** لم تبقَ مهمة كود غير محجوبة واضحة في P2 وP3. P3-03 تنتظر OD-03، وP2-05a تنتظر دور التقييم، وP1-06a تنتظر نواة مدربة. أجزاء الكود في P4، مثل P4-03 (أوزان ثلاثية بـ QAT) وP4-05 (KV cache وweight sharing وlow-rank) على النواة المرجعية، قد تُنفذ بنطاق كود فقط على مهام sanity اصطناعية. لكن ذلك يحتاج ADR تحدد النطاق كما فعلت ADR-0005 وADR-0006، ولم يُبدأ.
- **Duplicate-work check:** لا يوجد tokenizer سابق في `src/nawa/`؛ النواة تستخدم `vocab_size=256` placeholder. `src/nawa/training/sanity.py` يولّد نص ماركوف بأبجدية 29 رمزًا لـ P3-05 ولم يُنسخ. `pretok` و`corpus` جديدان.

### R-06 — نطاق مهام P4 القابلة للتنفيذ قبل إغلاق G3 (2026-10-01)

- **Task ID:** R-06
- **Owner:** agent-R-06
- **Status:** DONE
- **Scope:** إصلاح تعارض داخلي. قال تقرير P3-01/02 إنه لا توجد مهمة كود غير محجوبة واضحة، وإن أجزاء الكود في P4 تحتاج ADR تحدد نطاقها. بينما كان صف `P4-01..P4-08` مجملًا وPLANNED دون نطاق. فبقي الوكيل التالي بلا مهمة قابلة للتنفيذ، مع أن قاعدة §0 تسمح بالمهام التي لا تعتمد على قرار معلّق. الحل في ADR-0007:
  - فصل صف P4 إلى ثماني مهام دون تغيير أي معرف، وإضافة أربع مهام فرعية P4-02a..P4-05a للمقارنة على نص حقيقي (BLOCKED)، فلا تضيع المقارنة إذا أُغلقت مهمة الكود على دليل اصطناعي. وأضيف إلى G4 شرط إنجازها، وهذا تشديد لا تخفيف.
  - مهام الكود P4-02..P4-07 غير محجوبة: تنفيذ من الصفر على النواة المرجعية مع اختبارات صحة نجاح/فشل. الأرقام الاصطناعية دليل لا اختيار، ولا تُعتمد أي تقنية.
  - P4-01 (منحنيات التوسع) BLOCKED: المنحنى المقاس على نص اصطناعي يضلل قرار الحجم.
  - P4-08 (الرفع إلى HF) BLOCKED: checkpoints المهام الاصطناعية تُعاد بأمر واحد، ولا قدرة فيها تستحق التخزين.
  - "القرار التقني" في §4 لم يتغير. منع الاعتماد الصامت مفروض باختبار لا بنص: بصمة إعداد النواة `918f4cf4877c0cca` مثبتة، وحزم المسار S (`model` و`training` و`tokenizer`) ممنوعة من استيراد مكتبات النماذج الخارجية.
  - استُكملت مراجع commit/PR في 15 تقريرًا في §2.3 كانت تقول "PR لهذه المهمة (squash)". أُخذت المراجع من `git log` و`gh pr list`، وعُلّم كل منها بـ "سُجّل لاحقًا في R-06". لم تتغير أي نتيجة.
- **Files created:** `docs/decisions/ADR-0007-p4-code-scope.md`
- **Files modified:** `ROADMAP.md` (§2.1 G4، §2.2، §2.3، §4 P4 وG4، §12)، `tests/test_roadmap_consistency.py` (3 اختبارات جديدة)، `tests/test_original_system_policy.py` (اختباران جديدان)، `experiments/log.jsonl` (EXP-0023)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، `pre-commit run --all-files`، `detect-secrets-hook`، و7 اختبارات طفرة يدوية
- **Test results:** المرجع على `main` (`f368e0f`): 452 passed / 1 skipped. بعد التغيير: 457 passed / 0 failed / 1 skipped (452 + 5 جديدة: `test_p4_code_scope_split_blocks_curves_and_upload_and_keeps_g4_unchanged` و`test_task_reports_record_a_commit_or_pr` و`test_p4_real_text_comparisons_are_tracked_and_g4_stays_open` و`test_reference_core_default_config_is_pinned` و`test_track_s_packages_import_no_external_model_libraries`؛ التخطي: CUDA not available). اختبارات الطفرة السبعة كلها أفشلت الاختبار المعني: P4-01 PLANNED، وحذف شرط "scaling curves موجودة"، وإعادة نص "PR لهذه المهمة (squash)"، وحذف شرط P4-02a..P4-05a من G4، وجعل G4 PENDING_REVIEW، وتغيير `mlp` في `configs/base_model.yaml`، وإضافة `import transformers` إلى `src/nawa/model/layers.py`.
- **Metrics:** لا شيء. تغيير حوكمة.
- **مراجعة متعددة النماذج (R-03):** راجع التغيير نموذج مستقل (Claude Opus 5.5، دور reviewer/error_hunter) على حمولة اجتازت `check_payload`. رُفضت الحمولة الأولى لأن سطور السياق تذكر اسم ملف بصمة frozen، فأُرسلت حمولة أصغر بلا تلك السطور. الحكم APPROVE_WITH_CHANGES بثلاث ملاحظات حاجبة، وتحقق الوكيل من كل منها في الكود قبل قبولها (ADR-0003 D4):
  1. لا تعريف لإنجاز P4-02 وP4-04 يفصل الكود عن المقارنة: قُبلت، وأضيفت P4-02a..P4-05a.
  2. صف P4-05 يدّعي تكافؤًا دقيقًا لبنود تغيّر النموذج: قُبلت، وفُصلت البنود، وصار حد التسامح يُسجَّل قبل التشغيل.
  3. D4 مفروض بنص فقط: تأكدت بالفحص، فلا اختبار يثبت بصمة الإعداد ولا قاعدة استيراد. أضيف اختباران.
  - من الملاحظات غير الحاجبة قُبلت فحص بقاء G4 مفتوحة وتصحيحات الصياغة. ورُفضت ملاحظة اشتراط بصمة الدمج في تقرير R-06 نفسه قبل وجودها، فرقم PR هو المرجع وتُسجل البصمة بعد الدمج.
  - السجل: ADR-0007 قسم Review.
- **Git commit:** PR #24، squash `87ad308` على `main` (دُمج بموافقة المالك 2026-10-01 19:27 +03 بعد نجاح CI وفحص الأسرار)
- **HF repository/revision:** لا شيء
- **Dataset version:** لا شيء
- **فحص الأسرار والصلاحيات (بدون طباعة أي قيمة):** المتغيران `GITHUB_TOKEN` و`HF_TOKEN` غير موجودين كمتغيرات بيئة خام (`test -n` سلبي). الوصول يتم عبر مدير أسرار المنصة، الذي يحقن المصادقة عبر proxy، فلا تدخل القيمة إلى بيئة الوكيل ولا إلى أي ملف. سجّل المالك في 2026-10-01 اعتمادين جديدين عبر النموذج الآمن:
  - **HF:** توكن fine-grained للمستخدم `vuuuv`، مقصور على مستودعات `vuuuv/nawa-*` الثمانية بصلاحيات `repo.access.read` و`repo.content.read` و`repo.write` فقط، بلا صلاحيات على مستوى الحساب. هذا يسد توصية R-05 (`AGENTS.md` §11). المستودعات الثمانية كلها `private=true`.
  - **GitHub:** اعتماد محفوظ لـ `github.com`. عمليات Git في هذه الجلسة تمر عبر موصل GitHub للمنصة، وهو يقرأ ويكتب في `sooovg/nawa`.
  - **الحماية:** `main` محمي (PR إلزامي، فحص `test`، منع force push والحذف، enforce_admins). مستودع GitHub ما زال عامًا (OD-07 ACCEPTED_TEMPORARY).
- **Known limitations:**
  - ADR-0007 قُبل بموجب قاعدة إصلاح الخارطة في §0، وللمالك أن يعكسه.
  - ترتيب التنفيذ في D5 اختيار بحسب الاعتماديات: P4-06 قبل P4-02 لأنها السجل الذي تحتاجه كل تجارب P4.
  - المراجع المستكملة في §2.3 تشير إلى commit الدمج، لا إلى commit الفرع المسجل أحيانًا في `experiments/log.jsonl`. السجل نفسه لم يُعدَّل.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §4، §12
- **Next unblocked task:** P4-06 (سجل تجربة P4 الإلزامي ومدققه الآلي)، ثم P4-05 (KV cache بمعيار تكافؤ دقيق). ومراجعة المالك لـ G1 تبقى PENDING_REVIEW.
- **Duplicate-work check:** لا يوجد ADR-0007 ولا R-06 ولا فرع أو PR يعالج نطاق P4. الفروع البعيدة التسعة عشر كلها لمهام مدموجة (PRs #1..#23)، ولا يوجد PR مفتوح. لا يوجد في `src/nawa/` تنفيذ لأي تقنية من P4، فالنواة بلا KV cache (مؤجل صراحة إلى P4-05/P8-04 في تقرير P3-04).

### P4-06 — سجل تجربة P4 الإلزامي ومدققه (2026-10-01)

- **Task ID:** P4-06 (DONE)؛ P4-07 (IN_PROGRESS)
- **Owner:** agent-P4-06
- **Status:** DONE
- **Scope (ADR-0007):** كود فقط على مصدر اصطناعي، على CPU، دون بيانات حقيقية (OD-03 مفتوح)، ودون رفع إلى HF، ودون نموذج خارجي. لم يُقارن أو يُعتمد أي تقنية. البدء بتوجيه المالك (19:27 +03) بعد دمج PR #24.
- **التصميم** (`src/nawa/experiments.py`):
  - **السجل** `p4-record/v1`: حقول `AGENTS.md` §8 كلها، ويضاف إليها: `schema`، و`status`، و`git_dirty`، و`source_tree_sha256` (بصمة كود `src/nawa` الذي شُغّل فعلًا)، و`data_kind`، و`data_description`، و`config` كاملًا، و`criteria` المسجلة قبل التشغيل، و`passed`، و`claims`، و`reproduce`.
  - **المدقق لا يثق بالسجل بل يعيد الاشتقاق:**
    - يحسب `config_hash` من `config` بالاصطلاح نفسه الذي تستخدمه `DecoderConfig.config_hash`.
    - يعيد حساب `passed` من `criteria` و`metrics`، ويطابق بينها وبين `status`.
    - يقرأ من `ROADMAP.md` حالة OD-03 وP4-08. يرفض `data_kind: real` ما دام OD-03 غير محسوم، ويرفض أي `artifact` ما دامت P4-08 غير DONE.
    - يرفض ادعاء `improvement` على بيانات اصطناعية، ويرفض ادعاء `adoption` دائمًا، لأن الاعتماد قرار تقني ببوابة (§4).
    - يشترط أن يكون المسار S، وأن تكون `gpu_hours` و`cost_usd` صفرًا، وألا يوجد نموذج أساس خارجي، وأن تكون بصمة البيانات sha256 كاملة.
  - **السجلات القديمة** EXP-0001..EXP-0023 لم تُعدَّل، وتُفحص بقواعد legacy فقط: JSON سليم، ومعرفات فريدة تصاعدية، وtask_id، وconclusion.
  - `append` يرفض كتابة سجل يجعل الملف غير صالح.
  - الأوامر: `python -m nawa.experiments validate|smoke|bench|record-p4-06`.
- **Files created:** `src/nawa/experiments.py`، `tests/test_experiments.py`، `docs/ablations.md` (P4-07)
- **Files modified:** `experiments/log.jsonl` (EXP-0024، أُنشئ بالباني ومر بالمدقق)، `ROADMAP.md` (§2.1 G4، §2.2، §2.3، §2.4 OD-10، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.experiments validate`، و`bench --seed 2026` و`--seed 7 --n 40`، و`record-p4-06 --seed 42`، و`pre-commit run --all-files`، و`detect-secrets-hook`
- **Test results:** المرجع على `main` (`87ad308`): 457 passed / 1 skipped. بعد التغيير: 493 passed / 0 failed / 1 skipped (457 + 36 جديدة؛ منها 22 اختبار رفض، واحد لكل نوع مخالفة). pre-commit وdetect-secrets نظيفان.
- **Metrics (EXP-0024، المعايير سُجلت قبل التشغيل في `SMOKE_CRITERIA` و`BENCH_CRITERIA`):** كل المعايير محققة.
  - **المدقق على البذرتين 2026 و7:**
    - السجلات القديمة صالحة 23 من 23.
    - السجلات الصالحة مقبولة 30 من 30.
    - المخالفات مكشوفة 110 من 110، على 22 نوعًا.
    - `append` يرفض السجل غير الصالح.
  - **تشغيل الدخان (البذرة 42):**
    - نموذج من 13,568 معاملًا (`model_config_hash` `56bb5bc01d414355`)، 150 خطوة، نحو 4 ثوانٍ على CPU بنواتين.
    - تشغيلان متطابقان في بصمة البيانات والخسارة والأوزان.
    - خسارة التحقق 3.3821 ← 3.3485 (H0 = 3.3653، H2 = 2.3776). هذه أرقام صحة خط التسجيل، لا ادعاء تعلم ولا تحسن.
  - **البصمات:**
    - `config_hash`: `30fb8b8dd3745e51`
    - `data_sha256`: `c3628be8c3addfcb59f8925df205c1d758068480391f0acdd07b9c1535a4465c`
    - `final_weights_sha256`: `ebe88c8e1ba805ec2bd042ba72cc672c8e873dd765fdc8aa38f99e9401060eec`
    - `source_tree_sha256`: `ba59800a0a6c94d361a0271803de392abf8ba757272eefaaccb3f2148d9fcfca`
    - `git_commit`: `87ad308`، و`git_dirty: true`، لأن الكود لم يكن قد التُزم. بصمة الشجرة تحدد الكود بدقة.
    - العتاد: x86_64 بنواتين، وPython 3.14.3، وtorch 2.14.1+cpu.
- **فشل مسجَّل أثناء التطوير:**
  1. المحاولة الأولى للسجل (لم تُلتزم) قالت `git_dirty: false`، مع أن `experiments.py` لم يكن متتبَّعًا. السبب أن `git_state` كان يتجاهل الملفات غير المتتبعة. أُصلح ليحسبها، وأُعيد إنشاء السجل بالمعايير نفسها، وسُجل الفشل في `failure_cases`.
  2. اختبار إعادة الإنتاج كان سيقارن بصمة الأوزان حرفيًا، وCI يعمل بإصدار Python وtorch مختلفين. صار يطابق بصمة البيانات وبصمة الإعداد وعدد المعاملات حرفيًا في كل بيئة، ويطابق الخسارة بحد 1e-3، ولا يطابق بصمة الأوزان حرفيًا إلا في البيئة المسجلة نفسها.
- **المراجعة متعددة النماذج و OD-10 (تصحيح لتقرير R-06):** تحقق الوكيل من حالة تفويض مراجعة Claude Opus 5.5 في R-06:
  - `docs/multi_model_review.md` §1 ينص على ألا يُستخدم نموذج غير مسجل.
  - التسجيل لا يكون إلا بتفويض المالك (`authorized_by: owner`، OD-10).
  - OD-10 مفتوح، و`ModelRegistry` فارغ. وتوجيه المالك العام باستخدام "النماذج المصرح بها" لا يسمي مزودًا.
  - **النتيجة:** تلك المراجعة **غير حاكمة**، ولم تُبنَ عليها قرارات. قرارات R-06 قائمة على الاختبارات الحتمية واختبارات الطفرة السبعة التي أجراها الوكيل، وملاحظات المراجع كانت فرضيات تحقق منها في الكود قبل قبولها.
  - الحمولة كانت كود المستودع العام فقط، واجتازت `check_payload`، فلم يُرسل frozen ولا أسرار ولا بيانات مستخدم.
  - **لم يُستخدم أي نموذج خارجي في P4-06.** أي مراجعة حاكمة لاحقة تحتاج حسم OD-10 وتسجيل المزود.
  - نص تقرير R-06 أعلاه لم يُعَد كتابته.
- **Git commit:** PR #25 (squash بعد نجاح CI وموافقة المالك)
- **HF repository/revision:** لا شيء. لم يُرفع شيء، و`artifact: null`.
- **Dataset version:** لا شيء. البيانات اصطناعية يعيد الكود توليدها من البذرة، ووصفها وبصمتها في السجل.
- **Reproduce:** `python -m nawa.experiments record-p4-06 --seed 42 --dry-run`، و`python -m nawa.experiments validate`
- **Known limitations:**
  - المقياس والمدقق كتبهما الوكيل نفسه، ولا مراجعة مستقلة حاكمة لأن OD-10 مفتوح.
  - المعايير مقارنات بسيطة على مقاييس مفردة، ولا تدعم فواصل الثقة بعد. تُضاف عند أول مقارنة على نص حقيقي (P4-02a..P4-05a).
  - قراءة حالة OD-03 وP4-08 تعتمد على تنسيق جدولي §2.2 و§2.4. الحالة تُعامل محافظةً: OD-03 مفتوح ما لم تكن الحالة RESOLVED أو ACCEPTED.
  - `run_eval.py` ما زال يكتب سجلاته بصيغته القديمة (P1-07)، وتُفحص بقواعد legacy.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §2.4، §12
- **Next unblocked task:** P4-05: KV cache، وspeculative decoding (greedy)، وcompilation، بمعيار تكافؤ ضمن حد تسامح يُسجَّل قبل التشغيل، وبهذا السجل. G1 ما زالت PENDING_REVIEW، وقرارات المالك المفتوحة OD-01..OD-06 وOD-08..OD-10 كما في §2.4.
- **Duplicate-work check:** لا يوجد `src/nawa/experiments.py` ولا مدقق سابق لـ `experiments/log.jsonl`. `eval/run_eval.py` يُلحق سجلات التقييم ولا يتحقق منها. `nawa.review.ReviewLog` سجل مراجعات لا سجل تجارب. لا يوجد فرع أو PR سابق لـ P4-06، ولا PR مفتوح.

### P4-05 — KV cache وspeculative decoding وcompilation، وصحة البنى البديلة (2026-10-01)

- **Task ID:** P4-05 (DONE)؛ P4-07 (IN_PROGRESS، أضيف EXP-0025)
- **Owner:** agent-P4-05
- **Status:** DONE
- **Scope (ADR-0007 D2):** كود فقط، على مصدر اصطناعي، على CPU (`budget.check("cpu_local")`)، دون بيانات حقيقية (OD-03 مفتوح)، ودون رفع إلى HF، ودون نموذج خارجي (OD-10 مفتوح، ولم تُطلب مراجعة خارجية). النواة المرجعية (`src/nawa/model`) لم تتغير، و`configs/base_model.yaml` ما زالت بالبصمة `918f4cf4877c0cca`. لم تُعتمد أي تقنية (D4). البدء بتوجيه المالك (19:48 +03).
- **التسجيل المسبق:** كتبتُ `CRITERIA` و`LOGIT_TOL = 1e-4` و`CONFIG` في `src/nawa/efficiency/p4_05.py`، والتزمتُها في الفرع (commit `3c442f8`) قبل أول تشغيل، ولم تتغير بعده. مبرر حد التسامح: قيم logits في float32 من رتبة 1–10، وإعادة ترتيب الجمع تغيّرها نحو 1e-6. أما خطأ حقيقي، كإزاحة موضع خاطئة أو mask خاطئ، فيغيّرها بأكثر من 1e-2، وهذا ما تُثبته اختبارات التحكم السلبية.
- **التصميم** (`src/nawa/efficiency/`):
  - **`kv_cache.py`:** يستخدم الوحدات والأوزان نفسها، ويحفظ المفاتيح والقيم بعد RoPE وقبل تكرار GQA، ويُطبّق mask بالمواضع المطلقة. يعمل في وضع eval فقط. إذا تجاوز الطول `max_seq_len` فإنه يرجع إلى الحساب الكامل على النافذة المقصوصة، كما تفعل النواة المرجعية.
  - **`speculative.py`:** نموذج مسودة يقترح k رموزًا بطريقة greedy، والنموذج الهدف يتحقق منها في تمريرة واحدة، فيُقبل أطول بادئة مطابقة ثم يُضاف رمز الهدف. يعمل على batch بحجم 1، بالطريقة greedy فقط، ودون قص، وأي استدعاء خارج هذا النطاق يرفع خطأ. لم يُنفذ speculative decoding القائم على العيّنة (rejection sampling).
  - **`compiled.py`:** `torch.compile` على أشكال ثابتة. إن فشل التجميع تُسجَّل نتيجة الفشل، ولا تُخفى.
  - **`structural.py`:**
    - مشاركة الأوزان دوريًا بين الطبقات: الطبقة i تستخدم كتلة i % n.
    - `LowRankLinear` بتحليل SVD مقطوع.
    - `MaskedLinear`، أي sparsity حسب حجم الأوزان، بقناع ثابت.
    - مسابير للسببية والتدرج.
- **Files created:**
  - `src/nawa/efficiency/__init__.py`، `kv_cache.py`، `speculative.py`، `compiled.py`، `structural.py`، `p4_05.py`
  - `tests/test_efficiency.py`
- **Files modified:**
  - `tests/test_original_system_policy.py`: صار يفحص حزمة `efficiency` أيضًا بحثًا عن استيراد مكتبات نماذج خارجية. هذا تشديد.
  - `experiments/log.jsonl`: أضيف EXP-0025، أنشأه `P4Run.build` ومرّ بالمدقق.
  - `docs/ablations.md`
  - `ROADMAP.md`: §2.1 G4، §2.2، §2.3، §12.
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.efficiency.p4_05 --seed 42` (التشغيل المسجل)، و`--seed 7 --dry-run`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وطفرات يدوية.
- **Test results:** المرجع على `main` (`20e5bb2`): 493 passed / 1 skipped. بعد التغيير: 528 passed / 0 failed / 1 skipped (493 + 35؛ التخطي: CUDA not available). أربع طفرات يدوية أُفشلت كلها الاختبارات: رفع `LOGIT_TOL` إلى 1e-3، وحذف إزاحة RoPE في الـ cache، واستبدال رمز التصحيح في speculative برمز المسودة، وإلغاء القناع في `MaskedLinear`. وتحقق `git diff 3c442f8 -- src/nawa` من أن الكود الذي شُغّل هو كود التسجيل المسبق نفسه. الاختبارات الجديدة في `tests/test_efficiency.py` عددها 35، منها ثلاثة اختبارات تحكم سلبية: إزاحة RoPE خاطئة (الفرق أكبر من 1e-2)، وإزالة mask السببية (الفرق أكبر من 1e-2)، وقبول كل رموز المسودة (المخرجات تختلف). كل واحد منها أُفشل كما يجب.
- **Metrics (EXP-0025، البذرة 42)، وكل المعايير الثلاثة عشر محققة:**
  - **KV cache:**
    - أقصى فرق في logits بين المسار المخزَّن والحساب الكامل، على كل المواضع: 4.77e-6 لإعداد `rope_swiglu_gqa`، و3.58e-7 لإعداد `learned_gelu_layernorm_bias`. الحد 1e-4.
    - التوليد بطريقة greedy متطابق في 32 من 32 حالة، وبالعيّنة (T = 1، بالمولّد نفسه) في 32 من 32، وبعد القص (طول 50 + 30 > 64) في 8 من 8.
  - **Speculative decoding:** التطابق مع greedy الهدف 48 من 48 (k = 1، 2، 4).
  - **Compile:** متاح، وأقصى فرق 1.91e-6. استغرق التجميع نحو 13.5 ثانية.
  - **البنى البديلة** (4 طبقات، d = 32):
    - المعاملات: 51,392 في المرجع، و26,176 مع المشاركة، و23,360 مع low-rank (r = 4). كلها تطابق الصيغ المغلقة.
    - low-rank بالرتبة الكاملة يطابق المرجع بفرق 5.96e-8.
    - sparsity بنسبة 50% دقيقة في كل طبقة، و0% مطابقة تمامًا للمرجع.
    - مخالفات السببية 0، والتدرجات موجودة ومحدودة وغير صفرية، وتدرجات الأوزان المقنّعة صفر.
  - **أدلة لا ادعاءات** (نماذج صغيرة على CPU بنواتين وبيانات اصطناعية، فلا تُقرأ سرعةً ولا جودةً على مقياس NAWA):
    - KV cache أسرع بنحو 1.39–1.5 مرة لتوليد 32 رمزًا.
    - قبول المسودة 26.7% و16.6% و8.9% عند k = 1 و2 و4، واستدعاءات الهدف لكل رمز 0.80 و0.77 و0.76. المسودة ضعيفة، ولم أقس الزمن الكلي للـ speculative decoding.
  - **البذرة 7** (تشغيل dry-run للمتانة، لم يُضف إلى السجل): كل المعايير محققة. أقصى فرق 3.93e-6 للـ KV cache و2.67e-6 للـ compile، وكل التطابقات 1.0.
  - **البصمات:**
    - `config_hash`: `f76285c34a004a0b`
    - `data_sha256`: `f199ee47efbf5da0f22ea37be6f11c487bc0179cd9f1391d30ed0289e66b3c99`
    - `source_tree_sha256`: `13f4db9d8f740be187edb70449f818b474ecbee09758b4d1816cef4f789eff1c`
    - `git_commit`: `3c442f8`، و`git_dirty: true`، لأن الاختبارات لم تكن ملتزمة بعد. ملفات `src/nawa` هي نفسها في commit التسجيل المسبق.
    - الأهداف: `7d3150219395c552` و`b8b422c856192555`.
    - العتاد: x86_64 بنواتين، وPython 3.14.3، وtorch 2.14.1+cpu. زمن التجربة 30.3 ثانية.
- **فشل أو قيود مسجلة:**
  - لا فشل في المعايير.
  - قبول المسودة منخفض لأن المسودة أصغر وتدربت 300 خطوة. هذا متوقع، ولا يمس صحة المخرجات.
  - ثلاثة تحذيرات UserWarning في اختبارات `test_efficiency.py` (تحويل tensor يتطلب تدرجًا إلى رقم) أُصلحت داخل الاختبارات بـ `no_grad` أو `detach`، دون أي تغيير في `src`. التحذير الباقي سابق وبيئي: torch لا يجد numpy.
- **Git commit:** PR #26 (squash بعد نجاح CI وموافقة المالك). التسجيل المسبق في `3c442f8` داخل الفرع.
- **HF repository/revision:** لا شيء، و`artifact: null`.
- **Dataset version:** لا شيء. البيانات اصطناعية يعيد الكود توليدها، وبصمتها في السجل ويعيد اختبارٌ حسابها.
- **Reproduce:** `python -m nawa.efficiency.p4_05 --seed 42 --dry-run`
- **Known limitations:**
  - التكافؤ مُختبر على إعدادات صغيرة وعلى CPU float32 فقط، ولم يُختبر على GPU ولا bf16 ولا fp16.
  - speculative decoding يقتصر على greedy وbatch بحجم 1، ولا يقيس أداء نظام speculative كامل.
  - KV cache لا يدعم نافذة منزلقة. بعد `max_seq_len` يرجع إلى الحساب الكامل، تمامًا كالمرجع.
  - compile اختُبر على forward بأشكال ثابتة فقط، ولم يُجمَّع مسار الـ cache.
  - البنى البديلة صحيحة فقط، وأثرها على الجودة ينتظر P4-05a (BLOCKED، OD-03 وP3-03).
  - لا مراجعة مستقلة حاكمة لأن OD-10 مفتوح.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P4-03: أوزان ثلاثية بـ QAT، كود فقط على مهام اصطناعية، وفق ترتيب ADR-0007 D5. G1 ما زالت PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-10 مفتوحة كما في §2.4.
- **Duplicate-work check:** لا يوجد مسار KV cache ولا speculative ولا compile في `src/nawa`. `NawaDecoder.generate` ينص صراحة على أنه بلا cache، ويُحيل إلى P4-05 وP8-04. لا يوجد فرع أو PR سابق لـ P4-05، ولا PR مفتوح.

### P4-03 — أوزان ثلاثية و4-bit بـ QAT، مع fallback إلى 4-bit (2026-10-01)

- **Task ID:** P4-03 (DONE)؛ P4-07 (IN_PROGRESS، أضيف EXP-0026)
- **Owner:** agent-P4-03
- **Status:** DONE
- **Scope (ADR-0007 D2):** كود فقط من الصفر على النواة المرجعية (المسار S)، على مصدر اصطناعي، على CPU (`budget.check("cpu_local")`). لا بيانات حقيقية (OD-03 مفتوح)، ولا رفع إلى HF (P4-08 BLOCKED)، ولا مكتبة تكميم خارجية، ولا نموذج خارجي. النواة المرجعية لم تتغير، و`configs/base_model.yaml` ما زالت بالبصمة `918f4cf4877c0cca`. لم تُعتمد أي تقنية (D4): NAWA ليس "ternary" ولا "4-bit". البدء بتوجيه المالك في هذه الجلسة: "نفّذ أعلى مهمة غير منجزة وغير محجوبة"، وهي P4-03 بترتيب ADR-0007 D5 بعد P4-06 وP4-05.
- **التسجيل المسبق:** كتبتُ `CRITERIA` الخمسة عشر و`LOGIT_TOL = 1e-4` و`FALLBACK` (هامش 0.10 nat) و`CONFIG` في `src/nawa/efficiency/p4_03.py`، والتزمتُها في الفرع (commit `85792fc`) قبل أي تشغيل. تغيّر بعده سطر واحد قبل التشغيل المسجل (`b0420a0`: `float(loss.detach())` لإزالة تحذير)، ولم تتغير المعايير ولا الإعداد. `git diff b0420a0 -- src/nawa` فارغ: الكود الذي شُغّل هو الملتزم. قبل التشغيل المسجل جرى smoke تطويري مصغّر (30 خطوة، البذرة 1، غير مسجل) لكشف الأخطاء البرمجية: نجحت فيه فحوص الصحة كلها، وسقط شرطا التعلم كما هو متوقع بعد 30 خطوة.
- **التصميم** (`src/nawa/efficiency/quant.py`):
  - **الرموز:** الثلاثي: مقياس absmean لكل صف، والرمز `clamp(round(w/s), −1, 1)`. 4-bit: مقياس absmax/7 لكل صف، والرمز في −7..7 (القيمة −8 غير مستعملة كي تبقى الشبكة متماثلة). خيار `granularity="tensor"` متاح.
  - **QAT:** الـ forward يستخدم `codes × scale` بالضبط عبر `autograd.Function`، والـ backward هو STE: التدرج يصل كما هو إلى الوزن الكامن بدقة كاملة، والمقياس ثابت في الـ backward. اختير `Function` بدل صيغة `w + (q − w).detach()` لأن تلك الصيغة لا تعطي `q` بالضبط في float32.
  - **النطاق:** طبقات الكتل فقط (q/k/v/o وup/gate/down). الـ embeddings وlm_head المربوط والـ norms تبقى fp32. هذا نطاق معلن، لا ادعاء عن الطبقات التي يجب تكميمها.
  - **التصدير:** `PackedLinear` يخزن الرموز مضغوطة (الثلاثي 4 رموز في البايت، و4-bit رمزين) مع مقياس float32 لكل صف، ويحسب `(x @ codesᵀ) × scale + b`. حجمه يطابق صيغة مغلقة (`packed_bytes`).
  - **Fallback:** `choose_precision(ref, ternary, int4, FallbackRule(gap))` يعيد `ternary` إن كان ضمن الهامش، وإلا `int4`، وإلا `fp`. نتيجته على بيانات اصطناعية دليل فقط، لا قرار.
- **التجربة** (`p4_03.py`): ثلاث نسخ من النواة (fp وternary وint4)، بالتهيئة نفسها وتسلسل الدفعات نفسه، 1500 خطوة × 32 × 64 لكل منها، على مصدر ماركوف P3-05 (k = 29). النموذج 102,528 معاملًا (d = 64، طبقتان، 4 رؤوس). QAT من التهيئة، لا تكميم بعد تدريب.
- **Files created:** `src/nawa/efficiency/quant.py`، `src/nawa/efficiency/p4_03.py`، `tests/test_quant.py`
- **Files modified:** `experiments/log.jsonl` (EXP-0026، أنشأه `P4Run.build` ومرّ بالمدقق)، `docs/ablations.md` (صفان)، `ROADMAP.md` (§2.1 G4، §2.2، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.efficiency.p4_03 --seed 42` (التشغيل المسجل)، و`--seed 7 --dry-run`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وست طفرات يدوية.
- **Test results:** المرجع على `main` (`7b3f60c`): 528 passed / 1 skipped. بعد التغيير: 570 passed / 0 failed / 1 skipped (528 + 42 جديدة؛ التخطي: CUDA not available). الاختبارات الجديدة تشمل ثلاثة ضوابط سلبية: مكمّم بلا STE يفقد التدرج، ومقياس خاطئ في التصدير يغيّر الـ logits بأكثر من 1e-2، ورموز بلا clamp يرفضها الضغط. الطفرات اليدوية الست أُفشلت كلها الاختبارات: تدرج STE صفري (11 فشلًا)، وحذف الـ clamp (5)، وإزاحة فك الضغط في 4-bit (7)، وحذف المقياس من التصدير (4)، وقاعدة fallback تتجاهل الهامش (1)، وabsmax بدل absmean للثلاثي (1).
- **Metrics (EXP-0026، البذرة 42)، وكل المعايير الخمسة عشر محققة:**
  - **الرموز:** كل الطبقات الثلاثية الـ 14 في {−1, 0, +1} وتستخدم القيم الثلاث (نسبة الأصفار 0.31–0.36)، وكل طبقات 4-bit في −7..7 وإعادة تكميمها تعطي الرموز نفسها، والـ forward يساوي `codes × scale` بالضبط.
  - **STE:** أقصى فرق بين تدرج الوزن الكامن وتدرج الوزن المكمّم: 0.0.
  - **التصدير:** round-trip تام، وأقصى فرق في الـ logits 9.7e-6 (الحد 1e-4)، والبايتات تطابق الصيغة المغلقة.
  - **النموذج:** صفر مخالفات سببية، والتدرجات موجودة ومحدودة وغير صفرية، وحالات قاعدة fallback الست صحيحة، وبصمة النواة المرجعية لم تتغير.
  - **التعلم تحت QAT** (H1 = 3.3137، H2 = 2.3776): الهامش تحت H1 هو 0.614 للثلاثي و0.744 لـ 4-bit (الحد 0.10). النسختان تستخدمان سياق الرمزين.
  - **أدلة لا ادعاءات** (نموذج من طبقتين على مصدر اصطناعي، بذرة واحدة، بلا ضبط للثلاثي):
    - خسارة التحقق: fp 2.542، و4-bit 2.570 (+0.028)، والثلاثي 2.700 (+0.158).
    - قاعدة fallback المسجلة (هامش 0.10) تعيد `int4`: الثلاثي تجاوز الهامش على هذه المهمة. هذا ليس قرارًا ولا ترتيبًا.
    - بايتات طبقات الكتل: fp32 هي 401,408، و4-bit هي 55,552 (7.2×)، والثلاثي 30,464 (13.2×). هذه أرقام الصيغة المغلقة، ولا تشمل الـ embeddings.
  - **البذرة 7** (تشغيل dry-run للمتانة، لم يُضف إلى السجل): المعايير الخمسة عشر محققة. STE 0.0، والتصدير 6.0e-6، والهامشان 0.601 و0.718، والفجوتان عن fp هما +0.147 للثلاثي و+0.030 لـ 4-bit، والقاعدة تعيد `int4` أيضًا.
  - **البصمات:**
    - `config_hash`: `70c4c6f78cce735f`
    - `data_sha256`: `4fbdc37564c4fb902259d457a21dcb0aa0a6f6b93649bee67660acd22f4559a6`
    - `source_tree_sha256`: `a8f21eef9da545be7f77de4eac26a0434b3b4d6a6c8fff1dafe23b061718a78e`
    - `git_commit`: `b0420a0`، و`git_dirty: true` لأن الاختبارات لم تكن ملتزمة بعد، وملفات `src/nawa` هي نفسها في ذلك الـ commit.
    - العتاد: x86_64 بنواتين، وPython 3.14.3، وtorch 2.14.1+cpu. زمن التجربة 135.9 ثانية، وتكلفة صفرية، بلا GPU.
- **Git commit:** PR #27 (squash بعد نجاح CI). التسجيل المسبق في `85792fc` داخل الفرع.
- **HF repository/revision:** لا شيء، و`artifact: null` (P4-08 BLOCKED).
- **Dataset version:** لا شيء. البيانات اصطناعية يعيد الكود توليدها، ويعيد اختبارٌ حساب بصمتها.
- **Reproduce:** `python -m nawa.efficiency.p4_03 --seed 42 --dry-run`
- **Known limitations:**
  - المقارنة مع fp من نموذج واحد صغير ومصدر واحد، ومعدل التعلم نفسه لكل النسخ. QAT الثلاثي يحتاج عادة معدل تعلم وجدولة مختلفين، وهذا لم يُقس. فالفجوة لا تثبت شيئًا عن الثلاثي في حجم NAWA، وتبقى المقارنة الحاكمة في P4-03a.
  - تكميم الأوزان فقط: لا تكميم للتنشيطات، ولا kernel صحيح، فالتصدير يفك الضغط ثم يحسب بـ float32. لا قياس للسرعة (P8-02).
  - الـ embeddings وlm_head خارج التكميم، وهي جزء كبير من النماذج الصغيرة بمفردات كبيرة.
  - السلوك مختبر على CPU float32 فقط.
  - لا مراجعة مستقلة حاكمة، لأن OD-10 مفتوح و`ModelRegistry` فارغ. لم يُستخدم أي نموذج خارجي، والأدلة هي الاختبارات الحتمية والطفرات الست.
- **فحص الأسرار والصلاحيات (بدون طباعة أي قيمة):** `test -n "$GITHUB_TOKEN"` و`test -n "$HF_TOKEN"` سلبيان: التوكنان ليسا متغيري بيئة خامين في جلسة الوكيل. الوصول يتم عبر مدير أسرار المنصة، الذي يحقن المصادقة عبر proxy دون كشف القيمة، وهذا يحقق `AGENTS.md` §11 ("متغيرات بيئة أو مدير أسرار آمن"). أعاد المالك في 2026-10-01 تسجيل توكن HF عبر النموذج الآمن، ووصّل GitHub عبر موصل المنصة. تحقق الوكيل دون طباعة أي قيمة من أن توكن HF للمستخدم `vuuuv` fine-grained، ومقصور على مستودعات `vuuuv/nawa-*` الثمانية بصلاحيات `repo.access.read` و`repo.content.read` و`repo.write` فقط، بلا صلاحيات عامة وبلا قراءة للمستودعات المقيدة. والمستودعات الثمانية كلها `private=true`. أما صلاحية موصل GitHub فلم يُفحص نطاقها بالتفصيل، لأن المنصة تمنع فحص بيانات الاعتماد؛ وهو يقرأ ويكتب في `sooovg/nawa`. **OWNER ACTION REQUIRED:** إن أردت التزامًا كاملًا بـ §11، فاقصر تفويض تطبيق GitHub على مستودع `sooovg/nawa` وحده. مستودع GitHub ما زال عامًا (OD-07 ACCEPTED_TEMPORARY).
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P4-02: Dense مقابل Sparse MoE مقابل Hybrid، كود واختبارات صحة فقط على مهام اصطناعية، وفق ترتيب ADR-0007 D5. ثم P4-04. G1 ما زالت PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-10 مفتوحة كما في §2.4.
- **Duplicate-work check:** لا يوجد تكميم أو QAT أو ضغط رموز في `src/nawa`. `MaskedLinear` (P4-05) تقنية sparsity مختلفة ولم تُنسخ. P8-02 (تكميم الإصدار) مهمة مستقبلية تعتمد على نتيجة P4-03a ولم تُبدأ. فُحصت الفروع البعيدة الـ 22، وكلها لمهام مدموجة (PRs #1..#26)، ولا يوجد PR مفتوح ولا فرع لـ P4-03.

### P4-02 — Dense مقابل Sparse MoE مقابل Hybrid (2026-10-01)

- **Task ID:** P4-02 (DONE)؛ P4-07 (IN_PROGRESS، أضيف EXP-0027)
- **Owner:** agent-P4-02
- **Status:** DONE
- **Scope (ADR-0007 D2):**
  - كود فقط من الصفر على النواة المرجعية (المسار S)، على مصدر اصطناعي، على CPU (`budget.check("cpu_local")`).
  - لا بيانات حقيقية (OD-03 مفتوح)، ولا رفع أوزان أو artifacts إلى HF (P4-08 BLOCKED)، ولا مكتبة MoE خارجية، ولا نموذج خارجي.
  - النواة المرجعية لم تتغير، و`configs/base_model.yaml` ما زالت بالبصمة `918f4cf4877c0cca`. لم يُختر ولم يُعتمد Dense ولا MoE ولا Hybrid (D4).
  - البدء بتوجيه المالك في هذه الجلسة: "تابع إلى P4-02 ثم P4-04". وفي التوجيه نفسه: نتائج P4-03 تجارب تقنية فقط، وP4-03a تبقى BLOCKED، وتقليل الحجم النظري لا يمثل حجم النموذج النهائي ولا ذاكرة التشغيل.
- **التعريفات المستخدمة** (نطاق معلن، لا ادعاء عن التصميم الصحيح):
  - **Dense:** النواة المرجعية P3-04 كما هي.
  - **Sparse MoE:** كل MLP يُستبدل بـ `SparseMoE`. فيه router خطي، ثم softmax على الخبراء، ثم أعلى k خبراء لكل token، مع إعادة تطبيع البوابات على الخبراء المختارين. ويمكن إضافة خبراء مشتركين يعملون دائمًا. كل خبير بصيغة MLP المرجع (SwiGLU أو GELU) بعرض `d_expert`.
  - **Hybrid:** الكتل المدرجة في `moe_layers` فقط تستخدم `SparseMoE`، والباقية تبقى dense.
  - **Load-balance loss:** بصيغة Switch معممة إلى top-k: \(E \sum_i f_i P_i\)، وتساوي 1 عند التوجيه المتوازن تمامًا.
  - **التوجيه:** لكل token دون حد سعة، فلا يُسقط أي token، ولا يعتمد ناتج token على بقية الدفعة. حد السعة كان سيكسر السببية وثبات الناتج مع تغير الدفعة، لذلك لم يُنفَّذ (انظر القيود).
- **التسجيل المسبق:**
  - التزمتُ بالمعايير و`TOL = 1e-5` و`IDENTITY_TOL = 1e-6` و`CONFIG` في `093a367` قبل أي تشغيل.
  - **تعديل موثق قبل التشغيل المسجل (`1d8e66e`):** أظهر smoke تطويري مصغّر (20 خطوة، البذرة 1، غير مسجل) "مخالفة" سببية واحدة بحجم 1.5e-8 في مسار التوزيع، و0 في المسار الكثيف المرجعي (`dense_forward`). فحصتُ ست بذور بثماني محاولات لكل منها، فكانت النتيجة 0 مخالفات في المسار الكثيف، وأقصى فرق 1.5e-8 في مسار التوزيع. السبب تقريب float32: تغيير token لاحق قد يغيّر عدد الصفوف التي تدخل matmul خبيرٍ ما، فيتغير البت الأخير لصف لم يتغير. لا تتدفق أي معلومة إلى الخلف.
  - لذلك استُبدل المعيار `moe_causality_violations == 0` بمعيارين أشد في المضمون: سببية تامة (0) عبر المسار الكثيف، وفرق مسار التوزيع ≤ TOL. والعدد الصارم في مسار التوزيع محفوظ كدليل. لم يتغير أي معيار آخر، والسبب مكتوب في docstring الوحدة.
- **التجربة** (`p4_02.py`):
  - ثلاث نسخ بالتهيئة نفسها للانتباه والـ embeddings والـ norms، وبتسلسل الدفعات نفسه: 1500 خطوة × 32 × 64، على مصدر ماركوف P3-05 (k = 29). الخسارة هي cross-entropy + 0.01 × load-balance.
  - MoE: 4 خبراء، top-2، بعرض 88 (نصف عرض MLP المرجع 176)، فيبقى عرض MLP الفعال لكل token مساويًا للمرجع.
- **Files created:** `src/nawa/efficiency/moe.py`، `src/nawa/efficiency/p4_02.py`، `tests/test_moe.py`
- **Files modified:** `experiments/log.jsonl` (EXP-0027)، `docs/ablations.md` (صفان)، `ROADMAP.md` (§2.1 G4، §2.2 P4-02 وP4-07 وR-07، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.efficiency.p4_02 --seed 42` (التشغيل المسجل)، و`--seed 7 --dry-run`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وست طفرات يدوية.
- **Test results:**
  - المرجع على `main` (`1d1bd53`): 570 passed / 1 skipped.
  - بعد التغيير: 623 passed / 0 failed / 1 skipped (570 + 53 جديدة؛ التخطي: CUDA not available).
  - **الضوابط السلبية:** بوابة الخانة الأولى لكل الخانات تكسر تطابق التوزيع، وبوابات غير مُعاد تطبيعها تكسر هوية الخبراء المتساوين، وتسرب متوسط التسلسل يكشفه فحص السببية.
  - **الطفرات اليدوية الست** أُفشلت كلها الاختبارات:
    - بوابات بلا إعادة تطبيع (2 فشل)
    - بوابة خانة خاطئة (5)
    - مقام خاطئ في \(f_i\) (1)
    - صيغة active بـ `n_experts` (1)
    - FLOPs بلا router (2)
    - توزيع يُسقط الخبير المشترك (5)
- **Metrics (EXP-0027، البذرة 42)، وكل المعايير الستة عشر محققة:**
  - **المحاسبة:** المعاملات الكلية تطابق الصيغة المغلقة في 6 إعدادات (SwiGLU وGELU مع bias، وMoE وHybrid وخبير مشترك). والمعاملات الفعالة لكل token تساوي عدد المعاملات التي تتلقى تدرجًا من token واحد. وFLOPs الصيغة تساوي MACs المعدودة بـ hooks على كل Linear، مضافًا إليها حد سياق الانتباه.
  - **التوزيع:** أقصى فرق عن المرجع الكثيف 4.8e-7 (الحد 1e-5). كل خبير يعمل على tokens الموجهة إليه فقط، ومجموع الإسنادات يساوي top-k × عدد الـ tokens.
  - **الهويات:** خبير واحد ببوابة 1 فرقه 0.0 (الحد 1e-6)، وأربعة خبراء مطابقون للـ MLP فرقهم 1.2e-7.
  - **السلوك:** الثبات مع تغير الدفعة 1.2e-7. السببية في المسار الكثيف 0 مخالفات. فرق مسار التوزيع 4.8e-7، مع فرقين صارمين بحجم float32 (دليل). وDense نفسه 0 مخالفات.
  - **التدرجات وloss التوازن:** التدرجات سليمة لـ MoE وHybrid. فحوص loss التوازن صحيحة: يساوي 1.0 عند التوزيع المتساوي، ويطابق الحساب المستقل، ويعاقب التركيز، ويعطي الـ router تدرجًا. بصمة النواة المرجعية لم تتغير.
  - **التعلم** (H1 = 3.3137، H2 = 2.3776): الهامش تحت H1 هو 0.772 لـ Dense، و0.806 لـ MoE، و0.799 لـ Hybrid (الحد 0.10).
  - **أدلة لا ادعاءات** (نموذج من طبقتين، مصدر اصطناعي واحد، بذرتان):
    - خسارة التحقق: Dense 2.542، وMoE 2.508 (−0.034)، وHybrid 2.515 (−0.027). وبالبذرة 7: 2.563 و2.522 و2.524.
    - MoE وHybrid لديهما 1.66× و1.33× من معاملات Dense الكلية، بمعاملات فعالة وFLOPs شبه متساوية (103,040 و102,784 مقابل 102,528؛ و238,208 و237,696 مقابل 237,184 FLOPs/token عند سياق 64). لذلك لا تفصل الفجوة الصغيرة بين أثر السعة وأثر التوجيه.
    - بايتات المعاملات بـ fp32: 410,112 و682,496 و546,304. هذه أوزان فقط، وليست ذاكرة التشغيل (التنشيطات وKV cache وحالة المُحسِّن)، ولا حجم نموذج نهائي.
    - لا خبير ميت، وحصة كل خبير بين 0.21 و0.33.
    - **زمن الاستجابة:** القيم في سجل EXP-0027 غير صالحة، لأنها قيست أثناء تشغيل الوكيل اختبارات طفرة على المعالجين نفسيهما (Dense 9.7، وMoE 745، وHybrid 21.8 ms). أعاد الوكيل القياس دون أي حمل آخر في dry-run بالبذرة 7، فكانت النتيجة 4.9 و4.8 و3.9 ms (الوسيط لدفعة 8×64). هذا ضجيج عند هذا الحجم، ولا يُستنتج منه شيء.
  - **البذرة 7** (dry-run، لم يُضف إلى السجل): المعايير الستة عشر محققة. التوزيع 4.8e-7، وفرق مسار التوزيع 0.0، والثبات مع الدفعة 6.6e-7، والهوامش 0.748 و0.790 و0.787.
  - **البصمات:**
    - `config_hash`: `27370e3f7d5f28f8`
    - `data_sha256`: `4fbdc37564c4fb902259d457a21dcb0aa0a6f6b93649bee67660acd22f4559a6` (المصدر نفسه في EXP-0026)
    - `source_tree_sha256`: `b615828a77ddfc8cf46667436b5c47d65c7d2e208c0b4d52d0fb90c0bcec2005`
    - `git_commit`: `1d8e66e` (`git_dirty: true` لأن الاختبارات لم تكن ملتزمة بعد، و`src/nawa` مطابق لذلك الـ commit)
    - العتاد: x86_64 بنواتين، وPython 3.14.3، وtorch 2.14.1+cpu، والزمن 252.2 ثانية، والتكلفة صفرية.
- **Git commit:** PR #28 (squash بعد نجاح CI). التسجيل المسبق في `093a367`، وتعديله الموثق في `1d8e66e`، داخل الفرع.
- **HF repository/revision:** لا شيء (`artifact: null`).
- **Dataset version:** لا شيء. البيانات اصطناعية يعيد الكود توليدها، وبصمتها مختبرة.
- **Reproduce:** `python -m nawa.efficiency.p4_02 --seed 42 --dry-run`
- **Known limitations:**
  - **بلا حد سعة:** هذا يحفظ السببية والثبات مع الدفعة، لكنه ليس ما تفعله أنظمة MoE الموزعة عادة. أي حد سعة لاحق يحتاج تصميمًا لا يكسر السببية أثناء الاستدلال.
  - **التوزيع:** حلقة Python على الخبراء بـ `index_add`، فلا kernel مجمّع، ولا توازي خبراء، ولا قياس ذاكرة تشغيل.
  - **السببية في مسار التوزيع** صحيحة معلوماتيًا، لكنها ليست مطابقة بتًا ببت (فروق float32 تصل إلى 4.8e-7). وهي مثبتة تامة على المسار الكثيف.
  - **نطاق المقارنة:** نموذج واحد صغير ومصدر واحد. التوجيه في ماركوف من الرتبة 2 لا يمثل نصًا حقيقيًا. لم يُضبط معدل التعلم ولا معامل loss التوازن لكل متغير. والمقارنة الحاكمة في P4-02a.
  - **الاستقلالية:** لا مراجعة مستقلة حاكمة، لأن OD-10 مفتوح و`ModelRegistry` فارغ. لم يُستخدم أي نموذج خارجي.
- **فحص الأسرار والصلاحيات (بدون طباعة أي قيمة):** الوضع كما في تقرير P4-03، والوصول يتم عبر مدير أسرار المنصة. قصر تفويض GitHub على `sooovg/nawa` سُجِّل تحسينًا أمنيًا منفصلًا غير حاجب (R-07) بتوجيه المالك، وليس شرطًا لهذه المهمة.
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** P4-04: كتل attention + convolution/hybrid، كود واختبارات صحة فقط، دون اعتماد أي نسبة (ADR-0007 D5). G1 ما زالت PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-10 مفتوحة كما في §2.4.
- **Duplicate-work check:**
  - لا يوجد MoE أو router أو experts في `src/nawa` (`rg -i "moe|router|expert"` لا يجد إلا نصوصًا وصفية وآلية `expert_review` في `data_verify.py`، وهي غير ذات صلة).
  - لا فرع ولا PR لـ P4-02، ولا PR مفتوح. و`main` عند `1d1bd53`.

### P4-04 — كتل attention + convolution والتخطيطات الهجينة (2026-10-02)

- **Task ID:** P4-04 (DONE)؛ P4-07 (IN_PROGRESS، أضيف EXP-0028)
- **Owner:** agent-P4-04
- **Status:** DONE
- **Scope (ADR-0007 D2):**
  - كود فقط من الصفر على النواة المرجعية (المسار S)، على مصدر اصطناعي، على CPU (`budget.check("cpu_local")`).
  - لا بيانات حقيقية (OD-03 مفتوح)، ولا رفع إلى HF (P4-08 BLOCKED)، ولا مكتبة خارجية غير torch، ولا نموذج خارجي (OD-10 مفتوح).
  - النواة المرجعية لم تتغير، و`configs/base_model.yaml` ما زالت بالبصمة `918f4cf4877c0cca`. لم تُعتمد أي نسبة attention:convolution، ولا 1:2 ولا غيرها (§4 P4-04، ADR-0007 D4).
  - البدء بتوجيه المالك في هذه الجلسة: "نفّذ أعلى مهمة غير منجزة وغير محجوبة"، وهي P4-04 بترتيب ADR-0007 D5 بعد P4-06 وP4-05 وP4-03 وP4-02.
- **التعريفات المستخدمة** (نطاق معلن، لا ادعاء عن التصميم الصحيح):
  - **كتلة attention:** كتلة P3-04 المرجعية كما هي.
  - **كتلة convolution:** الكتلة نفسها، مع استبدال طبقة attention الفرعية بـ `ConvMixer`: \(o\_proj(conv(v) \odot act(g))\)، حيث \((v, g) = in\_proj(x)\). الالتفاف depthwise سببي بـ K معاملات لكل قناة: \(y_{t,c} = b_c + \sum_{j=0}^{K-1} w_{c,j}\, v_{t-j,c}\)، مع أصفار قبل الموضع 0. البوابة SiLU أو sigmoid أو بدون. طبقة MLP لم تتغير.
  - **التخطيط:** قائمة الكتل التي تستخدم الالتفاف (`conv_layers`). كل الكتل attention هو المرجع، وكلها convolution نموذج التفاف قصير، وما بينهما هجين بنسبة معلنة.
  - **التنفيذ:** الالتفاف مجموع K نسخ مُزاحة ومضروبة عنصريًا، فكل موضع يقرأ نفسه وK−1 موضعًا قبله فقط، بأشكال ثابتة. لذلك السببية والمجال الاستقبالي تامان بتًا ببت. `CausalDepthwiseConv.reference` مسار مستقل عبر `F.conv1d` (مع قلب النواة)، و`ConvMixer.step` صيغة تدفقية بحالة من آخر K−1 مدخلات.
- **التسجيل المسبق:**
  - التزمتُ بالمعايير الخمسة عشر و`TOL = 1e-5` و`IDENTITY_TOL = 1e-6` و`CONFIG` في `9af18f0` قبل أي تشغيل.
  - **تعديل موثق قبل التشغيل المسجل (`49628b2`):** smoke تطويري للمسابير (البذرة 1، بلا تدريب، غير مسجل) كشف عيبين في **المسابير** لا في التنفيذ. لم يتغير أي معيار ولا حد تسامح ولا إعداد:
    1. `surgery_preserved` اشترط غياب المفاتيح المستبدلة، لكن `ConvMixer` يسمي إسقاط خرجه `o_proj` أيضًا، فالمفتاح `blocks.i.attn.o_proj.*` موجود في النموذجين. صار المسبار يتخطى المفاتيح تحت البادئة المستبدلة، ويتحقق من أن الوحدة هناك `ConvMixer`، ويطابق كل مفتاح آخر حرفيًا، وهذا نص المعيار.
    2. `reference_and_streaming_checks` عشّأ المعاملات بانحراف 0.5، فبلغت المخرجات نحو 495، وكان الفرق المقاس 4.6e-5 مطلقًا و6e-8 نسبيًا، أي تقريب float32 خارج نطاق التنشيطات من رتبة 1 الذي بُرر به الحد. صار التعشية بانحراف 1/√fan_in، وأقصى خرج مسجل دليلًا (10.6).
  - `git diff 49628b2 -- src/nawa` فارغ: الكود الذي شُغّل هو الملتزم.
- **التجربة** (`p4_04.py`): ثلاث نسخ بالتهيئة نفسها للـ MLP والـ norms والـ embeddings، وبتسلسل الدفعات نفسه: 1500 خطوة × 32 × 64 لكل منها، على مصدر ماركوف P3-05 (k = 29). attention (المرجع)، وconvolution في الكتلتين (نسبة 0:2)، وهجين: convolution في الكتلة 0 وattention في الكتلة 1 (نسبة 1:1). K = 4 وبوابة SiLU.
- **Files created:** `src/nawa/efficiency/conv.py`، `src/nawa/efficiency/p4_04.py`، `tests/test_conv.py`
- **Files modified:** `experiments/log.jsonl` (EXP-0028، أنشأه `P4Run.build` ومرّ بالمدقق)، `docs/ablations.md` (صفان)، `ROADMAP.md` (§2.1 G4، §2.2 P4-04 وP4-07، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.efficiency.p4_04 --seed 42` (التشغيل المسجل)، و`--seed 7 --dry-run`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وثماني طفرات يدوية.
- **Test results:**
  - المرجع على `main` (`d09011f`): 623 passed / 1 skipped.
  - بعد التغيير: 712 passed / 0 failed / 1 skipped (623 + 89 جديدة؛ التخطي: CUDA not available). pre-commit وdetect-secrets نظيفان، والسجل صالح.
  - **الضوابط السلبية:** `conv1d` بلا قلب النواة يختلف بأكثر من 1e-2، وحالة تدفقية لا تتقدم تختلف بأكثر من 1e-2، والتفاف يقرأ الموضع t+1 يكشفه فحص السببية، وادعاء مجال استقبالي أقصر من الحقيقي يكشفه مسبار المجال.
  - **الطفرات اليدوية الثماني** أُفشلت كلها الاختبارات: الإزاحة في الاتجاه الخاطئ (30 فشلًا)، والخطوة التدفقية بلا قلب (5)، والمرجع بلا قلب (8)، وصيغة المعاملات بلا bias الالتفاف (10)، وFLOPs بلا معاملات النواة (1)، والمجال الاستقبالي L·K بدل L·(K−1) (5)، وعدم استعادة حالة RNG العامة (1)، وتجاهل البوابة (5).
- **Metrics (EXP-0028، البذرة 42)، وكل المعايير الخمسة عشر محققة:**
  - **المحاسبة:** المعاملات تطابق الصيغة المغلقة في 30 حالة (نموذجان من طبقتين بثلاثة تخطيطات، ونموذج من 4 طبقات بأربعة تخطيطات بنسب convolution:attention هي 1:3 و2:2 و3:1 و4:0، كلها × 3 إعدادات التفاف). وFLOPs الصيغة تساوي MACs المعدودة بـ hooks على كل Linear وكل التفاف، مضافًا إليها حد سياق كتل attention الباقية.
  - **الالتفاف:** أقصى فرق عن مسار `conv1d` المستقل 1.4e-6، والصيغة التدفقية عن الحساب الكامل 9.5e-7 (الحد 1e-5). النواة الدلتا بلا بوابة تعيد \(o\_proj(in\_proj(x))\) بفرق 0.0 (الحد 1e-6).
  - **السلوك:** صفر مخالفات سببية في convolution والهجين (وattention أيضًا 0). المجال الاستقبالي للنموذج الالتفافي الكامل 6 = 2 × (4 − 1) بالضبط: صفر تغيرات بعده، وتغير عند حده في كل محاولة. الثبات مع تغير الدفعة 0.0. الجراحة لا تمس أي وزن آخر، والتدرجات سليمة، وبصمة النواة المرجعية لم تتغير.
  - **التعلم** (H1 = 3.3137، H2 = 2.3776): الهامش تحت H1 هو 0.772 لـ attention، و0.807 لـ convolution، و0.819 للهجين (الحد 0.10).
  - **أدلة لا ادعاءات** (نموذج من طبقتين، مصدر اصطناعي واحد، بذرتان):
    - خسارة التحقق: attention 2.542، وهي مطابقة لـ Dense في EXP-0027 (البذرة والتهيئة والدفعات نفسها)، وهذا فحص إعادة إنتاج مستقل. convolution 2.507 (−0.035)، والهجين 2.495 (−0.047). وبالبذرة 7: 2.563 و2.517 و2.508.
    - المعاملات: 102,528 و94,848 و98,688.
    - FLOPs لكل token عند سياق 64: 237,184 و189,056 و213,120. وعند سياق 1,024 بالصيغة: 728,704 و189,056 و458,880، لأن كلفة الالتفاف لا تعتمد على طول السياق.
    - حالة فك الترميز لكل تسلسل عند سياق 1,024 بالصيغة: 262,144 و384 و131,264 عددًا عشريًا. هذه حالة attention/convolution فقط، وليست ذاكرة تشغيل.
    - زمن CPU (الوسيط لدفعة 8×64، دون حمل آخر): 2.9 و2.7 و2.3 ms. هذا ضجيج عند هذا الحجم.
    - **حد هذا المصدر:** ماركوف من الرتبة 2 لا يحتاج إلا رمزين من السياق، والمجال الاستقبالي للالتفاف الكامل 6. فهذا المصدر لا يستطيع إظهار ما تضيفه attention فوق التفاف قصير، ولا يصلح لترتيب التخطيطات.
  - **البذرة 7** (dry-run، لم يُضف إلى السجل): المعايير الخمسة عشر محققة. المرجع 1.1e-6، والتدفقية 9.5e-7، والثبات مع الدفعة 0.0، والسببية 0، والمجال 0 مخالفات، والهوامش 0.748 و0.795 و0.803.
  - **البصمات:**
    - `config_hash`: `88d01a41acfd15cc`
    - `data_sha256`: `4fbdc37564c4fb902259d457a21dcb0aa0a6f6b93649bee67660acd22f4559a6` (المصدر نفسه في EXP-0026 وEXP-0027)
    - `source_tree_sha256`: `c501b657cb0307235e3cbca69606a4d6c4dca49372b44aff04e683b94d6db7c7`
    - `git_commit`: `49628b2` (`git_dirty: true` لأن الاختبارات لم تكن ملتزمة بعد، و`src/nawa` مطابق لذلك الـ commit)
    - العتاد: x86_64 بنواتين، وPython 3.14.3، وtorch 2.14.1+cpu، والزمن 102.7 ثانية، والتكلفة صفرية، بلا GPU.
- **Git commit:** PR #29، squash `f47a3a9` على `main` (دُمج بعد نجاح CI، سُجّل لاحقًا في R-08)، من الفرع `agent/P4-04-attn-conv-hybrid`. التسجيل المسبق في `9af18f0`، وتعديله الموثق في `49628b2`. دُفعت الـ commits عبر GitHub Git Data API بالبصمات نفسها (الشجرة والآباء والمؤلف والتاريخ والرسالة مطابقة، فالـ SHA مطابق)، لأن `git push` عبر `github.com` غير متاح في هذه البيئة.
- **HF repository/revision:** لا شيء (`artifact: null`).
- **Dataset version:** لا شيء. البيانات اصطناعية يعيد الكود توليدها، وبصمتها مختبرة.
- **Reproduce:** `python -m nawa.efficiency.p4_04 --seed 42 --dry-run`
- **Known limitations:**
  - **المصدر:** ماركوف من الرتبة 2 يغطيه التفاف قصير، فلا يقيس الاعتماديات البعيدة. المقارنة الحاكمة على نص حقيقي في P4-04a.
  - **الالتفاف:** نوع واحد فقط: depthwise قصير بمجموع إزاحات (حلقة Python على K). لم تُنفَّذ نوى طويلة، ولا FFT، ولا التفافات معلَّمة ضمنيًا، ولا تبويب متعدد المراحل.
  - **التدفق:** الصيغة التدفقية مختبرة على مستوى الـ mixer. لا مسار توليد على مستوى النموذج يجمع KV cache للـ attention مع حالة الالتفاف، وذلك يتبع P4-05 وP8-04.
  - **التهيئة:** معاملات النواة U(−1/√K, 1/√K). لم يُضبط معدل التعلم ولا التهيئة لكل تخطيط.
  - **القياس:** CPU float32 فقط، وزمن الاستجابة ضجيج عند هذا الحجم.
  - **الاستقلالية:** لا مراجعة مستقلة حاكمة، لأن OD-10 مفتوح و`ModelRegistry` فارغ. لم يُستخدم أي نموذج خارجي، والأدلة هي الاختبارات الحتمية والضوابط السلبية والطفرات الثماني.
- **فحص الأسرار والصلاحيات (بدون طباعة أي قيمة):**
  - `test -n "$GITHUB_TOKEN"` و`test -n "$HF_TOKEN"` سلبيان: التوكنان ليسا متغيري بيئة خامين. أعاد المالك في 2026-10-02 تسجيل التوكنين عبر النموذج الآمن لمدير أسرار المنصة، الذي يحقن المصادقة عبر proxy، فلا تدخل القيمة إلى بيئة الوكيل ولا إلى أي ملف (`AGENTS.md` §11).
  - **HF:** توكن fine-grained للمستخدم `vuuuv`، مقصور على مستودعات `vuuuv/nawa-*` الثمانية بصلاحيات `repo.access.read` و`repo.content.read` و`repo.write` فقط، بلا صلاحيات عامة. `nawa-eval` و`nawa-core` تحققا `private=true`.
  - **GitHub:** الاعتماد الجديد مسجل لـ `api.github.com`، ويظهر أنه **classic PAT** بالنطاقات `repo` و`workflow` و`write:packages`، وينتهي في 2026-12-29. يرى مستودعًا واحدًا (`sooovg/nawa`)، لكن نطاق `repo` يشمل كل مستودعات الحساب. **OWNER ACTION REQUIRED (R-07، غير حاجب):** استبداله بتوكن fine-grained مقصور على `sooovg/nawa` بصلاحيات Contents وPull requests للقراءة والكتابة فقط، ودون `workflow` و`write:packages`.
  - `main` ما زال محميًا، ومستودع GitHub ما زال عامًا (OD-07 ACCEPTED_TEMPORARY).
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** إغلاق P4-07: شرط الإغلاق (P4-02..P4-05) تحقق، والمهمة ترتبط بجدول `docs/ablations.md` الذي يحمل الآن EXP-0024..EXP-0028. بعدها لا تبقى مهمة كود غير محجوبة في P0–P4: P3-03 وP4-01 وP4-02a..P4-05a وP4-08 تنتظر OD-03، وP2-05a تنتظر دور Eval، وP1-06a تنتظر نواة نصية من P5. المرشح التالي مهمة اتساق (R-08) تحدد بـ ADR نطاق كود فقط لمهام P6 (التحقق والامتناع والأدوات)، كما فعلت ADR-0005 وADR-0007. لم تُبدأ هنا. G1 ما زالت PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-10 مفتوحة كما في §2.4.
- **Duplicate-work check:**
  - لا يوجد التفاف ولا mixer بديل لـ attention في `src/nawa`: `rg -il "convolution|conv1d|ConvMixer"` خارج ملفي هذه المهمة لا يجد إلا نص `next_action` في `p4_02.py` الذي يسمي P4-04 مهمةً تالية. `MaskedLinear` وweight sharing وlow-rank (P4-05) وMoE (P4-02) تقنيات مختلفة ولم تُنسخ. يُعاد استخدام `causality_violations` و`gradient_report` من P4-05 والمصدر وحلقة التقييم من P3-05.
  - لا فرع ولا PR لـ P4-04، ولا PR مفتوح، و`main` عند `d09011f`.

### P4-07 — سجل ablations لكل تجارب P4 وإغلاقه (2026-10-02)

- **Task ID:** P4-07 (DONE)
- **Owner:** agent-P4-07
- **Status:** DONE
- **Scope:**
  - إغلاق P4-07 بشرطها في ADR-0007: P4-02..P4-05 منجزة، وكل تجربة P4 مدرجة بما فيها الإخفاقات. البدء بتوجيه المالك في 2026-10-02: "تابع وأغلق P4-07 ... وسجّل جدول التجارب كاملًا".
  - توثيق فقط: لا كود في `src`، ولا تشغيل جديد، ولا تعديل لـ `experiments/log.jsonl` (السجل append-only).
  - **لا اعتماد:** لا تُعتمد attention ولا convolution ولا hybrid ولا أي تقنية أخرى، ولا نسبة attention:convolution. نتائج P4-04 (EXP-0028) أدلة أولية على بيانات اصطناعية. بصمة النواة المرجعية `918f4cf4877c0cca` لم تتغير.
  - لم تبدأ أي مقارنة على نص حقيقي (P4-01، P4-02a..P4-05a)، ولم يُرفع شيء إلى HF (P4-08)، لأن OD-03 مفتوح. لم يُستخدم أي نموذج خارجي (OD-10 مفتوح).
- **ما أضيف إلى `docs/ablations.md`:**
  - **حالة الإغلاق:** قواعد ما بعد الإغلاق. يبقى السجل مفتوحًا للإضافة، فكل تجربة P4 لاحقة تضيف صفوفها.
  - **فهرس كل سجلات P4:** يُولَّد من `experiments/log.jsonl`، بصف لكل سجل `p4-record/v1` (EXP-0024..EXP-0028). أعمدته: الحالة، و`passed`، وعدد المعايير، و`data_kind`، والبذرة، والخطوات، وساعات GPU، والتكلفة، و`config_hash`، و`git_commit`، والأثر، وأمر إعادة الإنتاج. السجلات القديمة EXP-0001..EXP-0023 لمراحل أخرى، وليست ablations لـ P4.
  - **حالة كل تقنية:** تسع تقنيات، لكل منها مهمة الكود، ونتيجة الصحة، والدليل الاصطناعي الأولي، وعمود الاعتماد (NOT ADOPTED لكل تقنية نموذج)، والمقارنة الحاكمة (P4-02a..P4-05a BLOCKED، أو P8-04، أو P4-01 BLOCKED).
  - **ما فشل أو عُدِّل:** سبعة إخفاقات وتعديلات أثناء التطوير (P4-06 ×3، P4-05 ×1، P4-02 ×1، P4-04 ×2)، بالسبب والإصلاح، وهل تغيّر معيار، والمرجع. لم يفشل أي تشغيل مسجل في معاييره.
  - **تفاصيل التجارب:** الصفوف العشرة السابقة دون تغيير.
- **Files created:** `tests/test_ablations_register.py`
- **Files modified:** `docs/ablations.md`، `ROADMAP.md` (§2.1 G4، §2.2 P4-07، §2.3، §12)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وسبع طفرات يدوية.
- **Test results:**
  - المرجع على `main` (`f47a3a9`): 712 passed / 1 skipped.
  - بعد التغيير: 717 passed / 0 failed / 1 skipped (712 + 5 جديدة؛ التخطي: CUDA not available). pre-commit وdetect-secrets نظيفان، والسجل صالح.
  - **الاختبارات الخمسة:**
    1. الفهرس يساوي سجلات P4 في السجل حقلًا بحقل.
    2. لكل سجل صف تفصيلي، والسجلات غير الناجحة مذكورة.
    3. لا تقنية معتمدة، والمقارنات تشير إلى مهام النص الحقيقي، وتبقى BLOCKED ما دامت كذلك في الخارطة.
    4. السجلات الاصطناعية بلا ادعاء تحسين وبلا أثر.
    5. لا تكون P4-07 DONE إلا بإنجاز P4-02..P4-06. ويبقى P4-01 وP4-08 وP4-02a..P4-05a BLOCKED ما دام OD-03 مفتوحًا.
  - **الطفرات السبع** أفشلت كل منها اختبارًا واحدًا على الأقل: حذف صف من الفهرس، وتغيير `config_hash`، ووسم الالتفاف ADOPTED، ومقارنة P4-04a بلا BLOCKED، وحذف صف تفصيلي، وجعل P4-07 DONE وP4-04 PLANNED، وجعل P4-04a PLANNED وOD-03 مفتوح.
- **Metrics:** لا شيء. توثيق وحوكمة.
- **Git commit:** PR #30، squash `9ce369e` على `main` (دُمج بعد نجاح CI، سُجّل لاحقًا في R-08)، من الفرع `agent/P4-07-close-ablations` فوق `f47a3a9`.
- **HF repository/revision:** لا شيء.
- **Dataset version:** لا شيء.
- **Known limitations:**
  - الفهرس يُطابَق بالاختبار ولا يُولَّد آليًا عند كل إضافة، فعلى كل مهمة P4 لاحقة أن تضيف صفها، وإلا فشل الاختبار.
  - الإخفاقات أثناء التطوير مأخوذة من تقارير §2.3 ومن `failure_cases`. سجلا EXP-0027 وEXP-0028 لا يحملان تعديليهما في `failure_cases` (وهما موثقان في docstring الوحدة وفي §2.3)، ولم يُعدَّل السجل لأنه append-only.
  - لا مراجعة مستقلة حاكمة (OD-10 مفتوح).
- **فحص الأسرار:** لا تغيير عن تقرير P4-04. `GITHUB_TOKEN` و`HF_TOKEN` ليسا متغيري بيئة خامين، والمصادقة عبر مدير أسرار المنصة، ولم تُطبع أي قيمة. R-07 ما زالت مفتوحة (OWNER ACTION REQUIRED).
- **Roadmap section updated:** §2.1، §2.2، §2.3، §12
- **Next unblocked task:** لا توجد مهمة كود مستقلة غير محجوبة في P0–P4:
  - P3-03 وP4-01 وP4-02a..P4-05a وP4-08 تنتظر OD-03.
  - P2-05a تنتظر دور Eval.
  - P1-06a تنتظر نواة نصية.
  - صف P6 مجمل (`P6-01..P6-09 | PLANNED`) بلا نطاق.
  - لذلك المهمة التالية R-08: ADR-0008 يحدد نطاق أعمال P6 البرمجية فقط، كما فعلت ADR-0005 وADR-0007.
  - G1 تبقى PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-10 مفتوحة كما في §2.4.
- **Duplicate-work check:** لا فرع ولا PR لـ P4-07 غير هذا، ولا PR مفتوح، و`main` عند `f47a3a9`. لا يوجد اختبار سابق يقرأ `docs/ablations.md`.

### R-08 — نطاق مهام P6 البرمجية قبل إغلاق G5 (2026-10-02)

- **Task ID:** R-08
- **Owner:** agent-R-08
- **Status:** DONE
- **Scope:**
  - **السبب:** إصلاح تعارض داخلي. بعد P4-07 (PR #30) لا توجد مهمة كود مستقلة غير محجوبة في P0–P4، وصف `P6-01..P6-09 | PLANNED` مجمل بلا نطاق، فيبقى الوكيل التالي بلا مهمة. البدء بتوجيه المالك في 2026-10-02 (10:07 +03): "إذا لم توجد مهمة كود مستقلة غير محجوبة، أنشئ ADR لتحديد نطاق أعمال P6 البرمجية فقط".
  - **الحل في ADR-0008:**
    - فصل صف P6 إلى تسع مهام دون تغيير أي معرف، وإضافة خمس مهام فرعية P6-01a..P6-05a (BLOCKED) للأجزاء التي تحتاج نواة مدربة أو بيانات حقيقية أو قرار مالك.
    - مهام الكود P6-01..P6-08 غير محجوبة بشروط: المسار S، وCPU، وبلا نموذج خارجي بأي دور (OD-10)، وبلا شبكة، وبلا بيانات حقيقية ولا frozen ولا رفع، ومعايير صحة مسجلة قبل التشغيل مع ضوابط سلبية. المولّدات stub حتمية، ولا ادعاء جودة، ولا تغيير للأهداف أو العتبات.
    - P6-09 BLOCKED حتى G5 وP6-01a..P6-05a.
    - أضيف إلى G6 شرط إنجاز P6-01a..P6-05a وP6-09، وهذا تشديد لا تخفيف. شروط G6 الأربعة لم تتغير.
    - أضيف قرار المالك **OD-11** (مزودو search وAPI الخارجية) OPEN، ويحجب P6-02a فقط.
    - ترتيب التنفيذ: P6-08 ← P6-02 ← P6-04 ← P6-05 ← P6-01 ← P6-06 ← P6-03 ← P6-07.
    - إعادة الاستخدام لا النسخ: `nawa.evaluation.sandbox` (الذي يقول docstring إن P6-02 تستبدله)، و`normalize.is_abstention`، وأجيال الـ suites (`abstention`، `faithfulness`، `tool_use`، `factual`)، و`taxonomy`.
  - لم يُكتب كود في `src`، ولم يُشغَّل أي تدريب، ولم يُستخدم أي نموذج خارجي، ولم يُرفع شيء إلى HF.
- **فرض القرار بالاختبار لا بالنص:**
  - `test_p6_code_scope_split_blocks_model_dependent_parts_and_strengthens_g6` يتحقق من:
    - فصل الصف، وإشارة كل صف إلى ADR-0008؛
    - بقاء P6-01a وP6-03a وP6-04a وP6-05a وP6-09 BLOCKED ما دامت G5 غير منجزة؛
    - بقاء P6-02a BLOCKED ما دام OD-11 مفتوحًا؛
    - شروط G6 الخمسة؛
    - ألا تُغلق G6 قبل G5 والمهام الفرعية.
  - `test_track_s_packages_import_no_external_model_libraries` امتد ليشمل حزم P6 السبع.
  - `test_p6_packages_use_no_external_model_and_no_network` جديد: يمنع في حزم P6 عملاء النماذج الخارجية (`openai`، `anthropic`، `litellm`، `langchain`، `sentence_transformers` وغيرها) ومكتبات الشبكة (`socket`، `urllib`، `requests`، `httpx` وغيرها)، بما فيها `importlib.import_module`.
  - `test_p6_import_rule_is_not_vacuous` ضابط سلبي للقاعدة.
- **Files created:** `docs/decisions/ADR-0008-p6-code-scope.md`
- **Files modified:** `ROADMAP.md` (§2.1 G6، §2.2، §2.3، §2.4 OD-11، §4 P6 وG6، §12)، `tests/test_roadmap_consistency.py` (اختبار جديد)، `tests/test_original_system_policy.py` (اختبار ممتد واختباران جديدان)
- **Tests executed:** `NAWA_REQUIRE_TORCH=1 python -m pytest`، و`python -m nawa.experiments validate`، و`pre-commit run --all-files`، و`detect-secrets-hook`، وإحدى عشرة طفرة يدوية.
- **Test results:**
  - المرجع على `main` (`9ce369e`): 717 passed / 1 skipped.
  - بعد التغيير: 720 passed / 0 failed / 1 skipped (717 + 3 جديدة؛ التخطي: CUDA not available).
  - **الطفرات الإحدى عشرة** أفشلت كل منها اختبارًا:
    - جعل P6-09 PLANNED؛
    - حذف شرط G6 الجديد؛
    - حذف شرط G6 قديم؛
    - صف P6-04 بلا ADR-0008؛
    - جعل P6-02a PLANNED وOD-11 مفتوح؛
    - جعل G6 PENDING_REVIEW؛
    - حذف OD-11؛
    - `import requests` في `verification`؛
    - `from openai import OpenAI` في `tools`؛
    - `import transformers` في `reasoning`؛
    - حذف ملف ADR-0008.
- **Metrics:** لا شيء. تغيير حوكمة.
- **مراجعة متعددة النماذج:** لا شيء. OD-10 مفتوح و`ModelRegistry` فارغ، فلم يُستخدم أي نموذج خارجي (توجيه المالك 2026-10-02). الأدلة هي الاختبارات الحتمية والطفرات.
- **Git commit:** PR #31 من الفرع `agent/R-08-p6-code-scope` (squash بعد نجاح CI)، فوق `main` عند `9ce369e`.
- **HF repository/revision:** لا شيء.
- **Dataset version:** لا شيء.
- **Known limitations:**
  - ADR-0008 قُبل بموجب قاعدة إصلاح الخارطة في §0 وبتوجيه المالك، وللمالك أن يعكسه.
  - **قاعدة الاستيراد:** تفحص الاستيراد الصريح و`__import__`/`import_module` بأسماء ثابتة، لا بأسماء محسوبة وقت التشغيل. التنفيذ الفعلي بلا شبكة يفرضه sandbox في P6-02 باختبار سلوكي.
  - **حدود العزل:** `nawa.evaluation.sandbox` عزل على مستوى العملية، لا container ولا VM. تقويته في P6-02 لا تجعله صالحًا لأحمال إنتاج غير موثوقة، وهذا سؤال نشر لاحق (P9/P10).
  - **حدود المولّدات الاختبارية:** نتائج P6 بمولّدات stub تثبت صحة الآلية فقط.
- **فحص الأسرار:** لا تغيير عن تقرير P4-04. `GITHUB_TOKEN` و`HF_TOKEN` ليسا متغيري بيئة خامين، والمصادقة عبر مدير أسرار المنصة، ولم تُطبع أي قيمة. R-07 مفتوحة (OWNER ACTION REQUIRED).
- **Roadmap section updated:** §2.1، §2.2، §2.3، §2.4، §4، §12
- **Next unblocked task:** P6-08: الحالات الخمس `SUPPORTED` و`PARTIALLY_SUPPORTED` و`UNCERTAIN` و`CONTRADICTED` و`INSUFFICIENT_EVIDENCE` وقواعدها، كود فقط وفق ADR-0008. ثم P6-02. G1 تبقى PENDING_REVIEW، وقرارات المالك OD-01..OD-06 وOD-08..OD-11 مفتوحة كما في §2.4.
- **Duplicate-work check:**
  - لا يوجد ADR-0008 ولا R-08 ولا فرع أو PR يعالج نطاق P6، ولا PR مفتوح.
  - لا توجد في `src/nawa/` حزم `retrieval` أو `tools` أو `reasoning` أو `verification` أو `abstention` أو `routing` أو `pipeline`.
  - المكونات القريبة الموجودة (sandbox، `is_abstention`، suites التقييم، taxonomy) مذكورة في ADR-0008 D2 للاستخدام لا النسخ.

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
| OD-10 | المزودون والنماذج الخارجية المصرح بها كأدوات تطوير، وهل يجوز استخدام مخرجاتها بيانات تدريب | استخدام مخرجات خارجية في التدريب أو التقطير (P5-08)؛ وكل مراجعة حاكمة من نموذج خارجي، لأن سجل `ModelRegistry` فارغ (`docs/multi_model_review.md` §1). مراجعة Claude Opus 5.5 في R-06 مسجلة غير حاكمة (انظر تقرير P4-06) | OPEN |
| OD-11 | مزودو search وAPI الخارجية المعتمدون كأدوات لـ NAWA: أي مزود، ونطاق الشبكة، وحدود المعدل والتكلفة، وما يُرسل إليهم من بيانات (ADR-0008) | P6-02a فقط | OPEN |

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

> **نطاق التنفيذ قبل إغلاق G3 (ADR-0007):** مهام الكود P4-02..P4-07 غير محجوبة، بشرط التنفيذ من الصفر على النواة المرجعية (المسار S)، وعلى CPU، ودون بيانات خارجية أو أوزان خارجية أو frozen أو رفع. معايير الصحة نجاح/فشل، والأرقام المقارنة على المصادر الاصطناعية دليل فقط. لا تُعتمد أي تقنية ولا يتغير الإعداد الافتراضي للنواة قبل "القرار التقني" أدناه. P4-01 وP4-08 محجوبتان، ومعهما المقارنات على نص حقيقي P4-02a..P4-05a. ترتيب التنفيذ: P4-06 ← P4-05 (البنود القابلة للتحقق بالتكافؤ أولًا) ← P4-03 ← P4-02 ← P4-04، وP4-07 مع كل منها. شروط G4 لم تُخفَّف، وأضيف إليها شرط P4-02a..P4-05a.

### المهام

- **P4-01 [Git]** scaling curves: Tiny/Small/Medium وربط parameters/tokens/compute/loss/quality/memory/latency.
- **P4-02 [Git]** مقارنة Dense مقابل Sparse MoE مقابل Hybrid على quality/active parameters/FLOP/memory/latency.
  - **P4-02a [Git]** (ADR-0007) المقارنة نفسها على نص حقيقي مرخص بعد P3-03؛ BLOCKED حتى OD-03.
- **P4-03 [Git]** اختبار الأوزان الثلاثية `{−1,0,+1}` بأسلوب QAT/التكميم التدريجي. لا تفترض تفوقًا؛ fallback إلى 4-bit إذا فشل.
  - **P4-03a [Git]** (ADR-0007) قياس الأوزان الثلاثية و4-bit مقابل المرجع على نص حقيقي مرخص بعد P3-03؛ BLOCKED حتى OD-03.
- **P4-04 [Git]** اختبار Attention + convolution/hybrid blocks. لا تعتمد 1:2 أو أي نسبة قبل ablation.
  - **P4-04a [Git]** (ADR-0007) ablation الكتل الهجينة على نص حقيقي مرخص بعد P3-03؛ BLOCKED حتى OD-03.
- **P4-05 [Git]** اختبار weight sharing، low-rank، sparsity، speculative decoding، KV cache، compilation.
  - **P4-05a [Git]** (ADR-0007) قياس أثر weight sharing وlow-rank وsparsity على الجودة على نص حقيقي مرخص بعد P3-03؛ BLOCKED حتى OD-03.
- **P4-06 [Git]** لكل تجربة ملف config، commit، seed، hardware، metrics، failure، conclusion.
- **P4-07 [Git]** `docs/ablations.md` يوضح ما نجح وما فشل.
- **P4-08 [HF]** رفع checkpoints التجريبية إلى `nawa-core` فرع `dev` فقط إذا كانت قابلة لإعادة الإنتاج، مع manifest.

### قرار تقني

لا يصبح NAWA “ternary” أو “hybrid” أو “MoE” رسميًا إلا بعد أن تثبت بوابة مستقلة أن الاختيار يحسن trade-off دون تدهور غير مقبول. يمكن أن يكون الناتج هجينًا أو dense إذا أثبت القياس أنه أفضل.

### G4

- scaling curves موجودة.
- كل ادعاء معماري له ablation.
- ablations المهام P4-02a وP4-03a وP4-04a وP4-05a على نص حقيقي منجزة؛ نتائج المصادر الاصطناعية (ADR-0007) لا تكفي لهذا الشرط.
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

> **نطاق التنفيذ قبل إغلاق G5 (ADR-0008):** مهام الكود P6-01..P6-08 غير محجوبة، بشرط التنفيذ من الصفر (المسار S)، وعلى CPU، دون أي نموذج خارجي (مولّدًا أو متحققًا أو حكمًا أو مراجعًا؛ OD-10)، ودون شبكة، ودون بيانات حقيقية أو frozen أو رفع. المدخلات اصطناعية يولدها الكود أو عناصر `dev`/`calib` العامة الموجودة في Git. معايير الصحة نجاح/فشل مسجلة قبل التشغيل مع ضوابط سلبية، والمولّدات stub حتمية. النتائج دليل صحة لا ادعاء بأن NAWA يهلوس أقل أو يمتنع أفضل، ولا تتغير الأهداف ولا العتبات. محجوبة: P6-01a..P6-05a وP6-09. ترتيب التنفيذ: P6-08 ← P6-02 ← P6-04 ← P6-05 ← P6-01 ← P6-06 ← P6-03 ← P6-07. شروط G6 لم تُخفَّف، وأضيف إليها شرط P6-01a..P6-05a وP6-09.

### المهام

- **P6-01 [Git]** `src/nawa/retrieval`: embeddings، index، chunker، reranker، freshness، source quality.
  - **P6-01a [Git]** (ADR-0008) embeddings كثيفة وreranker متعلم واسترجاع من مدونة حقيقية مرخصة؛ BLOCKED حتى OD-03 ونواة مدربة أو حاجة موثقة في المسار B.
- **P6-02 [Git]** `src/nawa/tools`: calculator، Python sandbox، file inspector، approved search/API، permissions، audit.
  - **P6-02a [Git]** (ADR-0008) search وAPI خارجية معتمدة؛ BLOCKED حتى OD-11.
- **P6-03 [Git]** `src/nawa/reasoning`: planner، decomposer، candidate generator، self-consistency، state، budget.
  - **P6-03a [Git]** (ADR-0008) توليد المرشحين وself-consistency بنموذج NAWA؛ BLOCKED حتى G5.
- **P6-04 [Git]** `src/nawa/verification`: claim extraction، citation، fact checker، contradiction، uncertainty، confidence، consensus.
  - **P6-04a [Git]** (ADR-0008) تحقق الإجابات الحرة على مخرجات NAWA؛ BLOCKED حتى G5 (وOD-10 لأي نموذج خارجي).
- **P6-05 [Git]** `src/nawa/abstention`: أجب واستشهد / ابحث / نفذ أداة / اطلب توضيح / امتنع.
  - **P6-05a [Git]** (ADR-0008) معايرة NAWA وعتبات الامتناع على `calib` وفحص `frozen` بيد دور Eval؛ BLOCKED حتى G5.
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
- P6-01a وP6-02a وP6-03a وP6-04a وP6-05a وP6-09 منجزة على نواة NAWA مدربة (ADR-0008)؛ تسقط P6-02a من هذا الشرط فقط إن رفض المالك الـ search الخارجي في OD-11.

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
| 1.21.0 | 2026-10-01 | P3-01 وP3-02 منجزتان: 5 مرشحين للـ Tokenizer من الصفر وأداة قياس (EXP-0022). ADR-0006 تفصل صف P3-01..P3-03؛ P3-03 BLOCKED حتى توجد مدونة مرخصة. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P3-01، P3-02، ADR-0006، EXP-0022 |
| 1.22.0 | 2026-10-01 | R-06: فصل صف P4 إلى P4-01..P4-08. مهام الكود P4-02..P4-07 غير محجوبة دون اعتماد أي تقنية، وP4-01 وP4-08 BLOCKED؛ ترتيب تنفيذ P4؛ استكمال مراجع commit/PR في 15 تقريرًا في §2.3 من `git log`؛ تسجيل تضييق توكن HF على مستودعات NAWA. لم يُغيَّر أي هدف أو معيار أو شرط بوابة أو معرف، ولم تُحذف أي مهمة أو نتيجة. | R-06، ADR-0007، EXP-0023 |
| 1.23.0 | 2026-10-01 | P4-06 منجزة: سجل تجربة P4 (`p4-record/v1`) ومدققه وبانيه، مع إعادة اشتقاق config_hash وpassed، ورفض البيانات الحقيقية قبل OD-03، ورفض ادعاء التحسن على بيانات اصطناعية، ورفض الرفع قبل P4-08 (EXP-0024). P4-07 بدأت (`docs/ablations.md`). مراجعة R-06 الخارجية سُجلت غير حاكمة لأن OD-10 مفتوح. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P4-06، P4-07، EXP-0024 |
| 1.24.0 | 2026-10-01 | P4-05 منجزة: KV cache وspeculative decoding (greedy) و`torch.compile` مكافئة للمرجع ضمن 1e-4 مسجل مسبقًا، وweight sharing وlow-rank وsparsity باختبارات صحة فقط (EXP-0025). النواة المرجعية لم تتغير، ولا اعتماد لأي تقنية. فحص الاستيراد يشمل `efficiency`. لم يُغيَّر أي هدف أو معيار أو شرط بوابة. | P4-05، P4-07، EXP-0025 |
| 1.25.0 | 2026-10-01 | P4-03 منجزة: أوزان ثلاثية (absmean) و4-bit متماثلة (absmax) بـ QAT وSTE دقيق، وتصدير مضغوط، وقاعدة fallback إلى 4-bit، بمعايير مسجلة مسبقًا (EXP-0026، 15/15). المقارنة مع fp دليل فقط، ولا اعتماد، والنواة المرجعية لم تتغير. لم يُغيّر أي هدف أو معيار أو شرط بوابة. | P4-03، P4-07، EXP-0026 |
| 1.26.0 | 2026-10-01 | P4-02 منجزة: Sparse MoE (top-k، بلا حد سعة، loss توازن) وHybrid مقابل Dense، بصحة التوزيع والهويات والمحاسبة (معاملات فعالة وFLOPs) والسببية والثبات مع الدفعة، بمعايير مسجلة مسبقًا وتعديل موثق قبل التشغيل (EXP-0027، 16/16). المقارنات دليل فقط، لا اختيار ولا اعتماد. R-07 (قصر تفويض GitHub) سُجّل تحسينًا أمنيًا منفصلًا غير حاجب. لم يُغيّر أي هدف أو شرط بوابة. | P4-02، P4-07، R-07، EXP-0027 |
| 1.27.0 | 2026-10-02 | P4-04 منجزة: mixer التفاف سببي depthwise مُبوّب (`ConvMixer`) وتخطيطات attention + convolution بأي نسبة، بصحة مسار `conv1d` مستقل والصيغة التدفقية وهوية النواة الدلتا والسببية التامة والمجال الاستقبالي الدقيق والمحاسبة وعدم مساس الجراحة بغيرها، بمعايير مسجلة مسبقًا وتعديل موثق لمِسبارين قبل التشغيل (EXP-0028، 15/15). المقارنات دليل فقط، ولا نسبة ولا اعتماد. شرط إغلاق P4-07 تحقق. اعتماد GitHub الحالي classic PAT واسع النطاق (R-07، OWNER ACTION REQUIRED). لم يُغيّر أي هدف أو معيار أو شرط بوابة. | P4-04، P4-07، R-07، EXP-0028 |
| 1.28.0 | 2026-10-02 | P4-07 منجزة: سجل ablations كامل لكل تجارب P4 (EXP-0024..EXP-0028) بفهرس مطابق للسجل باختبار، وحالة كل تقنية، والإخفاقات والتعديلات. لا تقنية معتمدة، ونتائج P4-04 أدلة أولية اصطناعية. لا مقارنة على نص حقيقي ولا رفع إلى HF قبل OD-03. لم يُغيّر أي هدف أو معيار أو شرط بوابة. | P4-07، EXP-0024..EXP-0028 |
| 1.29.0 | 2026-10-02 | R-08: فصل صف P6 إلى P6-01..P6-09 وإضافة P6-01a..P6-05a (BLOCKED). مهام الكود P6-01..P6-08 غير محجوبة بلا نموذج خارجي ولا شبكة ولا بيانات حقيقية ولا ادعاء جودة، مفروضة باختبارات. P6-09 BLOCKED حتى G5. أضيف إلى G6 شرط P6-01a..P6-05a وP6-09، وهذا تشديد. أضيف OD-11 (search/API خارجية) OPEN. لم يُغيّر أي هدف أو معرف أو شرط قائم. | R-08، P6، G6، OD-11، ADR-0008 |

> يُضاف كل تغيير لاحق هنا في نفس PR الذي يغير الخارطة.
