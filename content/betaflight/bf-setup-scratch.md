---
id: bf-setup-scratch
title: "Betaflight с нуля: от пустой платы до первого висения"
level: L2
readingTime: 55 мин
firmware: Betaflight 4.5 (проверено на 4.5.6 SITL, ветка 4.5-maintenance)
status: published
added: 2026-11-10
tags:
  - Betaflight
  - настройка
  - SITL
  - калибровка
  - failsafe
  - первый полёт
related:
  - bf-intro
  - bf-ports
  - link-elrs
  - link-protocols
  - f-motors-esc
  - bf-modes-osd
  - bf-failsafe
  - link-vtx
  - bf-filters
  - bf-pid
  - bf-blackbox
  - bf-cli
next:
  - bf-filters
  - bf-blackbox
---

## summary
Один 5″ квадрокоптер (Betaflight 4.5, приёмник ELRS, ESC с DShot, аналоговый или цифровой VTX) проходит путь от пустой платы до записанного висения. Порядок — 17 шагов настройки курса. Шаги, которые уже разобраны в других модулях, здесь даны одной строкой: что нажать в этой прошивке и куда идти за подробностями. Подробно расписано то, чего в курсе раньше не было: калибровка `vbat_scale`, `ibata_scale` и `ibata_offset` по мультиметру и мА·ч зарядного (формулы проверены по исходникам 4.5), порядок и направление моторов (`motor_output_reordering`, `resource`, DShot-команды через `dshotprog` и диалог Motor direction), калибровка PWM-ESC, предполётная проверка и первое висение с критериями прерывания, основы GPS Rescue. Основной путь — Betaflight SITL, собранный из исходников. Лабораторная: конфиг и тест failsafe в SITL, затем тот же конфиг на реальном аппарате, калибровка АКБ, `diff all` и лог 60-секундного висения.

## theory
### Карта шагов: что, где и чем
{{diagram:bf-setup-flow|17 шагов идут строго по порядку: конфигурация, режимы, failsafe и бэкап проверяются в SITL; приёмник, моторы, ESC и АКБ — только на столе без пропов; пропы ставятся на шаге 15.}}

| # | Шаг | Где | Betaflight 4.5: вкладка / CLI | Подробно |
|---|---|---|---|---|
| 1 | Прошивка, бэкап старого конфига | SITL, USB | Firmware Flasher, `diff all` | bf-intro |
| 2 | Ориентация, миксер | SITL, USB | Setup, `mixer QUADX`, `align_board_*` | bf-intro |
| 3 | Порты UART | SITL (только CLI), USB | Ports, `serial` | bf-ports |
| 4 | Приёмник, bind | стол | Receiver, `serialrx_provider = CRSF` | link-elrs |
| 5 | Каналы, концы, центры | стол | Receiver, `map`, `min_check`, `max_check` | здесь, link-protocols |
| 6 | Протокол моторов | стол | Motors, `motor_pwm_protocol` | f-motors-esc |
| 7 | Порядок и направление | стол, без пропов | Motors, `motor_output_reordering`, `dshotprog` | здесь, bf-cli |
| 8 | Калибровка ESC (только PWM) | стол, без пропов | Motors, мастер-ползунок | здесь |
| 9 | Акселерометр | SITL, стол | Setup → Calibrate Accelerometer | bf-intro |
| 10 | Напряжение и ток | стол + полёт | Power & Battery, `vbat_scale`, `ibata_scale`, `ibata_offset` | здесь |
| 11 | Режимы, арм, блокировки | SITL | Modes, `aux`, `status` | bf-modes-osd |
| 12 | Failsafe: настроить и проверить | SITL + стол | Failsafe, `failsafe_*` | bf-failsafe |
| 13 | OSD и видео | стол | OSD, Video Transmitter | bf-modes-osd, link-vtx |
| 14 | GPS и GPS Rescue (если есть GPS) | стол + поле | `gps_rescue_*` | здесь, bf-failsafe |
| 15 | Предполётка и первое висение | поле | — | здесь |
| 16 | Первая настройка | поле | фильтры, PID, ползунки | bf-filters, bf-pid |
| 17 | Лог, `diff all`, восстановление | SITL + поле | Blackbox, CLI | bf-blackbox, bf-cli |

### Что умеет Betaflight SITL, а что нет
SITL — та же прошивка 4.5, собранная обычным gcc под Linux (`make TARGET=SITL`). Датчики виртуальные (`GYRO=VIRTUAL, ACC=VIRTUAL, BARO=VIRTUAL`), UART заменены TCP-портами `127.0.0.1:576x`: UART1 = 5761, UART2 = 5762. Конфиг хранится в `eeprom.bin` в текущей папке, а `save` и `exit` завершают процесс — его нужно запустить заново. С симулятором SITL общается по UDP: принимает состояние аппарата (FDM) на порт 9003 и RC-каналы на 9004, отдаёт моторы на 9002 (Gazebo) и 9001 (RealFlight). Без симулятора аппарат не летит, но CLI, режимы, блокировки арма, failsafe и `diff all` работают как на плате.

Чего в SITL нет: это видно в `src/main/target/SITL/target.h`, где отключены нужные `USE_*`, и в ответах CLI:
- **DShot.** Протокол по умолчанию `DISABLED`, поэтому висит флаг `MOTOR_PROTO`. В SITL ставят `PWM`, DShot-настроек (`dshot_idle_value`, `dshot_bidir`) в CLI нет.
- **Последовательный приёмник, ADC, OSD, VTX, GPS, Blackbox, `resource`.** На `get gps_provider` и `get blackbox_device` CLI отвечает `INVALID NAME`, на `resource` — `UNKNOWN COMMAND`.
- **Потеря связи.** Как только пришёл первый UDP-пакет RC, `rxRCFrameStatus()` в `sitl.c` всегда возвращает «кадр получен». Если остановить поток RC, флага `RXLOSS` не будет. Failsafe в SITL проверяют режимом FAILSAFE на тумблере.

### Датчики напряжения и тока: формулы из исходника
`src/main/sensors/voltage.c` (4.5) переводит отсчёт АЦП в напряжение (единица 0.01 В):

`V = ((ADC · vbat_scale · Vref_мВ / 10 + 0xFFF · 5) / (0xFFF · vbat_divider)) / vbat_multiplier`

Напряжение **прямо пропорционально** `vbat_scale` (по умолчанию 110, делитель 10, множитель 1 — это делитель 10 кОм : 1 кОм). Отсюда **new = old × V_мультиметр / V_FC**. Шаг в одну единицу — 0.9 %, на полной 6S-банке это ≈ 36 мВ на элемент. Критерий лабораторной (ошибка меньше 50 мВ на банку) достижим без дробных значений.

`src/main/sensors/current.c`: `centiAmps = (mV · 10000 / ibata_scale + ibata_offset) / 10`, то есть ток в мА равен `10000 · mV / ibata_scale + ibata_offset`. `ibata_scale` задан в мВ на 10 А (400 = 40 мВ/А, датчик ACS758), `ibata_offset` — в мА. Документация betaflight.com даёт те же единицы. Ток **обратно пропорционален** scale, поэтому **new = old × мА·ч_FC / мА·ч_зарядки**. Поправка смещения: **new_offset = old_offset + (I_амперметр − I_FC) × 1000**. Отрицательный `ibata_scale` (диапазон −16000…16000) нужен, если датчик стоит «задом наперёд» и показывает отрицательный ток.

мА·ч Betaflight интегрирует с момента подачи питания, а не с арма (`updateCurrentmAhDrawnState()` работает всегда). Включай аппарат от полностью заряженной банки и отключай сразу после посадки: тогда зарядное считает ровно то же, что и FC.

{{diagram:chart-bf-mah-calibration|Показание мА·ч обратно пропорционально ibata_scale: полёт, который при 400 дал 905 мА·ч против 1032 по зарядному, при 351 читается как 1031 — внутри полосы ±5 %.}}

### Моторы: порядок, направление, протокол
В миксере `QUADX` (`flight/mixer_init.c`) моторы идут так: 1 — задний правый, 2 — передний правый, 3 — задний левый, 4 — передний левый. При `yaw_motors_reversed = OFF` (props in) вращение такое: 1 — CW, 2 — CCW, 3 — CCW, 4 — CW, если смотреть сверху. `ON` (props out) меняет все четыре направления. Ошибку исправляют по-разному:
- **Порядок.** Самый простой способ — диалог Reorder motors на вкладке Motors. Он пишет массив `motor_output_reordering` (команда MSP `MSP2_SET_MOTOR_OUTPUT_REORDERING`). В драйвере мотор миксера `i` выводится на пад `resource MOTOR` с номером `motor_output_reordering[i] + 1`. По умолчанию массив `0,1,2,3,4,5,6,7`. Второй способ — переназначить пины командой `resource MOTOR n <pin>`: это уже ремаппинг таймеров и DMA, он разобран в bf-cli.
- **Направление.** В 4.5 **нет** параметра `motor_direction`: направление хранится в ESC. DShot-ESC (BLHeli_S, Bluejay, BLHeli_32, AM32) принимают команды `DSHOT_CMD_SPIN_DIRECTION_1` (7), `_2` (8) и `DSHOT_CMD_SAVE_SETTINGS` (12). Диалог Motor direction в Configurator шлёт именно 7 или 8, затем 12 (`MSP2_SEND_DSHOT_COMMAND`). Из CLI то же делает `dshotprog <индекс> <команды>`, где индекс с 0, а 255 — все моторы. FC сам повторяет команды направления и сохранения 10 раз, как требует спецификация DShot. Какое из направлений 1/2 окажется «нормальным», зависит от того, как распаяны фазы, поэтому после команды всегда проверяй глазами. Без DShot направление меняют в конфигураторе ESC или перекидкой двух фазных проводов.
- **Протокол.** DShot калибровать не нужно: газ передаётся числом 48…2047. Холостой ход — `dshot_idle_value` = 550 (5.5 %), то есть 48 + 0.055 · 1999 ≈ 158. PWM, OneShot и Multishot передают газ длительностью импульса, поэтому ESC надо один раз научить границам 1000 и 2000 мкс (`min_command` = 1000, `max_throttle` = 2000, холостой ход `min_throttle` = 1070).

### Газ висения: зачем знать заранее
Тяга примерно пропорциональна квадрату оборотов, а обороты — газу. Поэтому газ висения ≈ √(m / T_max). Для 5″ массой 650 г с моторами по 1600 г тяги (T/W ≈ 9.8) это √(650/6400) ≈ 0.32, то есть около 30 %. Реальные 5″ на 6S висят на 20–35 %. Это число нужно трижды: как критерий прерывания первого висения (газ выше 60 % — что-то не так), как `gps_rescue_throttle_hover` и как газ AUTO-LAND в failsafe (bf-failsafe).

## practice
### Шаг 1. Собрать SITL, подключить Configurator, сохранить исходный конфиг
Шаг 1 из 17. Сборка из ветки 4.5-maintenance (коммит 7dcc851, версия 4.5.6) на gcc 13.3 заняла около минуты:

```bash
git clone --depth 1 -b 4.5-maintenance https://github.com/betaflight/betaflight.git && cd betaflight
make arm_sdk_install        # Makefile проверяет arm-none-eabi-gcc даже для SITL
make TARGET=SITL            # -> obj/main/betaflight_SITL.elf
mkdir -p ~/bfsitl && cd ~/bfsitl && ~/betaflight/obj/main/betaflight_SITL.elf
```

Без ARM-тулчейна `make` останавливается с `arm-none-eabi-gcc not in the PATH`. Для SITL этот компилятор не используется, поэтому хватает фиктивного скрипта `arm-none-eabi-gcc` в PATH, который печатает `10.3.1`. Я собирал так:

```text
   text	   data	    bss	    dec	    hex	filename
 291764	  16456	  73832	 382052	  5d464	./obj/main/betaflight_SITL.elf
```

Официальный путь к Configurator — Betaflight App 2025.12 и новее (веб-версия) через websockify. Включи в Options «manual connection mode» и в поле порта впиши `ws://127.0.0.1:6761`:

```bash
pip3 install --user websockify
python3 -m websockify 127.0.0.1:6761 127.0.0.1:5761
```

Мост я проверил MSP-запросами через websocket: `MSP_API_VERSION` вернул 1.46, `MSP_FC_VARIANT` — `BTFL`. CLI доступен и без Configurator: отправь `#` в TCP 5761. Первым делом выполни `diff all` и сохрани результат. На реальной плате это бэкап старого конфига перед прошивкой.

### Шаг 2. Quad X, ориентация, порты
Шаги 2–3. В SITL `mixer` отвечает `Mixer: QUADX`, `align_board_yaw = 0`. Порты в SITL настраиваются только командой `serial` (функция 64 = Serial RX), но последовательного приёмника в сборке нет. Поэтому распределение UART для ELRS, GPS и VTX отрабатывай по таблице из bf-ports, а проверяй уже на плате.

### Шаг 3. Акселерометр
Шаг 9. Калибровка выполняется и в SITL, если подать в порт 9003 FDM-пакеты неподвижного аппарата (удельная сила в NED (0, 0, −g), кватернион w = 1) и отправить `MSP_ACC_CALIBRATION` (205). Я подал небольшой наклон (0.3; −0.2 м/с²), после калибровки `get acc_calibration` показал `-6,5,0,1`. Первые три числа — смещения, четвёртое (`calibrationCompleted` = 1) — признак выполненной калибровки. На плате то же делает кнопка Calibrate Accelerometer на ровном столе.

### Шаг 4. Расчёт калибровки АКБ
Шаг 10, расчётная часть. Измерения делаются на железе, но формулы проверяешь до этого. Пример: 6S 1300 мА·ч. Мультиметр на XT60 показал 24.42 В, FC — 24.04 В. На столе (моторы стоят, VTX 25 мВт) амперметр показал 0.42 А, FC — 0.19 А. После полёта с уже исправленным offset в OSD было 905 мА·ч, зарядное залило 1032 мА·ч.

```python
# Betaflight 4.5 battery-sensor calibration (formulas from sensors/voltage.c and sensors/current.c)
# V ~ vbat_scale (linear)      ->  new = old * V_meter / V_fc
# I = 10000*mV/ibata_scale + ibata_offset [mA]   ->  slope ~ 1/scale  ->  new = old * mAh_fc / mAh_charger
def vbat(old, v_meter, v_fc, cells):
    new = round(old * v_meter / v_fc)
    v_after = v_fc * new / old
    return new, v_after, abs(v_after - v_meter) / cells

def ibat_offset(old_offset_ma, i_meter_a, i_fc_a):
    return round(old_offset_ma + (i_meter_a - i_fc_a) * 1000)

def ibat_scale(old, mah_fc, mah_charger):
    new = round(old * mah_fc / mah_charger)
    return new, mah_fc * old / new

new, v_after, err = vbat(110, 24.42, 24.04, 6)
print(f"vbat_scale: 110 -> {new}; FC would show {v_after:.2f} V; error {err*1000:.0f} mV/cell")
print(f"one vbat_scale step = {100/new:.2f} % = {24.42/new/6*1000:.0f} mV/cell on a full 6S")
print(f"ibata_offset: 0 -> {ibat_offset(0, 0.42, 0.19)} mA")
new_i, mah_after = ibat_scale(400, 905, 1032)
print(f"ibata_scale: 400 -> {new_i}; same flight would read {mah_after:.0f} mAh "
      f"({(mah_after/1032-1)*100:+.1f} % vs charger)")
```

```text
vbat_scale: 110 -> 112; FC would show 24.48 V; error 10 mV/cell
one vbat_scale step = 0.89 % = 36 mV/cell on a full 6S
ibata_offset: 0 -> 230 mA
ibata_scale: 400 -> 351; same flight would read 1031 mAh (-0.1 % vs charger)
```

Строго говоря, offset тоже входит в мА·ч: 0.23 А за 6 минут от включения до отключения — это 23 мА·ч. Точная формула 400 × (905 − 23) / (1032 − 23) даёт 350 вместо 351, разница 0.3 %. Ток в полёте в десятки раз больше тока покоя, поэтому сначала выставляют offset, потом scale, а контрольный полёт проверяет обе поправки.

### Шаг 5. Режимы и арм
Шаг 11. Настройка с чистого `eeprom.bin` одним пакетом CLI: ARM на AUX1 (1700–2100), ANGLE на AUX2, режим FAILSAFE (id 27) на AUX3, протокол PWM (DShot в SITL нет). Реальный вывод, строки `Allowed …` убраны:

```text
# status
GYRO=VIRTUAL, ACC=VIRTUAL, BARO=VIRTUAL
Arming disable flags: RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
# mixer
Mixer: QUADX
# set motor_pwm_protocol = PWM
motor_pwm_protocol set to PWM
# aux 0 0 0 1700 2100 0 0
# aux 1 1 1 1300 2100 0 0
# aux 2 27 2 1700 2100 0 0
# set failsafe_switch_mode = STAGE2
failsafe_switch_mode set to STAGE2
# set craft_name = SCRATCH5
# save
Rebooting
SITL exit code after save: 0
```

Пять флагов блокировки — пять причин, по которым аппарат не армится: нет RC, неизвестен горизонт, не прошло время загрузки, открыт CLI, не выбран протокол моторов. Каждый следующий шаг снимает свой флаг.

### Шаг 6. Арм и failsafe по тумблеру
Шаг 12. Скрипт запускает SITL и делает три вещи: шлёт RC-пакеты (`double` timestamp + 16 × `uint16`) на UDP 9004, подаёт FDM неподвижного аппарата на 9003 и читает выходы моторов с 9002. Флаги арма он берёт из `MSP_STATUS_EX` (150) через TCP 5761:

```python
# Betaflight SITL: arming + failsafe check over MSP (TCP 5761) with RC over UDP 9004
import socket, struct, subprocess, threading, time, sys
NAMES=("NOGYRO FAILSAFE RXLOSS NOT_DISARMED BOXFAILSAFE RUNAWAY CRASH THROTTLE ANGLE BOOTGRACE NOPREARM LOAD "
       "CALIB CLI CMS BST MSP PARALYZE GPS RESCUE_SW DSHOT_TELEM REBOOT_REQD DSHOT_BBANG NO_ACC_CAL "
       "MOTOR_PROTO ARMSWITCH").split()   # fc/runtime_config.c, armingDisableFlagNames[]
sitl=subprocess.Popen([sys.argv[1]],cwd=sys.argv[2],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(2)
rc=[1500,1500,1000,1500]+[1000]*12   # AETR + AUX1..12, throttle low, arm switch low
sending=True; t0=time.time()
def rc_thread():
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    while True:
        if sending: u.sendto(struct.pack('<d16H',time.time()-t0,*rc),('127.0.0.1',9004))
        time.sleep(0.02)
threading.Thread(target=rc_thread,daemon=True).start()
def fdm_thread():  # stationary, level airframe on the ground: NED specific force (0,0,-g), quaternion w=1
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    while True:
        u.sendto(struct.pack('<d3d3d4d3d3dd',time.time()-t0,0,0,0,0,0,-9.80665,1,0,0,0,0,0,0,0,0,0,101325),('127.0.0.1',9003))
        time.sleep(0.002)
threading.Thread(target=fdm_thread,daemon=True).start()
motors=[0,0,0,0]
def pwm_thread():  # SITL sends motor outputs (0..1) to the simulator port 9002
    u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); u.bind(('127.0.0.1',9002))
    while True:
        d=u.recv(64); motors[:]=struct.unpack('<4f',d[:16])
threading.Thread(target=pwm_thread,daemon=True).start()
m=socket.create_connection(('127.0.0.1',5761)); m.settimeout(1)
def msp(cmd):
    m.sendall(b'$M<'+bytes([0,cmd,cmd])); buf=b''
    while True:
        buf+=m.recv(4096)
        while True:
            i=buf.find(b'$M>')
            if i<0 or len(buf)<i+6 or len(buf)<i+6+buf[i+3]: break
            n=buf[i+3]; c=buf[i+4]; payload=buf[i+5:i+5+n]; buf=buf[i+6+n:]
            if c==cmd: return payload
def status():
    p=msp(150); fm=struct.unpack_from('<I',p,6)[0]; bc=p[15]; o=16+bc
    flags=struct.unpack_from('<I',p,o+1)[0]
    return fm&1, [NAMES[b] for b in range(26) if flags>>b&1]
def show(tag): a,f=status(); print(f"t={time.time()-t0:5.1f}s {tag:34s} armed={a} motors={[round(x,3) for x in motors]} disable={f}")
time.sleep(1); show("boot: RC + FDM, arm switch low")
time.sleep(3); show("after gyro calibration")
rc[2]=1300; rc[4]=1800; time.sleep(0.5); show("arm attempt, throttle 1300")
rc[4]=1000; rc[2]=1000; time.sleep(0.3); rc[4]=1800; time.sleep(0.5); show("arm, throttle 1000 (idle)")
rc[2]=1400; time.sleep(0.5); show("throttle 1400")
rc[6]=1800; time.sleep(0.1); show("FAILSAFE switch on, 0.1 s")
time.sleep(1.0); show("FAILSAFE switch on, 1.1 s")
rc[6]=1000; rc[2]=1000; time.sleep(0.5); show("switch off, arm switch still high")
rc[4]=1000; time.sleep(0.5); show("arm switch low")
rc[4]=1800; time.sleep(0.5); show("re-arm")
sitl.terminate()
```

```text
t=  1.0s boot: RC + FDM, arm switch low     armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['BOOTGRACE']
t=  4.0s after gyro calibration             armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=[]
t=  4.5s arm attempt, throttle 1300         armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['THROTTLE', 'ARMSWITCH']
t=  5.4s arm, throttle 1000 (idle)          armed=1 motors=[0.07, 0.07, 0.07, 0.07] disable=[]
t=  5.9s throttle 1400                      armed=1 motors=[0.412, 0.412, 0.412, 0.412] disable=[]
t=  6.0s FAILSAFE switch on, 0.1 s          armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['FAILSAFE', 'RXLOSS', 'BOXFAILSAFE', 'ARMSWITCH']
t=  7.0s FAILSAFE switch on, 1.1 s          armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['FAILSAFE', 'RXLOSS', 'BOXFAILSAFE', 'ARMSWITCH']
t=  7.5s switch off, arm switch still high  armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=['ARMSWITCH']
t=  8.1s arm switch low                     armed=0 motors=[0.0, 0.0, 0.0, 0.0] disable=[]
t=  8.6s re-arm                             armed=1 motors=[0.07, 0.07, 0.07, 0.07] disable=[]
```

Что видно в выводе:
- Без FDM висит флаг `ANGLE`: горизонт не оценён. С FDM он пропадает, `BOOTGRACE` уходит через 3–4 с.
- Газ 1300 при арме даёт `THROTTLE`: армить можно только при газе ниже `min_check` (1050).
- Холостой ход 0.07 — это `min_throttle` 1070 в шкале 1000–2000. При газе 1400 выход 0.412 = 0.07 + 0.93 × (1400 − 1050) / (2000 − 1050).
- С `failsafe_switch_mode = STAGE2` тумблер сразу запускает Stage 2. Процедура по умолчанию `DROP`, поэтому через 0.1 с арм снят. Флаг `ARMSWITCH` не даёт переармиться, пока тумблер арма не опущен. Это защита от случайного рестарта моторов после восстановления связи.

### Шаг 7. Первая настройка и бэкап
Шаги 16–17. Фильтры и PID 4.5 по умолчанию годятся для первого висения. Без физической модели SITL их не проверит, они настраиваются по логу (bf-filters, bf-pid). `diff all` из SITL содержит только то, что ты изменил:

```text
# name: SCRATCH5
feature -GPS
feature -TELEMETRY
aux 0 0 0 1700 2100 0 0
aux 1 1 1 1300 2100 0 0
aux 2 27 2 1700 2100 0 0
set motor_pwm_protocol = PWM
set failsafe_switch_mode = STAGE2
set craft_name = SCRATCH5
```

Проверка восстановления: удали `eeprom.bin`, вставь diff в CLI нового SITL (`batch start`, `defaults nosave`, команды, `save`) и снова сделай `diff all`. У меня строки `set`/`aux`/`feature` совпали полностью. Именно так ты восстановишь аппарат после перепрошивки.

### Переход на реальное железо
Пропы сняты до пункта 13. Первое включение после пайки — через smoke stopper. Перед подключением АКБ мультиметр между + и − должен показывать не меньше сотен Ом.

**1. Прошивка (шаг 1).** `diff all` старой прошивки — в файл. В Configurator: target платы, Cloud Build с опциями под этот аппарат (CRSF, DShot, OSD SD или HD, GPS, протокол VTX), Full chip erase (bf-intro).

**2. Ориентация и порты (шаги 2–3).** На вкладке Setup наклони аппарат: модель должна повторять движение. Если плата повёрнута, выставь `align_board_yaw`. На Ports: UART приёмника → Serial RX; GPS (если есть) → GPS; VTX → Peripherals: SmartAudio или Tramp для аналога, MSP + `osd_displayport_device = MSP` для HD (bf-ports, link-vtx).

**3. Приёмник и каналы (шаги 4–5).** Receiver: Serial, `serialrx_provider = CRSF`. Bind ELRS — binding phrase, версии 3.x на TX и RX совпадают (link-elrs). Пульт: `map AETR1234`. CRSF в Betaflight даёт 988–2012 мкс (`rx/crsf.c`: 172 → 988, 1811 → 2012). Заполни таблицу каналов:

| Проверка | Норма |
|---|---|
| Крен вправо / тангаж вперёд / газ вверх / рыскание вправо | соответствующий канал растёт |
| Центр крена, тангажа, рыскания | 1500 ± 5 |
| Газ внизу | ниже `min_check` = 1050 (иначе флаг `THROTTLE`) |
| Газ вверху | выше `max_check` = 1900 |
| Тумблеры AUX | каждое положение не ближе 50 мкс к границе диапазона режима |

**4. Протокол (шаг 6).** `motor_pwm_protocol = DSHOT600` или `DSHOT300` (выбор по частоте PID — f-motors-esc). Для Bluejay, BLHeli_32 и AM32: `dshot_bidir = ON`, `motor_poles = 14` — это основа RPM-фильтра. В Motors проверь, что у всех четырёх моторов нет ошибок телеметрии.

**5. Порядок и направление (шаг 7).** Подключи АКБ, вкладка Motors → «I understand the risks». По очереди подними каждый ползунок до ~1100 и отметь, какой мотор крутится и в какую сторону (полоска скотча на колоколе). Пример: ползунок 1 крутит передний правый, ползунок 2 — задний правый, 3 и 4 на месте. Значит, пад M2 подключён к заднему правому, а M1 — к переднему правому: `set motor_output_reordering = 1,0,2,3,4,5,6,7` или диалог Reorder motors. Если мотор 3 крутится CW вместо CCW: диалог Motor direction или в CLI `dshotprog 2 8 12`. Если стало хуже — `dshotprog 2 7 12`. Повтори проверку всех четырёх и сохрани (`save`).

**6. Калибровка ESC (шаг 8, только PWM/OneShot/Multishot).** АКБ отключена, тест моторов включён, мастер-ползунок на 2000. Подключи АКБ. После сигнала «максимум» опусти ползунок на 1000, дождись подтверждения и отключи АКБ. Проверка: все моторы трогаются с одного значения ползунка (разница ≤ 10 мкс). DShot-ESC не калибруют.

**7. Акселерометр (шаг 9).** Calibrate Accelerometer на ровном столе. Флаг `ANGLE` исчезает в `status`, когда аппарат стоит ровно.

**8. Напряжение и ток (шаг 10).** Power & Battery: `battery_meter = ADC`, `current_meter = ADC`, `bat_capacity = 1300`. Напряжение — мультиметр на XT60, FC — строка `Voltage:` в `status`. Посчитай `vbat_scale` по шагу 4 и повтори проверку на банке в storage (≈ 3.85 В на элемент): ошибка меньше 50 мВ на банку в обеих точках. Ток покоя — амперметр последовательно с АКБ (диапазон 10 А) → `ibata_offset`. Затем полёт с расходом 50–70 % ёмкости (650–900 мА·ч), отключить АКБ сразу после посадки, зарядить с балансировкой до конца → `ibata_scale` по мА·ч. Контрольный полёт: расхождение с зарядным меньше 5 %.

**9. Режимы (шаг 11).** Вставь `aux` из SITL, на вкладке Modes проверь, что тумблеры подсвечивают ARM, ANGLE и FAILSAFE. Для 5″ полезны BEEPER и FLIP OVER AFTER CRASH (bf-modes-osd).

**10. Failsafe на столе (шаг 12).** Пропы сняты, АКБ подключена. Заармь и выключи TX-модуль в меню пульта. Сначала держится Stage 1 (`failsafe_delay` = 15, 1.5 с), затем Stage 2: при `DROP` арм снимается, в OSD — `FAILSAFE`. Повтори тест тумблером. Запиши Stage 2 на видео OSD или в Blackbox (bf-failsafe).

**11. OSD и видео (шаг 13).** Минимум элементов: среднее напряжение на банку, мА·ч, LQ/RSSI, режим, таймер, предупреждения. VTX на столе — 25 мВт и только с антенной (link-vtx).

**12. GPS Rescue, если стоит GPS (шаг 14).** `gps_provider = UBLOX`, 5 Гц и выше. Значения по умолчанию в 4.5 (`pg/gps_rescue.c`): `gps_rescue_min_sats` = 8 (документация советует 10), `gps_rescue_min_start_dist` = 15 м, `gps_rescue_alt_mode = MAX_ALT`, `gps_rescue_initial_climb` = 10 м, `gps_rescue_return_alt` = 30 м, `gps_rescue_ground_speed` = 750 см/с, `gps_rescue_throttle_hover` = 1275, `gps_rescue_sanity_checks = RESCUE_SANITY_FS_ONLY`, `gps_rescue_allow_arming_without_fix = OFF`. Без подтверждённой точки дома не армить: при реальном failsafe аппарат упадёт. `failsafe_procedure = GPS-RESCUE` включай только после пункта 13, когда `gps_rescue_throttle_hover` взят из лога. Первые тесты — тумблером с `failsafe_switch_mode = STAGE1` над травой, на 30–50 м.

**13. Предполётка и первое висение (шаг 15) — пропы ставятся здесь.** Перед вылетом:
- пропы стоят по схеме props in и затянуты;
- АКБ на ремне, антенны далеко от пропов;
- `status` без флагов, кроме `ARMSWITCH`;
- в OSD напряжение 4.15–4.20 В на банку;
- Blackbox стёрт, режим ANGLE.

Площадка: трава, 10 × 10 м свободно, люди не ближе 10 м, пилот в 5 м позади аппарата. Первый раз лети в прямой видимости, без очков. Арм → плавно газ до отрыва → висение на 1–1.5 м 60 с → посадка → дизарм. **Немедленный дизарм**, если при отрыве аппарат кренится или крутится на месте: это порядок или направление моторов, а не PID. Сажай и разбирайся, если:
- слышно или видно осцилляции;
- газ висения выше 60 % или ниже 12 %;
- в ANGLE без стиков аппарат сносит больше 1 м за 5 с в штиль (подтримь акселерометр);
- под нагрузкой напряжение ниже 3.5 В на банку;
- LQ упал или пропало видео;
- после 60 с мотор горячий: палец не держится 5 с.

Запиши газ висения: `rcCommand[3]` в Blackbox Explorer, медиана за 60 с. Это значение идёт в `gps_rescue_throttle_hover`.

**14. Первая настройка и бэкап (шаги 16–17).** Спектр гироскопа из лога висения → фильтры и RPM-фильтр (bf-filters, bf-rpm-filter). Затем ползунки PID (bf-pid). После каждого изменения — `diff all` с датой и версией в файле и в git.

Лабораторная засчитывается, когда:
- **SITL**: собран Betaflight 4.5 SITL. Сдан `diff all` с `aux` для ARM, ANGLE и FAILSAFE и `failsafe_switch_mode`. Лог скрипта показывает арм, блокировку `THROTTLE`, срабатывание `FAILSAFE`/`BOXFAILSAFE` и блокировку `ARMSWITCH` после failsafe. Восстановление diff в чистый SITL проверено. Расчёт `vbat_scale`, `ibata_offset` и `ibata_scale` выполнен по формулам из исходника.
- **Железо**: таблица каналов заполнена, порядок и направление моторов соответствуют `QUADX`, для PWM-ESC выполнена калибровка. Ошибка напряжения меньше 0.05 В на банку в двух точках, мА·ч FC в пределах 5 % от зарядного. Stage 2 failsafe записан. Сдан Blackbox 60-секундного висения с газом висения в отчёте и `diff all` с реального аппарата.

## diagnostics
- **Симптом:** `make TARGET=SITL` останавливается с `arm-none-eabi-gcc not in the PATH`
  - Возможная причина: `mk/tools.mk` проверяет ARM-тулчейн для любого target.
  - Что сделать: `make arm_sdk_install` или фиктивный скрипт `arm-none-eabi-gcc` в PATH, печатающий требуемую версию (10.3.1).
- **Симптом:** Configurator или CLI видят не Betaflight, а INAV (`MSP_FC_VARIANT` = `INAV`)
  - Возможная причина: на той же машине запущен INAV SITL, он занимает те же TCP 5760–5761.
  - Что сделать: закрыть его или запустить Betaflight SITL в отдельном сетевом пространстве (`unshare -n`, поднять `lo`).
- **Симптом:** в SITL арм не проходит с флагом `ANGLE`
  - Возможная причина: нет FDM-данных, горизонт не оценён (`isUpright()` требует `attitudeIsEstablished`).
  - Что сделать: подавать FDM неподвижного аппарата на UDP 9003 или подключить симулятор.
- **Симптом:** RC-поток остановлен, а `RXLOSS` не появляется
  - Возможная причина: в SITL статус кадра всегда «получен» после первого пакета.
  - Что сделать: проверять failsafe режимом FAILSAFE на тумблере, потерю связи — только на железе.
- **Симптом:** при первом отрыве аппарат переворачивается или крутится на месте
  - Возможная причина: моторы не в порядке `QUADX`, неверное направление или `yaw_motors_reversed` не совпадает с пропами.
  - Что сделать: снять пропы, тест на вкладке Motors, `motor_output_reordering`, `dshotprog`/Motor direction.
  - Последствия: сломанные пропы, рама, иногда ESC; на столе это ловится за 5 минут.
- **Симптом:** после `dshotprog` направление не изменилось
  - Возможная причина: протокол не DShot, аппарат заармлен или не отправлена команда 12.
  - Что сделать: DShot, дизарм, `dshotprog <i> 8 12`, переподключить АКБ и проверить.
- **Симптом:** напряжение в OSD отличается от мультиметра на 0.3–1 В
  - Возможная причина: `vbat_scale` от другой платы или исправлен не в ту сторону.
  - Что сделать: new = old × V_мультиметр / V_FC; при увеличении scale показание растёт.
- **Симптом:** мА·ч в OSD на 10–30 % меньше, чем заливает зарядное
  - Возможная причина: `ibata_scale` завышен (ток обратно пропорционален scale).
  - Что сделать: new = old × мА·ч_FC / мА·ч_зарядки, контрольный полёт.
- **Симптом:** PWM-ESC: один мотор стартует позже остальных
  - Возможная причина: ESC не откалиброваны по 1000/2000 мкс.
  - Что сделать: калибровка мастер-ползунком без пропов; перейти на DShot, если ESC поддерживает.
- **Симптом:** после реального failsafe GPS Rescue снимает арм и аппарат падает
  - Возможная причина: не было точки дома, мало спутников или `gps_rescue_throttle_hover` слишком мал.
  - Что сделать: армить только с домом, газ висения из лога, тесты тумблером с `STAGE1` на малой дистанции.

## checklist
- SITL собран, исходный `diff all` сохранён
- Quad X, ориентация, порты и каналы проверены, таблица каналов заполнена
- Протокол DShot, порядок и направление моторов проверены без пропов; PWM-ESC откалиброваны
- `vbat_scale`, `ibata_offset`, `ibata_scale` рассчитаны и проверены мультиметром и зарядным
- ARM, ANGLE, FAILSAFE на тумблерах; failsafe проверен в SITL и на столе
- OSD показывает напряжение на банку, мА·ч, LQ; GPS Rescue настроен, если есть GPS
- Первое висение 60 с с Blackbox, газ висения записан
- `diff all` с реального аппарата и лог сохранены, восстановление проверено

## references
- Betaflight voltage.c (формула vbat_scale), ветка 4.5-maintenance | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/voltage.c | primary | A
- Betaflight current.c (формула ibata_scale, ibata_offset) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/current.c | primary | A
- Betaflight dshot_command.h (команды DShot 7, 8, 12, 20, 21) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/drivers/dshot_command.h | primary | A
- Betaflight SITL README | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/target/SITL/README.md | primary | A
- Betaflight SITL (сборка, websockify, Betaflight App) | https://betaflight.com/docs/development/SITL | primary | A
- Betaflight Power & Battery tab | https://betaflight.com/docs/wiki/configurator/power-tab | primary | A
- Betaflight Battery (единицы amperage_meter_scale, offset) | https://betaflight.com/docs/development/Battery | primary | A
- Betaflight Motors tab | https://betaflight.com/docs/wiki/configurator/motors-tab | primary | A
- Betaflight GPS Rescue 4.5 | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight Configurator: диалог Motor direction (команды 7/8 + 12) | https://github.com/betaflight/betaflight-configurator/blob/master/src/composables/motors/escDshotDirection/EscDshotDirectionMotorDriver.ts | primary | A

## notes
GPS Rescue: страница документации 4.5 называет минимальную дистанцию запуска 30 м, а `pg/gps_rescue.c` в ветке 4.5-maintenance задаёт `minStartDistM = 15` (диапазон 10–30). Верь исходнику своей прошивки: `get gps_rescue_min_start_dist`.
