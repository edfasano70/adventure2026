# Instrucciones — Adventure 2024

Homenaje al Atari 2600. El juego está en `main.py` (requiere pygame 2.6 + Pillow) y el editor de mundos en `world_editor.py` (requiere PyQt5).

---

## El juego

### Controles

| Tecla | Acción |
|---|---|
| `Flechas` ↑↓←→ | Mover al héroe en 4 direcciones |
| `F11` | Alternar pantalla completa / ventana |
| `F1` | Abrir menú "Cargar Mundo" |
| `F2` | Reinicio instantáneo (sin transición de muerte) |
| `ESC` | Abrir menú de pausa (o cerrar submenús) |
| `ESC` (en pausa) | Volver al juego |

**Menú de pausa** (ratón o teclado): navegar con ↑↓, seleccionar con `RETURN` o clic.

- Pantalla Completa ON/OFF
- Cargar Mundo (abre selector de archivo de mundo)
- Salir del Juego

### Pantalla

- Área de juego: 20 columnas × 13 filas de 64 px = 1280 × 832 px.
- **Barra superior** (64 px): HUD — corazones del héroe, temporizador, contador de muertes del dragón.
- **Barra inferior** (64 px): Inventario del héroe.

### Objetivo

Encontrar el **trofeo** y llevarlo al **altar** (objeto 4×4 sólido). Al tocar el altar con el trofeo en el inventario, se gana la partida.

### Héroe

- Sprite: 64 × 128 px (dibujado), hitbox: 54 × 64 px (colisión reducida para pasar por huecos).
- Velocidad: 10 px/frame. Rebote al chocar paredes: 10 px.
- Salud inicial: 3. Salud máxima: 3.
- Sala inicial: 0.
- Daño: cooldown de 3000 ms entre golpes.

### Dragón

- Siempre presente (el flag `dragon` en los mundos se ignora).
- Velocidad inicial: 4 px/frame@60fps. Aumenta +0.5 cada vez que el héroe lo derrota.
- Distancia de aparición: 2000 px del héroe (ángulo aleatorio).
- Sin espada: persigue al héroe hasta colisionar (ataca).
- Con espada: mantiene ~500 px de distancia (orbita). Si se acerca demasiado, huye; si se aleja demasiado, se acerca.
- Congelado 1 s tras golpear al héroe.
- Al cambiar de sala: se reubica respecto al héroe (mismo radio/ángulo de órbita).

### Puertas y llaves

- Dos pares: puerta dorada `D` con llave `K`; puerta negra `d` con llave `b`.
- La puerta es sólida hasta que el héroe tiene la llave correspondiente.
- Al abrirla: la puerta y la llave **desaparecen del mapa permanentemente**.

### Muerte y reaparición

- El héroe muere cuando la salud llega a 0.
- Secuencia: sprite de muerte, el dragón vuela, texto "GAME OVER" durante 2.5 s.
- Después: **reinicio en sala 0 con inventario vacío** (2 s de pantalla negra).

### Niebla de guerra

- Cada sala tiene un radio de visibilidad (configurable en el editor).
- Valor ≥ 1000 = sin niebla.

### Sonidos

| Sonido | Se activa al... |
|---|---|
| `sfx_step` | Caminar (cada 180 ms) |
| `sfx_dragon_attack` | Dragón golpea al héroe |
| `sfx_dragon_death` | Héroe derrota al dragón |
| `sfx_hero_death` | Héroe muere |
| `sfx_take` | Recoger objeto |
| `sfx_door_open` | Abrir puerta |
| `sfx_win` | Victoria |

### Mundos

- El mundo por defecto es `worlds/atari_2600_world_1.py`.
- Otros mundos se cargan desde el menú de pausa → "Cargar Mundo", que escanea `worlds/*.py`.

---

## El editor

Se ejecuta con `python3 world_editor.py`. Es PyQt5, no pygame.

### Controles del teclado

| Tecla | Acción |
|---|---|
| `Flechas` | Mover cursor sobre el mapa |
| `ESPACIO` | Siguiente elemento del pincel |
| `+` / `=` | Incrementar valor en la zona (conexión +1, visibilidad +100, siguiente sala) |
| `-` / `_` | Decrementar valor en la zona (conexión −1, visibilidad −100, sala anterior) |
| `N` | Nueva sala |
| `L` | Cargar mundo |
| `S` | Guardar mundo |
| `RETURN` / `BACKSPACE` | Borrar tile / limpiar conexión (−1) / resetear dragón / resetear visibilidad a 1000 |
| `ESC` | Salir del editor |
| `F11` | Alternar pantalla completa |

### Ratón

| Acción | Efecto |
|---|---|
| Clic izquierdo (+ arrastrar) | Colocar elemento seleccionado en el mapa; en zonas de borde: incrementar valor (+1) |
| Clic derecho (+ arrastrar) | Borrar tile (poner hierba `' '`); en zonas de borde: decrementar valor (−1) |
| Arrastrar con botón pulsado | Pintar/borrar continuamente |
| Clic en combo box | Seleccionar elemento del pincel |
| Clic en botones del menú | Guardar / Cargar / Nueva Sala / Eliminar Sala / Nuevo Mundo |

### Zonas del mapa

El mapa tiene un borde alrededor de la cuadrícula 20×13:

| Zona | Ubicación | Clic izquierdo | Clic derecho |
|---|---|---|---|
| Sala | Esquina superior-izquierda (0,0) | Sala siguiente (+1) | Sala anterior (−1) |
| Dragón | Esquina superior-derecha | Alternar flag dragón (SI/NO) | Alternar flag dragón |
| Vis | Esquina inferior-izquierda | Visibilidad +100 | Visibilidad −100 |
| Estado | Esquina inferior-derecha | (solo info) | (solo info) |
| Arriba | Borde superior | Conexión ↑ +1 | Conexión ↑ −1 |
| Abajo | Borde inferior | Conexión ↓ +1 | Conexión ↓ −1 |
| Izquierda | Borde izquierdo | Conexión ← +1 | Conexión ← −1 |
| Derecha | Borde derecho | Conexión → +1 | Conexión → −1 |
| Cuadrícula | Área interior 20×13 | Colocar tile seleccionado | Borrar (poner hierba) |

`RETURN`/`BACKSPACE` en la cuadrícula borra el tile; en los bordes limpia la conexión a −1 o resetea dragón/visibilidad.

### Crear / editar elementos

El diálogo tiene los siguientes campos:

- **Char**: carácter (solo lectura al editar).
- **Nombre**: nombre para mostrar.
- **Imagen**: archivo `.png`/`.gif` con botón de exploración (`...`).
- **Sólido**: casilla para colisión.
- **Tipo**: `terrain` | `door` | `key` | `item` | `altar`.
- **ID Inventario**: identificador (p. ej. `"key"`, `"sword"`, `"trophy"`).

Al guardar: persiste en `core/elements.json` con la bandera `custom: true` y recarga las imágenes.

### Guardar / cargar

- El nombre del archivo se edita en la barra inferior; `RETURN` en ese campo guarda.
- **Guardar (S)**: escribe en `worlds/<archivo>.py`.
- **Cargar (L)**: lee de `worlds/<archivo>.py`.
- **Nueva Sala (N)**: añade una sala vacía.
- **Eliminar Sala**: elimina la sala actual y arregla conexiones que la referencian.
- **Nuevo Mundo**: crea un mundo nuevo con una sala vacía (genera nombre único automáticamente).
- El estado se persiste en `editor_settings.json`: última sala, pincel, directorio de imágenes, geometría de ventana.
