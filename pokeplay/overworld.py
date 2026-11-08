"""Overworld actions: build the list of things the AI can do, and carry them out."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from . import addresses as A
from .emulator import Emulator
from .game import (ARROW_WARPS, BEHAVIOR_COUNTER, BEHAVIOR_TALL_GRASS, WATER_BEHAVIORS, Game,
                   GameState, MapGrid, NPC)
from .memory import Memory
from .pathfinding import STEPS, find_path, reachable, walkable

OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}
TEMP_BLOCK_SECONDS = 45
BLOCKED_EXIT = "(blocked)"      # saved in her door links, so it survives restarts


def relative(x: int, y: int, tx: int, ty: int) -> str:
    """'3 steps up and 2 to the left' instead of coordinates."""
    dx, dy = tx - x, ty - y
    parts = []
    if dy:
        parts.append(f"{abs(dy)} {'step' if abs(dy) == 1 else 'steps'} {'up' if dy < 0 else 'down'}")
    if dx:
        parts.append(f"{abs(dx)} {'step' if abs(dx) == 1 else 'steps'} to the {'left' if dx < 0 else 'right'}")
    return " and ".join(parts) if parts else "right where you're standing"


def region(x: int, y: int, w: int, h: int) -> str:
    ns = "north" if y < h / 3 else "south" if y > 2 * h / 3 else ""
    ew = "west" if x < w / 3 else "east" if x > 2 * w / 3 else ""
    return (ns + ew) or "middle"


@dataclass
class Option:
    kind: str                 # warp | exit | talk | explore | train | menu | water | push
    label: str
    key: str                  # stable id used to count how often it was picked / remember where it leads
    target: tuple[int, int] | None = None
    direction: str = ""
    npc: NPC | None = None
    distance: int = 0


@dataclass
class Result:
    outcome: str              # arrived | warped | interrupted | no_path | stuck | talked
    detail: str = ""


@dataclass
class Overworld:
    emu: Emulator
    game: Game
    memory: Memory | None = None
    steps_taken: int = 0
    temp_blocks: dict[tuple[int, int, int, int], float] = field(default_factory=dict)
    visited: dict[tuple[int, int], set[tuple[int, int]]] = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers
    def _map_key(self, s: GameState) -> tuple[int, int]:
        return (s.map_group, s.map_num)

    def _avoid(self, s: GameState, npcs: list[NPC], warps_to_avoid: set[tuple[int, int]]) -> set[tuple[int, int]]:
        now = time.time()
        avoid = {(n.x, n.y) for n in npcs} | warps_to_avoid
        for (g, m, x, y), until in list(self.temp_blocks.items()):
            if until < now:
                del self.temp_blocks[(g, m, x, y)]
            elif (g, m) == self._map_key(s):
                avoid.add((x, y))
        return avoid

    def mark_visited(self, s: GameState) -> None:
        self.visited.setdefault(self._map_key(s), set()).add((s.x, s.y))

    def _wait_until_still(self, max_frames: int = 60) -> None:
        for _ in range(max_frames // 4):
            if self.emu.u8(A.gPlayerAvatar + 3) == 0 and self.emu.u8(A.gPlayerAvatar + 2) == 0:
                return
            self.emu.wait_frames(4)

    # ------------------------------------------------------------------ options
    def build_options(self, s: GameState) -> tuple[list[Option], MapGrid]:
        grid = self.game.map_grid()
        npcs = self.game.npcs()
        warps = self.game.warps()
        warp_tiles = {(w.x, w.y) for w in warps}
        avoid = self._avoid(s, npcs, warp_tiles)
        dist = reachable(grid, (s.x, s.y), avoid, s.surfing)
        options: list[Option] = []

        # Doors, stairs and other warps.
        seen_dest = set()
        # A doorway can have decoy warp tiles beside the real one (behavior 0 never fires), so real ones go first.
        for w in sorted(warps, key=lambda w: not grid.in_bounds(w.x, w.y) or grid.behavior[w.y][w.x] == 0):
            path = find_path(grid, (s.x, s.y), {(w.x, w.y)}, avoid - {(w.x, w.y)}, s.surfing)
            if path is None:
                continue
            dest = (w.dest_group, w.dest_num)
            # Many maps have 2-tile-wide doors to the same place; list each once.
            if dest in seen_dest and w.dest_group != 0x7F:
                continue
            seen_dest.add(dest)
            key = f"{s.map_group}.{s.map_num}|door@{w.x},{w.y}"
            known = self.memory.links.get(key) if self.memory else None
            where = f"leads to {known}" if known else "you haven't been through it yet"
            options.append(Option("warp", f"Go through the doorway/stairs {relative(s.x, s.y, w.x, w.y)} ({where})",
                                  key, (w.x, w.y), distance=len(path)))

        # Walking off the edge of the map into a connected area.
        for c in self.game.connections():
            edge = self._edge_tiles(grid, c.direction, s.surfing)
            reach = [t for t in edge if t in dist]
            if not reach:
                continue
            best = min(reach, key=lambda t: dist[t])
            key = f"{s.map_group}.{s.map_num}|edge:{c.direction}"
            known = self.memory.links.get(key) if self.memory else None
            if known == BLOCKED_EXIT:
                if not s.surfing:           # proven impassable on foot (usually water at the map's edge)
                    continue
                known = None
            where = f"leads to {known}" if known else "you haven't been that way yet"
            options.append(Option("exit", f"Leave this area by the {c.direction} side ({where})", key, best,
                                  direction={"north": "up", "south": "down", "west": "left", "east": "right"}[c.direction],
                                  distance=dist[best]))

        # People and objects to talk to.
        for n in npcs:
            stands = self._talk_positions(grid, n, s.surfing)
            reach = [t for t in stands if t in dist]
            if not reach:
                continue
            best = min(reach, key=lambda t: dist[t])
            key = f"{s.map_group}.{s.map_num}|{n.local_id}"
            said = self.memory.people.get(key) if self.memory else None
            extra = f' (you checked it before: "{said[:90]}")' if said else ""
            what = {A.OBJ_EVENT_GFX_CUT_TREE: "the small, thin tree",
                    A.OBJ_EVENT_GFX_PUSHABLE_BOULDER: "the big round boulder",
                    A.OBJ_EVENT_GFX_ROCK_SMASH_ROCK: "the cracked rock",
                    A.OBJ_EVENT_GFX_ITEM_BALL: "the round object on the ground"}.get(n.graphics_id, "the person")
            verb = "Talk to" if what == "the person" else "Check"
            options.append(Option("talk", f"{verb} {what} {relative(s.x, s.y, n.x, n.y)}{extra}",
                                  key, best, npc=n, distance=dist[best]))
            if n.graphics_id == A.OBJ_EVENT_GFX_PUSHABLE_BOULDER:
                options.append(Option("push", f"Try to push the big round boulder {relative(s.x, s.y, n.x, n.y)}",
                                      key + "|push", best, npc=n, distance=dist[best]))

        # Water's edge (she can try interacting with the water).
        if not s.surfing:
            shore = []
            for (tx, ty), d in dist.items():
                for name, (dx, dy) in STEPS.items():
                    wx, wy = tx + dx, ty + dy
                    if grid.in_bounds(wx, wy) and grid.behavior[wy][wx] in WATER_BEHAVIORS \
                            and not grid.blocked[wy][wx]:
                        shore.append((d, (tx, ty), name))
            if shore:
                d, tile, face = min(shore)
                options.append(Option("water", f"Go to the water's edge {relative(s.x, s.y, *tile)} and interact with the water",
                                      f"water:{s.map_group}.{s.map_num}", tile, direction=face, distance=d))

        # The main menu (Pokémon, Bag, save...).
        options.append(Option("menu", "Open the main menu (START button)", "menu", None, distance=0))

        # Tall grass for training.
        grass = [t for t in dist if grid.behavior[t[1]][t[0]] == BEHAVIOR_TALL_GRASS]
        if grass and s.party:
            g = min(grass, key=lambda t: dist[t])
            options.append(Option("train", f"Walk around in the tall grass {relative(s.x, s.y, g[0], g[1])}",
                                  f"grass:{s.map_group}.{s.map_num}", g, distance=dist[g]))

        # Explore the least-visited reachable spot.
        visited = self.visited.get(self._map_key(s), set())
        if len(dist) > 1:
            def novelty(t):
                if not visited:
                    return dist[t]
                return min(abs(t[0] - vx) + abs(t[1] - vy) for vx, vy in visited)
            candidates = random.sample(list(dist), min(200, len(dist)))
            unexplored = [t for t in candidates if novelty(t) >= 3]
            far = max(candidates, key=novelty)
            # Only offer exploring when a real chunk of the area is still unseen
            # (otherwise she wanders around the corners of a small room forever).
            if len(unexplored) >= max(6, len(candidates) // 8):
                options.append(Option("explore", f"Explore the {region(far[0], far[1], grid.width, grid.height)} part of this area, where you haven't walked yet",
                                      f"explore:{s.map_group}.{s.map_num}", far, distance=dist[far]))
        return options, grid

    def _edge_tiles(self, grid: MapGrid, direction: str, surfing: bool) -> list[tuple[int, int]]:
        if direction == "north":
            tiles = [(x, 0) for x in range(grid.width)]
        elif direction == "south":
            tiles = [(x, grid.height - 1) for x in range(grid.width)]
        elif direction == "west":
            tiles = [(0, y) for y in range(grid.height)]
        else:
            tiles = [(grid.width - 1, y) for y in range(grid.height)]
        return [t for t in tiles if walkable(grid, t[0], t[1], surfing)]

    def _talk_positions(self, grid: MapGrid, n: NPC, surfing: bool) -> list[tuple[int, int]]:
        out = []
        for dx, dy in STEPS.values():
            ax, ay = n.x + dx, n.y + dy
            if walkable(grid, ax, ay, surfing):
                out.append((ax, ay))
            # Shop/Pokemon Center counters: talk across the counter.
            if grid.in_bounds(ax, ay) and grid.behavior[ay][ax] == BEHAVIOR_COUNTER:
                bx, by = n.x + 2 * dx, n.y + 2 * dy
                if walkable(grid, bx, by, surfing):
                    out.append((bx, by))
        return out

    # ------------------------------------------------------------------ movement
    def step(self, direction: str) -> str:
        """Take one step. Returns 'moved', 'blocked', 'changed' (map/mode changed)."""
        before = self.game.state_light()
        for attempt in range(3):
            self.emu.press(direction, hold=10, wait=4)
            self._wait_until_still()
            after = self.game.state_light()
            if after[0] != "overworld" or after[1:3] != before[1:3]:
                return "changed"
            if after[3:5] != before[3:5]:
                self.steps_taken += 1
                return "moved"
        return "blocked"

    def walk_to(self, goals: set[tuple[int, int]], s: GameState, allow: set[tuple[int, int]] = frozenset(),
                max_replans: int = 6) -> Result:
        start_map = self._map_key(s)
        for _ in range(max_replans):
            cur = self.game.state()
            if cur.mode != "overworld":
                return Result("interrupted", cur.mode)
            if self._map_key(cur) != start_map:
                return Result("warped", cur.map_name)
            self.mark_visited(cur)
            if (cur.x, cur.y) in goals:
                return Result("arrived")
            npcs = self.game.npcs()
            warp_tiles = {(w.x, w.y) for w in self.game.warps()} - set(goals) - set(allow)
            grid = self.game.map_grid()
            avoid = self._avoid(cur, npcs, warp_tiles)
            path = find_path(grid, (cur.x, cur.y), goals, avoid, cur.surfing)
            if path is None:
                return Result("no_path")
            if not path:
                return Result("arrived")
            x, y = cur.x, cur.y
            for direction in path:
                r = self.step(direction)
                if r == "changed":
                    now = self.game.state()
                    if self._map_key(now) != start_map:
                        return Result("warped", now.map_name)
                    return Result("interrupted", now.mode)
                if r == "blocked":
                    dx, dy = STEPS[direction]
                    self.temp_blocks[(*start_map, x + dx, y + dy)] = time.time() + TEMP_BLOCK_SECONDS
                    break
                now = self.game.state_light()
                x, y = now[3], now[4]
                self.visited.setdefault(start_map, set()).add((x, y))
            else:
                now = self.game.state_light()
                if (now[3], now[4]) in goals:
                    return Result("arrived")
        return Result("stuck")

    # ------------------------------------------------------------------ actions
    def execute(self, opt: Option, s: GameState) -> Result:
        if opt.kind == "warp":
            r = self.walk_to({opt.target}, s, allow={opt.target})
            if r.outcome != "arrived":
                return r
            return self._nudge_warp(opt, s)
        if opt.kind == "exit":
            r = self.walk_to({opt.target}, s)
            if r.outcome != "arrived":
                return r
            for _ in range(3):
                if self.step(opt.direction) == "changed":
                    now = self.game.state()
                    return Result("warped", now.map_name) if self._map_key(now) != self._map_key(s) else Result("interrupted", now.mode)
            return Result("stuck", "could not leave the map edge")
        if opt.kind == "talk":
            r = self.walk_to({opt.target}, s)
            if r.outcome != "arrived":
                return r
            return self._talk(opt.npc)
        if opt.kind == "train":
            return self._train(opt, s)
        if opt.kind == "explore":
            return self.walk_to({opt.target}, s)
        if opt.kind == "menu":
            self.emu.press("START", hold=2, wait=30)
            return Result("talked", "opened the menu")
        if opt.kind == "water":
            r = self.walk_to({opt.target}, s)
            if r.outcome != "arrived":
                return r
            self.emu.press(opt.direction, hold=2, wait=8)   # face the water
            self.emu.press("A", hold=2, wait=30)
            return Result("talked" if self.game.mode() != "overworld" else "stuck", "")
        if opt.kind == "push":
            r = self.walk_to({opt.target}, s)
            if r.outcome != "arrived":
                return r
            _m, _g, _n, x, y = self.game.state_light()
            dx, dy = opt.npc.x - x, opt.npc.y - y
            d = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
            before = (opt.npc.x, opt.npc.y)
            for _ in range(3):
                self.emu.press(d, hold=16, wait=20)
            moved = all((n.x, n.y) != before for n in self.game.npcs() if n.local_id == opt.npc.local_id)
            return Result("arrived" if moved else "stuck", "the boulder moved" if moved else "it didn't budge")
        return Result("stuck", f"unknown option {opt.kind}")

    def _nudge_warp(self, opt: Option, s: GameState) -> Result:
        """Standing on a warp tile doesn't always trigger it (mats, stairs at edges)."""
        grid = self.game.map_grid()
        x, y = opt.target
        tries = []
        if ARROW_WARPS.get(grid.behavior[y][x]):
            tries.append(ARROW_WARPS[grid.behavior[y][x]])
        tries += ["down", "up", "left", "right"]
        for d in tries:
            self.emu.wait_frames(20)
            now = self.game.state()
            if self._map_key(now) != self._map_key(s):
                return Result("warped", now.map_name)
            if now.mode != "overworld":
                return Result("interrupted", now.mode)
            self.emu.press(d, hold=8, wait=30)
        now = self.game.state()
        if self._map_key(now) != self._map_key(s):
            return Result("warped", now.map_name)
        return Result("stuck", "warp did not trigger")

    def _talk(self, npc: NPC) -> Result:
        # Re-read the NPC position in case it moved.
        for n in self.game.npcs():
            if n.local_id == npc.local_id:
                npc = n
        _mode, _g, _m, x, y = self.game.state_light()
        dx, dy = npc.x - x, npc.y - y
        if abs(dx) + abs(dy) == 0:
            return Result("stuck")
        if abs(dx) >= abs(dy):
            face = "right" if dx > 0 else "left"
        else:
            face = "down" if dy > 0 else "up"
        self.emu.press(face, hold=2, wait=8)   # a short tap turns without walking
        self.emu.press("A", hold=4, wait=20)
        mode = self.game.mode()
        return Result("talked" if mode != "overworld" else "stuck", "nobody answered" if mode == "overworld" else "")

    def _train(self, opt: Option, s: GameState, steps: int = 40) -> Result:
        r = self.walk_to({opt.target}, s)
        if r.outcome != "arrived":
            return r
        grid = self.game.map_grid()
        x, y = opt.target
        pace = [d for d, (dx, dy) in STEPS.items()
                if grid.in_bounds(x + dx, y + dy) and grid.behavior[y + dy][x + dx] == BEHAVIOR_TALL_GRASS
                and walkable(grid, x + dx, y + dy, s.surfing)]
        if not pace:
            pace = [d for d, (dx, dy) in STEPS.items() if walkable(grid, x + dx, y + dy, s.surfing)]
        if not pace:
            return Result("stuck", "no room to pace")
        d = pace[0]
        for _ in range(steps):
            res = self.step(d)
            if res == "changed":
                return Result("interrupted", self.game.mode())
            d = OPPOSITE[d]
        return Result("arrived", "no wild Pokémon appeared")
