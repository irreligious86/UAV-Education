# Черновики контента

Имена файлов = **`id` статьи** в `index.html` и в **`data/content-manifest.json`** (см. `PROJECT-DIRECTIVES.md`, §6).

**Шаблон нового модуля:** **`article-template.md`** в этой папке.

Подкаталоги: `betaflight/`, `inav/`, `ardupilot/`, `px4/`, `companion/`, `tools/`.  
Обзоры secondary (Oscar Liang, Bardwell и т.д.) — в теле статьи в секции **`notes`** или в HTML как `.article-notes` (не копировать чужие тексты).

## Пайплайн (этап 12)

1. **Новая статья:** `python scripts/new_article.py <section> <id> "Заголовок" L2` — создаёт `.md` и строку в манифесте со статусом `draft` (по умолчанию). Когда текст готов — поставить `published` в манифесте и front matter.
2. Заполнить **`content/<stack>/<id>.md`**: `summary`, `theory`, `practice`, `diagnostics`, `references`, опционально `checklist`, `notes`, …
3. Слот в программе без текста: `--status planned` (видно на сайте как «скоро»).
4. **Публикация:** `publish.bat` / `publish.sh` или `python scripts/publish.py` — валидация, сборка всех страниц сайта, проверка ссылок.
5. **Место в курсе:** добавь модуль в нужный трек в `data/curriculum.json` (цели, prerequisites, часы). Validator не пропустит статью, не размещённую в курсе.
6. **Квиз:** `content/quiz/<id>.json` (см. формат в `assets/uav-quiz.js`); появляется на странице модуля автоматически.
7. Только проверка — `python scripts/validate_content.py`. То же самое выполняет CI на каждый push.


**Важно:** `index.html`, `m/`, `ref/`, `pages/`, `api/` генерируются целиком — руками их не правят. Ручные страницы (чек-листы, сравнение, ресурсы) живут в `content/pages/*.html`; глоссарий — `data/glossary.json`; журнал фейлов собирается из секций `## diagnostics` автоматически.

Строка в Changelog — **`PROJECT-DIRECTIVES.md`**.

## Tables

Standard GitHub-style Markdown tables are supported inside any section:

```
| Column | Column |
|---|---|
| cell | cell |
```

- A table may follow a heading or a sentence directly; a blank line is not required.
- Every row must have as many cells as the header (`validate_content.py` rejects shifted rows).
- Write a literal pipe inside a cell as `\|`.
- On a phone each row is shown as a card ("Header: value"), on a desktop as a normal table.
- `check_rendering.py` (in `publish.py` and CI) fails the build if a table, `**bold**`, a heading
  or a `{{diagram}}` tag ever shows up in a page as raw text.

## Practice depth

A published module needs at least 150 words of prose in `## practice` (code blocks excluded): expected results, numbers to record, a worked example and the lab acceptance line. `scripts/validate_content.py` enforces it.
