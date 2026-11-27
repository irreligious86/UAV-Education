---
id: f-motors-esc
title: "Motory, ESC a DShot"
level: L1
readingTime: 20 min
firmware: libovolný firmware
status: published
added: 2026-11-07
tags:
  - motory
  - ESC
  - DShot
related:
  - f-power
  - bf-rpm-filter
next:
  - f-fc-sensors
source: content/foundation/f-motors-esc.md
source_hash: 46a5be24d49c
---

## summary
Bezkartáčový motor se sám netočí: řídí ho regulátor otáček (ESC), který dostává povely od řídicí jednotky (FC). Modul vysvětluje, co znamenají čísla jako „2207 1750KV“, co jsou póly, proč všichni přešli z analogového PWM na digitální DShot a jaký firmware pro ESC je aktuální v roce 2026 po ukončení BLHeli_32.

## theory
### Značení motoru
- **2207** – rozměr statoru: průměr 22 mm, výška 7 mm. Větší stator znamená větší moment.
- **KV** – otáčky na volt bez zátěže. 1750KV na 6S (25.2 V) je přibližně 44 000 ot/min bez vrtule. Pod zátěží méně.
- **12N14P** – 12 cívek statoru, 14 magnetů. Počet magnetů je `motor_poles` ve firmwaru a je potřeba pro RPM filtr.

Pravidlo výběru: velká vrtule vyžaduje velký moment a nízké KV, malá vrtule vysoké KV. Motor s vysokým KV se na velké vrtuli přehřívá a odebírá obrovský proud.

### Co dělá ESC
Bezkartáčový motor je třífázový. ESC střídavě přivádí proud do fází, a vytváří tak točivé magnetické pole. Polohu rotoru určuje bez senzorů – podle elektromotorického napětí indukovaného v nenapájené fázi (sensorless). Odtud desync: při prudké změně plynu může ESC rotor „ztratit“ a motor sebou škubne nebo se zastaví.

### Řídicí protokoly
- **PWM** – impulz 1000–2000 µs s frekvencí kolem 50 Hz. Analogový, pomalý, vyžaduje kalibraci rozsahu. Dodnes se s ním setkáte u serv a těžkých ESC.
- **OneShot, Multishot** – stejné impulzy, jen kratší a častější. Historická etapa.
- **DShot150/300/600** – digitální protokol: 16bitový paket s kontrolním součtem, kalibrace není potřeba, rušení plyn neposouvá. Číslo udává rychlost v kilobitech.
- **Bidirectional DShot** – ESC v odpovědi posílá eRPM motoru. Na tom je postaven RPM filtr.

{{diagram:dshot-frame|Rámec DShot: 11 bitů plynu, bit žádosti o telemetrii a 4 bity CRC.}}

Otáčky se z eRPM počítají takto: RPM = eRPM / (počet magnetů / 2).

### Firmware ESC v roce 2026
- **BLHeli_S** – starší 8bitové ESC, firmware je otevřený. Nahrává se na ně **Bluejay** – s bidirectional DShot a RPM filtrem.
- **BLHeli_32** – 32bitové ESC. Projekt byl ukončen v červnu 2024: server pro nahrávání firmwaru je vypnutý, další aktualizace nebudou. Stávající ESC dál fungují a dají se nastavovat.
- **AM32** – otevřený firmware pro 32bitové ESC, de facto náhrada BLHeli_32. Přechod z BLHeli_32 na AM32 je jednosměrný.

### Proud ESC
ESC se vybírá podle trvalého proudu s rezervou vůči skutečnému špičkovému proudu z logu. Provedení 4-in-1 je pohodlné a lehké, ale přehřátí jednoho kanálu často zničí celou desku.

### Fyzika motoru ve dvou vzorcích
Bezkartáčový motor popisují dvě navzájem svázané konstanty: **KV** (ot/min na volt) a **Kt** (moment na ampér). Kt = 60/(2π·KV) N·m/A: motor 1750KV dává 0.0055 N·m na ampér, motor 380KV 0.025 N·m/A. Proto nízké KV = velký moment na ampér = velká vrtule bez přehřívání; vysoké KV = otáčky pro malou vrtuli. Otáčky pod zátěží: n = KV · (U − I·R_vinutí) – pokles způsobuje odpor vinutí (desítky mΩ) a vnitřní odpor baterie. Teplo ve vinutí P = I²·R: při 30 A a 40 mΩ je to 36 W na motor; chladičem je jen samotný zvon motoru (rotor) a proud vzduchu od vrtule.

Rozměr statoru určuje moment (objem magnetického materiálu): statory 2207 a 2306 mají objem téměř stejný a rozdíl mezi nimi je menší než mezi výrobci. Obvykle se má za to, že širší stator (2306) dává o něco větší moment a ostřejší odezvu, kdežto vyšší (2207) lépe odvádí teplo při dlouhých letech – porovnávejte podle tabulek tahu konkrétních motorů, ne podle čísel rozměru. Počet pólových dvojic (14 magnetů = 7 dvojic) určuje přepočet eRPM → RPM a frekvenci komutace: při 30 000 ot/min dává 7 dvojic 3500 elektrických otáček/s.

### Co ESC dělá každých pár mikrosekund
ESC je třífázový střídač se 6 tranzistory MOSFET. Komutuje fáze podle polohy rotoru, kterou odhaduje ze zpětného elektromotorického napětí v nenapájené fázi (zero-crossing). Parametry firmwaru ESC, které má smysl řešit:
- **PWM frequency** (24/48/96 kHz) – frekvence PWM na spínacích tranzistorech: vyšší znamená tišší a plynulejší chod při malém plynu, ale větší spínací ztráty a ohřev ESC; 48 kHz je kompromis pro 5".
- **Timing** (motor timing; ve firmwarech 0–30°, výchozí AM32 15°, Bluejay 22.5°) – předstih komutace: vyšší dává víc otáček a proudu a víc tepla, ale větší rezervu proti demagnetizaci; nižší je chladnější a účinnější, ale těžké vrtule a motory s velkou indukčností častěji ztrácejí synchronizaci při prudkém plynu.
- **Demag compensation** – ochrana před desyncem při prudkých změnách plynu, hlavně při zrychlení z malých otáček s těžkou vrtulí (demagnetizační proud roste s proudem motoru). Start pro každou třídu je výchozí hodnota firmwaru ESC (Bluejay Low, AM32 `demag_comp` podle tabulky v `f-esc-firmware`); zvyšovat o jeden stupeň jen při známce desyncu: propad eRPM jednoho motoru při prudkém plynu v Blackboxu. Častěji to potřebují velké motory s těžkými vrtulemi, 7" a víc (odhad kurzu). Kontrola po každém stupni: tři punch-outy z visu na 100 % bez propadů eRPM (`f-esc-firmware`).
- **Startup power / rampup** – plynulý rozběh velkých vrtulí.
- **Current limit / temperature protection** – ESC při přehřátí snižuje výkon: v logu to vypadá jako „propad tahu“.
Desync znamená, že ESC ztratil polohu rotoru: motor sebou škube, piští, klesá tah; příčinami jsou dlouhé fázové vodiče, slabá kompenzace demagnetizace nebo nízký timing pro těžkou vrtuli, příliš velká vrtule pro dané KV, starý firmware.

### DShot: jak je rámec uspořádán
16 bitů: 11 bitů hodnoty (0 – stop, 1–47 – speciální příkazy, 48–2047 – plyn), 1 bit žádosti o telemetrii, 4 bity CRC. Bit je kódován šířkou impulzu: „1“ ≈ 75 % periody bitu, „0“ ≈ 37 %; DShot300 – bit 3.33 µs, rámec 53 µs; DShot600 – 1.67 µs a 27 µs. Rámec se odesílá v každém cyklu PID. **Bidirectional DShot**: po rámci se směr linky obrátí a ESC odpoví rámcem s eRPM (perioda elektrické otáčky) zakódovaným v GCR; chyby této odpovědi jsou vidět jako `E%` na záložce Motors – normální hodnota je nejvýš 1 % (orientační hodnota kurzu, `bf-rpm-filter`; obvykle kolem 0), při vyšším podílu staví RPM filtr notche mimo skutečné frekvence. Notch (pásmová zádrž) je úzký „výřez“ ve spektru gyroskopu: tlumí jednu frekvenci a sousední téměř nechá; RPM filtr klade tyto výřezy na otáčkové frekvence motorů podle eRPM, takže chybné eRPM nebo `motor_poles` posune výřez mimo šum. Speciální příkazy DShot (1–47): bzučák, obrácení směru otáčení (`dshot_cmd` 7/8 – `motor direction`), zapnutí/vypnutí 3D, dotaz na informace o ESC – ty používá konfigurátor na záložce Motors.

### Řešený příklad: výběr dvojice motor–vrtule
5" freestyle 6S, 700 g: je potřeba T/W ≥ 6 (pásmo freestylu v `f-physics`) → 4200 g celkem, maximálně 1050 g na motor. Tabulka motoru 2207 1750KV s vrtulí 5.1×3: maximum ~1600 g při 38 A – rezerva je, vis ~180 g na motor při ~4 A. ESC 45 A 4-in-1 – trvalých 45 A při špičce 38 A na kanál: stačí, ale při agresivním letu s čerstvou baterií je to „na hraně“; s 55–60 A budete klidnější. 7" long range 6S 1.4 kg: 2806.5 1300KV + 7×3.5: maximum ~1200 g při ~22 A → ESC 35–45 A. Rozdíl KV mezi 5" a 7" je dán právě momentem na vrtuli (Kt).

{{diagram:motor-esc-selection|Цепочка подбора: ток ESC считают от пикового тока мотора по таблице тяги — 38 А × 1.3 = 49.4 А, поэтому 45 А впритык, а для 7" с 22 А хватает 35–45 А.}}

## practice
### Kontrola motorů a ESC na stole
1. Sundejte vrtule.
2. Při prvním zapnutí nové stavby připojte baterii přes omezovač proudu (smoke stopper).
3. Na záložce Motors roztočte každý motor na malý plyn: zkontrolujte směr a plynulost chodu.
4. S bidirectional DShot se přesvědčte, že každý motor posílá otáčky a chyby telemetrie téměř nejsou.
5. Zkontrolujte rukou: zvon motoru se točí bez vůle a bez drhnutí, magnety jsou celé, šrouby se nedotýkají vinutí.

### Volba protokolu
Pro Betaflight se rychlost DShot volí podle cyklu PID (pravidlo z `config/config.c` 2025.12.5): rámec i odpověď bidir DShot se musí vejít do cyklu, takže DShot300 s bidir dovolí PID do 4 kHz při gyru 8 kHz, DShot600 do 8 kHz. Na F405, F411 a G47x (a APM32F405/F407) s `dshot_bidir = ON` firmware sám přepíše DSHOT600 na DSHOT300 a PID na 4 kHz, kromě F405 s `cpu_overclock` od 216 MHz (`bf-filters`; `f-micro-whoop`). F7, H7 a AT32F435 toto omezení nemají: DSHOT600 při PID 8 kHz, DSHOT300 při PID 4 kHz a níže nebo při chybách DShot nad 1 % (orientační hodnota kurzu). Kontrola: `status` v CLI a chyby DShot v záložce Motors. Pro ArduPilot DShot tam, kde ho ESC podporuje, jinak PWM s kalibrací.

### Co zapsat: tabulka motorů
| Motor | Směr | Zvuk a plynulost | Vůle, drhnutí | eRPM při 10 % plynu | Chyby DShot |
|---|---|---|---|---|---|
| 1 | ✓ / ✗ | rovnoměrně / vrčí | ne / ano | … | … % |

- **Omezovač proudu.** Žárovka nebo smoke stopper při připojení krátce blikne (nabíjejí se kondenzátory) a zhasne. Pokud svítí jasně a trvale, je někde zkrat: baterii odpojte a hledejte.
- **Směr.** Porovnejte se schématem rámu na záložce Motors (Betaflight) nebo s testem motorů v pozemní stanici (ArduPilot: Optional Hardware → Motor Test, motory podle písmen A, B, C… od předního pravého ve směru hodinových ručiček). Špatný směr se mění ve firmwaru ESC nebo příkazem DShot – viz modul „Firmware ESC“.
- **Zvuk a ruce.** Motor, který při malém plynu vrčí nebo sebou škube, je kandidát na desync nebo poškozené vinutí. Vůle zvonu motoru znamená ložisko.
- **Telemetrie.** Se zapnutým bidir DShot jsou u každého motoru vidět otáčky a chyby při připojené baterii nesmí být vyšší než 1 %. Pokud je chyb víc, zkontrolujte pájení signálových vodičů a zem a zkuste také DShot300 místo 600.
- **Firmware ESC.** Zapište si, co je na regulátoru nahráno (BLHeli_S, Bluejay, BLHeli_32, AM32) a zda tento firmware podporuje bidir DShot: na tom závisí, jestli bude fungovat RPM filtr.

Laboratorní úloha je splněna, když první zapnutí proběhlo bez vrtulí a přes omezovač proudu, tabulka je vyplněna pro každý motor, je zjištěn firmware ESC a podpora bidir DShot a chyby telemetrie DShot při připojené baterii nepřesahují 1 %.

## diagnostics
- **Příznak:** jeden motor je teplejší než ostatní
  - Možná příčina: ložisko, zadrhávání, poškozené vinutí nebo vrtule.
  - Co udělat: porovnat hmatem otáčení zvonů motorů, prohodit podezřelý motor s jiným a sledovat, zda se problém „přestěhoval“.
- **Příznak:** motor sebou škube nebo se zastaví při prudkém přidání plynu
  - Možná příčina: desync ESC.
  - Co udělat: zkontrolovat nastavení timing/demag ve firmwaru ESC a pájení fází.
- **Příznak:** po připojení baterie ESC mlčí nebo nezahraje melodii
  - Možná příčina: ESC nemá napájení, shořel kanál, není zvolen protokol.
  - Co udělat: zkontrolovat pájení silových vodičů, `MOTOR_PROTO` mezi flagy blokujícími armování (Arming Disable Flags), firmware ESC.
- **Příznak:** RPM filtr se nezapne
  - Možná příčina: firmware ESC bez bidirectional DShot nebo špatná hodnota `motor_poles`.
  - Co udělat: nahrát Bluejay nebo AM32, přepočítat magnety.
- **Příznak:** motor sebou škube nebo piští při prudkém přidání plynu
  - Možná příčina: desync – demag/timing, dlouhé vodiče, vrtule příliš těžká pro dané KV.
  - Co udělat: nejdřív zvýšit demag, pak timing o stupeň výš (hlídat teplotu motorů), zkontrolovat fázové vodiče; když to nepomůže, menší vrtule (podrobně – `f-esc-firmware`).
- **Příznak:** `E%` na záložce Motors je vyšší než nula
  - Možná příčina: chyby bidirectional DShot – firmware ESC, rušení signálu, rychlost DShot.
  - Co udělat: aktualizovat ESC (Bluejay/AM32), použít DShot300 místo 600, zkrátit signálové vodiče.
- **Příznak:** tah se po minutě letu „propadne“
  - Možná příčina: tepelná ochrana ESC nebo motoru.
  - Co udělat: zkontrolovat teplotu ESC v telemetrii, zajistit ofukování, snížit PWM frequency, ověřit proud podle logu.

## references
- DShot RPM Filtering — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- BLHeli32, AM32 and BLHeli_S ESCs — ArduPilot | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A
- AM32 — firmware source (GitHub) | https://github.com/am32-firmware/AM32 | primary | A
- Bluejay — firmware source (GitHub) | https://github.com/bird-sanctuary/bluejay | primary | A
- The end of BLHeli_32 — Oscar Liang | https://oscarliang.com/end-of-blheli_32 | secondary | B

## checklist
- Umím rozluštit značení 2207 1750KV 12N14P
- Vím, jaký firmware je na mých ESC a zda podporuje bidirectional DShot
- Mám každý motor zkontrolovaný bez vrtulí: směr, plynulost chodu, vůle
- Znám skutečný špičkový proud z logu a proudovou rezervu ESC
