# Черновики контента

Имена файлов = **`id` статьи** в `index.html` и в **`data/content-manifest.json`** (см. `PROJECT-DIRECTIVES.md`, §6).

**Шаблон нового модуля:** **`article-template.md`** в этой папке.

Подкаталоги: `betaflight/`, `inav/`, `ardupilot/`, `px4/`, `companion/`, `tools/`.  
Обзоры secondary (Oscar Liang, Bardwell и т.д.) — в теле статьи в секции **`notes`** или в HTML как `.article-notes` (не копировать чужие тексты).

## Пайплайн (этап 12)

1. **Новая статья:** `python scripts/new_article.py <section> <id> "Заголовок" L2` — создаёт `.md`, строку в манифесте (`published` по умолчанию) и запускает автопубликацию.
2. Заполнить **`content/<stack>/<id>.md`**: `summary`, `theory`, `practice`, `diagnostics`, `references`, опционально `checklist`, `notes`, …
3. Для черновика используйте: `python scripts/new_article.py <section> <id> "Заголовок" L2 --status draft --no-publish`.
4. **Безопасная команда публикации (Windows):** `publish-safe.bat`. Альтернатива: `python scripts/publish.py` — валидация, генерация TOC и HTML статей, подстановка в **`index.html`** между комментариями `<!-- AUTO:TOC:... -->` / `<!-- AUTO:ARTICLES:... -->` / `<!-- AUTO:PROGRESS:... -->`.
5. Альтернатива: только проверка — `python scripts/validate_content.py`; только TOC в `build/` — `python scripts/build_content.py`.
6. Windows: **`publish.bat`** (вызов `publish.py`).

Манифест из кода: **`python scripts/build_content.py --write-manifest`**. Черновики без файлов: **`python scripts/generate_content_stubs.py`**.

**Важно:** блоки `orientation-guide` и таб-бар в `index.html` не трогаются; перезаписываются только участки между маркерами AUTO.

Строка в Changelog — **`PROJECT-DIRECTIVES.md`**.
