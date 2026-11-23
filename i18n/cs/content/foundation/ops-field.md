---
id: ops-field
title: "Provoz v terénu a práce týmu"
level: L2
readingTime: 25 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - provoz
  - tým
  - protokol
related:
  - f-regulations
  - bf-failsafe
  - link-vtx
next:
  - bf-blackbox
source: content/foundation/ops-field.md
source_hash: 21b5a09015db
---

## summary
Většinu nehod nezpůsobí firmware, ale organizace: nikdo si neověřil frekvence sousedů, nikdo se nedomluvil, kdo sleduje stroj, chyběl plán pro ztrátu spojení. Modul pojednává o provozu jako o disciplíně: plánování výjezdu, role v týmu, frekvence a komunikace, předletový a poletový protokol, postup při incidentu a hledání spadlého stroje. Vychází z praxe několika pilotů pracujících na jedné letové ploše.

## theory
### Plánování výjezdu
Před výjezdem je známo: letová plocha a zóny (modul o pravidlech), počasí (vítr v jednotlivých výškách, srážky, teplota – chlad ubírá LiPo kapacitu), cíl výjezdu a kritéria úspěchu, kdo se účastní a v jakých rolích, jaké frekvence obsazují sousedé.

### Role
I ve dvou se vyplatí role výslovně pojmenovat:

- **Pilot** – řídí a ničím jiným se nezabývá.
- **Pozorovatel (spotter)** – sleduje očima stroj i okolí: lidi, ptáky, jiné stroje; hlásí pilotovi, aniž by ho rozptyloval.
- **Technik / GCS** – telemetrie, parametry, logy, výměna baterií, časovač.
- **Vedoucí** – rozhoduje „letíme / neletíme“ a vede deník.

Jeden člověk může role spojovat, ale pilot je za letu jen pilotem.

### Frekvence a komunikace
- **Video**: tabulka obsazených kanálů na letové ploše; odstup od sousedů (orientačně ≥ ~37 MHz pro analog); změna kanálu probíhá podle postupu z modulu o VTX, nejdřív na jednom stroji.
- **RC**: binding phrase je unikátní; packet rate podle úkolu; při více vysílačkách ELRS různé fráze, jinak se vzory přeskoků shodnou.
- **Hlas**: krátké standardní fráze: „arm“, „vzlet“, „spojení“, „slabá baterie“, „přistáváme“, „nouze“. Pilot potvrzuje jedním slovem.

### Protokoly
**Předletový** (z modulu o bezpečnosti, doplněný): frekvence jsou dohodnuty, role pojmenovány, napětí baterie zapsáno, failsafe je vyzkoušený na tomto stroji, časovač se spouští při armování.

**Poletový**: disarm, baterie odpojena, teplota motorů, prohlídka vrtulí a rámu, záznam do deníku (čas, baterie před/po, poznámky), log uložen, pokud šlo o zkušební let.

### Incidenty
- **Ztráta spojení**: pilot ji ohlásí, všichni sledují stroj, nikdo neběží. Stroj dělá to, co je nastaveno ve failsafe – právě proto se failsafe zkouší předem.
- **Pád**: místo podle poslední telemetrie nebo videa, bzučák (BEEPER), souřadnice GPS z logu GCS. Při přístupu ke spadlému stroji počítejte s tím, že baterie může být poškozená: horké nebo nafouknuté baterie se nedotýkejte a nenabíjejte ji.
- **Úraz**: první pomoc, záchranné složky, teprve potom všechno ostatní.
- **Rozbor**: co se stalo, podle logu, bez hledání viníků; závěr se zapíše do deníku a do kontrolního seznamu.

{{diagram:crash-search-flow|Поиск начинается в первую минуту на месте: последняя точка по самому точному источнику плюс поправка на инерцию, затем схема поиска и решение старшего через 30–40 минут, пока АКБ не села.}}

### Případová studie
Ukázalo se, že používaný kanál E5 (5885 MHz) obsadil spadlý stroj, který vysílal až do konce směny. Řešení: jako nejbližší volná frekvence s ohledem na kanály dvou sousedů byl vybrán F1 (5740 MHz); změna proběhla nejdřív na dvou vysílačích a několika dronech na zkoušku, potom na všech. Hlavní poučení: tabulka obsazených frekvencí na letové ploše musí existovat dřív, než dojde k incidentu.

### Standardní protokol rádiové komunikace (tým 2–4 lidí)
| Událost | Fráze | Odpověď |
|---|---|---|
| Připravenost k armování | „Stroj 1, arm?“ | „Arm povolen“ / „Stop, <důvod>“ |
| Vzlet | „Vzlétám“ | „Vidím“ (pozorovatel) |
| Změna režimu | „Loiter“ / „Auto“ | „Rozumím“ |
| Problém | „Pozor, <co>“ | „Přistaň“ / „Pokračuj“ (vedoucí) |
| Slabá baterie | „Baterie 3.5“ | „Návrat“ |
| Ztráta videa/spojení | „Nemám video“ / „Failsafe“ | „Všichni sledují, nehýbat se“ |
| Přistání | „Přistávám“ | „Volno“ (plocha je volná) |
| Disarm | „Disarm“ | „Rozumím, další“ |
Krátké, stále stejné, bez žargonu; nováček se fráze naučí před prvním výjezdem.

### Briefing a debriefing (každý 10 minut)
Briefing: cíl výjezdu, role, letová plocha a zóny, frekvence, počasí, nouzové postupy, kdo rozhoduje o „stop“. Debriefing: co se povedlo, co ne, incidenty a „skoroincidenty“ (near miss – hlavní zdroj zlepšení), změny v protokolu nebo kontrolním seznamu, úkoly na příští výjezd. Zapisuje se do deníku letové plochy, ne do hlavy.

### Kontrolní seznam letové plochy (jedna stránka)
Příjezd a parkování; místo vzletu (rovné, bez trávy ve vrtulích); letový prostor podle pravidel (modul „Pravidla“); překážky (elektrické vedení, stožáry, stromy) s výškami; lidé/zvířata/silnice; vítr (anemometr nebo předpověď pro jednotlivé výšky), srážky, teplota (LiPo < 10 °C zahřát); spojení (telefon, vysílačky pro hlasovou komunikaci); lékárnička, hasicí přístroj nebo písek, voda; tabulka frekvencí účastníků; schéma „kam stroj spadne při DROP“ pro každý bod trasy.

### Řešený příklad: výjezd na test RTH
Briefing: cílem je ověřit RTH na 7" ve vzdálenosti 100 m od domova; pilot – A, pozorovatel – B, technik/GCS – C; letová plocha se zakázaným směrem k silnici; vítr 4 m/s od západu – RTH půjde proti větru, stroj se bude vracet pomaleji (rezerva baterie); frekvence: R1 analog, ELRS 2.4 250 Hz. Provedení: armování podle frází, vis v 1 m → stoupání do 30 m → odlet 100 m po větru → „RTH“ přepínačem → pozorovatel sleduje stroj očima → návrat → vis nad domovem → ruční přistání. Debriefing: RTH nastoupal do 60 m podle nastavení, stroj se vrátil za 25 s, přistání ručně; near miss – pozorovatel se na 5 s rozptýlil telefonem → do protokolu: telefony v režimu „nerušit“ u všech kromě technika.

{{diagram:sortie-flow|Výjezd jako proces: plán, briefing, kontrolní seznam letové plochy, let s rozdělenými rolemi, debriefing a záznam do deníku.}}

## practice
### Krok 1. Mapa letové plochy
Schéma: místo vzletu a přistání, letový prostor, zakázané směry (lidé, silnice, dráty), stanoviště týmu, směr přiblížení na přistání. Frekvence sousedů v tabulce.

### Krok 2. Protokol na jedné stránce
Vytiskněte: role, standardní fráze, předletový a poletový kontrolní seznam, postup při incidentu, telefonní čísla.

### Krok 3. Zkouška naostro
Jeden let přesně podle protokolu, s časovačem a deníkem. Potom si projděte, co bylo nepohodlné, a opravte to v protokolu.

### Krok 4. Rozbor incidentu
Vezměte skutečný nebo cvičný incident (ztráta spojení, pád) a rozeberte ho podle logu: příčina, co zafungovalo, co ne, jaká změna v protokolu z toho plyne.

### Řešený příklad: protokol na jedné stránce
- **Letová plocha:** místo vzletu – rovná polní cesta, bez trávy ve vrtulích; letový prostor – sektor 120° k severu, do 150 m; zakázaný směr – silnice na východě; elektrické vedení 300 m na západ, výška 25 m.
- **Frekvence:** tabulka účastníků – pilot, kanál videa, frekvence RC spoje. Kdo přijede později, zapíše se dřív, než poprvé zapne své vybavení.
- **Role:** pilot (jen stroj a vysílačka), pozorovatel (oči na stroji a na obloze, hlasem hlásí lidi a ptáky), technik nebo GCS (deník, baterie, telemetrie).
- **Standardní fráze:** „Armuji“ → „Volno“ od pozorovatele; „Vzlet“; „Přistání“; „Stop“ – smí ji říct kterýkoli účastník, po ní stroj okamžitě přistává nebo zůstává ve visu.
- **Deník letu:** čas armování a disarmu, číslo baterie, napětí před a po, poznámky. Příklad řádku: `14:05–14:12, baterie č. 3, 25.1 → 22.3 V, RTH ověřen, vibrace v normě`.

### Co zapsat po zkoušce
Kolik minut zabrala příprava a kolik samotný let; který bod kontrolního seznamu byl nepohodlný nebo vynechaný; co řekl pozorovatel a zda to bylo slyšet. Protokol se opravuje hned, dokud je vše čerstvé, a další verze dostane datum.

### Formát rozboru incidentu
Co se stalo (podle času, podle logu) → bezprostřední příčina → proč byla možná (několikrát „proč“, dokud nedojdete k procesu, ne k člověku) → co zafungovalo (failsafe, povel „Stop“) → co nezafungovalo → jedna konkrétní změna v protokolu nebo v nastavení a kdo za ni odpovídá. Bez hledání viníků: cílem je, aby se to neopakovalo.

Laboratorní úloha je splněna, když existuje mapa letové plochy se zónami, překážkami a tabulkou frekvencí, role a fráze jsou zapsány a vyzkoušeny při skutečném letu s deníkem a jeden incident (skutečný nebo cvičný) je rozebrán podle výše uvedeného formátu s konkrétní změnou v protokolu.

## diagnostics
- **Příznak:** rušení videa uprostřed letu
  - Možná příčina: soused zapnul vysílání na sousední frekvenci.
  - Co udělat: tabulka frekvencí, odstup kanálů, v případě potřeby přistát a změnit kanál.
- **Příznak:** dvě vysílačky se navzájem ruší
  - Možná příčina: stejná binding phrase nebo přetížené pásmo.
  - Co udělat: nastavte unikátní fráze, v těsné blízkosti snižte výkon, rozdělte lety v čase.
- **Příznak:** spadlý stroj se nepodařilo najít
  - Možná příčina: chybějí poslední souřadnice, bzučák není nastaven.
  - Co udělat: přiřaďte BEEPER na přepínač, používejte GCS se záznamem tlog, poslední polohu určete z videa.
- **Příznak:** pilot se rozptýlil telemetrií a ztratil stroj z dohledu
  - Možná příčina: role nejsou rozděleny.
  - Co udělat: pozorovatel a technik musí být samostatní lidé.

## references
- Safety — ArduPilot Copter | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A
- INAV Safety | https://github.com/iNavFlight/inav/blob/master/docs/Safety.md | primary | A
- Betaflight Arming Sequence & Safety | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A

## checklist
- Mapa letové plochy se zónami a tabulka frekvencí existují
- Role jsou pojmenovány, pilot je za letu jen pilotem
- Protokol na jedné stránce je vytištěn
- Let podle protokolu je proveden, deník je vyplněn
- Rozbor incidentu je proveden a přinesl změnu v protokolu
