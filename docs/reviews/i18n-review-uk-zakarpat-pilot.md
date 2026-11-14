# Review: Transcarpathian pilot (`uk-zakarpat`), 5 modules

Date: 2026-11-14. Independent review; nothing committed. Scope: `i18n/uk-zakarpat/content/`
(`f-safety`, `f-physics`, `bf-intro`, `bf-pid`, `inav-intro`, their 5 quiz banks, `tasks/f-physics.json`)
against `i18n/uk/content/`. Method: sentence-level `diff` of every module, key-by-key diff of every JSON
string; each changed sentence judged for meaning, attestation in `i18n/uk-zakarpat/terms.md`, readability
without the dialect, and tone. Source checks: ESU article (esu.com.ua/article-14618) and Ukrainian
Wikipedia «Закарпатський говір» were re-opened; the other sources of the guide were not.
`python3 scripts/check_i18n.py`: 0 errors before and after.

## Counts

| File | Changed sentences | Fixed |
|---|---|---|
| foundation/f-safety.md | 16 | 6 |
| foundation/f-physics.md | 24 | 6 |
| betaflight/bf-intro.md | 23 | 4 |
| betaflight/bf-pid.md | 22 | 6 |
| inav/inav-intro.md | 22 | 1 |
| quiz/*.json (5 files) | 30 strings (q / explain only) | 6 |
| tasks/f-physics.json | 1 string (solution) | 0 |
| **Total** | **138** | **29 (21 %)** |

Unchanged, as required: section set, directives, code blocks, diagnostic markers, all quiz options and
answer indices, task statements, parameters, numbers, units, formulas. No word outside the guide was
found; nothing Galician, Hutsul or Lemko. Tone is respectful throughout; no caricature.
Density is at the low end of the guide's range (mostly one feature per sentence; `ся`, `кедь`, `айбо`,
`лем` carry most of it).

## Fixes (before → after, why)

Meaning or ambiguity:

1. f-physics: «…в рази, **та** таблиця має бути…» → «**тому** таблиця». `та` before a feminine noun reads
   as "that table"; the causal link was lost.
2. bf-pid: «**Не годен** тримати — відкат» → «**Не можеш** тримати». Source is 2nd person (the reader's
   finger on the motor); the copula-less form reads as 3rd person.
3. bf-pid quiz q10: «Що **ти** каже сись фрагмент…» → «Що каже сись фрагмент…». Pronoun absent from the
   source; short dative reads as nominative "ти".
4. bf-pid: «Профіль **сьме** прибрали», «Чіткість **сьме** повернули» → without `сьме`. Source is
   indefinite-personal (no «ми» in uk or ru); the particle asserts a first-person subject.
5. f-safety: «що змінював**-ись**, як летів, що помітив» → standard. Only one of two 2nd-person verbs was
   marked, so «помітив» fell in with the aircraft's «летів»; a checklist line.
6. f-safety diagnostics: «**ачей**, VTX уже пошкоджено» → «**можливо**, …». The guide glosses `ачей` as
   both "maybe" and "surely"; a diagnostic may not change the degree of certainty.
7. bf-intro diagnostics: «під час **проби**» → «**спроби**». In standard Ukrainian «проба» is a test or a
   sample, not an attempt.
8. f-physics: «Порахував**-им** T/W … й записав го» → «Порахував T/W … й записав го». One particle with
   two coordinated verbs leaves the second unmarked (see ruling 5). «Перевірив-им порядок…» kept.

Attestation / guide consistency:

9. «X, **ай не** Y» → «**а не**» in 7 places (f-safety ×1, bf-pid ×2, inav-intro ×1, quiz f-safety ×1,
   quiz bf-pid ×2). The guide attests `ай` in the frame «не X, ай Y» and its own sample 10 keeps «а не»;
   the pilot itself kept «а не EKF» in one place. The four «не X, ай Y» sentences stay.
10. f-physics: «**вшитко** керування», «**вшитко** налаштування» → «усе …». Determiner use is not attested
    in the guide's sources.

Readability / placement:

11. f-physics: «налаштовувати**, ги** п'ятидюймовик» → «**як** п'ятидюймовик». `ги` without a preceding
    comparative gives the outside reader nothing to infer it from.
12. bf-intro: «літає на 5" **май файно, ги** більшість…» → «**краще, ги** більшість…». Two opaque words
    carried the whole comparison, the first directly after a number.
13. quiz f-physics: «у 50–100 разів більший, **ги** у 5"» → «**ніж** у 5"». One-letter term plus numbers.
14. bf-pid: «**Сесе** P: вун піднімає…» → «**Це** P: вун…».
15. f-physics: «Коби тяга йшла строго як квадрат газу, **вун** був би √(1 / 4.1) ≈ 49 %» → «**він**».
    Formula sentence: one feature at most.
16. bf-intro diagnostics: «ACCEL **ся розпізнає**» → «ACCEL **розпізнається**»; quiz bf-intro: «Чим diff
    all **ся відрізняє** від dump?» → «**відрізняється**». `ся` right after a Latin identifier can be read
    as part of it.
17. f-safety: «допустимий **лем** на стенді», «Тест моторів — **лем** без пропів» → «**лиш**». In a safety
    rule the restrictor is the content; `лиш` is in the guide and transparent.
18. f-safety: «вун чинить **тото**, чого ніхто не обирав» → «**те**». Four features in a failsafe warning.
19. bf-intro: «(не «**лем** зарядка»)» → «**лише** зарядка». Quoted cable label.

## Rulings on the listed extrapolations

| Feature | Ruling | Basis |
|---|---|---|
| `вшитко` as determiner | ban | Only the pronoun is attested; agreeing forms are not in any opened source |
| Position of `ся` | keep, restricted | ESU example «мозолі ми ся начинили» and the guide's sources show pre-verbal `ся`; no source states the rule, so: directly before the verb, after a full word, never after punctuation or Latin identifiers |
| `не годен` for 2nd person | ban | Attested only with a 3rd-person subject; ambiguous without a copula |
| «не X, ай Y» | keep; «X, ай не Y» banned | ESU lists `ай` among adversative conjunctions; guide sample keeps «а не» |
| `-им / -ись / сьме` | restrict | ESU re-checked: «ходив-им, ходив-ись, ходили-сьме» confirmed. Problem is scope and added person, not attestation: `сьме` only where the source has «ми»; `-им` / `-ись` only with a single past verb in the sentence, `-ись` not in procedures |
| short dative `ти` (and `ми`) | ban | Homograph of nominative in a text addressed as «ти»; `му` stays |
| «май файно, ги…» | restrict | ESU confirms the construction («май високий ги утиць му»); kept for transparent adjectives, not after numbers; «краще/гірше» stay synthetic + `ги` |
| `ачей` | ban in technical text | Meaning rests on context reading, guide gloss spans two certainty levels |
| `сесе` next to one-letter terms | restrict | «Це» next to P/I/D/F/J, numbers, formulas |

New restrictions (guide section 11.2): `лиш` instead of `лем` in safety rules; no `та` for «тому»; quoted
labels untouched; no standard-homonym words (`проба`) in diagnostics; no added person or pronoun; formula
sentences take one feature; options, task statements and code unchanged; a grep list for self-checking.

## What only a native speaker can settle

- Whether «не X, ай Y» is the natural frame and «X, ай не Y» really is not (ruled conservatively).
- Scope of one past particle over coordinated verbs («Порахував-им … й записав»), and the written shape
  (`-ись` vs `-їсь` vs `-есь`; hyphen or not).
- Whether `сьме` can stand for the indefinite "we" of a case study.
- Whether pre-verbal `ся` after a noun subject («пропи ся крутять») sounds natural as often as the pilot
  uses it (about 40 instances), or whether second position after the first word is expected.
- `хоть`: attested (Keshelia), but an outside reader may take it for a Russianism — the same argument by
  which the guide rejects `што`. Kept for now.
- `кедь` vs `кидь`, `позирати` vs `позерати`, «стрілка позирає вбік» for an inanimate subject,
  «чинити крен / чинити лог марним» as collocations, `кулько` in a quiz question.
- Whether the text at this low density still reads as the dialect to a speaker, given that `ы`, `-т` and
  the `у` reflex are not written.

## Verdict

**Conditionally ready.** The process is sound: no factual, numeric, structural or term error in 138 changed
sentences, and every fix was a dialect-layer problem. But 21 % of changed sentences needed correction, and
almost all of them fall under the nine extrapolations the author listed plus three patterns the guide
actively encouraged (`та` for «тому», dative `ти`, `ачей`). With section 11 of the guide these are now
mechanical rules and a grep list. Recommendation: rewrite the remaining ~120 modules only after (1) a native
speaker from the Irshava–Khust–Mukachevo area has read these five modules and section 11, and (2) the grep
list of 11.2.8 is run on every rewritten file. Without step 1 the result is a careful, readable
stylisation whose authenticity is unverified, and it should keep the «експеримент» label.
