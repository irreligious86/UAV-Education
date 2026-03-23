# Шаблон модуля (Markdown)

Создание черновика: `python scripts/new_article.py SECTION ID "Заголовок" L2`

Полные правила: `PROJECT-DIRECTIVES.md`.

## YAML

```yaml
---
id: my-article-id
title: "Заголовок"
level: L2
readingTime: "15 мин"
firmware: "INAV 7.0+"
status: draft
tags:
  - тег
references:
  - title: Docs
    url: https://example.com
    tier: primary | A
---
```

## Секции (для published обязательны)

- `## summary`
- `## theory`
- `## practice`
- `## diagnostics`
- `## references` — строки вида `- Название | URL | primary | A`

Опционально: `## checklist`, `## notes`.

Публикация: `status: published` в манифесте, затем `python scripts/publish.py`.

Не править статьи в index.html между маркерами AUTO:ARTICLES — перезапишется.
