# UAV Student

| Что | Где |
|-----|-----|
| **Сайт** | `index.html` + `style.css` |
| **Полное ТЗ и директивы** | `PROJECT-DIRECTIVES.md` |
| **Черновики статей (имя файла = id статьи)** | `content/` — см. `content/README.md` |
| **Манифест навигации и статей** | `data/content-manifest.json` |
| **Сборка контента** | `python scripts/publish.py` (валидация + TOC + HTML в `index.html` по маркерам `AUTO:*`) |
| **Отдельно** | `scripts/validate_content.py`, `scripts/build_content.py`, `scripts/new_article.py` |
| **Быстрый запуск (Windows)** | `publish-safe.bat` (проверка + сборка), `publish.bat` (только сборка) или `publish-git.bat` (сборка + git commit/push при наличии репозитория) |
| **Страница разработчика (отдельно от сайта)** | `curriculum/curriculum.html` |
| **Шаблон новой статьи** | `content/article-template.md` |
| **Резервная копия перед экспериментами** | `python scripts/bootstrap_from_index.py --backup` |
| **Программа курса (отдельно от сайта)** | `curriculum/` |
| **Архив вспомогательных файлов** | `archive/` — см. `archive/README.md` |

Вспомогательные указатели `*.md`, `references.json` и сырые ТЗ вынесены в **`archive/`**, чтобы не засорять корень и контекст ИИ. Резерв: **`archive/uav-student-supplementary-backup.zip`**.

## License

This project is licensed under the CC BY-NC-SA 4.0 License.

You are free to use and modify the content for non-commercial purposes with proper attribution.

Commercial use is prohibited.
