# Черновики контента

Имена файлов = **`id` статьи** в `index.html` и в **`data/content-manifest.json`** (см. `PROJECT-DIRECTIVES.md`, §6).

**Шаблон нового модуля:** **`article-template.md`** в этой папке.

Подкаталоги: `betaflight/`, `inav/`, `ardupilot/`, `px4/`, `companion/`, `tools/`.  
Обзоры secondary (Oscar Liang, Bardwell и т.д.) — в теле статьи в секции **`notes`** или в HTML как `.article-notes` (не копировать чужие тексты).

## Пайплайн (этап 12)

1. **Новая статья:** `python scripts/new_article.py <section> <id> "Заголовок" L2` — создаёт `.md` и строку в манифесте со статусом `draft` (по умолчанию). Когда текст готов — поставить `published` в манифесте и front matter.
2. Заполнить **`content/<stack>/<id>.md`**: `summary`, `theory`, `practice`, `diagnostics`, `references`, опционально `checklist`, `notes`, …
3. Слот в программе без текста: `--status planned` (видно на сайте как «скоро»).
4. **Публикация:** `publish.bat` / `publish.sh`, или напрямую `python scripts/publish.py` — валидация, генерация TOC и HTML статей, подстановка в **`index.html`** между комментариями `<!-- AUTO:TOC:... -->` / `<!-- AUTO:ARTICLES:... -->` / `<!-- AUTO:PROGRESS:... -->`.
5. Только проверка — `python scripts/validate_content.py`. То же самое выполняет CI на каждый push.
6. Windows: **`publish.bat`** (вызов `publish.py`).


**Важно:** блоки `orientation-guide` и таб-бар в `index.html` не трогаются; перезаписываются только участки между маркерами AUTO.

Строка в Changelog — **`PROJECT-DIRECTIVES.md`**.
