# UAV Student

| Что | Где |
|-----|-----|
| **Сайт** | `index.html` + `style.css` |
| **Полное ТЗ и директивы** | `PROJECT-DIRECTIVES.md` |
| **Черновики статей (имя файла = id статьи)** | `content/` — см. `content/README.md` |
| **Манифест навигации и статей** | `data/content-manifest.json` |
| **Сборка контента** | `python scripts/publish.py` (валидация + TOC + HTML в `index.html` по маркерам `AUTO:*`) |
| **Отдельно** | `scripts/validate_content.py`, `scripts/new_article.py` |
| **Быстрый запуск** | `publish.bat` (Windows) / `publish.sh` (Linux) — проверка + сборка; commit/push вручную |
| **CI** | `.github/workflows/ci.yml` — валидация, проверка что `index.html` пересобран, проверка ссылок |
| **План развития** | `ROADMAP.md` |
| **Страница разработчика (отдельно от сайта)** | `curriculum/curriculum.html` |
| **Шаблон новой статьи** | `content/article-template.md` |
| **Программа курса (отдельно от сайта)** | `curriculum/` |
| **Архив вспомогательных файлов** | `archive/` — см. `archive/README.md` |

Вспомогательные указатели `*.md`, `references.json` и сырые ТЗ вынесены в **`archive/`**, чтобы не засорять корень и контекст ИИ. Резерв: **`archive/uav-student-supplementary-backup.zip`**.

## Статусы статей

| status | Что видно на сайте |
|---|---|
| `published` | статья целиком; validator требует реальные источники и отсутствие заглушек |
| `planned` | слот в оглавлении с пометкой «скоро» и карточка «в разработке» |
| `draft` | скрыта (видна только с `--include-drafts`) |

## License

This project is licensed under the CC BY-NC-SA 4.0 License.

You are free to use and modify the content for non-commercial purposes with proper attribution.

Commercial use is prohibited.
