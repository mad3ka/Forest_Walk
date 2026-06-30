import math
import random
import sys

import pygame

W, H = 1100, 700
WORLD_W, WORLD_H = 3200, 3200
FPS = 60
COIN_COUNT = 200

pygame.init()
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Лесная бродилка")
clock = pygame.time.Clock()


def make_font(size, bold=False):
    return pygame.font.SysFont("arial", size, bold=bold)


FONT_SMALL = make_font(18)
FONT = make_font(24, bold=True)
FONT_BIG = make_font(56, bold=True)


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


ROAD_WIDTH = 90
ROAD_STEP = 6
GRID = 100


class World:
    def __init__(self, seed=7):
        rnd = random.Random(seed)
        self._make_roads()
        self.lakes = self._make_lakes(rnd)
        self.spawn = self.paths[0][0]
        self.trees = self._make_trees(rnd)
        self.background = self._render_background(rnd)
        self.minimap = pygame.transform.smoothscale(self.background, (180, 180))
        self.tree_cache = {}

    @staticmethod
    def _resample(points, step=ROAD_STEP):
        out = [points[0]]
        carry = 0.0
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            seg = dist(ax, ay, bx, by)
            d = step - carry
            while d <= seg:
                t = d / seg
                out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
                d += step
            carry = seg - (d - step)
        return out

    def _make_roads(self):
        cx, cy = WORLD_W / 2, WORLD_H / 2
        n = 2000
        loop = []
        for i in range(n + 1):
            a = i / n * math.tau
            r = 1150 + 150 * math.sin(3 * a) + 60 * math.cos(2 * a + 1)
            loop.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        cross = []
        for i in range(n + 1):
            t = i / n
            cross.append((450 + t * (WORLD_W - 900), cy + 240 * math.sin(t * math.pi * 2)))
        north = []
        for i in range(n + 1):
            t = i / n
            north.append((cx + 200 * math.sin(t * math.pi * 1.5), cy - t * 1350))
        self.paths = [self._resample(p) for p in (loop, cross, north)]

        self.road_grid = {}
        for path in self.paths:
            for x, y in path:
                self.road_grid.setdefault((int(x // GRID), int(y // GRID)), []).append((x, y))

    def _make_lakes(self, rnd):
        lakes = []
        tries = 0
        while len(lakes) < 6 and tries < 500:
            tries += 1
            rx, ry = rnd.randint(120, 260), rnd.randint(90, 200)
            x = rnd.randint(rx + 50, WORLD_W - rx - 50)
            y = rnd.randint(ry + 50, WORLD_H - ry - 50)
            if self.road_distance(x, y) < max(rx, ry) + 90:
                continue
            if any(dist(x, y, lx, ly) < max(rx, ry) + max(lrx, lry) + 80 for lx, ly, lrx, lry in lakes):
                continue
            lakes.append((x, y, rx, ry))
        return lakes

    def _make_trees(self, rnd):
        trees = []
        sx, sy = self.spawn
        for _ in range(2600):
            r = rnd.randint(26, 46)
            x = rnd.randint(30, WORLD_W - 30)
            y = rnd.randint(30, WORLD_H - 30)
            if self.road_distance(x, y) < ROAD_WIDTH / 2 + r * 0.6:
                continue
            if self.in_lake(x, y, r + 20):
                continue
            if dist(x, y, sx, sy) < 220:
                continue
            if any(dist(x, y, tx, ty) < (r + tr) * 0.75 for tx, ty, tr, _ in trees):
                continue
            trees.append((x, y, r, rnd.randint(0, 2)))
            if len(trees) >= 520:
                break
        return trees

    def _render_background(self, rnd):
        bg = pygame.Surface((WORLD_W, WORLD_H))
        bg.fill((78, 140, 62))
        for _ in range(900):
            c = rnd.choice([(70, 130, 56), (86, 150, 68), (74, 136, 58), (92, 156, 72)])
            pygame.draw.circle(bg, c, (rnd.randint(0, WORLD_W), rnd.randint(0, WORLD_H)), rnd.randint(20, 70))
        for _ in range(9000):
            c = rnd.choice([(60, 118, 48), (100, 166, 78)])
            x, y = rnd.randint(0, WORLD_W), rnd.randint(0, WORLD_H)
            pygame.draw.line(bg, c, (x, y), (x + rnd.randint(-2, 2), y - rnd.randint(3, 7)), 2)
        for _ in range(700):
            c = rnd.choice([(240, 240, 240), (250, 220, 60), (230, 90, 120), (160, 120, 230)])
            pygame.draw.circle(bg, c, (rnd.randint(0, WORLD_W), rnd.randint(0, WORLD_H)), 3)
        for x, y, rx, ry in self.lakes:
            pygame.draw.ellipse(bg, (196, 178, 120), (x - rx - 22, y - ry - 22, 2 * rx + 44, 2 * ry + 44))
            pygame.draw.ellipse(bg, (40, 110, 170), (x - rx, y - ry, 2 * rx, 2 * ry))
            pygame.draw.ellipse(bg, (60, 140, 200), (x - rx + 18, y - ry + 14, 2 * rx - 36, 2 * ry - 28))
            for _ in range(8):
                wx = x + rnd.randint(-rx // 2, rx // 2)
                wy = y + rnd.randint(-ry // 2, ry // 2)
                pygame.draw.arc(bg, (150, 200, 235), (wx, wy, 30, 10), 0.3, 2.8, 2)
        layers = (
            (ROAD_WIDTH + 26, (128, 112, 78)),
            (ROAD_WIDTH + 18, (160, 142, 100)),
            (ROAD_WIDTH + 6, (235, 235, 230)),
            (ROAD_WIDTH, (78, 80, 88)),
            (ROAD_WIDTH - 30, (84, 86, 94)),
        )
        for width, color in layers:
            for path in self.paths:
                for x, y in path:
                    pygame.draw.circle(bg, color, (round(x), round(y)), width // 2)
        for path in self.paths:
            for x, y in path[::2]:
                ox, oy = rnd.uniform(-38, 38), rnd.uniform(-38, 38)
                if ox * ox + oy * oy < 38 * 38:
                    c = rnd.choice([(70, 72, 80), (92, 94, 102)])
                    bg.set_at((int(x + ox), int(y + oy)), c)
        for path in self.paths:
            walked = 0.0
            for (ax, ay), (bx, by) in zip(path, path[1:]):
                if walked % 50 < 28:
                    pygame.draw.line(bg, (240, 215, 90), (ax, ay), (bx, by), 5)
                walked += ROAD_STEP
        return bg

    def road_distance(self, x, y):
        gx, gy = int(x // GRID), int(y // GRID)
        best = 10 ** 9
        for radius in range(5):
            for i in range(gx - radius, gx + radius + 1):
                for j in range(gy - radius, gy + radius + 1):
                    if max(abs(i - gx), abs(j - gy)) != radius:
                        continue
                    for px, py in self.road_grid.get((i, j), ()):
                        d = (px - x) ** 2 + (py - y) ** 2
                        if d < best:
                            best = d
            if best < (radius * GRID) ** 2:
                break
        return math.sqrt(best)

    def on_road(self, x, y):
        return self.road_distance(x, y) < ROAD_WIDTH / 2 + 4

    def in_lake(self, x, y, r=0):
        for lx, ly, rx, ry in self.lakes:
            nx = (x - lx) / (rx + r)
            ny = (y - ly) / (ry + r)
            if nx * nx + ny * ny < 1:
                return True
        return False

    def blocked(self, x, y, r):
        if x < r or y < r or x > WORLD_W - r or y > WORLD_H - r:
            return True
        if self.in_lake(x, y, r - 10):
            return True
        for tx, ty, tr, _ in self.trees:
            if abs(tx - x) < 60 and abs(ty - y) < 60 and dist(x, y, tx, ty) < r + tr * 0.32:
                return True
        return False

    def tree_sprite(self, r, variant):
        key = (r, variant)
        if key in self.tree_cache:
            return self.tree_cache[key]
        size = r * 2 + 20
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        palettes = [
            [(30, 90, 40), (44, 116, 52), (66, 146, 66)],
            [(26, 80, 52), (36, 104, 66), (56, 132, 84)],
            [(52, 96, 34), (72, 124, 44), (100, 156, 60)],
        ]
        dark, mid, light = palettes[variant]
        pygame.draw.circle(s, (0, 0, 0, 60), (c + 8, c + 10), r)
        pygame.draw.circle(s, dark, (c, c), r)
        rnd = random.Random(r * 10 + variant)
        for _ in range(6):
            a = rnd.random() * math.tau
            d = r * 0.45
            pygame.draw.circle(s, mid, (int(c + math.cos(a) * d), int(c + math.sin(a) * d)), int(r * 0.55))
        pygame.draw.circle(s, mid, (c, c), int(r * 0.7))
        pygame.draw.circle(s, light, (c - r // 4, c - r // 4), int(r * 0.4))
        self.tree_cache[key] = s
        return s

    def draw_trees(self, surf, cam_x, cam_y):
        for x, y, r, v in self.trees:
            sx, sy = x - cam_x, y - cam_y
            if -80 < sx < W + 80 and -80 < sy < H + 80:
                spr = self.tree_sprite(r, v)
                surf.blit(spr, (sx - spr.get_width() // 2, sy - spr.get_height() // 2))


def make_car_sprite():
    s = pygame.Surface((70, 38), pygame.SRCALPHA)
    for wx, wy in ((10, 0), (48, 0), (10, 30), (48, 30)):
        pygame.draw.rect(s, (25, 25, 25), (wx, wy, 14, 8), border_radius=3)
    pygame.draw.rect(s, (205, 40, 45), (2, 4, 66, 30), border_radius=10)
    pygame.draw.rect(s, (160, 25, 30), (2, 4, 66, 30), 2, border_radius=10)
    pygame.draw.rect(s, (120, 180, 220), (40, 8, 12, 22), border_radius=4)
    pygame.draw.rect(s, (100, 150, 190), (14, 9, 9, 20), border_radius=3)
    pygame.draw.rect(s, (225, 70, 70), (24, 8, 15, 22), border_radius=3)
    pygame.draw.circle(s, (255, 250, 200), (66, 9), 3)
    pygame.draw.circle(s, (255, 250, 200), (66, 29), 3)
    pygame.draw.rect(s, (255, 80, 60), (2, 7, 3, 5))
    pygame.draw.rect(s, (255, 80, 60), (2, 26, 3, 5))
    return s


CAR_SPRITE = make_car_sprite()


class Car:
    RADIUS = 17

    def __init__(self, x, y, angle):
        self.x, self.y = x, y
        self.angle = angle
        self.speed = 0.0

    def circles(self, x=None, y=None, angle=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        a = self.angle if angle is None else angle
        dx, dy = math.cos(a) * 16, math.sin(a) * 16
        return [(x + dx, y + dy), (x - dx, y - dy)]

    def collides(self, world, x, y, angle):
        return any(world.blocked(cx, cy, self.RADIUS) for cx, cy in self.circles(x, y, angle))

    def update(self, keys, world):
        up = keys[pygame.K_w] or keys[pygame.K_UP]
        down = keys[pygame.K_s] or keys[pygame.K_DOWN]
        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]

        max_speed = 9.0 if world.on_road(self.x, self.y) else 4.5
        if up:
            self.speed += 0.22
        elif down:
            self.speed -= 0.3 if self.speed > 0 else 0.15
        else:
            self.speed *= 0.97
        if self.speed > max_speed:
            self.speed = max(max_speed, self.speed - 0.35)
        self.speed = max(-3.5, self.speed)
        if abs(self.speed) < 0.03:
            self.speed = 0

        turn = (right - left)
        if turn and abs(self.speed) > 0.2:
            factor = min(1.0, abs(self.speed) / 3)
            new_angle = self.angle + turn * 0.055 * factor * (1 if self.speed > 0 else -1)
            if not self.collides(world, self.x, self.y, new_angle):
                self.angle = new_angle

        nx = self.x + math.cos(self.angle) * self.speed
        ny = self.y + math.sin(self.angle) * self.speed
        if self.collides(world, nx, ny, self.angle):
            self.speed = -self.speed * 0.3
        else:
            self.x, self.y = nx, ny

    def draw(self, surf, cam_x, cam_y):
        img = pygame.transform.rotate(CAR_SPRITE, -math.degrees(self.angle))
        sx, sy = self.x - cam_x, self.y - cam_y
        shadow = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        shadow.blit(img, (0, 0))
        shadow.fill((0, 0, 0, 70), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(shadow, shadow.get_rect(center=(sx + 5, sy + 6)))
        surf.blit(img, img.get_rect(center=(sx, sy)))


class Player:
    RADIUS = 13

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.facing = 0.0
        self.phase = 0.0
        self.moving = False

    def update(self, keys, world, car):
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        self.moving = bool(dx or dy)
        if not self.moving:
            return
        speed = 5.0 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else 3.0
        length = math.hypot(dx, dy)
        vx, vy = dx / length * speed, dy / length * speed
        self.facing = math.atan2(vy, vx)
        self.phase += speed * 0.08

        def free(x, y):
            if world.blocked(x, y, self.RADIUS):
                return False
            return all(dist(x, y, cx, cy) > self.RADIUS + car.RADIUS for cx, cy in car.circles())

        if free(self.x + vx, self.y):
            self.x += vx
        if free(self.x, self.y + vy):
            self.y += vy

    def draw(self, surf, cam_x, cam_y):
        sx, sy = self.x - cam_x, self.y - cam_y
        fx, fy = math.cos(self.facing), math.sin(self.facing)
        px, py = -fy, fx
        pygame.draw.ellipse(surf, (0, 0, 0, 70), (sx - 14, sy - 6, 30, 22))
        swing = math.sin(self.phase) * 8 if self.moving else 0
        for side, s in ((1, swing), (-1, -swing)):
            lx = sx + px * 6 * side + fx * s
            ly = sy + py * 6 * side + fy * s
            pygame.draw.circle(surf, (50, 40, 90), (int(lx), int(ly)), 5)
        for side, s in ((1, -swing), (-1, swing)):
            ax = sx + px * 13 * side + fx * s * 0.6
            ay = sy + py * 13 * side + fy * s * 0.6
            pygame.draw.circle(surf, (240, 200, 160), (int(ax), int(ay)), 4)
        pygame.draw.circle(surf, (230, 90, 150), (int(sx), int(sy)), 12)
        pygame.draw.circle(surf, (190, 60, 120), (int(sx), int(sy)), 12, 2)
        hx, hy = sx + fx * 2, sy + fy * 2
        pygame.draw.circle(surf, (110, 70, 40), (int(hx - fx * 2), int(hy - fy * 2)), 9)
        pygame.draw.circle(surf, (240, 200, 160), (int(hx + fx * 2), int(hy + fy * 2)), 6)


def draw_coin(surf, x, y, t, phase):
    w = max(2, int(abs(math.cos(t * 3 + phase)) * 22))
    bob = math.sin(t * 4 + phase) * 3
    rect = pygame.Rect(0, 0, w, 22)
    rect.center = (int(x), int(y + bob))
    pygame.draw.ellipse(surf, (0, 0, 0, 60), (x - 9, y + 10, 18, 6))
    pygame.draw.ellipse(surf, (200, 140, 20), rect)
    inner = rect.inflate(-max(0, w * 0.35), -7)
    pygame.draw.ellipse(surf, (255, 210, 50), inner)
    if w > 8:
        pygame.draw.line(surf, (255, 245, 180), (rect.centerx - w // 6, rect.top + 5), (rect.centerx - w // 6, rect.bottom - 7), 2)


class FloatText:
    def __init__(self, x, y, text, color):
        self.x, self.y = x, y
        self.img = FONT.render(text, True, color)
        self.life = 50

    def update(self):
        self.y -= 1.2
        self.life -= 1

    def draw(self, surf, cam_x, cam_y):
        img = self.img.copy()
        img.set_alpha(int(255 * self.life / 50))
        surf.blit(img, (self.x - cam_x - img.get_width() / 2, self.y - cam_y))


class Sparkle:
    def __init__(self, x, y):
        a = random.random() * math.tau
        sp = random.uniform(1, 4)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        self.life = random.randint(18, 32)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.92
        self.vy *= 0.92
        self.life -= 1

    def draw(self, surf, cam_x, cam_y):
        pygame.draw.circle(surf, (255, 230, 90), (int(self.x - cam_x), int(self.y - cam_y)), max(1, self.life // 8))


class Game:
    def __init__(self):
        self.world = World()
        self.reset()

    def reset(self):
        world = self.world
        sx, sy = world.spawn
        (ax, ay), (bx, by) = world.paths[0][0], world.paths[0][5]
        road_angle = math.atan2(by - ay, bx - ax)
        self.car = Car(sx + math.cos(road_angle) * 90, sy + math.sin(road_angle) * 90, road_angle)
        self.player = Player(sx - math.sin(road_angle) * 70, sy + math.cos(road_angle) * 70)
        self.in_car = False
        self.coins = self._make_coins()
        self.total = len(self.coins)
        self.collected = 0
        self.effects = []
        self.time = 0.0
        self.finish_time = None

    def _make_coins(self):
        world = self.world
        coins = []
        rnd = random.Random()
        step = 8
        while len(coins) < COIN_COUNT // 2:
            path = rnd.choice(world.paths)
            start = rnd.randrange(0, len(path) - 5 * step)
            lane = rnd.choice([-20, 0, 20])
            chain = []
            for k in range(5):
                i = start + k * step
                (ax, ay), (bx, by) = path[i], path[i + 1]
                seg = dist(ax, ay, bx, by) or 1
                nx, ny = -(by - ay) / seg, (bx - ax) / seg
                chain.append((ax + nx * lane, ay + ny * lane, rnd.random() * 6))
            if all(dist(x, y, cx, cy) > 70 for x, y, _ in chain for cx, cy, _ in coins):
                coins.extend(chain[:COIN_COUNT // 2 - len(coins)])
        while len(coins) < COIN_COUNT:
            x, y = rnd.randint(60, WORLD_W - 60), rnd.randint(60, WORLD_H - 60)
            if world.blocked(x, y, 22) or world.on_road(x, y):
                continue
            if all(dist(x, y, cx, cy) > 100 for cx, cy, _ in coins):
                coins.append((x, y, rnd.random() * 6))
        return coins

    def toggle_car(self):
        p, c = self.player, self.car
        if not self.in_car:
            if dist(p.x, p.y, c.x, c.y) < 65:
                self.in_car = True
        elif abs(c.speed) < 1.5:
            for side in (1, -1):
                ex = c.x - math.sin(c.angle) * 42 * side
                ey = c.y + math.cos(c.angle) * 42 * side
                if not self.world.blocked(ex, ey, Player.RADIUS):
                    p.x, p.y = ex, ey
                    c.speed = 0
                    self.in_car = False
                    return

    def focus(self):
        return (self.car.x, self.car.y) if self.in_car else (self.player.x, self.player.y)

    def update(self, dt):
        keys = pygame.key.get_pressed()
        if self.finish_time is None:
            self.time += dt
        if self.in_car:
            self.car.update(keys, self.world)
        else:
            self.player.update(keys, self.world, self.car)
            if abs(self.car.speed) > 0:
                self.car.speed *= 0.9

        fx, fy = self.focus()
        pick = 42 if self.in_car else 28
        left = []
        for coin in self.coins:
            if dist(fx, fy, coin[0], coin[1]) < pick:
                self.collected += 1
                self.effects.append(FloatText(coin[0], coin[1] - 20, "+1", (255, 230, 80)))
                self.effects.extend(Sparkle(coin[0], coin[1]) for _ in range(12))
            else:
                left.append(coin)
        self.coins = left
        if not self.coins and self.finish_time is None:
            self.finish_time = self.time

        for e in self.effects:
            e.update()
        self.effects = [e for e in self.effects if e.life > 0]

    def draw(self, t):
        fx, fy = self.focus()
        cam_x = int(max(0, min(WORLD_W - W, fx - W / 2)))
        cam_y = int(max(0, min(WORLD_H - H, fy - H / 2)))

        screen.blit(self.world.background, (0, 0), pygame.Rect(cam_x, cam_y, W, H))
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        for x, y, ph in self.coins:
            if -30 < x - cam_x < W + 30 and -30 < y - cam_y < H + 30:
                draw_coin(layer, x - cam_x, y - cam_y, t, ph)
        if not self.in_car:
            self.player.draw(layer, cam_x, cam_y)
        screen.blit(layer, (0, 0))
        self.car.draw(screen, cam_x, cam_y)
        self.world.draw_trees(screen, cam_x, cam_y)
        for e in self.effects:
            e.draw(screen, cam_x, cam_y)
        self.draw_hud()

    def draw_hud(self):
        panel = pygame.Surface((300, 92), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 120))
        screen.blit(panel, (12, 12))
        draw_coin(screen, 38, 38, 0, 0)
        screen.blit(FONT.render(f"Монеты: {self.collected} / {self.total}", True, (255, 240, 170)), (58, 24))
        mode = "В машине" if self.in_car else "Пешком"
        screen.blit(FONT_SMALL.render(f"{mode}   ·   Время: {int(self.time)} c", True, (230, 230, 230)), (24, 64))

        hint = None
        if self.in_car:
            hint = "E — выйти из машины (остановитесь)" if abs(self.car.speed) >= 1.5 else "E — выйти из машины"
        elif dist(self.player.x, self.player.y, self.car.x, self.car.y) < 65:
            hint = "E — сесть в машину"
        if hint:
            img = FONT.render(hint, True, (255, 255, 255))
            bg = pygame.Surface((img.get_width() + 24, img.get_height() + 12), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            r = bg.get_rect(midbottom=(W // 2, H - 20))
            screen.blit(bg, r)
            screen.blit(img, img.get_rect(center=r.center))

        mm = self.world.minimap.copy()
        k = 180 / WORLD_W
        for x, y, _ in self.coins:
            pygame.draw.circle(mm, (255, 215, 0), (int(x * k), int(y * k)), 2)
        pygame.draw.circle(mm, (230, 40, 40), (int(self.car.x * k), int(self.car.y * k)), 4)
        if not self.in_car:
            pygame.draw.circle(mm, (255, 255, 255), (int(self.player.x * k), int(self.player.y * k)), 4)
        mx, my = W - 196, H - 196
        pygame.draw.rect(screen, (20, 20, 20), (mx - 4, my - 4, 188, 188), border_radius=6)
        screen.blit(mm, (mx, my))

        if self.finish_time is not None:
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            screen.blit(shade, (0, 0))
            t1 = FONT_BIG.render("Победа!", True, (255, 220, 60))
            t2 = FONT.render(f"Все {self.total} монет собраны за {int(self.finish_time)} секунд", True, (255, 255, 255))
            t3 = FONT_SMALL.render("Нажмите R, чтобы сыграть ещё раз", True, (220, 220, 220))
            screen.blit(t1, t1.get_rect(center=(W // 2, H // 2 - 50)))
            screen.blit(t2, t2.get_rect(center=(W // 2, H // 2 + 10)))
            screen.blit(t3, t3.get_rect(center=(W // 2, H // 2 + 50)))


def main():
    game = Game()
    t = 0.0
    while True:
        dt = clock.tick(FPS) / 1000
        t += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_e:
                    game.toggle_car()
                if event.key == pygame.K_r:
                    game.reset()
        game.update(dt)
        game.draw(t)
        pygame.display.flip()


if __name__ == "__main__":
    main()
