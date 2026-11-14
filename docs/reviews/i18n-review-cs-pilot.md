# Czech (`cs`) pilot translation — independent review

Date: 2026-11-14. Scope: 5 modules, 5 quizzes, 1 task bank under `i18n/cs/content/`, compared sentence by
sentence with the Russian sources, against `i18n/cs/terms.md`.

Limits of this review: it was done by a language model acting as a Czech technical editor, not by a
native-speaking human. Web evidence was read through a fetch tool that returns an extract of the page, and
only one Czech page relevant to the open terminology item could be opened (Rotorama «Nastavení Betaflight»);
three further searches for Czech forum or shop usage returned English pages only. The site build was not run;
`python3 scripts/check_i18n.py` reports 0 errors (cs: 5 modules, 5 quizzes, 1 task bank).

## Verdict

The guide and the process are good enough to continue, after the instruction changes in the last section.
No meaning error touching a safety statement, number, unit, sign, condition or version was found. All 42
quiz answers keep their index, the correct option stays the only correct one, distractors stay wrong; both
task statements define the same problem and `answer`/`tol`/`params` are identical. Typography (quotes, en
dash, spaced units and percent, decimal points) and vykání are consistent in all 11 files. What was wrong
is of one kind: wording carried over from Russian word for word, plus the one terminology collision the
translator had already flagged.

## Counts

59 replacements in 9 of 11 files (`inav-intro` quiz and the task bank are unchanged).

| category | fixes |
|---|---|
| Terminology: flag vs příznak | 19 |
| Terminology: other (vzletová hmotnost, řešený příklad, splněna, stack) | 8 |
| Calques / Russian sentence patterns | 21 |
| Meaning (imprecise or misleading rendering) | 6 |
| Grammar / morphology (incl. „lozích“) | 5 |
| Typography, numbers, units, form of address | 0 |
| Quiz key or task definition | 0 |

Per file: f-safety.md 13, f-physics.md 8, bf-intro.md 7, bf-pid.md 13, inav-intro.md 9, quiz f-safety 5,
quiz f-physics 1, quiz bf-intro 2, quiz bf-pid 1.

## Open item resolved: «флаг запрета арма»

- Evidence: Rotorama, «Nastavení Betaflight» (https://www.rotorama.com/t-nastaveni-betaflight), as returned
  by the fetch extract: „Najdete zde i Arming Disable Flags – důvody, proč nejde armovat.“ The English
  label is kept and glossed; no Czech noun is coined. No other Czech source using a Czech word for these
  flags was found.
- Decision: **flag blokující armování**, with the on-screen name at first mention in a module („flagy
  blokující armování (Arming Disable Flags)“), afterwards *flag*. *příznak* now means only «симптом».
  This also repairs a sentence that was unreadable before: „Příznaky jsou pojistka. Vypnutím kontroly
  odstraníte příznak“ → „Flagy jsou pojistka. Vypnutím kontroly odstraníte příznak, ne nebezpečí.“
- Applied in f-safety.md (9 places, including the table header `| Flag |` and the diagram caption),
  bf-intro.md (3), inav-intro.md (1), quiz f-safety (4), quiz bf-intro (2). The `**Příznak:**` markers are
  untouched. The heading „### Příznaky“ in bf-pid.md translates «Симптомы» and is correct.
- Confidence: medium. *flag* is ordinary Czech developer usage, but the choice rests on one source plus
  judgement. Left for the human reviewer below.

## Fixes (before → after, why)

### foundation/f-safety.md
1. „seznam příznaků blokujících armování v Betaflightu“ → „seznam flagů blokujících armování (Arming Disable Flags) v Betaflightu“ — term.
2. „energie … jsou jednotky joulů“ → „činí jednotky joulů“ — subject/verb agreement.
3. „se může vznítit za několik minut i hodin po nárazu“ → „i několik minut nebo hodin po nárazu“ — „za … po“ doubled preposition; the delayed-ignition warning now reads unambiguously.
4. „jeden příznak blokující armování … vidět jsou příkazem `status` v CLI a v OSD“ → „jeden flag blokující armování … vypíše je příkaz `status` v CLI a ukazuje je OSD“ — term; calque of «видны по».
5. diagram caption „přečteme příznak“ → „přečteme flag“ — term.
6. table header `| Příznak |` → `| Flag |` — term.
7. „Tyto příznaky jsou pojistka“ → „Tyto flagy jsou pojistka“ — term.
8. „varování – žádné příznaky“ → „žádné flagy“ — term (as written it said "no symptoms").
9. „předtím s multimetrem“ → „předtím kontrola multimetrem“ — the source means "check with a multimeter first"; the Czech had no verb or noun for the check.
10. „→ příznak `MSP` →“ → „→ flag `MSP` →“ — term.
11. „je aktivní příznak blokující armování“ (inside a `Příznak:` item) → „flag“ — the collision itself.
12. checklist „Na stole nejsou vrtule“ → „Na stole je dron vždy bez vrtulí“ — the Czech said "there are no propellers lying on the table"; the rule is about propellers mounted on the drone.
13. checklist „Znám všechny příznaky blokující armování“ → „flagy“ — term.

### foundation/f-physics.md
1. „dělený vzletovou tíhou“ → „vzletovou hmotností“ — term; the module itself says „vzletová hmotnost“ in the worked example.
2. „nemůže povel splnit celý“ → „splnit úplně“ — word order/idiom.
3. „reakční momenty se nevyrovnají“ → „se nevyruší“ — the section says „Momenty se navzájem ruší“; keep one verb.
4. „rychlý náraz na saturaci“ → „brzká saturace“ — calque of «быстрый упор».
5. „maximální tah jednoho motoru, g.“ → „v g.“ — Russian unit-after-comma pattern.
6. „T/W = maximální tah / vzletová tíha“ → „vzletová hmotnost“ — term.
7. „Rozebraný příklad“ → „Řešený příklad“ — calque.
8. „Laboratorní úloha se uznává“ → „je splněna“ — guide (сдан → splněno).

### betaflight/bf-intro.md
1. „Hlavním důrazem celého stacku je výkon“ → „Celý projekt klade hlavní důraz na výkon“ — calque; *stack* is the hardware stack in the guide.
2. „zatížení a příznaky armování … a příznak `LOAD`“ → „flagy blokující armování … flag `LOAD`“ — term (2).
3. „Rozebraný příklad“ → „Řešený příklad“ — calque.
4. „ladění přijde až po lozích“ → „až podle logů“ — morphology; also "after the logs" → "from the logs".
5. „neporušenost vodičů a pájení“ → „pájených spojů“ — *pájení* is the activity, not the joints.
6. „Dron jde armovat, ale motory se netočí“ → „Dron se armuje“ — the source says the drone arms, not that it could be armed.
7. „`LOAD` v příznacích armování“ → „mezi flagy blokujícími armování“ — term.

### betaflight/bf-pid.md
1. „Modul dává pracovní metodu … pět metrik po manévrech“ → „Modul nabízí metodu, která funguje … pět metrik počítaných pro jednotlivé manévry“ — «рабочий метод» is a method that works, not a "work method"; „po manévrech“ reads "after the manoeuvres" (2).
2. „nastavovat zesilovač na pozadí rušení“ → „uprostřed rušení“ — calque of «на фоне помех».
3. „přesnost sledování kniplu a poruch“ → „a vyrovnávání vnějších poruch“ — as written it said the loop tracks faults; the guide asks for the sense of *porucha* to be clear.
4. heading „Pět metrik po manévrech“ → „pro jednotlivé manévry“.
5. „na … freestylových lozích, ale na krátkých lozích … šumí o ±40 %“ → „u … logů, ale u krátkých logů … kolísá o ±40 %“ — morphology (2); „šumí o“ is not Czech.
6. „Profil podle úkolu“ → „podle účelu“.
7. „Zafixování“ → „Uložení“ — calque.
8. „dělají log bezcenným“ → „log znehodnotí“ — calque of the instrumental predicate.
9. „v jednom vzletu“ → „během jednoho letu“ — «вылет» here is the flight.
10. „Krok 5. Jeden krok najednou“ and the checklist line → „Vždy jen jeden krok“ — „najednou“ means "all at once", the opposite of the intent (2).
11. diagnostics „přímé metriky po manévrech“ → „pro jednotlivé manévry“; checklist „mediány po manévrech“ → „přes manévry“ (2).

### inav/inav-intro.md
1. „se stejným přístupem ke konfigurátoru“ → „nastavuje se stejně – přes konfigurátor“ — the Czech meant "the same access to the configurator".
2. „safehomes je až 8 … bodů“ → „safehomes – až 8 … bodů“ — number agreement.
3. „kompas je žádoucí“ → „se doporučuje“ — register.
4. „řádek s příznaky blokování armování“ → „s flagy blokujícími armování“ — term.
5. „kurz to sleduje“ → „kurz se mění stejně“ — calque.
6. „odneste stroj o 20–30 m – … odpovídá krokům“ → „20–30 m daleko – … odpovídá odkrokované vzdálenosti“ — wrong preposition; "matches the steps" was unclear.
7. „s připraveností převzít řízení“ → „buďte připraveni převzít řízení“ — nominal calque in a safety instruction.
8. „zasáhl safehome“ → „se uplatnil safehome“ — *zasáhnout* is used in this batch for a protection tripping.
9. „parametry z diffu se nepoužily“ → „se nenačetly“ — «не применились».

### Quizzes
- f-safety: Q1, Q4, Q7 question text and Q4 explanation: příznak → flag (4); Q1 explanation „na stole vrtule nejsou“ → „na stole je dron bez vrtulí“.
- f-physics: Q3 explanation „vzletová tíha“ → „vzletová hmotnost“.
- bf-intro: Q7 „Příznak LOAD mezi příznaky armování“ → „Flag LOAD mezi flagy blokujícími armování“ (2); Q3 explanation „Konfigurace žije na desce“ → „je uložená na desce“.
- bf-pid: Q3 „medián po manévrech“ → „medián přes manévry“.

## Left for a human native speaker

1. **flag blokující armování** — confirm against how Czech pilots actually say it (candidates heard in other
   languages' communities: „arming flagy“, „důvod blokace armování“). One source only.
2. **vypnout armování** for disarm (guide). Reads stiff in tables („vypnout armování/restartovat“). Whether
   Czech pilots write „disarmovat“ or „odarmovat“ was not verified; the research found only „v poloze disarm“.
3. **poměr tahu k tíze (T/W)** — kept. Physically exact; whether FPV texts prefer „poměr tahu k hmotnosti“
   could not be confirmed (Rotorama's motor page is served in English; thesis PDFs did not open).
4. **LiPo „při zkratu dodá stovky ampérů“** for «при пробое» (f-safety summary) and „vnitřní zkrat“ for
   «внутренний пробой». Sense is right for an internal short; a battery specialist may prefer „při proražení“
   in the summary.
5. **estimátor** (guide) next to *odhad stavu*: fine in theses; check that „komplementární estimátor“ is
   not better as „komplementární filtr“ for INAV.
6. **satelity** vs *družice* (GNSS). Guide choice kept.
7. Register choices kept as translated: „rozmazaná odezva“ (мыльный отклик), „stroj velmi ostrý“ (резкий),
   „trhaný“ (дёрганый), „pětipalec“, „Protokol ladění“ (could be „Postup ladění“), „datasheet“.
8. Module titles in cross-references („Provoz v terénu“, „Elektřina 101“, „Mechanika letu“, „INAV: GPS a
   RTH“) must be reconciled with `i18n/cs/data.json` when it exists.
9. Front-matter tag „kontrolní seznam“ and the `firmware: libovolný firmware` value: check how they render.

## Is the guide + process ready for the remaining ~120 modules?

Yes, with these changes to the translator instructions first:

1. **Reserve *příznak* for symptoms.** Add the "Reviewer corrections" rows to the main table; never use
   *příznak* for a software flag. Add a pre-submit grep: every „příznak“ outside `**Příznak:**` must
   translate «симптом/признак».
2. **Translate the sentence, not the words.** Add a short list of banned calques with the Czech pattern:
   «по X» (distributive) → „pro jednotlivé X / přes X“, never „po X“; «рабочий» → „funkční / který funguje“;
   «на фоне» → „při / uprostřed“; «за раз» → „vždy jen“; «разобранный пример» → „řešený příklad“;
   «фиксация» → „uložení / záznam“; predicate instrumental („dělá X bezcenným“) → a verb; unit after a
   comma („…, g“) → „v g“; «живёт» for data → „je uložen“.
3. **Telegraphic source lines need a Czech verb or noun.** Where the source drops the verb («с мультиметром
   до того», «с готовностью перехватить»), write a full instruction; these are mostly safety steps.
4. **hmotnost vs tíha.** Any quantity in g/kg is *hmotnost*; *tíha* only for the force and in the name of
   the T/W ratio.
5. **Locative plural of *log*.** Do not write „lozích“/„logech“; rephrase („u logů“, „podle logů“, „v logu“).
6. **Checklist and quiz lines must be read alone.** „Na stole nejsou vrtule“ was correct in context and
   wrong on its own. Instruct: each checklist item and each `explain` must be unambiguous without the module.
7. **Quiz self-check.** After translating a quiz, state for each question why the keyed option is still the
   only correct one in Czech; keep option order and count; never merge two near-identical distractors.
8. **Disarm.** Decide the verb before the Betaflight track is translated (item 2 above); it occurs in most
   Betaflight and ArduPilot modules and is expensive to change later.
9. **Keep the second pass.** The translator's own open-item list was accurate (it flagged the only real
   term collision). Keep "translator lists open items → reviewer resolves → terms.md appended" per batch of
   about 10 modules, and have a Czech native speaker read at least the safety, failsafe and regulations
   modules before publication: nothing here has been read by one.
