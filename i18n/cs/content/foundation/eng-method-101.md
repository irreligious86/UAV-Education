---
id: eng-method-101
title: "Inženýrská metoda 101: požadavky, architektura, testy, dokumentace"
level: L1
readingTime: 30 min
firmware: libovolný firmware
status: published
added: 2026-11-08
tags:
  - inženýrská metoda
  - požadavky
  - testy
  - dokumentace
related:
  - f-components-choice
  - tools-overview
  - f-safety
next:
  - tools-overview
source: content/foundation/eng-method-101.md
source_hash: ae91b13ffb1e
---

## summary
Rozdíl mezi stavitelem a inženýrem není v páječce, ale v metodě: inženýr ví, *co* má stroj dělat (požadavky), *jak* je uspořádán (architektura), *čím* je doloženo, že to opravdu dělá (testy), a zanechává stopu, podle které může v práci pokračovat někdo jiný (dokumentace). Tento modul zavádí metodu hned na začátku kurzu – na příkladu první stavby – a určuje podobu „inženýrské složky“, která je od této chvíle povinná v každém závěrečném projektu.

## theory
### K čemu je to začátečníkovi
Bez požadavků každé nastavení „zabralo“ nebo „nezabralo“ jen podle pocitu. Bez architektury je hledání závady zkoušení naslepo. Bez testů nevíte, co včerejší změna rozbila. Bez dokumentace je vám za měsíc vlastní práce cizí. Metoda stojí hodinu na začátku a později ušetří dny; ve velkých projektech (viz rozbor nehod) stojí její absence stroje i pověst.

### 1. Požadavky
Požadavek je tvrzení o tom, co má stroj dělat, které lze **ověřit**. Formát: ID, text, kritérium, způsob ověření.

| ID | Požadavek | Kritérium | Ověření |
|---|---|---|---|
| R-01 | Visí s užitečným zatížením 30 g nejméně 15 min | ≥ 15:00 do 3.5 V/článek | Let se stopkami, log napětí |
| R-02 | T/W při vzletové hmotnosti ≥ 2.5 | výpočet a plyn ve visu ≤ 40 % | Tabulka tahu + log |
| R-03 | Při ztrátě spojení přistane na místě po 1.5 s | DROP po 1.5 s | Test na zemi bez vrtulí + log |
| R-04 | Video a RC se neztrácejí do 1 km ve výšce 50 m | LQ > 70 %, video bez výpadků | Test v terénu se záznamem |
| R-05 | Vzletová hmotnost ≤ 900 g | váha | Vážení |

Pravidla: měřitelnost („rychlý“ není požadavek, „zrychlení na 15 m/s za 3 s“ požadavek je); jeden požadavek – jedno ověření; požadavky na bezpečnost a soulad s předpisy tvoří samostatnou skupinu (S-xx); u každého čísla je uveden zdroj.

### 2. Architektura
Schéma bloků a vazeb: co je s čím spojeno, jakým rozhraním a odkud se napájí. U dronu jsou to tři vrstvy na jednom listu:
- **Napájení**: baterie → ESC; baterie → BEC 5 V → FC, RX, GPS; BEC 9 V → VTX. U šipek jsou proudy.
- **Data**: RX —CRSF→ FC (UART1); GPS —UBX→ FC (UART2); FC —DShot→ ESC; FC —MSP/OSD→ VTX (UART3); FC —Blackbox→ flash paměť.
- **Mechanika**: co je kde umístěno, hmotnosti, těžiště.
Architektura odpovídá na otázku „proč právě takhle“ jednou větou ke každému rozhodnutí: „GPS je na stožárku – kompas dál od silových vodičů (viz rušení)“.

{{diagram:eng-architecture-layers|Архитектура примера на одном листе: питание и данные — разными линиями, у каждой стрелки данных подписаны интерфейс и порт; токи на стрелках питания подписываешь своими числами.}}

### 3. Testy
Každý požadavek → test s očekávaným výsledkem, skutečným výsledkem a datem. Testy jsou:
- **Pozemní** (bez vrtulí): porty, směr otáčení motorů, failsafe, předletové kontroly firmwaru.
- **Simulační** (SITL pro INAV/ArduPilot/PX4): mise, failsafe, geofence.
- **Na měřicí stolici**: tah, proud, spektrum vibrací.
- **Letové**: vis, dosah, doba letu.
Pravidlo regrese: po každé změně konfigurace se zopakují pozemní testy a ten letový test, kterého se změna týká. Tabulka testů je živý dokument.

### 4. Dokumentace a deník změn
Minimální inženýrská složka (repozitář git):

```
my-drone/
  README.md          — co to je, k čemu slouží, aktuální stav, jak to spustit
  requirements.md    — tabulka požadavků
  architecture.md    — schémata napájení/dat/mechaniky (obrázky + text)
  tests.md           — tabulka testů s výsledky
  config/            — diff all / parametry s datem a verzí firmwaru
  logs/              — klíčové logy s poznámkou, co v nich je
  CHANGELOG.md       — datum, co se změnilo, proč, čím je to ověřeno
```

Deník změn má jeden řádek na každou změnu: `2026-11-08 — D-term 25→30 na roll; cíl: odstranit bounce-back; ověření: log 0042, overshoot 12%→6%`. Právě tohle je „ladění podle dat“.

### Trasovatelnost
Nit požadavek → architektonické rozhodnutí → test → výsledek. Pokud chybí, projekt nelze odevzdat: není jasné, co je doloženo. V hodnoticích kritériích závěrečných projektů kurzu je to samostatný řádek.

### Jak to vypadá v praxi u profesionálů
Zprávy z vyšetřování nehod (modul „Rozbor skutečných nehod“) uvádějí stále dokola tytéž příčiny: chyběly požadavky pro případ poruchy, chyběly testy failsafe, konfigurace se měnila bez záznamu, dokumentace neodpovídala stroji. Metoda není byrokracie, ale to, co odlišuje inženýrský stroj od hromady dílů.

{{diagram:traceability|Trasovatelnost: každý požadavek má test a každý test má požadavek; změna ukáže, které testy je třeba zopakovat.}}

{{diagram:eng-method-loop|Цикл метода замкнут: решение «не доказано» возвращает к новому эксперименту, а не к ощущениям; каждый шаг оставляет файл в инженерной папке.}}

{{diagram:eng-error-budget|Бюджет ошибок R-02: весы и калибровка стенда почти ничего не весят, больше половины дисперсии — разброс экземпляров (измерен один мотор из четырёх); нижнюю границу T/W выше 2.5 поднимает только обмер всех четырёх моторов вместе с замером при 14.0 В.}}

## practice
### Krok 1. Repozitář
Vytvořte repozitář `my-drone` se soubory podle šablony výše. Do README patří tři odstavce: co je to za stroj, k čemu slouží a jaký je aktuální stav.

### Krok 2. Požadavky
Tabulka s ≥ 8 požadavky na vaši první stavbu: 4–5 funkčních (doba letu, T/W, dosah, hmotnost), 3 bezpečnostní (failsafe, zóny, předletový kontrolní seznam), 1–2 provozní (opravitelnost, rozpočet). Každý s kritériem a způsobem ověření.

### Krok 3. Architektura
Jedno schéma napájení a dat (nakreslené rukou a vyfocené úplně stačí) s popsanými rozhraními a proudy.

### Krok 4. Testy
Tabulka testů ke každému požadavku. Proveďte ty, které už provést lze (vážení, výpočet T/W, pozemní kontroly); ostatní označte poznámkou „naplánován“.

### Krok 5. První commit a zápis do deníku
Commit se zprávou, co bylo uděláno; první řádek CHANGELOG.

### Příklady požadavků, které lze ověřit
| ID | Požadavek | Metoda | Test |
|---|---|---|---|
| REQ-01 | Vis nejméně 12 minut s baterií 6S 4000 mAh | test | T-01: vis do 3.5 V na článek, stopky |
| REQ-02 | T/W nejméně 3 s veškerým letovým vybavením | výpočet + vážení | T-02 |
| REQ-03 | Vzletová hmotnost nejvýše 900 g | vážení | T-03 |
| REQ-06 | Při ztrátě RC delší než 1 s – přistání ve failsafe nebo RTH | test | T-06: vypnutí vysílačky na stole bez vrtulí, potom v terénu |
| REQ-07 | Lety pouze mimo zakázané zóny | kontrola mapy | T-07: mapa plochy ve složce |

„Stroj musí být spolehlivý“ není požadavek: nelze ho ověřit. „Ani jedna porucha během 20 letů po sobě“ už ověřit lze.

### Co má být výsledkem
- V repozitáři jsou `README.md`, `requirements.md`, `architecture.jpg` (fotka schématu stačí), `tests.md`, `CHANGELOG.md`.
- Každý řádek tabulky testů odkazuje na požadavek a každý požadavek má alespoň jeden test. Provedené testy mají datum a výsledek, naplánované mají poznámku.
- První řádek CHANGELOG: `2026-11-09 — inženýrská složka vytvořena, T/W spočítán (3.4), hmotnost 860 g`. Čísla budou vaše.

Laboratorní úloha je splněna, když jsou v gitu požadavky s ID (8 a více, každý měřitelný), schéma architektury s popsanými rozhraními a proudy, tabulka „požadavek → test → výsledek“ a založené README a deník změn.

```python
"""eng-method-101: error budget for requirement R-02 (T/W >= 2.5) with GUM-style propagation + Monte Carlo.

Measured: one of the four installed motor+prop units on the stand at 16.0 V (4.0 V/cell under load), 20 C: T1 = 750 g.
Its own deviation from the batch mean enters all four motors at once: u = 3% * sqrt(12)/4 = 2.60%.
Requirement condition (rewritten R-02): end of flight 3.5 V/cell = 14.0 V, air 35 C, take-off mass.
Model: TW = 4 * T1 * (V/V0)^a * (T0/T) / m
"""
import math
import numpy as np

T1, V0, V, a, t0, t, m = 750.0, 16.0, 14.0, 1.8, 20.0, 35.0, 860.0
rho_ratio = (273.15 + t0) / (273.15 + t)           # same pressure: rho ~ 1/T_abs
volt = (V / V0) ** a
TW = 4 * T1 * volt * rho_ratio / m
print(f"corrections: voltage (14/16)^1.8 = {volt:.4f}, air density 293.15/308.15 = {rho_ratio:.4f}")
print(f"T/W at requirement conditions = 4*{T1:.0f}*{volt:.4f}*{rho_ratio:.4f}/{m:.0f} = {TW:.3f}")

# relative standard uncertainties (k=1) of each input, and sensitivity of ln(TW)
rows = [
    ("stand calibration (des-thrust-stand U=0.61% k=2)", 0.0061 / 2, "B, normal"),
    ("motor/prop spread 3%/unit; one measured unit stands for 4", 0.03 * math.sqrt(12) / 4, "B, normal"),
    ("exponent a in [1.6, 2.0], uniform: |ln(14/16)|*0.2/sqrt3", abs(math.log(V / V0)) * 0.2 / math.sqrt(3), "B, rect"),
    ("pack voltage under load +-0.2 V, uniform: a*0.2/sqrt3/14", a * 0.2 / math.sqrt(3) / V, "B, rect"),
    ("scale +-2 g, uniform", 2 / math.sqrt(3) / m, "B, rect"),
]
tot = math.sqrt(sum(u * u for _, u, _ in rows))
print("\n contribution                                              u_rel     share of variance")
for name, u, kind in sorted(rows, key=lambda r: -r[1]):
    print(f" {name:<58s} {u*100:5.2f} %   {u*u/tot/tot*100:5.1f} %")
U = 2 * tot * TW
print(f"\ncombined u_rel = {tot*100:.2f} %, u = {tot*TW:.3f}; expanded U (k=2) = {U:.3f}")
print(f"interval: {TW-U:.2f} ... {TW+U:.2f}")
print("decision with guard band (accept if TW - U >= 2.5):", "PASS" if TW - U >= 2.5 else "NOT PROVEN")

# Monte Carlo check of the linear propagation
rng = np.random.default_rng(42)
N = 200_000
Tst = T1 * (1 + rng.normal(0, 0.0061 / 2, N))                          # one calibration for all 4 (correlated)
e = rng.normal(0, 0.03, (N, 4))                                        # e[:,0] - the measured motor (installed)
units = (4 + e.sum(1)) / (1 + e[:, 0])                                 # true sum of 4 / measured one
aa = rng.uniform(1.6, 2.0, N)
VV = V + rng.uniform(-0.2, 0.2, N)
mm = m + rng.uniform(-2, 2, N)
tw = Tst * units * (VV / V0) ** aa * rho_ratio / mm
lo, hi = np.percentile(tw, [2.5, 97.5])
print(f"\nMonte Carlo {N}: mean {tw.mean():.3f}, sd {tw.std():.3f}, 95% interval {lo:.2f} ... {hi:.2f}, P(TW<2.5) = {(tw<2.5).mean()*100:.1f} %")

# what each next experiment buys
def comb(skip):
    return math.sqrt(sum(u * u for n_, u, _ in rows if not n_.startswith(skip)))
for label, skip in [("measure all four motors on the stand", "motor/prop"), ("measure at 14.0 V directly", "exponent"),
                    ("buy a 0.1 g scale", "scale"), ("all four motors AND at 14.0 V", ("motor/prop", "exponent"))]:
    c = comb(skip)
    print(f"next experiment: {label:<38s} -> U(k=2) = {2*c*TW:.3f}, lower bound {TW-2*c*TW:.3f}")
```

```text
corrections: voltage (14/16)^1.8 = 0.7863, air density 293.15/308.15 = 0.9513
T/W at requirement conditions = 4*750*0.7863*0.9513/860 = 2.610

 contribution                                              u_rel     share of variance
 motor/prop spread 3%/unit; one measured unit stands for 4   2.60 %    59.0 %
 exponent a in [1.6, 2.0], uniform: |ln(14/16)|*0.2/sqrt3    1.54 %    20.8 %
 pack voltage under load +-0.2 V, uniform: a*0.2/sqrt3/14    1.48 %    19.3 %
 stand calibration (des-thrust-stand U=0.61% k=2)            0.30 %     0.8 %
 scale +-2 g, uniform                                        0.13 %     0.2 %

combined u_rel = 3.38 %, u = 0.088; expanded U (k=2) = 0.177
interval: 2.43 ... 2.79
decision with guard band (accept if TW - U >= 2.5): NOT PROVEN

Monte Carlo 200000: mean 2.612, sd 0.089, 95% interval 2.44 ... 2.79, P(TW<2.5) = 10.3 %
next experiment: measure all four motors on the stand   -> U(k=2) = 0.113, lower bound 2.496
next experiment: measure at 14.0 V directly             -> U(k=2) = 0.157, lower bound 2.452
next experiment: buy a 0.1 g scale                      -> U(k=2) = 0.176, lower bound 2.433
next experiment: all four motors AND at 14.0 V          -> U(k=2) = 0.079, lower bound 2.530
```

## diagnostics
- **Příznak:** požadavky znějí jako přání („spolehlivý“, „rychlý“)
  - Možná příčina: chybí kritérium a způsob ověření.
  - Co udělat: přepište je s číslem a testem; pokud číslo není, nejde o požadavek, ale o cíl.
- **Příznak:** po ladění není jasné, jestli je to lepší, nebo horší
  - Možná příčina: chybí metrika a log „před“.
  - Co udělat: před změnou pořiďte log a metriku; do deníku zapište změnu i s výsledkem.
- **Příznak:** za měsíc není jasné, proč má parametr právě tuto hodnotu
  - Možná příčina: změna bez záznamu.
  - Co udělat: zaveďte pravidlo „není řádek v CHANGELOG – není změna“.
- **Příznak:** někdo jiný nedokáže stavbu zopakovat
  - Možná příčina: README popisuje sen, ne stroj.
  - Co udělat: README má popisovat aktuální stav a verze firmwaru; konfigurace patří do repozitáře.

## references
- Systems Engineering Handbook — NASA (free PDF) | https://www.nasa.gov/reference/systems-engineering-handbook/ | primary | A
- Requirements engineering (overview, further reading) — Wikipedia | https://en.wikipedia.org/wiki/Requirements_engineering | secondary | B
- Log Analysis and Tuning Workflow — ArduPilot (example of evidence-based tuning) | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A

## checklist
- Repozitář inženýrské složky je vytvořen
- ≥ 8 požadavků s kritériem a způsobem ověření
- Schéma napájení a dat s rozhraními je nakreslené
- Tabulka testů je provázaná s požadavky
- Deník změn se vede od první změny
