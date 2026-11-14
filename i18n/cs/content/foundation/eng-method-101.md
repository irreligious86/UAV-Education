---
id: eng-method-101
title: "Inženýrská metoda 101: požadavky, architektura, testy, dokumentace"
level: L1
readingTime: 30 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - inženýrská metoda
  - požadavky
  - testy
  - dokumentace
related:
  - f-components-choice
  - tools-overview
  - f-safety
next:
  - tools-overview
source: content/foundation/eng-method-101.md
source_hash: ae91b13ffb1e
---

## summary
Rozdíl mezi stavitelem a inženýrem není v páječce, ale v metodě: inženýr ví, *co* má stroj dělat (požadavky), *jak* je uspořádán (architektura), *čím* je doloženo, že to opravdu dělá (testy), a zanechává stopu, podle které může v práci pokračovat někdo jiný (dokumentace). Tento modul zavádí metodu hned na začátku kurzu – na příkladu první stavby – a určuje podobu „inženýrské složky“, která je od této chvíle povinná v každém závěrečném projektu.

## theory
### K čemu je to začátečníkovi
Bez požadavků každé nastavení „zabralo“ nebo „nezabralo“ jen podle pocitu. Bez architektury je hledání závady zkoušení naslepo. Bez testů nevíte, co včerejší změna rozbila. Bez dokumentace je vám za měsíc vlastní práce cizí. Metoda stojí hodinu na začátku a později ušetří dny; ve velkých projektech (viz rozbor nehod) stojí její absence stroje i pověst.

### 1. Požadavky
Požadavek je tvrzení o tom, co má stroj dělat, které lze **ověřit**. Formát: ID, text, kritérium, způsob ověření.

| ID | Požadavek | Kritérium | Ověření |
|---|---|---|---|
| R-01 | Visí s užitečným zatížením 30 g nejméně 15 min | ≥ 15:00 do 3.5 V/článek | Let se stopkami, log napětí |
| R-02 | T/W při vzletové hmotnosti ≥ 2.5 | výpočet a plyn ve visu ≤ 40 % | Tabulka tahu + log |
| R-03 | Při ztrátě spojení přistane na místě po 1.5 s | DROP po 1.5 s | Test na zemi bez vrtulí + log |
| R-04 | Video a RC se neztrácejí do 1 km ve výšce 50 m | LQ > 70 %, video bez výpadků | Test v terénu se záznamem |
| R-05 | Vzletová hmotnost ≤ 900 g | váha | Vážení |

Pravidla: měřitelnost („rychlý“ není požadavek, „zrychlení na 15 m/s za 3 s“ požadavek je); jeden požadavek – jedno ověření; požadavky na bezpečnost a soulad s předpisy tvoří samostatnou skupinu (S-xx); u každého čísla je uveden zdroj.

### 2. Architektura
Schéma bloků a vazeb: co je s čím spojeno, jakým rozhraním a odkud se napájí. U dronu jsou to tři vrstvy na jednom listu:
- **Napájení**: baterie → ESC; baterie → BEC 5 V → FC, RX, GPS; BEC 9 V → VTX. U šipek jsou proudy.
- **Data**: RX —CRSF→ FC (UART1); GPS —UBX→ FC (UART2); FC —DShot→ ESC; FC —MSP/OSD→ VTX (UART3); FC —Blackbox→ flash paměť.
- **Mechanika**: co je kde umístěno, hmotnosti, těžiště.
Architektura odpovídá na otázku „proč právě takhle“ jednou větou ke každému rozhodnutí: „GPS je na stožárku – kompas dál od silových vodičů (viz rušení)“.

### 3. Testy
Každý požadavek → test s očekávaným výsledkem, skutečným výsledkem a datem. Testy jsou:
- **Pozemní** (bez vrtulí): porty, směr otáčení motorů, failsafe, předletové kontroly firmwaru.
- **Simulační** (SITL pro INAV/ArduPilot/PX4): mise, failsafe, geofence.
- **Na měřicí stolici**: tah, proud, spektrum vibrací.
- **Letové**: vis, dosah, doba letu.
Pravidlo regrese: po každé změně konfigurace se zopakují pozemní testy a ten letový test, kterého se změna týká. Tabulka testů je živý dokument.

### 4. Dokumentace a deník změn
Minimální inženýrská složka (repozitář git):

```
my-drone/
  README.md          — co to je, k čemu slouží, aktuální stav, jak to spustit
  requirements.md    — tabulka požadavků
  architecture.md    — schémata napájení/dat/mechaniky (obrázky + text)
  tests.md           — tabulka testů s výsledky
  config/            — diff all / parametry s datem a verzí firmwaru
  logs/              — klíčové logy s poznámkou, co v nich je
  CHANGELOG.md       — datum, co se změnilo, proč, čím je to ověřeno
```

Deník změn má jeden řádek na každou změnu: `2026-11-08 — D-term 25→30 na roll; cíl: odstranit bounce-back; ověření: log 0042, overshoot 12%→6%`. Právě tohle je „ladění podle dat“.

### Trasovatelnost
Nit požadavek → architektonické rozhodnutí → test → výsledek. Pokud chybí, projekt nelze odevzdat: není jasné, co je doloženo. V hodnoticích kritériích závěrečných projektů kurzu je to samostatný řádek.

### Jak to vypadá v praxi u profesionálů
Zprávy z vyšetřování nehod (modul „Rozbor skutečných nehod“) uvádějí stále dokola tytéž příčiny: chyběly požadavky pro případ poruchy, chyběly testy failsafe, konfigurace se měnila bez záznamu, dokumentace neodpovídala stroji. Metoda není byrokracie, ale to, co odlišuje inženýrský stroj od hromady dílů.

{{diagram:traceability|Trasovatelnost: každý požadavek má test a každý test má požadavek; změna ukáže, které testy je třeba zopakovat.}}

## practice
### Krok 1. Repozitář
Vytvořte repozitář `my-drone` se soubory podle šablony výše. Do README patří tři odstavce: co je to za stroj, k čemu slouží a jaký je aktuální stav.

### Krok 2. Požadavky
Tabulka s ≥ 8 požadavky na vaši první stavbu: 4–5 funkčních (doba letu, T/W, dosah, hmotnost), 3 bezpečnostní (failsafe, zóny, předletový kontrolní seznam), 1–2 provozní (opravitelnost, rozpočet). Každý s kritériem a způsobem ověření.

### Krok 3. Architektura
Jedno schéma napájení a dat (nakreslené rukou a vyfocené úplně stačí) s popsanými rozhraními a proudy.

### Krok 4. Testy
Tabulka testů ke každému požadavku. Proveďte ty, které už provést lze (vážení, výpočet T/W, pozemní kontroly); ostatní označte poznámkou „naplánován“.

### Krok 5. První commit a zápis do deníku
Commit se zprávou, co bylo uděláno; první řádek CHANGELOG.

### Příklady požadavků, které lze ověřit
| ID | Požadavek | Metoda | Test |
|---|---|---|---|
| REQ-01 | Vis nejméně 12 minut s baterií 6S 4000 mAh | test | T-01: vis do 3.5 V na článek, stopky |
| REQ-02 | T/W nejméně 3 s veškerým letovým vybavením | výpočet + vážení | T-02 |
| REQ-03 | Vzletová hmotnost nejvýše 900 g | vážení | T-03 |
| REQ-06 | Při ztrátě RC delší než 1 s – přistání ve failsafe nebo RTH | test | T-06: vypnutí vysílačky na stole bez vrtulí, potom v terénu |
| REQ-07 | Lety pouze mimo zakázané zóny | kontrola mapy | T-07: mapa plochy ve složce |

„Stroj musí být spolehlivý“ není požadavek: nelze ho ověřit. „Ani jedna porucha během 20 letů po sobě“ už ověřit lze.

### Co má být výsledkem
- V repozitáři jsou `README.md`, `requirements.md`, `architecture.jpg` (fotka schématu stačí), `tests.md`, `CHANGELOG.md`.
- Každý řádek tabulky testů odkazuje na požadavek a každý požadavek má alespoň jeden test. Provedené testy mají datum a výsledek, naplánované mají poznámku.
- První řádek CHANGELOG: `2026-11-09 — inženýrská složka vytvořena, T/W spočítán (3.4), hmotnost 860 g`. Čísla budou vaše.

Laboratorní úloha je splněna, když jsou v gitu požadavky s ID (8 a více, každý měřitelný), schéma architektury s popsanými rozhraními a proudy, tabulka „požadavek → test → výsledek“ a založené README a deník změn.

## diagnostics
- **Příznak:** požadavky znějí jako přání („spolehlivý“, „rychlý“)
  - Možná příčina: chybí kritérium a způsob ověření.
  - Co udělat: přepište je s číslem a testem; pokud číslo není, nejde o požadavek, ale o cíl.
- **Příznak:** po ladění není jasné, jestli je to lepší, nebo horší
  - Možná příčina: chybí metrika a log „před“.
  - Co udělat: před změnou pořiďte log a metriku; do deníku zapište změnu i s výsledkem.
- **Příznak:** za měsíc není jasné, proč má parametr právě tuto hodnotu
  - Možná příčina: změna bez záznamu.
  - Co udělat: zaveďte pravidlo „není řádek v CHANGELOG – není změna“.
- **Příznak:** někdo jiný nedokáže stavbu zopakovat
  - Možná příčina: README popisuje sen, ne stroj.
  - Co udělat: README má popisovat aktuální stav a verze firmwaru; konfigurace patří do repozitáře.

## references
- Systems Engineering Handbook — NASA (free PDF) | https://www.nasa.gov/reference/systems-engineering-handbook/ | primary | A
- Requirements engineering (overview, further reading) — Wikipedia | https://en.wikipedia.org/wiki/Requirements_engineering | secondary | B
- Log Analysis and Tuning Workflow — ArduPilot (example of evidence-based tuning) | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A

## checklist
- Repozitář inženýrské složky je vytvořen
- ≥ 8 požadavků s kritériem a způsobem ověření
- Schéma napájení a dat s rozhraními je nakreslené
- Tabulka testů je provázaná s požadavky
- Deník změn se vede od první změny
