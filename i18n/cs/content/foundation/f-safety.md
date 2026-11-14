---
id: f-safety
title: "Bezpečnost a předletová kontrola"
level: L1
readingTime: 25 min
firmware: libovolný firmware
status: published
added: 2026-11-07
tags:
  - bezpečnost
  - kontrolní seznam
  - LiPo
  - armování
related:
  - bf-failsafe
  - f-power
  - f-regulations
  - ops-field
next:
  - f-regulations
source: content/foundation/f-safety.md
source_hash: c3dbe1ced49d
---

## summary
Konec listu pětipalcové vrtule se pohybuje rychlostí kolem 300 km/h a nese dost energie na to, aby rozřízl kůži až na kost; LiPo při zkratu dodá stovky ampérů a hoří s vlastním okysličovadlem: plamen lze srazit, ale hoření se obnovuje, dokud články nevychladnou. Většina úrazů v tomto hobby se nestane ve vzduchu, ale na stole: dron se při nastavování armoval s nasazenými vrtulemi. Modul podává fyziku nebezpečí v číslech, pravidla, o kterých se nediskutuje, úplný seznam flagů blokujících armování (Arming Disable Flags) v Betaflightu (ze zdrojového kódu, s vysvětlením) a jejich obdobu v ArduPilotu, předletový a poletový kontrolní seznam a postup při požáru baterie.

## theory
### Nebezpečí v číslech
- **Vrtule.** Obvodová rychlost konce listu = π · D · n. Pro 5" (D = 0.127 m) ve visu při 14 000 ot/min (233 ot/s): 0.40 m × 233 ≈ 93 m/s – asi 335 km/h; bez zátěže až 30 000 ot/min – 200 m/s. Kinetická energie rotující 5" vrtule (~4 g) činí jednotky joulů: stačí to na hluboké řezné rány; u 7–10" jsou to desítky joulů a zlomeniny prstů; 15" na X8 – zranění neslučitelná s pokračováním v hobby.
- **Motory na stole.** Test motorů v konfigurátoru bez sundaných vrtulí je klasický úraz. Firmware varuje, ale nezastaví vás.
- **LiPo.** Vnitřní odpor 1–3 mΩ na článek: zkrat 6S baterie znamená proud ve stovkách ampérů, vodič se rozžhaví během sekundy. Článek proražený při pádu se může vznítit i několik minut nebo hodin po nárazu. Hoření je tepelný únik (thermal runaway), při kterém se z katody uvolňuje kyslík: srazte plamen (hasicí přístroj ABC, písek), potom **chlaďte velkým množstvím vody**, nebo baterii vyneste v nehořlavé nádobě ven a nechte ji dohořet. Hasicí přístroj třídy D je určen na kovové lithium – to v LiPo ani Li-Ion není. Nafouknutá baterie je vyřazená: vybijte ji na 0 ve slané vodě (několik dní) a odevzdejte k likvidaci.
- **Ztráta spojení.** Pokud failsafe není na tomto stroji vyzkoušený, udělá to, co si nikdo nevybral (modul „Failsafe“).
- **První let po jakékoli změně** – zaměněný motor, směr vrtule, špatný mixer, neověřený filtr: statisticky nejnebezpečnější vzlet.

### Jak firmware brání armování (Betaflight master; ve 2025.12 není `AUTOPILOT_SW`, ve 4.5 nejsou `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW` a `ARM_SWITCH` se jmenuje `ARMSWITCH`)
Armovat nelze, dokud je aktivní alespoň jeden flag blokující armování. Jejich seznam je v `src/main/fc/runtime_config.c`, vypíše je příkaz `status` v CLI a ukazuje je OSD (prvek „Warnings“):

{{diagram:arming-tree|Diagnostický strom „nejde armovat“: nejdřív přečteme flag, potom ověříme konkrétní příčinu.}}

| Flag | Co znamená | Co udělat |
|---|---|---|
| `NOGYRO` | gyroskop nebyl nalezen | zkontrolovat desku/target, nelétat |
| `FAILSAFE` / `BOXFAILSAFE` | aktivní failsafe (není RC) / zapnutý přepínač failsafe | obnovit spojení, vypnout přepínač |
| `RXLOSS` | chybí signál přijímače | bind, napájení RX, protokol portu |
| `NOT_DISARMED` | armování nebylo vypnuto po… | vypnout armování přepínačem |
| `RUNAWAY` | zasáhla ochrana runaway takeoff | vypnout armování; zkontrolovat směr motorů/vrtulí |
| `CRASH` | detektor pádu | vypnout armování/restartovat |
| `THROTTLE` | plyn není na minimu | páka plynu dolů, zkontrolovat `min_check` |
| `ANGLE` | náklon větší než `small_angle` | srovnat do roviny, nebo `small_angle = 180` pro Acro |
| `BOOTGRACE` | ještě neuplynula doba po zapnutí | počkat |
| `NOPREARM` | není zapnutý PREARM | zapnout PREARM |
| `LOAD` | přetížení procesoru | snížit frekvenci smyčky/vypnout funkce |
| `CALIB` | probíhá kalibrace | počkat |
| `CLI`, `CMS`, `MSP`, `BST` | otevřené CLI / menu OSD / připojený konfigurátor | zavřít – a je to tak správně |
| `PARALYZE` | aktivován režim PARALYZE | restartovat |
| `GPS` | GPS Rescue vyžaduje fix a ten není | počkat na fix, nebo požadavek vypnout |
| `RESCUE_SW` | přepínač GPS Rescue zapnutý při armování | vypnout |
| `DSHOT_TELEM` | RPM filtr je zapnutý, ale eRPM z ESC nepřichází | `dshot_bidir`, firmware ESC, vodiče |
| `REBOOT_REQD` | po změně nastavení je nutný restart | restartovat |
| `DSHOT_BBANG` | chyba bitbang DShot | zkontrolovat resources/časovače |
| `NO_ACC_CAL` | akcelerometr není zkalibrovaný | kalibrace |
| `MOTOR_PROTO` | protokol motorů není nastavený | vybrat DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, `AUTOPILOT_SW` | přepínač režimu zapnutý při armování | vypnout |
| `ARM_SWITCH` | přepínač ARM byl při připojení zapnutý | vypnout a znovu zapnout |

Tyto flagy jsou pojistka, ne překážka. Pravidlo: odstraňujte příčinu, nevypínejte kontrolu. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, bitová maska **přeskakovaných** kontrol; do 4.7 `ARMING_CHECK`, bitová maska zapnutých: barometr, kompas, GPS, INS, parametry, RC, napětí, geofence…), zprávy „PreArm: …“ v GCS – stejná logika; přeskakovat kontroly je přípustné jen na zkušebním stole.

### Režimy a zařízení pro ochranu
- **PREARM** – druhý přepínač, bez kterého armovat nelze; povinný na strojích s vrtulemi 7"+.
- **Failsafe** – co dělat při ztrátě spojení; zkouší se na zemi bez vrtulí před prvním letem každé nové stavby.
- **Beeper** a **GPS v OSD** – k nalezení spadlého stroje.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) – vypne armování, pokud gyroskop po armování ukazuje rostoucí rotaci bez reakce na řízení (zaměněné motory/vrtule).
- **Bzučák při vybití, časovač** – abyste neodletěli s vybitou baterií.

### Plocha a lidé
Poloměr bezpečné zóny kolem místa vzletu je nejméně 10–15 m pro 5", 30 m pro těžké stroje; při armování nikdo nestojí v rovině vrtulí; vzlet směrem od sebe. Pravidla a zóny – modul „Pravidla“, organizace týmu – „Provoz v terénu“.

## practice
### Předletový kontrolní seznam (vytisknout)
1. Vrtule: nepoškozené, dotažené, směr podle schématu motorů, v rovině vrtulí žádné cizí předměty.
2. Baterie: bez nafouknutí a poškození, napětí článků v normě (4.1–4.2 V/článek při plném nabití), upevněná páskem, konektor XT není natavený.
3. Antény RC a VTX: na místě, nepoškozené, mimo rovinu vrtulí; VTX s anténou (bez ní shoří).
4. Vysílačka: správný model, nabitá, přepínače ARM/PREARM vypnuté, test failsafe na tomto stroji proveden.
5. Video/OSD: napětí, LQ/RSSI, varování – žádné flagy.
6. Zóna: lidé a zvířata mimo poloměr, vzlet směrem od sebe, překážky zohledněné, pravidla plochy.
7. Po armování: 2–3 s visu ve výšce 0.5–1 m – odezva, zvuk, žádné chvění; při čemkoli podezřelém přistát.

### Pravidla na stole
1. Vrtule sundat před připojením baterie. Vždy. Včetně „jen na vteřinu“.
2. První zapnutí nové/přepájené stavby – přes smoke stopper, předtím kontrola multimetrem (modul „Elektřina 101“).
3. Test motorů – jen bez vrtulí, s omezeným plynem, s rukou u konektoru baterie.
4. Konfigurátor připojen → flag `MSP` → armovat nelze. Neobcházet.
5. Nabíjení LiPo – v nehořlavém vaku/boxu, pod dohledem, s balancováním, ne na hořlavém povrchu; skladování při 3.8 V/článek.

### Při požáru baterie
1. Nesahat rukama, nefoukat. Odstoupit, nechat odstoupit ostatní (kouř je toxický).
2. Zasypat pískem/zeminou, nebo odtáhnout kovovým předmětem na nehořlavý povrch.
3. Hasicí přístroj – srazit plamen, potom chladit (hoření se může obnovovat).
4. Potom hodinu nenechávat bez dozoru; zbytky do kovové nádoby.

### Po letu
1. Vypnout armování, vysílačku vypnout jako poslední (ne jako první!), odpojit baterii.
2. Teplota motorů a ESC rukou; prohlídka vrtulí a rámu.
3. Zápis do deníku stroje: co se změnilo, jak letěl, čeho jste si všimli; log – pokud šlo o zkušební let.

## diagnostics
- **Příznak:** dron nejde armovat
  - Možná příčina: je aktivní flag blokující armování.
  - Co udělat: `status` v CLI nebo OSD Warnings; tabulka výše; odstranit příčinu.
- **Příznak:** dron se armoval hned po připojení baterie
  - Možná příčina: přepínač ARM byl zapnutý a ochrana `ARM_SWITCH` je vypnutá/nezasáhla, nebo je armování přiřazeno špatnému kanálu.
  - Co udělat: zkontrolovat Modes, rozsah kanálu ARM, přidat PREARM.
- **Příznak:** po armování stroj vyrazil do strany a armování se vypnulo
  - Možná příčina: runaway takeoff – zaměněné motory/směr vrtulí.
  - Co udělat: test motorů bez vrtulí, schéma směrů, remap přes `resource`/`motor`.
- **Příznak:** baterie se po pádu zahřívá bez zátěže
  - Možná příčina: vnitřní zkrat.
  - Co udělat: izolovat venku na nehořlavém povrchu, sledovat, nenabíjet, odevzdat k likvidaci.
- **Příznak:** VTX je horký, obraz není
  - Možná příčina: byl zapnut bez antény.
  - Co udělat: anténa vždy před napájením; VTX už může být poškozený.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A

## checklist
- Na stole je dron vždy bez vrtulí – bez výjimek
- Znám všechny flagy blokující armování a vím, co s každým dělat
- Předletový kontrolní seznam je vytištěný a používá se
- Failsafe je na tomto dronu vyzkoušený bez vrtulí
- Znám postup při požáru LiPo a vím, kde je písek
- Po letu vedu záznam v deníku stroje
