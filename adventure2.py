#!/usr/bin/env python3
import pygame
from pygame import mixer
import math # Necesario para la IA de persecución
import random # Necesario para la reaparición aleatoria
import sys # Para poder importar desde subcarpetas
import json # Para guardar y cargar la configuración del usuario
import os # Para listar los archivos de mundos
import importlib.util # Para cargar mundos en tiempo de ejecución
from PIL import Image # Necesario para cargar frames de GIFs
sys.path.append('worlds') # Añade la carpeta de datos al path
pygame.init()
# El import de atari_2600_world_1 debe estar después de la definición de constantes si las usa
from atari_2600_world_1 import *

mixer.init()

CONFIG_PATH = 'settings.json'
DEFAULT_CONFIG = {'fullscreen': False, 'volume': 0.2}

def load_config():
    """Carga la configuración guardada, completando los valores que falten."""
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH) as f:
            config.update(json.load(f))
    except Exception:
        pass
    return config

def save_config(config):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
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
KNOCKBACK_SPEED = 600 # Píxeles por segundo del rechazo del dragón
KNOCKBACK_DISTANCE = 300 # Píxeles que se aleja el dragón al golpear al héroe
HIT_COOLDOWN_MS = 3000 # Milisegundos de inmunidad tras recibir un golpe del dragón

# --- Constantes para la animación de apertura de puertas ---
DOOR_SLIDE_SPEED = 3 # Píxeles por frame que se desliza la puerta al abrirse

config = load_config()
is_fullscreen = config.get('fullscreen', False)
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
font = pygame.font.Font(None, 36) # Fuente para los contadores

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
# --- Carga de recursos (imágenes de tiles) ---
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

# --- Carga de imagen para la espada ---
sword_image = pygame.image.load('assets/images/sword.png').convert_alpha()

# --- Carga de imagen para la llave ---
key_image = pygame.image.load('assets/images/key_golden.png').convert_alpha()
key_black_image = pygame.image.load('assets/images/key_black.png').convert_alpha()

# --- Carga de imagen para el trofeo ---
trophy_image = pygame.image.load('assets/images/trophy.png').convert_alpha()

# --- Carga de imagen para el altar ---
altar_image = pygame.image.load('assets/images/altar.png').convert_alpha()

# --- Carga de imagen de Game Over ---
gameover_image = pygame.image.load('assets/images/game_over_win.png').convert_alpha()

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
    processed_coords = set() # Para evitar procesar celdas ocupadas por objetos grandes
    x, y = 0, 0 # Dibuja en la superficie local desde (0,0)
    for row_idx, row in enumerate(map_data):
        for col_idx, cell_char in enumerate(row):
            if (row_idx, col_idx) in processed_coords:
                x += CELL
                continue

            # Dibuja el tile base. Si es un item, dibuja hierba debajo.
            # La puerta del castillo negro 'd' usa la misma imagen que la dorada 'D'.
            base_tile = ' ' if cell_char in 'SKbTA' else ('D' if cell_char == 'd' else cell_char)
            if base_tile in tile_images:
                map_surface.blit(tile_images[base_tile], (x, y))

            # Gestiona colisiones y objetos especiales
            if cell_char in 'XYWy': # Muros (roca, roca dorada, roca negra) y agua causan colisión
                collision_rects.append(pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL))
            elif cell_char in 'Dd': # Las puertas van a su propia lista, con su color
                door_type = 'gold' if cell_char == 'D' else 'black'
                door_rects.append({'type': door_type, 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif cell_char == 'S' and 'sword' not in hero['inventory']:
                item_rects.append({'type': 'sword', 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif cell_char == 'K' and 'key' not in hero['inventory']:
                item_rects.append({'type': 'key', 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif cell_char == 'b' and 'key_black' not in hero['inventory']:
                item_rects.append({'type': 'key_black', 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif cell_char == 'T' and 'trophy' not in hero['inventory']:
                item_rects.append({'type': 'trophy', 'rect': pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL, CELL)})
            elif cell_char == 'A':
                # Dibuja un fondo de hierba de 4x4 para el altar
                for r_offset in range(4):
                    for c_offset in range(4):
                        map_surface.blit(tile_images[' '], (x + c_offset * CELL, y + r_offset * CELL))
                altar_rect = pygame.Rect(x, y + TOP_BAR_HEIGHT, CELL * 4, CELL * 4)
                item_rects.append({'type': 'altar', 'rect': altar_rect})
                collision_rects.append(altar_rect) # El altar vuelve a ser una colisión sólida
                # Marca las celdas que ocupa el altar como ya procesadas
                for r_offset in range(4):
                    for c_offset in range(4):
                        # Asegúrate de no salirte de los límites del mapa si el altar está en un borde
                        if row_idx + r_offset < len(map_data) and col_idx + c_offset < len(map_data[0]):
                            processed_coords.add((row_idx + r_offset, col_idx + c_offset))

            x += CELL
        x = 0
        y += CELL
    return map_surface, collision_rects, item_rects, door_rects

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

    opened_doors = set() # Colores de puerta ('gold'/'black') que el héroe puede abrir
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
            door_key = 'key' if door_rect['type'] == 'gold' else 'key_black'
            if door_key in player['inventory']:
                # Si tiene la llave del color correcto, notifica al bucle principal
                opened_doors.add(door_rect['type'])
            else:
                # Si no tiene la llave del color correcto, la puerta actúa como un muro.
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
            door_key = 'key' if door_rect['type'] == 'gold' else 'key_black'
            if door_key in player['inventory']:
                opened_doors.add(door_rect['type'])
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
    """Maneja la IA de persecución y animación del dragón.
    El dragón vuela libremente (sin colisiones con muros).
    Devuelve True si el dragón escapó de la sala mientras huía del héroe."""
    # --- Animación ---
    dragon['animation_timer'] += dt
    if dragon['animation_timer'] >= DRAGON_ANIMATION_INTERVAL:
        dragon['animation_timer'] -= DRAGON_ANIMATION_INTERVAL
        # Elige la lista de imágenes correcta según la dirección
        current_images = dragon['images_l'] if dragon['direction'] == 'left' else dragon['images_r']
        dragon['frame_index'] = (dragon['frame_index'] + 1) % len(current_images)
        dragon['image'] = current_images[dragon['frame_index']]

    # --- Knockback (rechazo animado tras golpear al héroe) ---
    # Durante el rechazo el dragón no persigue ni huye: solo se aleja.
    if dragon.get('knockback_remaining', 0) > 0:
        move = KNOCKBACK_SPEED * (dt / 1000)
        if move > dragon['knockback_remaining']:
            move = dragon['knockback_remaining']
        dragon['x'] += dragon['knockback_dir_x'] * move
        dragon['y'] += dragon['knockback_dir_y'] * move
        dragon['knockback_remaining'] -= move
        # No se sale del área de juego durante el rechazo
        dragon['x'] = max(0.0, min(WIDTH - dragon['rect'].width, dragon['x']))
        dragon['y'] = max(float(TOP_BAR_HEIGHT), min(TOP_BAR_HEIGHT + GAME_HEIGHT - dragon['rect'].height, dragon['y']))
        sync_dragon_rect(dragon)
        return False

    # Calcular vector hacia el jugador usando las coordenadas flotantes
    dx = player['rect'].centerx - dragon['x']
    dy = player['rect'].centery - dragon['y']
    
    # Calcular distancia para normalizar el vector
    distance = math.hypot(dx, dy)

    # Por defecto, el dragón persigue
    should_move = True
    fleeing = False

    # Si el jugador tiene la espada, el dragón cambia su comportamiento:
    # nunca lo persigue. Huye y, si puede, escapa de la sala.
    if 'sword' in player['inventory']:
        fleeing = True
        # Invierte el vector: se aleja siempre del héroe
        dx *= -1
        dy *= -1

    # Mover solo si es necesario y si no está ya encima del jugador
    if should_move and distance > 1:
        # Velocidad en px/segundo independiente del framerate
        # (dragon['speed'] está en px/frame a 60fps, se convierte a px/s)
        speed_px_per_sec = dragon['speed'] * 60
        target_speed = speed_px_per_sec * (dt / 1000)

        # Normalizar vector y añadir una pequeña variabilidad (zigzag)
        # para que la trayectoria no sea una línea recta perfecta.
        norm_x = dx / distance + random.uniform(-0.15, 0.15)
        norm_y = dy / distance + random.uniform(-0.15, 0.15)

        move_x = norm_x * target_speed
        move_y = norm_y * target_speed

        # Actualiza la dirección del dragón para la animación
        if move_x < 0:
            dragon['direction'] = 'left'
        elif move_x > 0:
            dragon['direction'] = 'right'

        # Mueve las coordenadas flotantes (el rect de dibujo se sincroniza después)
        dragon['x'] += move_x
        dragon['y'] += move_y

        # Mientras persigue, no se sale de los márgenes verticales del área de juego.
        # Mientras huye, no se limita para poder escapar de la sala.
        if not fleeing:
            if dragon['y'] < TOP_BAR_HEIGHT:
                dragon['y'] = TOP_BAR_HEIGHT
            if dragon['y'] + dragon['rect'].height > TOP_BAR_HEIGHT + GAME_HEIGHT:
                dragon['y'] = TOP_BAR_HEIGHT + GAME_HEIGHT - dragon['rect'].height

    sync_dragon_rect(dragon)

    # Si está huyendo y se salió de la sala, escapó y desaparece
    if fleeing and (
        dragon['rect'].right < 0 or
        dragon['rect'].left > WIDTH or
        dragon['rect'].bottom < TOP_BAR_HEIGHT or
        dragon['rect'].top > TOP_BAR_HEIGHT + GAME_HEIGHT
    ):
        return True
    return False

def reset_game_state(hero, dragon, show_transition=True):
    """Resetea el estado del juego. Con show_transition=True muestra
    una pantalla negra de 2 segundos (para la derrota); con False
    reinicia al instante (para el reinicio manual con F2)."""
    if show_transition:
        # Muestra una pantalla negra para indicar la derrota
        gameScreen.fill('black')
        pygame.display.flip()
        pygame.time.wait(2000)

    # Reinicia el estado
    currentMap = 0
    hero["rect"].center = (WIDTH / 2, TOP_BAR_HEIGHT + GAME_HEIGHT - CELL * 2.5)
    hero["direction"] = 'right'
    hero["frame_index"] = 0
    hero["inventory"] = [] # Vacía el inventario al reiniciar
    hero["dragons_killed"] = 0 # Reinicia el contador de dragones
    hero["health"] = 4 # Restablece la energía al máximo
    hero["last_damage_time"] = 0 # Sin enfriamiento de daño pendiente
    hero["image"] = hero_images[0] # Restaura el sprite normal del héroe
    dragon["x"] = float(CELL)
    dragon["y"] = float(TOP_BAR_HEIGHT + CELL)
    sync_dragon_rect(dragon)
    dragon['speed'] = 4.0 # Restablece la velocidad del dragón
    dragon['frame_index'] = 0 # Reinicia la animación del dragón
    dragon['direction'] = 'right' # Reinicia la dirección
    dragon['image'] = dragon['images_r'][0]
    dragon['knockback_remaining'] = 0 # Cancela cualquier rechazo en curso
    dragon_respawn_room = -1 # El dragón no está esperando para reaparecer

    map_surface, collision_rects, item_rects, door_rects = build_map_surface(maps[currentMap][1], hero)
    # El dragón se desactiva al reiniciar
    dragon_is_active = maps[currentMap][2]

    return currentMap, map_surface, collision_rects, item_rects, door_rects, dragon_is_active, dragon_respawn_room, pygame.time.get_ticks()

def list_world_files():
    """Devuelve la lista de archivos de mundo (.py) disponibles en la carpeta worlds."""
    try:
        files = os.listdir('worlds')
        return sorted(f for f in files if f.endswith('.py') and not f.startswith('__'))
    except Exception:
        return []


def load_world_file(filename):
    """Carga un mundo desde la carpeta worlds y reinicia la partida."""
    global maps, currentMap, map_surface, collision_rects, item_rects, door_rects
    global dragon_is_active, dragon_respawn_room, start_time, opening_doors
    path = os.path.join('worlds', filename)
    try:
        spec = importlib.util.spec_from_file_location('loaded_world', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        new_maps = mod.maps
    except Exception:
        return False

    maps = new_maps
    currentMap = 0
    hero["rect"].center = (WIDTH / 2, TOP_BAR_HEIGHT + GAME_HEIGHT - CELL * 2.5)
    hero["direction"] = 'right'
    hero["frame_index"] = 0
    hero["inventory"] = [] # Vacía el inventario
    hero["dragons_killed"] = 0
    hero["health"] = 4 # Restablece la energía al máximo
    dragon["x"] = float(CELL)
    dragon["y"] = float(TOP_BAR_HEIGHT + CELL)
    sync_dragon_rect(dragon)
    dragon['speed'] = 4.0
    dragon['frame_index'] = 0
    dragon['direction'] = 'right'
    dragon['image'] = dragon['images_r'][0]
    dragon['knockback_remaining'] = 0 # Cancela cualquier rechazo en curso
    dragon_respawn_room = -1
    opening_doors = []
    map_surface, collision_rects, item_rects, door_rects = build_map_surface(maps[currentMap][1], hero)
    dragon_is_active = maps[currentMap][2]
    start_time = pygame.time.get_ticks()
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
    "dragons_killed": 0,
    "health": 4, # Energía del héroe (4 tramos)
    "last_damage_time": 0 # Momento (ms) del último golpe del dragón para el enfriamiento de daño
}
hero["rect"].center = (WIDTH / 2, TOP_BAR_HEIGHT + GAME_HEIGHT - CELL * 2.5)

# --- Inicialización del juego ---
currentMap = 0
map_surface, collision_rects, item_rects, door_rects = build_map_surface(maps[currentMap][1], hero)
# El dragón está inactivo al principio. Se activará cuando el jugador entre en una sala de dragones.
dragon_is_active = False
# -1 significa que no está esperando para reaparecer. Un valor >= 0 es la sala donde reaparecerá.
dragon_respawn_room = -1

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
    "knockback_remaining": 0, # Píxeles que le quedan por alejarse (rechazo)
    "knockback_dir_x": 0.0, # Dirección del rechazo
    "knockback_dir_y": 0.0
}

def sync_dragon_rect(dragon):
    """Copia las coordenadas flotantes del dragón a su rect de dibujo."""
    dragon['rect'].x = int(dragon['x'])
    dragon['rect'].y = int(dragon['y'])

def play_death_sequence(screen, hero, dragon, map_surface):
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

        # Dibuja la escena: mapa, héroe caído y dragón volando
        screen.blit(map_surface, (0, TOP_BAR_HEIGHT))
        screen.blit(hero['image'], death_rect)
        screen.blit(dragon['image'], dragon['rect'])
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
        screen.blit(map_surface, (0, TOP_BAR_HEIGHT))
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
                currentMap, map_surface, collision_rects, item_rects, door_rects, dragon_is_active, dragon_respawn_room, start_time = reset_game_state(hero, dragon, show_transition=False)
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
            if door_rect['type'] in opened_doors:
                opening_doors.append({'rect': door_rect['rect'].copy(), 'slide': 0})

        # Abre solo las puertas del color correspondiente a la llave usada
        if 'gold' in opened_doors:
            # Se usó la llave dorada: la llave 'K' desaparece del mapa y se abren las puertas 'D'
            maps[currentMap][1] = [row.replace('K', ' ') for row in maps[currentMap][1]]
            maps[currentMap][1] = [row.replace('D', ' ') for row in maps[currentMap][1]]
        if 'black' in opened_doors:
            # Se usó la llave negra: la llave 'b' desaparece del mapa y se abren las puertas 'd'
            maps[currentMap][1] = [row.replace('b', ' ') for row in maps[currentMap][1]]
            maps[currentMap][1] = [row.replace('d', ' ') for row in maps[currentMap][1]]

        map_surface, collision_rects, item_rects, door_rects = build_map_surface(maps[currentMap][1], hero)

    if dragon_is_active:
        dragon_escaped = update_dragon(dragon, hero, dt) # La IA ahora depende del estado del héroe
        if dragon_escaped:
            # El dragón huyó y escapó de la sala: desaparece y reaparecerá en otra sala
            dragon_is_active = False
            possible_rooms = list(range(len(maps)))
            possible_rooms.remove(currentMap)
            dragon_respawn_room = random.choice(possible_rooms)
        # Crea el rect de colisión del héroe para esta comprobación
        hero_collision_rect = pygame.Rect(
            hero['rect'].centerx - HERO_COLLISION_WIDTH // 2,
            hero['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT),
            HERO_COLLISION_WIDTH,
            HERO_COLLISION_HEIGHT
        )
        # Comprueba colisión entre héroe y dragón
        if hero_collision_rect.colliderect(dragon['rect']):
            if 'sword' in hero['inventory']:
                # El héroe derrota al dragón
                sfx_dragon_death.play()
                hero['dragons_killed'] += 1
                dragon['speed'] += 0.5 # Aumenta la velocidad para la próxima vez
                dragon_is_active = False # El dragón desaparece
                
                # Elige una nueva sala de reaparición que no sea la actual
                possible_rooms = list(range(len(maps)))
                possible_rooms.remove(currentMap)
                dragon_respawn_room = random.choice(possible_rooms)

            else:
                # Enfriamiento de daño: el héroe no puede perder otra vida
                # hasta que hayan pasado 3 segundos desde el último golpe.
                now = pygame.time.get_ticks()
                if now - hero['last_damage_time'] >= HIT_COOLDOWN_MS:
                    # El dragón golpea al héroe: pierde 1 tramo de energía
                    sfx_dragon_attack.play()
                    hero['health'] -= 1
                    hero['last_damage_time'] = now
                    # Inicia el rechazo animado: el dragón se aleja 300px del héroe
                    dx = dragon['x'] - hero['rect'].centerx
                    dy = dragon['y'] - hero['rect'].centery
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        dragon['knockback_dir_x'] = dx / dist
                        dragon['knockback_dir_y'] = dy / dist
                    else:
                        dragon['knockback_dir_x'] = 0.0
                        dragon['knockback_dir_y'] = -1.0
                    dragon['knockback_remaining'] = KNOCKBACK_DISTANCE

                    if hero['health'] <= 0:
                        # El héroe ha muerto: secuencia de muerte y reinicio
                        if not play_death_sequence(gameScreen, hero, dragon, map_surface):
                            gameOver = True # El jugador cerró la ventana durante la secuencia
                            continue
                        currentMap, map_surface, collision_rects, item_rects, door_rects, dragon_is_active, dragon_respawn_room, start_time = reset_game_state(hero, dragon)
                        # Continúa al siguiente ciclo para evitar procesar el resto de la lógica con el estado antiguo
                        continue

    # --- Lógica de Items ---
    hero_collision_rect = pygame.Rect(hero['rect'].centerx - HERO_COLLISION_WIDTH // 2, hero['rect'].y + (HERO_HEIGHT - HERO_COLLISION_HEIGHT), HERO_COLLISION_WIDTH, HERO_COLLISION_HEIGHT)
    for item in item_rects[:]: # Itera sobre una copia para poder modificar la lista
        if item['type'] != 'altar' and hero_collision_rect.colliderect(item['rect']):
            new_item_type = item['type']
            hero['inventory'].append(new_item_type) # Añade el nuevo objeto al inventario
            item_rects.remove(item) # El objeto desaparece del suelo
            sfx_take.play() # Sonido al recoger un objeto

    # --- CONDICIÓN DE VICTORIA ---
    # El juego termina cuando el héroe, con el trofeo en el inventario,
    # colisiona con el altar. El altar es sólido y el héroe rebota al tocarlo,
    # por eso se usa un rect de detección un poco más grande.
    if 'trophy' in hero['inventory']:
        altar_detection_rect = hero_collision_rect.inflate(CELL, CELL)
        for item in item_rects:
            if item['type'] == 'altar' and altar_detection_rect.colliderect(item['rect']):
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
    if hero["rect"].top < TOP_BAR_HEIGHT:
        if dragon_is_active:
            dragon['y'] += (GAME_HEIGHT - CELL)
            sync_dragon_rect(dragon)
        hero["rect"].bottom = TOP_BAR_HEIGHT + GAME_HEIGHT
        currentMap=maps[currentMap][0][0]
        mapChange=True
    elif hero["rect"].left < 0:
        if dragon_is_active:
            dragon['x'] += WIDTH
            sync_dragon_rect(dragon)
        hero["rect"].right = WIDTH - 1
        mapChange=True
        currentMap=maps[currentMap][0][3]
    elif hero["rect"].bottom > TOP_BAR_HEIGHT + GAME_HEIGHT:
        if dragon_is_active:
            dragon['y'] -= (GAME_HEIGHT - CELL)
            sync_dragon_rect(dragon)
        hero["rect"].top = TOP_BAR_HEIGHT
        mapChange=True
        currentMap=maps[currentMap][0][2]
    elif hero["rect"].right > WIDTH:
        if dragon_is_active:
            dragon['x'] -= WIDTH
            sync_dragon_rect(dragon)
        hero["rect"].left = 0
        mapChange=True
        currentMap=maps[currentMap][0][1]

    if mapChange:
        # Reconstruye los sprites del mapa solo cuando es necesario
        map_surface, collision_rects, item_rects, door_rects = build_map_surface(maps[currentMap][1], hero)
        # Si el dragón no estaba activo, comprueba si debe activarse en esta nueva sala.
        # Una vez activo, permanece activo.
        if not dragon_is_active:
            # Comprueba si el dragón debe aparecer por primera vez
            if maps[currentMap][2]:
                 dragon_is_active = True
            # O comprueba si el jugador ha entrado en la sala de reaparición
            elif currentMap == dragon_respawn_room:
                dragon_is_active = True
                dragon['x'] = float(CELL)
                dragon['y'] = float(TOP_BAR_HEIGHT + CELL)
                sync_dragon_rect(dragon)
                dragon_respawn_room = -1 # Resetea la sala de reaparición
                
    # --- Dibujado ---
    gameScreen.fill('black') # Limpia toda la pantalla

    # --- Dibuja la Interfaz de Usuario (Barra Superior) ---
    # Dibuja el contador de tiempo
    elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
    minutes = elapsed_time // 60
    seconds = elapsed_time % 60
    time_text = font.render(f"{minutes:02}:{seconds:02}", True, 'white')
    gameScreen.blit(time_text, (10, 5))

    # Dibuja el contador de dragones
    dragon_count_text = font.render(f"x {hero['dragons_killed']}", True, 'white')
    gameScreen.blit(dragon['images_r'][0], (WIDTH - 130, 0)) # Usa una imagen fija para la UI
    gameScreen.blit(dragon_count_text, (WIDTH - 60, 5))

    # --- Dibuja la barra de energía del héroe (4 tramos) ---
    segments = 4
    seg_w, seg_h, gap = 44, 22, 6
    total_w = segments * seg_w + (segments - 1) * gap
    bar_x = WIDTH // 2 - total_w // 2
    bar_y = 6
    for i in range(segments):
        seg_rect = pygame.Rect(bar_x + i * (seg_w + gap), bar_y, seg_w, seg_h)
        if i < hero['health']:
            if hero['health'] >= 3:
                color = (60, 220, 60)      # Verde: mucha energía
            elif hero['health'] == 2:
                color = (240, 200, 40)     # Amarillo: media energía
            else:
                color = (220, 60, 40)      # Rojo: poca energía
            pygame.draw.rect(gameScreen, color, seg_rect)
        else:
            pygame.draw.rect(gameScreen, (40, 40, 40), seg_rect)  # Tramo vacío
        pygame.draw.rect(gameScreen, 'white', seg_rect, 2)        # Borde

    # Dibuja el área de juego
    gameScreen.blit(map_surface, (0, TOP_BAR_HEIGHT)) # El mapa se dibuja debajo de la barra superior
    # Dibuja los items que queden en el mapa
    for item in item_rects:
        if item['type'] == 'sword':
            gameScreen.blit(sword_image, item['rect'])
        elif item['type'] == 'key':
            gameScreen.blit(key_image, item['rect'])
        elif item['type'] == 'key_black':
            gameScreen.blit(key_black_image, item['rect'])
        elif item['type'] == 'trophy':
            gameScreen.blit(trophy_image, item['rect'])
        elif item['type'] == 'altar':
            gameScreen.blit(altar_image, item['rect'])
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

    # Dibuja al dragón encima de la niebla: vuela por encima y siempre es visible
    if dragon_is_active:
        gameScreen.blit(dragon['image'], dragon['rect'])

    # --- Dibuja la Interfaz de Usuario (Inventario) ---
    # Dibuja la barra negra del inventario en la parte inferior
    pygame.draw.rect(gameScreen, 'black', (0, TOP_BAR_HEIGHT + GAME_HEIGHT, WIDTH, BOTTOM_BAR_HEIGHT))
    # Dibuja todos los objetos que el héroe tenga en el inventario
    inventory_x_offset = 10
    if 'sword' in hero['inventory']:
        gameScreen.blit(sword_image, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - sword_image.get_height()) // 2))
        inventory_x_offset += sword_image.get_width() + 10
    if 'key' in hero['inventory']:
        gameScreen.blit(key_image, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - key_image.get_height()) // 2))
        inventory_x_offset += key_image.get_width() + 10
    if 'key_black' in hero['inventory']:
        gameScreen.blit(key_black_image, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - key_black_image.get_height()) // 2))
        inventory_x_offset += key_black_image.get_width() + 10
    if 'trophy' in hero['inventory']:
        gameScreen.blit(trophy_image, (inventory_x_offset, TOP_BAR_HEIGHT + GAME_HEIGHT + (BOTTOM_BAR_HEIGHT - trophy_image.get_height()) // 2))

    pygame.display.flip()

pygame.quit()
