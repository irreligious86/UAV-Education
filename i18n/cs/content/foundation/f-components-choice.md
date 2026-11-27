---
id: f-components-choice
title: "Výběr komponent podle úkolu a rozpočtu"
level: L1
readingTime: 35 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - komponenty
  - specifikace
  - rozpočet
  - výběr
related:
  - f-aero-props
  - f-power
  - f-motors-esc
  - eng-method-101
next:
  - eng-method-101
source: content/foundation/f-components-choice.md
source_hash: 80945e456a7c
---

## summary
Osmdesát procent skutečné inženýrské práce není nastavování, ale výběr: co koupit, aby stroj plnil úkol, vešel se do rozpočtu a nerozpadl se. Modul dává metodu: úkol v číslech → třída stroje → rám a vrtule → motory a ESC → baterie → FC a periferie → kontrola hmotnosti a T/W → dvě alternativy. S kalkulačkou T/W a doby letu a s rozborem dvou specifikací: 7" na dálkové lety a nákladní 10".

## theory
### Krok 0: úkol v číslech
Dokud úkol zní „chci létat daleko“, není z čeho vybírat. Jsou potřeba čísla:

| Parametr | Příklad: 7" na dálkové lety | Příklad: nákladní 10" |
|---|---|---|
| Užitečné zatížení | kamera 30 g | náklad 1000 g |
| Doba letu | ≥ 15 min | ≥ 12 min s nákladem |
| Dosah | 5 km | 1 km |
| Cestovní rychlost | 15–20 m/s | 8 m/s |
| Podmínky | vítr do 8 m/s | vítr do 6 m/s |
| Rozpočet | 400 € | 700 € |
| Omezení | hmotnost < 1 kg (kategorie) | skládací |

Každé číslo se stane požadavkem s ID v inženýrské složce (následující modul).

### Krok 1: třída a rám
Velikost vrtule určuje všechno ostatní. Pravidlo: hmotnost nákladu a doba letu určují potřebnou účinnost (g/W), účinnost určuje průměr vrtule (modul o aerodynamice): 5" – 4–6 g/W, 7" – 8–10, 10" – 12–15, 15" – 15–20. Dlouhý vis s nákladem znamená velké vrtule; rychlost a obratnost malé.

Rám: karbon 4–5 mm na ramenech pro 5" (rezonance ramene 300–500 Hz — nad harmonickými motorů ve visu), 5–6 mm nebo trubky pro 10" a větší. U 7" rezonuje 5mm rameno na 150–250 Hz, v pásmu harmonických visu (`f-frame-mech`), a 6 mm místo 5 zvedne frekvenci jen o ~20 %. Pravidlo pro 7": po sestavení poklepový test ramene (`f-frame-mech`); shoda s 1. nebo 2. harmonickou visu — statický notch nebo jiné místo uchycení motoru. Sledujte: hmotnost, volné místo pro baterii a náklad, ochranu elektroniky, dostupnost náhradních dílů (rameno se musí dát koupit samostatně), stack 20×20 nebo 30.5×30.5 mm.

### Krok 2: motory a vrtule
Z tabulky tahu výrobce pro zvolenou vrtuli a napětí: tah ve visu má vycházet na 30–45 % plynu (rezerva na vítr a manévry) při proudu nejvýše 40 % trvalého proudu. Velikost motoru a KV: 7" – 2806.5/2807 1300–1700 KV na 6S; 10" – 3110/3115 600–900 KV na 6S; 15" – 4008–4114 320–400 KV na 6S. Hmotnost motorů se započítá do hmotnostního rozpočtu.

{{diagram:component-choice-tree|Orientační hodnoty pohonné jednotky pro typické třídy strojů.}}

### Krok 3: ESC
Trvalý proud ESC ≥ 1.3 × maximální proud motoru z tabulky; napětí s rezervou (6S → ESC na 6S, ne „do 6S“ na hraně). 4v1 je kompaktní, ale jedna nehoda znamená výměnu celku; samostatné ESC se dají opravit, je ale nutné k nim rozvést napájení. Firmware (BLHeli_32/AM32/BLHeli_S) určuje telemetrii a RPM filtr.

### Krok 4: baterie
Kapacita z proudu: I_stř (z tabulky pro cestovní let nebo vis × počet motorů + palubní elektronika) × t / 0.8. Chemie: LiPo dává proud, Li-Ion energii na kilogram (ale snese jen malé proudy: katalogový trvalý proud 21700 je 3–10C na článek a kvůli ohřevu se průměrný proud drží nejvýš na 1.5C, `el-battery-packs`). Kontrola: vejde se hmotnost baterie do hmotnostního rozpočtu? Pokud ne, následuje iterace: těžší baterie → větší proud → ještě větší baterie. Tento cyklus nekonverguje vždy; pokud nezkonvergoval, změňte třídu.

### Krok 5: FC, přijímač, video, GPS
FC: F4 stačí pro Betaflight bez zbytečností, F7/H7 pro INAV/ArduPilot s GPS, kompasem a logy; počet UART ≥ počet připojených zařízení + 1; blackbox (flash/SD) pro ladění podle logů. Přijímač: ELRS, pásmo podle úlohy (`link-elrs`, výběr režimu podle úlohy): freestyle, závody, přímá viditelnost — 2.4 GHz; křídlo, les, dlouhé trasy — 900 MHz (delší vlna lépe obchází překážky a prochází listím; cenou je delší anténa a regulační doména vaší země); dálkové 7–10" — 2.4 GHz 150 Hz nebo 900 MHz 100 Hz. Video podle úlohy (`link-digital-video`, „Jak vybírat“): závody a létání ve skupině — analog nebo HDZero, freestyle a natáčení — DJI nebo Walksnail, dálkové lety na autopilotu — digitál plus samostatný RC link a OSD. GPS: s kompasem na stožárku pro INAV/ArduPilot.

### Krok 6: hmotnostní rozpočet a kontrola
Tabulka: díl, hmotnost, cena. Výsledek: vzletová hmotnost → T/W podle tabulky motoru → proud ve visu → doba letu → porovnání s požadavky. Pravidlo: je-li T/W < 2 při plném zatížení, předělat. Rezerva v rozpočtu 15 % na vrtule, spojovací materiál, vodiče, opravy.

### Kompromisy
- **Cena vs. hmotnost**: levné komponenty jsou těžší; hmotnost znamená dobu letu a proud.
- **Opravitelnost**: stroj z drobných, dostupných dílů vydrží déle než exotika.
- **Rezerva**: 20 % v proudu a tahu se vyplatí hned první větrný den.
- **Dostupnost**: díl, který za půl roku není skladem, je problém při první opravě.

Kalkulačka níže počítá T/W, proud ve visu a dobu letu z vašich čísel – použijte ji v kroku 6.

## practice
{{widget:tw-calc}}

### Krok 1. Požadavky
Tabulka úkolu v číslech pro vlastní nápad na stroj (jako v teorii), 8–12 řádků.

### Krok 2. Specifikace
Tabulka komponent: model, hmotnost, cena, odkaz na zdroj dat (tabulka tahu, datasheet). Součet hmotnosti a ceny.

### Krok 3. Výpočet
Kalkulačkou: T/W, plyn ve visu, proud, doba letu. Porovnejte s požadavky a zapište, které jsou splněny.

### Krok 4. Alternativy
Dvě varianty (například 7" Li-Ion vs. 7" LiPo; nebo 10" kvadrokoptéra vs. 7" s menším nákladem) v jedné tabulce podle kritérií: doba letu, cena, hmotnost, opravitelnost, riziko. Výběr zdůvodněte.

### Řešený výpočet
Výchozí hodnoty kalkulačky: hmotnost 1400 g, 4 motory po 1200 g maximálního tahu, 6.5 g/W ve visu, 6S 4000 mAh, palubní elektronika 0.8 A.
- T/W = 4 · 1200 / 1400 = 3.43, plyn ve visu ≈ 1 / 3.43 ≈ 29 % – v lineárním přiblížení „tah ∝ plyn“; tah roste rychleji než plyn (T ∝ n²), proto je skutečný plyn ve visu vyšší: při křivce `MOT_THST_EXPO = 0.65` kolem 45 %.
- Výkon motorů ve visu: 1400 g / 6.5 g/W ≈ 215 W; proud 215 / (6 · 3.7) + 0.8 ≈ 10.5 A.
- Vis na 80 % kapacity: 4 · 0.8 / 10.5 · 60 ≈ 18 minut. Při letu s manévry a větrem o 20–40 % méně.
- Po přidání 400 g nákladu (1800 g): T/W 2.67, plyn 38 %, proud 13.3 A, vis ≈ 14.5 minuty. To je cena každého gramu v minutách letu.

### Co zapsat a jak se zkontrolovat
- **Tabulka požadavků:** každý řádek má číslo a jednotku. „Létá dlouho“ není požadavek, „≥ 15 minut visu s nákladem 300 g“ požadavek je.
- **Specifikace:** každá komponenta má zdroj čísel: tabulku tahu výrobce, datasheet, vážení. Hmotnost bez vodičů, konektorů a spojovacího materiálu je podhodnocená o 5–10 %, to je nutné přidat samostatným řádkem.
- **Výpočet:** vyznačte, které požadavky jsou splněny, které ne a o kolik. Je-li T/W pod 2, nemá stroj rezervu na vítr a manévry – mění se specifikace, ne požadavek.
- **Alternativy:** tabulka se 4–6 kritérii, vahami a výsledkem. Výběr je zdůvodněn čísly, ne slovem „líbí se mi“.

### Laboratorní úloha
Specifikace s požadavky, výpočtem a porovnáním dvou alternativ – první dokument inženýrské složky.

Laboratorní úloha je splněna, když jsou požadavky zapsány čísly, specifikace obsahuje ceny, hmotnosti a zdroje dat, T/W a doba letu jsou spočítány se započtením vodičů a spojovacího materiálu a dvě alternativy jsou porovnány podle kritérií se zdůvodněným výběrem.

## diagnostics
- **Příznak:** výpočet doby letu nevychází: baterie roste, doba letu neroste
  - Možná příčina: cyklus hmotnost → proud → hmotnost diverguje; třída stroje je na daný úkol malá.
  - Co udělat: zvolte větší vrtuli a rám, nebo snižte požadavky.
- **Příznak:** T/W je na papíře 3, ale stroj visí na 60 % plynu
  - Možná příčina: tabulka tahu platí pro jiné napětí nebo vrtuli; skutečná hmotnost je vyšší.
  - Co udělat: stroj znovu zvažte, přepočítejte podle vlastní tabulky, zkontrolujte napětí při zátěži.
- **Příznak:** nestačí počet UART pro všechny periferie
  - Možná příčina: FC byl vybrán bez spočítání portů.
  - Co udělat: zvolte FC s větším počtem UART nebo slučte funkce (například telemetrie ESC přes jeden port).
- **Příznak:** rozpočet je překročen dvojnásobně
  - Možná příčina: nejsou započteny vrtule, spojovací materiál, nabíječka, náhradní díly.
  - Co udělat: počítejte s rezervou 15–20 % v rozpočtu, nepovinné položky (digitální video) odložte na další iteraci.

## references
- Choosing a MultiCopter Frame — ArduPilot Copter | https://ardupilot.org/copter/docs/choosing-a-frame.html | primary | A
- UIUC Propeller Database (efficiency data by diameter) | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- How to choose motors for FPV drones — Oscar Liang | https://oscarliang.com/quadcopter-motor-propeller/ | secondary | B

## checklist
- Úkol je zapsán v číslech, ne slovy
- Průměr vrtule je zvolen podle požadované účinnosti
- Motory jsou vybrány podle tabulky tahu: vis na 30–45 % plynu
- Baterie je spočítána z proudu a doby letu, hmotnost vyšla
- Dvě alternativy jsou porovnány, výběr je zdůvodněn
