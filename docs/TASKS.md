# Numeric tasks

Calculation modules carry tasks with a numeric answer that the site checks itself. The numbers
in a statement change on every load (several precomputed variants), so a student cannot copy an
answer from a friend — only the method transfers.

## Authoring

`content/tasks/<module-id>.json`:

```json
{ "module": "rf-link-budget", "tasks": [
  { "id": "fspl", "title": "Потери в свободном пространстве",
    "statement": "Дистанция **{d} км**, частота **{f} МГц**. Найдите FSPL (дБ).",
    "params": { "d": { "min": 0.5, "max": 30, "step": 0.5 }, "f": [433, 868, 915, 2400, 5800] },
    "answer": "20*math.log10(d)+20*math.log10(f)+32.44",
    "unit": "дБ", "tol": 0.01,
    "solution": "FSPL = 20·lg(d_км) + 20·lg(f_МГц) + 32.44." } ] }
```

- `params`: either a range `{min, max, step}` or an explicit list; `{name}` in the statement is
  replaced by the drawn value. Statement and solution accept the course's inline Markdown.
- `answer`: a Python expression over the parameters with `math` available; evaluated at build
  time (`scripts/build_site.py`, `build_task_variants`), never in the browser.
- `tol`: relative tolerance (default 0.03); `abs`: optional absolute tolerance floor.
- `solution`: shown after a correct answer or on "Показать решение" (a revealed variant does
  not count; the student must solve a fresh one).

The build publishes `tasks/<module>.json` with 8 deterministic variants per task (seeded by
module/task id), embeds `<uav-tasks>` on the module page, and records the task count in
`api/v1/grading.json`.

## Grading

`assets/grading.js`: a module with tasks scores quiz 30 % + tasks 30 % + lab 40 % (renormalised
when a part is absent); "Освоен" requires quiz ≥ 80 %, every task solved and every lab criterion.
Solved tasks are stored per module in the progress store (`tasks` key) and show on the module
page ("задачи 2/3") and in the transcript.

## Inventory: 40 tasks in 17 modules + a 10-task entry test (`prereq-test`, pages/prerequisites.html)

f-physics (2), f-aero-props (3), f-electricity-101 (3), f-power (2), f-motors-esc (2),
el-power-design (2), el-wiring (2), el-battery-packs (2), rf-link-budget (3), link-elrs (2),
est-kalman (3), aero-wing (2), bf-filters (1), ctl-signals (2), math-linalg-rot (3), math-ode-dyn (3), math-prob-est (3).
