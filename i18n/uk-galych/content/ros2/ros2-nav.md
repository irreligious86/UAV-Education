---
id: ros2-nav
title: "Навігація й обхід перешкод: карти, планувальники, уставки"
level: L3
readingTime: 45 хв
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - навігація
  - планування
  - A*
  - обхід перешкод
  - Nav2
related:
  - ros2-app-arch
  - mav-component
  - per-visual-nav
next:
  - ros2-from-ros1
source: content/ros2/ros2-nav.md
source_hash: 5e677a226b42
---

## summary
Автопілот уміє летіти в точку. Аби летіти в точку **і ні в що не врізатися**, треба карту, планувальник і ланцюжок від плану до уставок — і чесно розуміти, що з того автопілот уже вміє сам (ArduPilot: BendyRuler і Dijkstra, PX4: collision prevention), а де треба власної логіки на companion. Модуль розбирає представлення карти (сітка зайнятості, вартість, 3D-вокселі), глобальне й локальне планування (A*, Dijkstra, реактивні методи), роздування перешкод і згладжування шляху, роль Nav2 і чому він «наземний», і як план перетворюється на уставки GUIDED/Offboard з обмеженнями швидкості й висоти. Лабораторна: A* на сітці з тестами, а відтак обліт перешкоди в Gazebo за даними лідара.

## theory
### Що вміє автопілот без тебе
- **ArduPilot**: proximity-датчики (`PRX1_TYPE`, зокрема MAVLink `OBSTACLE_DISTANCE`) → **simple avoidance** (зупинка/ковзання в Loiter, `AVOID_ENABLE`, `AVOID_MARGIN`) і **object avoidance** в автоматичних режимах: `OA_TYPE = 1` BendyRuler (реактивний, шукає обхідний напрямок), `2` Dijkstra (за геозонами-полігонами, глобальний шлях довкола відомих заборонених зон), `3` комбінація. Параметри `OA_MARGIN_MAX`, `OA_BR_LOOKAHEAD`.
- **PX4**: **collision prevention** у Position-режимі (`CP_DIST` — мінімальна дистанція, за `OBSTACLE_DISTANCE`/ROS 2 `ObstacleDistance`), обмежує швидкість у бік перешкоди.

То працює і перевірене в польоті — з того й починай. Власна навігація на companion треба тоді, коли: карту мусиш будувати й зберігати (політ у приміщенні, ліс), шлях — глобально оптимальний у невідомому середовищі, або є ціль вищого рівня (обстежити об'єкт, долетіти до точки, яку знайшла камера).

### Представлення карти
- **Сітка зайнятості (occupancy grid)** 2D: комірка — імовірність зайнятості (у ROS `nav_msgs/OccupancyGrid`: 0–100, −1 — невідомо). Оновлюється за променями далекоміра/лідара: уздовж променя — вільно, на кінці — зайнято (log-odds, аби накопичувати свідчення).
- **Карта вартості (costmap)**: зайнятість + роздування (inflation) + шари (статичний, перешкоди, геозони). Роздування на радіус апарата плюс запас дає змогу планувати для точки, а не для тіла.
- **3D**: OctoMap (октодерево вокселів), ESDF/TSDF (поле відстаней до найближчої перешкоди: Voxblox, nvblox). Для польоту на різних висотах 2D-сітки замало, але 2D на сталій висоті — файний старт.
- **Невідоме = зайняте** за замовчуванням: летіти лиш туди, де вже бачили, що вільно. Бо інакше планувальник прокладе шлях «крізь стіну», якої ще ніхто не бачив.

### Глобальне планування
**A\*** по сітці: пошук найкоротшого шляху від старту до цілі з евристикою (оцінкою відстані, що лишилася). Як евристика не переоцінює (допустима) — шлях оптимальний. Для 8-зв'язної сітки — октильна дистанція `(dx + dy) + (√2 − 2)·min(dx, dy)`. Заборона «зрізати кут» між двома зайнятими клітинками по діагоналі. **Dijkstra** — то A* з нульовою евристикою (повільніше, але рішення те саме). Для великих 3D-просторів — вибіркові методи (RRT*, PRM).

Сирий шлях A* — «драбинка» по клітинках. **Згладжування** (shortcut): викидати проміжні точки, доки прямий відрізок вільний; потім — обмеження динаміки (швидкість, прискорення, ривок), коли будуєш траєкторію.

### Локальне планування й реакція
Глобальний план будується за картою, яка на момент польоту вже застаріла. Локальний рівень реагує на те, що видно зараз: векторні поля (VFH), динамічне вікно (DWA), MPC або просто «стати й перепланувати». Частоти: глобальний — 0.5–2 Гц, локальний — 10–20 Гц, уставки — 20–50 Гц. Шари мусять бути окремими вузлами (модуль ros2-app-arch), а останній рубіж — автопілот (simple avoidance / collision prevention) і геозона.

{{diagram:planning-layers|Шари навігації та їхні частоти; останній рубіж — автопілот.}}

### Nav2 і дрони
Nav2 — стек навігації ROS 2: BT-навігатор (дерева поведінки), планувальники (NavFn, Smac), контролери (DWB, MPPI), costmap-шари, recovery. Він зроблений під наземних роботів (2D, неголономні моделі). Для мультикоптера на сталій висоті його можна вживати (голономна модель, `cmd_vel` → швидкості GUIDED/Offboard), але 3D-планування, урахування висоти й динаміки польоту — то вже поза його межами. Багато дронових проєктів беруть із Nav2 costmap-шари та ідеї BT, а планувальник пишуть власний або беруть із дослідницьких стеків (приміром, EGO-Planner, Fast-Planner — для досвідчених).

### Від плану до уставок
1. Шлях у фреймі `map` (ENU) → проміжні точки з кроком 1–3 м.
2. Обмеження: максимальна швидкість біля перешкод (залежить від дальності датчика й гальмівного шляху: v ≤ √(2·a·d)), висота в коридорі (над землею за далекоміром і нижче геозони), рискання — за напрямком руху, як камера мусить дивитися вперед.
3. Надсилання: PX4 — `TrajectorySetpoint` (позиція та/або швидкість, NED — конвертувати!), ArduPilot — `/ap/cmd_vel` (ENU, frame `map`) або позиційні цілі через MAVROS.
4. Контроль виконання: відхилення від шляху > порога → зупинка й перепланування; ціль недосяжна → утримання й повідомлення операторові.

## practice
### Крок 1. A* з тестами
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_grid_planner.py
```
Прочитай `grid_planner.py`: роздування, октильна евристика, заборона зрізання кутів, shortcut. Допиши тест: шлях із роздуванням довший за шлях без нього, але не коротший за пряму.

### Крок 2. Гальмівний шлях
Для апарата з максимальним уповільненням 3 м/с² і лідаром із надійною дальністю 8 м порахуй максимальну безпечну швидкість із запасом 2 м і затримкою реакції 0.3 с. Порівняй з параметрами simple avoidance своєї прошивки.

```python
"""ros2-nav lab: Dijkstra vs A* vs weighted A*, inflation, shortcut, unknown cells, log-odds.
Run from examples/ros2-docker/ws/src/uav_ros2_labs:  python3 nav_lab.py"""
import heapq, math, random, sys
sys.path.insert(0, ".")
from uav_ros2_labs.grid_planner import inflate, line_free, path_length, shortcut


def search(grid, s, g, w):
    """8-connected grid search; w = heuristic weight (0 Dijkstra, 1 A*, >1 weighted A*)."""
    def h(c):
        dx, dy = abs(c[0] - g[0]), abs(c[1] - g[1])
        return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)
    free = lambda c: 0 <= c[0] < len(grid[0]) and 0 <= c[1] < len(grid) and grid[c[1]][c[0]] == 0
    openq, best, parent, closed = [(w * h(s), 0.0, s)], {s: 0.0}, {}, set()
    while openq:
        _, gc, c = heapq.heappop(openq)
        if c in closed:
            continue
        closed.add(c)
        if c == g:
            p = [c]
            while c in parent:
                c = parent[c]; p.append(c)
            return p[::-1], len(closed)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (c[0] + dx, c[1] + dy)
                if (dx, dy) == (0, 0) or not free(n):
                    continue
                if dx and dy and not (free((c[0] + dx, c[1])) and free((c[0], c[1] + dy))):
                    continue
                ng = gc + math.hypot(dx, dy)
                if ng < best.get(n, math.inf):
                    best[n], parent[n] = ng, c
                    heapq.heappush(openq, (ng + w * h(n), ng, n))
    return None, len(closed)


W, H = 60, 40                          # 0.5 m cells -> 30 x 20 m
grid = [[0] * W for _ in range(H)]
for y in range(0, 30):                 # wall from the bottom edge, gap at the top
    grid[y][30] = 1
S, G = (5, 5), (55, 5)
print("1) search on the raw grid, 0.5 m cells")
for name, w in (("Dijkstra  w=0  ", 0), ("A*        w=1  ", 1), ("weighted  w=2  ", 2)):
    p, n = search(grid, S, G, w)
    print(f"   {name} expanded {n:5d} cells, path {path_length(p) * 0.5:6.2f} m")

forest = random.Random(1)                                # 25 % random obstacles, seed 1
fg = [[1 if forest.random() < 0.25 else 0 for _ in range(W)] for _ in range(H)]
fg[5][5] = fg[35][55] = 0
print("   'forest' 60x40, 25 % occupied, (5,5) -> (55,35):")
for name, w in (("Dijkstra  w=0  ", 0), ("A*        w=1  ", 1), ("weighted  w=2  ", 2)):
    p, n = search(fg, (5, 5), (55, 35), w)
    print(f"   {name} expanded {n:5d} cells, path {path_length(p) * 0.5:6.2f} m")

print("2) inflation for a 0.6 m radius + 0.4 m margin = 2 cells")
gi = inflate(grid, 2)
p0, _ = search(grid, S, G, 1)
p1, _ = search(gi, S, G, 1)
s1 = shortcut(gi, p1)
print(f"   raw {path_length(p0) * 0.5:.2f} m, inflated {path_length(p1) * 0.5:.2f} m, "
      f"inflated+shortcut {path_length(s1) * 0.5:.2f} m in {len(s1) - 1} segments, straight {math.dist(S, G) * 0.5:.2f} m")
print(f"   shortcut stays free: {all(line_free(gi, a, b) for a, b in zip(s1, s1[1:]))}")

print("3) unseen cells: the gap at the top was never observed (-1)")
gu = [row[:] for row in grid]
for y in range(30, 40):
    gu[y][30] = -1
blocked = [[0 if v == 0 else 1 for v in row] for row in gu]       # unknown = occupied
optim = [[0 if v in (0, -1) else 1 for v in row] for row in gu]   # unknown = free
print(f"   unknown=occupied: path {'found' if search(blocked, S, G, 1)[0] else 'none -> hold and explore'}")
po, _ = search(optim, S, G, 1)
thru = [c for c in po if gu[c[1]][c[0]] == -1]
print(f"   unknown=free: path {path_length(po) * 0.5:.2f} m, crosses {len(thru)} unseen cells at x=30, y={thru[0][1]}..{thru[-1][1]}")

print("4) log-odds occupancy: p_hit = 0.7, p_miss = 0.4 per beam")
l_hit, l_miss = math.log(0.7 / 0.3), math.log(0.4 / 0.6)
l = 0.0
for k, z in enumerate("HHHMM", 1):
    l += l_hit if z == "H" else l_miss
    print(f"   beam {k} {'hit ' if z == 'H' else 'miss'}  L = {l:+.3f}  p = {1 - 1 / (1 + math.exp(l)):.3f}")
```

```text
1) search on the raw grid, 0.5 m cells
   Dijkstra  w=0   expanded  2290 cells, path  35.94 m
   A*        w=1   expanded   785 cells, path  35.94 m
   weighted  w=2   expanded   537 cells, path  35.94 m
   'forest' 60x40, 25 % occupied, (5,5) -> (55,35):
   Dijkstra  w=0   expanded  1778 cells, path  33.56 m
   A*        w=1   expanded   462 cells, path  33.56 m
   weighted  w=2   expanded    86 cells, path  37.85 m
2) inflation for a 0.6 m radius + 0.4 m margin = 2 cells
   raw 35.94 m, inflated 37.94 m, inflated+shortcut 36.80 m in 2 segments, straight 25.00 m
   shortcut stays free: True
3) unseen cells: the gap at the top was never observed (-1)
   unknown=occupied: path none -> hold and explore
   unknown=free: path 35.94 m, crosses 1 unseen cells at x=30, y=30..30
4) log-odds occupancy: p_hit = 0.7, p_miss = 0.4 per beam
   beam 1 hit   L = +0.847  p = 0.700
   beam 2 hit   L = +1.695  p = 0.845
   beam 3 hit   L = +2.542  p = 0.927
   beam 4 miss  L = +2.136  p = 0.894
   beam 5 miss  L = +1.731  p = 0.850
```

```text
OA_TYPE 2
FENCE_ENABLE 1
FENCE_TYPE 4
GUID_OPTIONS 64
WP_SPD 5
```

```text
$ ./run_lab.sh oa oa.parm "" oa_dijkstra_lab.py
home -35.363261 149.165230
fence upload ack type 0
DO_FENCE_ENABLE ack result 4
FENCE_ENABLE = 1
armed, takeoff 10 m
goal 80 m north sent
time 31.8 s, path 87.0 m vs straight 80.0 m, max |E| 13.7 m, min clearance to square 3.6 m
$ python3 oadj.py sitl-run/oa/logs/00000001.BIN
OADJ State 0 point 0/0 OA -35.362542 149.165230
OADJ State 2 point 1/4 OA -35.363023 149.165379
OADJ State 2 point 2/4 OA -35.362780 149.165379
```

```text
$ ./run_lab.sh oa_nofence_enable oa_nofence.parm "" oa_dijkstra_lab.py
DO_FENCE_ENABLE ack result 4
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
$ ./run_lab.sh oa_nofence oa_nofence.parm "" oa_dijkstra_lab.py --no-enable
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
```

{{diagram:chart-nav-oa-dijkstra-track|Трек SITL совпал с планом Dijkstra до 0.5 м по длине: вершины зоны вынесены на 5/√2 = 3.54 м, путь 87.0 м вместо 80 м и 31.8 с вместо 21.2 с из-за остановок в углах.}}

{{diagram:chart-nav-brake-speed|Задержка реакции 0.3 с срезает безопасную скорость при d = 6 м с 6.0 до 5.2 м/с, а забытый запас добавляет ещё ошибку до 6.9 м/с.}}

### Крок 3. Обліт у Gazebo
Світ із колоною на шляху квадрата. Варіант А (без власного коду): ArduPilot SITL з proximity від симульованого лідара, `OA_TYPE = 1`, місія через колону — зафіксуй траєкторію BendyRuler. Варіант Б (власний вузол): сітка зайнятості за `/scan` або `OBSTACLE_DISTANCE`, A* + shortcut, уставки через автомат з ros2-px4. Порівняй траєкторії й час.

### Крок 4. Невідомий простір
Повтори крок 3 з `unknown_is_free=True` і `False`: покажи, де «оптимістичний» планувальник прокладає шлях через ще не побачене, і чому то небезпечно.

Лабораторну зараховано, коли проходить власний тест планувальника, порахована безпечна швидкість, є траєкторії обльоту (бодай варіант А) і розбір невідомого простору.

## diagnostics
- **Симптом:** шлях іде впритул до перешкоди, апарат зачіпає
  - Можлива причина: нема роздування або радіус менший за розмір апарата + похибку позиції.
  - Що зробити: inflation = радіус + 2σ позиції + запас.
- **Симптом:** апарат «смикається», перепланування кожні 100 мс міняє шлях
  - Можлива причина: глобальний планувальник на частоті локального, шумна карта.
  - Що зробити: глобальний план 1 Гц, гістерезис зміни шляху, фільтр карти (log-odds).
- **Симптом:** апарат залітає в невідому зону й губить перешкоду з поля зору
  - Можлива причина: невідоме вважається вільним; датчик дивиться не туди, куди летимо.
  - Що зробити: unknown = occupied; рискання за напрямком руху.
- **Симптом:** уставки за шляхом ведуть не туди
  - Можлива причина: шлях в ENU вислано в PX4 як NED.
  - Що зробити: конвертація на межі (frames.py), тест на відомій точці.

## references
- ArduPilot — Object avoidance (BendyRuler, Dijkstra) | https://ardupilot.org/copter/docs/common-object-avoidance-landing-page.html | primary | A
- PX4 — Collision prevention | https://docs.px4.io/main/en/computer_vision/collision_prevention.html | primary | A
- Nav2 documentation | https://docs.nav2.org/ | primary | A
- OctoMap | https://octomap.github.io/ | primary | A
- Hart, Nilsson, Raphael — A formal basis for the heuristic determination of minimum cost paths (A*) | https://ieeexplore.ieee.org/document/4082128 | secondary | A

## checklist
- Знаю, що вміють BendyRuler/Dijkstra і collision prevention без власного коду
- Розрізняю сітку зайнятості, costmap і 3D-представлення; невідоме — зайняте
- Реалізую A* з допустимою евристикою, роздуванням і згладжуванням
- Ділю глобальне й локальне планування за частотами й ролями
- Перетворюю шлях на уставки з обмеженнями швидкості за гальмівним шляхом
- Розумію, де Nav2 придається дронові, а де ні
