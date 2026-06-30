import math
import random

SIZE = 300.0
ROAD_W = 8.0
ROAD_STEP = 0.6
CELL = 10.0
COIN_COUNT = 400
WATER_Y = -0.45


def dist(ax, az, bx, bz):
    return math.hypot(ax - bx, az - bz)


def resample(points, step=ROAD_STEP):
    out = [points[0]]
    carry = 0.0
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        seg = dist(ax, az, bx, bz)
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append((ax + (bx - ax) * t, az + (bz - az) * t))
            d += step
        carry = seg - (d - step)
    return out


class World:
    def __init__(self, seed=7):
        rnd = random.Random(seed)
        self._make_roads()
        self.lakes = self._make_lakes(rnd)
        self.spawn = self.paths[0][0]
        sx, sz = self.spawn
        self.garage = {'x': sx + 21, 'z': sz, 'hx': 5.0, 'hz': 5.5}
        self.garage_door = (sx + 21 - 5.0, sz)
        self.garage_pad = (sx + 11, sz)
        self.obstacles = {}
        self.trees = self._make_trees(rnd)
        self.rocks = self._make_rocks(rnd)
        self.bushes, self.tufts, self.flowers = self._make_decor(rnd)

    def _make_roads(self):
        c = SIZE / 2
        n = 2000
        loop, cross, north = [], [], []
        for i in range(n + 1):
            t = i / n
            a = t * math.tau
            r = 105 + 14 * math.sin(3 * a) + 5.5 * math.cos(2 * a + 1)
            loop.append((c + math.cos(a) * r, c + math.sin(a) * r))
            cross.append((40 + t * (SIZE - 80), c + 22 * math.sin(t * math.tau)))
            north.append((c + 18 * math.sin(t * math.pi * 1.5), c + t * 122))
        self.paths = [resample(p) for p in (loop, cross, north)]

        self.road_grid = {}
        for path in self.paths:
            for x, z in path:
                self.road_grid.setdefault((int(x // CELL), int(z // CELL)), []).append((x, z))

    def _make_lakes(self, rnd):
        lakes = []
        for _ in range(600):
            if len(lakes) >= 6:
                break
            rx, rz = rnd.uniform(11, 22), rnd.uniform(8, 17)
            x = rnd.uniform(rx + 8, SIZE - rx - 8)
            z = rnd.uniform(rz + 8, SIZE - rz - 8)
            if self.road_distance(x, z) < max(rx, rz) * 1.6 + 6:
                continue
            if any(dist(x, z, lx, lz) < max(rx, rz) + max(lrx, lrz) + 10 for lx, lz, lrx, lrz in lakes):
                continue
            lakes.append((x, z, rx, rz))
        return lakes

    def _add_obstacle(self, x, z, r):
        self.obstacles.setdefault((int(x // CELL), int(z // CELL)), []).append((x, z, r))

    def _free_spot(self, x, z, road_gap, lake_pad, near):
        if self.road_distance(x, z) < ROAD_W / 2 + road_gap:
            return False
        if self.in_lake(x, z, lake_pad):
            return False
        return not any(dist(x, z, ox, oz) < near + orad for ox, oz, orad in self._nearby_obstacles(x, z))

    def _make_trees(self, rnd):
        trees = []
        sx, sz = self.spawn
        for _ in range(6000):
            if len(trees) >= 560:
                break
            s = rnd.uniform(0.8, 1.4)
            x, z = rnd.uniform(3, SIZE - 3), rnd.uniform(3, SIZE - 3)
            if dist(x, z, sx, sz) < 18 or self.near_garage(x, z, 22):
                continue
            if not self._free_spot(x, z, 2.5 * s, 2.5, 3.0 * s):
                continue
            kind = 0 if rnd.random() < 0.55 else 1
            trees.append((x, z, s, kind, rnd.randint(0, 2), rnd.uniform(0, 360)))
            self._add_obstacle(x, z, 0.4 * s)
        return trees

    def _make_rocks(self, rnd):
        rocks = []
        for _ in range(1500):
            if len(rocks) >= 70:
                break
            r = rnd.uniform(0.5, 1.6)
            x, z = rnd.uniform(5, SIZE - 5), rnd.uniform(5, SIZE - 5)
            if not self._free_spot(x, z, 2 + r, 1 + r, 1.5 + r) or self.near_garage(x, z, 20):
                continue
            rocks.append((x, z, r, rnd.randint(0, 9999)))
            self._add_obstacle(x, z, r * 0.85)
        return rocks

    def _make_decor(self, rnd):
        bushes, tufts, flowers = [], [], []
        while len(bushes) < 260:
            x, z = rnd.uniform(2, SIZE - 2), rnd.uniform(2, SIZE - 2)
            if self._free_spot(x, z, 1.5, 1.5, 1.2) and not self.near_garage(x, z, 16):
                bushes.append((x, z, rnd.uniform(0.5, 1.0), rnd.randint(0, 9999)))
        while len(tufts) < 2600:
            x, z = rnd.uniform(1, SIZE - 1), rnd.uniform(1, SIZE - 1)
            if self.road_distance(x, z) > ROAD_W / 2 + 1.4 and not self.in_lake(x, z, 0.5) \
                    and not self.near_garage(x, z, 11):
                tufts.append((x, z, rnd.uniform(0.6, 1.2), rnd.uniform(0, math.tau)))
        while len(flowers) < 700:
            x, z = rnd.uniform(1, SIZE - 1), rnd.uniform(1, SIZE - 1)
            if self.road_distance(x, z) > ROAD_W / 2 + 1.4 and not self.in_lake(x, z, 1.0) \
                    and not self.near_garage(x, z, 11):
                flowers.append((x, z, rnd.randint(0, 3)))
        return bushes, tufts, flowers

    def make_coins(self, seed):
        rnd = random.Random(seed)
        coins = []
        on_roads = COIN_COUNT * 2 // 5
        step = 7
        for _ in range(4000):
            if len(coins) >= on_roads:
                break
            path = rnd.choice(self.paths)
            start = rnd.randrange(0, len(path) - 5 * step - 1)
            lane = rnd.choice([-1.8, 0.0, 1.8])
            chain = []
            for k in range(5):
                i = start + k * step
                (ax, az), (bx, bz) = path[i], path[i + 1]
                seg = dist(ax, az, bx, bz) or 1
                nx, nz = -(bz - az) / seg, (bx - ax) / seg
                chain.append((ax + nx * lane, az + nz * lane))
            if all(dist(x, z, cx, cz) > 5 for x, z in chain for cx, cz in coins):
                coins.extend(chain[:on_roads - len(coins)])
        gap, tries = 7.0, 0
        while len(coins) < COIN_COUNT:
            tries += 1
            if tries % 3000 == 0:
                gap *= 0.85
            x, z = rnd.uniform(6, SIZE - 6), rnd.uniform(6, SIZE - 6)
            if self.blocked(x, z, 1.0) or self.on_road(x, z):
                continue
            if all(dist(x, z, cx, cz) > gap for cx, cz in coins):
                coins.append((x, z))
        return [(x, self.ground_height(x, z) + 1.2, z) for x, z in coins]

    def road_distance(self, x, z):
        gx, gz = int(x // CELL), int(z // CELL)
        best = 10 ** 9
        for radius in range(5):
            for i in range(gx - radius, gx + radius + 1):
                for j in range(gz - radius, gz + radius + 1):
                    if max(abs(i - gx), abs(j - gz)) != radius:
                        continue
                    for px, pz in self.road_grid.get((i, j), ()):
                        d = (px - x) ** 2 + (pz - z) ** 2
                        if d < best:
                            best = d
            if best < (radius * CELL) ** 2:
                break
        return math.sqrt(best)

    def near_garage(self, x, z, radius):
        g = self.garage
        return dist(x, z, g['x'] - 5, g['z']) < radius

    def on_road(self, x, z):
        return self.road_distance(x, z) < ROAD_W / 2 + 0.4

    def lake_k(self, x, z):
        best = 99.0
        for lx, lz, rx, rz in self.lakes:
            k = math.sqrt(((x - lx) / rx) ** 2 + ((z - lz) / rz) ** 2)
            best = min(best, k)
        return best

    def in_lake(self, x, z, pad=0.0):
        for lx, lz, rx, rz in self.lakes:
            nx = (x - lx) / max(1.0, rx + pad)
            nz = (z - lz) / max(1.0, rz + pad)
            if nx * nx + nz * nz < 1:
                return True
        return False

    def ground_height(self, x, z):
        blend = min(1.0, max(0.0, (self.road_distance(x, z) - 6) / 14))
        noise = (math.sin(x * 0.045) * math.cos(z * 0.038) * 1.4
                 + math.sin(x * 0.11 + z * 0.07) * 0.5
                 + math.cos(z * 0.13 - x * 0.05) * 0.35)
        h = (1.0 + 0.6 * noise) * blend
        for lx, lz, rx, rz in self.lakes:
            k = math.sqrt(((x - lx) / rx) ** 2 + ((z - lz) / rz) ** 2)
            if k < 1:
                bowl = WATER_Y + 0.1 - (1 - k) * 3.0
            else:
                bowl = WATER_Y + 0.1 + (k - 1) * 1.2
            h = min(h, bowl)
        return h

    def _nearby_obstacles(self, x, z):
        gx, gz = int(x // CELL), int(z // CELL)
        for i in (gx - 1, gx, gx + 1):
            for j in (gz - 1, gz, gz + 1):
                yield from self.obstacles.get((i, j), ())

    def blocked(self, x, z, r):
        if x < r + 1 or z < r + 1 or x > SIZE - r - 1 or z > SIZE - r - 1:
            return True
        if self.in_lake(x, z, r - 1.0):
            return True
        g = self.garage
        if abs(x - g['x']) < g['hx'] + r and abs(z - g['z']) < g['hz'] + r:
            return True
        return any(dist(x, z, ox, oz) < r + orad for ox, oz, orad in self._nearby_obstacles(x, z))
