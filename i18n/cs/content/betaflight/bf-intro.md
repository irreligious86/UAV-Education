---
id: bf-intro
title: "Úvod do Betaflightu"
level: L1
readingTime: 25 min
firmware: Betaflight 4.5+
status: published
tags:
  - Betaflight
  - začínáme
  - konfigurátor
  - nastavení
references:
  - title: "Getting Started — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/getting-started"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 Release Notes"
    url: "https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Official Web App"
    url: "https://app.betaflight.com"
    tier: primary
    stack: betaflight
  - title: "Betaflight Advanced Guide — iFlight"
    url: "https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396"
    tier: secondary
    stack: betaflight
  - title: "Betaflight FAQ — How to Start"
    url: "https://www.betaflight.com/docs/wiki/guides/current/FAQ"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Releases"
    url: "https://github.com/betaflight/betaflight-configurator/releases"
    tier: primary
    stack: betaflight
related:
  - bf-ports
  - bf-modes-osd
  - bf-cli
next:
  - bf-ports
source: content/betaflight/bf-intro.md
source_hash: 18aabbcd6bb5
---

## summary

Betaflight je otevřený firmware pro řídicí jednotky multikoptér s důrazem na **nízké zpoždění** řízení a pružné nastavení. V článku najdete celý řetězec od instalace konfigurátoru po první bezpečný vzlet.

**Po přečtení budete umět:**

- nahrát firmware do FC a udělat **zálohu** konfigurace (`diff all`);
- nastavit **porty, přijímač, režimy** a kalibraci senzorů;
- zkontrolovat **motory a failsafe** před letem.

## theory

### Co je Betaflight

Betaflight je fork projektu **Cleanflight** (nástupce Baseflightu / portu MultiWii na STM32). Hlavním důrazem celého stacku je **výkon**: minimální **latency** a vysoká frekvence smyčky gyroskopu (až **8 kHz**).

**Podpora:** řídicí jednotky s **STM32** (F4, F7, H7). **Možnosti firmwaru:**

- více profilů **PID**;
- filtrace gyroskopu a **D-term**;
- digitální protokoly pro ESC (**DShot**, ProShot);
- **Blackbox** pro logy;
- **CLI** pro přesné nastavení.

### Architektura firmwaru

Firmware je modulární, úlohy běží v reálném čase. **Hlavní úlohy (tasks):**

- **Gyro task** – čtení gyroskopu (až 8 kHz), filtry.
- **PID task** – výstup na motory podle odchylky **setpoint** vs **gyro**.
- **RX task** – přijímač (CRSF, SBUS, ELRS aj.).
- **Scheduler** – rozdělování času mezi úlohy.

**Cyklus PID:** parametr `pid_process_denom` určuje frekvenci smyčky PID. Příklad: gyro **8 kHz**, `pid_process_denom = 2` → PID **4 kHz** (typický výchozí bod pro většinu staveb).

### Verze firmwaru a kompatibilita

**Betaflight 4.5** je předchozí stabilní větev (poslední vydání 4.5.5); aktuální jsou 2025.12.x a 2026.6.x. Klíčové změny:

- GPS (včetně modulů **M10**) a **GPS Rescue**;
- magnetometry;
- **Angle / Horizon** s volbou *Earth referencing*;
- fonty pro HD VTX (Walksnail);
- filtrace zohledňující harmonické **RPM**.

**Důležité:** při přechodu **4.4 → 4.5** je nutný **Full Chip Erase** a nastavení od nuly. Staré **výpisy CLI** z verze 4.3 a nižších bývají **nekompatibilní** kvůli přejmenování a změnám rozsahů parametrů.

### Ekosystém Betaflightu

Kromě firmwaru je tu **Betaflight Configurator**. Webová aplikace byla dostupná už pro 4.5 (Configurator 10.10) a od verze **2025.12** je hlavním nástrojem **webový konfigurátor** (`https://app.betaflight.com`) přes **WebUSB / WebSerial**. Pro Android jsou i nadále nativní aplikace.

### Target, unified target a Cloud Build
Firmware se sestavuje pro **target** – popis desky: procesor, které piny jsou k čemu přivedeny (`resource`), který gyroskop je na které sběrnici SPI. Od verze 4.3 jsou téměř všechny desky **unified targets**: jeden binární soubor pro rodinu procesorů (například `STM32F405`) plus textová konfigurace desky (`board_name`, `manufacturer_id`, sada `resource`/`set`), kterou konfigurátor načte při nahrávání firmwaru. Cloud Build (4.4+) sestaví binární soubor na serveru s vybranou sadou funkcí: protokol přijímače, OSD, GPS, telemetrie, LED – co nezaškrtnete, to ve firmwaru není (typická příčina toho, že „přijímač mlčí“). Příkaz `version` v CLI ukáže verzi, target, datum a git revizi sestavení; `BUILD KEY` (klíč sestavení pro jeho zopakování) vypíše `status` a seznam voleb podle tohoto klíče vrátí build.betaflight.com.

### Co dělá plánovač každých 125 µs
`fc/tasks.c` popisuje úlohy s periodou a prioritou; `scheduler/scheduler.c` je vybírá. Kritické jsou `GYRO` (čtení, filtry) a `PID` (`taskMainPidLoop`: RC povel → PID → mixer → DShot) – na frekvenci gyroskopu / `pid_process_denom`. Ostatní dostávají čas, který zbude: `RX` (příjem a zpracování rámců, řízené událostmi), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (podle `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. Příkaz `tasks` v CLI ukáže skutečnou periodu, průměrnou a maximální dobu každé úlohy a zatížení CPU; `status` ukáže frekvenci gyroskopu, zatížení a příznaky armování. Přetížení (> 85–90 % na F4 s 8 kHz) znamená vynechané úlohy, jitter a příznak `LOAD`: řeší se nastavením `pid_process_denom = 2` nebo vypnutím funkcí.

### Mapa nastavení: kde co najdete
| Co | Kde v konfigurátoru | Klíčové parametry CLI |
|---|---|---|
| Porty a zařízení | Ports | `serial`, `resource`, `serialrx_provider` |
| Přijímač, kanály, rates | Receiver | `map`, `rates_type`, `roll_rc_rate`… |
| Režimy na přepínačích | Modes | `aux` |
| Motory, ESC, protokol | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `dshot_idle_value` (2025.12: `motor_idle`) |
| PID, filtry, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Firmware | Firmware Flasher | — |
Profily: až 4 PID profily (`profile`) a 4 profily rates (`rateprofile`), přepínané přepínačem/adjustments – jeden „klidný“, jeden „závodní“.

### Rozebraný příklad: pořadí prvního nastavení
Firmware (Cloud Build: CRSF, OSD HD, GPS, pokud je) → výchozí `resource`/target → Ports (UART přijímače) → Receiver (CRSF, kontrola kanálů a `map` AETR) → Motors (DShot600, `motor_poles`, `dshot_bidir`, směr bez vrtulí) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP pro první let) → OSD (napětí, LQ, časovač, varování) → Blackbox (2 kHz) → `diff all` do repozitáře (modul „CI“). První let na výchozích hodnotách PID: Betaflight 4.5 létá na 5" „z krabice“ lépe než většina ručních nastavení začátečníka; ladění přijde až po lozích.

{{diagram:bf-setup-map|Pořadí prvního nastavení: záloha → Ports → Receiver → Modes → Motors (bez vrtulí) → OSD → PID a filtry podle logu.}}

## practice

### Instalace Betaflight Configuratoru

**Varianta A – web (doporučeno pro PC):**

1. Prohlížeč na bázi **Chromium** (Chrome, Edge, Opera).
2. Otevřete `https://app.betaflight.com`.
3. Při prvním připojení FC povolte přístup k **USB**.

**Varianta B – offline nebo starší prostředí:**

- instalátor z repozitáře GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

### Připojení řídicí jednotky

1. USB kabel **s přenosem dat** (ne „jen nabíjecí“).
2. V konfigurátoru: port (**COM*** / `/dev/ttyACM*`) → **Connect**.
3. Pokud port chybí – ovladače (**ImpulseRC Driver Fixer** nebo ručně ve Windows).

**Kontrola:** záložka **Setup** – 3D model kopíruje náklony. Bez reakce – akcelerometr nebo spojení.

### Záloha (CLI)

Před jakýmikoli úpravami: záložka **CLI** → zadejte příkaz níže → **Save to File**.

```text
diff all
```

`diff all` ukládá jen **rozdíly oproti výchozím hodnotám** – hodí se pro obnovu. `dump all` slouží k hloubkové diagnostice; pro přenos konfigurace **mezi hlavními verzemi** se nedoporučuje.

### Aktualizace firmwaru (Firmware Flasher)

1. **Firmware Flasher** – cílová řídicí jednotka (často se rozpozná přes USB).
2. Verze – poslední stabilní **4.5.x**.
3. Při změně hlavní větve zapněte **Full chip erase**.
4. **Load Firmware [Online]** → **Flash Firmware**; neodpojujte USB až do konce.
5. Po restartu obnovte konfiguraci ze zálohy (**CLI**), nebo nastavte znovu.

### Záložka Configuration

- **Mixer** – typ rámu (**Quad X** pro typickou FPV kvadrokoptéru).
- **Board and Sensor Alignment** – **Yaw degrees**, pokud je FC na rámu pootočená.
- **Battery Voltage** – **VBAT** pro zobrazení napětí.
- **ESC/Motor** – v aktuální aplikaci se protokol DShot, **Bidirectional DShot** a Motor idle nastavují na záložce **Motors**.
- **Motor Stop** – pokud se motory po armování nemají točit při nulovém plynu.

### Záložka Ports

- **USB VCP** – samostatný řádek v Ports (ne UART1), MSP na něm musí zůstat zapnuté; UART1 je běžný hardwarový port.
- **UART2/3/4** – **Serial RX** na tom portu, ke kterému je připájen přijímač.
- **UART5** (příklad) – **GPS**, rychlost **57600** nebo **115200**.

### Záložka Receiver

- **Serial-based receiver** pro CRSF / SBUS / FPORT.
- **Provider:** **CRSF** (ELRS, TBS), **SBUS** (FrSky, DJI aj.).
- Kniply na vysílačce → posuvníky v konfigurátoru se musí hýbat.
- Rozsah **1000–2000** (střed **1500**); jinak **rxrange** v CLI nebo endpoints na vysílačce.
- **Channel Map** (například **AETR**, **TAER**) při zaměněných kanálech.

### Záložka Modes

Přiřaďte kanály **AUX** k režimům. Stručně, co který znamená:

- **ARM** – zapnutí motorů (nejlépe dvoupolohový přepínač).
- **ANGLE** – samovyrovnávání, výuka.
- **HORIZON** – hybrid stabilizace a akra.
- **ACRO** – výchozí režim, v seznamu nemá vlastní řádek.
- **BEEPER** – hledání dronu.
- **GPS RESCUE** – pokud je nastavená GPS.

Pro každý režim: **Add Range** → zvolte kanál a rozsah polohy přepínače.

### Kalibrace senzorů

- **Akcelerometr:** **Setup**, vodorovná plocha → **Calibrate Accelerometer**.
- **Magnetometr:** **Calibrate Magnetometer**, ~30 s otáčení kolem os; ověřte shodu se skutečným kurzem.

### ESC a motory (bez vrtulí!)

**Nebezpečí:** před testem motorů vždy **sundejte vrtule**.

1. **Motors** – zapněte **I understand the risks**.
2. **Motor 1** – ověřte, že odpovídá fyzickému motoru (v Betaflightu Quad X: Motor 1 – zadní pravý, 2 – přední pravý, 3 – zadní levý, 4 – přední levý).
3. Směr otáčení – podle schématu rámu; opravuje se přehozením vodičů nebo v **BLHeli / Bluejay**.
4. Neshoda pořadí/směru je typická příčina převrácení při vzletu.

### Předletová kontrola

- **ARM bez vrtulí** – motory se točí v nízkých otáčkách.
- **Náklon vpřed** – přední motory krátce přidají plyn (stabilizace reaguje).
- **Failsafe** – vypněte vysílačku; očekávané chování (přistání / **GPS Rescue**).
- **OSD** – napětí, časovač, režim (pokud používáte videopřenos).

## diagnostics
- **Příznak:** Konfigurátor nevidí řídicí jednotku, port se neobjeví
  - Možná příčina: nejsou nainstalované ovladače (Windows), nekvalitní USB kabel, konflikt portů.
  - Co zkontrolovat/udělat: vyměnit kabel za kabel s přenosem dat. Ve Windows nainstalovat ovladače pomocí ImpulseRC Driver Fixer. Restartovat počítač. Zkusit jiný port USB.

- **Příznak:** Řídicí jednotka se připojí, ale 3D model nereaguje na pohyb
  - Možná příčina: akcelerometr není zkalibrovaný, senzor je poškozený.
  - Co zkontrolovat/udělat: provést kalibraci akcelerometru na vodorovné ploše. Pokud to nepomůže, zkontrolovat v CLI status a ověřit, že je ACCEL rozpoznán. Zkontrolovat neporušenost vodičů a pájení.

- **Příznak:** Dron nejde armovat, v pravém horním rohu bliká chyba (například RXLOSS)
  - Možná příčina: přijímač nedostává signál, není nastavený port, špatný protokol.
  - Co zkontrolovat/udělat: zkontrolovat, že je pro Serial RX zvolen správný UART a že je zvolen správný protokol (CRSF/SBUS). Ověřit, že je vysílačka zapnutá a přijímač spárovaný (kontrolka na přijímači svítí). Na záložce Receiver zkontrolovat, že se posuvníky hýbou.

- **Příznak:** Motory se točí, ale dron nevzlétne nebo se při pokusu převrátí
  - Možná příčina: špatný směr otáčení motorů, špatné pořadí zapojení, špatná orientace FC.
  - Co zkontrolovat/udělat: na záložce Motors zkontrolovat, že odpovídá pořadí motorů (Motor 1 – zadní pravý, Motor 2 – přední pravý atd.). Zkontrolovat směr otáčení (podle značení na vrtulích). Ověřit, že je úhel pootočení FC (Yaw degrees) nastaven správně.

- **Příznak:** Kniply se v konfigurátoru hýbou, ale hodnoty nedosahují 1000–2000
  - Možná příčina: koncové body na vysílačce jsou nastavené špatně.
  - Co zkontrolovat/udělat: v nastavení vysílačky upravit Travel/Endpoints na 1000–2000 µs. Případně použít ke korekci příkaz CLI rxrange.

- **Příznak:** Dron jde armovat, ale motory se netočí (při vypnutém MOTOR_STOP)
  - Možná příčina: minimální plyn (min_throttle) je příliš nízký na rozběh motorů.
  - Co zkontrolovat/udělat: s DShot se `min_throttle` nepoužívá: na záložce Motors zvýšit Motor Idle (`dshot_idle_value` ve 4.5, `motor_idle` ve 2025.12; výchozí hodnota 5.5 %).
- **Příznak:** po nahrání firmwaru nefunguje přijímač/GPS, přestože je zapojení správné
  - Možná příčina: funkce není zahrnutá v Cloud Buildu.
  - Co udělat: `version` → seznam voleb; nahrát firmware znovu s potřebnými.
- **Příznak:** `LOAD` v příznacích armování nebo CPU > 90 %
  - Možná příčina: F4 na 8 kHz se všemi funkcemi.
  - Co udělat: `pid_process_denom = 2`, vypnout LED/zbytečné telemetrie, `tasks` k nalezení náročných úloh.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- GPS Rescue 4.5 — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight — Arming sequence and safety (arming flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B

