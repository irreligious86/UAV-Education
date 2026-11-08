import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uav_ros2_labs.grid_planner import astar, inflate, line_free, path_length, shortcut, to_waypoints  # noqa: E402


def empty(w, h):
    return [[0] * w for _ in range(h)]


def wall(grid, x, y0, y1):
    for y in range(y0, y1 + 1):
        grid[y][x] = 1


def test_straight_line_in_free_space():
    p = astar(empty(20, 20), (0, 0), (10, 0))
    assert p[0] == (0, 0) and p[-1] == (10, 0) and abs(path_length(p) - 10) < 1e-9


def test_diagonal_cost_is_octile():
    p = astar(empty(20, 20), (0, 0), (5, 5))
    assert abs(path_length(p) - 5 * math.sqrt(2)) < 1e-9


def test_goes_around_wall_and_never_through_it():
    g = empty(30, 30)
    wall(g, 15, 0, 25)
    p = astar(g, (5, 5), (25, 5))
    assert p is not None
    assert all(g[y][x] == 0 for x, y in p)
    assert max(y for _, y in p) >= 26             # must pass the wall's end


def test_inflation_keeps_clearance():
    g = empty(30, 30)
    wall(g, 15, 0, 25)
    gi = inflate(g, 2)
    p = astar(gi, (5, 5), (25, 5))
    walls = [(15, y) for y in range(0, 26)]
    assert all(min(math.dist((x, y), w) for w in walls) > 2 for x, y in p)


def test_unknown_is_occupied_by_default():
    g = empty(10, 3)
    for x in range(10):
        g[1][x] = -1
    assert astar(g, (0, 0), (0, 2)) is None
    assert astar(g, (0, 0), (0, 2), unknown_is_free=True) is not None


def test_no_path_returns_none():
    g = empty(10, 10)
    wall(g, 5, 0, 9)
    assert astar(g, (0, 0), (9, 9)) is None


def test_shortcut_shortens_and_stays_free():
    g = empty(40, 40)
    wall(g, 20, 0, 30)
    p = astar(g, (5, 5), (35, 5))
    s = shortcut(g, p)
    assert len(s) < len(p) and path_length(s) <= path_length(p) + 1e-9
    assert all(line_free(g, a, b) for a, b in zip(s, s[1:]))


def test_waypoints_are_cell_centres():
    assert to_waypoints([(0, 0), (2, 1)], 0.5) == [(0.25, 0.25), (1.25, 0.75)]
