---
id: f-aero-props
title: "Aerodynamika vrtule a výběr pohonné jednotky"
level: L2
readingTime: 30 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - vrtule
  - tah
  - pohonná jednotka
related:
  - f-physics
  - f-motors-esc
  - f-power
next:
  - f-frame-mech
source: content/foundation/f-aero-props.md
source_hash: 7d1695cc2385
---

## summary
Vrtule je jediná součást, která mění elektřinu v let, a jediná, kterou začátečníci vybírají „podle obrázku“. Modul podává fyziku na úrovni, která stačí k vědomému výběru: odkud se bere tah, proč je velká pomalá vrtule účinnější než malá rychlá, co je stoupání a účinnost, jak číst tabulky tahu od výrobce a jak vybrat kombinaci motor–vrtule–baterie pro požadovaný T/W a dobu letu. Včetně výpočtu na příkladu 7" stroje a X8.

## theory
### Aktuátorový disk: odkud se bere tah
Nejjednodušší model: vrtule je disk o ploše A, který urychluje vzduch z rychlosti V₀ (nabíhající proud) na Vₑ (za diskem). Tah je změna hybnosti vzduchu za sekundu:

{{diagram:actuator-disk|Aktuátorový disk: tah je změna hybnosti proudu; výkon roste rychleji než tah.}}

**F = ½ · ρ · A · (Vₑ² − V₀²)**, kde ρ je hustota vzduchu (≈1.225 kg/m³ u země).

Ve visu je V₀ = 0 a tah roste s druhou mocninou rychlosti odhazovaného vzduchu. Důsledky:

- **Velký disk je výhodnější.** Pro stejný tah odhazuje velká vrtule hodně vzduchu pomalu, malá málo vzduchu rychle. Kinetická energie ~ V², hybnost ~ V: při stejném tahu je výkon na malé vrtuli vyšší. Proto dálkové a nákladní stroje létají s velkými pomalými vrtulemi.
- **Na hustotě vzduchu záleží.** Na horách a v horku je ρ menší – tah při stejných otáčkách klesá; stroj, který v nížině sotva visel, na horách nevzlétne.
- Model je ideální: skutečné ztráty (koncové víry, profilový odpor listu, rotace proudu) účinnost snižují.

### Stoupání, průměr a značení
„5×4.3×3“ = průměr 5", stoupání 4.3", 3 listy. **Stoupání** udává, o kolik se vrtule za jednu otáčku „zašroubuje“ do vzduchu bez skluzu. Větší stoupání znamená větší rychlost proudu a tah na otáčku, ale také větší moment a proud. Víc listů znamená víc tahu ze stejného průměru za cenu účinnosti.

### Bezrozměrné součinitele
Výrobci a databáze (UIUC) popisují vrtuli pomocí těchto veličin:

- **Cₜ = T / (ρ·n²·D⁴)** – součinitel tahu (n – otáčky v ot/s, D – průměr v m);
- **Cₚ = P / (ρ·n³·D⁵)** – součinitel výkonu;
- **J = V / (n·D)** – rychlostní poměr (poměr rychlosti letu k rychlosti vrtule);
- **η = J·Cₜ/Cₚ** – účinnost za letu (ve visu je J = 0 a mluví se o statické účinnosti v g/W).

Praktický závěr ze vzorců: tah ~ n², výkon ~ n³. **Ke zdvojnásobení tahu je potřeba 1.41krát víc otáček a 2.8krát víc výkonu.** Právě proto je „přidat plyn“ tak drahé na proud.

### Motor + vrtule: pracovní bod
Motor určuje otáčky přes KV a napětí, vrtule zátěž. Pracovní bod je tam, kde se moment motoru rovná momentu odporu vrtule. Výrobci motorů zveřejňují tabulky: vrtule, napětí, plyn → tah (g), proud (A), výkon (W), g/W. Je to hlavní dokument při výběru.

Čím vyšší KV při stejné vrtuli, tím vyšší otáčky, tah i proud. Přehnaná volba znamená přehřátí vinutí a ESC. Pravidlo: velká vrtule – nízké KV (10": 600–900 KV na 6S), malá – vysoké (5": 1700–2300 KV na 6S).

### Účinnost ve visu
Statická účinnost v g/W je klíčový ukazatel pro dobu letu. Typické hodnoty: závodní 5" ~4–6 g/W ve visu, 7" ~8–10, 10–15" ~10–14 (až 15–20 při malém podílu maximálního tahu). Čím vyšší g/W, tím delší vis se stejnou baterií.

### Koaxiální dvojice a letouny
U X8 pracuje spodní vrtule ve zrychleném rotujícím proudu od horní vrtule: celkový tah dvojice je nižší než dvojnásobek tahu samostatné vrtule (orientačně ztráta 10–20 %). U letounu pracuje vrtule při J > 0 a je třeba ji vybírat pro cestovní rychlost, ne pro vis: statická účinnost tam téměř nehraje roli.

{{diagram:chart-thrust-current|Tah roste s druhou mocninou otáček, proud s třetí: při polovičním plynu 375 g při 5 A (3.4 g/W), při plném 1500 g při 40 A (1.7 g/W). Model T ∝ n², I ∝ n³; skutečný motor posuzujte podle tabulky tahu od výrobce.}}

## practice
{{widget:tw-calc}}

### Krok 1. Co je k výpočtu potřeba
1. Vzletová hmotnost m (všechno, co letí).
2. Cílový T/W (2:1 nákladní, 3–4:1 dálkový, 6+:1 freestyle).
3. Tabulka tahu kandidátů motor + vrtule při vašem napětí.

### Krok 2. Výpočet na příkladu 7" stroje o hmotnosti 1.4 kg
- Potřebný tah ve visu: 1400 g / 4 motory = 350 g na motor.
- T/W 3:1 → maximum 1050 g na motor.
- Podle tabulky motoru 2806.5 1300KV s vrtulí 7×3.5 na 6S: maximum ~1200 g při ~22 A → vyhovuje. Při 350 g je to asi 2.5–3 A a ~55–65 W na motor (≈6 g/W; přesné číslo dá jen tabulka vašeho motoru).
- Proud ve visu: 4 × 3 + 1 A palubní elektronika = 13 A. Baterie 6S 4000 mAh Li-Ion: 0.8 × 4 / 13 × 60 ≈ 15 min čistého visu; s manévry a větrem o 20–40 % méně. Pokud je to málo, použijte vrtuli 7×4 (na tomto motoru má vyšší g/W) nebo větší kapacitu a přepočítejte hmotnost.

### Krok 3. X8 s motory třídy 4008/4006 380KV (tabulka MN4006)
- Hmotnost 6 kg, osm motorů, ale koaxiální ztráty ~15 %: efektivní tah dvojice počítejte jako 1.7násobek tahu samostatného motoru.
- Ve visu je potřeba 6000 g / (4 dvojice × 1.7) ≈ 880 g na motor.
- Podle tabulky T-Motor MN4006 380KV s vrtulí 15×5 CF při 24 V: 805 g při 3.1 A (74 W), 959 g při 4.1 A (98 W), maximum 2228 g při 15 A (T/W ≈ 2228 × 1.7 × 4 / 6000 ≈ 2.5 – pro nákladní stroj stačí). Interpolace na 880 g: ~3.6 A, ~86 W, ≈10 g/W, ~52 % plynu na měřicí stolici, ~3900 ot/min.
- Tabulka byla změřena při 24 V, kdežto 6S Li-Ion má jmenovitě 22.2 V: výkon pro stejný tah je téměř stejný, proud je 24 / 22.2 ≈ 1.08krát vyšší → ~3.9 A na motor.
- Proud ve visu ≈ 8 × 3.6–3.9 ≈ 29–31 A, počítáme ~30 A včetně palubní elektroniky. Li-Ion 6S 20 Ah → 0.8 × 20 / 30 × 60 ≈ 32 min.
- Vlastní kontrola podle g/W: 880 g / 86 W ≈ 10 – dolní hranice pro 15". Pokud vám na 15" vyšlo 5–6 g/W, je chyba v proudu nebo v tabulce.
- Po prvním visu porovnejte se skutečným logem `CTUN.ThH` a `BAT.Curr`: odchylka větší než 20 % znamená chybu v hmotnosti nebo v tabulce.

### Krok 4. Kontrola přehřívání
Trvalý proud motoru ve visu musí být výrazně nižší než maximální proud z tabulky (orientačně ≤ 40 %). Kontrola po 5 minutách visu: motor je teplý, ne horký.

### Laboratorní úloha
Proveďte kroky 1–3 pro svou stavbu se dvěma variantami vrtulí, jednu vyberte a volbu zdůvodněte čísly; po letu porovnejte vypočtený proud ve visu s logem.

## diagnostics
- **Příznak:** vis při plynu nad 60 %
  - Možná příčina: T/W je příliš nízký – vrtule je malá, KV nízké nebo vzrostla hmotnost.
  - Co udělat: přepočítat podle tabulky, použít vrtuli s větším průměrem nebo stoupáním, snížit hmotnost.
- **Příznak:** motory jsou po krátkém letu horké
  - Možná příčina: vrtule je pro dané KV příliš velká nebo má příliš velké stoupání – proud je vyšší než trvalý.
  - Co udělat: zvolit menší stoupání nebo průměr, ověřit proud ve visu podle logu.
- **Příznak:** doba letu je poloviční proti výpočtu
  - Možná příčina: výpočet platí pro statický vis, ale létá se s manévry; nebo je kapacita baterie nižší než jmenovitá.
  - Co udělat: vzít střední proud z logu, ověřit kapacitu nabíjecím cyklem.
- **Příznak:** na horách stroj nevzlétne, v nížině létal
  - Možná příčina: hustota vzduchu je nižší – tah při stejných otáčkách je menší.
  - Co udělat: použít vrtuli s větším průměrem nebo stoupáním, nebo snížit hmotnost.

## references
- Propeller Thrust — NASA Glenn Research Center | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/ | primary | A
- UIUC Propeller Database | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- Propulsion by Propellers — MH Aerotools | https://mh-aerotools.de/airfoils/propuls4.htm | secondary | B

## checklist
- Umím vysvětlit, proč je velká pomalá vrtule účinnější
- Vím, že tah ~ n² a výkon ~ n³
- Umím číst tabulku tahu motoru a najít pracovní bod ve visu
- Mám spočítaný proud ve visu a dobu letu pro svou stavbu
- Mám výpočet po letu porovnaný s logem
