# AGENTS.md

Pygame homage to Atari 2600 Adventure. No git repo, no packaging, no tests. All code, comments, and UI strings are in **Spanish** — keep new comments/UI in Spanish.

## Running

- Game: `python3 adventure2.py` (requires a display; pygame 2.6 + Pillow installed).
- World editor: `python3 world_editor.py`.
- **Always run from the repo root.** Both programs use relative paths (`assets/`, `worlds/`, `settings.json`) and fail if launched elsewhere.
- `settings.json` is auto-written at runtime by the game (tracks `fullscreen`/`volume`); don't hand-edit it unless you know what you're doing.
- There is no test suite. `tests/` holds old standalone prototypes that are broken/outdated (`tests/hero.py` references an undefined `Banner()`) — do not rely on them.

## Architecture

- `adventure2.py` (monolith, ~1060 lines) — the whole game: assets, input, collision, dragon AI, maps, UI, main loop. State is held in dicts (`hero`, `dragon`) and module globals.
- `world_editor.py` — mouse-free tile editor for building/editing world files. Saves/loads the same format the game reads.
- `worlds/*.py` — pure data files (no logic). `worlds/atari_2600_world_1.py` is hardcoded as the default via `from atari_2600_world_1 import *` at the top of `adventure2.py` (line 14). Other worlds load at runtime from the Pause → "Cargar Mundo" menu, which scans `worlds/*.py`.
- `assets/images/`, `assets/sounds/` — game resources. GIFs are loaded frame-by-frame with Pillow (`load_gif_frames`), PNGs via pygame.

## World file format

Each room is `maps.append([[up, right, down, left], [grid_rows...], dragon, visibility])`:

- Connections are 0-indexed room numbers; `-1` = no connection. Order is **up, right, down, left** — the game teleports the hero across the edge to `maps[conn][0][1]` for right, `[0][3]` for left, `[0][0]` up, `[0][2]` down.
- Grid is exactly **20 columns × 13 rows** of tile chars. Mismatched rows are padded with spaces on load, so off-by-one column errors silently produce grass.
- `dragon` (bool): room starts the dragon active. `visibility` (int): fog radius; `>= 1000` means no fog.

Tile legend:

| Char | Meaning | Notes |
|---|---|---|
| ` ` | grass | walkable |
| `X` `Y` `y` `W` | rock / gold rock / black rock / water | solid collision |
| `B` | wood | walkable |
| `w` | window | decorative, walkable |
| `D` `d` | gold / black door | solid until you hold the matching key; then it (and the key tile) are erased from the map permanently |
| `K` `b` | gold / black key | picked up on contact |
| `S` | sword | hero holding it makes the dragon flee instead of attack |
| `T` | trophy | victory requires trophy **+** altar |
| `A` | altar | solid 4×4 object; place at the top-left of its 4×4 area (adjacent cells are auto-consumed on render). Colliding with altar while holding trophy wins |

Items placed on `K b S T A` draw grass underneath (only the item renders).

Dragon behavior gotcha: when the hero has the sword, the dragon never attacks and can escape the room, then respawns in a random other room. Death of the hero resets progress to room 0 with empty inventory.

## Editor usage quick reference

Mouse + keyboard. A dropdown at the bottom-left shows the currently selected element; click it to choose from all built-in and custom tiles. A **"Nuevo"** button opens a dialog to create new elements (image path, name, char code, rigid flag, item type). Click the map to place the selected element. The cursor follows the mouse. Keyboard: arrows move cursor, `SPACE` rotates the selected element, `+`/`-` adjust connection/visibility values or room number (left/right mouse button do the same on those zones), `N` new room, `L` load, `S` save, `RETURN` deletes tile / clears a connection, `ESC` quits, `F11` toggles fullscreen. The window is resizable (content scales to fit). The filename is edited in the bottom bar; `S` saves to `worlds/<name>.py`. Corner zones toggle dragon/visibility/room number.
