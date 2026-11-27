---
id: f-electricity-101
title: "Elektřina a měření 101"
level: L1
readingTime: 30 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - elektřina
  - Ohmův zákon
  - multimetr
  - LiPo
related:
  - f-power
  - el-power-design
  - el-measure
next:
  - f-power
source: content/foundation/f-electricity-101.md
source_hash: ad65d5a7349e
---

## summary
Můstek mezi „jak to létá“ a „návrhem napájecích obvodů“. Bez něj člověk jen opakuje cizí řešení: osadí kondenzátor, protože „se to tak dělá“, a nechápe, proč je BEC horký. Modul dává minimum, se kterým už lze počítat: Ohmův zákon, výkon, sériové a paralelní zapojení, řetězec tah → výkon → proud → úbytek napětí ve vzorcích, bezpečnou práci s multimetrem a pravidla zacházení s LiPo – nabíjení, skladování, poškození, požár.

## theory
### Tři veličiny a dva vzorce
- **Napětí U** (volty) – „tlak“ v obvodu. Baterie 4S má 14.8 V jmenovitě a 16.8 V plně nabitá.
- **Proud I** (ampéry) – „průtok“. Motor 5" odebírá při plném plynu 30–40 A.
- **Odpor R** (ohmy) – to, co průtoku brání. Vinutí motoru má zlomky ohmu, vodič miliohmy.

**Ohmův zákon: U = I·R.** Teče-li odporem 10 mΩ (vodič + konektor) proud 60 A, vzniká na něm úbytek 0.6 V. **Výkon P = U·I = I²·R = U²/R** (watty). Stejných 60 A na 10 mΩ znamená 36 W tepla ve vodiči a konektoru. Proto je proud hlavní nepřítel: ztráty rostou s druhou mocninou proudu.

### Sériově a paralelně
- **Sériově (S)**: napětí se sčítají, proud je společný. 6 článků po 3.7 V = 22.2 V (6S). Odpory se také sčítají.
- **Paralelně (P)**: proud se dělí, napětí je společné, kapacita se sčítá. 4 články po 3 Ah = 12 Ah (4P); vnitřní odpor se dělí čtyřmi.
Články 18650 s 3 Ah a 30 mΩ v sadě 6S4P: 22.2 V, 12 Ah, R_i = 30 × 6 / 4 = 45 mΩ.

### Řetězec od tahu k úbytku napětí
1. Je potřeba tah T (z mechaniky: m·g ve visu).
2. Z tabulky motoru: tah → výkon P_mech a proud I_motoru při napětí U.
3. Proud baterie ≈ ΣI_motorů + ostatní spotřebiče (ESC proud propouštějí, nenásobí ho; při částečném plynu je ale proud baterie menší než fázový proud motoru – ESC pracuje jako snižující měnič).
4. Úbytek napětí ΔU = I·(R_i_baterie + R_vodičů + R_konektorů). Při zátěži platí U_paluby = U_0 − ΔU, kde U_0 je napětí naprázdno.
5. Výkon, který baterie dodává: P = U_paluby·I; ztráty P_ztr = I²·R_celk zahřívají baterii a vodiče.

Příklad: nákladní 10", 4 × 5 A = 20 A ve visu, R_i baterie 6S Li-Ion 4P je 45 mΩ, vodiče a XT60 15 mΩ → ΔU = 20 × 0.06 = 1.2 V, ztráty 24 W. Při plném plynu 100 A → ΔU = 6 V (!) a 600 W ztrát – Li-Ion není na závody.

### Energie a kapacita
Kapacita v Ah (nebo mAh) říká, kolik proudu po kolik hodin. Energie Wh = Ah × U_nom. 6S 4 Ah = 88.8 Wh. Při středním výkonu 300 W je to teoreticky 0.3 h = 18 min, ~14 min s ohledem na využitelných 80 %. **Hodnocení C (C-rating)** je maximální proud v násobcích kapacity: 4 Ah × 25C = 100 A. Skutečné hodnoty bývají nižší než údaj na štítku; sledujte úbytek napětí při zátěži.

### Multimetr: co a jak
- **Napětí (V⎓)**: hroty paralelně k měřenému místu; černý do COM, červený do V. Bezpečné téměř vždy. Kontrola baterie: celkové napětí a každý článek přes balanční konektor (prahy rozptylu jsou na jednom řádku v `f-power`: po nabití ≤ 0.02 V, po letu ≤ 0.05 V, po nabití a odpočinku víc než 0.05 V — vyřadit).
- **Test spojitosti (•)))**: jen na obvodu bez napětí. Pípnutí mezi + a − napájecí větve = zkrat. U obvodu s kondenzátorem může být pípnutí krátké a odpor potom roste – to je v pořádku.
- **Odpor (Ω)**: bez napětí. Vinutí motoru – tři stejné hodnoty (0.05–0.3 Ω; levný multimetr ukáže šum – důležitá je shoda hodnot). Rozdíl znamená mezizávitový zkrat.
- **Proud (A)**: hroty *sériově*, červený do zdířky 10 A; nad 10 A se měřit nesmí (shoří pojistka nebo přístroj). Hlavní chyba začátečníka: nechat hrot ve zdířce A a změřit napětí – to je zkrat přes přístroj. Proud celého stroje se měří proudovým senzorem FC (kalibruje se) nebo wattmetrem zapojeným do série s baterií.
- **Test diod**: kontrola diod a přechodů – bude se hodit později.

### LiPo: pravidla, o kterých se nediskutuje
- Napětí na článek: plně nabitý 4.20 V (HV – 4.35), jmenovité 3.7, skladovací 3.80–3.85, minimum při zátěži ~3.3–3.5, pod 3.0 dochází k poškození.
- **Nabíjení**: jen nabíječkou s balancováním, proudem ≤ 1C (4 Ah → 4 A), pokud výrobce nepovoluje víc; v LiPo vaku nebo na nehořlavém povrchu; nenechávejte bez dozoru; nenabíjejte studenou (< 5 °C) ani horkou baterii.
- **Skladování**: při skladovacím napětí, v chladu; plně nabitou baterii neskladujte déle než den – ztrácí kapacitu a nafukuje se.
- **Poškození**: nafouknutí, proražení, zápach – taková baterie už nelétá. Vybijte ji na 0 přes zátěž (vybíječ nebo rezistor; ne slaná voda — postup v `f-power`) a zlikvidujte podle předpisů. Po pádu dronu položte baterii na 30 minut na otevřené nehořlavé místo.
- **Požár**: LiPo hoří sama a hasí se špatně. Plán mějte předem: kbelík písku, místo, kam baterii vyhodit, nevdechujte kouř. Velké množství vody chladí a u LiPo je přípustné (kovové lithium v ní není), ale nejlepším nástrojem je prevence: správné nabíjení, prohlídka, vak.
- **Zkrat**: zkratový proud jsou stovky ampérů, konektor se svaří za zlomek sekundy. Napájecí konektor pájejte vždy jen po jednom kontaktu, nářadí izolujte, XT60 nepokládejte na kov.

{{diagram:thrust-sag-chain|Řetězec od tahu k úbytku napětí: větší tah – větší proud, větší úbytek na vnitřním odporu, nižší napětí při zátěži.}}

## practice
{{widget:wire-drop}}

### Krok 1. Pasport elektriky
Tabulka: U_0 baterie, napětí každého článku, výstup BEC 5 V a 9 V (bez zátěže a s připojenou palubní elektronikou), odpor tří fází každého motoru.

### Krok 2. Výpočet proudu ve visu
Podle tabulky motoru: tah na motor ve visu → proud → ×4 + 1 A na palubní elektroniku. Zapište. R_i baterie: z dokumentace, nebo změřte: U_0 − U při zátěži známým proudem, děleno tímto proudem.

### Krok 3. Porovnání
Po visu odečtěte střední proud z logu (proudový senzor musí být zkalibrovaný podle wattmetru). Rozdíl a jeho příčinu zapište do pasportu.

### Krok 4. Kontrolní seznam LiPo
Vlastní kontrolní seznam na jednu stránku: nabíjení, skladování, prohlídka, co dělat po pádu, kde je písek. Připevněte ho u nabíjecího místa.

### Orientační hodnoty a řešený příklad
- **Články LiPo:** 4.20 V je plné nabití, 3.80–3.85 V skladování. Po balancování je rozdíl mezi články ≤ 0.02 V; po nabití a odpočinku od 0.03 V — sledovat, víc než 0.05 V — vyřadit (orientační hodnota kurzu, `f-power` a modul „Údržba“).
- **BEC:** 5 V má být s připojenou palubní elektronikou v rozmezí přibližně ±5 % (4.75–5.25 V). Pokud napětí při zátěži znatelně klesá, je BEC proudově poddimenzovaný.
- **Vnitřní odpor baterie:** bez zátěže 25.2 V, při proudu 20 A 24.4 V → R = (25.2 − 24.4) / 20 = 0.04 Ω na baterii 6S, ≈ 6.7 mΩ na článek. Při proudu ve visu bude úbytek úměrně menší.
- **Vinutí motorů:** odpor fází jsou desetiny a setiny ohmu a běžný multimetr ho měří špatně: hroty a přechodový odpor dávají srovnatelnou chybu. Porovnávejte tři fáze jednoho motoru mezi sebou: musí se shodovat. Špatně připájený vývod zvýší hodnotu u obou dvojic s tímto vývodem; jedna dvojice, která se liší od zbylých dvou, znamená poškozené vinutí (mezizávitový zkrat); „přerušení“ znamená přerušené vinutí nebo vývod. Přesnější je pustit vinutím známý proud z laboratorního zdroje (například 1 A) a změřit úbytek napětí.

### Co má při porovnání vyjít
Vypočtený proud ve visu a střední proud z logu se liší o 10–20 % – to je normální: tabulka motoru byla změřena s jinou vrtulí, při jiné teplotě a jiném napětí. Při rozdílu nad 30 % zkontrolujte kalibraci proudového senzoru podle wattmetru a hmotnost stroje.

### Laboratorní úloha
Pasport elektriky stroje (krok 1), výpočet proudu ve visu s porovnáním (kroky 2–3), kontrolní seznam LiPo (krok 4).

Laboratorní úloha je splněna, když jsou napětí každého článku a výstupů BEC změřena a zapsána, proud ve visu je spočítán a porovnán s logem včetně vysvětlení rozdílu, tři fáze každého motoru se shodují a kontrolní seznam pro skladování a nabíjení LiPo visí u nabíjecího místa.

## diagnostics
- **Příznak:** multimetr shořel nebo se při měření přepálila pojistka
  - Možná příčina: hrot ve zdířce A při měření napětí.
  - Co udělat: vyměňte pojistku; pravidlo: po měření proudu hrot ihned vraťte do zdířky V.
- **Příznak:** jeden článek baterie je o 0.1 V nebo víc níž než ostatní
  - Možná příčina: degradace článku, nevyvážené články.
  - Co udělat: nabijte s balancováním; pokud se to opakuje, baterii uskladněte nebo zlikvidujte, nelétejte s ní.
- **Příznak:** XT60 je po letu horký
  - Možná příčina: přechodový odpor kontaktu: I²·R.
  - Co udělat: vyměňte konektor, zkontrolujte pájení.
- **Příznak:** doba letu je poloviční proti výpočtu podle kapacity
  - Možná příčina: výpočet podle jmenovité kapacity, skutečná kapacita je menší (stáří, chlad), proud je vyšší.
  - Co udělat: změřte dodanou kapacitu nabíječkou a střední proud z logu.
- **Příznak:** odpory fází motoru se liší
  - Možná příčina: mezizávitový zkrat nebo poškozený vodič.
  - Co udělat: vyměňte motor; zkontrolujte, zda se nezahřívá víc než ostatní.

## references
- Battery Safety — INAV documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- LiPo Battery Basics: Safe Use — Academy of Model Aeronautics (Model Aviation) | https://www.modelaviation.com/lipo1 | secondary | B
- Battery Monitor configuration and calibration — ArduPilot | https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html | primary | A

## checklist
- Umím použít U = I·R a P = U·I na obvody stroje
- Chápu, proč ztráty rostou s druhou mocninou proudu
- Napětí a odpor měřím bezpečně a bezpečně testuji spojitost obvodu
- Znám napětí LiPo: plně nabitý článek, skladování, minimum
- Kontrolní seznam LiPo je sepsán a leží u nabíjecího místa
