---
id: px4-control
title: "Контуры управления и тюнинг PX4"
level: L3
readingTime: 25 мин
firmware: PX4 1.14+
status: published
added: 2026-03-21
tags:
  - PID
  - autotune
  - control allocation
related:
  - px4-architecture
  - bf-pid
next:
  - px4-ros2
---

## summary
Управление мультиротором в PX4 — каскад из трёх контуров: позиция → ориентация → угловая скорость, плюс распределение моментов по моторам. Модуль объясняет, какой параметр за какой контур отвечает, в чём разница форм rate-регулятора (K-множитель против обычного P), как выглядит процедура ручного тюнинга по step response и почему для большинства рам правильный ответ — autotune. Для перешедших с Betaflight — таблица соответствий.

## theory
### Каскад
1. **Position controller** (`MPC_*`): из ошибки позиции — желаемая скорость (`MPC_XY_P`, `MPC_Z_P`), из ошибки скорости — желаемое ускорение/наклон (`MPC_XY_VEL_P_ACC` и др.). Здесь же газ висения `MPC_THR_HOVER` и ограничения скоростей `MPC_XY_VEL_MAX`, `MPC_Z_VEL_MAX_UP/DN`.
2. **Attitude controller** (`MC_ROLL_P`, `MC_PITCH_P`, `MC_YAW_P`): из ошибки угла — желаемая угловая скорость. Только P.
3. **Rate controller** (`MC_ROLLRATE_P/I/D/K`, то же для PITCH и YAW, плюс `MC_*RATE_FF`): из ошибки угловой скорости — момент. Самый быстрый контур, он определяет «ощущение» аппарата.
4. **Control allocation**: моменты и тяга → команды моторам по геометрии `CA_AIRFRAME`, `CA_ROTOR_COUNT`, `CA_ROTOR<n>_PX/PY/KM`.

### Форма rate-регулятора
PX4 использует параллельную форму с общим множителем K: выход = K × (P·e + I·∫e + D·de/dt). `MC_ROLLRATE_K` масштабирует все три сразу, поэтому первый шаг грубого тюнинга — K, а не P. У Betaflight такого множителя нет; его роль в слайдерах играет Master Multiplier.

### Соответствия с Betaflight
| Betaflight | PX4 |
|---|---|
| P/I/D roll (rate) | `MC_ROLLRATE_P/I/D` (× `MC_ROLLRATE_K`) |
| Feedforward | `MC_ROLLRATE_FF` |
| Angle mode strength | `MC_ROLL_P` |
| Фильтры гиро | `IMU_GYRO_CUTOFF`, `IMU_DGYRO_CUTOFF`, notch `IMU_GYRO_NF*_FRQ` |
| Throttle hover / air mode | `MPC_THR_HOVER`, `MC_AIRMODE` |

### Autotune
Для большинства рам документация прямо рекомендует autotune: быстрее и обычно даёт хороший результат. Он идентифицирует модель по откликам в висении и применяет найденные rate-гейны; применение управляется `MC_AT_APPLY` (сразу, после посадки или вручную). Ручной тюнинг — когда autotune не справляется: нестандартные рамы, сильные вибрации, большие аппараты.

### Ручной тюнинг по step response
Порядок: фильтры → rate (K, затем D, затем I) → attitude P → position. Шаг: Acro или Stabilized, резкие короткие движения стиком, лог, график `vehicle_rates_setpoint` против `vehicle_angular_velocity` в Flight Review. Перелёт — меньше K или больше D; медленный отклик — больше K; дрейф — больше I. Тот же метод и те же метрики, что в модуле про PID по данным.

## practice
### Шаг 1. Сначала аллокация
Без пропов: Actuators в QGC — геометрия соответствует раме, каждый мотор крутится в нужную сторону по тесту.

### Шаг 2. Фильтры по логу
Полёт с логом, Flight Review → спектрограмма гироскопа. `IMU_GYRO_CUTOFF` и `IMU_DGYRO_CUTOFF` — так, чтобы срезать шум моторов, не задевая управление.

### Шаг 3. Autotune
QGC → PID Tuning → Autotune, или тумблер на функцию autotune. Висение, запуск, не трогать стики до завершения, посадка. Проверить, что новые `MC_*RATE_*` применены.

### Шаг 4. Проверка
Step response в Flight Review до и после: перелёт и время установления. При необходимости — ручная подстройка K/D на 10–20%.

### Лабораторная
В SITL: записать step response на дефолтных гейнах, намеренно удвоить `MC_ROLLRATE_K`, записать снова, объяснить разницу по графику.

## diagnostics
- **Симптом:** быстрые осцилляции после autotune
  - Возможная причина: шум не отфильтрован, autotune подобрал гейны под шумный сигнал.
  - Что сделать: фильтры, повторный autotune.
- **Симптом:** в Position аппарат медленно «качается»
  - Возможная причина: внешний контур (`MPC_*`) слишком агрессивен при слабом внутреннем.
  - Что сделать: сначала rate/attitude, потом position.
- **Симптом:** горячие моторы
  - Возможная причина: высокий D на шумном гироскопе.
  - Что сделать: снизить D, поднять фильтрацию, проверить механику.
- **Симптом:** мотор крутится не туда в тесте
  - Возможная причина: геометрия или направление в Actuators.
  - Что сделать: исправить `CA_ROTOR<n>_KM`/направление, перепроверить без пропов.

## references
- PX4 Multicopter PID Tuning Guide (Advanced) | https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter.html | primary | A
- PX4 Multicopter PID Tuning Guide (Basic) | https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter_basic.html | primary | A
- PX4 Autotuning (Multicopter) | https://docs.px4.io/main/en/config/autotune_mc.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/main/en/concept/control_allocation.html | primary | A

## checklist
- Понимаю каскад position → attitude → rate → allocation
- Знаю роль `MC_*RATE_K` и чем это отличается от Betaflight
- Аллокация проверена без пропов
- Autotune выполнен, результат проверен по step response
