---
id: f-fc-sensors
title: "Řídicí jednotka a senzory"
level: L1
readingTime: 20 min
firmware: libovolný firmware
status: published
added: 2026-11-07
tags:
  - FC
  - senzory
  - UART
related:
  - f-motors-esc
  - link-protocols
next:
  - bf-pid-reg-in-bf
source: content/foundation/f-fc-sensors.md
source_hash: d5fed3f0a90a
---

## summary
Letová řídicí jednotka (FC) je malý počítač, který tisíckrát za sekundu čte senzory, počítá regulátor a posílá povely motorům. Modul vysvětluje, co je na desce osazeno, za co odpovídá který senzor, jak číst schéma zapojení a proč se stejný vodič na různých pájecích ploškách chová různě. Po jeho prostudování přestane být schéma desky rébusem.

## theory
### Procesor
Srdcem FC je mikrokontrolér. Možnosti určuje jeho řada:

- **F4** – nejrozšířenější a nejlevnější; mají omezený počet UART a neumějí UART invertovat softwarově (pro SBUS je potřeba externí hardwarový invertor na desce, jen u některých portů) (viz modul o SBUS).
- **F7** – rychlejší, víc UART, softwarová inverze.
- **H7** – nejvýkonnější, standard pro ArduPilot a PX4 na složitých platformách.

Důležitý není „nejlepší procesor“, ale to, zda desku podporuje potřebný firmware: každý firmware má vlastní seznam targetů (targets).

### Senzory
- **Gyroskop (gyro)** – úhlová rychlost ve třech osách. Hlavní senzor: stojí na něm stabilizace. Čte se tisíckrát za sekundu a je citlivý na vibrace.
- **Akcelerometr (accel)** – zrychlení, v klidu ukazuje směr gravitace. Je potřeba pro režimy se samočinným srovnáním (ANGLE) a pro navigaci.
- **Barometr (baro)** – tlak, z něj se počítá výška. Je citlivý na proud vzduchu od vrtulí a na světlo – zakrývá se molitanem.
- **Magnetometr (mag, kompas)** – kurz. Vadí mu silové vodiče: umisťuje se na stožárek spolu s GPS, co nejdál od proudu.
- **GPS** – poloha a rychlost. Je potřeba pro držení pozice, návrat domů a mise.

Spojit údaje těchto senzorů je úkolem filtru pro odhad stavu: v ArduPilotu je to EKF, v Betaflightu zjednodušené schéma bez navigace.

### Sběrnice
- **UART** – sériový port: přijímač, GPS, VTX, telemetrie, companion. Vodiče se zapojují křížem (TX → RX).
- **I2C** – sběrnice pro několik senzorů (kompas, externí barometr, displej) po dvou vodičích SDA/SCL.
- **SPI** – rychlá sběrnice uvnitř desky: gyroskop, OSD, flash paměť pro logy.

### Pájecí plošky na desce
Typická označení: `VBAT` (napětí baterie), `5V`/`9V`/`10V` (výstupy BEC), `GND`, `TX1`/`RX1` (UART1), `SDA`/`SCL` (I2C), `CURR` (senzor proudu), `LED` (adresovatelné LED), `BZ+`/`BZ-` (bzučák), `M1`–`M4` nebo `S1`–`S8` (výstupy pro ESC/serva).

### Montáž
Standardní rozteče upevnění jsou 30.5×30.5 a 20×20 mm. Deska se montuje na gumové tlumiče: gyroskop má vnímat pohyb rámu, ne jeho vibrace. Šipka na desce ukazuje „dopředu“; pokud je deska pootočená, zadává se pootočení ve firmwaru (board alignment / AHRS_ORIENTATION).

### Gyroskop zblízka: čipy a frekvence
Gyroskop je čip MEMS na sběrnici SPI. Rozšířené typy: MPU6000 (starý, výstup 8 kHz, nízký šum, už se nevyrábí), ICM20602/20689 (větší šum, citlivější na napájení), ICM42688-P (současný standard: až 32 kHz, nastavitelný hardwarový antialiasingový filtr, nízký šum), BMI270 (alternativa; podle datasheetu až 6.4 kHz, ale Betaflight ho ve výchozím stavu čte na 3.2 kHz, takže cyklus PID na něm není rychlejší než 3.2 kHz; s `gyro_hardware_lpf = EXPERIMENTAL` 6.4 kHz bez hardwarového LPF; `drivers/accgyro/gyro_sync.c`). Firmware čte čip přes SPI na 8–24 MHz s DMA (modul „Embedded“) a spouští smyčku PID synchronně s výstupem gyroskopu (ve verzích 4.x vždy; dělitel smyčky PID je `pid_process_denom`): při 8 kHz každých 125 µs. Řetězec: čip → hardwarový LPF (`gyro_hardware_lpf`) → softwarové filtry (modul „Filtry“) → PID. Dva gyroskopy na desce (dual gyro) znamenají průměrování nebo výběr; ArduPilot na H7 zvládá až tři IMU se samostatnými jádry EKF.

{{diagram:fc-signal-path|Cesta signálu uvnitř FC: gyroskop → filtry → PID → mixer → ESC; RC povel určuje žádanou hodnotu, Blackbox a OSD si berou kopii.}}

### Co dalšího je na desce
- **Čip OSD** (MAX7456 pro analog) nebo digitální OSD přes MSP DisplayPort (DJI/Walksnail/HDZero) – vykresluje telemetrii do videa.
- **Flash/SD** pro Blackbox: 16–32 MB flash stačí při 2 kHz na minuty; SD na hodiny. Zapisuje se přes SPI/SDIO, na F4 se někdy dostává do konfliktu o DMA s jinými funkcemi.
- **BEC**: 5 V (typicky 2–3 A celkem pro všechny spotřebiče) a 9–12 V (pro VTX/digitální systém, 2–3 A). Limity najdete v popisu desky; Raspberry Pi se z plošky FC nenapájí (modul „Připojení periferií“).
- **Senzor proudu** na PDB/ESC → ploška `CURR`, měřítko `ibata_scale` (Betaflight) / `BATT_AMP_PERVLT` (ArduPilot) se kalibruje podle wattmetru.
- **Invertory UART** jsou na F4 jen u některých portů (pro SBUS jsou označeny „SBUS“/„RX“ a mají hardwarový invertor); F7/H7 invertují libovolný port softwarově.
- **Softserial** – UART emulovaný na GPIO: do 19200 baudů, zatěžuje procesor; hodí se pro SmartAudio/telemetrii, ne pro přijímač.

### Co omezuje výběr desky
Počet UART (přijímač + GPS + VTX + companion = minimálně 4), přítomnost barometru a kompasu (pro INAV/ArduPilot jsou povinné), proud BEC podle zátěže, podpora targetu potřebným firmwarem **a jeho verzí** (ArduPilot – `hwdef`, Betaflight – unified target), rozměry a hmotnost, upevnění 30.5/20 mm, přítomnost CAN (DroneCAN na velkých strojích), počet výstupů pro motory/serva (VTOL – 8 a více).

{{diagram:fc-board-choice-tree|Выбор платы идёт от прошивки: навигации нужны баро, компас и не меньше 4 UART, а VTOL и большим аппаратам — H7 с CAN и 8+ выходами.}}

### Řešený příklad: čteme rozložení pinů
Typická deska H743 (30.5 mm): `UART1` – RX s invertorem (označen SBUS), `UART2` – GPS (vedle jsou `SDA/SCL` pro kompas), `UART4` – VTX/DisplayPort (vedle je ploška `9V`), `UART6`/`UART7` – companion/telemetrie, `M1–M8` – DShot, `CURR` – senzor proudu z ESC, `LED` – adresovatelný pásek, `BZ-` – bzučák, `VBAT` – měření napětí, `5V` – přijímač/GPS, `4V5` – je napájena z USB (pro nastavování bez baterie). Pravidlo čtení: nejdřív napájení (co odkud, jaký proud), potom UART podle funkcí, pak I2C a nakonec „zvláštní“ plošky. Tabulku „ploška → funkce → zařízení → proud“ zapište do pasportu stavby.

## practice
### Laboratorní úloha: přečíst schéma vlastní desky
1. Najděte u výrobce schéma zapojení (wiring diagram) své FC.
2. Vypište si, který UART je volný pro přijímač, který pro GPS a který pro VTX.
3. Zjistěte, z které plošky napájet VTX a kameru a jaký proud tento BEC dává.
4. Poznamenejte si, zda je na desce ploška s invertorem (pro SBUS na F4) a kam připájet LED a bzučák.
5. Výsledek uložte do deníku stavby vedle fotografie desky.

### Kontrola senzorů po stavbě
1. Připojte FC ke konfigurátoru (Betaflight App, Mission Planner nebo QGroundControl).
2. Naklánějte dron: model na obrazovce musí bez zpoždění opakovat pohyby ve všech třech osách.
3. Zkalibrujte akcelerometr na rovné ploše.
4. Ověřte, že barometr ukazuje změnu výšky, když dron zvednete rukou, a kompas kurz.

### Co zapsat: mapa desky
| Prostředek | Účel | Poznámka |
|---|---|---|
| UART1 | přijímač (CRSF) | plošky RX1/TX1 vedle 5 V |
| UART2 | GPS | 5 V ze samostatné plošky |
| UART3 | VTX (MSP/SmartAudio) | |
| UART4 | volný | |
| 9 V BEC | VTX a kamera | proud podle datasheetu desky, například 2 A |
| 5 V BEC | přijímač, GPS, LED | |
| ploška SBUS | s invertorem (F4), nebo není potřeba (F7/H7) | |

Hodnoty v tabulce jsou ukázkou formátu: vyplňujte podle schématu své desky a uvádějte zdroj (strana schématu, fotografie s popisky).

### Co má při kontrole vyjít
- **Gyroskop a akcelerometr.** Model na záložce Setup opakuje náklony okamžitě a správným směrem ve všech osách. Pokud je osa obrácená nebo se model „dívá“ jinam, je špatně zadaná orientace desky (`align_board_*` v Betaflightu, `AHRS_ORIENTATION` v ArduPilotu); opravuje se to před prvním letem.
- **Kalibrace akcelerometru** se provádí na rovné ploše, po ní je horizont rovný.
- **Barometr.** Když dron zvednete rukou o metr, výška vzroste přibližně o metr. Barometr v přímém proudu vzduchu nebo na světle šumí – přikrývá se kouskem molitanu.
- **Kompas** (pokud je osazen) ukazuje kurz, který se při otáčení stroje mění. V blízkosti silových vodičů ukazuje špatně – viz modul „Rušení“.

Laboratorní úloha je splněna, když mají všechny UART zapsaný účel, napájecí plošky a proud BEC jsou zapsány včetně zdroje, ploška s invertorem je nalezena nebo je poznamenáno, že není potřeba, a všechny senzory jsou po stavbě zkontrolovány v konfigurátoru a výsledek je zapsán.

## diagnostics
- **Příznak:** model v konfigurátoru se otáčí špatným směrem
  - Možná příčina: deska je namontována pootočeně a pootočení není zadáno ve firmwaru.
  - Co udělat: nastavit board alignment / AHRS_ORIENTATION.
- **Příznak:** mezi flagy blokujícími armování (Arming Disable Flags) je `NOGYRO`
  - Možná příčina: gyroskop není rozpoznán – špatný firmware (target) nebo poškozená deska.
  - Co udělat: nahrát firmware se správným targetem, zkontrolovat, zda deska není poškozená.
- **Příznak:** kurz kompasu při přidání plynu „ujíždí“
  - Možná příčina: magnetické rušení od silových vodičů.
  - Co udělat: přemístit kompas s GPS na stožárek, zkroutit silové vodiče.
- **Příznak:** výška podle barometru ve visu skáče
  - Možná příčina: proud vzduchu od vrtulí míří na senzor.
  - Co udělat: zakrýt barometr molitanem.
- **Příznak:** přijímač na UART na F4 nefunguje
  - Možná příčina: SBUS je připojen na port bez invertoru.
  - Co udělat: použít port s invertorem (je označen) nebo protokol bez inverze (CRSF).
- **Příznak:** záznam Blackboxu se přerušuje nebo má mezery
  - Možná příčina: konflikt o DMA nebo pomalá flash paměť.
  - Co udělat: snížit frekvenci logování, vypnout kolidující funkci (LED), použít SD místo flash.
- **Příznak:** FC se po připojení GPS + VTX + kamery restartuje
  - Možná příčina: je překročen proud BEC 5 V/9 V.
  - Co udělat: sečíst proudy, přesunout spotřebič na samostatný BEC.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Flight Controller Hardware — ArduPilot | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Compass Setup — ArduPilot | https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | primary | A

## checklist
- Znám řadu procesoru své FC a vím, že ho firmware podporuje
- Mám UART své desky rozepsané pro přijímač, GPS a VTX
- Vím, která napájecí ploška je pro kterou periferii
- Deska je na tlumičích a její orientace je zadána ve firmwaru
- Senzory jsou po stavbě zkontrolovány v konfigurátoru
