#!/usr/bin/env python3
import pygame
import os

# --- Configuración de la ventana ---
CELL = 64
GRID_W = 20  # Columnas de la cuadrícula
GRID_H = 13  # Filas de la cuadrícula
W_COLS = GRID_W + 2  # Bordes izquierdo y derecho
W_ROWS = GRID_H + 4  # Bordes sup/inf + fila de paleta + barra del nombre del archivo

PALETTE_START = 1  # Columna inicial de la paleta de tiles

WIDTH = W_COLS * CELL
HEIGHT = W_ROWS * CELL

DEFAULT_FILENAME = 'atari_2600_world_1'


def world_path(filename):
    """Devuelve la ruta completa del archivo de mundo a partir de su nombre."""
    name = filename.strip()
    if not name.endswith('.py'):
        name += '.py'
    return os.path.join('worlds', name)

# Tipos de recuadro que se ciclan con ESPACIO
TILE_TYPES = [' ', 'X', 'Y', 'y', 'W', 'B', 'D', 'd', 'w', 'K', 'b', 'S', 'T', 'A']
TILE_NAMES = {
    ' ': 'HIERBA', 'X': 'MURO', 'Y': 'ROCA ORO', 'y': 'ROCA NEGRA', 'W': 'AGUA',
    'B': 'MADERA', 'D': 'PUERTA DORADA', 'd': 'PUERTA NEGRA', 'w': 'VENTANA',
    'K': 'LLAVE ORO', 'b': 'LLAVE NEGRA', 'S': 'ESPADA', 'T': 'TROFEO', 'A': 'ALTAR'
}

pygame.init()
gameScreen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('World Editor - Adventure 2024')
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 20)
tiny_font = pygame.font.Font(None, 16)

# Superficie interna de tamaño fijo; al dibujar se escala a la ventana.
render_surface = pygame.Surface((WIDTH, HEIGHT))
fullscreen = False
windowed_size = (WIDTH, HEIGHT)


def toggle_fullscreen():
    """Alterna entre pantalla completa y modo ventana con F11."""
    global gameScreen, fullscreen, windowed_size
    fullscreen = not fullscreen
    if fullscreen:
        windowed_size = gameScreen.get_size()
        info = pygame.display.Info()
        gameScreen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    else:
        gameScreen = pygame.display.set_mode(windowed_size)


def mouse_to_cell(pos):
    """Convierte un punto de la ventana (posiblemente escalada) a celda."""
    sx = WIDTH / gameScreen.get_width()
    sy = HEIGHT / gameScreen.get_height()
    gx = int(pos[0] * sx) // CELL
    gy = int(pos[1] * sy) // CELL
    return max(0, min(W_COLS - 1, gx)), max(0, min(W_ROWS - 1, gy))


# --- Carga de assets (misma estética que el juego) ---
tile_images = {
    'X': pygame.image.load('assets/images/rock_64.png').convert_alpha(),
    'Y': pygame.image.load('assets/images/rock_64_gold.png').convert_alpha(),
    'y': pygame.image.load('assets/images/rock_64_black.png').convert_alpha(),
    'W': pygame.image.load('assets/images/water_64.png').convert_alpha(),
    'B': pygame.image.load('assets/images/wood_64.png').convert_alpha(),
    'D': pygame.image.load('assets/images/door_64.png').convert_alpha(),
    ' ': pygame.image.load('assets/images/grass_64.png').convert_alpha(),
    'w': pygame.image.load('assets/images/window_64.png').convert_alpha(),
}
item_images = {
    'K': pygame.image.load('assets/images/key_golden.png').convert_alpha(),
    'b': pygame.image.load('assets/images/key_black.png').convert_alpha(),
    'S': pygame.image.load('assets/images/sword.png').convert_alpha(),
    'T': pygame.image.load('assets/images/trophy.png').convert_alpha(),
    'A': pygame.image.load('assets/images/altar.png').convert_alpha(),
}


def blank_grid():
    return [' ' * GRID_W for _ in range(GRID_H)]


def new_room(number):
    return {
        'number': number,
        'grid': blank_grid(),
        'connections': {'up': -1, 'right': -1, 'down': -1, 'left': -1},
        'dragon': False,
        'visibility': 1000,
    }


def load_world(path):
    rooms = {}
    if not os.path.exists(path):
        return rooms
    ns = {}
    with open(path) as f:
        code = f.read()
    exec(compile(code, path, 'exec'), ns)
    for i, m in enumerate(ns.get('maps', [])):
        try:
            # Conexiones con valores por defecto si faltan
            conn = list(m[0]) if len(m) > 0 and isinstance(m[0], (list, tuple)) else []
            conn = (conn + [-1] * 4)[:4]
            # Filas de la cuadrícula, ignorando entradas que no sean cadenas
            raw_rows = m[1] if len(m) > 1 else []
            grid = []
            for row in raw_rows:
                if isinstance(row, str):
                    grid.append(row.ljust(GRID_W)[:GRID_W])
                else:
                    grid.append(' ' * GRID_W)
            while len(grid) < GRID_H:
                grid.append(' ' * GRID_W)
            dragon = bool(m[2]) if len(m) > 2 else False
            vis = m[3] if len(m) > 3 and isinstance(m[3], int) else 1000
            rooms[i] = {
                'number': i,
                'grid': grid[:GRID_H],
                'connections': {'up': conn[0], 'right': conn[1], 'down': conn[2], 'left': conn[3]},
                'dragon': dragon,
                'visibility': vis,
            }
        except Exception:
            continue
    return rooms


def save_world(path, rooms):
    lines = ['maps = []']
    for num in sorted(rooms):
        r = rooms[num]
        c = r['connections']
        lines.append(f'#------Sala {num}')
        lines.append(f'maps.append([[{c["up"]},{c["right"]},{c["down"]},{c["left"]}], [')
        for row in r['grid']:
            lines.append(f"    '{row}',")
        lines.append('],')
        lines.append(f'    {str(r["dragon"])}, # ¿Hay dragón en esta sala?')
        lines.append(f'    {r["visibility"]}] #visibilidad')
        lines.append(')')
        lines.append('')
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    return len(rooms)


def zone_of(cx, cy):
    file_row = W_ROWS - 1   # Barra del nombre del archivo
    bottom_row = W_ROWS - 3 # Borde inferior (conexión ABAJO)
    palette_row = W_ROWS - 2 # Fila de la paleta de tiles
    if cy == file_row:
        return 'file'
    if cy == palette_row:
        return 'palette'
    if cx == 0 and cy == 0:
        return 'room'
    if cx == W_COLS - 1 and cy == 0:
        return 'dragon'
    if cx == 0 and cy == bottom_row:
        return 'vis'
    if cx == W_COLS - 1 and cy == bottom_row:
        return 'status'
    if cy == 0:
        return 'up'
    if cy == bottom_row:
        return 'down'
    if cx == 0:
        return 'left'
    if cx == W_COLS - 1:
        return 'right'
    return 'grid'


def grid_pos(cx, cy):
    """Devuelve (gx, gy) dentro de la cuadrícula, o None si el cursor no está
    sobre una celda de la cuadrícula o queda fuera de sus límites."""
    if zone_of(cx, cy) != 'grid':
        return None
    gx, gy = cx - 1, cy - 1
    if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
        return gx, gy
    return None


def draw_rotated(surface, text, font, color, center, angle=90):
    img = font.render(text, True, color)
    img = pygame.transform.rotate(img, angle)
    surface.blit(img, img.get_rect(center=center))


def draw_lines(surface, lines, font, color, center):
    imgs = [font.render(line, True, color) for line in lines]
    y = center[1] - sum(i.get_height() for i in imgs) // 2
    for i in imgs:
        surface.blit(i, (center[0] - i.get_width() // 2, y))
        y += i.get_height()


def blit_tile(surface, img, rect):
    """Dibuja una imagen de tile; si mide más que la celda, la redimensiona a su tamaño."""
    if img.get_width() > rect.width or img.get_height() > rect.height:
        img = pygame.transform.scale(img, (rect.width, rect.height))
    surface.blit(img, rect)


# ==================== NUEVOS COMPONENTES UI ====================

class Dropdown:
    """Desplegable para seleccionar un elemento (tile/item)."""
    def __init__(self, x, y, width, height, font, small_font, items, get_item_image, get_item_name):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.small_font = small_font
        self.items = items          # lista de claves (chars)
        self.get_image = get_item_image
        self.get_name = get_item_name
        self.expanded = False
        self.selected_index = 0
        self.list_rect = None
        self.item_height = 32
        self.max_visible = 8

    @property
    def selected(self):
        return self.items[self.selected_index] if self.items else None

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse_pos):
                self.expanded = not self.expanded
                return True
            if self.expanded and self.list_rect and self.list_rect.collidepoint(mouse_pos):
                # Clic en la lista: selecciona el item
                rel_y = mouse_pos[1] - self.list_rect.top
                idx = rel_y // self.item_height
                if 0 <= idx < len(self.items):
                    self.selected_index = idx
                self.expanded = False
                return True
            if self.expanded:
                # Clic fuera: cierra
                self.expanded = False
        return False

    def draw(self, surface):
        # Botón principal
        pygame.draw.rect(surface, (55, 55, 55), self.rect)
        pygame.draw.rect(surface, (90, 90, 90), self.rect, 1)
        ch = self.selected
        if ch:
            img = self.get_image(ch)
            if img:
                img_rect = pygame.Rect(self.rect.x + 4, self.rect.y + 4, self.rect.height - 8, self.rect.height - 8)
                blit_tile(surface, img, img_rect)
            name = self.get_name(ch)
            txt = self.font.render(name, True, 'white')
            surface.blit(txt, (self.rect.x + self.rect.height, self.rect.y + (self.rect.height - txt.get_height()) // 2))
        # Flecha
        arrow = self.font.render('▼' if not self.expanded else '▲', True, 'white')
        surface.blit(arrow, (self.rect.right - arrow.get_width() - 8, self.rect.y + (self.rect.height - arrow.get_height()) // 2))

        if not self.expanded:
            return

        # Lista desplegada (hacia arriba desde el botón)
        list_h = min(len(self.items), self.max_visible) * self.item_height
        self.list_rect = pygame.Rect(self.rect.x, self.rect.y - list_h, self.rect.width, list_h)
        pygame.draw.rect(surface, (40, 40, 40), self.list_rect)
        pygame.draw.rect(surface, (90, 90, 90), self.list_rect, 1)

        for i, item_ch in enumerate(self.items):
            iy = self.list_rect.y + i * self.item_height
            item_rect = pygame.Rect(self.list_rect.x, iy, self.list_rect.width, self.item_height)
            if i == self.selected_index:
                pygame.draw.rect(surface, (70, 70, 90), item_rect)
            img = self.get_image(item_ch)
            if img:
                img_r = pygame.Rect(item_rect.x + 4, iy + 2, self.item_height - 4, self.item_height - 4)
                blit_tile(surface, img, img_r)
            name = self.get_name(item_ch)
            txt = self.small_font.render(name, True, 'white')
            surface.blit(txt, (item_rect.x + self.item_height, iy + (self.item_height - txt.get_height()) // 2))


class InputBox:
    """Cuadro de texto editable."""
    def __init__(self, x, y, w, h, font, text='', label=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.text = text
        self.label = label
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.active = False
            else:
                ch = getattr(event, 'unicode', '') or ''
                if ch and ch.isprintable():
                    self.text += ch
        return self.active

    def draw(self, surface):
        color = (80, 80, 120) if self.active else (60, 60, 60)
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, (120, 120, 120), self.rect, 1)
        if self.label:
            lbl = self.font.render(self.label, True, (180, 180, 180))
            surface.blit(lbl, (self.rect.x - lbl.get_width() - 8, self.rect.y + (self.rect.height - lbl.get_height()) // 2))
        txt = self.font.render(self.text, True, 'white')
        surface.blit(txt, (self.rect.x + 6, self.rect.y + (self.rect.height - txt.get_height()) // 2))


class CheckBox:
    """Casilla de verificación."""
    def __init__(self, x, y, size, font, label='', checked=False):
        self.rect = pygame.Rect(x, y, size, size)
        self.font = font
        self.label = label
        self.checked = checked

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked
                return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, (60, 60, 60), self.rect)
        pygame.draw.rect(surface, (120, 120, 120), self.rect, 1)
        if self.checked:
            # Check mark
            pygame.draw.line(surface, 'white', (self.rect.x + 4, self.rect.centery), (self.rect.centerx, self.rect.bottom - 4), 2)
            pygame.draw.line(surface, 'white', (self.rect.centerx, self.rect.bottom - 4), (self.rect.right - 4, self.rect.y + 4), 2)
        if self.label:
            lbl = self.font.render(self.label, True, 'white')
            surface.blit(lbl, (self.rect.right + 8, self.rect.y + (self.rect.height - lbl.get_height()) // 2))


class NewElementDialog:
    """Diálogo para crear un nuevo elemento (tile/item)."""
    def __init__(self, font, small_font, screen_w, screen_h):
        self.font = font
        self.small_font = small_font
        self.visible = False
        # Centrado en pantalla
        w, h = 500, 360
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.rect = pygame.Rect(x, y, w, h)
        self.inputs = {}
        self.result = None
        self._create_fields()

    def _create_fields(self):
        x = self.rect.x + 20
        y = self.rect.y + 60
        spacing = 40
        self.inputs['char'] = InputBox(x, y, 60, 32, self.font, '', 'Char:')
        y += spacing
        self.inputs['name'] = InputBox(x, y, 300, 32, self.font, '', 'Nombre:')
        y += spacing
        self.inputs['image'] = InputBox(x, y, 300, 32, self.font, '', 'Imagen:')
        y += spacing
        self.inputs['rigid'] = CheckBox(x, y, 24, self.font, 'Rígido (colisión)', False)
        y += spacing
        self.inputs['is_item'] = CheckBox(x, y, 24, self.font, 'Es item (inventario)', False)
        y += spacing
        self.inputs['item_type'] = InputBox(x, y, 200, 32, self.font, '', 'Tipo item:')

    def open(self):
        self.visible = True
        for inp in self.inputs.values():
            if hasattr(inp, 'text'):
                inp.text = ''
            if hasattr(inp, 'checked'):
                inp.checked = False
        self.inputs['char'].text = ''
        self.inputs['name'].text = ''
        self.inputs['image'].text = ''
        self.inputs['item_type'].text = ''

    def close(self):
        self.visible = False
        self.result = None

    def handle_event(self, event):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                self.close()
                return True
        # Botones Aceptar/Cancelar
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn_ok = pygame.Rect(self.rect.right - 180, self.rect.bottom - 50, 80, 36)
            btn_cancel = pygame.Rect(self.rect.right - 90, self.rect.bottom - 50, 80, 36)
            if btn_ok.collidepoint(event.pos):
                self._accept()
                return True
            if btn_cancel.collidepoint(event.pos):
                self.close()
                return True
        for inp in self.inputs.values():
            inp.handle_event(event)
        return True

    def _accept(self):
        ch = self.inputs['char'].text.strip()
        if not ch or len(ch) != 1:
            return
        name = self.inputs['name'].text.strip() or ch
        image = self.inputs['image'].text.strip()
        rigid = self.inputs['rigid'].checked
        is_item = self.inputs['is_item'].checked
        item_type = self.inputs['item_type'].text.strip() or name.lower()
        self.result = {
            'char': ch,
            'name': name,
            'image': image,
            'rigid': rigid,
            'is_item': is_item,
            'item_type': item_type
        }
        self.visible = False

    def draw(self, surface):
        if not self.visible:
            return
        # Overlay
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        # Panel
        pygame.draw.rect(surface, (40, 40, 50), self.rect)
        pygame.draw.rect(surface, (100, 100, 120), self.rect, 2)
        title = self.font.render('Nuevo Elemento', True, 'white')
        surface.blit(title, (self.rect.x + (self.rect.width - title.get_width()) // 2, self.rect.y + 16))
        for inp in self.inputs.values():
            inp.draw(surface)
        # Botones
        btn_ok = pygame.Rect(self.rect.right - 180, self.rect.bottom - 50, 80, 36)
        btn_cancel = pygame.Rect(self.rect.right - 90, self.rect.bottom - 50, 80, 36)
        pygame.draw.rect(surface, (60, 120, 60), btn_ok)
        pygame.draw.rect(surface, (120, 60, 60), btn_cancel)
        ok_txt = self.font.render('Aceptar', True, 'white')
        cancel_txt = self.font.render('Cancelar', True, 'white')
        surface.blit(ok_txt, ok_txt.get_rect(center=btn_ok.center))
        surface.blit(cancel_txt, cancel_txt.get_rect(center=btn_cancel.center))


def draw(surface, rooms, current, cx, cy, filename, message, selected, dropdown, new_element_btn, dialog):
    surface.fill('black')
    r = rooms[current]
    bottom_row = W_ROWS - 3  # Fila del borde inferior
    palette_row = W_ROWS - 2  # Fila del desplegable y botones

    # --- Cuadrícula con los tiles ---
    for gy in range(GRID_H):
        for gx in range(GRID_W):
            ch = r['grid'][gy][gx]
            rect = pygame.Rect((gx + 1) * CELL, (gy + 1) * CELL, CELL, CELL)
            if ch in tile_images:
                surface.blit(tile_images[ch], rect)
            if ch in item_images:
                surface.blit(item_images[ch], rect)

    # --- Bordes (áreas de conexión) ---
    for row in range(W_ROWS):
        for col in range(W_COLS):
            if zone_of(col, row) != 'grid':
                pygame.draw.rect(surface, (45, 45, 45), (col * CELL, row * CELL, CELL, CELL))
                pygame.draw.rect(surface, (90, 90, 90), (col * CELL, row * CELL, CELL, CELL), 1)

    # --- Etiquetas de conexiones ---
    c = r['connections']
    top_txt = font.render(f'ARRIBA: {c["up"]}', True, 'white')
    surface.blit(top_txt, top_txt.get_rect(center=(WIDTH // 2, CELL // 2)))
    bottom_txt = font.render(f'ABAJO: {c["down"]}', True, 'white')
    surface.blit(bottom_txt, bottom_txt.get_rect(center=(WIDTH // 2, bottom_row * CELL + CELL // 2)))
    draw_rotated(surface, f'IZQUIERDA: {c["left"]}', small_font, 'white',
                 (CELL // 2, HEIGHT // 2))
    draw_rotated(surface, f'DERECHA: {c["right"]}', small_font, 'white',
                 (WIDTH - CELL // 2, HEIGHT // 2))

    # --- Esquinas ---
    draw_lines(surface, ['SALA', str(current)], small_font, 'yellow', (CELL // 2, CELL // 2))
    dragon_txt = 'SI' if r['dragon'] else 'NO'
    draw_lines(surface, ['DRAGON', dragon_txt], tiny_font, 'yellow', (WIDTH - CELL // 2, CELL // 2))
    draw_lines(surface, ['VISIB', str(r['visibility'])], tiny_font, 'yellow',
               (CELL // 2, bottom_row * CELL + CELL // 2))
    draw_lines(surface, ['S:GRD', 'ESC:SAL'], tiny_font, (180, 180, 180),
               (WIDTH - CELL // 2, bottom_row * CELL + CELL // 2))

    # --- Tipo de recuadro actual y mensajes ---
    zone = zone_of(cx, cy)
    pos = grid_pos(cx, cy)
    if pos is not None:
        gx, gy = pos
        ch = r['grid'][gy][gx]
        tipo_txt = small_font.render(f'TIPO: {TILE_NAMES[ch]}', True, 'white')
        surface.blit(tipo_txt, (CELL + 6, bottom_row * CELL + 6))
    info_txt = small_font.render(
        'ESP: rotar elem  +/-: num  RET: borra  N: sala  L: cargar  S: guardar  Despl: elegir  Nuevo: crear', True,
        (180, 180, 180))
    surface.blit(info_txt, info_txt.get_rect(midright=(WIDTH - CELL - 6, bottom_row * CELL + CELL // 2)))
    if message:
        msg_txt = small_font.render(message, True, (120, 255, 120))
        surface.blit(msg_txt, msg_txt.get_rect(center=(WIDTH // 2, bottom_row * CELL + CELL // 2)))

    # --- Desplegable de elementos + botón Nuevo ---
    # Dibuja el desplegable (lo maneja la clase Dropdown)
    dropdown.draw(surface)
    # Botón "Nuevo elemento"
    pygame.draw.rect(surface, (60, 100, 60), new_element_btn)
    pygame.draw.rect(surface, (120, 180, 120), new_element_btn, 2)
    btn_txt = font.render('Nuevo', True, 'white')
    surface.blit(btn_txt, btn_txt.get_rect(center=new_element_btn.center))
    # Ayuda
    help_txt = tiny_font.render('Click desplegable = elegir  Click mapa = colocar  Nuevo = crear elemento', True, (180, 180, 180))
    surface.blit(help_txt, (new_element_btn.right + 10, palette_row * CELL + (CELL - help_txt.get_height()) // 2))

    # --- Barra del nombre del archivo ---
    file_row = W_ROWS - 1
    pygame.draw.rect(surface, (30, 30, 55), (0, file_row * CELL, WIDTH, CELL))
    pygame.draw.rect(surface, (90, 90, 90), (0, file_row * CELL, WIDTH, CELL), 1)
    cursor_blink = (pygame.time.get_ticks() // 500) % 2 == 0
    cursor_txt = '_' if (zone == 'file' and cursor_blink) else ' '
    archivo_txt = font.render(f'ARCHIVO: {filename}{cursor_txt}', True, 'white')
    surface.blit(archivo_txt, (CELL // 2, file_row * CELL + (CELL - archivo_txt.get_height()) // 2))
    ayuda_txt = small_font.render('Escribe el nombre y pulsa S para guardar', True, (180, 180, 180))
    surface.blit(ayuda_txt, ayuda_txt.get_rect(midright=(WIDTH - CELL // 2, file_row * CELL + CELL // 2)))

    # --- Resaltar la zona editable donde está el cursor ---
    zone_color = (255, 255, 0)
    if zone != 'grid':
        if zone == 'room':
            rect = pygame.Rect(0, 0, CELL, CELL)
        elif zone == 'dragon':
            rect = pygame.Rect(WIDTH - CELL, 0, CELL, CELL)
        elif zone == 'vis':
            rect = pygame.Rect(0, bottom_row * CELL, CELL, CELL)
        elif zone == 'up':
            rect = pygame.Rect(CELL, 0, GRID_W * CELL, CELL)
        elif zone == 'down':
            rect = pygame.Rect(CELL, bottom_row * CELL, GRID_W * CELL, CELL)
        elif zone == 'left':
            rect = pygame.Rect(0, CELL, CELL, GRID_H * CELL)
        elif zone == 'right':
            rect = pygame.Rect(WIDTH - CELL, CELL, CELL, GRID_H * CELL)
        elif zone == 'file':
            rect = pygame.Rect(0, (W_ROWS - 1) * CELL, WIDTH, CELL)
        elif zone == 'palette':
            rect = pygame.Rect(0, (W_ROWS - 2) * CELL, WIDTH, CELL)
        else:
            rect = None
        if rect:
            pygame.draw.rect(surface, zone_color, rect, 3)

    # --- Cursor ---
    # Solo se muestra cuando el cursor está sobre la cuadrícula (mapa)
    if zone == 'grid':
        pygame.draw.rect(surface, (255, 255, 0), (cx * CELL, cy * CELL, CELL, CELL), 3)


def main():
    global gameScreen
    filename = DEFAULT_FILENAME
    rooms = load_world(world_path(filename))
    if not rooms:
        rooms = {0: new_room(0)}
    current = min(rooms)
    cx = GRID_W // 2 + 1
    cy = GRID_H // 2 + 1
    selected = ' '  # Elemento seleccionado (pincel)
    message = ''
    msg_timer = 0

    # --- Registro de elementos personalizados ---
    custom_elements = {}  # char -> dict con name, image, rigid, is_item, item_type, surface

    def get_item_image(ch):
        """Devuelve la superficie de imagen para un char (built-in o custom)."""
        if ch in tile_images:
            return tile_images[ch]
        if ch in item_images:
            return item_images[ch]
        if ch in custom_elements and custom_elements[ch].get('surface'):
            return custom_elements[ch]['surface']
        return None

    def get_item_name(ch):
        """Devuelve el nombre para un char."""
        if ch in TILE_NAMES:
            return TILE_NAMES[ch]
        if ch in custom_elements:
            return custom_elements[ch].get('name', ch)
        return ch

    def load_custom_image(path):
        """Carga una imagen desde ruta relativa a assets/images/."""
        try:
            full = os.path.join('assets', 'images', path)
            if not os.path.exists(full):
                full = path  # ruta absoluta o relativa al cwd
            img = pygame.image.load(full).convert_alpha()
            return img
        except Exception as e:
            print(f'Error cargando imagen {path}: {e}')
            return None

    # --- Elementos disponibles para el desplegable (built-in + custom) ---
    def build_item_list():
        items = list(TILE_TYPES)
        for ch in custom_elements:
            if ch not in items:
                items.append(ch)
        return items

    # --- UI: desplegable, botón nuevo, diálogo ---
    dropdown_x = PALETTE_START * CELL
    dropdown_y = (W_ROWS - 2) * CELL + (CELL - 36) // 2
    dropdown_w = 260
    dropdown_h = 36
    dropdown = Dropdown(dropdown_x, dropdown_y, dropdown_w, dropdown_h,
                        font, small_font, build_item_list(), get_item_image, get_item_name)
    # Sincroniza selected_index con 'selected'
    def sync_dropdown_selection():
        try:
            dropdown.selected_index = dropdown.items.index(selected)
        except ValueError:
            dropdown.selected_index = 0

    new_element_btn = pygame.Rect(dropdown_x + dropdown_w + 16, dropdown_y, 100, 36)
    dialog = NewElementDialog(font, small_font, WIDTH, HEIGHT)

    def adjust_value(step):
        """Aplica +step al valor numérico de la zona del cursor.
        Equivale a pulsar '+' (step=1) o '-' (step=-1)."""
        nonlocal current
        if zone == 'room':
            if step > 0:
                new_num = current + 1
                if new_num not in rooms:
                    rooms[new_num] = new_room(new_num)
                current = new_num
            elif current > 0:
                current -= 1
        elif zone in ('up', 'down', 'left', 'right'):
            rooms[current]['connections'][zone] += step
            if rooms[current]['connections'][zone] < -1:
                rooms[current]['connections'][zone] = -1
        elif zone == 'vis':
            rooms[current]['visibility'] = max(100, rooms[current]['visibility'] + step * 100)

    running = True
    while running:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                # El cursor sigue al ratón
                cx, cy = mouse_to_cell(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 1. Diálogo modal tiene prioridad
                if dialog.visible:
                    dialog.handle_event(event)
                    if dialog.result:
                        # Nuevo elemento creado
                        data = dialog.result
                        ch = data['char']
                        custom_elements[ch] = data
                        img = load_custom_image(data['image'])
                        if img:
                            custom_elements[ch]['surface'] = img
                        # Actualiza lista del desplegable
                        dropdown.items = build_item_list()
                        sync_dropdown_selection()
                        selected = dropdown.selected
                        dialog.result = None
                    continue

                # 2. Desplegable
                if dropdown.handle_event(event, event.pos):
                    selected = dropdown.selected
                    continue

                # 3. Botón "Nuevo elemento"
                if new_element_btn.collidepoint(event.pos):
                    dialog.open()
                    continue

                # 4. Resto: zonas del mapa
                zone = zone_of(cx, cy)
                if event.button == 1:
                    if zone == 'grid':
                        pos = grid_pos(cx, cy)
                        if pos is not None:
                            gx, gy = pos
                            r = rooms[current]
                            row = list(r['grid'][gy])
                            row[gx] = selected
                            r['grid'][gy] = ''.join(row)
                    elif zone in ('room', 'up', 'down', 'left', 'right', 'vis'):
                        adjust_value(1)
                elif event.button == 3:
                    if zone in ('room', 'up', 'down', 'left', 'right', 'vis'):
                        adjust_value(-1)
            elif event.type == pygame.KEYDOWN:
                zone = zone_of(cx, cy)

                # Movimiento: siempre disponible
                if event.key == pygame.K_LEFT:
                    cx = max(0, cx - 1)
                elif event.key == pygame.K_RIGHT:
                    cx = min(W_COLS - 1, cx + 1)
                elif event.key == pygame.K_UP:
                    cy = max(0, cy - 1)
                elif event.key == pygame.K_DOWN:
                    cy = min(W_ROWS - 1, cy + 1)
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11:
                    toggle_fullscreen()
                elif zone == 'file':
                    # Entrada de texto para el nombre del archivo
                    if event.key == pygame.K_BACKSPACE:
                        filename = filename[:-1]
                    else:
                        ch = getattr(event, 'unicode', '') or ''
                        if ch and ch.isprintable():
                            filename += ch
                elif event.key == pygame.K_RETURN or event.key == pygame.K_BACKSPACE:
                    pos = grid_pos(cx, cy)
                    if pos is not None:
                        gx, gy = pos
                        r = rooms[current]
                        row = list(r['grid'][gy])
                        row[gx] = ' '
                        r['grid'][gy] = ''.join(row)
                    elif zone in ('up', 'down', 'left', 'right'):
                        rooms[current]['connections'][zone] = -1
                    elif zone == 'dragon':
                        rooms[current]['dragon'] = False
                    elif zone == 'vis':
                        rooms[current]['visibility'] = 1000
                elif event.key == pygame.K_SPACE:
                    if zone == 'dragon':
                        rooms[current]['dragon'] = not rooms[current]['dragon']
                    else:
                        # Cicla el elemento seleccionado usando la lista completa del desplegable
                        items = dropdown.items
                        if items:
                            idx = (items.index(selected) + 1) % len(items)
                            selected = items[idx]
                            sync_dropdown_selection()
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    adjust_value(1)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    adjust_value(-1)
                elif event.key == pygame.K_n:
                    new_num = max(rooms) + 1
                    rooms[new_num] = new_room(new_num)
                    current = new_num
                    message = f'Sala {new_num} creada'
                    msg_timer = 2000
                elif event.key == pygame.K_l:
                    path = world_path(filename)
                    rooms = load_world(path)
                    if not rooms:
                        rooms = {0: new_room(0)}
                    if current not in rooms:
                        current = min(rooms)
                    message = f'Cargado: {path}'
                    msg_timer = 2000
                elif event.key == pygame.K_s:
                    path = world_path(filename)
                    n = save_world(path, rooms)
                    message = f'Guardado ({path}): {n} salas'
                    msg_timer = 2000

        if msg_timer > 0:
            msg_timer -= clock.get_time()
            if msg_timer <= 0:
                message = ''

        # Dibuja la escena en la superficie interna fija y la escala a la ventana
        draw(render_surface, rooms, current, cx, cy, filename, message, selected,
             dropdown, new_element_btn, dialog)
        scaled = pygame.transform.scale(render_surface, gameScreen.get_size())
        gameScreen.blit(scaled, (0, 0))
        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
