# Review: Odessa pilot (`ru-odessa`), 5 modules

Date: 2026-11-14. Independent review; nothing committed. Scope: `i18n/ru-odessa/content/` (`f-safety`,
`f-physics`, `bf-intro`, `bf-pid`, `inav-intro`, their 5 quiz banks, `tasks/f-physics.json`) against
`content/`. Method: sentence-level `diff` of every module, key-by-key diff of every JSON string, plus a
search for leftover singular address (pronouns, `-ешь/-ишь` verbs, sentence-initial singular imperatives).
`python3 scripts/check_i18n.py`: 0 errors before and after.

## Counts

| File | Changed sentences | Address only (ты→вы) | With colour | Fixed |
|---|---|---|---|---|
| foundation/f-safety.md | 1 | 1 | 0 | 1 |
| foundation/f-physics.md | 14 | 8 | 6 | 0 |
| betaflight/bf-intro.md | 5 | 0 | 5 | 2 |
| betaflight/bf-pid.md | 9 | 2 | 7 | 1 |
| inav/inav-intro.md | 4 | 0 | 4 | 1 |
| quiz/*.json | 1 string | 1 | 0 | 0 |
| tasks/f-physics.json | 0 | 0 | 0 | 0 |
| **Total** | **34** | **12** | **22** | **5** |

Verified: no leftover «ты» form anywhere; safety text, numbered steps, diagnostic cards, quiz options and
task statements differ from the source in grammatical person only or not at all; all numbers, parameters,
commands and structure identical. Every marked construction is in the guide's tables and used in its
attested sense; none of the banned groups (accent spelling, broken grammar, ethnic or religious items,
argot) appears. Density is within limits (at most two per paragraph, each formula once per module).
Tone: warm, ironic about hardware, never about people; no caricature.

## Fixes (before → after, why)

1. f-safety, post-flight checklist: «что меняли, как **летели**, что заметили» → «как **летел**». The
   subject of «летел» is the aircraft; only verbs whose subject is the reader take the plural. This was the
   only meaning error in the pilot.
2. bf-intro, practice, directly after the `diff all` code block: «`diff all` сохраняет только **отличия от
   дефолта**. И что вы с этого будете иметь? Удобное восстановление.» → source wording («… — удобно для
   восстановления.»). A question sitting between a command and the next command (`dump all`) in a step
   section; the guide already demands zero colour in step-by-step instructions.
3. bf-pid, line closing the numbered tuning protocol: «**Ша:** один полёт — одно изменение.» → «Один
   полёт — одно изменение.» The sentence is the protocol's own rule, placed right after step 5; «Ша» there
   reads as a "stop" instruction.
4. bf-intro: «Первый полёт — на умолчаниях PID, **и не морочьте себе голову**: Betaflight 4.5 … летает на
   5" лучше…» → «Первый полёт — на умолчаниях PID: Betaflight 4.5 … летает на 5" **таки** лучше…». An
   imperative idiom welded onto a real recommendation; the guide's sample 7 keeps recommendations plain.
5. inav-intro: «…разные прошивки по поведению, хоть и один бинарник: **две большие разницы**.» → «Крыло и
   квадрокоптер — это **две большие разницы**: разные прошивки по поведению, хоть и один бинарник.» After
   the concessive clause the formula attached to "one binary".

Kept after consideration: «И что мы имеем? Имеем дрон, который на рыскании реагирует медленнее…»
(replaces «Поэтому»; the cause is the preceding sentence, so the result reading survives — now limited
by rule); «но обмануть физику? Я вас умоляю: без запаса тяги нет управления» (the technical statement
follows verbatim); «таки да: lag на 7 мс меньше»; «Как вам это нравится? На втором пилот летал резче…».

## Rulings

| Case | Ruling |
|---|---|
| «И что вы с этого будете иметь?» after the `diff all` step | Removed. The benefit question is for theory only; never in `## practice`, after a code block or step, or in a sentence naming a command |
| «Ша:» closing the tuning protocol | Removed. «Ша» never before a procedure rule or right after a numbered list |
| Imperative-form idioms («не морочьте себе голову», «не делайте мне нервы», «слушайте сюда») | Never in the same sentence as a recommendation or action; separate sentence before an explanation. Guide sample 9 is retired |
| Past-tense plurals | Only where the subject is the reader; name the subject before converting |
| Evaluative formula placement | Next to what it evaluates, not after a concessive clause |

New restrictions (appended to the guide): a silence zone around commands; causal connectives replaced
only when the cause is in the previous sentence, once per module; a negation from the source must remain
as a word, not as intonation; «таки» near numbers only before an evaluative word; quiz/task strings
byte-identical unless they contain «ты»; a grep list for self-checking.

## What only a native speaker can settle

- Whether the mix of formal «вы» with «слушайте сюда», «я вас умоляю», «имею вам сказать пару слов за…»
  reads as warm or as stage "Odessa for export" at this frequency (about four formulas per module).
- «за это и поговорим» closing a 40-word fronted clause (f-physics summary) — grammatical, but whether it
  sounds spoken.
- «Поговорим за то, где INAV…» — «за то, где» with a subordinate clause rather than a noun.
- Whether «две большие разницы» in two of five modules already feels repetitive across a course.

## Verdict

**Ready, with the appended rules.** 5 fixes in 34 changed sentences; one was a meaning error of a kind
that is now a mechanical check, four were placement of colour, two of which the author had flagged. The
guide is conservative, its constructions are widely understood, and the hard rule "safety, steps,
diagnostics, quiz and tasks change only in person" held in every file. The remaining ~120 modules can be
rewritten with the current guide plus the post-pilot section, provided the grep list is run per file and a
reviewer spot-checks every past-tense verb next to an aircraft noun. A native read is desirable for tone
but does not block.
