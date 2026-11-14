---
id: inav-intro
title: "Úvod do INAV"
level: L1
readingTime: 20 min
firmware: INAV 7.0+
status: published
added: 2026-11-08
tags:
  - INAV
  - navigace
related:
  - bf-intro
  - ap-intro
next:
  - inav-gps
source: content/inav/inav-intro.md
source_hash: f1445c3a46b5
---

## summary
INAV vyrostl ze stejné kódové základny jako Betaflight, ale vydal se jiným směrem: k navigaci. Je to firmware pro ty, kdo potřebují držení pozice, návrat domů a mise na levné řídicí jednotce – a pro letouny, které Betaflight nepodporuje vůbec. Modul vysvětluje, kde INAV stojí mezi Betaflightem a ArduPilotem, co je v něm pilotovi Betaflightu povědomé, co je zásadně jinak (platforma, armování, navigační režimy, safehomes) a jak připravit první let.

## theory
### Místo INAV
- **Betaflight** – jen ruční létání, minimální zpoždění.
- **INAV** – ruční létání plus navigace: POSHOLD, RTH, mise, automatický vzlet letounu, automatické přistání. Běží na stejných deskách F4/F7/H7, se stejným přístupem ke konfigurátoru a podobným CLI.
- **ArduPilot** – plnohodnotný autopilot s EKF, Lua, companion počítačem, tisícovkou parametrů a nároky na hardware.

INAV je kompromis: navigace bez přechodu na H7 a bez studia ArduPilotu.

### Platforma
První rozhodnutí je `platform_type`: MULTIROTOR, AIRPLANE, TRICOPTER (hodnoty HELICOPTER, ROVER, BOAT v seznamu jsou, ale nejsou implementovány úplně). Na platformě závisí dostupné režimy, presety mixeru, přítomnost klapek a logika navigace. Letoun a kvadrokoptéra jsou chováním různé firmwary, i když je to jeden binární soubor.

### Co je povědomé z Betaflightu
Záložky Ports, Receiver, Modes, OSD, CLI se `set`/`get`/`save`/`diff all`, Blackbox. Přijímač přes CRSF nebo SBUS se připojuje stejně.

### Co je jinak
- **Armování jen přepínačem.** Armování kniply bylo odstraněno už v INAV 2.2.
- **Armování je bez GPS fixu blokováno**, pokud jsou nastavené navigační režimy (`nav_extra_arming_safety` to umí obejít, ale je to vědomé riziko).
- **Navigační režimy**: NAV ALTHOLD, NAV POSHOLD, NAV RTH, NAV WP, NAV CRUISE (pro letouny). POSHOLD a RTH vyžadují u multikoptéry zkalibrovaný kompas.
- **Domov** je bod prvního armování; **safehomes** je až 8 předem zadaných bezpečných bodů přistání; při RTH nahradí domov nejbližší z nich v dosahu `safehome_max_distance`.
- **Failsafe** s procedurami DROP, LAND (nouzové přistání), RTH, NONE. RTH jako failsafe je hlavní důvod, proč INAV nasadit.
- **Programming Framework** – logické podmínky přímo ve firmwaru, bez Lua.

### Požadavky
Navigace znamená GPS (povinně), kompas (u multikoptéry povinný pro POSHOLD/RTH) a barometr (u multikoptéry prakticky povinný: bez něj se výška drží jen podle GPS a akcelerometru, znatelně hůř). U letounu lze kurz odhadovat z GPS, kompas je žádoucí.

### Co je pod kapotou: estimátor, ne EKF
INAV počítá pozici a výšku komplementárním estimátorem s váhami (`inav_w_*`), ne pomocí EKF – je to jednodušší a pro F4 méně náročné, ale bez automatické důvěry/nedůvěry k senzorům (modul „INAV: GPS a RTH“). Odtud plynou požadavky: kompas a barometr jsou u multikoptéry povinné; kvalita GPS je důležitější než v ArduPilotu, kde EKF špatné rámce „přežije“.

### Proč nejde armovat: čteme OSD
Příčina blokování je vidět na třech místech: jako text v OSD (řádky typu „NAVIGATION SAFETY“, „AIRCRAFT IS NOT LEVEL“ – přesné znění závisí na verzi), na záložce Setup konfigurátoru a v CLI příkazem `status` (řádek s příznaky blokování armování). Typické příčiny: chybí GPS fix při navigačních režimech (`nav_extra_arming_safety`), akcelerometr nebo kompas nejsou zkalibrované, plyn není na minimu, náklon je větší než `small_angle`, přepínač armování je zapnutý při připojení napájení, je otevřené CLI nebo menu OSD, první bod mise je dál než `nav_wp_max_safe_distance`, porucha senzoru. Stejný princip jako v Betaflightu (modul „Bezpečnost“): příčina se odstraňuje, neobchází.

### Verze a kompatibilita
INAV 7/8 – doporučené jsou H7/F7, F4 je podporována s omezeními kvůli paměti (část funkcí je v targetech vyřazena); konfigurátor se musí s firmwarem přesně shodovat v hlavní verzi; `diff all` se mezi hlavními verzemi přenáší jen s kontrolou – parametry se přejmenovávají (`nav_use_midthr_for_althold` → `nav_mc_althold_throttle`). Aktualizace firmwaru = úplná záloha + porovnání `diff` + nová kalibrace senzorů.

{{diagram:firmware-choice|Místo INAV mezi firmwary: navigace podle GPS a letoun bez složitosti ArduPilotu/PX4.}}

## practice
### Krok 1. Platforma a mixer
1. Nahrajte do desky INAV se správným targetem.
2. Záložka Mixer: zvolte `platform_type` a preset (Quad X, Flying Wing…), použijte, uložte.
3. Bez vrtulí zkontrolujte výstupy: motory a serva reagují na správné kniply.

### Krok 2. Senzory
1. Kalibrace akcelerometru (6 poloh).
2. Kompas: kalibrace na otevřeném místě, kontrola orientace (`align_mag`).
3. GPS na UART, v Configuration protokol (obvykle UBLOX) a rychlost.

### Krok 3. Režimy
ARM – samostatný přepínač. ANGLE – základní. NAV ALTHOLD, NAV POSHOLD, NAV RTH – na třípolohovém přepínači podle rostoucí autonomie. Pro letoun: MANUAL povinně na samostatném přepínači.

### Krok 3b. Kontrola estimátoru na zemi (před prvním vzletem)
INAV letí tam, kam si myslí, že letí; ověřit to lze bez vrtulí:
1. **Kompas**: stroj na rovném místě přídí k severu (podle kompasu v telefonu) – kurz v OSD ±10°. Otočte o 90°, 180°, 270° – kurz to sleduje. Chyba v jednom směru znamená rušení nebo špatný `align_mag`.
2. **Domov a šipka**: po fixu je domov zapsán; odneste stroj o 20–30 m – vzdálenost k domovu v OSD odpovídá krokům, šipka domů ukazuje tam, odkud jste přišli. Šipka míří stranou – kurz je špatný, RTH odletí jinam.
3. **Výška**: zvedněte stroj o 2 m (v natažených rukou/na žebříku) – výška v OSD se změní o ~2 m a vrátí se. Drift metr za minutu v klidu – barometr je na přímém slunci nebo v proudu vzduchu.
4. **Satelity**: 3D fix, ≥ 10 satelitů, HDOP v OSD ≤ 1.5–2 před prvním navigačním letem.

| Kontrola | Norma | Pokud ne |
|---|---|---|
| Kurz podle světových stran | ±10° ve všech čtyřech | `align_mag`, nová kalibrace daleko od železa, přemístění kompasu |
| Vzdálenost k domovu při přenesení | ±2 m na 20 m | počkat na lepší fix, zkontrolovat anténu GPS |
| Výška při zvednutí o 2 m | 2 ± 0.5 m | zakrýt barometr molitanem, zkontrolovat kryt |

### Krok 4. První let
1. Na otevřené ploše počkejte na 3D fix (počet satelitů v OSD).
2. Armování, ANGLE, krátký vis / okruh.
3. Přepněte na ALTHOLD, potom na POSHOLD. Sledujte, jak drží.
4. RTH na krátkou vzdálenost a v malé výšce, s připraveností převzít řízení.

## diagnostics
- **Příznak:** nejde armovat, přestože je všechno nastavené
  - Možná příčina: chybí GPS fix při nastavených navigačních režimech, nebo kompas není zkalibrovaný.
  - Co udělat: podívat se na příčinu v OSD/konfigurátoru, počkat na fix, zkalibrovat kompas.
- **Příznak:** v POSHOLD „krouží“ nebo ujíždí
  - Možná příčina: kompas – kalibrace, orientace, rušení od silových vodičů.
  - Co udělat: znovu zkalibrovat, vynést kompas na stožárek, zkontrolovat `align_mag`.
- **Příznak:** RTH vede jinam
  - Možná příčina: domov je zapsán jinde (armování na jiném místě), nebo zasáhl safehome.
  - Co udělat: po armování zkontrolovat bod domova v OSD a seznam safehomes.
- **Příznak:** v MANUAL je letoun neřiditelný
  - Možná příčina: reverz serv nebo špatný preset mixeru.
  - Co udělat: zkontrolovat směry řídicích ploch na stole.
- **Příznak:** po aktualizaci INAV se část nastavení „ztratila“
  - Možná příčina: přejmenované parametry z diffu se nepoužily.
  - Co udělat: číst výstup CLI při načítání diffu, Settings.md nové verze, znovu zkalibrovat.

## references
- INAV Getting Started | https://github.com/iNavFlight/inav/blob/master/docs/Getting%20Started.md | primary | A
- INAV Navigation | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Controls (arming) | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A
- INAV Safehomes | https://github.com/iNavFlight/inav/blob/master/docs/Safehomes.md | primary | A

## checklist
- Rozumím, kde INAV stojí mezi Betaflightem a ArduPilotem
- `platform_type` a mixer odpovídají stroji
- Akcelerometr a kompas jsou zkalibrované, estimátor je ověřený na zemi (kurz, domov, výška)
- Umím najít příčinu blokování armování v OSD, konfigurátoru a `status`
- ARM je na samostatném přepínači, navigační režimy podle rostoucí autonomie
- První RTH je vyzkoušený blízko a nízko
