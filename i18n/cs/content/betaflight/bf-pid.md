---
id: bf-pid
title: "Ladění PID podle dat"
level: L2
readingTime: 30 min
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - PID
  - ladění
  - Blackbox
related:
  - bf-pid-reg-in-bf
  - bf-filters
  - bf-blackbox
next:
  - bf-cli
source: content/betaflight/bf-pid.md
source_hash: b05992625bbe
---

## summary
„Ostřejší“, „měkčí“, „houpe se“, „hřeje se“ – to jsou pocity pilota, které lze převést na čísla z logu a profily mezi sebou poctivě porovnat. Modul dává pracovní metodu: filtry před PID, jeden parametr na krok, čtyři profily v jednom letu, pět metrik po manévrech. Případová studie je experiment na dvou stejných 7": čtyři profily, co se shodlo s pocity, co ne, a proč výsledkem nebyl nový PID, ale nové filtry.

## theory
### Pořadí: nejdřív filtry, potom PID
PID zesiluje všechno, co přichází z gyroskopu, včetně šumu. Ladit PID na špatných filtrech znamená nastavovat zesilovač na pozadí rušení. Proto: RPM filtr a dynamický notch fungují, spektrum je čisté (moduly o filtrech a RPM filtru), a teprve potom PID.

### Posuvníky Betaflightu 4.3+
Jednoduchý režim ladění mění celé skupiny parametrů najednou:

- **Damping** (D) – odpor proti rychlým pohybům, tlumí překmit; vyšší hodnota – motory se hřejí.
- **Tracking** (P a I) – přesnost sledování kniplu a poruch; vyšší hodnota – oscilace.
- **Stick Response** (FF) – reakce na rychlé pohyby kniplu; vyšší hodnota – překmit na konci flipu.
- **Dynamic Damping** (D max) – o kolik může D vzrůst při rychlých pohybech.
- **Drift – Wobble** (I) – držení v zatáčkách a při nulovém plynu.
- **Master Multiplier** – všechno najednou; sahá se na něj, když ostatním nestačí rozsah.

V CLI to jsou `simplified_pi_gain`, `simplified_d_gain`, `simplified_feedforward_gain`, `simplified_dmax_gain` (ve 2025.12 `simplified_d_max_gain`), `simplified_i_gain`, `simplified_master_multiplier` plus `simplified_tuning apply`. PID profily jsou čtyři, profily rates čtyři – přepínají se přepínačem nebo v CLI příkazem `profile N`.

{{widget:pid-sim}}

### Příznaky
- P je velké – trhaný, překorigovává, rychlá oscilace. Malé – líný, pomalé rozhoupání.
- I je velké – „robot“, nízkofrekvenční oscilace. Malé – ujíždí, „klouže jako po ledu“.
- D je malé – bounce-back po flipech, propwash při klesání. Velké – horké motory, rozmazaná odezva.
- FF je velké – překmit na začátku flipu, chvění při pohybech kniplu.

Kontrola teploty motorů po každé změně D nebo filtrů: krátký let, přistání, prst na motor. Neudržíte ho tam – vraťte změnu.

### Pět metrik po manévrech
Manévr je úsek, kde je |setpoint| nad prahem (například 200 °/s) déle než 50 ms. Pro každý:

| Pocit | Metrika | Jak počítat |
|---|---|---|
| hřeje se | **motor noise** | std povelů motorům nad 40 Hz, průměr přes motory |
| třese se při klesání | **propwash RMS** | RMS gyro v pásmu 20–70 Hz na úsecích klesání |
| houpe se po zastavení | **bounce-back** | špička gyro opačného znaménka do 150 ms po zastavení / amplituda manévru, % |
| líně reaguje na knipl | **entry lag** | doba od začátku pohybu setpointu do 50 % na gyro, ms |
| nedotáhne / přetáhne | **peak tracking** | max gyro / max setpoint, % |

Medián z 10–20 manévrů je stabilní; průměr zkazí jeden nepovedený pohyb kniplem. Klasická step response (Blackbox Explorer; PID-Analyzer – od roku 2019 se nevyvíjí, PIDscope) je dobrá na dlouhých freestylových lozích, ale na krátkých lozích po 1–2 minutách na profil šumí o ±40 % – přímé metriky jsou poctivější.

### Případová studie: čtyři profily na dvou 7"
Dva téměř stejné stroje 7" (stejný rám, motory, vrtule, FC), uvedené do společného výchozího stavu. Čtyři profily se lišily jen posuvníky, filtry byly stejné:

| | COOL | SHARP | WASH | FLOAT |
|---|---|---|---|---|
| Tracking | 1.00 | **1.15** | 1.00 | 1.00 |
| Damping | 1.00 | 1.00 | **1.20** | **0.85** |
| D max | 1.00 | 1.00 | **1.20** | 1.00 |
| Feedforward | 1.00 | **1.15** | 1.00 | **0.80** |

Výsledek (dron A, mediány): motor noise 16.1 / 23.3 / 18.0 / 14.6; bounce-back 6.0 / 8.5 / 9.4 / 14.9 %; entry lag 38 / 31 / 40 / 44 ms.

- **SHARP „ostřejší“** – ano: lag je o 7 ms menší. Cenou je šum na motorech +45 %. To je P: zvedá zesílení na všech frekvencích.
- **FLOAT „měkčí“** – ano, nejtišší. Ale bounce-back je skoro 15 %: po zastavení se dron vrátí o 1/7 amplitudy. Pro natáčení špatné.
- **WASH „rozdíl není cítit“** – a čísla to potvrdila: propwash 0.97 oproti COOL, v mezích šumu. U 1.4 kg na 7" vrtulích je propwash aerodynamika, ne nedostatečné tlumení. Profil byl vyřazen.
- **Dva „stejné“ drony daly u SHARP různý bounce-back** (2.9 % proti 8.5 %): na druhém létal pilot ostřeji, D-max se stíhal zapínat. Závěr o metodě: porovnávat profily jen v rámci jednoho letu, nebo normovat na amplitudu manévru.

**Výsledek:** COOL je nejlepší kompromis. Ostrost se nevrátila přes P, ale přes filtry: `simplified_gyro_filter_multiplier` 1.00 → 1.10 a `dyn_notch_q` 400 → 450, PID jako COOL. Tak vznikl profil CRISP. První návrh byl agresivnější (1.25 a jeden notch), byl zamítnut ve prospěch malých kroků: 1.10 → let → při úspěchu 1.20.

### Protokol ladění (podle dat, ne podle pocitů)
1. **Základ**: výchozí hodnoty 4.5, filtry podle modulu „Filtry“, spektrum čisté, motory studené. Log A: vis 30 s + 10 manévrů s prudkým zastavením v ose roll/pitch + 3 klesání s propwashem.
2. **Metriky** z logu A (`data-python`: `step_metrics`, `bounce_back`, motor noise, propwash RMS) – do tabulky.
3. **Jeden posuvník na let**: Damping ±0.1 → log → metriky; potom Tracking ±0.1; potom Stick Response. Kritérium přijetí: cílová metrika se zlepšila, ostatní se nezhoršily, motory nejsou teplejší.
4. **Profil podle úkolu**: závodní (vyšší Tracking, vyšší Stick Response) a klidný (vyšší Damping) – různé `profile`, přepínání přepínačem.
5. **Zafixování**: `diff all` + tabulka „co – proč – metriky před/po“ do repozitáře (modul „CI“).
Jeden let – jedna změna. Dvě změny v jednom letu dělají log bezcenným.

### Orientační hodnoty metrik pro 5" 6S
| Metrika | Dobré | Snesitelné | Problém |
|---|---|---|---|
| overshoot | 3–10 % | 10–20 % | > 20 % (P/FF) |
| bounce-back | < 8 % | 8–15 % | > 15 % (D, zpoždění) |
| entry lag (do 50 %) | 20–35 ms | 35–50 | > 50 (FF, filtry) |
| settle (±5 %) | < 80 ms | 80–150 | > 150 |
| motor noise (std > 40 Hz) | nízký, stabilní | roste s D | „tráva“ v grafu motorů |
| teplota motorů | teplé | horké na dotek 5 s | prst se nedá udržet |
Pro 7–10" jsou všechny časy ×1.5–2, overshoot nižší (setrvačnost), bounce-back citlivější na zpoždění.

### Co nedělat
Neladit při větru > 5 m/s (I a polohové metriky lžou); neměnit PID a filtry v jednom letu; nekopírovat cizí `diff all` celý (jiné motory, vrtule, hmotnost, zpoždění); „neléčit“ mechaniku D-termem.

{{diagram:bf-tuning-loop|Ladění podle dat: nejdřív filtry, potom jedna změna → let podle programu → metriky → rozhodnutí nebo návrat zpět.}}

## practice
### Krok 1. Výchozí stav
Filtry čisté, RPM filtr funguje, posuvníky na 1.00, `diff all` uložen s datem. To je kontrolní profil.

### Krok 2. Čtyři profily
V profilech 1–4 nastavte varianty, které se liší jedním nebo dvěma posuvníky. Přepínání přepínačem (režim nebo `adjustment`), aby šlo měnit ve vzduchu.

### Krok 3. Program letu
Stejný pro všechny profily: 20 s visu, 10 prudkých pohybů v ose roll, 10 v ose pitch, tři klesání s nulovým plynem. Profily postupně v jednom vzletu. Po každém zápis do `session_notes.md`: pořadí, vítr, pocity, teplota motorů.

### Krok 4. Metriky
Rozbor logu v Pythonu (`orangebox` pro čtení, `scipy` pro spektra). Oříznout první a poslední 3 s, šum počítat na úsecích s plynem 25–60 %, logy se ztrátou rámců nad 1 % nebrat. Porovnávat mediány.

### Krok 5. Jeden krok najednou
Vítězný profil je nový výchozí stav. Další změna – jedna, malá, s letem a logem. Zpět se jde jedním pohybem přepínače: kontrolní profil zůstává ve slotu.

## diagnostics
- **Příznak:** step response „skáče“ mezi sousedními manévry
  - Možná příčina: krátký log, plynulý styl, režim ANGLE.
  - Co udělat: přímé metriky po manévrech, mediány, pro test ACRO.
- **Příznak:** motory jsou horké po profilu s vysokým D
  - Možná příčina: D zesiluje zbytkový šum.
  - Co udělat: vrátit D, zlepšit filtry, potom zopakovat.
- **Příznak:** propwash zvýšením D nemizí
  - Možná příčina: aerodynamika těžkého dronu na malých vrtulích.
  - Co udělat: jiné vrtule/hmotnost, TPA, nepřehánět D.
- **Příznak:** dva stejné drony dávají různá čísla
  - Možná příčina: program letu byl ve skutečnosti různý.
  - Co udělat: porovnávat profily v rámci jednoho letu, normovat na amplitudu.

## references
- PID Tuning Guide — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- PID Tuning tab — Betaflight App | https://betaflight.com/docs/wiki/app/pid-tuning-tab | primary | A
- Betaflight settings reference (settings.c, GitHub) | https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c | primary | A
- PID-Analyzer — step response tool (legacy, unmaintained since 2019) | https://github.com/Plasmatree/PID-Analyzer | secondary | C

## checklist
- Filtry jsou nastavené před PID, spektrum je čisté
- Kontrolní profil je uložený a zůstává ve slotu
- Profily se liší jedním nebo dvěma posuvníky
- Jeden program letu pro všechny profily, zápisy v session_notes
- Metriky jsou mediány po manévrech, ne průměr
- Jeden krok najednou, s logem
