#!/usr/bin/env python3
"""Carga de imágenes del juego, con soporte de SVG.

Los SVG se rasterizan a mapa de bits RGBA (con transparencia real) usando
svglib + reportlab (backend rlPyCairo) y, cuando hace falta una superficie de
pygame, se convierten con load_surface(). El rasterizado en sí no necesita
pygame: sólo load_surface() lo importa.
"""
import os
import threading

_native_cache = {}
_cache_lock = threading.Lock()


def is_svg(path):
    """¿La ruta corresponde a un archivo SVG?"""
    return bool(path) and str(path).lower().endswith('.svg')


def _rasterize_native(path):
    """Rasteriza un SVG a una imagen PIL RGBA (cacheada por ruta)."""
    key = os.path.abspath(path)
    with _cache_lock:
        if key in _native_cache:
            return _native_cache[key]

    img = None
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        drawing = svg2rlg(path)
        if drawing is not None:
            # bg=None + backendFmt='RGBA' => fondo transparente
            img = renderPM.drawToPIL(drawing, bg=None, backendFmt='RGBA').convert('RGBA')
    except Exception as exc:
        print(f"Error al rasterizar SVG '{path}': {exc}")
        img = None

    with _cache_lock:
        _native_cache[key] = img
    return img


def rasterize_svg(path, size=None):
    """Devuelve una imagen PIL RGBA de un SVG (o None si falla).

    size: (ancho, alto) destino opcional; se redimensiona con LANCZOS.
    """
    native = _rasterize_native(path)
    if native is None:
        return None
    if size is not None and native.size != tuple(size):
        from PIL import Image
        return native.resize(size, Image.LANCZOS)
    return native.copy()


def load_pil(path, size=None):
    """Carga una imagen (SVG o raster) como PIL RGBA (o None si falla)."""
    if is_svg(path):
        return rasterize_svg(path, size)
    try:
        from PIL import Image
        img = Image.open(path).convert('RGBA')
    except Exception as exc:
        print(f"Error al cargar la imagen '{path}': {exc}")
        return None
    if size is not None and img.size != tuple(size):
        img = img.resize(size, Image.LANCZOS)
    return img


def load_surface(path, size=None):
    """Carga una imagen (SVG o raster) como superficie de pygame (RGBA).

    Requiere pygame.display.init() previo, ya que usa convert_alpha().
    """
    import pygame
    try:
        if is_svg(path):
            img = rasterize_svg(path, size)
            if img is None:
                return None
            return pygame.image.fromstring(img.tobytes(), img.size, 'RGBA').convert_alpha()
        surf = pygame.image.load(path).convert_alpha()
    except Exception as exc:
        print(f"Error al cargar la imagen '{path}': {exc}")
        return None
    if size is not None and surf.get_size() != tuple(size):
        surf = pygame.transform.smoothscale(surf, size)
    return surf
