#!/usr/bin/env python3
import pygame
from pygame import mixer
import math # Necesario para la IA de persecución
import random # Necesario para la reaparición aleatoria
import sys # Para poder importar desde subcarpetas
import os # Para listar los archivos de mundos
import importlib.util # Para cargar mundos en tiempo de ejecución
import xml.etree.ElementTree as ET # Para guardar y cargar la configuración del usuario (XML)
from PIL import Image # Necesario para cargar frames de GIFs
sys.path.append('worlds') # Añade la carpeta de datos al path
# La definición de elementos vive en core/
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core'))
pygame.init()
# --- Carga de la definición de elementos desde core/elements.json ---
import elements
ELEMENTS = elements.ELEMENTS
GAME_RULES = elements.GAME_RULES
# Constantes derivadas de las reglas del JSON
FLEE_ITEMS = set(GAME_RULES.get('dragon', {}).get('flees_if_hero_has', []))
VICTORY = GAME_RULES.get('victory', {})
START_HEALTH = GAME_RULES.get('hero', {}).get('start_health', 4)
START_ROOM = GAME_RULES.get('hero', {}).get('start_room', 0)
# El import de atari_2600_world_1 debe estar después de la definición de constantes si las usa
from atari_2600_world_1 import *

mixer.init()

# Configuración del usuario en XML, dentro de ~/.config/adventure2026/
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config', 'adventure2026')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.xml')
DEFAULT_CONFIG = {'fullscreen': False, 'volume': 0.2}

def load_config():
    """Carga la configuración XML guardada, completando los valores que falten."""
    config = dict(DEFAULT_CONFIG)
    raw = {}
    try:
        root = ET.parse(CONFIG_PATH).getroot()
        for key, default in DEFAULT_CONFIG.items():
            node = root.find(key)
            if node is None or node.text is None:
                continue
            text = node.text.strip()
            # Convierte el texto XML al tipo del valor por defecto
            if isinstance(default, bool):
                raw[key] = text.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(default, int):
                raw[key] = int(text)
            elif isinstance(default, float):
                raw[key] = float(text)
            else:
                raw[key] = text
        config.update(raw)
    except Exception:
        raw = {}
    # Si faltan claves nuevas (añadidas a DEFAULT_CONFIG), las escribe
    if set(DEFAULT_CONFIG) - set(raw):
        save_config(config)
    return config

def save_config(config):
    """Guarda la configuración en un archivo XML en ~/.config/adventure2026/."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        root = ET.Element('config')
        for key, value in config.items():
            node = ET.SubElement(root, key)
            if isinstance(value, bool):
                node.text = 'true' if value else 'false'
            else:
                node.text = str(value)
        ET.ElementTree(root).write(CONFIG_PATH, encoding='utf-8', xml_declaration=True)
    except Exception:
        pass

CELL    =   64  #80
HERO_WIDTH    =   64
HERO_COLLISION_WIDTH = 54 # Un poco menos que CELL para pasar por huecos
HERO_HEIGHT   =   128
HERO_COLLISION_HEIGHT = 64
WIDTH   =   CELL*20 #1280
TOP_BAR_HEIGHT = CELL
GAME_HEIGHT = 13*CELL # Altura del área de juego
BOTTOM_BAR_HEIGHT = CELL
SCREEN_HEIGHT = TOP_BAR_HEIGHT + GAME_HEIGHT + BOTTOM_BAR_HEIGHT # Altura total de la ventana (512)
HEIGHT = SCREEN_HEIGHT
PLAYER_SPEED = 10
BOUNCE_BACK_AMOUNT = 10 # Pixeles para rebotar hacia atrás en caso de colisión

# --- Constantes para la animación del héroe ---
ANIMATION_INTERVAL = 100 # Milisegundos entre cada frame de animación
STEP_SOUND_INTERVAL = 180 # Milisegundos entre cada sonido de paso

# Estructura para la animación del héroe
HERO_ANIMATIONS = {
    'right': {'start_frame': 0, 'num_frames': 4},
    'left':  {'start_frame': 4, 'num_frames': 4},
    'up':    {'start_frame': 8, 'num_frames': 2},
    'down':  {'start_frame': 10, 'num_frames': 2}
}

# --- Constantes para la animación del dragón ---
DRAGON_ANIMATION_INTERVAL = 200 # Milisegundos entre cada frame de animación
KNOCKBACK_DISTANCE = 300 # Píxeles que se aleja el dragón al golpear al héroe
HERO_KNOCKBACK_DISTANCE = 80 # Píxeles que rebota el héroe al recibir un golpe del dragón
DRAGON_FROZEN_MS = 1000 # Milisegundos que el dragón queda inmóvil tras golpear al héroe
HIT_COOLDOWN_MS = 3000 # Milisegundos de inmunidad tras recibir un golpe del dragón

# --- Constantes para la animación de apertura de puertas ---
DOOR_SLIDE_SPEED = 3 # Píxeles por frame que se desliza la puerta al abrirse

config = load_config()
is_fullscreen = config.get('fullscreen', False)
# Distancia objetivo a la que el dragón trata de mantenerse respecto al héroe
DRAGON_ORBIT_DISTANCE = 500
DRAGON_ORBIT_TOLERANCE = 40  # Rango ± alrededor del objetivo antes de corregir
# Distancia inicial a la que aparece el dragón (en un ángulo aleatorio)
DRAGON_SPAWN_DISTANCE = 2000
gameScreen  =   pygame.display.set_mode((WIDTH,SCREEN_HEIGHT), pygame.FULLSCREEN if is_fullscreen else 0)
pygame.display.set_caption('Adventure 2024 - FanMade')
pygame_icon = pygame.image.load('assets/images/atari_icon_32.png')
pygame.display.set_icon(pygame_icon)
gameClock   =   pygame.time.Clock()

def toggle_fullscreen():
    """Alterna entre pantalla completa y modo ventana con F11."""
    global gameScreen, is_fullscreen
    is_fullscreen = not is_fullscreen
    config['fullscreen'] = is_fullscreen
    save_config(config) # Recuerda la configuración para la próxima vez
    flags = pygame.FULLSCREEN if is_fullscreen else 0
    gameScreen = pygame.display.set_mode((WIDTH, SCREEN_HEIGHT), flags)
# --- Pantalla de inicio ---
landing_image = pygame.image.load('assets/images/adventure_intro2.png').convert_alpha()
landing_rect = landing_image.get_rect(center=gameScreen.get_rect().center)
gameScreen.blit(landing_image, landing_rect)
pygame.display.flip()
pygame.time.wait(2000)

# --- Inicialización del temporizador y la fuente ---
start_time = pygame.time.get_ticks()
font = pygame.font.Font(None, 50) # Fuente para los contadores

# --- Carga de Sonidos ---
# (Asegúrate de tener un archivo de sonido para la derrota del dragón)
sfx_step = mixer.Sound('assets/sounds/sfx_step.wav')
sfx_step.set_volume(config.get('volume', 0.2))
sfx_dragon_death = mixer.Sound('assets/sounds/sfx_dragon_death.wav') 
sfx_dragon_attack = mixer.Sound('assets/sounds/sfx_dragon_attack.wav')
sfx_hero_death = mixer.Sound('assets/sounds/sfx_hero_death.wav')
sfx_take = mixer.Sound('assets/sounds/sfx_take.wav')
sfx_win = mixer.Sound('assets/sounds/sfx_win.wav')
sfx_door_open = mixer.Sound('assets/sounds/sfx_door_open.wav')
# --- Carga de imágenes de tiles/items desde elements.json ---
tile_images, item_images = elements.build_element_surfaces()
# --- Frames de los elementos animados (p. ej. el agua que gira 90° cada 250 ms) ---
ANIMATED = elements.build_animations()

# --- Carga de imagen de Game Over ---
gameover_image = pygame.image.load('assets/images/game_over_win.png').convert_alpha()

# --- Imagen de la muerte del dragón (aparece al derrotarlo y se desvanece) ---
dragon_death_image = pygame.image.load('assets/images/dragon_death.png').convert_alpha()
dragon_icon_image = pygame.image.load('assets/images/dragon_icon.png').convert_alpha()
# --- Imágenes para la barra de vida del héroe ---
heart_full_image = pygame.image.load('assets/images/heart_full.png').convert_alpha()
heart_empty_image = pygame.image.load('assets/images/heart_empty.png').convert_alpha()


def load_gif_frames(path):
    """Carga los frames de un archivo GIF y los convierte a superficies de Pygame."""
    try:
        gif = Image.open(path)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo GIF en '{path}'")
        return []
    frames = []
    try:
        while True:
            # Convertir el frame de PIL a una superficie de Pygame
            frame_rgba = gif.convert("RGBA")
            pygame_image = pygame.image.fromstring(frame_rgba.tobytes(), frame_rgba.size, frame_rgba.mode).convert_alpha()
            frames.append(pygame_image)
            gif.seek(gif.tell() + 1) # Mover al siguiente frame
    except EOFError:
        pass # Fin de los frames
    return frames

def build_map_surface(map_data, hero):
    """Crea una superficie pre-renderizada del mapa y una lista de rects de colisión."""
    map_surface = pygame.Surface((WIDTH, GAME_HEIGHT))
    collision_rects = []
    door_rects = [] # Nueva lista para las puertas
    item_rects = []
    animated_rects = [] # Celdas de elementos animados (p. ej. agua)
    processed_coords = set() # Para evitar procesar celdas ocupadas por objetos grandes
    x, y = 0, 0 # Dibuja en la superficie local desde (0,0)
    for row_idx, row in enumerate(map_data):
        for col_idx, cell_char in enumerate(row):
            if (row_idx, col_idx) in processed_coords:
                x += CELL
                continue

            # Dibuja el tile base. Si el elemento define draws_under (items, agua),
            # se dibuja ese tile debajo; si no, el propio elemento.
            base_char = elements.draws_under(cell_char) or cell_char
            if base_char in tile_images:
                map_surface.blit(tile_images[base_char], (x, y))

            # Gestiona colisiones y objetos especiales según el tipo del elemento
            kind = elements.kind_of(cell_char)
            if cell_char in ANIMATED: # Elemento animado: no se hornea en el mapa estático
                animated_rects.append({'char': cell_char, 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
                if elements.solid(cell_char):
                    collision_rects.append(pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL))
            elif kind == 'terrain' and elements.solid(cell_char): # Muros (roca, madera, ventana...)
                collision_rects.append(pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL))
            elif kind == 'door': # Las puertas van a su propia lista
                door_rects.append({'char': cell_char, 'key_char': elements.door_opens_with(cell_char), 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif kind in ('key', 'item') and elements.key_inventory_id(cell_char) not in hero['inventory']:
                item_rects.append({'type': elements.key_inventory_id(cell_char), 'char': cell_char, 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif kind == 'altar':
                size_w, size_h = elements.element_size(cell_char)
                # Dibuja un fondo de hierba de size×size para el altar
                for r_offset in range(size_h):
                    for c_offset in range(size_w):
                        map_surface.blit(tile_images[' '], (x + c_offset * CELL, y + r_offset * CELL))
                altar_rect = pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL * size_w, CELL * size_h)
                item_rects.append({'type': 'altar', 'char': cell_char, 'rect': altar_rect})
                collision_rects.append(altar_rect) # El altar vuelve a ser una colisión sólida
                # Marca las celdas que ocupa el altar como ya procesadas
                for r_offset in range(size_h):
                    for c_offset in range(size_w):
                        # Asegúrate de no salirte de los límites del mapa si el altar está en un borde
                        if row_idx + r_offset < len(map_data) and col_idx + c_offset < len(map_data[0]):
                            processed_coords.add((row_idx + r_offset, col_idx + c_offset))

            x += CELL
        x = 0
        y += CELL
    return map_surface, collision_rects, item_rects, door_rects, animated_rects

def update_player(player, collision_rects, door_rects, current_map_data, dt):
    """Maneja la entrada, movimiento, animación y colisión del jugador."""
    dx = 0
    dy = 0
    moved = False
    input_dx = 0 # Movimiento deseado por el jugador en X
    input_dy = 0 # Movimiento deseado por el jugador en Y
    moved_by_keys = False # Indica si se presionaron teclas de movimiento

    keys = pygame.key.get_pressed()
    if keys[pygame.K_UP]:
        dy -= PLAYER_SPEED
        input_dy -= PLAYER_SPEED
        player['direction'] = 'up'
        moved = True
        moved_by_keys = True
    if keys[pygame.K_DOWN]:
        dy += PLAYER_SPEED
        input_dy += PLAYER_SPEED
        player['direction'] = 'down'
        moved = True
        moved_by_keys = True
    if keys[pygame.K_LEFT]:
        dx -= PLAYER_SPEED
        input_dx -= PLAYER_SPEED
        player['direction'] = 'left'
        moved = True
        moved_by_keys = True
    if keys[pygame.K_RIGHT]:
        dx += PLAYER_SPEED
        input_dx += PLAYER_SPEED
        player['direction'] = 'right'
        moved = True
        moved_by_keys = True

    # --- Animación basada en tiempo ---
    if moved_by_keys: # Solo animar si se están presionando teclas de movimiento
        player['animation_timer'] += dt
        if player['animation_timer'] >= ANIMATION_INTERVAL:
            player['animation_timer'] = 0
            anim_info = HERO_ANIMATIONS[player['direction']]
            # Avanza el frame dentro del ciclo de la animación actual
            player['frame_index'] = (player['frame_index'] + 1) % anim_info['num_frames']
            # Calcula el índice global en la lista de imágenes
            image_index = anim_info['start_frame'] + player['frame_index']
            player['image'] = player['images'][image_index]
    else: # Si no se mueve, resetea al primer frame de la dirección actual
        player['frame_index'] = 0
        player['image'] = player['images'][HERO_ANIMATIONS[player['direction']]['start_frame']]

    # Guarda la posición original para posibles rebotes
    original_player_x = player['rect'].x
    original_player_y = player['rect'].y

    opened_doors = set() # Chars de puerta que el héroe puede abrir
    collided_on_x = False
    collided_on_y = False

    # --- Intento de movimiento en X ---
    player['rect'].x += dx
    
    # --- Crea un rect de colisión para la parte inferior del jugador ---
    # El rect de colisión es más pequeño que el rect de dibujado
    current_collision_rect = pygame.Rect(
        player['rect'].centerx - HERO_COLLISION_WIDTH // 2, # Centra la caja de colisión
        player['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT),
        HERO_COLLISION_WIDTH,
        HERO_COLLISION_HEIGHT
    )

    # Comprueba colisión con muros impenetrables en X
    if current_collision_rect.collidelist(collision_rects) != -1:
        collided_on_x = True

    # Comprueba colisión con puertas en X
    for door_rect in door_rects:
        if current_collision_rect.colliderect(door_rect['rect']):
            door_key = elements.key_inventory_id(door_rect['key_char'])
            if door_key in player['inventory']:
                # Si tiene la llave correcta, notifica al bucle principal
                opened_doors.add(door_rect['char'])
            else:
                # Si no tiene la llave, la puerta actúa como un muro.
                collided_on_x = True

    if collided_on_x:
        player['rect'].x = original_player_x # Revertir movimiento en X
        # Aplicar rebote en la dirección opuesta al intento de movimiento
        if dx > 0: # Intentó moverse a la derecha
            player['rect'].x -= BOUNCE_BACK_AMOUNT
        elif dx < 0: # Intentó moverse a la izquierda
            player['rect'].x += BOUNCE_BACK_AMOUNT

    # --- Intento de movimiento en Y ---
    player['rect'].y += dy
    
    # Crea el rect de colisión para la parte inferior del jugador en la nueva posición Y
    current_collision_rect = pygame.Rect(
        player['rect'].centerx - HERO_COLLISION_WIDTH // 2,
        player['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT),
        HERO_COLLISION_WIDTH,
        HERO_COLLISION_HEIGHT
    )

    # Comprueba colisión con muros impenetrables en Y
    if current_collision_rect.collidelist(collision_rects) != -1:
        collided_on_y = True

    # Comprueba colisión con puertas en Y (se repite por si el movimiento fue solo vertical)
    for door_rect in door_rects:
        if current_collision_rect.colliderect(door_rect['rect']):
            door_key = elements.key_inventory_id(door_rect['key_char'])
            if door_key in player['inventory']:
                opened_doors.add(door_rect['char'])
            else:
                collided_on_y = True

    if collided_on_y:
        player['rect'].y = original_player_y # Revertir movimiento en Y
        # Aplicar rebote en la dirección opuesta al intento de movimiento
        if dy > 0: # Intentó moverse hacia abajo
            player['rect'].y -= BOUNCE_BACK_AMOUNT
        elif dy < 0: # Intentó moverse hacia arriba
            player['rect'].y += BOUNCE_BACK_AMOUNT

    # --- Sonido de Pasos ---
    # El sonido solo se reproduce si el jugador se ha movido y no ha colisionado en ninguno de los ejes.
    if moved and not (collided_on_x or collided_on_y):
        player['step_sound_timer'] += dt
        if moved and player['step_sound_timer'] > STEP_SOUND_INTERVAL:
            sfx_step.play()
            player['step_sound_timer'] = 0 # Reinicia el temporizador

    return opened_doors

def update_dragon(dragon, player, dt):
    """Gestiona la posición y animación del dragón (posición real con lag).

    El dragón guarda su posición real (x, y). Cada frame calcula la separación
    respecto al héroe y avanza a su propia velocidad (dragon['speed']) hacia el
    radio deseado. Como el héroe es más rápido, puede dejarlo atrás: la distancia
    real puede superar 500 px pero nunca el máximo DRAGON_SPAWN_DISTANCE (2000) px.
    Sin espada el dragón se acerca hasta colisionar; con espada tiende a
    DRAGON_ORBIT_DISTANCE (500) px. Tras golpear al héroe queda congelado
    DRAGON_FROZEN_MS. Devuelve False."""
    # --- Animación ---
    dragon['animation_timer'] += dt
    if dragon['animation_timer'] >= DRAGON_ANIMATION_INTERVAL:
        dragon['animation_timer'] -= DRAGON_ANIMATION_INTERVAL
        # Elige la lista de imágenes correcta según la dirección
        current_images = dragon['images_l'] if dragon['direction'] == 'left' else dragon['images_r']
        dragon['frame_index'] = (dragon['frame_index'] + 1) % len(current_images)
        dragon['image'] = current_images[dragon['frame_index']]

    # Congelado tras golpear al héroe: no se mueve durante DRAGON_FROZEN_MS
    if pygame.time.get_ticks() < dragon.get('frozen_until', 0):
        return False

    # Separación real héroe -> dragón
    dx = dragon['x'] - player['rect'].centerx
    dy = dragon['y'] - player['rect'].centery
    radius = math.hypot(dx, dy)
    if radius > 1:
        angle = math.atan2(dy, dx)
        dir_x = dx / radius
        dir_y = dy / radius
    else:
        angle, dir_x, dir_y = 0.0, 1.0, 0.0

    # Velocidad de desplazamiento del dragón (px/s), respetando dragon['speed']
    speed_px_per_sec = dragon['speed'] * 60
    target_speed = speed_px_per_sec * (dt / 1000)

    if FLEE_ITEMS & set(player['inventory']):
        # Con la espada: mantener el radio objetivo (~500 px)
        if radius < DRAGON_ORBIT_DISTANCE - DRAGON_ORBIT_TOLERANCE:
            # Demasiado cerca: se aleja del héroe (dir apunta hacia afuera)
            pass
        elif radius > DRAGON_ORBIT_DISTANCE + DRAGON_ORBIT_TOLERANCE:
            # Demasiado lejos: se acerca al héroe (dirección contraria)
            dir_x, dir_y = -dir_x, -dir_y
        else:
            # Dentro del objetivo: orbita (movimiento tangencial)
            orbit_dir = dragon.get('orbit_dir', 1)
            tx, ty = -dir_y, dir_x
            dir_x, dir_y = tx * orbit_dir, ty * orbit_dir
    else:
        # Sin la espada: se acerca al centro hasta colisionar (dirección contraria)
        dir_x, dir_y = -dir_x, -dir_y

    # Avanza a su velocidad real (puede quedarse atrás si el héroe es más rápido)
    dragon['x'] += dir_x * target_speed
    dragon['y'] += dir_y * target_speed

    # Tope: nunca supera el radio máximo del círculo alrededor del héroe
    dx = dragon['x'] - player['rect'].centerx
    dy = dragon['y'] - player['rect'].centery
    radius = math.hypot(dx, dy)
    if radius > DRAGON_SPAWN_DISTANCE:
        scale = DRAGON_SPAWN_DISTANCE / radius
        dragon['x'] = player['rect'].centerx + dx * scale
        dragon['y'] = player['rect'].centery + dy * scale

    # El dragón mira hacia el héroe: dragon_l si el héroe está a su izquierda,
    # dragon_r si el héroe está a su derecha.
    if dragon['x'] - player['rect'].centerx > 0:
        dragon['direction'] = 'left'
    elif dragon['x'] - player['rect'].centerx < 0:
        dragon['direction'] = 'right'

    dragon['radius'] = math.hypot(dragon['x'] - player['rect'].centerx,
                                   dragon['y'] - player['rect'].centery)
    dragon['orbit_angle'] = math.atan2(dragon['y'] - player['rect'].centery,
                                        dragon['x'] - player['rect'].centerx)
    sync_dragon_rect(dragon)
    return False


def play_dragon_death_sequence(screen, dragon, hero, map_surface, animated_rects, item_rects, opening_doors, start_time):
    """Muestra la imagen de muerte del dragón unos segundos y la desvanece
    lentamente, manteniendo al héroe visible y controlable en la escena.
    Devuelve False solo si el jugador cierra la ventana."""
    # Imagen de muerte escalada al tamaño del rect del dragón
    death_img = pygame.transform.scale(dragon_death_image,
                                       (dragon['rect'].width, dragon['rect'].height))
    hold_ms = 1200  # Tiempo mostrando la imagen estática
    fade_ms = 1500  # Duración del desvanecimiento
    start = pygame.time.get_ticks()

    while True:
        dt = gameClock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        elapsed = pygame.time.get_ticks() - start

        screen.fill('black')
        # --- Dibuja la escena completa (copiado del bucle principal) ---
        screen.blit(map_surface, (0, TOP_BAR_HEIGHT))
        if animated_rects:
            for anim_rect in animated_rects:
                anim = ANIMATED.get(anim_rect['char'])
                if anim:
                    frames = anim['frames']
                    frame = frames[(pygame.time.get_ticks() // anim['interval_ms']) % len(frames)]
                    screen.blit(frame, anim_rect['rect'])
        for item in item_rects:
            img = item_images.get(item['type'])
            if img:
                screen.blit(img, item['rect'])
        screen.blit(hero['image'], hero['rect'])
        door_img_copy = tile_images['D'].copy()
        for door in opening_doors:
            direction = -1 if door['rect'].centerx < WIDTH // 2 else 1
            sliding_rect = door['rect'].move(direction * door['slide'], 0)
            screen.blit(door_img_copy, sliding_rect)

        draw_visibility_fog(screen, hero, maps[currentMap][3])
        # --- Fin del dibujado de la escena ---


        if elapsed < hold_ms:
            screen.blit(death_img, dragon['rect'].topleft)
        else:
            # Fase de desvanecimiento progresivo
            fade_elapsed = elapsed - hold_ms
            alpha = max(0, 255 * (1 - fade_elapsed / fade_ms))
            if alpha <= 0:
                break
            fading = death_img.copy()
            fading.set_alpha(int(alpha))
            screen.blit(fading, dragon['rect'].topleft)

        # --- Dibuja la UI (copiado del bucle principal) ---
        pygame.draw.rect(screen, 'black', (0, TOP_BAR_HEIGHT + GAME_HEIGHT, WIDTH, BOTTOM_BAR_HEIGHT))
        inventory_x_offset = 10
        for inv_id in item_images:
            if inv_id in hero['inventory']:
                img = item_images[inv_id]
                screen.blit(img, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - img.get_height()) // 2))
                inventory_x_offset += img.get_width() + 10

        pygame.draw.rect(screen, 'black', (0, 0, WIDTH, TOP_BAR_HEIGHT))
        hearts_to_draw = GAME_RULES.get('hero', {}).get('max_health', 3)
        heart_gap = 10
        heart_y = (TOP_BAR_HEIGHT - heart_full_image.get_height()) // 2
        for i in range(hearts_to_draw):
            heart_x = 10 + i * (heart_full_image.get_width() + heart_gap)
            if i < hero['health']:
                screen.blit(heart_full_image, (heart_x, heart_y))
            else:
                screen.blit(heart_empty_image, (heart_x, heart_y))

        elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
        minutes = elapsed_time // 60
        seconds = elapsed_time % 60
        time_text = font.render(f"{minutes:02}:{seconds:02}", True, 'white')
        screen.blit(time_text, time_text.get_rect(centerx=WIDTH // 2, centery=TOP_BAR_HEIGHT // 2))

        dragon_count_text = font.render(f"x {hero['dragons_killed']}", True, 'white')
        screen.blit(dragon_icon_image, (WIDTH - 130, (TOP_BAR_HEIGHT - dragon_icon_image.get_height()) // 2))
        screen.blit(dragon_count_text, (WIDTH - 60, (TOP_BAR_HEIGHT - dragon_count_text.get_height()) // 2))
        # --- Fin del dibujado de la UI ---

        pygame.display.flip()
    return True


def _initialize_game_state(hero, dragon):
    """Inicializa o resetea el estado del héroe, dragón y mapa al valor por defecto."""
    currentMap = START_ROOM
    hero["rect"].center = (WIDTH / 2, TOP_BAR_HEIGHT + GAME_HEIGHT - CELL * 2.5)
    hero["direction"] = 'right'
    hero["frame_index"] = 0
    hero["inventory"] = []
    hero["dragons_killed"] = 0
    hero["health"] = START_HEALTH
    hero["last_damage_time"] = 0
    hero["image"] = hero['images'][0]

    dragon["speed"] = 4.0
    dragon["frame_index"] = 0
    dragon["direction"] = 'right'
    dragon["image"] = dragon['images_r'][0]
    dragon["frozen_until"] = 0
    spawn_dragon(dragon, hero)

    map_surface, collision_rects, item_rects, door_rects, animated_rects = build_map_surface(maps[currentMap][1], hero)
    start_time = pygame.time.get_ticks()
    return currentMap, map_surface, collision_rects, item_rects, door_rects, animated_rects, start_time

def reset_game_state(hero, dragon, show_transition=True):
    """Resetea el estado del juego. Con show_transition=True muestra
    una pantalla negra de 2 segundos (para la derrota); con False
    reinicia al instante (para el reinicio manual con F2)."""
    if show_transition:
        # Muestra una pantalla negra para indicar la derrota
        gameScreen.fill('black')
        pygame.display.flip()
        pygame.time.wait(2000)

    return _initialize_game_state(hero, dragon)

def list_world_files():
    """Devuelve la lista de archivos de mundo (.py) disponibles en la carpeta worlds."""
    try:
        files = os.listdir('worlds')
        return sorted(f for f in files if f.endswith('.py') and not f.startswith('__'))
    except Exception:
        return []


def load_world_file(filename):
    """Carga un mundo desde la carpeta worlds y reinicia la partida."""
    global maps, currentMap, map_surface, collision_rects, item_rects, door_rects, animated_rects
    global start_time, opening_doors
    path = os.path.join('worlds', filename)
    try:
        spec = importlib.util.spec_from_file_location('loaded_world', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        new_maps = mod.maps
    except Exception:
        return False

    maps = new_maps
    opening_doors = []
    currentMap, map_surface, collision_rects, item_rects, door_rects, animated_rects, start_time = _initialize_game_state(hero, dragon)
    return True


def show_world_select_menu(screen):
    """Muestra un submenú para elegir y cargar un mundo."""
    world_files = list_world_files()
    if not world_files:
        return False
    title_font = pygame.font.Font(None, 60)
    option_font = pygame.font.Font(None, 36)
    title_text = title_font.render('CARGAR MUNDO', True, 'white')
    selected = 0

    while True:
        overlay = pygame.Surface((WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))
        screen.blit(title_text, title_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 160)))

        # Dibuja las opciones y guarda sus rects para el ratón
        start_y = HEIGHT / 2 - 90
        option_rects = []
        for i, f in enumerate(world_files):
            color = 'yellow' if i == selected else 'white'
            txt = option_font.render(f, True, color)
            rect = txt.get_rect(center=(WIDTH / 2, start_y + i * 40))
            screen.blit(txt, rect)
            option_rects.append(rect)

        click = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return 'quit'
            if event.type == pygame.MOUSEMOTION:
                for i, r in enumerate(option_rects):
                    if r.collidepoint(event.pos):
                        selected = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(option_rects):
                    if r.collidepoint(event.pos):
                        selected = i
                        click = i
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False # Volver al menú de pausa
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(world_files)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(world_files)
                elif event.key == pygame.K_RETURN:
                    click = selected

        if click is not None:
            if load_world_file(world_files[click]):
                return True # Mundo cargado
            return False

        pygame.display.flip()
        gameClock.tick(15)


def show_pause_menu(screen):
    """Muestra un menú de pausa y maneja la selección del usuario."""
    # Fuentes y textos del menú
    title_font = pygame.font.Font(None, 80)
    option_font = pygame.font.Font(None, 50)
    title_text = title_font.render('PAUSA', True, 'white')
    selected_option = 0

    paused = True
    while paused:
        # Crea una superficie semi-transparente para el efecto de atenuación
        overlay = pygame.Surface((WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))  # Negro con transparencia
        screen.blit(overlay, (0, 0))

        # La opción de pantalla completa muestra su estado actual
        fs_state = 'ON' if is_fullscreen else 'OFF'
        options = [f"Pantalla Completa: {fs_state}", "Configuración", "Cargar Mundo", "Salir del Juego"]

        # Dibuja el título
        screen.blit(title_text, title_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 - 100)))

        # Dibuja las opciones y guarda sus rects para el ratón
        option_rects = []
        for i, option in enumerate(options):
            color = 'yellow' if i == selected_option else 'white'
            option_text = option_font.render(option, True, color)
            option_rect = option_text.get_rect(center=(WIDTH / 2, HEIGHT / 2 + i * 60))
            screen.blit(option_text, option_rect)
            option_rects.append(option_rect)

        # Actualiza la selección según el ratón
        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate(option_rects):
            if rect.collidepoint(mouse_pos):
                selected_option = i

        click = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True  # Salir si se cierra la ventana
            if event.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(option_rects):
                    if rect.collidepoint(event.pos):
                        selected_option = i
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(option_rects):
                    if rect.collidepoint(event.pos):
                        selected_option = i
                        click = i
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False  # Salir del menú y volver al juego
                elif event.key == pygame.K_UP:
                    selected_option = (selected_option - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected_option = (selected_option + 1) % len(options)
                elif event.key == pygame.K_RETURN:
                    click = selected_option

        if click is not None:
            if click == 0: # Pantalla Completa
                toggle_fullscreen()
                screen = gameScreen  # Seguir usando la nueva ventana
            elif click == 1: # Configuración
                # Por ahora, esta opción no hace nada.
                # En el futuro, aquí se podría llamar a una función show_settings_menu().
                pass
            elif click == 2: # Cargar Mundo
                result = show_world_select_menu(screen)
                if result == 'quit':
                    return True # Salir del juego
                elif result is True:
                    return False # Mundo cargado: volver al juego
            elif click == 3: # Salir del Juego
                return True

        pygame.display.flip()
        gameClock.tick(15) # Limita los FPS en el menú para no consumir recursos innecesariamente

def draw_visibility_fog(screen, hero, visibility_radius):
    """Dibuja una capa de "niebla de guerra" con un círculo de visión alrededor del héroe."""
    if visibility_radius >= 1000: # Si la visibilidad es "infinita", no dibujes niebla
        return

    # Crea una superficie para la niebla del tamaño del área de juego
    fog_surface = pygame.Surface((WIDTH, GAME_HEIGHT), pygame.SRCALPHA)
    # Llena la superficie con negro sólido
    fog_surface.fill((0, 0, 0, 255))

    # --- Lógica para el borde difuso ---
    blur_steps = 64 # Cuantos más pasos, más suave pero más costoso en rendimiento
    hero_center_x = hero['rect'].centerx
    hero_center_y = hero['rect'].centery - TOP_BAR_HEIGHT

    # Dibuja múltiples círculos concéntricos con alfa creciente para crear el efecto de desenfoque
    # El círculo central es completamente transparente, y se vuelve más opaco hacia los bordes.
    for i in range(blur_steps, 0, -1):
        alpha = int(255 * (i / blur_steps))
        pygame.draw.circle(fog_surface, (0, 0, 0, alpha), (hero_center_x, hero_center_y), visibility_radius + i)
    
    # Dibuja el círculo central completamente transparente para asegurar la visibilidad del héroe
    pygame.draw.circle(fog_surface, (0, 0, 0, 0), (hero_center_x, hero_center_y), visibility_radius)

    # Dibuja la superficie de la niebla sobre el área de juego
    screen.blit(fog_surface, (0, TOP_BAR_HEIGHT))

# --- Carga de imágenes del héroe desde GIFs ---
hero_images = []
hero_images.extend(load_gif_frames('assets/images/hero_r.gif')) # 4 frames
hero_images.extend(load_gif_frames('assets/images/hero_l.gif')) # 4 frames
hero_images.extend(load_gif_frames('assets/images/hero_u.gif')) # 2 frames
hero_images.extend(load_gif_frames('assets/images/hero_d.gif')) # 2 frames
hero_death_image = pygame.image.load('assets/images/hero_death.png').convert_alpha()

hero = {
    "rect": pygame.Rect(0, 0, HERO_WIDTH, HERO_HEIGHT),
    "images": hero_images,
    "direction": 'right', # Dirección actual: 'right', 'left', 'up', 'down'
    "frame_index": 0, # Frame actual de la animación
    "animation_timer": 0, # Temporizador para la animación
    "step_sound_timer": 0, # Temporizador para el sonido de los pasos
    "image": hero_images[0],
    "inventory": [], # El inventario ahora es una lista
    "dragons_killed": 0, # Contador de dragones derrotados
    "health": START_HEALTH, # Energía del héroe (4 tramos)
    "last_damage_time": 0 # Momento (ms) del último golpe del dragón para el enfriamiento de daño
}
hero["rect"].center = (WIDTH / 2, TOP_BAR_HEIGHT + GAME_HEIGHT - CELL * 2.5)

# --- Inicialización del juego ---
currentMap = START_ROOM
map_surface, collision_rects, item_rects, door_rects, animated_rects = build_map_surface(maps[currentMap][1], hero)

# --- Lista para la animación de puertas ---
opening_doors = []

# --- Inicialización del dragón (usando un diccionario) ---
dragon_images_r = load_gif_frames('assets/images/dragon_r.gif')
dragon_images_l = load_gif_frames('assets/images/dragon_l.gif')
if not dragon_images_r or not dragon_images_l:
    print("Error: No se pudieron cargar las animaciones del dragón. Usando fallback.")
    fallback = pygame.Surface((CELL, CELL))
    fallback.fill('red')
    dragon_images_r = dragon_images_r or [fallback]
    dragon_images_l = dragon_images_l or [fallback]

dragon = {
    "rect": dragon_images_r[0].get_rect(topleft=(CELL, TOP_BAR_HEIGHT + CELL)),
    "x": float(CELL), # Coordenadas flotantes para no perder precisión al mover
    "y": float(TOP_BAR_HEIGHT + CELL),
    "images_r": dragon_images_r,
    "images_l": dragon_images_l,
    "image": dragon_images_r[0], # Imagen actual a dibujar
    "speed": 4, # Velocidad inicial del dragón (px/frame a 60fps)
    "frame_index": 0,
    "animation_timer": 0,
    "direction": "right", # Dirección inicial
    "orbit_dir": random.choice([-1, 1]), # Sentido en el que orbita al mantener la distancia
    "radius": DRAGON_SPAWN_DISTANCE, # Radio actual (posición polar relativa al héroe)
    "orbit_angle": math.pi / 2, # Ángulo inicial fijo a 90 grados
    "frozen_until": 0, # Instante (ms) hasta el que el dragón queda inmóvil tras golpear
}

def sync_dragon_rect(dragon):
    """Copia las coordenadas flotantes del dragón a su rect de dibujo."""
    dragon['rect'].x = int(dragon['x'])
    dragon['rect'].y = int(dragon['y'])
    


def spawn_dragon(dragon, hero):
    """Coloca al dragón en el borde del círculo máximo (radio DRAGON_SPAWN_DISTANCE,
    2000 px) alrededor del héroe, en un ángulo aleatorio. Puede quedar fuera de
    pantalla; desde ahí se acerca o mantiene distancia según el inventario."""
    dragon['orbit_dir'] = random.choice([-1, 1])
    dragon['radius'] = DRAGON_SPAWN_DISTANCE
    dragon['orbit_angle'] = random.uniform(0, math.pi * 2)
    dragon['x'] = hero["rect"].centerx + math.cos(dragon['orbit_angle']) * dragon['radius']
    dragon['y'] = hero["rect"].centery + math.sin(dragon['orbit_angle']) * dragon['radius']
    sync_dragon_rect(dragon)


# El dragón parte de la posición inicial definida en su diccionario
spawn_dragon(dragon, hero)

def play_death_sequence(screen, hero, dragon, map_surface, animated_rects, item_rects, opening_doors, start_time, currentMap):
    """Muestra la secuencia de muerte del héroe:
    el héroe cae (imagen hero_death), el dragón huye volando y luego 'GAME OVER'."""
    hero['image'] = hero_death_image # El héroe muestra su sprite de muerte
    sfx_hero_death.play()
    game_over_font = pygame.font.Font(None, 100)
    game_over_text = game_over_font.render('GAME OVER', True, (220, 40, 40))

    # Rect para dibujar el sprite de muerte centrado sobre los pies del héroe
    death_rect = hero_death_image.get_rect()
    death_rect.midbottom = hero['rect'].midbottom

    # Fase 1: el dragón aletea y vuela fuera de la pantalla
    while True:
        dt = gameClock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

        # Animación de vuelo (aleteo) del dragón
        dragon['animation_timer'] += dt
        if dragon['animation_timer'] >= DRAGON_ANIMATION_INTERVAL:
            dragon['animation_timer'] -= DRAGON_ANIMATION_INTERVAL
            current_images = dragon['images_l'] if dragon['direction'] == 'left' else dragon['images_r']
            dragon['frame_index'] = (dragon['frame_index'] + 1) % len(current_images)
            dragon['image'] = current_images[dragon['frame_index']]

        # Vuela hacia arriba y hacia el lado al que mira
        speed = 10 * (dt / 16) # ~10 px/frame a 60fps
        dragon['x'] += (-1 if dragon['direction'] == 'left' else 1) * speed
        dragon['y'] -= speed * 1.5
        sync_dragon_rect(dragon)

        # --- Dibuja la escena completa ---
        screen.blit(map_surface, (0, TOP_BAR_HEIGHT))
        if animated_rects:
            for anim_rect in animated_rects:
                anim = ANIMATED.get(anim_rect['char'])
                if anim:
                    frames = anim['frames']
                    frame = frames[(pygame.time.get_ticks() // anim['interval_ms']) % len(frames)]
                    screen.blit(frame, anim_rect['rect'])
        for item in item_rects:
            img = item_images.get(item['type'])
            if img:
                screen.blit(img, item['rect'])
        screen.blit(hero['image'], death_rect)
        door_img_copy = tile_images['D'].copy()
        for door in opening_doors:
            direction = -1 if door['rect'].centerx < WIDTH // 2 else 1
            sliding_rect = door['rect'].move(direction * door['slide'], 0)
            screen.blit(door_img_copy, sliding_rect)
        draw_visibility_fog(screen, hero, maps[currentMap][3])
        screen.blit(dragon['image'], dragon['rect'])

        # --- Dibuja la UI completa ---
        pygame.draw.rect(screen, 'black', (0, TOP_BAR_HEIGHT + GAME_HEIGHT, WIDTH, BOTTOM_BAR_HEIGHT))
        inventory_x_offset = 10
        for inv_id in item_images:
            if inv_id in hero['inventory']:
                img = item_images[inv_id]
                screen.blit(img, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - img.get_height()) // 2))
                inventory_x_offset += img.get_width() + 10
        pygame.draw.rect(screen, 'black', (0, 0, WIDTH, TOP_BAR_HEIGHT))
        hearts_to_draw = GAME_RULES.get('hero', {}).get('max_health', 3)
        for i in range(hearts_to_draw):
            heart_x = 10 + i * (heart_full_image.get_width() + 10)
            screen.blit(heart_full_image if i < hero['health'] else heart_empty_image, (heart_x, (TOP_BAR_HEIGHT - heart_full_image.get_height()) // 2))
        elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
        minutes, seconds = divmod(elapsed_time, 60)
        time_text = font.render(f"{minutes:02}:{seconds:02}", True, 'white')
        screen.blit(time_text, time_text.get_rect(centerx=WIDTH // 2, centery=TOP_BAR_HEIGHT // 2))
        dragon_count_text = font.render(f"x {hero['dragons_killed']}", True, 'white')
        screen.blit(dragon_icon_image, (WIDTH - 130, (TOP_BAR_HEIGHT - dragon_icon_image.get_height()) // 2))
        screen.blit(dragon_count_text, (WIDTH - 60, (TOP_BAR_HEIGHT - dragon_count_text.get_height()) // 2))

        pygame.display.flip()

        # El dragón ha salido de la pantalla
        if dragon['rect'].bottom < TOP_BAR_HEIGHT or dragon['rect'].right < 0 or dragon['rect'].left > WIDTH:
            break

    # Fase 2: muestra el texto GAME OVER durante un momento
    show_until = pygame.time.get_ticks() + 2500
    while pygame.time.get_ticks() < show_until:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        # --- Dibuja la escena completa (sin el dragón) ---
        screen.blit(map_surface, (0, TOP_BAR_HEIGHT))
        if animated_rects:
            for anim_rect in animated_rects:
                anim = ANIMATED.get(anim_rect['char'])
                if anim:
                    frames = anim['frames']
                    frame = frames[(pygame.time.get_ticks() // anim['interval_ms']) % len(frames)]
                    screen.blit(frame, anim_rect['rect'])
        for item in item_rects:
            img = item_images.get(item['type'])
            if img:
                screen.blit(img, item['rect'])
        door_img_copy = tile_images['D'].copy()
        for door in opening_doors:
            direction = -1 if door['rect'].centerx < WIDTH // 2 else 1
            sliding_rect = door['rect'].move(direction * door['slide'], 0)
            screen.blit(door_img_copy, sliding_rect)
        draw_visibility_fog(screen, hero, maps[currentMap][3])

        # --- Dibuja la UI completa ---
        pygame.draw.rect(screen, 'black', (0, 0, WIDTH, TOP_BAR_HEIGHT))
        pygame.draw.rect(screen, 'black', (0, TOP_BAR_HEIGHT + GAME_HEIGHT, WIDTH, BOTTOM_BAR_HEIGHT))
        elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
        minutes, seconds = divmod(elapsed_time, 60)
        time_text = font.render(f"{minutes:02}:{seconds:02}", True, 'white')
        screen.blit(time_text, time_text.get_rect(centerx=WIDTH // 2, centery=TOP_BAR_HEIGHT // 2))
        dragon_count_text = font.render(f"x {hero['dragons_killed']}", True, 'white')
        screen.blit(dragon_icon_image, (WIDTH - 130, (TOP_BAR_HEIGHT - dragon_icon_image.get_height()) // 2))
        screen.blit(dragon_count_text, (WIDTH - 60, (TOP_BAR_HEIGHT - dragon_count_text.get_height()) // 2))

        # Dibuja al héroe caído y el texto GAME OVER
        screen.blit(hero['image'], death_rect)
        screen.blit(game_over_text, game_over_text.get_rect(center=(WIDTH // 2, TOP_BAR_HEIGHT + GAME_HEIGHT // 2)))
        pygame.display.flip()
        gameClock.tick(60)

    return True

gameOver = False
while not gameOver:
    dt = gameClock.tick(60) # dt es el tiempo en ms desde el último frame
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            gameOver=True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                toggle_fullscreen()
            if event.key == pygame.K_F1:
                # Abre la ventana de selección de mundos
                result = show_world_select_menu(gameScreen)
                if result == 'quit':
                    gameOver = True
            if event.key == pygame.K_F2:
                # Reinicia la partida al instante
                currentMap, map_surface, collision_rects, item_rects, door_rects, animated_rects, start_time = reset_game_state(hero, dragon, show_transition=False)
                continue
            if event.key == pygame.K_ESCAPE:
                if show_pause_menu(gameScreen):
                    gameOver = True

    # --- Actualización de estado ---
    # Mientras dure la animación de las puertas, el héroe permanece inmóvil
    if opening_doors:
        opened_doors = set()
    else:
        opened_doors = update_player(hero, collision_rects, door_rects, maps[currentMap][1], dt)
    if opened_doors:
        sfx_door_open.play() # Sonido de puerta abriéndose

        # Añade las puertas abiertas a la lista de animación antes de que desaparezcan de las colisiones
        for door_rect in door_rects:
            if door_rect['char'] in opened_doors:
                opening_doors.append({'rect': door_rect['rect'].copy(), 'slide': 0})

        # Abre las puertas: se borran del mapa la puerta y su llave
        if GAME_RULES.get('doors', {}).get('erase_door_and_key_on_open', True):
            for door_char in opened_doors:
                key_char = elements.door_opens_with(door_char)
                maps[currentMap][1] = [row.replace(door_char, ' ') for row in maps[currentMap][1]]
                if key_char:
                    maps[currentMap][1] = [row.replace(key_char, ' ') for row in maps[currentMap][1]]

        map_surface, collision_rects, item_rects, door_rects, animated_rects = build_map_surface(maps[currentMap][1], hero)

    # El dragón siempre está presente: se reposiciona alrededor del héroe
    update_dragon(dragon, hero, dt)
    # Crea el rect de colisión del héroe para esta comprobación
    hero_collision_rect = pygame.Rect(
        hero['rect'].centerx - HERO_COLLISION_WIDTH // 2,
        hero['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT),
        HERO_COLLISION_WIDTH,
        HERO_COLLISION_HEIGHT
    )
    # Comprueba colisión entre héroe y dragón
    if hero_collision_rect.colliderect(dragon['rect']):
        if FLEE_ITEMS & set(hero['inventory']):
            # El héroe derrota al dragón: secuencia de muerte con fundido
            sfx_dragon_death.play()
            hero['dragons_killed'] += 1
            dragon['speed'] += 0.5 # Aumenta la velocidad para la próxima vez
            if not play_dragon_death_sequence(gameScreen, dragon, hero, map_surface, animated_rects,
                                              item_rects, opening_doors, start_time):
                gameOver = True # El jugador cerró la ventana durante la secuencia
                continue
            # Reaparece a 2000px en un ángulo aleatorio y vuelve a acercarse
            spawn_dragon(dragon, hero)

        else:
                # Enfriamiento de daño: el héroe no puede perder otra vida
                # hasta que hayan pasado 3 segundos desde el último golpe.
                now = pygame.time.get_ticks()
                if now - hero['last_damage_time'] >= HIT_COOLDOWN_MS:
                    # El dragón golpea al héroe: pierde 1 tramo de energía
                    sfx_dragon_attack.play()
                    hero['health'] -= 1
                    hero['last_damage_time'] = now

                    # Rebote: héroe y dragón se separan en direcciones opuestas
                    dx = dragon['x'] - hero['rect'].centerx
                    dy = dragon['y'] - hero['rect'].centery
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        nx, ny = dx / dist, dy / dist
                    else:
                        nx, ny = 1.0, 0.0
                    # El dragón rebota hacia atrás (se aleja del héroe)
                    dragon['x'] += nx * KNOCKBACK_DISTANCE
                    dragon['y'] += ny * KNOCKBACK_DISTANCE
                    dragon['radius'] = min(math.hypot(dragon['x'] - hero['rect'].centerx,
                                                      dragon['y'] - hero['rect'].centery),
                                           DRAGON_SPAWN_DISTANCE)
                    sync_dragon_rect(dragon)
                    # El dragón queda fijo en su posición durante DRAGON_FROZEN_MS
                    dragon['frozen_until'] = now + DRAGON_FROZEN_MS
                    # El héroe rebota en la dirección contraria
                    hero['rect'].x -= nx * HERO_KNOCKBACK_DISTANCE
                    hero['rect'].y -= ny * HERO_KNOCKBACK_DISTANCE

                    if hero['health'] <= 0:
                        # El héroe ha muerto: secuencia de muerte y reinicio
                        if not play_death_sequence(gameScreen, hero, dragon, map_surface, animated_rects,
                                                   item_rects, opening_doors, start_time, currentMap):
                            gameOver = True # El jugador cerró la ventana durante la secuencia
                            continue
                        currentMap, map_surface, collision_rects, item_rects, door_rects, animated_rects, start_time = reset_game_state(hero, dragon)
                        # Continúa al siguiente ciclo para evitar procesar el resto de la lógica con el estado antiguo
                        continue

    # --- Lógica de Items ---
    hero_collision_rect = pygame.Rect(hero['rect'].centerx - HERO_COLLISION_WIDTH // 2, hero['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT), HERO_COLLISION_WIDTH, HERO_COLLISION_HEIGHT)
    for item in item_rects[:]: # Itera sobre una copia para poder modificar la lista
        if item.get('char') and elements.kind_of(item['char']) in ('key', 'item') and hero_collision_rect.colliderect(item['rect']):
            new_item_type = item['type']
            hero['inventory'].append(new_item_type) # Añade el nuevo objeto al inventario
            item_rects.remove(item) # El objeto desaparece del suelo
            sfx_take.play() # Sonido al recoger un objeto

    # --- CONDICIÓN DE VICTORIA ---
    # El juego termina cuando el héroe, con los items requeridos en el inventario
    # (según rules.victory de elements.json), colisiona con el elemento indicado
    # (p. ej. el trofeo + el altar). El altar es sólido y el héroe rebota al tocarlo,
    # por eso se usa un rect de detección un poco más grande.
    victory_items = set(VICTORY.get('items_required', []))
    victory_target = VICTORY.get('interact_with')
    if victory_items and victory_target and victory_items <= set(hero['inventory']):
        altar_detection_rect = hero_collision_rect.inflate(CELL, CELL)
        for item in item_rects:
            if item.get('char') == victory_target and altar_detection_rect.colliderect(item['rect']):
                sfx_win.play() # Sonido de victoria
                gameScreen.fill('black')
                gameover_rect = gameover_image.get_rect(center=gameScreen.get_rect().center)
                gameScreen.blit(gameover_image, gameover_rect)
                pygame.display.flip()
                pygame.time.wait(5000)
                gameOver = True
                continue # Salta el resto de la lógica para este frame

 
    # --- Lógica de cambio de mapa ---
    mapChange = False
    # Antes de mover al héroe, guarda la posición relativa actual del dragón
    if any([hero["rect"].top < TOP_BAR_HEIGHT, hero["rect"].left < 0,
            hero["rect"].bottom > TOP_BAR_HEIGHT + GAME_HEIGHT, hero["rect"].right > WIDTH]):
        dragon['radius'] = math.hypot(dragon['x'] - hero['rect'].centerx, dragon['y'] - hero['rect'].centery)
        dragon['orbit_angle'] = math.atan2(dragon['y'] - hero['rect'].centery, dragon['x'] - hero['rect'].centerx)

    if hero["rect"].top < TOP_BAR_HEIGHT:
        hero["rect"].bottom = TOP_BAR_HEIGHT + GAME_HEIGHT
        currentMap=maps[currentMap][0][0]
        mapChange=True
    elif hero["rect"].left < 0:
        hero["rect"].right = WIDTH - 1
        mapChange=True
        currentMap=maps[currentMap][0][3]
    elif hero["rect"].bottom > TOP_BAR_HEIGHT + GAME_HEIGHT:
        hero["rect"].top = TOP_BAR_HEIGHT
        mapChange=True
        currentMap=maps[currentMap][0][2]
    elif hero["rect"].right > WIDTH:
        hero["rect"].left = 0
        mapChange=True
        currentMap=maps[currentMap][0][1]

    if mapChange:
        # Reconstruye los sprites del mapa solo cuando es necesario
        map_surface, collision_rects, item_rects, door_rects, animated_rects = build_map_surface(maps[currentMap][1], hero)
        # Al cambiar de sala, recoloca al dragón relativo al héroe para que no
        # aparezca en zonas extrañas de la nueva sala
        dragon['x'] = hero['rect'].centerx + math.cos(dragon.get('orbit_angle', 0.0)) * dragon.get('radius', DRAGON_SPAWN_DISTANCE)
        dragon['y'] = hero['rect'].centery + math.sin(dragon.get('orbit_angle', 0.0)) * dragon.get('radius', DRAGON_SPAWN_DISTANCE)
        sync_dragon_rect(dragon)

    # --- Dibujado ---
    gameScreen.fill('black') # Limpia toda la pantalla

    # Dibuja el área de juego
    gameScreen.blit(map_surface, (0, TOP_BAR_HEIGHT)) # El mapa se dibuja debajo de la barra superior
    # Dibuja el agua animada: el tile gira 90° cada 250 ms
    if animated_rects:
        for anim_rect in animated_rects:
            anim = ANIMATED.get(anim_rect['char'])
            if anim:
                frames = anim['frames']
                frame = frames[(pygame.time.get_ticks() // anim['interval_ms']) % len(frames)]
                gameScreen.blit(frame, anim_rect['rect'])
    # Dibuja los items que queden en el mapa
    for item in item_rects:
        img = item_images.get(item['type'])
        if img:
            gameScreen.blit(img, item['rect'])
    gameScreen.blit(hero['image'], hero['rect'])

    # --- Dibuja y actualiza la animación de las puertas que se deslizan hacia los lados ---
    door_img_copy = tile_images['D'].copy() # Usa una copia para no modificar la original
    for door in opening_doors[:]:
        door['slide'] += DOOR_SLIDE_SPEED # La puerta se desliza cada frame
        if door['slide'] >= CELL: # Se ha deslizado el ancho completo de una celda
            opening_doors.remove(door)
        else:
            # Se desliza hacia la izquierda o hacia la derecha según la mitad de la sala
            direction = -1 if door['rect'].centerx < WIDTH // 2 else 1
            sliding_rect = door['rect'].move(direction * door['slide'], 0)
            gameScreen.blit(door_img_copy, sliding_rect)
    
    # --- Dibuja la capa de visibilidad ---
    draw_visibility_fog(gameScreen, hero, maps[currentMap][3])

    # Dibuja al dragón encima de la niebla: siempre presente, orbitando al héroe.
    gameScreen.blit(dragon['image'], dragon['rect'])

    # --- Dibuja la Interfaz de Usuario (Inventario) ---
    # Dibuja la barra negra del inventario en la parte inferior
    pygame.draw.rect(gameScreen, 'black', (0, TOP_BAR_HEIGHT + GAME_HEIGHT, WIDTH, BOTTOM_BAR_HEIGHT))
    # Dibuja todos los objetos que el héroe tenga en el inventario
    inventory_x_offset = 10
    for inv_id in item_images:
        if inv_id in hero['inventory']:
            img = item_images[inv_id]
            gameScreen.blit(img, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - img.get_height()) // 2))
            inventory_x_offset += img.get_width() + 10

    # --- Dibuja la Interfaz de Usuario (Barra Superior) ---
    # Se dibuja al final para que quede por encima de todos los elementos del juego.
    # Dibuja el fondo negro de la barra para tapar cualquier elemento del juego (como el dragón).
    pygame.draw.rect(gameScreen, 'black', (0, 0, WIDTH, TOP_BAR_HEIGHT))

    # --- Dibuja la barra de energía del héroe (corazones) a la izquierda ---
    hearts_to_draw = GAME_RULES.get('hero', {}).get('max_health', 3)
    heart_gap = 10
    heart_y = (TOP_BAR_HEIGHT - heart_full_image.get_height()) // 2
    for i in range(hearts_to_draw):
        heart_x = 10 + i * (heart_full_image.get_width() + heart_gap)
        if i < hero['health']:
            gameScreen.blit(heart_full_image, (heart_x, heart_y))
        else:
            gameScreen.blit(heart_empty_image, (heart_x, heart_y))

    # Dibuja el contador de tiempo
    elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    time_text = font.render(f"{minutes:02}:{seconds:02}", True, 'white')
    gameScreen.blit(time_text, time_text.get_rect(centerx=WIDTH // 2, centery=TOP_BAR_HEIGHT // 2))

    # Dibuja el contador de dragones
    dragon_count_text = font.render(f"x {hero['dragons_killed']}", True, 'white')
    gameScreen.blit(dragon_icon_image, (WIDTH - 130, (TOP_BAR_HEIGHT - dragon_icon_image.get_height()) // 2))
    gameScreen.blit(dragon_count_text, (WIDTH - 60, (TOP_BAR_HEIGHT - dragon_count_text.get_height()) // 2))

    pygame.display.flip()

pygame.quit()
