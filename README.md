# UAV Student

| Что | Где |
|-----|-----|
| **Сайт (собирается)** | `index.html` (карта курса), `m/<id>.html` (модули), `ref/` (справочник), `pages/`, `api/v1/` |
| **Программа курса** | `data/curriculum.json` — треки, модули, prerequisites, цели |
| **Дизайн** | Ground Control UI — submodule `lib/ground-control-ui`, закреплён на теге; свои стили — `assets/site.css` |
| **Полное ТЗ и директивы** | `PROJECT-DIRECTIVES.md` |
| **Черновики статей (имя файла = id статьи)** | `content/` — см. `content/README.md` |
| **Манифест навигации и статей** | `data/content-manifest.json` |
| **Сборка** | `python scripts/publish.py` = валидация + `build_site.py` + `check_links.py` |
| **Отдельно** | `scripts/validate_content.py`, `scripts/new_article.py` |
| **Быстрый запуск** | `publish.bat` (Windows) / `publish.sh` (Linux) — проверка + сборка; commit/push вручную |
| **CI** | `.github/workflows/ci.yml` — валидация, сайт пересобран и закоммичен, ссылки, GC закреплён на теге |
| **Квизы** | `content/quiz/<id>.json` — 5+ вопросов, `answer` = индекс верного, `explain` обязателен; validator проверяет |
| **План развития** | `ROADMAP.md` |
| **Страница разработчика (отдельно от сайта)** | `curriculum/curriculum.html` |
| **Шаблон новой статьи** | `content/article-template.md` |
| **Программа курса (отдельно от сайта)** | `curriculum/` |
| **Архив вспомогательных файлов** | `archive/` — см. `archive/README.md` |

Вспомогательные указатели `*.md`, `references.json` и сырые ТЗ вынесены в **`archive/`**, чтобы не засорять корень и контекст ИИ. Резерв: **`archive/uav-student-supplementary-backup.zip`**.

## Клонирование

Дизайн-система подключена как submodule:

```bash
git clone --recurse-submodules https://github.com/irreligious86/UAV-Education
# уже склонировано без него:
git submodule update --init
```

Обновить Ground Control: `cd lib/ground-control-ui && git fetch --tags && git checkout vX.Y.Z`, затем пересобрать и закоммитить.

## Статусы статей

| status | Что видно на сайте |
|---|---|
| `published` | статья целиком; validator требует реальные источники и отсутствие заглушек |
| `planned` | в карте курса с пометкой «скоро»; страница модуля показывает цели и «в разработке» |
| `draft` | не попадает на сайт |

## License

This project is licensed under the CC BY-NC-SA 4.0 License.

You are free to use and modify the content for non-commercial purposes with proper attribution.

Commercial use is prohibited.
