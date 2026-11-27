---
id: f-frame-mech
title: "Rám, mechanika a vibrace"
level: L2
readingTime: 25 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - rám
  - vibrace
  - vyvažování
related:
  - f-aero-props
  - bf-filters
next:
  - bf-pid-reg-in-bf
source: content/foundation/f-frame-mech.md
source_hash: e0540f818c0a
---

## summary
Polovina „problémů s laděním“ je mechanika: nevyvážená vrtule, uvolněný motor, rám, který zvoní na frekvenci, do níž se trefují harmonické motorů. Filtry a PID léčí příznaky; tento modul je o příčinách. Odkud se berou vibrace, co je rezonance rámu, jak vyvažovat vrtule a motory, jak upevnit řídicí jednotku a vést vodiče a jak výsledek změřit podle spektra, a ne podle pocitu.

## theory
### Zdroje vibrací
- **Nevyváženost vrtule** – hmotnost listů není stejná: síla ~ m·r·ω², roste tedy s druhou mocninou otáček. Hlavní zdroj na frekvenci otáčení (1. harmonická).
- **Nevyváženost motoru** – zvon motoru (rotor), magnety; stejná frekvence.
- **Aerodynamika listů** – pulzace tahu na frekvenci „otáčky × počet listů“ (2. a 3. harmonická).
- **Vůle a ohyb** – ložisko, nedotažený motor, poddajné rameno: přidávají širokopásmový šum a mohou „zvonit“ na vlastní frekvenci.
- **Propwash a turbulence** – nízkofrekvenční třesení 20–70 Hz; je to aerodynamika, ne mechanika.

### Rezonance rámu
Rám má vlastní frekvence (ramena, upevnění FC, distanční sloupky). Když harmonická motoru prochází vlastní frekvencí, amplituda vzroste několikanásobně. Ve spektru je to špička, která se nepohybuje spolu s otáčkami. Rezonanci neodfiltruje RPM filtr (ten sleduje motory); zachytí ji dynamic notch, nebo ji odstraní změna konstrukce: tužší rameno, jiná hmotnost, tlumič.

### Jak vibrace kazí let
- Gyroskop vidí vibrace jako úhlovou rychlost → PID „vyrovnává“ pohyb, který neexistuje → horké motory, rozmazaná odezva.
- Akcelerometr se dostává do clippingu (saturace) → EKF v ArduPilotu ztrácí odhad výšky a polohy (`VIBE`, `Clip`).
- Barometr „dýchá“ vlivem proudu vzduchu.

### Upevnění řídicí jednotky
Cílem je přenést pohyby rámu, ale ne vysokofrekvenční vibrace. Standard: měkké gumové silentbloky nebo sloupky s tlumičem, vodiče bez tahu (napnutý svazek je tuhá vazba, která tlumiče obchází). Příliš měkké upevnění znamená vlastní rezonance na nízkých frekvencích a zpoždění gyroskopu. U velkých strojů se používají tlumicí plošiny. U závodních 5" se vyskytuje i tuhé upevnění s laděním filtrů: silentbloky přidávají vlastní rezonanci 50–150 Hz. Pravidlo kurzu pro 5": začít se silentbloky ze sady stacku (5" má okno měkkého uchycení); na tuhé přejít, jen když spektrum ukazuje špičku uchycení — vodorovnou čáru pod harmonickými motorů nezávislou na plynu — a tvrdší silentbloky ji neodstraní.

### Čísla
Frekvence 1. harmonické motoru = RPM/60. Ve visu má 5" ~250–350 Hz, 7" ~120–200, 10" ~80–100, 15" ~50–70. Rezonance karbonových ramen leží obvykle na 100–400 Hz, upevnění FC na 50–150 Hz.

### Vlastní frekvence: hrubý odhad
Rameno jako vetknutý nosník: f₁ ≈ 0.56·√(E·I/(μ·L⁴)) (E – modul pružnosti, I – kvadratický moment průřezu, μ – hmotnost na metr, L – délka); pro inženýrský odhad je jednodušší měřit: cvrnknutí do ramene se záznamem akcelerometru/gyroskopu v logu (`LOG_DISARMED`/`blackbox_mode = ALWAYS`) dá tlumené kmity – frekvence špičky ve spektru je hledaná rezonance. Typické hodnoty: 5" karbonové rameno 4–5 mm – 300–500 Hz (nad harmonickými motorů ve visu, pod nimi při plném plynu); 7" 5 mm – 150–250 Hz (shoduje se s 1. až 2. harmonickou – nebezpečné pásmo); 10" a větší, trubková ramena 16–25 mm – 60–150 Hz. Vyztužením ramene (tlustší, kratší, trubka místo desky) frekvence roste jako √(tuhost/hmotnost); přidáním hmoty na konec (těžší motor) klesá.

### Tlumení FC: jak vybírat
Gumový silentblok je pružina s tlumičem: vlastní frekvence soustavy „deska na silentblocích“ je f₀ = (1/2π)·√(k/m). Je potřeba, aby f₀ byla 3–5krát nižší než nejnižší harmonická motorů, ale vyšší než pásmo řízení (≥ 50–80 Hz): pro 5" (motory 250 Hz a více) f₀ ≈ 50–83 Hz (250 / 5 … 250 / 3); pro X8 (motory 55 Hz) jsou tlumiče s f₀ 15–20 Hz už „měkké“ a způsobují zpoždění – tam se pracuje vyvažováním a notchem, ne měkkostí. Příznak příliš měkkého upevnění: nízkofrekvenční špička 20–40 Hz ve spektru a „vatový“ let. Vodiče a ploché kabely tlumiče obcházejí, pokud jsou napnuté.

{{diagram:chart-fc-damper-window|Окно мягкого крепления (f₀ в 3–5 раз ниже гармоники моторов, но не ниже 50–80 Гц) есть только при гармониках от 150–240 Гц: у 5" (250 Гц) это 50–83 Гц, у 7" из примера (125 Гц), 10" и X8 окна нет — там балансировка и notch.}}

### Řešený příklad: 7" se špičkou na 180 Hz
Spektrogram: vodorovná čára na 180 Hz nezávislá na plynu, 25 dB nad pozadím; harmonická motorů ve visu je 125 Hz, 2. harmonická 250 Hz (při přidávání plynu prochází přes 180 Hz – rezonance „zvoní“). Test cvrnknutím do ramene dá 182 Hz: je to rameno. Možnosti: rameno 6 mm místo 5 (f ↑ ~20 % → 215 Hz, vzdálí se od 1. harmonické, ale 2. jím stejně prochází) – to není řešení; dynamický notch na 180 Hz (pomáhá, ale přidává zpoždění) – dočasně; skutečné řešení je změnit bod upevnění motoru nebo zkrátit rameno (f ↑ 1.3–1.5krát), nebo rezonanci přijmout a nastavit statický notch `gyro_notch1_hz = 180`, `cutoff = 150`. Do pasportu stavby zapište: „rezonance ramene 180 Hz, notch“. Bez spektra by to celé vypadalo jako „je třeba snížit D“.

{{diagram:vibration-path|Cesta vibrací od motorů a vrtulí přes rám a upevnění ke gyroskopu a do regulační smyčky – a kde ji přerušit.}}

## practice
### Krok 1. Prohlídka
1. Vrtule: praskliny, odštípnutá místa, stejný model a stoupání na všech motorech.
2. Motory: vůle zvonu motoru nahoru a dolů, drhnutí ložiska při otáčení rukou, dotažení šroubů (ne delší, než je nutné – šroub ve vinutí = zkrat).
3. Rám: praskliny u otvorů, dotažení sloupků, vodiče se nikde nedotýkají vrtulí.

### Krok 2. Vyvažování
1. Vrtule na vyvažovačce: těžší list klesá; uberte materiál smirkovým papírem ze zadní strany u špičky, nebo přidejte kapku laku či kousek lepicí pásky na lehčí list.
2. Motory: roztočte motor bez vrtule na malý plyn a dotkněte se sloupku – vibrující motor je cítit. Přesnější je spektrum logu bez vrtulí.

### Krok 3. Měřit, ne odhadovat pocitem
1. Log visu před změnami, spektrum gyroskopu (Blackbox Explorer / PID Toolbox / vlastní Python).
2. Najděte špičky: pohybují se s plynem → motory; stojí na místě → rezonance.
3. Po vyvážení nebo montáži tlumiče stejný let, stejné spektrum, rozdíl v dB v pásmu špičky.

### Krok 4. Vodiče
Svazky nejsou napnuté, nedotýkají se rotujících částí, silové vodiče jsou zkroucené (proti rušení) a připevněné k rámu, ne k FC.

### Laboratorní úloha
Spektrum před vyvážením vrtulí a po něm na vlastním stroji; zapište frekvenci hlavní špičky a změnu amplitudy v dB.

## diagnostics
- **Příznak:** špička ve spektru se při změně plynu nepohybuje
  - Možná příčina: rezonance rámu nebo upevnění FC.
  - Co udělat: zvýšit tuhost ramene nebo sloupku, přidat tlumič, nastavit dynamic notch na tuto frekvenci.
- **Příznak:** špička na frekvenci motorů je obrovská
  - Možná příčina: nevyváženost vrtule nebo motoru.
  - Co udělat: vyvážit, vyměnit vrtuli, zkontrolovat zvon motoru.
- **Příznak:** `VIBE` a `Clip` v ArduPilotu rostou
  - Možná příčina: tuhé upevnění FC, nevyváženost velkých vrtulí.
  - Co udělat: odtlumit FC, vyvážit vrtule, vést vodiče bez tahu.
- **Příznak:** po montáži tlumičů je let „vatový“
  - Možná příčina: příliš měkké upevnění, nízkofrekvenční rezonance.
  - Co udělat: použít tužší silentbloky, snížit hmotnost na tlumiči.

## references
- Vibration Damping — ArduPilot Copter | https://ardupilot.org/copter/docs/common-vibration-damping.html | primary | A
- Measuring Vibration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-measuring-vibration.html | primary | A
- Blackbox Explorer — Betaflight (GitHub) | https://github.com/betaflight/blackbox-log-viewer | primary | A

## checklist
- Vrtule a motory jsou zkontrolovány prohlídkou a vyváženy
- Rozumím rozdílu mezi špičkou motorů a rezonancí ve spektru
- FC je na tlumičích, vodiče jsou bez tahu
- Spektrum před úpravou a po ní je změřeno, výsledek v dB zapsán
