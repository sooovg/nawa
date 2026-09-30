# NAWA Architecture

> **الحالة:** مسودة مبدئية (P0-02). هذا وصف للمكونات المخطط لها، **لا وصف لنظام مكتمل**. المكون الوحيد المنفذ حتى الآن هو النواة المرجعية (P3-04، `src/nawa/model/`)، وهي مرجع داخلي للقياس لا الحجم أو المعمارية النهائية لـ NAWA.
> كل اختيار تقني (ternary، hybrid، MoE، نوع الـ tokenizer…) **فرضية** لا تُعتمد إلا بعد ablation وبوابة (`ROADMAP.md` P4 و"قرار تقني").

## المبدأ

NAWA نظام، لا ملف أوزان منفرد. تُقاس قوته بالصيغة التالية (`AGENTS.md` §1):

```text
الصحة × التحقق × حسن اختيار الأداة × الاعتراف بعدم المعرفة
──────────────────────────────────────────────────────────
الحجم × الذاكرة × الزمن × التكلفة
```

## المكونات

| المكون | الدور | المسار المخطط | مهمة الخارطة |
|---|---|---|---|
| **Core Model** | النواة اللغوية (decoder). تبدأ بـ Transformer مرجعي من الصفر. | `src/nawa/model/`, `src/nawa/core/` | P3-04، P4، P5-01..04 |
| **Tokenizer** | تقطيع مملوك يُختار بالقياس (BPE / Unigram / byte-aware / Arabic-aware). | `src/nawa/tokenizer/` | P3-01..03 |
| **Router** | تصنيف المهمة واختيار النواة أو خبير أو عدة خبراء، مع fallback وtrace. | `src/nawa/routing/` | P6-06، P7-03 |
| **Experts** | adapters أو خبراء لمجالات محددة. لكل خبير هدف وبيانات واختبارات. | `src/nawa/` + HF `nawa-adapters` | P7-01..04 |
| **Retrieval** | embeddings وindex وchunker وreranker، مع مراعاة حداثة المصادر وجودتها. | `src/nawa/retrieval/` | P6-01 |
| **Tools** | calculator وPython sandbox وفاحص ملفات وبحث/API معتمد، بصلاحيات وسجل تدقيق. | `src/nawa/tools/` | P6-02 |
| **Reasoning** | planner وdecomposer ومولّد مرشحين وself-consistency وميزانية. | `src/nawa/reasoning/` | P6-03 |
| **Verification** | استخراج الادعاءات والاستشهاد وفحص الحقائق والتناقض. مستقل عن المولّد. | `src/nawa/verification/` + HF `nawa-verifier` | P6-04، P6-08 |
| **Abstention** | قرار معاير: أجب واستشهد / ابحث / نفذ أداة / اطلب توضيحًا / امتنع. | `src/nawa/abstention/` | P6-05 |
| **Memory** | working وepisodic وsemantic وprocedural، مع الحذف وتسجيل المصدر. | `src/nawa/memory/` | P7-05..08 |
| **Evaluation** | مجموعات dev/calib/frozen، وتقارير، وتتبع lineage. | `eval/`, `src/nawa/evaluation/` | P1-02..07 |
| **Runtime** | التشغيل والضغط والتكميم والـ KV cache والتشغيل المحلي. | `src/nawa/runtime/`, `compress/` | P8 |

## Core مقابل Runtime

- **Core (Track S):** الأوزان والـ tokenizer وكود التدريب. يجب أن تكون مملوكة وقابلة لإعادة الإنتاج، ولا تدخلها أوزان خارجية.
- **Runtime/System:** كل ما حول النواة (Router وRetrieval وTools وReasoning وVerification وAbstention وMemory). يمكن تحسينه وتحديثه دون إعادة تدريب النواة.
- **المعرفة المتغيرة** تبقى في retrieval/memory القابلة للتحديث والحذف، لا في الأوزان (P7-06).

## مسار السؤال المخطط (P6-07)

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

حالات التحقق: `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNCERTAIN`, `CONTRADICTED`, `INSUFFICIENT_EVIDENCE`.

## أسئلة مفتوحة

- الحجم المستهدف للنواة: `TBD` (يتحدد من scaling curves في P4-01).
- Dense مقابل MoE مقابل Hybrid: `TBD` (P4-02).
- الأوزان الثلاثية: فرضية تُختبر في P4-03، مع fallback إلى 4-bit.
- الـ Tokenizer: `TBD` (ADR بعد P3-03).
