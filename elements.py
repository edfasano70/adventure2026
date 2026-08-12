#!/usr/bin/env python3
"""Carga y consulta la definición de los elementos del juego desde elements.json.

Este módulo es la fuente única de datos sobre los elementos (tiles/items):
tanto el juego (adventure2.py) como el editor (world_editor.py) lo usan.
La lectura del JSON no requiere pygame; las superficies se construyen después
de pygame.init() con build_element_surfaces() y build_animations().
"""
import json

ELEMENTS_PATH = 'elements.json'

# Valores por defecto de un elemento si el JSON no define alguno
DEFAULTS = {
    'name': '',
    'image': '',
    'solid': False,
    'kind': 'terrain',        # terrain | door | key | item | altar
    'opens_with': None,       # char de la llave que abre una puerta
    'inventory_id': None,     # id que entra en el inventario del héroe
    'effects': {},            # efectos de gameplay (p.ej. {"dragon": "flee"})
    'draws_under': None,      # char del tile que se dibuja debajo (p.ej. hierba)
    'size': [1, 1],           # tamaño en celdas (p.ej. altar 4x4)
    'animation': None,        # {"type": "rotate", "interval_ms": 250}
    'custom': False,          # True si lo creó el editor
}


def _load(path=ELEMENTS_PATH):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


_data = _load()
ELEMENTS = _data['elements']                 # char -> dict de definición
GAME_RULES = _data.get('rules', {})


def reload_elements(path=ELEMENTS_PATH):
    """Recarga elements.json (lo usa el editor tras crear un elemento)."""
    global _data, ELEMENTS, GAME_RULES
    _data = _load(path)
    ELEMENTS = _data['elements']
    GAME_RULES = _data.get('rules', {})


def save_elements(path=ELEMENTS_PATH):
    """Persiste elements.json con todos los elementos (incluidos los custom del editor)."""
    data = {'version': 1, 'elements': ELEMENTS, 'rules': GAME_RULES}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def element_def(ch):
    """Devuelve la definición completa de un char (con los valores por defecto)."""
    return {**DEFAULTS, **(ELEMENTS.get(ch) or {})}


# --- Consultas por char ---
def solid(ch):
    """¿El elemento es sólido (causa colisión)?"""
    return bool(element_def(ch)['solid'])


def kind_of(ch):
    """Tipo funcional del elemento: terrain | door | key | item | altar."""
    return element_def(ch)['kind']


def draws_under(ch):
    """Char del tile base que se dibuja debajo del elemento (o None)."""
    return element_def(ch)['draws_under']


def door_opens_with(ch):
    """Char de la llave que abre la puerta (o None)."""
    return element_def(ch)['opens_with']


def key_inventory_id(ch):
    """Id de inventario del elemento (o None)."""
    return element_def(ch)['inventory_id']


def effects_of(ch):
    """Efectos de gameplay del elemento (dict)."""
    return element_def(ch)['effects'] or {}


def element_size(ch):
    """Tamaño del elemento en celdas: (ancho, alto)."""
    w, h = element_def(ch)['size']
    return max(1, int(w)), max(1, int(h))


def element_image_path(ch):
    """Ruta resuelta de la imagen de un elemento (o None si no tiene imagen)."""
    return _resolve_image_path(element_def(ch)['image'])


def animation_of(ch):
    """Definición de animación del elemento (o None)."""
    return element_def(ch)['animation']


# --- Construcción de superficies (requiere pygame.init() previo) ---
def _resolve_image_path(path):
    """Resuelve una ruta de imagen: primero en assets/images/, luego tal cual."""
    import os
    if not path:
        return None
    if os.path.exists(os.path.join('assets', 'images', path)):
        return os.path.join('assets', 'images', path)
    if os.path.exists(path):
        return path
    return os.path.join('assets', 'images', path)


def build_element_surfaces():
    """Construye dos dicts de superficies pygame a partir de elements.json.

    Devuelve (tile_images, item_images):
      - tile_images: char -> superficie de TODOS los elementos (para hornear el mapa).
      - item_images: inventory_id -> superficie de los items (llaves, espada, trofeo, altar).
    """
    import pygame
    tile_images = {}
    item_images = {}
    for ch, data in ELEMENTS.items():
        full = _resolve_image_path(data.get('image', ''))
        if full is None:
            continue
        try:
            surf = pygame.image.load(full).convert_alpha()
        except Exception:
            continue
        tile_images[ch] = surf
        kid = data.get('inventory_id')
        if kid and data.get('kind') in ('key', 'item', 'altar'):
            item_images[kid] = surf
    return tile_images, item_images


def build_animations():
    """Construye los frames de los elementos animados.

    Devuelve {char: {'frames': [...], 'interval_ms': n}} para cada elemento
    con "animation": {"type": "rotate", "interval_ms": 250}.
    """
    import pygame
    out = {}
    for ch, data in ELEMENTS.items():
        anim = data.get('animation')
        if not anim:
            continue
        full = _resolve_image_path(data.get('image', ''))
        if full is None:
            continue
        try:
            base = pygame.image.load(full).convert_alpha()
        except Exception:
            continue
        if anim.get('type') == 'rotate':
            interval = max(1, int(anim.get('interval_ms', 250)))
            frames = [
                base,
                pygame.transform.rotate(base, 90),
                pygame.transform.rotate(base, 180),
                pygame.transform.rotate(base, 270),
            ]
            out[ch] = {'frames': frames, 'interval_ms': interval}
    return out
