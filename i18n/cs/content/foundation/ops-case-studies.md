---
id: ops-case-studies
title: "Rozbor skutečných nehod"
level: L1
readingTime: 40 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - nehody
  - vyšetřování
  - failsafe
  - případové studie
related:
  - ops-field
  - bf-failsafe
  - eng-method-101
  - f-frame-mech
next:
  - diag-troubleshooting
source: content/foundation/ops-case-studies.md
source_hash: a6b854a7320d
---

## summary
Inženýři se učí z cizích pádů, pokud jsou ty pády rozebrané. Modul bere tři veřejná vyšetřování státních komisí – Matternet M2 v Curychu (2019, platforma na ArduCopteru, porucha způsobená vibracemi a EKF), Alauda Airspeeder Mk II v Goodwoodu (2019, ztráta spojení a nefunkční nouzový vypínač) a Freefly Alta X v Henley (2022, vybití baterie) – a každé rozebírá podle stejného schématu: příznak → příčina → co je vidět v logu → důsledky → co změnit v konfiguraci a postupech. Každá případová studie končí řádkem do vašeho kontrolního seznamu.

## theory
### Schéma rozboru
Zprávy komisí (AAIB ve Velké Británii, STSB/SUST ve Švýcarsku, NTSB v USA) se píšou podle jedné logiky a tatáž logika je i vaším nástrojem:

1. **Příznak** – co viděl provozovatel.
2. **Sled událostí** – události v čase podle logů a telemetrie.
3. **Příčina** – technická (co selhalo) a systémová (proč to bylo možné).
4. **Co je vidět v datech** – konkrétní zprávy v logu, parametry, hodnoty.
5. **Důsledky** – energie nárazu, kdo byl poblíž, co se stalo s prostorem.
6. **Náprava** – konfigurace, konstrukce, postup.

Rozlišujte tři typy příčin: **porucha techniky** (díl se rozbil), **chyba nastavení** (parametr neodpovídal úloze), **chyba provozovatele** (postup nebyl dodržen). U skutečných nehod jsou téměř vždy přítomny všechny tři.

### Případová studie 1. Matternet M2, Curych, 9. května 2019 (STSB, závěrečná zpráva č. 2390, stroj SUI-9903)
**Kontext.** Doručovací kvadrokoptéra Swiss Post na upraveném ArduCopteru (na základě 3.5.0-rc5), tři IMU, systém ukončení letu (FTS) s padákem. Zpáteční let bez nákladu.

**Sled událostí.** Vzlet v 10:37:35. Po ~50 s vzrostly vibrace na všech třech IMU (zrychlení místy > 30 m/s²) a IMU3 začala dávat prudké výchylky, zatímco IMU1 a IMU2 ukazovaly shodné hodnoty; stroj se začal rozkývávat v klopení (pitch). V 10:38:46 je v logu `EKFCHECK_BAD_VARIANCE`; obsluha chyb aktivovala FTS ve výšce ~185 m nad místem vzletu (~100 m nad zemí): všechny čtyři motory se zastavily a padák byl vystřelen. Lano padáku se přetrhlo u úchytu na stroji; následoval pád bez brzdění a zničení stroje v 10:38:48. Místo dopadu – les, ~50 m od skupiny dětí s vychovateli, kteří neslyšeli výstražný signál.

**Příčiny.** Technická: narůstající vibrace nezjištěného původu (pravděpodobně rezonance vyvolaná vnějším vlivem – poškozením vrtule nebo srážkou s ptákem) v kombinaci s nedostatečnou odolností firmwaru vůči takové události. Systémová: upravený ArduCopter uměl provozovat jen dvě instance EKF, `EK2_IMU_MASK = 5` (IMU1 a IMU3, bez IMU2) – vadný senzor nebylo možné izolovat; FTS reagoval okamžitě neřízeným klesáním, místo aby se pokusil o řízené ukončení letu. Lano padáku poškodila ostrá hrana hliníkového úchytu ještě před otevřením padáku a lano nevydrželo trhnutí.

**Co je vidět v logu.** `VIBE` roste na všech IMU, ale data jedné IMU se prudce rozcházejí s oběma ostatními (příznak lokálního zdroje nebo senzoru, ne rámu jako celku); inovace EKF rostou → `EKFCHECK_BAD_VARIANCE`; přepnutí na FTS.

**Důsledky.** Energie nárazu ≈ 118 J bez nákladu (víc než 80 J, které se berou jako práh vážného zranění). Pozastavení doručovacího programu. Sedm bezpečnostních doporučení.

**Nápravy (skutečné).** `EK2_IMU_MASK = 3` (dvě funkční IMU + možnost izolace), kontrola obou instancí EKF při armování, druhé jisticí lano a přepracovaný úchyt, siréna 100 dB, nástroj pro analýzu logů, padák vyhovující ASTM F3322, snížení maximální rychlosti z 20 na 16 m/s. Doporučení komise č. 591: usilovat o redundantní koncepci pohonu (v analýze se uvádí, že uspořádání se 6 a více motory mají výrazně menší pravděpodobnost selhání).

**Řádek do vašeho kontrolního seznamu:** „Vibrace každé IMU jsou v logu zkontrolované po každé změně mechaniky; chování při EKF failsafe je známé a ověřené v SITL“.

### Případová studie 2. Alauda Airspeeder Mk II, Goodwood, 4. července 2019 (AAIB, zpráva 03/2021)
**Kontext.** Předváděcí multikoptéra o hmotnosti 95 kg, vlastní řídicí jednotka se dvěma IMU, bez GNSS a bez RTH, řízení vysílačkou FrSky Taranis X9D + modul R9M na 915 MHz (10 mW, režim FCC – pásmo, které ve Velké Británii není povoleno pro použití ve vzduchu). Samostatný nouzový vypínač na 433 MHz LoRa s vlastní baterií, který přes relé přerušuje napájení řídicí jednotky.

**Sled událostí.** ~65 s po vzletu se stroj náhle a bez povelu srovnal do vodorovné polohy a poté došlo ke ztrátě spojení. Řídicí jednotka při ztrátě spojení **zmrazila poslední povel plynu a držela vodorovnou polohu** – stroj dál stoupal rychlostí ~2000 ft/min a otáčel se přitom ~40°/s po dobu 4 min 12 s až do ~7900 ft, kde vlétl do řízeného vzdušného prostoru vyčkávacího obrazce letiště Gatwick. Pozorovatel na povel „kill“ aktivoval vypínač – bez účinku. Po vybití baterie se stroj převrátil a spadl rychlostí ~4500 ft/min do pole 40 m od obytných domů, 700 m za hranicí povoleného prostoru. Energie nárazu ≈ 24 800 J. Nikdo nebyl zraněn.

**Příčiny.** Přesná příčina ztráty spojení nebyla zjištěna: **palubní záznam neexistoval**, desky byly zničeny. Systémové příčiny, které komise zjistila: failsafe při ztrátě spojení byl navržen jako „držet plyn“, a ne „klesat/přistát“; nouzový vypínač neměl zpětnou vazbu (ztrátu jeho kanálu nebylo jak zjistit), relé bylo v klidu sepnuté (porucha vypínače se neprojeví až do chvíle, kdy je ho potřeba), byl postaven na nepájivém poli s propojkami a aktivoval se hlasovým povelem místo automaticky; v troskách byly relé i napájecí vodič odpojené od desky. Stroj nebyl navržen ani zkoušen podle žádných norem: montáž na suchý zip a stahovací pásky, ethernetové kabely jako signálové vedení k ESC, pájené spoje s propojkami, baterie 42–58 V bez jakékoli ochrany; žádné vibrační ani RF zkoušky. Rychlost za letu až 25 m/s při deklarovaném omezení 11 m/s.

**Co je vidět v datech.** Nic – a to je hlavní poučení: bez logu vyšetřování končí slovy „nebylo zjištěno“.

**Nápravy.** 15 doporučení regulačnímu úřadu a provozovateli. Pro vás: failsafe má stroj převést do bezpečného stavu (klesání/přistání/RTH), ne „držet“; nouzový obvod má mít zpětnou vazbu a autodiagnostiku; jednotlivá místa poruchy (single point of failure) mají být spočítaná; palubní záznam vždy.

**Řádek do vašeho kontrolního seznamu:** „Failsafe je před prvním letem každé nové konfigurace ověřen vypnutím vysílačky na zemi bez vrtulí; černá skříňka je zapnutá“.

### Případová studie 3. Freefly Alta X, Henley-on-Thames, 29. června 2022 (AAIB, bulletin 01/2023)
**Kontext.** Komerční natáčení regaty, multikoptéra 28 kg (MTOW 34.9) se dvěma 12S LiPo, plné nabití 50.4 V. 21. let toho dne, 6. let na této sadě baterií, ačkoli záměrem bylo měnit je po každých třech letech.

**Sled událostí.** Ve výšce ~50 m se spustilo varování nízkého napětí. Při návratu napětí dál klesalo a řízený let byl ztracen; stroj téměř volným pádem (≈ 30 m/s) narazil do lodi na řece. Nikdo nebyl zraněn; energie nárazu ≈ 13 700 J (odhad AAIB; ½·28·30² ≈ 12 600 J, hodnotě 13 700 J odpovídá ~31 m/s – volný pád z 50 m) – komise uvedla, že zásah člověka by byl smrtelný. **Logy nejsou** – stroj nebyl vyzvednut.

**Příčiny.** Chyba nastavení: pilot snížil práh varování ze 44 V (výchozí hodnota výrobce, „přistát co nejdříve“) na 42 V – rezerva do kritického napětí se zmenšila o 2 V. Chyba provozovatele: napětí před vzletem s největší pravděpodobností nikdo nekontroloval (výrobce požaduje > 48 V, pilot „vzlétal i pod 48“); baterie nebyly vyměněny podle plánu. Porucha techniky nebyla zjištěna.

**Co by bylo vidět v logu.** Napětí pod zátěží pod prahem dlouho před varováním; varování, které se spustilo při napětí, jež ponechává sekundy, ne minuty.

**Nápravy.** Prahy ne níže, než doporučuje výrobce, a pro vlastní baterie podle změřené vybíjecí křivky; předletová kontrola napětí je bod kontrolního seznamu, který nelze přeskočit; evidence letů na každé sadě baterií.

**Řádek do vašeho kontrolního seznamu:** „Napětí baterie je zapsané před každým vzletem; prahy varování a failsafe jsou podložené vybíjecí křivkou a nejsou snížené kvůli minutě navíc“.

### Společné zákonitosti tří případových studií
- Ve všech třech není problém ve „špatném dílu“, ale v **návrhu chování při poruše**: co stroj dělá, když se něco pokazí.
- Ve dvou ze tří **chyběla data**; vyšetřování skončilo u „nebylo zjištěno“. Log neslouží k ladění, slouží k odpovědi na otázku „proč“.
- Ani v jednom případě nebyl nikdo zraněn – **a je to štěstí**, ne výsledek: 50 m od dětí, 40 m od domů, loď místo člověka.
- Energie nárazu 118 J, 13 700 J a 24 800 J proti prahu vážného zranění ~80 J: i lehký stroj je nebezpečný, těžký je smrtelný.

{{diagram:chart-impact-energy|Энергия удара даже лёгкого Matternet в 1.5 раза выше порога серьёзной травмы, у тяжёлых аппаратов — в 171 и 310 раз (шкала логарифмическая).}}

{{diagram:incident-analysis|Schéma rozboru nehody podle logiky zpráv komisí – a poslední krok: co změnit ve vlastním procesu.}}

## practice
### Krok 1. Přečíst primární zdroj
Otevřete jednu ze tří zpráv (odkazy níže) a přečtěte si oddíl se sledem událostí a závěry. Porovnejte ho s rozborem výše: co ve zprávě je a co tady chybí.

### Krok 2. Rozebrat další dva incidenty
Vezměte dva veřejné případy (AAIB publikuje desítky zpráv o bezpilotních letadlech; bulletiny „record-only“ jsou krátké) a vyplňte tabulku podle schématu o šesti bodech, s odkazy.

### Krok 3. Vlastní incident
Vlastní pád nebo ztráta spojení (případně cvičný incident: log z fóra) – stejné schéma, podle logu. Pokud log není, je právě tohle první závěr.

### Krok 4. Změny
Ke každému z pěti rozebraných případů jeden řádek do vlastního předletového kontrolního seznamu nebo jeden parametr v konfiguraci se zdůvodněním. Zapište je do CHANGELOG inženýrské složky.

### Laboratorní úloha
Tabulka rozboru tří veřejných incidentů s odkazy na zprávy; ke každému změna ve vlastním kontrolním seznamu nebo konfiguraci; rozbor jednoho vlastního incidentu podle logu.

### Schéma rozboru a příklad řádku
Šest bodů ke každému případu: co se stalo → sled událostí v čase → bezprostřední příčina → kořenová příčina (proces, ne člověk) → co zafungovalo a co ne → změna u vás. Příklad řádku výsledku: „Zpráva X (odkaz): ztráta GNSS u kovové konstrukce → kořen: let s držením pozice bez kontroly kvality navigace → u mě: v kontrolním seznamu bod "HDOP a počet satelitů na letové ploše", v konfiguraci varování na kvalitu GNSS“.

### Co má být výsledkem
- Tabulka tří veřejných případů: každý s odkazem na primární zprávu, ne na převyprávění.
- Každý závěr je převeden na konkrétní opatření – řádek kontrolního seznamu, parametr nebo pravidlo letové plochy, ne na „dávat větší pozor“.
- Vlastní incident je rozebrán podle logu stejným schématem. Pokud log není, prvním opatřením je zapnout logování. To není vtip, ale nejčastější skutečný závěr.
- Zápisy v CHANGELOG inženýrské složky: datum, změna, odkaz na případ, který k ní vedl.

Laboratorní úloha je splněna, když jsou tři veřejné incidenty rozebrané podle schématu s odkazy na zdroje, ke každému existuje konkrétní změna ve vlastním kontrolním seznamu nebo konfiguraci a jeden vlastní (nebo cvičný) incident je rozebrán podle logu.

## diagnostics
- **Příznak:** rozbor vlastního pádu končí slovy „nevím proč“
  - Možná příčina: chyběl palubní záznam nebo telemetrie.
  - V logu/na přístroji: není na co se dívat.
  - Důsledky: příčina se zopakuje.
  - Co udělat: zapněte Blackbox/DataFlash při všech letech a na GCS ukládejte tlog.
- **Příznak:** failsafe je „nastavený“, ale nikdy se nezkoušel
  - Možná příčina: v postupu chybí test na zemi.
  - V logu/na přístroji: událost failsafe v logu chybí za celou historii stroje.
  - Důsledky: jako u Airspeederu – stroj dělá něco jiného, než si myslíte.
  - Co udělat: test bez vrtulí při každé nové konfiguraci, výsledek zapište do tabulky testů.
- **Příznak:** prahy baterie jsou snížené, „aby se dalo létat déle“
  - Možná příčina: rezerva byla obětována době letu.
  - V logu/na přístroji: napětí pod zátěží je u kritické úrovně ještě před spuštěním varování.
  - Důsledky: jako u Alta X – pád volným pádem.
  - Co udělat: nastavte prahy podle vybíjecí křivky vlastních baterií, ne níže, než doporučuje výrobce.
- **Příznak:** vibrace vzrostly jen na jedné IMU
  - Možná příčina: lokální zdroj (úchyt, senzor) nebo poškození.
  - V logu/na přístroji: `VIBE` jednotlivých IMU se rozcházejí, inovace EKF rostou.
  - Důsledky: EKF failsafe, u Matternetu FTS.
  - Co udělat: přistaňte a prohlédněte vrtule a úchyty; masku IMU nastavte tak, aby bylo možné vadný senzor izolovat.

## references
- STSB (SUST) — Final report SUI-9903, Matternet M2 V9, Zürich, 9 May 2019 (PDF) | https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf | primary | A
- AAIB — Investigation to Alauda Airspeeder Mk II (UAS), Goodwood, 4 July 2019 | https://www.gov.uk/aaib-reports/aaib-investigation-to-alauda-airspeeder-mk-ii-uas-registration-n-slash-a-040719 | primary | A
- AAIB — Investigation to Freefly Systems Inc. Alta X (UAS), Henley-on-Thames, 29 June 2022 | https://www.gov.uk/aaib-reports/aaib-investigation-to-freefly-systems-inc-alta-x-uas-registration-n-slash-a | primary | A
- AAIB — all UAS reports (search) | https://www.gov.uk/aaib-reports?keywords=UAS | primary | A

## checklist
- Znám schéma rozboru o šesti bodech a tři typy příčin
- Mám přečtený alespoň jeden primární zdroj celý
- Tři veřejné incidenty jsou rozebrané s odkazy
- Vlastní incident je rozebrán podle logu (nebo je zapsán závěr, že log chybí)
- Pět změn je zanesených do kontrolního seznamu/konfigurace a zapsaných v CHANGELOG
