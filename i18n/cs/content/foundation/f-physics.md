---
id: f-physics
title: "Jak létá multikoptéra"
level: L1
readingTime: 15 min
firmware: libovolný firmware
status: published
added: 2026-11-07
tags:
  - fyzika
  - mixer
related:
  - f-motors-esc
  - bf-pid-reg-in-bf
next:
  - f-power
source: content/foundation/f-physics.md
source_hash: c96f8d3b120a
---

## summary
Multikoptéra nemá kormidla: veškeré řízení spočívá ve změně otáček motorů. Modul vysvětluje, jak ze čtyř (šesti, osmi) vrtulí vznikají plyn, klonění (roll), klopení (pitch) a zatáčení (yaw), proč se vrtule točí opačnými směry, co je mixer a proč poměr tahu k tíze určuje povahu dronu. Je to základ, na kterém stojí PID, filtry a vůbec celé ladění.

## theory
### Tah a tíha
Vrtule odhazuje vzduch dolů a získává tah směrem nahoru. Aby dron visel, musí se celkový tah všech motorů rovnat tíze. Tah roste přibližně s druhou mocninou otáček: aby se tah zdvojnásobil, je třeba otáčky zvýšit asi 1.4krát.

Poměr tahu k tíze (thrust-to-weight, T/W) je maximální tah všech motorů dělený vzletovou hmotností:

- kolem 2:1 – minimum pro řiditelný let: těžké platformy, nákladní oktokoptéry;
- 3:1–4:1 – klidné stroje 7–10" na dlouhé lety;
- 6:1 a více – freestyle a závody.

Při T/W 2:1 probíhá vis přibližně na polovině plynu a rezerva na manévr a poryv větru téměř není. To je hlavní argument, proč těžký dron nelze ladit jako pětipalec.

{{diagram:chart-hover-throttle|Газ висения лежит между долей тяги f и квадратом: при T/W 4.1 это 24–49 %, по кривой 0.65 — 40 %; 60 % газа — уже T/W 2.25–2.8, для 5–7" это стоп.}}

### Reakční moment a směry otáčení
Motor, který roztáčí vrtuli, se zároveň snaží pootočit rám opačným směrem – to je reakční moment. Kdyby se všechny vrtule točily stejným směrem, rám by se otáčel kolem svislé osy. Proto má kvadrokoptéra dva páry: vrtule na úhlopříčce se točí stejným směrem, sousední opačným. Momenty se navzájem ruší, dokud jsou otáčky stejné.

{{diagram:quad-forces|Klonění a zatáčení kvadrokoptéry: rozdíl tahů dává moment kolem osy, rozdíl reakčních momentů páru CCW/CW dává zatáčení.}}

### Čtyři osy řízení
- **Plyn (throttle):** všechny motory současně rychleji nebo pomaleji.
- **Klonění (roll):** motory na jedné straně rychleji, na druhé pomaleji. Klonění doprava – levé motory rychleji.
- **Klopení (pitch):** přední proti zadním. Sklopení přídě dolů (let vpřed) – zadní motory rychleji.
- **Zatáčení (yaw):** úhlopříčné páry. Motor, který se točí proti směru hodinových ručiček, tlačí rám ve směru hodinových ručiček. Pro otočení ve směru hodinových ručiček (při pohledu shora) se zrychlí motory točící se proti směru hodinových ručiček a druhý pár se zpomalí. Celkový tah se přitom téměř nemění.

Yaw je „nejslabší“ osa: moment z rozdílu otáček je malý ve srovnání s momenty z rozdílu tahu. Proto dron v zatáčení reaguje pomaleji a snáze narazí na omezení motorů.

### Mixer
Řídicí jednotka (FC) počítá požadovaný plyn, klonění, klopení a zatáčení a mixer je převádí na povel pro každý motor. Pro každý motor je to součet: plyn plus příspěvek klonění, klopení a zatáčení se znaménkem, které závisí na poloze motoru a směru otáčení. Mixer je dán typem rámu (Quad X, Hex, Octo X8 atd.) a firmware zná znaménka pro každý typ.

Z toho plyne hlavní pravidlo: pořadí motorů a směry otáčení ve firmwaru se musí shodovat se skutečnou stavbou. Zaměněný motor znamená dron, který se při vzletu okamžitě převrátí.

### Saturace motorů
Pokud je některý motor už na 100 % nebo na 0 %, mixer nemůže povel splnit úplně. Firmwary to řeší různě (Betaflight – air mode a mixer scaling, ArduPilot – priorita klonění/klopení před zatáčením), ale fyziku neošidíte: bez rezervy tahu není řízení.

### Mixer v číslech (Quad X, konvence Betaflightu)
Povel motoru = plyn + k_r·roll + k_p·pitch + k_y·yaw, kde k je ±1 podle polohy a směru otáčení. Pro Quad X (číslování Betaflightu: 1 – zadní pravý, 2 – přední pravý, 3 – zadní levý, 4 – přední levý; „props in“/„props out“ mění znaménka yaw):

| Motor | roll | pitch | yaw |
|---|---|---|---|
| 1 zadní pravý (CW) | −1 | +1 | −1 |
| 2 přední pravý (CCW) | −1 | −1 | +1 |
| 3 zadní levý (CCW) | +1 | +1 | +1 |
| 4 přední levý (CW) | +1 | −1 | −1 |

(znaménka yaw závisí na konvenci firmwaru; ArduPilot používá vlastní číslování po obvodu – vždy porovnávejte se schématem frame type). Příklad: plyn 0.5, povel roll +0.1, ostatní 0 → motory 1,2 = 0.4, motory 3,4 = 0.6: tah vlevo je větší – klonění doprava. Povel yaw +0.05 → 1 = 0.45, 2 = 0.55, 3 = 0.55, 4 = 0.45: součet tahu je stejný, reakční momenty se nevyruší → rám se otáčí.

### Proč je yaw slabý – odhad
Moment v ose roll/pitch = Δtah × rameno (0.1–0.3 m): při Δ = 200 g (2 N) a rameni 0.15 m je to 0.3 N·m. Moment v ose yaw = rozdíl reakčních momentů motorů: reakční moment motoru ≈ výkon/úhlová rychlost = 150 W / (14 000 ot/min ≈ 1470 rad/s) ≈ 0.1 N·m; změna o 30 % u páru – ~0.06 N·m. To je 5krát méně – odtud pomalý yaw a brzká saturace. U „props out“ a nakloněných motorů pracuje část tahu pro yaw – je to rychlejší, ale se ztrátami.

### Dynamika: od povelu k úhlu
Úhlové zrychlení = moment / moment setrvačnosti J (u 5" je J v ose roll ≈ 0.003–0.005 kg·m²; u 15" X8 je 50–100krát větší): 0.3 N·m / 0.004 = 75 rad/s² ≈ 4300 °/s² – proto 5" zvládne 1000 °/s za čtvrt sekundy, kdežto X8 se stejnou poměrnou rezervou tahu je o řád pomalejší a jeho PID koeficienty a omezení zrychlení (`ATC_ACCEL_*_MAX`) jsou jiné. Podrobně – modul „Mechanika letu“.

## practice
### Laboratorní úloha: spočítat T/W vlastní stavby
1. Najděte v datasheetu motoru tabulku tahu pro vaši vrtuli a napětí: maximální tah jednoho motoru v g.
2. Vynásobte počtem motorů – to je maximální tah.
3. Zvažte dron s baterií, kamerou a vším, co za letu nese.
4. T/W = maximální tah / vzletová hmotnost. Zapište do deníku dronu.
5. Kontrola podle logu: průměrný plyn ve visu by měl být přibližně roven `1 / (T/W)` (s opravou na nelinearitu – tah roste rychleji než plyn).

### Kontrola směrů bez vrtulí
1. Sundejte vrtule.
2. Na záložce Motors (Betaflight) nebo Motor Test (ArduPilot) postupně roztočte každý motor na malém plynu.
3. Porovnejte číslo a směr otáčení se schématem rámu vašeho firmwaru.

### Řešený příklad a co čekat v logu
Motor podle tabulky výrobce dává 1500 g na zvolené vrtuli a 6S, motory jsou čtyři, vzletová hmotnost s baterií je 1450 g: T/W = 4 · 1500 / 1450 ≈ 4.1.

Odhad plynu ve visu „1 / (T/W)“ by dal ~24 %. Tah ale roste rychleji než plyn (přibližně s druhou mocninou otáček), takže skutečný plyn ve visu je vyšší. Kdyby tah rostl přesně s druhou mocninou plynu, byl by √(1 / 4.1) ≈ 49 %. V praxi leží plyn ve visu mezi těmito dvěma odhady – pro tento příklad 24–49 %. V Betaflightu je vidět v Blackboxu (průměrný `motor` ve visu), v ArduPilotu jako `CTUN.ThO` a naučený `MOT_THST_HOVER`.

### Co zapsat
- Zdroj maximálního tahu: model motoru, vrtule, napětí, řádek tabulky. Tah na 4S a na 6S se liší několikanásobně, proto musí být tabulka pro vaše napětí.
- Hmotnost – na váze, se vším, co letí: s baterií, kamerou, anténami, páskem.
- T/W a plyn ve visu z logu. Je-li plyn ve visu nad 60 %, rezerva na manévr a vítr téměř není; pod 20 % je stroj velmi ostrý a ladění na malém plynu bude obtížnější.
- Tabulku motorů: číslo, očekávaný směr podle schématu rámu, skutečný směr, značku „ok“.

Laboratorní úloha je splněna, když jsou zapsány hmotnost s baterií a maximální tah se zdrojem, T/W je spočítán a zanesen do deníku dronu, plyn ve visu z logu je porovnán s rozsahem mezi 1/(T/W) a √(1/(T/W)) a pořadí i směr všech motorů jsou ověřeny bez vrtulí.

## diagnostics
- **Příznak:** dron se převrací hned při vzletu
  - Možná příčina: zaměněné pořadí motorů nebo směr otáčení, vrtule jsou nasazené obráceně.
  - Co udělat: bez vrtulí zkontrolovat každý motor podle schématu rámu, zkontrolovat vrtule.
- **Příznak:** dron se ve visu pomalu otáčí v ose yaw
  - Možná příčina: nakřivo usazený motor, různé vrtule, různě silné motory.
  - Co udělat: zkontrolovat souosost motorů, nasadit stejné nové vrtule.
- **Příznak:** vis při plynu nad 60–70 %
  - Možná příčina: přetížení, T/W kolem 1.5–2.
  - Co udělat: odlehčit, nasadit jiné vrtule/motory, nelétat ve větru.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Connect ESCs and Motors — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- Copter Motors Library — ArduPilot Dev | https://ardupilot.org/dev/docs/code-overview-copter-motors-library.html | primary | A

## checklist
- Umím vysvětlit, jak dron bez kormidel dělá klonění, klopení a zatáčení
- Vím, proč se sousední vrtule točí opačnými směry
- T/W vlastní stavby mám spočítaný a zapsaný
- Pořadí a směr motorů mám ověřené bez vrtulí
