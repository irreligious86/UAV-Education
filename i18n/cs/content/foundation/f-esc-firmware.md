---
id: f-esc-firmware
title: "Firmware ESC: Bluejay, AM32, BLHeli_32 a nastavení regulátoru"
level: L2
readingTime: 30 min
firmware: Betaflight 4.4+ · ArduPilot 4.5+ · Bluejay 0.21+ · AM32 2.x
status: published
tags:
  - ESC
  - Bluejay
  - AM32
  - DShot
related:
  - f-motors-esc
  - bf-rpm-filter
  - bf-filters
  - bf-blackbox
next:
  - bf-rpm-filter
source: content/foundation/f-esc-firmware.md
source_hash: e6c1fde3e719
---

## summary
Regulátor otáček (ESC) je samostatný počítač s vlastním firmwarem a na něm závisí RPM filtr, zvuk motorů, zahřívání a dokonce i to, jestli se motor po pádu znovu rozběhne. Modul „Motory a ESC“ vysvětlil, co ESC dělá; tady se dozvíte, jaký firmware patří na jaký hardware, co je obousměrný DShot a EDT, která nastavení regulátoru skutečně mění let (frekvence PWM, časování, demagnetizace, rozběhový výkon), jak nahrávat firmware přes řídicí jednotku v Betaflightu a ArduPilotu a jak neudělat ze 4-in-1 cihlu.

## theory
### Kdo je kdo
| Firmware | Hardware | Stav | Co je důležité |
|---|---|---|---|
| BLHeli_S | 8bitové EFM8 (BB1/BB2/BB21) | tovární na levných ESC, nevyvíjí se | v původní podobě bez obousměrného DShotu |
| Bluejay | 8bitové EFM8 BB21 a BB51 (BB1/BB10 jen do verze 0.18.1) | otevřený, vyvíjí se | obousměrný DShot, EDT, frekvence PWM 24/48/96 kHz, startovací melodie |
| BLHeli_32 | 32bitové ARM | uzavřený; vývoj i podpora skončily v roce 2024 | funguje, aktualizace ani nový konfigurátor už nebudou |
| AM32 | 32bitové ARM (STM32F051, G071, AT32F421, GD32 aj.) | otevřený, vyvíjí se | náhrada BLHeli_32 tam, kde pro desku existuje target |

Název firmwaru na krabici vypovídá o mikrokontroléru regulátoru: „BLHeli_S“ znamená 8 bitů, „BLHeli_32“ nebo „AM32“ znamená ARM.

### Obousměrný DShot a EDT
- **DShot** – digitální protokol povelů z řídicí jednotky do ESC: DShot300/600 udává rychlost v kbit/s; bez kalibrace rozsahu plynu, s kontrolním součtem.
- **Obousměrný DShot (bidir)** – po stejném vodiči ESC odpovídá elektrickými otáčkami (eRPM). To je vstup RPM filtru v Betaflightu a harmonického notch filtru v ArduPilotu. Mechanické otáčky = eRPM / (počet pólů / 2), proto musí být počet pólů motoru (obvykle 14 u 22xx–28xx) zadán v řídicí jednotce.
- **EDT (Extended DShot Telemetry)** – do týchž odpovědí se přidává teplota, napětí, proud a stav ESC – bez samostatného telemetrického vodiče. Podporují ji Bluejay a AM32; zapíná se v řídicí jednotce.

### Nastavení, která mění let
- **Frekvence PWM.** Vyšší (48–96 kHz) znamená tišší a plynulejší chod při malém plynu a lepší odezvu; nižší (24 kHz) znamená menší spínací ztráty a zahřívání a víc „tahu na ampér“ u těžkých strojů. Pro 5" freestyle je typických 48 kHz, pro velké vrtule 24.
- **Časování (timing, advance).** Úhel předstihu komutace. Vyšší znamená víc otáček a proudu a větší zahřívání; nižší je účinnější, ale hrozí ztráta synchronizace při prudkém přidání plynu. Automatické nebo střední je rozumný začátek.
- **Demagnetizace (demag compensation).** Ochrana proti ztrátě synchronizace při prudkých změnách plynu u velkých motorů. Ztráty synchronizace („desync“) – motor za letu cuká nebo se zastaví – se řeší nejdřív zvýšením kompenzace.
- **Rozběhový výkon (startup/rampup power).** Příliš vysoký – při zablokování motoru shoří vinutí; příliš nízký – těžký motor se nerozběhne.
- **Směr otáčení.** Mění se ve firmwaru ESC nebo příkazem DShot z řídicí jednotky – vodiče není třeba přepájet.
- **Melodie a beacon.** Zvuk „ztraceného stroje“ po pádu je užitečná funkce, ne hračka.

{{diagram:esc-pwm-class-map|Чем меньше аппарат, тем выше стартовая частота; DJI O3/O4 с Gyroflow сдвигает все классы со стартом 24 кГц на 48, а окончательное значение проверяется по N = 10·f/eRPM на висении.}}

{{diagram:chart-esc-temp-derate|При пороге 100 °C Bluejay снимает мощность ступенями до 20 %, а AM32 на 101 °C сразу оставляет 25 % и к 110 °C — ноль: низкий порог AM32 в жару роняет аппарат.}}

### Jak nahrávat firmware
- **Přes řídicí jednotku (passthrough).** Řídicí jednotka propojí signálový vodič ESC s počítačem. Betaflight: připojte USB, Configurator zavřete (port je obsazený) a otevřete ESC Configurator (esc-configurator.com) v Chromu – pro BLHeli_S/Bluejay a AM32; pro BLHeli_32 použijte BLHeliSuite32 (archivní verze). ArduPilot: `SERVO_BLH_AUTO = 1` pro motory (u letounů `SERVO_BLH_MASK`), protokol DShot, pozemní stanici odpojte, USB nechte připojené, v konfigurátoru zvolte rozhraní „BLHeli32/AM32 Bootloader (Betaflight/Cleanflight)“. Výstupy IOMCU (MAIN) passthrough nepodporují – jsou potřeba výstupy FMU/AUX.
- **Pravidlo targetu.** Firmware se vybírá pro konkrétní desku ESC (layout/target). Špatný target znamená cokoli od nesprávné funkce až po spálené spínací tranzistory. Konfigurátor obvykle ukazuje aktuální layout – nahrávejte jen ten, který se shoduje.
- **Před nahráním firmwaru**: sundejte vrtule, uložte aktuální nastavení (snímek obrazovky nebo soubor), při pochybnostech nahrávejte vždy jen do jednoho ESC, baterii připojte přes ochranu (smoke stopper).

### Řídicí jednotka: co zapnout
- Betaflight: `set motor_pwm_protocol = DSHOT600` (nebo 300 — podle cyklu PID a MCU, pravidlo v `f-motors-esc`; na F405/F411/G47x s bidir nastaví firmware 300 sám), `set dshot_bidir = ON`, `set motor_poles = 14`; kontrola – záložka Motors ukazuje RPM, chyby DShot ≤ 1 % (`bf-rpm-filter`).
- ArduPilot: `MOT_PWM_TYPE` – DShot300/600, `SERVO_BLH_BDMASK` – maska výstupů s obousměrným DShotem, `SERVO_BLH_POLES` – počet pólů; telemetrie ESC je vidět v logu (`ESC`) a využívá ji harmonický notch filtr (`INS_HNTCH_MODE = 3` – podle telemetrie ESC).

{{diagram:esc-firmware-choice|Výběr firmwaru ESC: 8bitový regulátor s BB21/BB51 – Bluejay místo BLHeli_S, 32bitový – AM32, pokud existuje target, fungující BLHeli_32 lze ponechat, bez targetu firmware nenahrávat.}}

## practice
### Krok 1. Inventura
Přes passthrough přečtěte každý ESC: firmware a verze, layout/target, frekvence PWM, časování, směr. Tabulku zapište do karty stroje.

### Krok 2. Bidir DShot a RPM
Pokud to firmware podporuje, zapněte v řídicí jednotce obousměrný DShot a zadejte počet pólů. Betaflight: záložka Motors, při roztočených motorech (bez vrtulí) sledujte otáčky a procento chyb. Zapište eRPM a mechanické otáčky při 10 % plynu a ověřte vzorec přepočtu na svém počtu pólů.

### Krok 3. Nahrání firmwaru (pokud to má přínos)
Jen pokud potřebujete bidir DShot nebo EDT a ESC je neumí: BLHeli_S → Bluejay (pouze na MCU BB21/BB51) nebo BLHeli_32 → AM32, pokud existuje target. Nejdřív uložte nastavení; target vezměte z přečteného layoutu. Po nahrání firmwaru vraťte směr otáčení a zkontrolujte pořadí a směr motorů.

### Krok 4. Frekvence PWM: srovnání za letu
Bez vrtulí neměřte – je potřeba skutečný provozní režim. S vrtulemi, na upoutání nebo za letu: dva lety se stejnou baterií na 24 a 48 kHz (Bluejay/AM32). V Blackboxu nebo v logu porovnejte proud ve visu, teplotu ESC (EDT) a šum gyroskopu. Zapište závěr pro svůj stroj.

Laboratorní úloha je splněna, když je tabulka ESC vyplněná, RPM z ESC jsou v řídicí jednotce vidět s chybami kolem 0 % a volba frekvence PWM je potvrzena srovnáním proudu nebo teploty.

## diagnostics
- **Příznak:** RPM filtr se nezapne, na záložce Motors nejsou otáčky
  - Možná příčina: firmware ESC bez bidir DShotu (původní BLHeli_S), vypnutý `dshot_bidir`, špatný protokol.
  - Co udělat: zkontrolujte firmware ESC, zapněte bidir, v případě potřeby nahrajte Bluejay/AM32.
- **Příznak:** velké procento chyb DShot
  - Možná příčina: rušení na signálových vodičích, příliš vysoká rychlost DShot na danou délku vodiče, špatná zem.
  - Co udělat: DShot300 místo 600, krátké vodiče, společná zem, podle potřeby ferity.
- **Příznak:** motor při prudkém přidání plynu cuká nebo se zastaví
  - Možná příčina: ztráta synchronizace (desync).
  - Co udělat: nejdřív zvyšte demag compensation, pak časování o stupeň výš (hlídejte teplotu motorů; když se přehřívají, vraťte časování a dejte menší vrtuli), zkontrolujte ložiska, vinutí a délku fázových vodičů.
- **Příznak:** passthrough nenajde ESC
  - Možná příčina: je otevřený Configurator nebo pozemní stanice, ESC nemají napájení z baterie, v ArduPilotu jde o výstupy IOMCU, protokol není DShot.
  - Co udělat: zavřete ostatní programy, připojte baterii, přejděte na výstupy FMU/AUX, zapněte DShot.
- **Příznak:** po nahrání firmwaru se motor netočí nebo se v klidu zahřívá
  - Možná příčina: špatný target/layout.
  - Co udělat: nahrajte přes bootloader firmware se správným targetem; pokud je bootloader poškozený, jde to už jen programátorem.

## references
- Bluejay — open-source firmware for BLHeli_S ESCs | https://github.com/bird-sanctuary/bluejay | primary | A
- AM32 — open-source firmware for ARM ESCs | https://github.com/am32-firmware/AM32 | primary | A
- ESC Configurator (web) | https://esc-configurator.com | primary | B
- ArduPilot — BLHeli32, AM32 and BLHeli_S ESCs (passthrough) | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A
- Betaflight — DShot RPM filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A

## checklist
- Umím určit typ ESC (8 bitů / ARM) a vhodný firmware
- Umím vysvětlit bidir DShot, eRPM a EDT a přepočítat eRPM na otáčky
- Vím, co mění frekvence PWM, časování a demagnetizace
- Umím nahrát firmware do ESC přes řídicí jednotku a zkontrolovat target
- Umím zapnout RPM z ESC v Betaflightu i v ArduPilotu
