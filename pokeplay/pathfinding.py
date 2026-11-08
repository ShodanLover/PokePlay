"""Breadth-first pathfinding over the current map's tile grid."""

from __future__ import annotations

from collections import deque

from .game import LEDGE_BEHAVIORS, WATER_BEHAVIORS, MapGrid

STEPS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def walkable(grid: MapGrid, x: int, y: int, surfing: bool) -> bool:
    if not grid.in_bounds(x, y) or grid.blocked[y][x]:
        return False
    if grid.behavior[y][x] in WATER_BEHAVIORS and not surfing:
        return False
    return True


def neighbors(grid: MapGrid, x: int, y: int, surfing: bool, avoid: set[tuple[int, int]],
              goals: set[tuple[int, int]]):
    """Yield (direction, nx, ny) for each tile reachable with one button press."""
    for name, (dx, dy) in STEPS.items():
        nx, ny = x + dx, y + dy
        if (nx, ny) in goals and (nx, ny) not in avoid:
            yield name, nx, ny
            continue
        if not grid.in_bounds(nx, ny) or (nx, ny) in avoid:
            continue
        jump = LEDGE_BEHAVIORS.get(grid.behavior[ny][nx])
        if jump is not None:
            # Ledges can only be jumped in one direction, landing two tiles away.
            if jump == (dx, dy):
                lx, ly = nx + dx, ny + dy
                if (lx, ly) not in avoid and (walkable(grid, lx, ly, surfing) or (lx, ly) in goals):
                    yield name, lx, ly
            continue
        if walkable(grid, nx, ny, surfing):
            yield name, nx, ny


def find_path(grid: MapGrid, start: tuple[int, int], goals: set[tuple[int, int]],
              avoid: set[tuple[int, int]] | None = None, surfing: bool = False) -> list[str] | None:
    """Return the list of directions to press to reach any goal tile, or None.

    Goal tiles are allowed even if they look blocked (doors, warp tiles)."""
    avoid = set(avoid or ()) - {start}
    goals = set(goals)
    if start in goals:
        return []
    prev: dict[tuple[int, int], tuple[tuple[int, int], str]] = {}
    seen = {start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for direction, nx, ny in neighbors(grid, cur[0], cur[1], surfing, avoid, goals):
            nxt = (nx, ny)
            if nxt in seen:
                continue
            seen.add(nxt)
            prev[nxt] = (cur, direction)
            if nxt in goals:
                path = []
                node = nxt
                while node != start:
                    node, d = prev[node]
                    path.append(d)
                return list(reversed(path))
            # Goals that look blocked (e.g. doors) are destinations, not corridors.
            if walkable(grid, nx, ny, surfing):
                queue.append(nxt)
    return None


def reachable(grid: MapGrid, start: tuple[int, int], avoid: set[tuple[int, int]] | None = None,
              surfing: bool = False) -> dict[tuple[int, int], int]:
    """All tiles reachable from start, mapped to their step distance."""
    avoid = set(avoid or ()) - {start}
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for _d, nx, ny in neighbors(grid, cur[0], cur[1], surfing, avoid, set()):
            if (nx, ny) not in dist:
                dist[(nx, ny)] = dist[cur] + 1
                queue.append((nx, ny))
    return dist
