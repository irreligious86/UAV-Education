---
id: f-mechanics
title: "Mechanika letu: síly, momenty, pohybové rovnice"
level: L1
readingTime: 30 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - mechanika
  - síly
  - momenty
  - dynamika
related:
  - f-physics
  - f-aero-props
  - bf-pid-reg-in-bf
next:
  - f-aero-props
source: content/foundation/f-mechanics.md
source_hash: 18bc29e1dc9d
---

## summary
Modul „Jak létá multikoptéra“ vysvětlil princip; tento modul ho převádí do rovnic, se kterými lze počítat. Vis, stoupání, klonění (roll) a zatáčka jsou čtyři rovnováhy sil, které dávají čísla: kolik tahu a proudu je potřeba v každém režimu, s jakým zrychlením se stroj rozjede při úhlu klonění 30°, proč je těžký stroj na dlouhých ramenech „líný“ (moment setrvačnosti a rameno síly) a proč je při klonění nutné k udržení výšky přidat plyn. Vše s výpočtem pro 7" o hmotnosti 1.4 kg, který se potom porovná s logem.

## theory
### Síly: druhý Newtonův zákon pro dron
Na stroj působí: tíha m·g dolů, celkový tah T podél osy stroje (kolmo k rovině vrtulí) a odpor vzduchu D proti směru rychlosti. Pohybová rovnice: **m·a = T + m·g + D** (vektorově). Čtyři režimy:

**1. Vis.** a = 0, tah je svislý: **T = m·g**. Pro 1.4 kg: T = 1.4 × 9.81 = 13.7 N = 1400 gf. Na jeden motor připadá 350 gf. To je právě ten „plyn ve visu“ v logu.

**2. Stoupání.** Aby stroj zrychlil vzhůru se zrychlením a: T = m·(g + a) + D. Zrychlení na 3 m/s za 1 s → a = 3 m/s² → T = 1.4 × 12.8 = 17.9 N (1830 gf, +30 % proti visu). Ustálené stoupání 3 m/s: a = 0, stačí vyrovnat odpor – při této rychlosti je D malý (~20 gf při stejných C_d = 1.1 a A = 0.03 m² pro 7"), T ≈ m·g + D ≈ 1410–1420 gf. Závěr: draho vychází *zrychlení*, ne rychlost stoupání. Vrtule ale ve vzestupném proudění pracuje hůř (roste V₀ ve vzorci pro tah) a skutečný plyn při stoupání je vyšší, než udává tento odhad.

**3. Klonění (nebo klopení (pitch)) s udržením výšky.** Stroj je nakloněn o úhel φ a tah je nakloněn s ním. Svislá složka se musí rovnat tíze: T·cos φ = m·g → **T = m·g / cos φ**. Vodorovná složka stroj urychluje: m·a = T·sin φ → **a = g·tan φ**.
- φ = 30°: T = 1.155·m·g (+15.5 % plynu), a = 5.7 m/s².
- φ = 45°: T = 1.41·m·g, a = 9.8 m/s² (1 g).
- φ = 60°: T = 2·m·g – T/W 2:1 už na udržení výšky nestačí.
To je důvod, proč se v režimu Angle s omezením náklonu 60° dron s T/W 2:1 při prudkých manévrech propadá a proč mají Betaflight/INAV/ArduPilot kompenzaci plynu podle úhlu náklonu (například `thr_corr_value` (Betaflight), `throttle_tilt_comp_str` (INAV), `ATC_ANGLE_BOOST` (ArduPilot) v různých podobách).

**4. Zatáčka (koordinovaná zatáčka).** Dostředivé zrychlení v²/r dodává vodorovná složka tahu: m·v²/r = m·g·tan φ → **r = v² / (g·tan φ)**. 15 m/s při úhlu klonění 30°: r = 225 / 5.66 = 40 m. Aby se stroj při stejné rychlosti vešel do poloměru 20 m, je potřeba úhel klonění 49° a plyn ×1.52.

### Odpor vzduchu
**D = ½·ρ·C_d·A·v²**, ρ = 1.225 kg/m³, A je čelní plocha, C_d ≈ 1.0–1.3 pro „krabici s rameny“. 7" s čelní plochou 0.03 m² při 20 m/s: D = 0.5 × 1.225 × 1.1 × 0.03 × 400 = 8 N – víc než polovina tíhy! Proto je maximální vodorovná rychlost omezená: při náklonu φ se odpor vyrovná s T·sin φ a dál už stroj nezrychluje. Pád: při D = m·g stroj dosáhne **mezní rychlosti** v_t = √(2·m·g / (ρ·C_d·A)); pro náš příklad ≈ 26 m/s – to je rychlost, kterou narazí do země, když mu ve velké výšce selžou všechny motory.

### Momenty: proč je stroj „ostrý“, nebo „líný“
Otáčení kolem osy určuje **moment M = ΔT·L**: rozdíl tahu mezi protilehlými motory ΔT vynásobený ramenem síly L (vzdálenost motoru od osy). Úhlové zrychlení **α = M / I**, kde I je **moment setrvačnosti** I = Σ mᵢ·rᵢ² (hmotnost každého dílu krát druhá mocnina vzdálenosti od osy).

- Hmotnost na koncích ramen (motory, vrtule) vychází draho: r² roste rychle. 4 motory po 35 g na ramenech dlouhých 15 cm dávají I = 4 × 0.035 × 0.15² ≈ 0.0032 kg·m² – stejně jako baterie 300 g posunutá 10 cm od středu.
- Velký stroj: rameno síly L roste lineárně, I kvadraticky. Proto se 15" X8 při jakémkoli rozumném tahu otáčí pomaleji než 5": při ΔT = 500 gf na rameni 0.4 m je M = 2 N·m, I ≈ 0.3 kg·m² → α ≈ 6.7 rad/s² (380°/s²); u 5" s M = 0.5 N·m a I = 0.004 → α = 125 rad/s² (7000°/s²). Rozdíl je dvacetinásobný – odtud různé PID a rates.
- Zatáčení (yaw) se neřídí tahem, ale **reakčními momenty** motorů (rozdíl otáček dvojic CW a CCW). Tyto momenty jsou malé a I kolem svislé osy je největší (všechny hmoty jsou daleko od osy), proto je yaw u všech multikoptér nejvíc „líná“ osa a u velkých strojů to platí obzvlášť. To je důvod pro oslabené D a velké I-term na ose yaw i pro naklonění motorů na některých rámech.

### Rovnice jako nástroj
Když to spojíme: pro jakýkoli manévr lze odhadnout potřebný tah (→ proud z tabulky motoru), zrychlení a poloměr. Dobrou praxí je tabulka režimů pro vlastní stroj: vis / stoupání / klonění 30° / klonění 45° / maximální rychlost – s tahem, proudem a rezervou do T_max. Rezerva v nejnáročnějším režimu < 20 % znamená, že se stroj při poryvu větru nebo poklesu napětí propadne.

{{diagram:forces-moments|Posuvný pohyb určují síly (tah, tíha, odpor), otáčivý pohyb momenty a setrvačnost J.}}

{{diagram:chart-tilt-thrust|Tah potřebný k udržení výšky v náklonu roste jako 1/cos φ: při 30° je potřeba +15.5 %, při 60° dvojnásobek tíhy. Stroj s T/W = 2 fyzicky neudrží výšku při náklonu větším než 60°.}}

## practice
### Krok 1. Data
Hmotnost m s baterií (váha), rameno síly L (střed → osa motoru), hmotnosti větších dílů a jejich vzdálenosti od středu, tabulka tahu motoru (tah → proud).

### Krok 2. Tabulka režimů
Pro vis, zrychlení vzhůru 3 m/s², klonění 30° a 45°: T = m·g·k (k = 1, 1.31, 1.155, 1.41), tah na motor, proud podle tabulky, rezerva do maxima.

### Krok 3. Momenty setrvačnosti
I pro klonění a klopení: motory s vrtulemi ve vzdálenosti L, baterie a FC u středu, rám zhruba jako prstenec o hmotnosti m_rámu na poloměru 0.6·L. Zapište I_roll, I_pitch, I_yaw (pro yaw leží všechny hmoty ve vodorovné rovině: motory ve vzdálenosti L, baterie ve středu).

### Krok 4. Porovnání s logem
Z logu visu: plyn ve visu a proud. Porovnejte proud s vypočteným z kroku 2 (rozdíl > 20 % znamená chybu v hmotnosti, v tabulce, nebo silný vítr). Z logu klonění: maximální úhlové zrychlení podle gyroskopu (derivace gyro) proti odhadu α = ΔT_max·L / I – řádově se musí shodovat.

### Laboratorní úloha
Tabulka režimů a momentů setrvačnosti pro vlastní stavbu, porovnaná s logem ve dvou číslech (proud ve visu, úhlové zrychlení). Uložte ji do pasportu stavby.

## diagnostics
- **Příznak:** v režimu Angle dron při prudkém klonění ztrácí výšku
  - Možná příčina: T = m·g/cos φ převyšuje dostupný tah; T/W je malý nebo je omezení náklonu příliš velké.
  - Co udělat: omezte úhel, zapněte kompenzaci plynu podle náklonu, zvyšte T/W.
- **Příznak:** velký stroj „nedotáčí“ yaw, I-term se hromadí
  - Možná příčina: reakční momenty jsou malé, I_yaw je velký.
  - Co udělat: snižte nároky na rates na ose yaw, přehodnoťte PID pro yaw, u velkých rámů zvažte naklonění motorů.
- **Příznak:** po přesunutí baterie na okraj rámu je odezva pomalá a objevilo se houpání
  - Možná příčina: vzrostl moment setrvačnosti a posunulo se těžiště.
  - Co udělat: přesuňte hmotu ke středu a stroj znovu nalaďte.
- **Příznak:** proud ve visu je v logu výrazně vyšší než vypočtený
  - Možná příčina: nesprávná hmotnost, tabulka pro jiné napětí, poškozené vrtule, vítr.
  - Co udělat: stroj znovu zvažte, porovnejte s tabulkou pro vlastní napětí, prohlédněte vrtule.

## references
- Multicopter Dynamics (equations of motion) — PX4 Autopilot documentation | https://docs.px4.io/main/en/flight_stack/controller_diagrams.html | primary | A
- Quadrotor dynamics — Beard, "Quadrotor Dynamics and Control", BYU (PDF) | https://scholarsarchive.byu.edu/facpub/1325/ | primary | A
- Newton's laws and drag — NASA Glenn Beginner's Guide to Aeronautics | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ | secondary | B

## checklist
- Umím zapsat rovnováhu sil pro vis, stoupání, klonění a zatáčku
- Vím, že při úhlu klonění φ je potřeba tah m·g/cos φ a zrychlení je g·tan φ
- Chápu, proč je yaw nejpomalejší osa a proč jsou velké stroje „líné“
- Tabulka režimů a momenty setrvačnosti jsou spočítány pro vlastní stavbu
- Dvě čísla jsou porovnána s logem
