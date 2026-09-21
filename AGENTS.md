# AGENTS.md

Pygame homage to Atari 2600 Adventure. No git repo, no packaging, no tests. All code, comments, and UI strings are in **Spanish** — keep new comments/UI in Spanish.

## Running

- Game: `python3 main.py` (requires a display; pygame 2.6 + Pillow installed).
- World editor: `python3 world_editor.py` — **based on PyQt5** (not pygame; needs PyQt5 installed). The game itself is still pygame; only the editor is Qt.
- **Always run from the repo root.** Both programs use relative paths (`assets/`, `worlds/`) and fail if launched elsewhere. The element data lives in `core/` (added to `sys.path` by both programs).
- The game's user config is `~/.config/adventure2/config.xml` (XML, auto-written at runtime; tracks `fullscreen`/`volume`). The editor persists its own state in `editor_settings.json` (repo root).
- There is no test suite. The old broken/outdated standalone prototypes (`hero.py`, `maze.py`) now live in `obsolete/tests/` — do not rely on them.

## Architecture

- `main.py` (monolith, ~1060 lines) — the whole game: input, collision, dragon, maps, UI, main loop. State is held in dicts (`hero`, `dragon`) and module globals.
- `core/elements.py` + `core/elements.json` — **single source of truth for element definitions** (tiles/items/door/key/altar). Both `main.py` and `world_editor.py` add `core/` to `sys.path` and `import elements`, reading all tile data from `core/elements.json`. `build_element_surfaces()`/`build_animations()` build pygame surfaces; `save_elements()` persists elements (the editor writes new custom elements here). Do not hardcode tile logic in the games — use `elements.solid()`, `elements.kind_of()`, `elements.door_opens_with()`, `elements.key_inventory_id()`, `elements.effects_of()`, etc.
- `world_editor.py` — **PyQt5** tile editor for building/editing world files. Saves/loads the same format the game reads. The "Nuevo" dialog persists created elements to `core/elements.json` (flag `custom: true`) and reloads surfaces (via `build_pixmaps()`, no pygame needed).
- `worlds/*.py` — pure data files (no logic). `worlds/atari_2600_world_1.py` is hardcoded as the default via `from atari_2600_world_1 import *` at the top of `main.py` (line 14). Other worlds load at runtime from the Pause → "Cargar Mundo" menu, which scans `worlds/*.py`.
- `assets/images/`, `assets/sounds/` — game resources. GIFs are loaded frame-by-frame with Pillow (`load_gif_frames`), PNGs via pygame.

## World file format

Each room is `maps.append([[up, right, down, left], [grid_rows...], dragon, visibility])`:

- Connections are 0-indexed room numbers; `-1` = no connection. Order is **up, right, down, left** — the game teleports the hero across the edge to `maps[conn][0][1]` for right, `[0][3]` for left, `[0][0]` up, `[0][2]` down.
- Grid is exactly **20 columns × 13 rows** of tile chars. Mismatched rows are padded with spaces on load, so off-by-one column errors silently produce grass.
- `dragon` (bool): **ignored by the game** — the dragon no longer depends on rooms. Kept only for editor/format compatibility. `visibility` (int): fog radius; `>= 1000` means no fog.

Tile legend (chars defined in `elements.json` — always use `elements` module helpers, never hardcode):

| Char | Meaning | Notes |
|---|---|---|
| ` ` | grass | walkable |
| `X` `Y` `y` `W` | rock / gold rock / black rock / water | solid collision |
| `B` | wood | walkable |
| `w` | window | decorative, walkable |
| `D` `d` | gold / black door | solid until you hold the matching key; then it (and the key tile) are erased from the map permanently |
| `K` `b` | gold / black key | picked up on contact |
| `S` | sword | hero holding it makes the dragon keep its distance (500 px) instead of chasing |
| `T` | trophy | victory requires trophy **+** altar |
| `A` | altar | solid 4×4 object; place at the top-left of its 4×4 area (adjacent cells are auto-consumed on render). Colliding with altar while holding trophy wins |

Items placed on `K b S T A` draw grass underneath (only the item renders).

Dragon behavior: the dragon is **always present** and moves with **real displacement** (its position is not re-derived from the hero each frame). It advances toward/away from the hero at its own speed (`dragon['speed']` px/frame@60fps), so because the hero is faster he can pull away from the dragon (the separation can exceed 500 px) but never more than the max circle radius `DRAGON_SPAWN_DISTANCE` (2000 px) centered on the hero. If the hero does **not** carry a `FLEE_ITEMS` item (e.g. the sword), the dragon closes in until collision (its collision attacks the hero). If the hero **does** carry such an item, the dragon keeps `DRAGON_ORBIT_DISTANCE` (500 px) as its target radius: too close it moves away, too far it moves closer, and within `DRAGON_ORBIT_TOLERANCE` (40 px) it orbits. When the dragon lands a hit, hero and dragon **bounce apart** (`HERO_KNOCKBACK_DISTANCE`/`KNOCKBACK_DISTANCE`) and the dragon stays frozen in place for `DRAGON_FROZEN_MS` (1 s, `dragon['frozen_until']`). On room change the dragon is **repositioned relative to the hero** (same `radius`/`orbit_angle`, so it never appears in weird spots). The `dragon` flag in world files is ignored by the game. Death of the hero resets progress to room 0 with empty inventory.

## Editor usage quick reference

Mouse + keyboard (PyQt). A combo box at the top selects the "pincel" (the currently placed element); click it to choose from all built-in and custom tiles. **"Nuevo"**/**"Editar"** open a dialog to create/edit elements (char, name, image with a file browser, sólido, kind, inventory id). Click (and drag) the map to place the selected element; right-click (and drag) erases a tile in the grid / adjusts zones down. Keyboard: arrows move cursor, `SPACE` cycles the pincel, `+`/`-` adjust connection/visibility values or room number (left/right mouse button do the same on those zones), `N` new room, `L` load, `S` save, `RETURN` deletes tile / clears a connection, `ESC` quits, `F11` toggles fullscreen. The map scales to fit the window. The filename is edited in the bottom bar (Enter saves); Load/Save/New-room buttons are in the bottom bar too. Corner zones toggle visibility/room number. Editor state (last world/room/tile/image dir/window geometry) is persisted in `editor_settings.json`.
