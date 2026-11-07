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


**Важно:** `index.html`, `m/`, `ref/`, `pages/`, `api/` генерируются целиком — руками их не правят. Ручные страницы (глоссарий, фейлы и т.д.) живут в `content/pages/*.html`.

Строка в Changelog — **`PROJECT-DIRECTIVES.md`**.
