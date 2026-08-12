#!/usr/bin/env python3
"""Editor de mundos basado en PyQt5.

Sustituye al antiguo editor pygame. Usa elements.json como fuente única de
datos de elementos (igual que el juego). Los mundos se guardan/cargan en el
mismo formato world_file que lee adventure2.py (worlds/*.py).
"""
import os
import sys
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

import elements

# --- Configuración del mapa ---
CELL = 64
GRID_W = 20  # Columnas de la cuadrícula
GRID_H = 13  # Filas de la cuadrícula
MAP_COLS = GRID_W + 2  # Bordes izquierdo y derecho
MAP_ROWS = GRID_H + 2  # Borde superior + cuadrícula + borde inferior
LOGICAL_W = MAP_COLS * CELL
LOGICAL_H = MAP_ROWS * CELL

DEFAULT_FILENAME = 'atari_2600_world_1'


def world_path(filename):
    """Devuelve la ruta completa del archivo de mundo a partir de su nombre."""
    name = filename.strip()
    if not name.endswith('.py'):
        name += '.py'
    return os.path.join('worlds', name)


def element_name(ch):
    """Nombre legible de un char según elements.json."""
    return elements.element_def(ch)['name'] or ch


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
            conn = list(m[0]) if len(m) > 0 and isinstance(m[0], (list, tuple)) else []
            conn = (conn + [-1] * 4)[:4]
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
    """Devuelve la zona en la que está una celda del mapa."""
    bottom_row = GRID_H + 1  # Borde inferior (conexión ABAJO)
    if cx == 0 and cy == 0:
        return 'room'
    if cx == MAP_COLS - 1 and cy == 0:
        return 'dragon'
    if cx == 0 and cy == bottom_row:
        return 'vis'
    if cx == MAP_COLS - 1 and cy == bottom_row:
        return 'status'
    if cy == 0:
        return 'up'
    if cy == bottom_row:
        return 'down'
    if cx == 0:
        return 'left'
    if cx == MAP_COLS - 1:
        return 'right'
    return 'grid'


def grid_pos(cx, cy):
    """Devuelve (gx, gy) dentro de la cuadrícula, o None si no es una celda."""
    if zone_of(cx, cy) != 'grid':
        return None
    gx, gy = cx - 1, cy - 1
    if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
        return gx, gy
    return None


def build_pixmaps():
    """Construye el dict char -> QPixmap con las imágenes de elements.json.

    No usa pygame: carga las imágenes directamente con Qt.
    """
    pixmaps = {}
    for ch in elements.ELEMENTS:
        path = elements.element_image_path(ch)
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                pixmaps[ch] = pm
    return pixmaps


class NewElementDialog(QDialog):
    """Diálogo para crear un nuevo elemento (tile/item)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Nuevo Elemento')
        self.setMinimumWidth(380)

        self.char_edit = QLineEdit()
        self.char_edit.setMaxLength(1)
        self.name_edit = QLineEdit()
        self.image_edit = QLineEdit()
        self.rigid_box = QCheckBox('Rígido (colisión)')
        self.item_box = QCheckBox('Es item (inventario)')
        self.item_type_edit = QLineEdit()
        self.item_type_edit.setEnabled(False)
        self.item_box.toggled.connect(self.item_type_edit.setEnabled)

        form = QFormLayout()
        form.addRow('Char:', self.char_edit)
        form.addRow('Nombre:', self.name_edit)
        form.addRow('Imagen:', self.image_edit)
        form.addRow(self.rigid_box)
        form.addRow(self.item_box)
        form.addRow('Tipo item:', self.item_type_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Aceptar')
        buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        ch = self.char_edit.text().strip()
        if not ch or len(ch) != 1:
            QMessageBox.warning(self, 'Char inválido', 'El char debe ser un único carácter.')
            return
        if not self.image_edit.text().strip():
            QMessageBox.warning(self, 'Imagen', 'Indica la ruta de la imagen (en assets/images/).')
            return
        if ch in elements.ELEMENTS:
            QMessageBox.warning(self, 'Char ya existe', f'El char "{ch}" ya está definido en elements.json.')
            return
        super().accept()

    def result_data(self):
        name = self.name_edit.text().strip() or self.char_edit.text().strip()
        is_item = self.item_box.isChecked()
        item_type = self.item_type_edit.text().strip() or name.lower()
        return {
            'char': self.char_edit.text().strip(),
            'name': name,
            'image': self.image_edit.text().strip(),
            'rigid': self.rigid_box.isChecked(),
            'is_item': is_item,
            'item_type': item_type,
        }


class MapWidget(QWidget):
    """Panel que dibuja el mapa (cuadrícula + bordes de conexión)."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.cx = GRID_W // 2 + 1
        self.cy = GRID_H // 2 + 1

    def sizeHint(self):
        return QSize(LOGICAL_W, LOGICAL_H)

    def _mapping(self):
        """Devuelve (escala, offset_x, offset_y) para encajar el mapa lógico en el widget."""
        w, h = self.width(), self.height()
        scale = min(w / LOGICAL_W, h / LOGICAL_H) if w and h else 1.0
        ox = (w - LOGICAL_W * scale) / 2
        oy = (h - LOGICAL_H * scale) / 2
        return scale, ox, oy

    def screen_to_cell(self, pos):
        scale, ox, oy = self._mapping()
        lx = (pos.x() - ox) / scale
        ly = (pos.y() - oy) / scale
        gx = int(lx) // CELL
        gy = int(ly) // CELL
        return max(0, min(MAP_COLS - 1, gx)), max(0, min(MAP_ROWS - 1, gy))

    def mouseMoveEvent(self, event):
        self.cx, self.cy = self.screen_to_cell(event.pos())
        self.editor.on_cursor_moved(self.cx, self.cy)
        self.update()

    def mousePressEvent(self, event):
        gx, gy = self.screen_to_cell(event.pos())
        self.cx, self.cy = gx, gy
        zone = zone_of(gx, gy)
        if event.button() == Qt.LeftButton:
            if zone == 'grid':
                pos = grid_pos(gx, gy)
                if pos:
                    gx2, gy2 = pos
                    r = self.editor.rooms[self.editor.current]
                    row = list(r['grid'][gy2])
                    row[gx2] = self.editor.selected
                    r['grid'][gy2] = ''.join(row)
            elif zone in ('room', 'up', 'down', 'left', 'right', 'vis'):
                self.editor.adjust_value(1)
        elif event.button() == Qt.RightButton:
            if zone in ('room', 'up', 'down', 'left', 'right', 'vis'):
                self.editor.adjust_value(-1)
            elif zone == 'grid':
                pos = grid_pos(gx, gy)
                if pos:
                    gx2, gy2 = pos
                    r = self.editor.rooms[self.editor.current]
                    row = list(r['grid'][gy2])
                    row[gx2] = ' '
                    r['grid'][gy2] = ''.join(row)
        self.update()

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Left:
            self.cx = max(0, self.cx - 1)
        elif k == Qt.Key_Right:
            self.cx = min(MAP_COLS - 1, self.cx + 1)
        elif k == Qt.Key_Up:
            self.cy = max(0, self.cy - 1)
        elif k == Qt.Key_Down:
            self.cy = min(MAP_ROWS - 1, self.cy + 1)
        elif k == Qt.Key_Escape:
            self.editor.close()
        elif k == Qt.Key_F11:
            self.editor.toggle_fullscreen()
        elif k in (Qt.Key_Return, Qt.Key_Backspace):
            self.editor.erase_action()
        elif k == Qt.Key_Space:
            self.editor.cycle_or_toggle()
        elif k in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_asterisk):
            self.editor.adjust_value(1)
        elif k in (Qt.Key_Minus, Qt.Key_Underscore):
            self.editor.adjust_value(-1)
        elif k == Qt.Key_N:
            self.editor.new_room_action()
        elif k == Qt.Key_L:
            self.editor.load_action()
        elif k == Qt.Key_S:
            self.editor.save_action()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#000000'))
        scale, ox, oy = self._mapping()
        painter.translate(ox, oy)
        painter.scale(scale, scale)
        self._draw(painter)
        painter.end()

    def _draw(self, p):
        editor = self.editor
        r = editor.rooms[editor.current]
        bottom_row = GRID_H + 1

        # --- Cuadrícula con los tiles ---
        for gy in range(GRID_H):
            for gx in range(GRID_W):
                ch = r['grid'][gy][gx]
                pm = editor.pixmaps.get(ch)
                if pm:
                    p.drawPixmap(QRect((gx + 1) * CELL, (gy + 1) * CELL, CELL, CELL), pm)

        # --- Bordes (áreas de conexión) ---
        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                if zone_of(col, row) != 'grid':
                    rect = QRect(col * CELL, row * CELL, CELL, CELL)
                    p.fillRect(rect, QColor('#2d2d2d'))
                    p.setPen(QColor('#5a5a5a'))
                    p.drawRect(rect)

        # --- Etiquetas de conexiones ---
        c = r['connections']
        f_main = QFont()
        f_main.setPointSize(11)
        p.setFont(f_main)
        p.setPen(QColor('white'))
        p.drawText(QRect(CELL, 0, GRID_W * CELL, CELL), Qt.AlignCenter, f'ARRIBA: {c["up"]}')
        p.drawText(QRect(CELL, bottom_row * CELL, GRID_W * CELL, CELL), Qt.AlignCenter, f'ABAJO: {c["down"]}')
        self._rotated_text(p, f'IZQUIERDA: {c["left"]}', QRect(0, CELL, CELL, GRID_H * CELL), -90)
        self._rotated_text(p, f'DERECHA: {c["right"]}', QRect((MAP_COLS - 1) * CELL, CELL, CELL, GRID_H * CELL), 90)

        # --- Esquinas ---
        self._label(p, ['SALA', str(editor.current)], QRect(0, 0, CELL, CELL), QColor('yellow'))
        dragon_txt = 'SI' if r['dragon'] else 'NO'
        self._label(p, ['DRAGON', dragon_txt], QRect((MAP_COLS - 1) * CELL, 0, CELL, CELL), QColor('yellow'))
        self._label(p, ['VISIB', str(r['visibility'])], QRect(0, bottom_row * CELL, CELL, CELL), QColor('yellow'))
        self._label(p, ['S:GRD', 'ESC:SAL'], QRect((MAP_COLS - 1) * CELL, bottom_row * CELL, CELL, CELL),
                    QColor('#b4b4b4'))

        # --- Resaltar la zona o celda del cursor ---
        p.setPen(QColor('#ffff00'))
        p.setBrush(Qt.NoBrush)
        zone = zone_of(self.cx, self.cy)
        p.drawRect(self._zone_rect(zone))

    def _zone_rect(self, zone):
        bottom_row = GRID_H + 1
        if zone == 'room':
            return QRect(0, 0, CELL, CELL)
        if zone == 'dragon':
            return QRect((MAP_COLS - 1) * CELL, 0, CELL, CELL)
        if zone == 'vis':
            return QRect(0, bottom_row * CELL, CELL, CELL)
        if zone == 'up':
            return QRect(CELL, 0, GRID_W * CELL, CELL)
        if zone == 'down':
            return QRect(CELL, bottom_row * CELL, GRID_W * CELL, CELL)
        if zone == 'left':
            return QRect(0, CELL, CELL, GRID_H * CELL)
        if zone == 'right':
            return QRect((MAP_COLS - 1) * CELL, CELL, CELL, GRID_H * CELL)
        return QRect(self.cx * CELL, self.cy * CELL, CELL, CELL)

    def _label(self, p, lines, rect, color):
        small = QFont()
        small.setPointSize(8)
        p.setFont(small)
        p.setPen(color)
        fm = p.fontMetrics()
        heights = [fm.height() for _ in lines]
        total = sum(heights)
        y = rect.y() + (rect.height() - total) // 2
        for line, h in zip(lines, heights):
            p.drawText(QRect(rect.x(), y, rect.width(), h), Qt.AlignCenter, line)
            y += h

    def _rotated_text(self, p, text, rect, angle):
        p.save()
        cx = rect.center().x()
        cy = rect.center().y()
        p.translate(cx, cy)
        p.rotate(angle)
        small = QFont()
        small.setPointSize(8)
        p.setFont(small)
        p.setPen(QColor('white'))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        p.drawText(-tw // 2, -th // 2, tw, th, Qt.AlignCenter, text)
        p.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('World Editor (PyQt) - Adventure 2024')
        self.filename = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILENAME
        self.rooms = load_world(world_path(self.filename))
        if not self.rooms:
            self.rooms = {0: new_room(0)}
        self.current = min(self.rooms)
        self.selected = ' '
        self.pixmaps = build_pixmaps()

        self.map_widget = MapWidget(self)
        self.combo = QComboBox()
        self.file_edit = QLineEdit(self.filename)

        self._build_ui()
        self._populate_combo()
        self.statusBar().showMessage('Listo')

    def _build_ui(self):
        central = QWidget()
        v = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel('Elemento:'))
        self.combo.setMinimumWidth(260)
        top.addWidget(self.combo, 1)
        btn_new = QPushButton('Nuevo')
        btn_new.clicked.connect(self.new_element_action)
        top.addWidget(btn_new)
        v.addLayout(top)

        v.addWidget(self.map_widget, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel('Archivo:'))
        self.file_edit.setMinimumWidth(220)
        bottom.addWidget(self.file_edit, 1)
        btn_save = QPushButton('Guardar (S)')
        btn_save.clicked.connect(self.save_action)
        btn_load = QPushButton('Cargar (L)')
        btn_load.clicked.connect(self.load_action)
        btn_newroom = QPushButton('Nueva Sala (N)')
        btn_newroom.clicked.connect(self.new_room_action)
        btn_delroom = QPushButton('Eliminar Sala')
        btn_delroom.clicked.connect(self.delete_room_action)
        btn_newworld = QPushButton('Nuevo Mundo')
        btn_newworld.clicked.connect(self.new_world_action)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_load)
        bottom.addWidget(btn_newroom)
        bottom.addWidget(btn_delroom)
        bottom.addWidget(btn_newworld)
        v.addLayout(bottom)

        self.setCentralWidget(central)
        self.file_edit.returnPressed.connect(self.save_action)
        self.map_widget.setFocus()

    def _populate_combo(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        for ch in elements.ELEMENTS:
            pm = self.pixmaps.get(ch)
            icon = QIcon(pm.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if pm else QIcon()
            self.combo.addItem(icon, f'{element_name(ch)} ({ch})', ch)
        idx = self.combo.findData(self.selected)
        if idx < 0:
            idx = 0
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)

    def _on_combo_changed(self, _index):
        self.selected = self.combo.currentData() or ' '
        self.map_widget.setFocus()
        self.map_widget.update()

    def _set_status(self, msg, timeout=0):
        self.statusBar().showMessage(msg, timeout)

    # --- Acciones del cursor ---
    def on_cursor_moved(self, cx, cy):
        pos = grid_pos(cx, cy)
        if pos:
            gx, gy = pos
            ch = self.rooms[self.current]['grid'][gy][gx]
            self._set_status(f'Celda ({gx},{gy}) — {element_name(ch)}')

    def erase_action(self):
        cx, cy = self.map_widget.cx, self.map_widget.cy
        zone = zone_of(cx, cy)
        if zone == 'grid':
            pos = grid_pos(cx, cy)
            if pos:
                gx, gy = pos
                r = self.rooms[self.current]
                row = list(r['grid'][gy])
                row[gx] = ' '
                r['grid'][gy] = ''.join(row)
        elif zone in ('up', 'down', 'left', 'right'):
            self.rooms[self.current]['connections'][zone] = -1
        elif zone == 'dragon':
            self.rooms[self.current]['dragon'] = False
        elif zone == 'vis':
            self.rooms[self.current]['visibility'] = 1000

    def cycle_or_toggle(self):
        cx, cy = self.map_widget.cx, self.map_widget.cy
        zone = zone_of(cx, cy)
        if zone == 'dragon':
            self.rooms[self.current]['dragon'] = not self.rooms[self.current]['dragon']
        else:
            count = self.combo.count()
            idx = (self.combo.currentIndex() + 1) % count if count else 0
            self.combo.setCurrentIndex(idx)
            self.selected = self.combo.currentData() or ' '

    def adjust_value(self, step):
        cx, cy = self.map_widget.cx, self.map_widget.cy
        zone = zone_of(cx, cy)
        if zone == 'room':
            if step > 0:
                new_num = self.current + 1
                if new_num not in self.rooms:
                    self.rooms[new_num] = new_room(new_num)
                self.current = new_num
            elif self.current > 0:
                self.current -= 1
        elif zone in ('up', 'down', 'left', 'right'):
            self.rooms[self.current]['connections'][zone] += step
            if self.rooms[self.current]['connections'][zone] < -1:
                self.rooms[self.current]['connections'][zone] = -1
        elif zone == 'vis':
            self.rooms[self.current]['visibility'] = max(100, self.rooms[self.current]['visibility'] + step * 100)

    # --- Acciones de mundo ---
    def new_room_action(self):
        new_num = max(self.rooms) + 1
        self.rooms[new_num] = new_room(new_num)
        self.current = new_num
        self._set_status(f'Sala {new_num} creada', 2000)

    def delete_room_action(self):
        """Elimina la sala actual. Reajusta las conexiones que apuntaban a ella."""
        if len(self.rooms) <= 1:
            QMessageBox.information(self, 'Eliminar Sala', 'No se puede eliminar la única sala del mundo.')
            return
        resp = QMessageBox.question(
            self, 'Eliminar Sala',
            f'¿Eliminar la sala {self.current}? Se perderán sus tiles y conexiones.',
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        removed = self.current
        del self.rooms[removed]
        # Reajusta conexiones que apuntaban a la sala eliminada
        for r in self.rooms.values():
            for zone in ('up', 'down', 'left', 'right'):
                if r['connections'][zone] == removed:
                    r['connections'][zone] = -1
        # Selecciona una sala cercana restante
        nums = sorted(self.rooms)
        for n in nums:
            if n > removed:
                self.current = n
                break
        else:
            self.current = nums[-1]
        self._set_status(f'Sala {removed} eliminada', 2000)

    def new_world_action(self):
        """Crea un mundo nuevo con una única sala vacía."""
        resp = QMessageBox.question(
            self, 'Nuevo Mundo',
            '¿Crear un mundo nuevo? Se descartarán las salas actuales.',
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        self.rooms = {0: new_room(0)}
        self.current = 0
        self._set_status('Mundo nuevo creado (sala 0)', 2000)

    def load_action(self):
        self.filename = self.file_edit.text().strip() or DEFAULT_FILENAME
        self.file_edit.setText(self.filename)
        path = world_path(self.filename)
        rooms = load_world(path)
        if not rooms:
            rooms = {0: new_room(0)}
        self.rooms = rooms
        if self.current not in self.rooms:
            self.current = min(self.rooms)
        self._set_status(f'Cargado: {path}', 2000)

    def save_action(self):
        self.filename = self.file_edit.text().strip() or DEFAULT_FILENAME
        self.file_edit.setText(self.filename)
        path = world_path(self.filename)
        n = save_world(path, self.rooms)
        self._set_status(f'Guardado ({path}): {n} salas', 2000)

    # --- Elementos ---
    def new_element_action(self):
        dlg = NewElementDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.result_data()
        ch = data['char']
        new_def = {
            'name': data['name'],
            'image': data['image'],
            'solid': data['rigid'],
            'kind': 'item' if data['is_item'] else 'terrain',
            'inventory_id': data['item_type'] if data['is_item'] else None,
            'draws_under': ' ' if data['is_item'] else None,
            'custom': True,
        }
        elements.ELEMENTS[ch] = new_def
        elements.save_elements()
        self.pixmaps = build_pixmaps()
        self._populate_combo()
        idx = self.combo.findData(ch)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
            self.selected = ch
        self.map_widget.setFocus()
        self._set_status(f'Elemento "{ch}" creado y guardado en elements.json', 3000)

    # --- Ventana ---
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 900)
    window.show()
    sys.exit(app.exec_())