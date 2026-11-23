---
id: diag-troubleshooting
title: "Diagnostický strom: dron nevzlétne"
level: L1
readingTime: 40 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - diagnostika
  - závady
  - rozhodovací strom
  - troubleshooting
related:
  - f-electricity-101
  - bf-failsafe
  - el-measure
  - ops-case-studies
next:
  - bf-blackbox
source: content/foundation/diag-troubleshooting.md
source_hash: 89e1c8e01676
---

## summary
Hledání závady není zkoušení dohadů, ale vylučování větví stromu, kde je každý krok potvrzen faktem: měřením multimetrem, hlášením firmwaru, řádkem logu. Modul dává strom pro pět typických situací – „nejde armovat“, „motory se netočí nebo se točí špatně“, „při přidání plynu začne bláznit“, „ESC nebo deska při připojení baterie hoří“, „ztrácí spojení nebo video“ – a pravidlo, jak do něj doplňovat vlastní případy. Nástroje: smoke stopper, multimetr, `status` v CLI a hlášení pre-arm, Blackbox/DataFlash.

## theory
### Pravidla diagnostiky
1. **Nejdřív fakt, potom hypotéza.** Firmware téměř vždy *říká*, co je špatně: Betaflight – `status` v CLI (řádek Arming disable flags, tedy flagy blokující armování), INAV – záložka Status a `status` v CLI, ArduPilot – hlášení PreArm v GCS. Začínejte u nich, ne u přepájení.
2. **Jedna změna – jedno ověření.** Změníte dva parametry a začne to fungovat – nevíte, který pomohl, a nevíte, co se tím rozbilo.
3. **Od levného k drahému.** Prohlídka a multimetr přicházejí na řadu dřív než osciloskop a výměna desky.
4. **Bezpečnost v každém kroku.** Při všem, co souvisí s motory, jsou vrtule sundané. První zapnutí po jakémkoli pájení vždy přes smoke stopper.
5. **Zapisujte si postup.** Kroky s výsledky patří do poznámek; nalezená příčina do stromu a do deníku stroje.

### Strom 1. Nejde armovat
Přečtěte si příčinu: Betaflight CLI → `status` → `Arming disable flags: ...`. CLI vypisuje krátké názvy z `runtime_config.c` (FAILSAFE, CALIB, NO_ACC_CAL, CMS, BOOTGRACE, MOTOR_PROTO, DSHOT_TELEM, ARMSWITCH ve 4.5 / ARM_SWITCH ve 2025.12+); část flagů je níže pojmenována podle dokumentace. Nejčastější:
- **RXLOSS / RX_FAILSAFE** – přijímač nedává kanály. → Port a protokol (UART, CRSF/SBUS, inverze pro SBUS na F4), bind, napájení přijímače (5 V změřit multimetrem), záložka Receiver – hýbou se kanály?
- **THROTTLE** – plyn je nad minimem. → Kalibrace kniplů ve vysílačce, `min_check`, reverz kanálu.
- **ANGLE** – stroj je nakloněn víc než `small_angle`. → Podložka, kalibrace akcelerometru.
- **CALIBRATING / ACC_CALIBRATION / NOGYRO** – gyroskop není zkalibrován nebo nebyl nalezen. → Stroj musí být při zapnutí v klidu; NOGYRO znamená hardwarovou závadu nebo špatný target firmwaru.
- **ARM_SWITCH** – přepínač armování byl při připojení napájení zapnutý. → Vypnout, zapnout.
- **MSP / CLI / CMS_MENU** – je připojen konfigurátor nebo je otevřené menu OSD. → Odpojit USB, opustit menu.
- **NOPREARM** – je nastaven režim prearm, ale není aktivován.
- **DSHOT_TELEM** (do 4.5 RPMFILTER) – je zapnutý RPM filtr, ale chybí telemetrie ESC (firmware ESC nepodporuje DShot bidir, nebo není zapnutý).
- **BOOT_GRACE_TIME** – stačí po zapnutí několik sekund počkat.
- **MOTOR_PROTOCOL** – není zvolen protokol motorů.
INAV: záložka Status ukazuje příčiny (Navigation is unsafe, Compass not calibrated, Hardware failure...). ArduPilot: `PreArm: ...` v GCS – každý řádek jmenuje viníka (Compass not calibrated, Gyros inconsistent, RC not calibrated, Throttle below failsafe, GPS: No Fix, Battery failsafe atd.); kontroly v `ARMING_SKIPCHK` (do 4.7 `ARMING_CHECK`) nevypínejte – opravte příčinu.

{{diagram:arming-tree|Strom 1 jako schéma: flag → příčina → kontrola.}}

### Strom 2. Motory se netočí / točí se špatně
Vrtule jsou sundané.
- **Na záložce Motors nereaguje žádný motor.** → Odpovídají protokol (DShot300/600) a `motor_pwm_protocol` tomu, co umí ESC? → Mají ESC napájení (napětí na pájecích ploškách)? → Jsou signálové vodiče na správných ploškách (`resource MOTOR`)? → Pípají ESC při připojení napájení (startovací melodie)? Pokud ne, ESC je mrtvý nebo nemá napájení.
- **Jeden motor se netočí, ostatní ano.** → Prohoďte signálové vodiče s motorem, který funguje: pokud se závada přestěhovala s vodičem, je to signál nebo ploška FC; pokud zůstala, je to ESC nebo motor. → Je odpor všech tří fází motoru stejný? → Zkontrolujte pájení fází (studený spoj je typický).
- **Motor cuká a nerozběhne se.** → Jedna fáze ztratila kontakt (pájení, prodřený vodič), nebo je poškozený ESC. → Změřte průchodnost fází a pohněte vodiči.
- **Točí se na špatnou stranu / ve špatném pořadí.** → Záložka Motors: u každého motoru zvlášť ověřte číslo a směr podle schématu rámu; směr měňte ve firmwaru ESC (BLHeli Suite/Configurator) nebo přepájením dvou fází. Směr „props in/out“ musí být stejně nastaven u všech čtyř.
- **Dron se při vzletu převrátí.** → Patří do stromu 2: pořadí nebo směr motorů, případně špatný mixer (`mixer` není pro váš rám).

### Strom 3. „Blázní“ při přidání plynu
Příznak: visí normálně, nad 60–70 % plynu se třese, motory jsou horké a dron se chová nepředvídatelně.
- **Máte log z Blackboxu?** Pokud ne, nahrajte ho, jinak jen hádáte. Spektrum gyroskopu: obrovská špička na frekvenci motorů → mechanika (nevyváženost, vrtule, vůle motoru); širokopásmový šum roste s plynem → vibrace + nedostatečná filtrace; špička se s plynem nepohybuje → rezonance rámu.
- **Šum gyroskopu vzrostl po výměně nebo opravě?** → Je na silové sběrnici kondenzátor? Zkontrolujte pájení jeho vývodů a kapacitu. → Uchycení FC (silentbloky, napnuté vodiče).
- **ESC desync** (motor náhle ztratí otáčky, cukne a pak se vzpamatuje; v logu je propad eRPM jednoho motoru): → Nastavení ESC (timing, demag), příliš rychlý DShot na dlouhé vodiče, poškozený motor; snižte protokol na DShot300 a zkontrolujte fáze.
- **Úbytek napětí:** v logu VBAT při přidání plynu klesá pod práh → BEC restartuje FC (okamžitá ztráta řízení), nebo ESC přejdou do ochrany. → Konektor, baterie, pájení.
- **PID/filtry**: příliš velké D nebo P při nedostatečné filtraci → oscilace při vysokém plynu, kde je šumu víc. → Filtry nastavte podle spektra, potom snižte D.
- **Rušení přijímače od VTX na plný výkon** (LQ klesá s plynem – vzácné, ale stává se to při zvlnění napájení VTX): → filtr napájení VTX, větší vzdálenost mezi anténami.

### Strom 4. Při připojení baterie něco hoří nebo se z toho kouří
Okamžitě odpojte. Dál už jen přes smoke stopper (žárovka nebo omezovač zapojený do kladného vodiče).
- **Žárovka svítí jasně, dron se nezapne – zkrat.** → Odpojujte spotřebiče jeden po druhém (ESC, FC, VTX, kamera), počínaje tím, který byl připájen naposled; kde žárovka zhasne, tam je zkrat. → Změřte průchodnost mezi + a − u každého zařízení zvlášť. → Typická místa: můstek pájky mezi ploškami, šroub ve vinutí motoru (příliš dlouhý šroub), vodič přiskřípnutý rámem, přehozená polarita konektoru (2pinový JST-PH má u různých výrobců obrácenou polaritu – klasika), kondenzátor zapojený obráceně.
- **Žárovka slabě žhne, dron funguje** – to je normální (nabíjecí proud kondenzátorů a provoz BEC).
- **Je cítit zápach, ale žárovka nesvítila** – součástka shořela už dříve; zkontrolujte napětí BEC (je na výstupu 5 V?), po krátkém zapnutí prstem teplotu čipů a pod lupou viditelná poškození.
- **ESC shořel při prvním připojení** → polarita, napětí vyšší než dovolené (6S na ESC pro 4S), fáze zkratované na zem (šroub), můstek pájky mezi fází a napájením.
- **Shořelo to po nahrání firmwaru do ESC** → špatný target nebo nastavení, vzácný případ; ale 90 % případů „shořelo po flashování“ je souběh s novým pájením.

### Strom 5. Ztrácí spojení nebo video
- **Failsafe na malou vzdálenost** → LQ a RSSI v OSD: nízké RSSI – anténa (pájení, konektor U.FL, anténa pod karbonem), výkon TX, bind fráze; nízké LQ při normálním RSSI – rušení poblíž přijímače (VTX, měnič buck, companion). → Test dosahu na zemi (viz antény).
- **Video šumí při přidání plynu** → zvlnění napájení (kondenzátor, LC filtr), zem, anténa VTX.
- **Video se v dálce ztrácí, RC drží** → rezerva video spoje je vyčerpaná – to se dá čekat; antény, výkon a také to, zda je takový výkon povolený.
- **Spojení vypadává při otočení stroje** → polarizace nebo minimum vyzařovacího diagramu: druhá anténa pod úhlem 90°.
- **GPS nechytá satelity** → modul je pod karbonem, blízko zdroje rušení, nemá napájení (LED na modulu), špatný protokol nebo rychlost UART.

{{diagram:inair-disarm-tree|Дерево 6 в виде схемы: сначала — есть ли в логе событие дизарма; нет — ищи питание, есть — иди по ветке причины, а сработавший детектор аварии считай следствием.}}

### Jak strom rozšiřovat
Každý vlastní případ: příznak → kroky (s fakty) → příčina → do které větve ho doplnit. Za rok to bude vaše hlavní příručka. Část větví kurzu je už poskládaná automaticky: stránka „Poruchy a chyby“ obsahuje všechny oddíly „Řešení problémů“ ze všech modulů.

## practice
### Krok 1. Rozbor tří závad
Tři závady – vlastní, cvičné (vytvořte je: odpojte signálový vodič motoru, vypněte přijímač, nastavte špatně `min_check`) nebo z fóra s logem. Postupujte přísně podle stromu a zapisujte každý krok a fakt.

### Krok 2. Fakt v každém kroku
V zápisu každého kroku je to, co bylo změřeno nebo přečteno: „status: RXLOSS“, „5 V na RX: 4.98 V“, „fáze A–B 0.08 Ω, B–C 0.08, A–C přerušeno“. Kroky bez faktu předělejte.

### Krok 3. Doplnit strom
Alespoň jeden vlastní případ, který ve stromu není, zapište do své kopie stromu (soubor `troubleshooting.md` v inženýrské složce).

### Řešený příklad: záznam jednoho případu
Závada: motor 3 se po armování netočí, ostatní se točí.

| Krok stromu | Kontrola | Fakt | Závěr |
|---|---|---|---|
| Dojde povel až k ESC? | záložka Motors, posuvník motoru 3 | ESC při připojení napájení pípá, na posuvník nereaguje | ESC žije, signál chybí nebo je špatný |
| Signál na výstupu FC | `resource` v CLI, osciloskop nebo přehození signálového vodiče na sousední výstup | na sousedním výstupu se motor 3 točí | ESC i motor jsou v pořádku |
| Výstup FC | pájení plošky M3 pod lupou, měření průchodnosti | studený spoj signálového vodiče | příčina nalezena |
| Kontrola po opravě | Motors, všechny čtyři motory, chyby DShot | všechny se točí, chyby 0 % | uzavřeno |

Každý řádek je fakt, který lze zopakovat. Řádek „asi ESC“ bez ověření není krok, ale dohad.

### Co si ke třem závadám zapsat
- **Ke každé** tabulku kroků jako výše a čas strávený hledáním. Za měsíc porovnejte, jak se zkrátil.
- **Cvičné závady** vytvářejte tak, aby se nic nepoškodilo: odpojený signálový vodič (bez napájení!), vypnutý přijímač (Betaflight ukáže ve `status` flag `RXLOSS`), špatný `min_check` (páka plynu dole se nerozpozná jako „plyn dole“ a armování neproběhne kvůli flagu `THROTTLE`).
- **Vlastní případ do stromu:** větev s otázkou, kontrolou a příznakem. Například: „motory cukají při zapnutí videovysílače → rušení na signálových vodičích → přemístit VTX, ferity, DShot300“.

### Laboratorní úloha
Tři závady jsou nalezené podle stromu se zápisem kroků; každý krok je potvrzen měřením nebo hlášením firmwaru; strom je doplněn o vlastní případ.

Laboratorní úloha je splněna, když má každá ze tří závad tabulku kroků s fakty a závěrem, žádný závěr není udělán bez měření nebo hlášení firmwaru a v `troubleshooting.md` je doplněna vlastní větev stromu.

## diagnostics
- **Příznak:** „nic nepomohlo, po novém nahrání firmwaru to začalo fungovat“
  - Možná příčina: příčina nebyla nalezena, jde o souběh (nejčastěji se při tom znovu zapojily kontakty).
  - Co udělat: považujte závadu za nevyřešenou; zapište ji jako otevřený případ a sledujte ji.
- **Příznak:** závada je občasná, objeví se jednou za několik letů
  - Možná příčina: kontakt nebo pájení, vibrace, teplota.
  - V logu/na přístroji: událost v logu (propad eRPM, skok VBAT, RXLOSS) v okamžiku příznaku.
  - Co udělat: logujte každý let; při zapnutém dronu pohněte kabelovými svazky; ohřívejte bodově horkovzdušnou pistolí.
- **Příznak:** po výměně dílu příznak zůstal
  - Možná příčina: díl za to nemohl – větev byla vyloučena chybně.
  - Co udělat: vraťte se k poslednímu potvrzenému faktu.
- **Příznak:** dron se převrátí hned při vzletu
  - Možná příčina: přehozené pořadí motorů nebo směr otáčení, špatný mixer.
  - Co udělat: bez vrtulí ověřte na záložce Motors každý motor podle schématu rámu.

## references
- Betaflight — Arming Sequence & Safety (arming disable flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- ArduPilot — Pre-Arm Safety Checks (messages and causes) | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- ArduPilot — Diagnosing problems using logs | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- INAV — Troubleshooting / Status reasons (wiki) | https://github.com/iNavFlight/inav/wiki | secondary | B

## checklist
- Začínám u hlášení firmwaru (`status` / PreArm), ne u páječky
- Jedna změna – jedno ověření, každý krok s faktem
- První zapnutí po pájení vždy přes smoke stopper
- Tři závady jsou nalezené podle stromu a zapsané
- Vlastní diagnostický strom je založen v inženýrské složce
