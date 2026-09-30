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

### B — Baseline/Practical

مسار عملي للمقارنة وتقليل المخاطر: نماذج مفتوحة، Adapters، وdistillation مسموح الترخيص. الناتج يبقى `nawa-practical-baseline` ولا يُسمى NAWA Core.

**سبب الفصل:** لا يوجد تعارض بين البحث من الصفر واستخدام baseline إذا كان لكل منهما lineage وقياس واسم وmanifest مستقل.

## قواعد تشغيل معتمدة من المالك (2026-09-30)

- **التنفيذ المتتابع:** ينفذ الوكيل دائمًا أعلى مهمة غير منجزة وغير محجوبة، دون انتظار أمر مستقل لكل مهمة.
- **قرارات المالك لا توقف المشروع كله:** القرار الجوهري غير المحدد يُسجَّل في §2.4 بوصفه `OWNER DECISION REQUIRED`، ويستمر العمل المستقل عنه.
- **إغلاق البوابات بالترتيب:** يجوز تنفيذ مهام مرحلة لا تعتمد على قرار معلّق. أما **إغلاق** بوابة فيتطلب إغلاق كل البوابات السابقة لها. ولا تبدأ مرحلة تعتمد مخرجاتها على بوابة سابقة غير مغلقة (مثل البيانات والتدريب).
- **الدمج:** يجوز للوكيل دمج الـ PR الذي فتحه بعد نجاح CI (تفويض المالك بتاريخ 2026-09-30). قاعدة استقلال الحكم (`AGENTS.md` §6) باقية: البوابة التي يغلقها قياس أجراه الوكيل نفسه تُعلَّم `PENDING_REVIEW` حتى يراجعها المالك.
- **إصلاح الخارطة:** يُصلح الوكيل التعارضات الداخلية في هذه الخارطة بشرط ألا يغير هدف المشروع ولا المسارات المعمارية، وألا يخفض أي معيار، وألا يحذف مهمة أو نتيجة، وأن يسجل كل تعديل في §12 أو في ADR.
- **مستودع GitHub العام:** وضع مؤقت موثق (ADR-0001 C1). لا تُوضع فيه أسرار ولا بيانات خاصة ولا أوزان ولا مجموعة `frozen`.

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

تُثبت الأرقام النهائية بعد baseline في `P1-06`، ويُسمح برفع الهدف فقط دون خفضه:

| الرمز | الهدف الابتدائي المقترح | ملاحظة |
|---|---|---|
| T1 | خفض الهلوسة النسبية ≥ 50% مقابل baseline نفسه | على `faithfulness` و`factual` |
| T2 | امتناع صحيح ≥ 80% في نقص الدليل مع عدم خفض الإجابات الصحيحة أكثر من 5% نسبيًا | يمنع الامتناع الدائم |
| T3 | مطابقة أو تجاوز نموذج أكبر 4–8× في المجال الأول | مهمة محددة لا كل العالم |
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
| G1 القياس وbaseline (P1) | PLANNED | — | — |
| G2 أطلس الإخفاقات ومصنع البيانات (P2) | PLANNED | — | — |
| G3 Tokenizer ونواة مرجعية (P3) | PLANNED | — | — |
| G4 دراسات الكفاءة والابتكار (P4) | PLANNED | — | — |
| G5 تدريب النواة ومسار baseline (P5) | PLANNED | — | — |
| G6 نظام الاستدلال والتحقق (P6) | PLANNED | — | — |
| G7 الخبراء والمحولات والذاكرة (P7) | PLANNED | — | — |
| G8 الضغط والكفاءة (P8) | PLANNED | — | — |
| G9 التعلم المستمر ومقاومة الانحدار (P9) | PLANNED | — | — |
| G10 الإصدار 1.0 — تعريف 100% (P10) | PLANNED | — | — |

## 2.2 سجل المهام

الحالات المسموحة: `PLANNED`, `CLAIMED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `DONE`, `REJECTED`, `SUPERSEDED`.

| Task ID | الحالة | المالك | المخرج/الدليل | آخر تحديث |
|---|---|---|---|---|
| P0-01 | IN_PROGRESS | bootstrap-agent | `PROJECT_CHARTER.md` مسودة؛ بنود `[OWNER DECISION REQUIRED]` مفتوحة | 2026-09-30 |
| P0-02 | IN_PROGRESS | bootstrap-agent | `ARCHITECTURE.md` مسودة مبدئية؛ بانتظار اعتماد المالك | 2026-09-30 |
| P0-03 | IN_PROGRESS | bootstrap-agent | `SUCCESS_CRITERIA.md` ينقل T1–T6 دون أرقام جديدة؛ التثبيت في P1-06 | 2026-09-30 |
| P0-04 | IN_PROGRESS | bootstrap-agent | `SECURITY.md` أُنشئ؛ `RISK_REGISTER.md` لم يُنشأ (ADR-0001 C6) | 2026-09-30 |
| P0-05 | DONE | bootstrap-agent | بنية المستودع، `AGENTS.md`، `.gitignore`؛ `tests/test_repository_structure.py` (30 اختبارًا ناجحًا) | 2026-09-30 |
| P0-06 | DONE | bootstrap-agent | 8 مستودعات HF خاصة وفارغة تحت `vuuuv`؛ `configs/hf_repos.yaml`؛ `tests/test_config_loading.py` (5 اختبارات ناجحة) | 2026-09-30 |
| P0-07 | BLOCKED | — | `configs/budget.yaml` يحتاج أرقام المالك (ساعات GPU، التكلفة) | 2026-09-30 |
| P0-08 | DONE | bootstrap-agent | `ROADMAP.md` وسجل الحالة و`.github/CODEOWNERS` و`ci.yml`؛ CI نجح على `d34f3f1`؛ `main` محمي (PR إلزامي، فحص `test`، منع force push والحذف، enforce_admins) | 2026-09-30 |
| R-01 | DONE | bootstrap-agent | اتساق الخارطة: ADR-0002، `tests/test_roadmap_consistency.py` | 2026-09-30 |
| P1-01..P1-08 | PLANNED | — | — | — |
| P2-01..P2-08 | PLANNED | — | — | — |
| P3-01..P3-08 | PLANNED | — | — | — |
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

## 2.4 قرارات المالك المطلوبة (OWNER DECISION REQUIRED)

| ID | القرار | يحجب | الحالة |
|---|---|---|---|
| OD-01 | المجال الأول (first domain) | P1-02 (مجموعة `domain`)، T3، اعتماد الميثاق (G0) | OPEN |
| OD-02 | ترخيص كود المشروع | P0-01، G0 | OPEN (مؤقتًا: جميع الحقوق محفوظة) |
| OD-03 | ترخيص الأوزان والبيانات المستقبلية | P0-01، P2-07 | OPEN |
| OD-04 | معنى "خاص بي" / امتلاك NAWA | P0-01، G0 | OPEN |
| OD-05 | سقف ساعات GPU والتكلفة المالية | P0-07، G0، أي عمل مدفوع أو على GPU | OPEN |
| OD-06 | عتاد الهدف لقياس سرعة T4 | تثبيت T4 في P1-06 | OPEN |
| OD-07 | ظهور مستودع GitHub (عام حاليًا) | لا شيء؛ وضع مؤقت مقبول بتعليمات المالك | ACCEPTED_TEMPORARY |
| OD-08 | مصير مستودع HF القديم `vuuuv/nawa` (عام) | لا شيء | OPEN |
| OD-09 | اعتماد الميثاق والمعمارية | G0 | OPEN |

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
- **P0-08 [Git]** إنشاء `ROADMAP.md` وسجل الحالة وCODEOWNERS.

### G0 — لا عبور قبل

- الميثاق معتمد.
- النطاق الأول محدد.
- مسارا S وB مفصولان.
- صلاحيات محدودة.
- مستودعات HF خاصة.
- CI مبدئي يعمل.

---

## P1 — القياس أولًا وbaseline

> **ترتيب التنفيذ الفعلي** (بسبب الاعتماديات، ودون تغيير المعرفات): P1-01 ← P1-02 ← P1-03 ← P1-07 ← P1-04 ← P1-05 ← P1-06 ← P1-08. سبب التقديم أن المهمة P1-07 (المشغّل والتقرير) شرط لتشغيل الـ baselines في P1-04 وP1-05.

**القاعدة:** لا تدريب كبير قبل وجود baseline واختبار مجمد.

### المهام

- **P1-01 [Git]** إنشاء `docs/failure_taxonomy.md`، ويشمل: مصدر مختلق، رقم خاطئ، حساب، API وهمية، افتراض خاطئ، معلومة قديمة، خلط كيانات، مجاراة الخطأ، فقدان سياق، prompt injection، وثقة زائدة.
- **P1-02 [Git]** بناء حزم `eval/suites/`: faithfulness، abstention، factual، reasoning_math، code، tool_use، domain، robustness، arabic، regression_general (الأسماء كما في `AGENTS.md` §10).
- **P1-03 [Git→HF]** فصل `dev/calib/frozen`، حساب `eval/FROZEN.sha256`، ورفع frozen إلى `nawa-eval` خاص. Eval role فقط يلمسه.
- **P1-04 [Git]** تشغيل عدة نماذج مفتوحة بأحجام مختلفة في مسار B، مع نموذج أكبر كمرجع مقارنة إن أمكن، وتسجيل النتائج في `eval/baselines.md`.
- **P1-05 [Git]** بناء baseline لنموذج Decoder صغير يعمل محليًا.
- **P1-06 [Git]** تثبيت T1–T6 بعد معرفة نقطة البداية، ولا تُضبط العتبات باستخدام frozen.
- **P1-07 [Git]** إنشاء `eval/run_eval.py`, `report.py`, `targets.yaml` وأمر إعادة إنتاج واحد.
- **P1-08 [Git]** تسجيل أول حالات فشل في Atlas مع إجابات متحققة.

### G1

- أرقام baseline محفوظة.
- frozen له hash ومكان خاص.
- لا تسرب بين train/eval.
- يوجد أمر يعيد التقرير.

---

## P2 — أطلس الإخفاقات ومصنع البيانات

**الهدف:** جعل كل فشل مصدرًا لتحسين واختبار، لا مجرد شكوى.

### المهام

- **P2-01 [Git]** `data_pipeline/atlas/mine.py`: تشغيل نماذج على أسئلة واسعة والتقاط الاختلافات والفشل.
- **P2-02 [Git]** `verify.py`: لا يدخل المثال التدريب قبل تحقق مستقل: حساب، تنفيذ، مصدر مرخص، أو مراجعة خبرة.
- **P2-03 [Git]** بناء توائم الامتناع: نسخة بدليل يجيب ويستشهد، ونسخة بلا دليل يمتنع ويشرح الناقص.
- **P2-04 [Git]** بناء أزواج التفضيل: جواب مؤسس مقابل جواب مهلوس.
- **P2-05 [Git]** تنظيف، PII، dedup، decontamination، provenance، license، quality score.
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

## P5 — تدريب النواة ومسار baseline

### مسار S — Core من الصفر

- **P5-01 [Git]** pretraining تدريجي: لغة عامة، معرفة عالية الجودة، reasoning، code/math، long context، corpus عربي/خاص مرخص.
- **P5-02 [Git]** كل مرحلة لها dataset revision وcheckpoint وeval مستقل.
- **P5-03 [Git]** تدرج الأحجام بدل القفز إلى نموذج ضخم.
- **P5-04 [Git]** تسجيل ساعات GPU والتكلفة ومعدل البيانات والـ loss والقدرة.

### مسار B — Practical baseline

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
5. بناء eval وbaseline.
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

> يُضاف كل تغيير لاحق هنا في نفس PR الذي يغير الخارطة.
