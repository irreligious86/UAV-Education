# Шаблон модуля (Markdown)

Создание черновика: `python scripts/new_article.py SECTION ID "Заголовок" L2`

Полные правила: `PROJECT-DIRECTIVES.md`. Пайплайн и таблицы: `content/README.md`. Квизы: `docs/QUIZZES.md`. Схемы: `docs/DIAGRAMS.md`.

## Front matter

```yaml
---
id: my-article-id
title: "Заголовок модуля"
level: L2
readingTime: 30 мин
firmware: ArduPilot 4.5+ · PX4 1.15+
status: published
tags:
  - тег
related:
  - other-module-id
next:
  - next-module-id
---
```

`related` и `next` — только существующие id (validator проверяет).

## Секции

Обязательные для `published`:

- `## summary` — один абзац: зачем модуль, что умеет студент после него, какая лабораторная.
- `## theory` — подразделы `###`; числа, параметры в обратных кавычках (`MNT1_TYPE`), версии прошивок.
- `## practice` — шаги `### Шаг N.`; рабочий пример с числами или кодом, который запускался; в конце — строка «Лабораторная засчитывается, когда …» с проверяемыми критериями.
- `## diagnostics` — список «Симптом → Возможная причина → Что сделать».
- `## references` — не меньше двух строк вида `- Название | URL | primary|secondary | A|B|C`, первичные источники (документация, исходники) в приоритете.

Опционально: `## checklist`, `## notes`.

## Схемы, графики, виджеты

- Схема или график: `{{diagram:<id>|Подпись, которая объясняет вывод схемы.}}` — SVG генерируется в `scripts/diagrams/` (`build_diagrams.py`, `wave2.py`, `wave3.py` для графиков).
- Интерактивный виджет: `{{widget:<id>}}` — см. `assets/widgets/`.
- Таблицы — обычный GFM; число ячеек в каждой строке равно числу колонок заголовка. Сырые таблицы, `**`, `##` или `{{…}}` в собранной странице ловит `scripts/check_rendering.py`.

## Квиз

`content/quiz/<id>.json`: 5+ вопросов (обычно 8), `answer` — индекс верного, `explain` обязателен. Верный вариант не должен быть самым длинным больше чем в трети вопросов — дистракторы той же длины и конкретики.

## Публикация

1. Модуль в треке `data/curriculum.json` (цели, prerequisites, часы, лабораторная) — без этого validator не пропустит.
2. Строка в `data/content-manifest.json` (`new_article.py` создаёт её), `status: published`.
3. `python scripts/publish.py` — схемы, валидация, сборка, проверка ссылок, отрисовки и JS.

Не править сгенерированные страницы (`m/*.html`, `index.html`, `ref/`, `api/`) — перезапишутся при сборке.
