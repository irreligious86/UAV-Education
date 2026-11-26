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


{{diagram:safety-thermal-ladder|Окно заряда 10–45 °C и ступени разгона на одной шкале: от верха окна до саморазогрева всего 35 °C, а с 180 °C катод сам даёт кислород.}}

{{diagram:safety-bench-sequence|Порядок стенда: шаги 1–6 без пропов, пропы — последним шагом на площадке; любой непройденный шаг останавливает работу.}}

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

{{diagram:preflight-go-nogo|Предполётный чек-лист как цепочка «да/нет»: любой непройденный пункт останавливает вылет, а странность на первом висении заканчивается посадкой.}}

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

### Лабораторные (SITL ArduCopter 4.7.2 и расчёт; текст — в русской версии)

```python
"""f-safety lab: ArduCopter 4.7.2 SITL — what 'armed' means on the bench, and what an RC loss does
(1) on the ground, armed;  (2) in the air at 10 m in GUIDED.  RC loss = SIM_RC_FAIL=1 (no pulses)."""
import sys, time
from pymavlink import mavutil
m = mavutil.mavlink_connection(sys.argv[1]); m.wait_heartbeat()
t0 = time.time()
def T(): return f"t={time.time()-t0:6.1f}s"
def setp(n, v):
    m.mav.param_set_send(m.target_system, m.target_component, n.encode(), v, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(0.3)
def mode(name):
    m.set_mode(m.mode_mapping()[name])
def flush():
    while m.recv_match(blocking=False) is not None: pass
def armed():
    flush()
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    return bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED), mavutil.mode_string_v10(hb)
def pwm():
    flush()
    s = m.recv_match(type='SERVO_OUTPUT_RAW', blocking=True, timeout=3)
    return [s.servo1_raw, s.servo2_raw, s.servo3_raw, s.servo4_raw]
def drain(sec, tag=""):
    end = time.time() + sec; last = None
    while time.time() < end:
        msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
        if msg is None: continue
        if msg.get_type() == 'STATUSTEXT':
            print(f"{T()} {tag} STATUSTEXT: {msg.text}")
        else:
            st = (bool(msg.base_mode & 128), mavutil.mode_string_v10(msg))
            if st != last: print(f"{T()} {tag} armed={st[0]} mode={st[1]}"); last = st
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
for n in ("MOT_SPIN_ARM", "MOT_SPIN_MIN", "FS_THR_ENABLE", "FS_THR_VALUE", "RC_FS_TIMEOUT", "DISARM_DELAY"):
    flush(); m.mav.param_request_read_send(m.target_system, m.target_component, n.encode(), -1)
    while True:
        p = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
        if p.param_id == n: break
    print(f"param {p.param_id} = {p.param_value:g}")
# wait until arming is possible (EKF + GPS) — try every 2 s
mode('STABILIZE')
for i in range(40):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
flush(); print(f"{T()} (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = {pwm()}")
time.sleep(2); print(f"{T()}     2 s later, still no throttle:                motors PWM = {pwm()}")
flush(); setp("SIM_RC_FAIL", 1); print(f"{T()}     SIM_RC_FAIL=1 (receiver silent)")
drain(4, "   ")
setp("SIM_RC_FAIL", 0); time.sleep(2)
# (2) in the air
mode('GUIDED')
for i in range(10):
    m.arducopter_arm(); time.sleep(1.5)
    if armed()[0]: break
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
while True:
    p = m.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
    if p.relative_alt > 9500: break
print(f"{T()} (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1")
flush(); tf = time.time(); setp("SIM_RC_FAIL", 1)
end = time.time() + 6; last = None
while time.time() < end:
    msg = m.recv_match(type=['STATUSTEXT', 'HEARTBEAT'], blocking=True, timeout=0.5)
    if msg is None: continue
    dt = time.time() - tf
    if msg.get_type() == 'STATUSTEXT': print(f"    +{dt:4.2f}s STATUSTEXT: {msg.text}")
    else:
        md = mavutil.mode_string_v10(msg)
        if md != last: print(f"    +{dt:4.2f}s mode={md}"); last = md
setp("SIM_RC_FAIL", 0); print(f"{T()} RC restored (SIM_RC_FAIL=0)"); drain(3, "   ")
```

```text
param MOT_SPIN_ARM = 0.1
param MOT_SPIN_MIN = 0.15
param FS_THR_ENABLE = 1
param FS_THR_VALUE = 975
param RC_FS_TIMEOUT = 1
param DISARM_DELAY = 10
t=  25.0s (1) armed on the ground in STABILIZE, throttle stick 1000 us: motors PWM = [1026, 1026, 1026, 1026]
t=  27.1s     2 s later, still no throttle:                motors PWM = [1100, 1100, 1100, 1100]
t=  27.5s     SIM_RC_FAIL=1 (receiver silent)
t=  28.0s     armed=True mode=STABILIZE
t=  28.2s     STATUSTEXT: Radio Failsafe - Disarming
t=  28.2s     STATUSTEXT: Disarming motors
t=  29.0s     armed=False mode=STABILIZE
t=  29.4s     STATUSTEXT: PreArm: Radio failsafe on
t=  50.8s (2) GUIDED, 10 m reached; now SIM_RC_FAIL=1
    +0.30s mode=GUIDED
    +0.99s mode=RTL
    +0.99s STATUSTEXT: Radio Failsafe
t=  57.9s RC restored (SIM_RC_FAIL=0)
t=  57.9s     STATUSTEXT: Radio Failsafe Cleared
t=  58.0s     armed=True mode=RTL
```

```python
import math
# 1) Energy of a pack and the IATA passenger category (Wh = Ah x V nominal; LiPo/Li-Ion 3.6-3.7 V per cell)
def wh(s, mah, v_cell): return s * v_cell * mah / 1000
def iata(e): return "<=100 Wh: ручная кладь, без согласования" if e <= 100 else (
    "100-160 Wh: ручная кладь, согласование, не больше 2" if e <= 160 else ">160 Wh: пассажиру нельзя, только груз")
packs = [("6S 1300 LiPo", 6, 1300, 3.7), ("6S 2200 LiPo", 6, 2200, 3.7), ("4S 5200 LiPo", 4, 5200, 3.7),
         ("6S2P P42A Li-Ion", 6, 8400, 3.6), ("6S4P P42A Li-Ion", 6, 16800, 3.6)]
for name, s, mah, v in packs:
    e = wh(s, mah, v); print(f"{name:18s} {e:6.1f} Wh  {iata(e)}")
# 2) Charging: current at 1C (course rule) and charger power at 4.2 V/cell
for name, s, mah in [("6S 1300", 6, 1300), ("4S 5200", 4, 5200)]:
    i = mah / 1000; p = s * 4.2 * i
    print(f"{name}: 1C = {i:.1f} A, P = {s}x4.2x{i:.1f} = {p:.0f} W")
# 3) Kinetic energy of a spinning prop, thin-rod model I = m L^2 / 12 (L = diameter)
for d_in, m_g, rpm in [(5, 4, 14000), (5, 4, 30000), (7, 9, 9000), (10, 18, 6000)]:
    L = d_in * 0.0254; I = m_g / 1000 * L**2 / 12; w = rpm * 2 * math.pi / 60
    print(f'{d_in}" {m_g} g @ {rpm} rpm: tip {math.pi*L*rpm/60:5.0f} m/s, E = {0.5*I*w*w:5.1f} J')
# 4) Temperature gate before charging (Gens Ace 10-45 C, course rule)
for t in (5, 25, 52):
    print(f"pack {t} C:", "заряжать" if 10 <= t <= 45 else "не заряжать: ждать/греть до 10-45 C")
```

```text
6S 1300 LiPo         28.9 Wh  <=100 Wh: ручная кладь, без согласования
6S 2200 LiPo         48.8 Wh  <=100 Wh: ручная кладь, без согласования
4S 5200 LiPo         77.0 Wh  <=100 Wh: ручная кладь, без согласования
6S2P P42A Li-Ion    181.4 Wh  >160 Wh: пассажиру нельзя, только груз
6S4P P42A Li-Ion    362.9 Wh  >160 Wh: пассажиру нельзя, только груз
6S 1300: 1C = 1.3 A, P = 6x4.2x1.3 = 33 W
4S 5200: 1C = 5.2 A, P = 4x4.2x5.2 = 87 W
5" 4 g @ 14000 rpm: tip    93 m/s, E =   5.8 J
5" 4 g @ 30000 rpm: tip   199 m/s, E =  26.5 J
7" 9 g @ 9000 rpm: tip    84 m/s, E =  10.5 J
10" 18 g @ 6000 rpm: tip    80 m/s, E =  19.1 J
pack 5 C: не заряжать: ждать/греть до 10-45 C
pack 25 C: заряжать
pack 52 C: не заряжать: ждать/греть до 10-45 C
```

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
