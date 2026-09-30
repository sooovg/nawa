# Contributing to NAWA

التفاصيل الملزمة في `AGENTS.md`. هذا الملف ملخص عملي لها، وليس بديلًا عنها.

## قبل أي عمل

1. اقرأ `AGENTS.md` ثم `ROADMAP.md` كاملين.
2. ابحث في `ROADMAP.md` §2.2 عن Task ID أو أي مهمة متداخلة معه.
3. افحص `git log` وقائمة الفروع والـ PRs المفتوحة و`experiments/log.jsonl` و`docs/decisions/`.
4. طبّق قائمة منع التكرار (`ROADMAP.md` §8). إذا وجدت عملًا قائمًا، ابنِ عليه ولا تنشئ نسخة موازية.

## دورة المهمة

```bash
git pull --ff-only
git switch -c agent/<TASK-ID>-<slug>
make setup      # مرة واحدة
# ... أصغر تغيير قابل للاختبار ...
make test
```

ثم:

- حدّث `ROADMAP.md` (الحالة، المالك، المخرج، الاختبارات، الـ commit/PR) في **نفس الـ PR**.
- سجّل أي تجربة في `experiments/log.jsonl`، وأي قرار في `docs/decisions/ADR-<n>-<slug>.md`.
- افتح PR عنوانه يبدأ بـ Task ID، مثل `P0-07: add compute budget config`.
- ألحق بوصف الـ PR "Task completion report" (القالب أدناه).
- لا تدمج PR نفسك إذا كنت مالك تدريب أو تقييم متعارض.

## رسائل الـ commit

صيغة Conventional Commits، مثل `feat:` و`fix:` و`docs:` و`chore:` و`test:`، ويُذكر Task ID عند وجوده.

## ممنوع

- رفع أوزان أو checkpoints أو بيانات كبيرة إلى Git (الحد 5MB، ويفحصه CI).
- رفع أسرار.
- تعديل `frozen` أو `eval/targets.yaml` دون ADR ودور Eval.
- حذف تجارب فاشلة.
- وضع `DONE` لمهمة لم تُقَس.

## Task completion report

```markdown
## Task completion report

- Task ID:
- Owner:
- Status:
- Scope:
- Files created:
- Files modified:
- Tests executed:
- Test results:
- Metrics:
- Git commit:
- HF repository/revision:
- Dataset version:
- Known limitations:
- Roadmap section updated:
- Next unblocked task:
- Duplicate-work check:
```
