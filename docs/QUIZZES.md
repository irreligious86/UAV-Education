# Quizzes

One bank per published module: `content/quiz/<module-id>.json`, at least the validator's minimum
number of questions, pass mark 80 %. The widget (`assets/uav-quiz.js`) shuffles option order on every
render, explains every answer and stores the best attempt in the progress store.

```json
{ "module": "ap-ekf", "pass": 80, "questions": [
  { "q": "EK3_SRC1_YAW = 8 означает…",
    "options": ["Курс по компасу", "Курс по GPS-скорости (GSF)", "Курс не оценивается", "Курс от внешней навигации"],
    "answer": 1,
    "explain": "Работает только в движении — на земле курса нет." },
  { "q": "Фрагмент XKF4 во время рывков позиции. Что происходит?",
    "kind": "apply",
    "fragment": "XKF4  C=0  SV=1.34  SP=1.62  SH=0.31  SM=0.22",
    "options": ["…"], "answer": 0, "explain": "…" } ] }
```

## Application questions (`kind: "apply"`)

"Here is a log fragment / config / frame — find the fault." The `fragment` (≤ 1500 characters) is shown
preformatted via `textContent`, so it can never inject markup. Use real field and parameter names, checked
against the firmware source; the fault must be decidable from the fragment alone.

## Writing options that measure knowledge, not test-taking

Enforced by `scripts/validate_content.py`:
- 3+ options, no duplicates, `answer` in range, an explanation for every question.
- **The correct option may be the unique longest one in at most 34 % of a bank's questions.**
  Before this rule the bank had the correct answer as the longest option in 79 % of questions — "always
  pick the longest" would have passed most quizzes. Now that strategy scores ~15 %, i.e. below guessing.

Not enforced, but checked in review:
- Distractors are as specific as the correct option and plausibly wrong (a real misconception, a
  neighbouring parameter value, a correct fact about something else) — not jokes.
- No two distractors say the same thing in different words.
- Put the justification in `explain`, not in the correct option ("X, because Y" gives the answer away).
