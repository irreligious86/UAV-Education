---
id: f-power
title: "Napájení: LiPo, Li-Ion, BEC"
level: L1
readingTime: 20 min
firmware: libovolný firmware
status: published
added: 2026-11-07
tags:
  - LiPo
  - Li-Ion
  - napájení
related:
  - f-physics
  - f-motors-esc
next:
  - f-motors-esc
source: content/foundation/f-power.md
source_hash: 1a74e9e76d18
---

## summary
Baterie je nejtěžší a nejnebezpečnější součást dronu. Modul vysvětluje, čím se LiPo liší od Li-Ion, co ve skutečnosti znamenají „S“, „mAh“ a „C“, proč napětí pod zátěží klesá, jak odhadnout dobu letu a jak nespálit baterii ani dílnu. Na závěr skutečný log těžkého 10" stroje, kde úbytek napětí ukázal víc než jakákoli specifikace.

## theory
### Značení
- **S** – počet článků zapojených do série. 6S = 6 článků, napětí se sčítá.
- **mAh** – kapacita. 1300 mAh = 1.3 Ah.
- **C** – vybíjecí proud vyjádřený v násobcích kapacity. 1300 mAh × 100C = 130 A podle štítku. Marketingové C je téměř vždy nadsazené, řiďte se vnitřním odporem a skutečnými testy.
- **P** – paralelně zapojené články u sad z válcových článků (6S2P = 12 článků).

### LiPo versus Li-Ion
- **LiPo:** jmenovité napětí 3.7 V/článek, plné nabití 4.2 V (LiHV – 4.35 V). Dodává obrovské proudy, ale energie na gram má méně. Pro freestyle, závody a všude, kde jsou proudy velké a let krátký.
- **Li-Ion (18650, 21700):** jmenovité napětí kolem 3.6 V, plné nabití 4.2 V, vybíjí se hlouběji – do 2.8–3.0 V. Energie na gram má znatelně víc, proudy jsou skromnější. Pro dálkové stroje 7–10", letouny a dlouhý vis při mírném plynu.

Pravidlo výběru: pokud je střední proud na článek malý (dálkový let, letoun), dá Li-Ion víc minut. Pokud potřebujete špičky v desítkách ampérů, volte LiPo.

### Úbytek napětí
Každý článek má vnitřní odpor R. Při proudu I klesne napětí o I × R. Při prudkém přidání plynu je úbytek okamžitý a řídicí jednotka nevidí „kolik zbývá“, ale „kolik zbývá minus úbytek“. Odtud falešná varování před nízkým napětím při punchi (prudkém přidání plynu naplno) a skutečná vypnutí ESC při vybité baterii.

### Doba letu
Odhad: doba v min ≈ využitelná kapacita v Ah / střední proud v A × 60. Využitelná kapacita je kolem 80 % jmenovité: vybíjet do nuly se nesmí. Střední proud berte z logu, ne z hlavy.

### BEC a palubní napětí
Řídicí jednotka, přijímač, kamera a VTX pracují s 5, 9 nebo 12 V, ne s napětím 6S. Tato napětí dodává BEC – stabilizátory napětí na řídicí jednotce nebo na ESC. Před připojením periferie zkontrolujte, z které pájecí plošky je napájena, zda stačí proud BEC (VTX na vysokém výkonu může odebírat víc než ampér) a že VTX není připojen na 5 V, pokud potřebuje 9–12 V.

### Případová studie: úbytek napětí na 10"
Log těžkého 10" stroje na 6S (baterie 23.8 V na začátku letu): medián proudu 14–16 A, ale p95 na agresivním profilu je 124 A, špička 147 A. Při těchto špičkách klesalo napětí na 16.2 V, tedy 2.7 V na článek. Závěr: při takových proudech pracuje baterie na hranici možností a ESC je třeba ověřit na trvalý proud kolem 125 A. Žádný štítek by to neřekl – řekl to log.

### Poctivý výpočet doby letu
t ≈ (kapacita × využitelný podíl) / střední proud. Podíl: 0.8 pro LiPo (přistání při 3.5 V/článek), 0.85 pro Li-Ion (do 3.0 V/článek). Střední proud berte z logu (`BAT.Curr`/`amperageLatest`), ne z visu: freestyle 5" – střední proud 25–40 A při špičkách 60–100 A; 7" long range v cestovním režimu – 8–12 A; X8 15" ve visu ~30 A. Příklad: 6S 4000 mAh Li-Ion na 7" při 10 A: 0.85 × 4 / 10 × 60 ≈ 20 min. Kontrola po letu: dobité mAh se musí shodovat s `CurrTot`/mAh drawn v logu na ±10 % – jinak je senzor proudu zkalibrován špatně (`BATT_AMP_PERVLT`, `ibata_scale`).

### Úbytek napětí a vnitřní odpor v číslech
U pod zátěží = E − I·R. „Čerstvá“ LiPo 6S 1300 mAh 100C: R ≈ 2 mΩ/článek → 12 mΩ na celou baterii; při 80 A je úbytek 1 V (4.0 → 3.84 V/článek). Stejná baterie po 150 cyklech má 6 mΩ/článek → 36 mΩ → úbytek 2.9 V: proto „staré“ baterie vyvolají varování v OSD hned při prvním punchi. Li-Ion 6S4P P42A ≈ 40–50 mΩ na celou baterii: při 60 A je to 2.4–3 V, jako by se „ztratil“ jeden článek; prahy varování se proto nastavují podle napětí **pod zátěží** nebo podle mAh. Teplo: 60 A × 60 A × 0.045 Ω = 160 W v baterii – Li-Ion se zahřívá citelně; LiPo 100C – 80 × 80 × 0.012 = 77 W. Podrobnosti (chemie, sady článků, BMS) najdete v modulu „Sady článků Li-Ion“.

### Nabíjení, skladování, likvidace
Nabíjení s balancováním proudem 1C (LiPo) / Li-Ion standardním proudem z datasheetu článku (Molicel P42A: 4.2 A = 1C, CC-CV do 4.2 V, nabíjení při 0–45 °C), bez datasheetu 0.5C, do 4.2 V/článek (při 4.1 V vydrží baterie déle); skladování při 3.8 V/článek (LiPo) / 3.6–3.7 V (Li-Ion), plně nabitou baterii nenechávejte déle než den; rozdíl mezi články po nabití ≤ 0.02 V, po letu ≤ 0.05 V – větší rozdíl znamená slabý článek; vnitřní odpor (IR) jednotlivých článků, který ukazuje nabíječka, slouží jako „zdravotní průkaz“ baterie; nafouknutou nebo proraženou baterii vyřaďte (vybití přes zátěž na ~0 V, ne slaná voda — postup v `f-power`, odevzdání k likvidaci). V zimě: LiPo pod 10 °C ztrácí až 30–50 % výkonu – před letem ji ohřejte na 20–25 °C (orientační hodnota kurzu, jako v `ops-weather`).

### Větve BEC: proudový rozpočet
Součet na 5 V: FC 0.2 + RX 0.2 + GPS 0.1 + LED 0.5 ≈ 1 A → BEC 5 V/2–3 A na desce stačí; přidáte-li Raspberry Pi (2–3 A), stačit nebude a je potřeba samostatný BEC. 9–12 V: digitální air unit 0.8–1.2 A → BEC 9 V/2 A na FC je při zahřátí na hraně; se samostatným BEC 3 A budete klidnější. Všechna čísla zapište do pasportu stavby (modul „Návrh palubního napájení“).

{{diagram:flight-time-chain|Poctivý výpočet doby letu: využitelný podíl kapacity, střední proud přes celý profil letu, korekce na podmínky.}}

{{diagram:chart-discharge|Vybíjecí křivky: pod zátěží klesne napětí článku o I·R, proto LiPo při 40C narazí na 3.5 V dříve a Li-Ion při 3C ztratí znatelnou část kapacity ještě před odpojením. Tvar křivek je typický, odpory jsou z příkladů v modulu.}}

## practice
### Bezpečná práce s LiPo
1. Nabíjejte proudem 1C, na nehořlavém podkladu, pod dohledem a s balancováním.
2. Skladujte při napětí kolem 3.8 V/článek (režim Storage na nabíječce). Plně nabitá baterie ležící týdny na polici degraduje a nafukuje se.
3. Nafouknutá nebo proražená baterie a baterie s poškozeným obalem se vyřazuje z provozu.
4. Přepravujte v ohnivzdorném vaku nebo boxu.
5. Po tvrdém pádu baterii odložte a před nabíjením ji nějakou dobu pozorujte.

### Laboratorní úloha: spočítat dobu letu a porovnat ji s logem
1. Vezměte kapacitu baterie a střední proud z logu Blackbox nebo DataFlash.
2. Spočítejte odhad: 0.8 × kapacita v Ah / proud × 60.
3. Porovnejte ho se skutečnou dobou letu do varování před nízkým napětím.
4. Najděte v logu minimální napětí pod zátěží a přepočítejte ho na článek.

### Nastavení hlídání napětí
V Betaflightu zkontrolujte podle multimetru měřítko senzoru napětí a proudu (Power & Battery) a nastavte varování v OSD tak, abyste přistávali s rezervou, a ne až na signál „už je pozdě“.

## diagnostics
- **Příznak:** varování před nízkým napětím při každém punchi
  - Možná příčina: úbytek napětí pod proudem, stará baterie s vysokým vnitřním odporem.
  - Co udělat: sledovat klidové napětí po letu, změřit vnitřní odpor nabíječkou.
- **Příznak:** doba letu je výrazně kratší než vypočtená
  - Možná příčina: střední proud je vyšší, než se zdálo, nebo baterie ztratila kapacitu.
  - Co udělat: vzít střední proud z logu, ověřit kapacitu nabíjecím cyklem.
- **Příznak:** VTX nebo kamera se při přidání plynu restartují
  - Možná příčina: úbytek napětí na větvi BEC nebo napájení z nevhodné pájecí plošky.
  - Co udělat: zkontrolovat napájecí plošku, přidat kondenzátor na silovou větev, ověřit proud BEC.
- **Příznak:** baterie je po letu teplá a nafouknutá
  - Možná příčina: proudové přetížení.
  - Co udělat: vyřadit baterii z provozu, přehodnotit kapacitu a C podle skutečného proudu.

## references
- Betaflight App — tabs reference (Power & Battery) | https://betaflight.com/docs/wiki/app | primary | A
- Battery Monitors — ArduPilot Copter | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- LiPo Battery Guide — Oscar Liang | https://oscarliang.com/lipo-battery-guide/ | secondary | B

## checklist
- Rozumím rozdílu mezi S, P, mAh a C
- Vím, kdy zvolit Li-Ion a kdy LiPo
- Mám spočítanou dobu letu a porovnanou s logem
- Mám měřítko senzoru napětí ověřené multimetrem
- Baterie jsou uloženy při skladovacím napětí (storage) a v ohnivzdorném obalu
