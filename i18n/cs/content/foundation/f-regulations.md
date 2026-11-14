---
id: f-regulations
title: "Pravidla, zóny a odpovědnost provozovatele"
level: L1
readingTime: 20 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - pravidla
  - bezpečnost
  - odpovědnost
related:
  - f-safety
  - ops-field
next:
  - tools-overview
source: content/foundation/f-regulations.md
source_hash: 88b3f9de7c73
---

## summary
Inženýr UAV neodpovídá jen za to, že stroj létá, ale také za to, kde a jak létá. Pravidla se v jednotlivých zemích liší a každý rok se mění, proto je modul nepřevypráví, ale učí, jak najít ta aktuální, jak pochopit jejich společnou logiku (kategorie rizika, zóny, výšky, registrace, pojištění) a jak vést dokumentaci provozovatele. Není to právní poradenství: zdrojem pravdy je letecký úřad vaší země.

## theory
### Obecná logika regulace
Většina zemí staví pravidla kolem **rizika**: hmotnost stroje, blízkost lidí a infrastruktury, výška, viditelnost. Typické prvky:

- **Registrace** provozovatele a/nebo stroje nad určitou hmotnost.
- **Kategorie provozu**: od „otevřené“ (malé stroje, ve vizuálním dohledu, daleko od lidí) po „specifickou“ a „certifikovanou“ (povolení, posouzení rizik).
- **Omezení výšky** nad zemí (v otevřené kategorii často kolem 120 m / 400 stop).
- **Zóny**: letiště, města, objekty infrastruktury, hranice, vojenské objekty – zákaz, nebo povolení.
- **Vizuální dohled** (VLOS) jako základní požadavek; lety mimo vizuální dohled (BVLOS) vyžadují zvláštní povolení.
- **Noční lety, lety nad lidmi** – zvláštní podmínky.
- **Pojištění odpovědnosti** – povinné, nebo důrazně doporučené.

### Co to znamená pro inženýra
- Zkušební lety jsou také lety: platí pro ně stejná pravidla.
- Autonomní mise a BVLOS jsou téměř vždy samostatná kategorie. Plánujte je legálně, nebo v simulátoru.
- Frekvence RC a videa se regulují zvlášť: výkon a pásma VTX i povolené kanály ELRS/900 MHz závisejí na zemi.
- Odpovědnost nese provozovatel a vlastník. Deník letů je vaše ochrana při incidentu.

### Dokumentace provozovatele
Minimum, které vedou profesionálové:

- **Deník provozovatele**: datum, místo, stroj, doba letu, účel, incidenty.
- **Deník stroje**: konfigurace, opravy, výměny, provozní hodiny motorů a baterií.
- **Pasport stavby** (z capstone projektu okruhu „Základy“): hmotnost, pohonná jednotka, frekvence.
- **Posouzení rizik letové plochy**: lidé, překážky, zóny, počasí, plán pro případ poruchy.

### Jak fungují dva „vzorové“ systémy (abyste rozuměli tomu svému)
- **EASA (EU)**: tři kategorie – **Open** (do 25 kg, VLOS, ≤ 120 m, podkategorie A1/A2/A3 podle blízkosti lidí a třídy stroje C0–C4 (třídy C5/C6 jsou určeny pro standardní scénáře STS v kategorii Specific); registrace provozovatele od 250 g nebo při vybavení kamerou; online zkouška A1/A3, doplňková zkouška pro A2), **Specific** (posouzení rizik SORA, povolení národního úřadu nebo standardní scénáře STS; sem spadá BVLOS, těžké stroje, lety nad lidmi), **Certified** (jako pilotované letectví). Stroje vlastní stavby smějí v kategorii Open jen do A1 (< 250 g) nebo A3 (daleko od lidí), jinak Specific.
- **FAA (USA)**: **Part 107** pro komerční provoz (zkouška, osvědčení, ≤ 400 stop, VLOS, Remote ID), **Recreational** (test TRUST, registrace od 250 g, 400 stop, Remote ID), povolení k letům v řízeném vzdušném prostoru přes LAANC; BVLOS – waiver.
Oba systémy mají společné: registraci a identifikaci (Remote ID / třída C), kategorii podle rizika, výšku ~120 m/400 stop, VLOS, zóny, odpovědnost provozovatele. Svou zemi si ověřte podle stejné struktury: „jaká kategorie, jaká hranice registrace, jaká výška, jaká identifikace, jak je to s BVLOS“.

### Rádiové frekvence: co bývá omezeno
Pásma ISM (2.4 GHz, 5.8 GHz, 868/915 MHz) jsou otevřená pro použití bez licence s omezením výkonu (v EU 2.4 GHz – 100 mW EIRP, 5.8 GHz video – 25 mW EIRP podle obecných pravidel; 868 MHz – 25 mW s omezením duty cycle; v USA je to jinak, pásmo 900 MHz je širší) – výkon 1 W u VTX nebo ELRS je ve většině zemí formálně mimo obecné normy a vyžaduje radioamatérskou licenci nebo zvláštní povolení. Moduly kurzu o rozpočtu spoje počítají fyziku; zákonnost výkonu je samostatná otázka, která se řeší před letem.

### Řešený příklad: zkušební lety 7" vlastní stavby
Stroj 1.4 kg, vlastní stavby (bez třídy C), kamera. EU: Open A3 – ≥ 150 m od obytných, průmyslových a rekreačních oblastí, daleko od lidí, ≤ 120 m, registrace provozovatele, zkouška A1/A3, pojištění podle požadavků země; jakýkoli test BVLOS nebo test s autonomní misí mimo VLOS – Specific. USA: recreational (TRUST, registrace, modul Remote ID) nebo Part 107, 400 stop, v případě potřeby LAANC. Závěr do inženýrské složky: letová plocha, kategorie, dokumenty a co se nesmí – vše zapsáno před prvním letem; autonomní testy probíhají v SITL a na zkušebním stavu s upoutaným strojem, dokud není povolení.

{{diagram:airspace-check|Logika kontroly před letem: stav zóny na oficiální mapě, pravidla kategorie a povolené rádiové frekvence (konkrétní hodnoty podle právních předpisů vlastní země).}}

## practice
### Krok 1. Najít pravidla své země
1. Úřad pro civilní letectví vaší země – oficiální web, sekce o bezpilotních letadlech.
2. Zapište si s odkazy: registrace (od jaké hmotnosti), kategorie, výška, zóny, VLOS/BVLOS, pojištění.
3. Zvlášť si zapište pravidla pro rádiové frekvence (výkon VTX, pásma).
4. Datum kontroly uveďte v poznámce: za rok zkontrolujte znovu.

### Krok 2. Mapa zón kolem vlastní letové plochy
Najděte oficiální mapu zón (řada úřadů má službu nebo aplikaci). Vyznačte nejbližší letiště a zakázané zóny a určete, kde lze létat bez povolení.

### Krok 3. Založit deníky
Dva soubory v repozitáři dronů: `operator-log.md` a `<dron>/log.md`. První záznam je dnešní.

### Krok 4. Posouzení rizik letové plochy
Kontrolní seznam na jednu stránku: lidé a zvířata, překážky a dráty, zóna a výška, počasí (vítr, srážky, teplota baterie), plán při ztrátě spojení (kam stroj spadne při DROP, kam poletí při RTH), kontakt na záchranné složky.

### Šablona výpisků z pravidel
| Bod | Co říká pravidlo | Odkaz (dokument, bod) | Datum kontroly |
|---|---|---|---|
| Registrace | od jaké hmotnosti, jak a kde | … | … |
| Kategorie a podkategorie | pro váš stroj a úkol | … | … |
| Výška | maximální nad zemí | … | … |
| Zóny | kde se nesmí nebo je potřeba povolení | … | … |
| Viditelnost | VLOS, je-li potřeba pozorovatel | … | … |
| Pojištění, průkaz | je-li potřeba | … | … |
| Rádio | výkon a pásma VTX a RC | … | … |
| Remote ID | je-li potřeba a v jaké podobě | … | … |

Výpisky obsahují odkazy na oficiální dokumenty úřadu, ne na převyprávění v chatech: pravidla se mění a převyprávění zaostává.

### Co zapsat
- **Deník provozovatele,** první záznam: `2026-11-09 – pravidla zkontrolována (odkazy v regs.md), letová plocha „pole u řeky“: mimo zóny, nejbližší letiště 18 km, výška do 120 m`. Konkrétní čísla převezměte z pravidel a mapy své země.
- **Deník dronu:** každý let – datum, letová plocha, doba letu, baterie, poznámky.
- **Posouzení rizik letové plochy** – jeden list vázaný na konkrétní místo. Nová plocha znamená nový list.

Laboratorní úloha je splněna, když jsou aktuální pravidla vaší země vypsána podle šablony s odkazy na oficiální zdroje a s datem kontroly, zóny kolem vlastní letové plochy jsou ověřeny na oficiální mapě a deník provozovatele i deník dronu jsou založeny s prvními záznamy.

## diagnostics
- **Příznak:** není jasné, zda je nutná registrace
  - Možná příčina: hmotnostní hranice se v jednotlivých zemích liší a mění se.
  - Co udělat: řiďte se jen oficiálním zdrojem a zapište si datum kontroly.
- **Příznak:** letová plocha je „snad volná“, ale poblíž je letiště
  - Možná příčina: zóny letišť často sahají kilometry daleko.
  - Co udělat: zkontrolujte oficiální mapu zón; při pochybnostech nelétejte.
- **Příznak:** incident s třetími osobami
  - Možná příčina: jakákoli.
  - Co udělat: poskytněte pomoc postiženým, vše zdokumentujte, podejte oznámení podle pravidel země a zapište událost do deníku.

## references
- ICAO — Unmanned Aircraft Systems (UAS) | https://www.icao.int/UA | primary | A
- EASA — Civil drones (příklad struktury pravidel: otevřená/specifická/certifikovaná kategorie) | https://www.easa.europa.eu/en/domains/civil-drones | primary | A
- FAA — Unmanned Aircraft Systems (příklad: Part 107, Recreational Flyers) | https://www.faa.gov/uas | primary | A

## checklist
- Pravidla vlastní země jsou nalezena na oficiálním webu a vypsána s datem
- Zóny kolem letové plochy jsou ověřeny na oficiální mapě
- Deník provozovatele a deník stroje jsou založeny
- Posouzení rizik letové plochy je sepsáno
- Znám omezení frekvencí a výkonu VTX/RC ve své zemi
