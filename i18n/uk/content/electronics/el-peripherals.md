---
id: el-peripherals
title: "Підключення периферії: UART, I2C, CAN на практиці"
level: L2
readingTime: 35 хв
firmware: Betaflight · INAV · ArduPilot
status: published
added: 2026-11-08
tags:
  - UART
  - I2C
  - DroneCAN
  - периферія
related:
  - el-measure
  - f-fc-sensors
  - bf-ports
  - el-emi
next:
  - rf-antennas
source: content/electronics/el-peripherals.md
source_hash: a416702cb100
---

## summary
Спалити порт польотника простіше, ніж здається: 5 В на 3.3-вольтову ногу, переплутані TX/RX із подачею живлення від двох джерел, I2C без підтягувань, CAN без термінатора. Модуль — практичний протокол підключення будь-якого пристрою: визначити інтерфейс і рівні → знайти порт і його живлення → перевірити мультиметром до ввімкнення → налаштувати протокол у прошивці → підтвердити дані аналізатором. З прикладами: GPS+компас, далекомір, ESC-телеметрія, цифрова відеосистема, DroneCAN-вузол.

## theory
### Три шини та їхній характер
| Шина | Проводи | Швидкість | Адресація | Типові пристрої | Головні граблі |
|---|---|---|---|---|---|
| UART | TX, RX, GND (+живлення) | 9600 – 2 Мбод; GPS 57600–230400 (за прошивкою: Betaflight — 57600, ArduPilot ставить 230400), CRSF 420000, MSP 115200 | точка-точка | GPS, приймач, телеметрія, VTX, далекомір, companion | TX↔RX навхрест; інверсія (SBUS); один порт — один пристрій |
| I2C | SDA, SCL, GND | 100/400 кГц | адреса 7 біт, багато пристроїв на шині | компас, барометр, OLED, деякі далекоміри | немає підтягувань; однакові адреси; довгі проводи (> 30 см — проблеми) |
| SPI | CLK, MOSI, MISO, CS | до десятків МГц | за CS | гіроскоп, OSD, flash, іноді баро | лише на платі; назовні майже не виводять |
| CAN (DroneCAN) | CAN_H, CAN_L, GND (+живлення) | 1 Мбіт/с | node ID 1–125 | GPS/компас, ESC, датчики струму, серво, далекоміри | немає термінаторів 120 Ом на кінцях; вита пара; однакові node ID |

### Рівні та живлення
- Логіка FC — **3.3 В**. Більшість входів витримують 5 В («5V tolerant»), але не всі: читай даташит МК (STM32F4/F7/H7 — більшість GPIO 5V-tolerant, крім ніг з аналоговими функціями). Правило: сумніваєшся — дільник 1k/2k на вході FC або узгоджувач рівнів.
- **Живлення портів**: пади 5 В і 9 В на FC живляться від бортових BEC з лімітом (типово 5 В/2–3 А, 9 В/2–3 А сумарно на всіх споживачів). Підключення Raspberry Pi або цифрового air unit «від пада» — перевантаження BEC; живи від окремого BEC.
- **Спільна земля** — завжди. Пристрій із власним живленням без спільної землі з FC — сміття на UART або згорілий порт.
- **Дві точки живлення** (пристрій живиться від FC і від USB companion одночасно) — зворотний струм через BEC. Діод або одне живлення.

### UART: деталі
- TX FC → RX пристрою, RX FC ← TX пристрою.
- **Інверсія**: SBUS і деякі протоколи інвертовані; на F4 без апаратного інвертора потрібен зовнішній або порт з інвертором; F7/H7 — програмна інверсія (Betaflight `serialrx_inverted`). CRSF — не інвертований, одна лінія в кожен бік.
- **Один провід**: ESC-телеметрія (протокол KISS/BLHeli_32) — односпрямована (ESC → FC): приходить на один RX-пін від усіх ESC по черзі через спільний провід, запит іде сигналом DShot; VTX SmartAudio/Tramp — справжній half-duplex: один провід на TX-пін, дані в обидва боки.
- На один UART — один пристрій (крім half-duplex-протоколів, спеціально так зроблених).

### I2C: деталі
- Підтягування 2.2–4.7 кОм на SDA і SCL до 3.3 В — зазвичай уже є на FC; другий пристрій із власними підтягуваннями сумарно знижує опір — норма до ~1 кОм еквівалентно.
- Адреси: компас HMC5883 0x1E, QMC5883 0x0D, IST8310 0x0C/0x0E, баро BMP280 0x76/0x77, MS5611 0x76/0x77. Два пристрої з однією адресою — конфлікт.
- Довжина: короткі проводи, скручені із землею; на щоглі GPS 15–20 см — норма, 50 см — уже ризиковано (знизити до 100 кГц).

{{diagram:i2c-transaction|Транзакція I2C по бітах — саме це бачить логічний аналізатор, коли «датчик не знаходиться».}}

{{diagram:chart-i2c-pullup-window|Подтяжка должна лежать между красной линией (0.97 кОм) и кривой режима: при 100 пФ одиночные 4.7 кОм для 400 кГц слишком слабы, а две параллельные (2.35 кОм) — в окне.}}

### DroneCAN: коли і як
Коли: апарат великий (довгі проводи → UART/I2C ловлять завади), багато пристроїв, потрібна телеметрія ESC і датчиків по одній шині, резервування. В ArduPilot: `CAN_P1_DRIVER = 1` (увімкнути порт 1), `CAN_D1_PROTOCOL = 1` (DroneCAN), перезавантаження; GPS `GPS_TYPE = 9` (`GPS1_TYPE` у 4.6+) — DroneCAN, компас знаходиться автоматично. Шина: вита пара, термінатори 120 Ом на обох кінцях (багато пристроїв мають перемичку термінатора), живлення вузлів за специфікацією (зазвичай 5 В), унікальні node ID (автопілот роздає їх як DNA-сервер при динамічному розподілі; `CAN_D1_UC_NODE` — власний node ID автопілота).

### Протокол підключення (завжди однаковий)
1. Даташит пристрою: інтерфейс, рівні, живлення (В, мА), протокол і швидкість.
2. Карта FC: вільний порт, його інвертор/живлення, ліміт BEC.
3. Проводи підписані; TX/RX навхрест; земля спільна.
4. **До ввімкнення**: мультиметр — немає КЗ 5 В/3.3 В на GND, живлення пристрою піде з потрібного пада.
5. Увімкнення через smoke stopper. Напруга на пристрої в нормі.
6. Прошивка: порт → функція → протокол/швидкість. Перевірка даних (GPS: супутники; компас: курс змінюється при повороті; ESC-телеметрія: RPM на вкладці моторів).
7. Якщо даних немає — аналізатор на лінію: чи є байти, яка швидкість, інверсія.

{{diagram:periph-connect-flow|Мультиметр и smoke stopper — до прошивки; если данных нет, следующий шаг — анализатор на линии: есть ли байты, какая скорость, нет ли инверсии.}}

## practice
### Крок 0. Розрахунок шин до паяння
Перевіряє чотири рішення з теорії: вікно підтяжок I²C за ємністю шини, перетин адрес датчиків, завантаження UART потоком UBX-NAV-PVT і опір шини CAN. Запускається на будь-якому комп'ютері з Python 3; збережи як `periph_lab.py`:
```python
"""Peripheral bus checks: I2C pull-up window, address conflicts, UART load of a GPS, CAN termination."""
import itertools

# I2C: TI SLVA689 (from the I2C-bus spec): Rp_min = (Vcc - VOL) / IOL, Rp_max = tr / (0.8473 * Cb)
VCC, VOL, IOL = 3.3, 0.4, 3e-3
TR = {"100 kHz": 1000e-9, "400 kHz": 300e-9, "1 MHz (Fm+)": 120e-9}
rp_min = (VCC - VOL) / IOL
print(f"1) I2C pull-up window at {VCC} V: Rp_min = {rp_min:.0f} Ohm")
for cb_pf in (50, 100, 200, 400):
    cells = []
    for mode, tr in TR.items():
        rmax = tr / (0.8473 * cb_pf * 1e-12)
        bad = "Fm+" not in mode and rmax < rp_min          # Fm+: the I2C spec (UM10204) allows 20 mA sink, so Rp_min is lower; not checked here
        cells.append(f"{mode} {rmax / 1000:5.2f} k" + (" (impossible)" if bad else ""))
    print(f"   Cb {cb_pf:3d} pF: Rp_max " + " | ".join(cells))


def par(*r):
    return 1 / sum(1 / x for x in r)


print(f"   pull-ups in parallel: FC 4.7k || GPS 4.7k = {par(4700, 4700):.0f} Ohm, "
      f"+ third 2.2k = {par(4700, 4700, 2200):.0f} Ohm (min {rp_min:.0f})")
for r in (4700, 2350, 1000):
    tr = 0.8473 * r * 100e-12
    print(f"   rise time with {r} Ohm and 100 pF: {tr * 1e9:.0f} ns")

# Address conflicts (7-bit) from ArduPilot 4.7.2 drivers
DEV = {"QMC5883L": [0x0D], "IST8310": [0x0C, 0x0D, 0x0E, 0x0F], "HMC5883": [0x1E],
       "MS5611": [0x76, 0x77], "BMP280": [0x76, 0x77], "MS4525DO": [0x28, 0x36, 0x46], "PX4Flow": [0x42]}
print("\n2) I2C address overlaps (possible addresses per driver):")
for a, b in itertools.combinations(DEV, 2):
    common = sorted(set(DEV[a]) & set(DEV[b]))
    if common:
        print(f"   {a} / {b}: " + ", ".join(f"0x{x:02X}" for x in common))

# UART load: UBX-NAV-PVT payload is the ubx_nav_pvt struct in AP_GPS_UBLOX.h
pvt = 4 + 2 + 5 * 1 + 1 + 4 + 4 + 4 * 1 + 2 * 4 + 2 * 4 + 2 * 4 + 4 * 4 + 4 + 4 + 4 + 2 + 1 + 5 + 4 + 2 + 2
frame = pvt + 8                                   # sync 2 + class 1 + id 1 + length 2 + checksum 2
print(f"\n3) UBX-NAV-PVT: payload {pvt} B, frame {frame} B")
for baud in (9600, 38400, 115200, 230400):
    for hz in (5, 10):
        load = frame * hz * 10 / baud
        print(f"   {baud:>6} baud, {hz:>2} Hz: {100 * load:5.1f} % of the line")

print("\n4) CAN: resistance CAN_H-CAN_L, power off")
for n in (1, 2, 3):
    print(f"   {n} x 120 Ohm -> {120 / n:.0f} Ohm" + ("  <- correct" if n == 2 else ""))
for rate in (1_000_000, 500_000):
    print(f"   {rate // 1000} kbit/s: bit time {1e9 / rate:.0f} ns")
```
Вивід `python3 periph_lab.py` (2026-11-26):
```
1) I2C pull-up window at 3.3 V: Rp_min = 967 Ohm
   Cb  50 pF: Rp_max 100 kHz 23.60 k | 400 kHz  7.08 k | 1 MHz (Fm+)  2.83 k
   Cb 100 pF: Rp_max 100 kHz 11.80 k | 400 kHz  3.54 k | 1 MHz (Fm+)  1.42 k
   Cb 200 pF: Rp_max 100 kHz  5.90 k | 400 kHz  1.77 k | 1 MHz (Fm+)  0.71 k
   Cb 400 pF: Rp_max 100 kHz  2.95 k | 400 kHz  0.89 k (impossible) | 1 MHz (Fm+)  0.35 k
   pull-ups in parallel: FC 4.7k || GPS 4.7k = 2350 Ohm, + third 2.2k = 1136 Ohm (min 967)
   rise time with 4700 Ohm and 100 pF: 398 ns
   rise time with 2350 Ohm and 100 pF: 199 ns
   rise time with 1000 Ohm and 100 pF: 85 ns

2) I2C address overlaps (possible addresses per driver):
   QMC5883L / IST8310: 0x0D
   MS5611 / BMP280: 0x76, 0x77

3) UBX-NAV-PVT: payload 92 B, frame 100 B
     9600 baud,  5 Hz:  52.1 % of the line
     9600 baud, 10 Hz: 104.2 % of the line
    38400 baud,  5 Hz:  13.0 % of the line
    38400 baud, 10 Hz:  26.0 % of the line
   115200 baud,  5 Hz:   4.3 % of the line
   115200 baud, 10 Hz:   8.7 % of the line
   230400 baud,  5 Hz:   2.2 % of the line
   230400 baud, 10 Hz:   4.3 % of the line

4) CAN: resistance CAN_H-CAN_L, power off
   1 x 120 Ohm -> 120 Ohm
   2 x 120 Ohm -> 60 Ohm  <- correct
   3 x 120 Ohm -> 40 Ohm
   1000 kbit/s: bit time 1000 ns
   500 kbit/s: bit time 2000 ns
```

### Крок 1. GPS із компасом (UART + I2C)
Підключити GPS до UARTx (TX↔RX), компас до SDA/SCL, живлення 5 В. Betaflight: Ports → GPS на UARTx, Configuration → GPS UBLOX, 57600/115200; магнітометр увімкнути. ArduPilot: `SERIALx_PROTOCOL = 5`, `GPS_TYPE = 2` (`GPS1_TYPE` у 4.6+, u-blox), компас — автодетект. Перевірка: NSats ≥ 6 надворі, курс повертається.

### Крок 2. ESC-телеметрія
Спільний телеметрійний провід від усіх ESC → RX вільного UART. Betaflight: Ports → ESC на UARTx, `feature ESC_SENSOR` (Configuration → ESC Sensor) увімкнено; перевірка — RPM/температура на вкладці Motors без пропів. ArduPilot: `SERIALx_PROTOCOL = 16`.

### Крок 3. Далекомір або інший UART/I2C-пристрій
За протоколом із теорії; перевірка в прошивці (ArduPilot `RNGFND1_TYPE`, Betaflight/INAV — вкладка датчиків).

### Крок 4. Аналізатор
Зняти один кадр: UBX з GPS (заголовок `B5 62`), байт ESC-телеметрії або I2C-транзакцію компаса з адресою та ACK.

### Що має вийти і що записати
- **До ввімкнення:** мультиметром — 5 В на роз'ємі пристрою, спільна земля, TX і RX не переплутані (TX одного йде на RX іншого). Рівні 3.3 і 5 В не змішані: 5-вольтовий TX на 3.3-вольтовий RX без узгодження — шлях до згорілого порту.
- **GPS:** у прошивці зростає кількість супутників, з'являється фіксація. Компас на I²C знаходиться автоматично. Якщо ні, сканер шини покаже адресу: наприклад, 0x0D (QMC5883L), 0x0E (IST8310), 0x1E (HMC5883L).
- **ESC-телеметрія:** у вкладці Motors (Betaflight) без пропів видно оберти й температуру кожного ESC. Якщо в одного немає — провід телеметрії не дійшов від його ESC.
- **Кадр аналізатором:** UBX починається з `B5 62`, далі клас, ID і довжина. I²C-транзакція — адреса, біт читання або запису та ACK від пристрою. Підпиши байти на скриншоті аналізатора й поклади його в паспорт збірки.

Лабораторна зараховується, коли UART-пристрій, I²C-пристрій і ESC-телеметрія підключені й видні в прошивці, рівні та живлення перевірені мультиметром до ввімкнення із записом значень, а один кадр протоколу знятий аналізатором і підписаний по байтах.

## diagnostics
- **Симптом:** пристрій не відповідає, порт налаштовано
  - Можлива причина: TX/RX не навхрест, швидкість, інверсія, немає спільної землі.
  - Що зробити: аналізатор на лінію пристрою: чи є байти; поміняти TX/RX; перевірити GND.
- **Симптом:** I2C-пристрій «то видно, то ні»
  - Можлива причина: довгі проводи, немає підтягувань, завади від силових.
  - Що зробити: коротше, скручені, 100 кГц, підтягування 2.2–4.7 кОм.
- **Симптом:** після підключення companion FC перезавантажується
  - Можлива причина: перевантаження 5 В BEC польотника.
  - Що зробити: окремий BEC 5 В/3–5 А для companion, спільна земля.
- **Симптом:** DroneCAN-вузол не видно
  - Можлива причина: немає термінаторів, CAN_H/CAN_L переплутані, драйвер не ввімкнено.
  - Що зробити: 120 Ом на кінцях, перевірити `CAN_P1_DRIVER`/`CAN_D1_PROTOCOL`, перезавантаження.
- **Симптом:** згорів порт після підключення 5-вольтового датчика
  - Можлива причина: нога не 5V-tolerant або живлення потрапило на сигнальну лінію.
  - Що зробити: дільник/узгоджувач рівнів; інший порт; перевіряти даташит МК.

## references
- ArduPilot — CAN Bus Setup (DroneCAN) | https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html | primary | A
- Betaflight — Serial (development docs: ports, inversion, half-duplex) | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- ArduPilot — Serial Port Options and Protocols | https://ardupilot.org/copter/docs/common-serial-options.html | primary | A

## checklist
- Знаю рівні, живлення та граблі кожної шини
- Протокол підключення виконую завжди в одному порядку, з мультиметром до ввімкнення
- GPS, компас і ESC-телеметрія підключені й видні в прошивці
- Зняв кадр протоколу аналізатором
- Розумію, коли потрібен DroneCAN і як його ввімкнути
