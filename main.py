import math
import random
import struct
import sys
import wave
from pathlib import Path

from ursina import (Audio, Button, Color, Entity, Mesh, Quad, Text, Texture, Ursina, Vec3,
                    application, camera, destroy, held_keys, lerp, scene, time, window)
from panda3d.core import ClockObject, Filename, WindowProperties

import car_model
import models
import storage
import world as W
from i18n import LANGUAGES, Tr

BASE = Path(__file__).resolve().parent
FONT = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
FONT_BOLD = Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')

app = Ursina(title='Forest Walk', borderless=False, development_mode=False,
             editor_ui_enabled=False, size=(1280, 720), vsync=True)

if FONT.exists():
    Text.default_font = str(FONT)
BOLD = str(FONT_BOLD) if FONT_BOLD.exists() else Text.default_font

SKY = Color(0.62, 0.80, 0.95, 1)
window.color = SKY
scene.fog_color = SKY
scene.fog_density = (90, 280)
camera.fov = 78
camera.clip_plane_far = 700


def C(r, g, b, a=255):
    return Color(r / 255, g / 255, b / 255, a / 255)


BTN = C(34, 92, 60, 235)
BTN_HI = C(52, 130, 84, 245)
BTN_ON = C(200, 150, 30, 245)
BTN_RED = C(150, 45, 45, 235)
GOLD = C(255, 215, 70)

ADMIN = '--admin' in sys.argv
RESPAWN = 180
PAINT_PRICE = 5
RIM_PRICE = 8
ENGINE_PRICES = [20, 35, 50]


def fmt_time(seconds):
    s = int(seconds)
    return f'{s // 60:02d}:{s % 60:02d}' if s < 3600 else f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}'


def look_at(target):
    d = target - camera.world_position
    yaw = math.degrees(math.atan2(d.x, d.z))
    pitch = -math.degrees(math.atan2(d.y, math.hypot(d.x, d.z)))
    camera.rotation = (pitch, yaw, 0)


def make_coin_sound(path):
    rate = 22050
    frames = bytearray()
    for i in range(int(rate * 0.3)):
        t = i / rate
        f = 1320 if t < 0.07 else 1760
        s = 0.35 * math.exp(-t * 12) * math.sin(math.tau * f * t)
        frames += struct.pack('<h', int(32767 * s))
    path.parent.mkdir(exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


class MouseLook:
    def __init__(self):
        self.active = False
        self.last = None
        self.frame = -10
        self.skip = 0

    def lock(self, flag):
        props = WindowProperties()
        props.setCursorHidden(flag)
        props.setMouseMode(WindowProperties.M_relative if flag else WindowProperties.M_absolute)
        application.base.win.requestProperties(props)
        self.active = flag
        self.last = None
        self.skip = 3

    def delta(self):
        win = application.base.win
        frame = ClockObject.getGlobalClock().getFrameCount()
        if frame - self.frame > 1:
            self.last = None
        self.frame = frame
        if not self.active or not win.getProperties().getForeground():
            self.last = None
            return 0.0, 0.0
        if self.skip:
            self.skip -= 1
            self.last = None
            return 0.0, 0.0
        md = win.getPointer(0)
        x, y = md.getX(), md.getY()
        if win.getProperties().getMouseMode() == WindowProperties.M_relative:
            if self.last is None:
                self.last = (x, y)
                return 0.0, 0.0
            dx, dy = x - self.last[0], y - self.last[1]
            self.last = (x, y)
        else:
            cx, cy = win.getXSize() // 2, win.getYSize() // 2
            first = self.last is None
            win.movePointer(0, cx, cy)
            self.last = (cx, cy)
            if first:
                return 0.0, 0.0
            dx, dy = x - cx, y - cy
        if abs(dx) > 400 or abs(dy) > 400:
            return 0.0, 0.0
        return dx, dy


class Player:
    EYE = 1.65
    RADIUS = 0.4

    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.yaw = self.pitch = 0.0
        self.vy = 0.0
        self.grounded = True
        self.bob = 0.0


class Car:
    def __init__(self, world):
        self.world = world
        self.model_id = None
        self.entity = None
        self.trailer = None
        self.x = self.z = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.pitch = 0.0
        self.speed = 0.0
        self.steer = 0.0
        self.spin = 0.0
        self.engine = 0
        self.axle = None

    def set_model(self, model_id, tuning):
        if self.entity is not None:
            if self.entity.isAncestorOf(camera):
                camera.parent = scene
            destroy(self.entity)
        if self.trailer is not None:
            destroy(self.trailer)
        v = car_model.build_vehicle(model_id, tuning.get('color', 0), tuning.get('rims', 0))
        self.model_id = model_id
        self.spec = car_model.SPECS[model_id]
        self.phys = self.spec['phys']
        self.engine = tuning.get('engine', 0)
        self.entity, self.glass, self.wheels = v.root, v.glass, v.wheels
        self.trailer, self.trailer_wheels = v.trailer, v.trailer_wheels
        (wx, wy, wz), tilt = v.steering
        holder = Entity(parent=self.entity, position=(wx, wy, wz), rotation_x=tilt)
        self.wheel = car_model.build_steering_wheel(holder)
        self.seat = Entity(parent=self.entity, position=v.seat)
        self.glass_alpha = 1.0
        self.axle = None
        self.sync()

    @property
    def radius(self):
        return self.phys['radius']

    def place(self, x, z, heading):
        self.x, self.z, self.heading = x, z, heading
        self.speed = self.steer = 0.0
        self.axle = None
        self.sync()

    def circles(self, x, z, heading):
        h = math.radians(heading)
        return [(x + math.sin(h) * d, z + math.cos(h) * d) for d in self.phys['circles']]

    def collides(self, x, z, heading):
        return any(self.world.blocked(cx, cz, self.radius) for cx, cz in self.circles(x, z, heading))

    def update(self, dt, fwd, back, left, right, handbrake):
        ph = self.phys
        boost = 1 + 0.12 * self.engine
        on_road = self.world.on_road(self.x, self.z)
        max_v = (ph['max_road'] if on_road else ph['max_off']) * boost
        accel = ph['accel'] * (1 + 0.2 * self.engine)
        if fwd:
            self.speed += (16 if self.speed < 0 else accel) * dt
        elif back:
            self.speed -= (14 if self.speed > 0 else 5) * dt
        else:
            self.speed -= self.speed * min(1.0, 0.7 * dt)
        if handbrake:
            self.speed -= math.copysign(min(abs(self.speed), 20 * dt), self.speed)
        if self.speed > max_v:
            self.speed = max(max_v, self.speed - 12 * dt)
        self.speed = max(-6.0, self.speed)
        if abs(self.speed) < 0.05 and not (fwd or back):
            self.speed = 0.0

        self.steer += ((right - left) - self.steer) * min(1.0, 8 * dt)
        if abs(self.speed) > 0.1:
            turn = self.steer * ph['turn'] * min(1.0, abs(self.speed) / 5) * (1 if self.speed > 0 else -1) * dt
            if not self.collides(self.x, self.z, self.heading + turn):
                self.heading = (self.heading + turn) % 360

        h = math.radians(self.heading)
        nx = self.x + math.sin(h) * self.speed * dt
        nz = self.z + math.cos(h) * self.speed * dt
        if self.collides(nx, nz, self.heading):
            self.speed = -self.speed * 0.3
        else:
            self.x, self.z = nx, nz
        radius = self.wheels[0][0].y if self.wheels else 0.4
        self.spin = (self.spin + math.degrees(self.speed * dt / radius)) % 360
        self.sync()

    def sync(self):
        h = math.radians(self.heading)
        fx, fz = math.sin(h) * 1.5, math.cos(h) * 1.5
        front = self.world.ground_height(self.x + fx, self.z + fz)
        rear = self.world.ground_height(self.x - fx, self.z - fz)
        self.y = (front + rear) / 2
        self.pitch = -math.degrees(math.atan2(front - rear, 3.0))
        self.entity.position = (self.x, self.y, self.z)
        self.entity.rotation = (self.pitch, self.heading, 0)
        self.wheel.rotation_z = self.steer * 100
        for wheel, front in self.wheels:
            wheel.rotation = (self.spin, self.steer * 28 if front else 0, 0)
        if self.trailer is not None:
            self._sync_trailer(h)

    def _sync_trailer(self, h):
        length = self.spec['trailer_axle']
        hx = self.x - math.sin(h) * self.spec['hitch']
        hz = self.z - math.cos(h) * self.spec['hitch']
        if self.axle is None:
            self.axle = (hx - math.sin(h) * length, hz - math.cos(h) * length)
        dx, dz = hx - self.axle[0], hz - self.axle[1]
        d = math.hypot(dx, dz) or 1.0
        self.axle = (hx - dx / d * length, hz - dz / d * length)
        th = math.atan2(dx, dz)
        hy = self.world.ground_height(hx, hz)
        ay = self.world.ground_height(*self.axle)
        self.trailer.position = (hx, (hy + ay) / 2, hz)
        self.trailer.rotation = (-math.degrees(math.atan2(hy - ay, length)), math.degrees(th), 0)
        for wheel in self.trailer_wheels:
            wheel.rotation_x = self.spin


class Hud:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, enabled=False)
        tl = window.top_left
        Entity(parent=self.root, model=Quad(radius=0.02, aspect=0.6 / 0.12), color=C(0, 0, 0, 110),
               scale=(0.6, 0.12), origin=(-0.5, 0.5), position=(tl.x + 0.02, tl.y - 0.02, 1))
        self.coin_text = Text(parent=self.root, font=BOLD, origin=(-0.5, 0.5), scale=1.5, color=GOLD,
                              position=(tl.x + 0.045, tl.y - 0.035))
        self.info_text = Text(parent=self.root, origin=(-0.5, 0.5), scale=1.0, color=C(235, 235, 235),
                              position=(tl.x + 0.045, tl.y - 0.09))
        self.crosshair = Entity(parent=self.root, model=Quad(radius=0.5), scale=0.007, color=C(255, 255, 255, 200))
        self.hint = Text(parent=self.root, origin=(0, 0), y=-0.36, scale=1.3)
        self.speed_text = Text(parent=self.root, font=BOLD, origin=(-0.5, -0.5), scale=2.2,
                               position=(window.bottom_left.x + 0.04, window.bottom_left.y + 0.04))
        self.tip = Text(parent=self.root, origin=(0, 0), y=-0.44, scale=0.95, color=C(255, 255, 255, 220))
        self.toast = Text(parent=camera.ui, font=BOLD, origin=(0, 0), y=0.38, z=-2, scale=1.4, color=GOLD)
        self.toast_time = 0.0
        self.tip_time = 0.0
        self.pulse = 0.0

        tr_ = window.top_right
        size = 0.3
        Entity(parent=self.root, model='quad', color=C(20, 20, 20, 220), scale=size + 0.012,
               position=(tr_.x - 0.02 - size / 2, tr_.y - 0.02 - size / 2, 1))
        self.map = Entity(parent=self.root, model='quad', texture=Texture(models.minimap_image(game.world)),
                          scale=size, position=(tr_.x - 0.02 - size / 2, tr_.y - 0.02 - size / 2, 0.5))
        arrow = Mesh(vertices=[(0, 0.5, 0), (-0.35, -0.4, 0), (0.35, -0.4, 0)], triangles=[0, 1, 2])
        arrow.setTwoSided(True)
        self.car_dot = Entity(parent=self.map, model='quad', color=C(230, 40, 40), scale=(0.035, 0.05), z=-0.02)
        self.player_dot = Entity(parent=self.map, model=arrow, color=C(255, 255, 255), scale=0.06, z=-0.03)
        self.coin_dots = {}
        self._last = {}

    def _set(self, name, entity, text):
        if self._last.get(name) != text:
            self._last[name] = text
            entity.text = text

    def show(self, flag):
        self.root.enabled = flag

    def build_coin_dots(self, coins):
        for dot in self.coin_dots.values():
            destroy(dot)
        self.coin_dots = {}
        for idx, entity, *_ in coins:
            self.coin_dots[idx] = Entity(parent=self.map, model='quad', color=GOLD, scale=0.018, z=-0.01,
                                         position=(entity.x / W.SIZE - 0.5, entity.z / W.SIZE - 0.5))

    def add_coin_dot(self, idx, entity):
        self.coin_dots[idx] = Entity(parent=self.map, model='quad', color=GOLD, scale=0.018, z=-0.01,
                                     position=(entity.x / W.SIZE - 0.5, entity.z / W.SIZE - 0.5))

    def remove_coin_dot(self, idx):
        dot = self.coin_dots.pop(idx, None)
        if dot:
            destroy(dot)

    def show_toast(self, text):
        self.toast.text = text
        self.toast_time = 2.0

    def refresh_language(self):
        self._last = {}
        self.tip_time = max(self.tip_time, 0.01)

    def update(self, dt):
        g, tr = self.game, self.game.tr
        p, car = g.player, g.car
        self._set('coins', self.coin_text, tr('coins_admin') if g.admin else tr('coins', c=g.wallet))
        self.pulse = max(0.0, self.pulse - dt * 4)
        self.coin_text.scale = 1.5 + self.pulse * 0.4
        mode = tr('in_car') if g.in_car else tr('on_foot')
        self._set('info', self.info_text, f"{tr('collected', c=min(g.total, W.COIN_COUNT), t=W.COIN_COUNT)}    "
                                          f"{mode}    {tr('time', t=fmt_time(g.play_time))}")
        self.crosshair.enabled = not g.in_car

        if g.in_car:
            self._set('speed', self.speed_text, tr('speed', v=int(abs(car.speed) * 3.6)))
            if abs(car.speed) < 1.5:
                hint = tr('hint_exit', key=g.key_label('interact'), cam=g.key_label('camera'))
            else:
                hint = tr('hint_stop')
        else:
            self._set('speed', self.speed_text, '')
            near = g.nearby()
            hint = tr('hint_enter', key=g.key_label('interact')) if near == 'car' else \
                tr('hint_garage', key=g.key_label('interact')) if near == 'garage' else ''
        self._set('hint', self.hint, hint)

        if self.tip_time > 0:
            self.tip_time -= dt
            keys = '/'.join(g.key_label(a) for a in ('forward', 'left', 'back', 'right'))
            self._set('tip', self.tip, tr('tip', keys=keys, run=g.key_label('run'), jump=g.key_label('jump'))
                      if self.tip_time > 0 else '')
        if self.toast_time > 0:
            self.toast_time -= dt
            self.toast.alpha = min(1.0, self.toast_time)

        fx, fz, yaw = (car.x, car.z, car.heading) if g.in_car else (p.x, p.z, p.yaw)
        self.player_dot.position = (fx / W.SIZE - 0.5, fz / W.SIZE - 0.5, -0.03)
        self.player_dot.rotation_z = yaw
        self.car_dot.position = (car.x / W.SIZE - 0.5, car.z / W.SIZE - 0.5, -0.02)
        self.car_dot.rotation_z = car.heading
        self.car_dot.enabled = not g.in_car


class Menu:
    def __init__(self, game):
        self.game = game
        self.items = []
        self.waiting_action = None
        self.screen = None
        self.settings_back = None

    @property
    def tr(self):
        return self.game.tr

    def clear(self):
        for e in self.items:
            destroy(e)
        self.items = []
        self.waiting_action = None
        self.screen = None

    def add(self, e):
        self.items.append(e)
        return e

    def dim(self, alpha=120):
        return self.add(Entity(parent=camera.ui, model='quad', color=C(0, 0, 0, alpha), scale=(4, 2), z=5))

    def panel(self, w, h, x=0, y=0, alpha=170):
        return self.add(Entity(parent=camera.ui, model=Quad(radius=0.03, aspect=w / h), color=C(10, 25, 18, alpha),
                               scale=(w, h), position=(x, y, 4)))

    def label(self, text, x=0, y=0, scale=1.2, origin=(0, 0), color=None, bold=False):
        return self.add(Text(text, parent=camera.ui, position=(x, y, -1), scale=scale, origin=origin,
                             color=color or C(255, 255, 255), font=BOLD if bold else Text.default_font))

    def title(self, text, y):
        self.label(text, 0.004, y - 0.006, scale=3.2, color=C(0, 0, 0, 150), bold=True)
        self.label(text, 0, y, scale=3.2, color=GOLD, bold=True)

    def button(self, text, on_click, x=0, y=0, w=0.5, h=0.075, color=BTN, text_scale=1.2):
        b = self.add(Button(text=text, parent=camera.ui, position=(x, y, -1), scale=(w, h), radius=0.25,
                            color=color, highlight_color=BTN_HI, pressed_color=color.tint(-0.2), on_click=on_click))
        b.text_entity.world_scale = text_scale
        return b

    def show_main(self):
        self.clear()
        self.screen = 'main'
        self.dim(70)
        self.title(self.tr('title'), 0.25)
        self.button(self.tr('play'), self.show_slots, y=0.04)
        self.button(self.tr('settings'), lambda: self.show_settings(self.show_main), y=-0.06)
        self.button(self.tr('quit'), self.game.quit, y=-0.16, color=BTN_RED)

    def show_slots(self):
        self.clear()
        self.screen = 'slots'
        self.dim(90)
        self.title(self.tr('choose_save'), 0.36)
        for n in range(1, storage.SLOTS + 1):
            y = 0.19 - (n - 1) * 0.18
            data = storage.load_slot(n)
            self.panel(1.3, 0.15, 0, y)
            self.label(self.tr('slot', n=n), -0.62, y + 0.03, scale=1.5, origin=(-0.5, 0), bold=True)
            if data:
                total = data.get('total', len(data.get('collected', [])))
                info = self.tr('slot_info', w=data.get('wallet', total), c=min(total, W.COIN_COUNT), t=W.COIN_COUNT,
                               time=fmt_time(data.get('time', 0)), date=data.get('saved_at', ''))
                self.button(self.tr('continue'), lambda n=n: self.game.start_slot(n, new=False),
                            x=0.12, y=y, w=0.24, h=0.065, color=C(40, 120, 70, 240), text_scale=1.0)
                self.button(self.tr('new_game'), lambda n=n: self.confirm(
                    self.tr('confirm_new', n=n), lambda: self.game.start_slot(n, new=True), self.show_slots),
                    x=0.38, y=y, w=0.24, h=0.065, text_scale=1.0)
                self.button(self.tr('delete'), lambda n=n: self.confirm(
                    self.tr('confirm_del', n=n), lambda: (storage.delete_slot(n), self.show_slots()), self.show_slots),
                    x=0.565, y=y, w=0.11, h=0.065, color=BTN_RED, text_scale=0.8)
            else:
                info = self.tr('empty')
                self.button(self.tr('new_game'), lambda n=n: self.game.start_slot(n, new=True),
                            x=0.38, y=y, w=0.24, h=0.065, text_scale=1.0)
            self.label(info, -0.62, y - 0.035, scale=0.9, origin=(-0.5, 0), color=C(210, 225, 210))
        self.button(self.tr('back'), self.show_main, y=-0.38, w=0.3)
        if ADMIN:
            self.button(self.tr('admin_mode'), lambda: self.game.start_slot('admin', new=False),
                        x=0.45, y=-0.38, w=0.34, color=BTN_ON, text_scale=1.0)

    def confirm(self, text, on_yes, on_no):
        self.clear()
        self.screen = 'confirm'
        self.dim(140)
        self.panel(1.0, 0.32)
        self.label(text, 0, 0.06, scale=1.3)
        self.button(self.tr('yes'), on_yes, x=-0.14, y=-0.06, w=0.22, color=BTN_RED)
        self.button(self.tr('no'), on_no, x=0.14, y=-0.06, w=0.22)
        self._confirm_no = on_no

    def show_settings(self, back):
        self.clear()
        self.screen = 'settings'
        self.settings_back = back
        g, s = self.game, self.game.settings
        self.dim(140)
        self.panel(1.25, 0.96)
        self.label(self.tr('settings'), 0, 0.42, scale=2.2, color=GOLD, bold=True)

        lx = -0.56
        self.label(self.tr('language'), lx, 0.33, origin=(-0.5, 0))
        for i, (code, name) in enumerate(LANGUAGES.items()):
            self.button(name, lambda code=code: g.set_language(code), x=0.05 + i * 0.19, y=0.33, w=0.18, h=0.055,
                        color=BTN_ON if s['language'] == code else BTN, text_scale=1.0)

        self.label(self.tr('sensitivity'), lx, 0.25, origin=(-0.5, 0))
        self.button('-', lambda: g.change_sensitivity(-0.1), x=0.1, y=0.25, w=0.07, h=0.055)
        self.label(f"{s['sensitivity']:.1f}", 0.24, 0.25)
        self.button('+', lambda: g.change_sensitivity(0.1), x=0.38, y=0.25, w=0.07, h=0.055)

        self.label(self.tr('invert_y'), lx, 0.17, origin=(-0.5, 0))
        self.button(self.tr('on') if s['invert_y'] else self.tr('off'), g.toggle_invert, x=0.24, y=0.17,
                    w=0.2, h=0.055, color=BTN_ON if s['invert_y'] else BTN, text_scale=1.0)

        self.label(self.tr('controls'), 0, 0.09, scale=1.4, color=GOLD, bold=True)
        self.key_buttons = {}
        for i, action in enumerate(storage.ACTIONS):
            y = 0.03 - i * 0.052
            self.label(self.tr('act_' + action), lx, y, scale=1.05, origin=(-0.5, 0))
            self.key_buttons[action] = self.button(
                g.key_label(action), lambda a=action: self.wait_key(a), x=0.24, y=y, w=0.3, h=0.045, text_scale=1.0)
        self.button(self.tr('reset_keys'), g.reset_keys, x=-0.2, y=-0.43, w=0.36, h=0.06, text_scale=1.0)
        self.button(self.tr('back'), back, x=0.2, y=-0.43, w=0.3, h=0.06)

    def wait_key(self, action):
        if self.waiting_action:
            self.key_buttons[self.waiting_action].text = self.game.key_label(self.waiting_action)
        self.waiting_action = action
        b = self.key_buttons[action]
        b.text = self.tr('press_key')
        b.text_entity.world_scale = 1.0
        b.color = BTN_ON

    def show_pause(self):
        self.clear()
        self.screen = 'pause'
        g = self.game
        self.dim(120)
        self.title(self.tr('paused'), 0.26)
        self.button(self.tr('resume'), g.resume, y=0.08)
        self.button(self.tr('save'), lambda: g.save(toast=True), y=-0.01)
        self.button(self.tr('settings'), lambda: self.show_settings(self.show_pause), y=-0.10)
        self.button(self.tr('to_menu'), g.exit_to_menu, y=-0.19, w=0.56)
        self.button(self.tr('quit'), g.quit, y=-0.28, color=BTN_RED)

    def show_win(self):
        self.clear()
        self.screen = 'win'
        g = self.game
        self.dim(130)
        self.title(self.tr('win_title'), 0.2)
        self.label(self.tr('win_text', t=W.COIN_COUNT, time=fmt_time(g.play_time)), 0, 0.07, scale=1.5)
        self.button(self.tr('keep_walking'), g.resume, y=-0.06, w=0.42)
        self.button(self.tr('main_menu'), g.exit_to_menu, y=-0.16, w=0.42)

    def swatch(self, col, on_click, x, y, selected, w=0.1, h=0.07):
        if selected:
            self.add(Entity(parent=camera.ui, model=Quad(radius=0.25, aspect=(w + 0.018) / (h + 0.018)), color=GOLD,
                            scale=(w + 0.018, h + 0.018), position=(x, y, 0)))
        c = Color(col[0], col[1], col[2], 1)
        self.add(Button(parent=camera.ui, position=(x, y, -1), scale=(w, h), radius=0.25, color=c,
                        highlight_color=c.tint(0.15), pressed_color=c.tint(-0.15), on_click=on_click))

    def show_garage(self, tab='cars'):
        self.clear()
        self.screen = 'garage'
        self.garage_tab = tab
        g, tr = self.game, self.tr
        px = window.top_right.x - 0.4
        self.panel(0.74, 0.96, px, 0, alpha=205)
        self.label(tr('garage'), px, 0.42, scale=2.2, color=GOLD, bold=True)
        self.label(tr('coins_admin') if g.admin else tr('coins', c=g.wallet), px, 0.355, scale=1.3, color=GOLD)
        self.button(tr('tab_cars'), lambda: self.show_garage('cars'), x=px - 0.17, y=0.29, w=0.32, h=0.06,
                    color=BTN_ON if tab == 'cars' else BTN, text_scale=1.1)
        self.button(tr('tab_tuning'), lambda: self.show_garage('tuning'), x=px + 0.17, y=0.29, w=0.32, h=0.06,
                    color=BTN_ON if tab == 'tuning' else BTN, text_scale=1.1)
        gar = g.garage
        if tab == 'cars':
            for i, mid in enumerate(car_model.MODELS):
                spec = car_model.SPECS[mid]
                y = 0.19 - i * 0.115
                self.panel(0.68, 0.1, px, y, alpha=120)
                self.label(tr('car_' + mid), px - 0.32, y + 0.02, scale=1.2, origin=(-0.5, 0), bold=True)
                ph = spec['phys']
                self.label(tr('car_stats', v=int(ph['max_road'] * 3.6), off=int(ph['max_off'] * 3.6)),
                           px - 0.32, y - 0.027, scale=0.78, origin=(-0.5, 0), color=C(210, 225, 210))
                if mid == gar['current']:
                    self.button(tr('selected'), lambda: None, x=px + 0.23, y=y, w=0.19, h=0.055, color=BTN_ON,
                                text_scale=1.0)
                elif mid in gar['owned']:
                    self.button(tr('select'), lambda m=mid: g.select_car(m), x=px + 0.23, y=y, w=0.19, h=0.055,
                                text_scale=1.0)
                else:
                    self.button(tr('buy', p=spec['price']), lambda m=mid: g.buy_car(m), x=px + 0.23, y=y,
                                w=0.19, h=0.055, color=C(40, 120, 70, 240) if g.can_afford(spec['price']) else BTN,
                                text_scale=1.0)
        else:
            mid = gar['current']
            t = g.tuning(mid)
            self.label(tr('tuning_for', name=tr('car_' + mid)), px, 0.215, scale=1.3, bold=True)
            self.label(tr('paint', p=PAINT_PRICE), px - 0.33, 0.155, scale=1.0, origin=(-0.5, 0))
            for j, (_, col) in enumerate(car_model.PAINTS):
                self.swatch(col, lambda j=j: g.buy_paint(j), px - 0.24 + (j % 5) * 0.12, 0.09 - (j // 5) * 0.09,
                            t['color'] == j)
            self.label(tr('rims', p=RIM_PRICE), px - 0.33, -0.085, scale=1.0, origin=(-0.5, 0))
            for j, (_, col) in enumerate(car_model.RIMS):
                self.swatch(col, lambda j=j: g.buy_rims(j), px - 0.24 + j * 0.12, -0.15, t['rims'] == j)
            self.label(tr('engine', lvl=t['engine'], max=len(ENGINE_PRICES)), px - 0.33, -0.225, scale=1.0,
                       origin=(-0.5, 0))
            self.label(tr('engine_bonus'), px - 0.33, -0.262, scale=0.75, origin=(-0.5, 0), color=C(210, 225, 210))
            if t['engine'] < len(ENGINE_PRICES):
                price = ENGINE_PRICES[t['engine']]
                self.button(tr('upgrade', p=price), g.upgrade_engine, x=px, y=-0.32, w=0.36, h=0.06,
                            color=C(40, 120, 70, 240) if g.can_afford(price) else BTN, text_scale=1.0)
            else:
                self.button(tr('max_level'), lambda: None, x=px, y=-0.32, w=0.36, h=0.06, color=BTN_ON,
                            text_scale=1.0)
        self.button(tr('leave_garage'), g.close_garage, x=px, y=-0.42, w=0.46, h=0.065, color=BTN_RED, text_scale=1.1)

    def back(self):
        if self.waiting_action:
            return
        if self.screen == 'settings':
            self.settings_back()
        elif self.screen == 'slots':
            self.show_main()
        elif self.screen == 'confirm':
            self._confirm_no()


class Game(Entity):
    def __init__(self):
        super().__init__()
        self.settings = storage.load_settings()
        if self.settings['language'] not in LANGUAGES:
            self.settings['language'] = 'ru'
        self.tr = Tr(self.settings['language'])
        window.title = self.tr('title')

        self.world = W.World()
        models.build_ground(self.world)
        models.build_water(self.world)
        models.build_roads(self.world)
        models.build_trees(self.world)
        models.build_decor(self.world)
        models.build_outskirts(self.world)
        models.build_garage(self.world)
        gx, gz = self.world.garage_door
        self.garage_sign = Text(parent=scene, font=BOLD, text='', origin=(0, 0), billboard=True, scale=40,
                                color=GOLD, position=(gx - 0.4, self.world.ground_height(gx, gz) + 6.4, gz))
        self.clouds = models.build_clouds()

        self.car = Car(self.world)
        self.player = Player()
        self.coin_mesh = models.coin_mesh()
        self.coins = []
        self.coin_positions = []
        self.pending = {}
        self.wallet = 0
        self.admin = False
        self.total = 0
        self.garage = {'owned': ['sedan'], 'current': 'sedan', 'tuning': {}}
        self.particles = []
        self.coin_sound = self._load_sound()
        self.mouse = MouseLook()

        self.state = 'menu'
        self.slot = None
        self.coin_seed = 1
        self.play_time = 0.0
        self.finished = False
        self.in_car = False
        self.cam_mode = 'first'
        self.look_yaw = self.look_pitch = 0.0
        self.autosave = 0.0
        self.respawn_timer = 0.0
        self.menu_angle = 0.0
        self.garage_angle = 0.0

        self.apply_save(self.new_save_data())
        self.hud = Hud(self)
        self.menu = Menu(self)
        self.garage_sign.text = self.tr('garage').upper()
        self.menu.show_main()
        application.base.exitFunc = self.on_exit

    def _load_sound(self):
        path = BASE / 'sounds' / 'coin.wav'
        try:
            if not path.exists():
                path = storage.DATA_DIR / 'sounds' / 'coin.wav'
                if not path.exists():
                    make_coin_sound(path)
            return Audio(loader.loadSfx(Filename.fromOsSpecific(str(path))), autoplay=False, volume=0.5)
        except Exception:
            return None

    def key(self, action):
        return self.settings['keys'][action]

    def held(self, action):
        return held_keys[self.key(action)]

    def key_label(self, action):
        k = self.key(action)
        names = {'space': self.tr('key_space'), 'left shift': 'L-Shift', 'right shift': 'R-Shift',
                 'left control': 'L-Ctrl', 'right control': 'R-Ctrl', 'left alt': 'L-Alt', 'right alt': 'R-Alt',
                 'up arrow': 'Up', 'down arrow': 'Down', 'left arrow': 'Left', 'right arrow': 'Right',
                 'enter': 'Enter', 'tab': 'Tab', 'backspace': 'Backspace'}
        return names.get(k, k.upper())

    def save_settings(self):
        storage.save_settings(self.settings)

    def set_language(self, code):
        self.settings['language'] = code
        self.tr.lang = code
        window.title = self.tr('title')
        self.save_settings()
        self.hud.refresh_language()
        self.garage_sign.text = self.tr('garage').upper()
        self.menu.show_settings(self.menu.settings_back)

    def change_sensitivity(self, delta):
        s = self.settings
        s['sensitivity'] = round(min(3.0, max(0.2, s['sensitivity'] + delta)), 1)
        self.save_settings()
        self.menu.show_settings(self.menu.settings_back)

    def toggle_invert(self):
        self.settings['invert_y'] = not self.settings['invert_y']
        self.save_settings()
        self.menu.show_settings(self.menu.settings_back)

    def reset_keys(self):
        self.settings['keys'] = dict(storage.DEFAULT_KEYS)
        self.save_settings()
        self.hud.refresh_language()
        self.menu.show_settings(self.menu.settings_back)

    def bind_key(self, action, key):
        keys = self.settings['keys']
        for other, k in keys.items():
            if k == key and other != action:
                keys[other] = keys[action]
        keys[action] = key
        self.save_settings()
        self.hud.refresh_language()
        self.menu.show_settings(self.menu.settings_back)

    def new_save_data(self):
        path = self.world.paths[0]
        (ax, az), (bx, bz) = path[0], path[8]
        heading = math.degrees(math.atan2(bx - ax, bz - az))
        h = math.radians(heading)
        px, pz = ax - math.sin(h) * 6, az - math.cos(h) * 6
        return {
            'version': 2, 'coin_seed': random.randint(1, 10 ** 9), 'pending': {}, 'wallet': 0, 'total': 0,
            'time': 0.0, 'finished': False, 'in_car': False, 'cam_mode': 'first',
            'garage': {'owned': ['sedan'], 'current': 'sedan', 'tuning': {}},
            'player': {'x': px, 'y': self.world.ground_height(px, pz), 'z': pz, 'yaw': heading, 'pitch': 0.0},
            'car': {'x': ax, 'z': az, 'heading': heading},
        }

    def save_data(self):
        p, c = self.player, self.car
        return {
            'version': 2, 'coin_seed': self.coin_seed, 'time': self.play_time,
            'pending': {str(i): t for i, t in self.pending.items()}, 'wallet': self.wallet, 'total': self.total,
            'finished': self.finished, 'in_car': self.in_car, 'cam_mode': self.cam_mode, 'garage': self.garage,
            'player': {'x': p.x, 'y': p.y, 'z': p.z, 'yaw': p.yaw, 'pitch': p.pitch},
            'car': {'x': c.x, 'z': c.z, 'heading': c.heading},
        }

    def apply_save(self, d):
        self.coin_seed = d.get('coin_seed', 1)
        self.play_time = float(d.get('time', 0))
        pending = d.get('pending')
        if pending is None:
            pending = {str(i): self.play_time for i in d.get('collected', [])}
        self.pending = {int(i): float(t) for i, t in pending.items()}
        self.total = int(d.get('total', len(self.pending)))
        self.wallet = int(d.get('wallet', self.total))
        gar = d.get('garage') or {}
        owned = [m for m in gar.get('owned', ['sedan']) if m in car_model.SPECS] or ['sedan']
        current = gar.get('current', 'sedan')
        self.garage = {'owned': owned, 'current': current if current in owned else owned[0],
                       'tuning': dict(gar.get('tuning', {}))}
        self.finished = bool(d.get('finished', False))
        self.in_car = bool(d.get('in_car', False))
        self.cam_mode = d.get('cam_mode', 'first')
        p, pd = self.player, d['player']
        p.x, p.y, p.z, p.yaw, p.pitch = pd['x'], pd['y'], pd['z'], pd['yaw'], pd.get('pitch', 0.0)
        p.vy = 0.0
        c, cd = self.car, d['car']
        c.set_model(self.garage['current'], self.tuning(self.garage['current']))
        c.place(cd['x'], cd['z'], cd['heading'])
        self.look_yaw = self.look_pitch = 0.0
        self.spawn_coins()

    def spawn_coins(self):
        for _, e, *_ in self.coins:
            destroy(e)
        self.coins = []
        self.coin_positions = self.world.make_coins(self.coin_seed)
        for idx in range(len(self.coin_positions)):
            if idx not in self.pending:
                self.spawn_coin(idx)

    def spawn_coin(self, idx):
        x, y, z = self.coin_positions[idx]
        e = Entity(position=(x, y, z), rotation_y=random.uniform(0, 360))
        self.coin_mesh.instanceTo(e)
        self.coins.append([idx, e, y, random.uniform(0, math.tau)])
        return e

    def respawn_coins(self):
        for idx, t in list(self.pending.items()):
            if self.play_time - t >= RESPAWN:
                del self.pending[idx]
                self.hud.add_coin_dot(idx, self.spawn_coin(idx))

    def tuning(self, model_id):
        t = self.garage['tuning'].setdefault(model_id, {})
        t.setdefault('color', car_model.SPECS[model_id]['color'])
        t.setdefault('rims', 0)
        t.setdefault('engine', 0)
        return t

    def nearby(self):
        p, car = self.player, self.car
        to_door = math.hypot(p.x - self.world.garage_door[0], p.z - self.world.garage_door[1])
        to_car = min(math.hypot(p.x - cx, p.z - cz) for cx, cz in car.circles(car.x, car.z, car.heading))
        if to_door < 3.5 and to_door < to_car:
            return 'garage'
        if to_car < car.radius + 2.2:
            return 'car'
        return None

    def open_garage(self):
        self.save()
        self.state = 'garage'
        self.in_car = False
        self.mouse.lock(False)
        self.hud.show(False)
        self.park_at_garage()
        if camera.parent != scene:
            camera.parent = scene
        self.menu.show_garage('cars')

    def park_at_garage(self):
        px, pz = self.world.garage_pad
        self.car.place(px, pz, 0.0)

    def close_garage(self):
        p = self.player
        dx, dz = self.world.garage_door
        p.x, p.z = dx - 1.5, dz
        p.y = self.world.ground_height(p.x, p.z)
        p.yaw, p.pitch, p.vy = 270.0, 0.0, 0.0
        self.save()
        self.resume()

    def refresh_car(self):
        mid = self.garage['current']
        self.car.set_model(mid, self.tuning(mid))
        self.park_at_garage()

    def can_afford(self, amount):
        return self.admin or self.wallet >= amount

    def spend(self, amount):
        if self.admin:
            self.hud.show_toast(self.tr('bought'))
            return True
        if self.wallet < amount:
            self.hud.show_toast(self.tr('no_money'))
            return False
        self.wallet -= amount
        self.hud.show_toast(self.tr('bought'))
        return True

    def buy_car(self, model_id):
        if self.spend(car_model.SPECS[model_id]['price']):
            self.garage['owned'].append(model_id)
            self.select_car(model_id)

    def select_car(self, model_id):
        self.garage['current'] = model_id
        self.refresh_car()
        self.save()
        self.menu.show_garage('cars')

    def buy_paint(self, idx):
        t = self.tuning(self.garage['current'])
        if t['color'] != idx and self.spend(PAINT_PRICE):
            t['color'] = idx
            self.refresh_car()
            self.save()
        self.menu.show_garage('tuning')

    def buy_rims(self, idx):
        t = self.tuning(self.garage['current'])
        if t['rims'] != idx and self.spend(RIM_PRICE):
            t['rims'] = idx
            self.refresh_car()
            self.save()
        self.menu.show_garage('tuning')

    def upgrade_engine(self):
        t = self.tuning(self.garage['current'])
        if t['engine'] < len(ENGINE_PRICES) and self.spend(ENGINE_PRICES[t['engine']]):
            t['engine'] += 1
            self.car.engine = t['engine']
            self.save()
        self.menu.show_garage('tuning')

    def save(self, toast=False):
        if self.slot is None:
            return
        storage.write_slot(self.slot, self.save_data())
        if toast:
            self.hud.show_toast(self.tr('saved'))

    def start_slot(self, n, new):
        data = None if new else storage.load_slot(n)
        self.slot = n
        self.admin = n == 'admin'
        try:
            self.apply_save(data or self.new_save_data())
        except (KeyError, TypeError, ValueError):
            self.apply_save(self.new_save_data())
        self.save()
        self.hud.build_coin_dots(self.coins)
        self.hud.tip_time = 12.0
        self.autosave = 0.0
        self.resume()

    def resume(self):
        self.menu.clear()
        self.hud.show(True)
        self.state = 'play'
        self.mouse.lock(True)

    def pause(self):
        self.save()
        self.state = 'pause'
        self.mouse.lock(False)
        self.menu.show_pause()

    def exit_to_menu(self):
        self.save()
        self.slot = None
        self.admin = False
        self.state = 'menu'
        self.hud.show(False)
        self.mouse.lock(False)
        self.menu.show_main()

    def on_exit(self):
        if self.state != 'menu':
            self.save()

    def quit(self):
        self.on_exit()
        application.quit()

    def input(self, key):
        menu = self.menu
        if menu.waiting_action:
            if key == 'escape':
                menu.show_settings(menu.settings_back)
            elif not (key.endswith(' up') or key.endswith(' hold') or 'mouse' in key or 'scroll' in key):
                self.bind_key(menu.waiting_action, key)
            return

        if key == 'escape':
            if self.state == 'play':
                self.pause()
            elif self.state == 'pause':
                if menu.screen == 'pause':
                    self.resume()
                else:
                    menu.back()
            elif self.state == 'menu':
                menu.back()
            elif self.state == 'garage':
                self.close_garage()
            return

        if self.state != 'play':
            return
        p, car = self.player, self.car
        if key == self.key('interact'):
            if not self.in_car:
                near = self.nearby()
                if near == 'garage':
                    self.open_garage()
                elif near == 'car':
                    self.in_car = True
                    self.look_yaw = self.look_pitch = 0.0
            elif abs(car.speed) < 1.5:
                self.exit_car()
        elif key == self.key('jump') and not self.in_car and p.grounded:
            p.vy = 6.0
            p.grounded = False
        elif key == self.key('camera') and self.in_car:
            self.cam_mode = 'third' if self.cam_mode == 'first' else 'first'

    def exit_car(self):
        car, p = self.car, self.player
        h = math.radians(car.heading)
        fx, fz = math.sin(h), math.cos(h)
        rx, rz = math.cos(h), -math.sin(h)
        side, along = car.phys['exit'], max(car.phys['circles']) + car.radius + 1.0
        for ox, oz in ((-rx * side, -rz * side), (rx * side, rz * side), (-fx * along, -fz * along),
                       (fx * along, fz * along)):
            x, z = car.x + ox, car.z + oz
            if not self.world.blocked(x, z, Player.RADIUS):
                p.x, p.z = x, z
                p.y = self.world.ground_height(x, z)
                p.vy = 0.0
                p.yaw, p.pitch = car.heading, 0.0
                car.speed = 0.0
                self.in_car = False
                return

    def update(self):
        dt = min(time.dt, 0.05)
        if self.state == 'menu':
            self.menu_angle += dt * 0.06
            c = W.SIZE / 2
            if camera.parent != scene:
                camera.parent = scene
            camera.position = (c + math.cos(self.menu_angle) * 95, 32, c + math.sin(self.menu_angle) * 95)
            look_at(Vec3(c, 0, c))
        self.clouds.x = (self.clouds.x + dt * 1.5) % 60
        if self.state == 'garage':
            self.garage_angle += dt * 0.3
            car = self.car
            h = math.radians(car.heading)
            back = 6.0 if car.trailer is not None else 0.0
            cx, cz = car.x - math.sin(h) * back, car.z - math.cos(h) * back
            r = car.phys['view']
            a = math.pi + math.sin(self.garage_angle) * 1.0
            cam = Vec3(cx + math.cos(a) * r, car.y + r * 0.32 + 1.0, cz + math.sin(a) * r)
            fx, fz = cx - cam.x, cz - cam.z
            length = math.hypot(fx, fz) or 1
            camera.position = cam
            look_at(Vec3(cx + fz / length * r * 0.3, car.y + 0.8, cz - fx / length * r * 0.3))

        if self.state == 'play':
            self.play_time += dt
            self.autosave += dt
            if self.autosave > 60:
                self.autosave = 0.0
                self.save()
            self.respawn_timer += dt
            if self.respawn_timer > 1.0:
                self.respawn_timer = 0.0
                self.respawn_coins()
            if self.in_car:
                self.update_car(dt)
            else:
                self.update_walk(dt)
            self.collect_coins()

        if self.state in ('play', 'win', 'menu', 'garage'):
            for item in self.coins:
                e = item[1]
                e.rotation_y += 140 * dt
                e.y = item[2] + math.sin(self.play_time * 2.5 + item[3]) * 0.12
        for part in self.particles[:]:
            part[1] -= dt
            part[2].y -= 9 * dt
            part[0].position += part[2] * dt
            part[0].scale = max(0.001, part[1] * 0.18)
            if part[1] <= 0:
                destroy(part[0])
                self.particles.remove(part)
        glass_alpha = 0.15 if self.in_car and self.cam_mode == 'first' and self.state != 'menu' else 1.0
        if self.car.glass_alpha != glass_alpha:
            self.car.glass_alpha = glass_alpha
            for part in self.car.glass:
                part.alpha = glass_alpha
        if self.state != 'menu':
            self.hud.update(dt)

    def mouse_look(self):
        dx, dy = self.mouse.delta()
        k = self.settings['sensitivity'] * 0.15
        inv = -1 if self.settings['invert_y'] else 1
        return dx * k, -dy * k * inv

    def update_walk(self, dt):
        p = self.player
        dx, dy = self.mouse_look()
        p.yaw = (p.yaw + dx) % 360
        p.pitch = min(85.0, max(-85.0, p.pitch - dy))

        f = self.held('forward') - self.held('back')
        s = self.held('right') - self.held('left')
        h = math.radians(p.yaw)
        mx = math.sin(h) * f + math.cos(h) * s
        mz = math.cos(h) * f - math.sin(h) * s
        length = math.hypot(mx, mz)
        moving = length > 0
        if moving:
            speed = 8.0 if self.held('run') else 4.5
            mx, mz = mx / length * speed * dt, mz / length * speed * dt
            if p.grounded:
                p.bob += dt * speed * 1.6
            if self.walk_free(p.x + mx, p.z):
                p.x += mx
            if self.walk_free(p.x, p.z + mz):
                p.z += mz

        ground = self.world.ground_height(p.x, p.z)
        p.vy -= 20 * dt
        p.y += p.vy * dt
        if p.y <= ground or (p.grounded and p.vy <= 0 and p.y - ground < 0.35):
            p.y, p.vy, p.grounded = ground, 0.0, True
        else:
            p.grounded = False

        bob = math.sin(p.bob * 2) * 0.05 if moving and p.grounded else 0.0
        if camera.parent != scene:
            camera.parent = scene
        camera.position = (p.x, p.y + Player.EYE + bob, p.z)
        camera.rotation = (p.pitch, p.yaw, 0)

    def walk_free(self, x, z):
        if self.world.blocked(x, z, Player.RADIUS):
            return False
        return all(math.hypot(x - cx, z - cz) > Player.RADIUS + self.car.radius
                   for cx, cz in self.car.circles(self.car.x, self.car.z, self.car.heading))

    def update_car(self, dt):
        car = self.car
        car.update(dt, self.held('forward'), self.held('back'), self.held('left'), self.held('right'),
                   self.held('jump'))
        p = self.player
        p.x, p.z, p.y = car.x, car.z, car.y
        if self.cam_mode == 'first':
            dx, dy = self.mouse_look()
            self.look_yaw = min(110.0, max(-110.0, self.look_yaw + dx))
            self.look_pitch = min(45.0, max(-35.0, self.look_pitch - dy))
            if camera.parent != car.seat:
                camera.parent = car.seat
            camera.position = (0, 0, 0)
            camera.rotation = (self.look_pitch, self.look_yaw, 0)
        else:
            h = math.radians(car.heading)
            back, up = car.phys['cam']
            target = Vec3(car.x - math.sin(h) * back, car.y + up, car.z - math.cos(h) * back)
            if camera.parent != scene:
                camera.parent = scene
                camera.position = target
            camera.position = lerp(camera.position, target, min(1.0, dt * 6))
            look_at(Vec3(car.x, car.y + up * 0.35, car.z))

    def collect_coins(self):
        if self.in_car:
            fx, fy, fz, reach = self.car.x, self.car.y + 1.0, self.car.z, self.car.phys['reach']
        else:
            fx, fy, fz, reach = self.player.x, self.player.y + 1.0, self.player.z, 1.6
        for item in self.coins[:]:
            idx, e, base, _ = item
            if abs(e.x - fx) < reach and abs(e.z - fz) < reach and \
                    math.hypot(e.x - fx, e.z - fz) < reach and abs(base - fy) < 2.5:
                self.coins.remove(item)
                self.pending[idx] = self.play_time
                self.wallet += 1
                self.total += 1
                self.hud.remove_coin_dot(idx)
                self.hud.pulse = 1.0
                for _ in range(10):
                    v = Vec3(random.uniform(-2, 2), random.uniform(2, 5), random.uniform(-2, 2))
                    part = Entity(model='cube', color=GOLD, position=e.position, scale=0.12)
                    self.particles.append([part, 0.7, v])
                destroy(e)
                if self.coin_sound:
                    self.coin_sound.play()
        if self.total >= W.COIN_COUNT and not self.finished:
            self.finished = True
            self.save()
            self.state = 'win'
            self.mouse.lock(False)
            self.menu.show_win()


game = Game()
app.run()
