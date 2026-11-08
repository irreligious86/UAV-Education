"""2D occupancy-grid planning for the ros2-nav lab. No ROS imports.

  inflate(grid, r)      grow obstacles by the vehicle radius + margin (cells)
  astar(grid, s, g)     8-connected A* with an octile heuristic; returns a list of cells or None
  shortcut(grid, path)  remove intermediate cells while the straight segment stays collision-free
  to_waypoints(...)     cells -> metric waypoints in the map frame

grid[y][x]: 0 free, 1 occupied, -1 unknown (treated as occupied by default — fly only where you have seen).
"""
from __future__ import annotations

import heapq
import math


def inflate(grid, r: int):
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(h):
        for x in range(w):
            if grid[y][x] != 0:
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r:
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and out[yy][xx] == 0:
                                out[yy][xx] = 1
    return out


def free(grid, c, unknown_is_free=False) -> bool:
    x, y = c
    if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
        return False
    v = grid[y][x]
    return v == 0 or (unknown_is_free and v == -1)


def astar(grid, start, goal, unknown_is_free=False):
    if not free(grid, start, unknown_is_free) or not free(grid, goal, unknown_is_free):
        return None
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]

    def hfun(c):
        dx, dy = abs(c[0] - goal[0]), abs(c[1] - goal[1])
        return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)     # octile distance: admissible for 8-connectivity

    openq = [(hfun(start), 0.0, start)]
    g = {start: 0.0}
    parent = {}
    while openq:
        _, gc, c = heapq.heappop(openq)
        if c == goal:
            path = [c]
            while c in parent:
                c = parent[c]
                path.append(c)
            return path[::-1]
        if gc > g[c]:
            continue
        for dx, dy, cost in moves:
            n = (c[0] + dx, c[1] + dy)
            if not free(grid, n, unknown_is_free):
                continue
            if dx and dy and not (free(grid, (c[0] + dx, c[1]), unknown_is_free) and free(grid, (c[0], c[1] + dy), unknown_is_free)):
                continue                                            # no corner cutting between two obstacles
            ng = gc + cost
            if ng < g.get(n, math.inf):
                g[n], parent[n] = ng, c
                heapq.heappush(openq, (ng + hfun(n), ng, n))
    return None


def line_free(grid, a, b, unknown_is_free=False) -> bool:
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2 + 1
    for i in range(n + 1):
        t = i / n
        c = (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t))
        if not free(grid, c, unknown_is_free):
            return False
    return True


def shortcut(grid, path, unknown_is_free=False):
    if not path:
        return path
    out, i = [path[0]], 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not line_free(grid, path[i], path[j], unknown_is_free):
            j -= 1
        out.append(path[j])
        i = j
    return out


def path_length(path) -> float:
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def to_waypoints(path, resolution: float, origin=(0.0, 0.0)):
    """Cells -> (x, y) metres in the map frame (cell centres)."""
    return [(origin[0] + (c[0] + 0.5) * resolution, origin[1] + (c[1] + 0.5) * resolution) for c in path]
