# Architecture

UAV Student is a **modular monolith on static hosting**: one build, one deploy (GitHub Pages),
but strict internal boundaries so that the data layer can move to our own server without
touching pages. This document describes the layers, the contracts between them, and the
migration path.

## Layers

```
content/           authored data: Markdown modules, quiz banks (JSON), hand-written pages
data/              structure: content-manifest.json (articles by stack), curriculum.json
                   (tracks, prerequisites, labs, capstones), glossary.json
scripts/           build: validate_content.py -> build_site.py -> check_links.py
lib/ground-control-ui/   design system, git submodule pinned to a release tag (never main)
assets/            site-specific CSS + JS: layout, progress store, quiz, search
--- generated (committed, served as-is) ---
index.html         course map
m/<id>.html        one page per module       cap/<id>.html   capstone pages
ref/               reference by stack        pages/          glossary, fails, checklists…
quiz/<id>.json     quiz banks (copied)       api/v1/*.json   static API
```

Rules:

1. **Nothing is edited in generated output.** `python scripts/publish.py` rebuilds everything;
   CI fails if the committed output is stale.
2. **Data files are the source of truth for structure.** Adding a module = Markdown file +
   manifest entry + curriculum placement. The validator refuses stubs, placeholders,
   broken prerequisites, orphan articles, malformed quizzes.
3. **Design system is external.** Anything reusable goes to Ground Control UI as a release;
   `assets/site.css` holds only layout specific to this site and uses `--gc-*` tokens only.
4. **Pages never touch storage directly.** All per-student state goes through `window.UAVProgress`.

## Contracts

### Static API (`api/v1/`)

| File | Shape | Future server endpoint |
|---|---|---|
| `curriculum.json` | groups → modules (id, title, level, hours, status, prerequisites, objectives, lab, url) | `GET /api/v1/curriculum` |
| `search.json` | documents (id, type, title, url, group, level, summary, headings, text, tags) | `GET /api/v1/search?q=` (server-side ranking) |
| `quiz/<id>.json` | module, pass, questions[{q, options, answer, explain}] | `GET /api/v1/quiz/<id>` — note: a server should strip `answer` and grade server-side |

These files are produced by `scripts/build_site.py` and define the JSON a server must return.
Pages read them with plain `fetch()`; the base path is `document.body.dataset.base`.

### ProgressStore (`assets/progress-store.js`)

```
getDone()               -> Promise<Set<moduleId>>
setDone(id, bool)       -> Promise<void>
getChecks(prefix)       -> Promise<Set<checkId>>     checkId = "<moduleId>:<kind>:<n>"
setCheck(id, bool)      -> Promise<void>
getQuiz(moduleId)       -> Promise<{correct,total,ts}|null>
setQuiz(moduleId, res)  -> Promise<void>
```

Today: `LocalProgressStore` (localStorage, one browser). Later: `ApiProgressStore` with the
same methods over HTTP, selected by one line at the bottom of the file. Module ids, capstone
ids (`cap-*`) and check ids are stable strings; a server stores them as-is.

## Migration to our own server (when the time comes)

1. **Keep the static site.** Host it from the same server (nginx) or keep GitHub Pages; the
   API moves, the pages don't.
2. **progress-api** (FastAPI): `GET/PUT /api/v1/progress/{student}` returning
   `{done: [...], checks: [...], quiz: {...}}` — the exact object `LocalProgressStore` keeps in
   localStorage today. Add `ApiProgressStore`, switch the one line, done.
3. **Auth**: simplest workable — magic link by e-mail, session cookie. Students are few and known.
4. **Quiz grading server-side**: serve banks without `answer`, add `POST /api/v1/quiz/{id}/attempt`.
   `<uav-quiz>` gets a second code path; the UI stays.
5. **Mentor view**: one page reading `/api/v1/progress/*` — who is where, which labs are open.
6. **Search**: optional; the static index is fine up to a few hundred modules.
7. **Offline**: a service worker precaching `lib/`, `assets/`, `api/v1/*.json` and visited pages.

Each step is independent and reversible. None requires changing content or the build.

## What is deliberately *not* here

- No framework, no bundler. The site is HTML + CSS + small scripts, same policy as Ground Control.
- No database in the repo. Student state lives in the browser until a server exists.
- No analytics. If ever added, it goes through the same API boundary, not into pages.
