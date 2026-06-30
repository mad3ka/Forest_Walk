import math
import random

from PIL import Image, ImageDraw
from ursina import Color, Entity, Mesh

import world as W

SUN = (0.45, 0.82, 0.35)
_l = math.sqrt(sum(c * c for c in SUN))
SUN = tuple(c / _l for c in SUN)
MAX_VERTS = 60000


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / length, v[1] / length, v[2] / length)


def shade(col, n, ambient=0.58):
    k = ambient + (1 - ambient) * max(0.0, n[0] * SUN[0] + n[1] * SUN[1] + n[2] * SUN[2])
    return Color(col[0] * k, col[1] * k, col[2] * k, 1)


def rgb(r, g, b):
    return (r / 255, g / 255, b / 255)


class MeshBuilder:
    def __init__(self):
        self.done = []
        self._reset()

    def _reset(self):
        self.v, self.t, self.c = [], [], []

    def _flush_if_full(self):
        if len(self.v) > MAX_VERTS:
            self.done.append((self.v, self.t, self.c))
            self._reset()

    def face(self, pts, col, center=None, normal=None):
        n = normal or _norm(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])))
        if center is not None and normal is None:
            fc = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
            d = _sub(fc, center)
            if n[0] * d[0] + n[1] * d[1] + n[2] * d[2] < 0:
                n = (-n[0], -n[1], -n[2])
        c = shade(col, n)
        base = len(self.v)
        self.v.extend(pts)
        self.c.extend([c] * len(pts))
        for i in range(1, len(pts) - 1):
            self.t.extend((base, base + i, base + i + 1))
        self._flush_if_full()

    def smooth_face(self, pts, cols):
        base = len(self.v)
        self.v.extend(pts)
        self.c.extend(cols)
        for i in range(1, len(pts) - 1):
            self.t.extend((base, base + i, base + i + 1))
        self._flush_if_full()

    def box(self, cx, cy, cz, sx, sy, sz, col, yaw=0.0):
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        ca, sa = math.cos(yaw), math.sin(yaw)

        def p(x, y, z):
            return (cx + x * ca + z * sa, cy + y, cz - x * sa + z * ca)

        corners = [p(x, y, z) for x in (-hx, hx) for y in (-hy, hy) for z in (-hz, hz)]
        center = (cx, cy, cz)
        for idx in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
            self.face([corners[i] for i in idx], col, center)

    def cylinder(self, x, y, z, r_bottom, r_top, height, col, segs=8, cap_col=None, axis='y'):
        def p(a, h, r):
            u, w = math.cos(a) * r, math.sin(a) * r
            if axis == 'y':
                return (x + u, y + h, z + w)
            if axis == 'z':
                return (x + u, y + w, z + h - height / 2)
            return (x + h - height / 2, y + u, z + w)

        center = p(0, height / 2, 0)
        for i in range(segs):
            a0, a1 = i / segs * math.tau, (i + 1) / segs * math.tau
            quad = [p(a0, 0, r_bottom), p(a1, 0, r_bottom), p(a1, height, r_top), p(a0, height, r_top)]
            if r_top == 0:
                quad = quad[:3]
            self.face(quad, col, center)
        cap = cap_col or col
        self.face([p(i / segs * math.tau, 0, r_bottom) for i in range(segs)], cap, center)
        if r_top > 0:
            self.face([p(i / segs * math.tau, height, r_top) for i in range(segs)], cap, center)

    def blob(self, x, y, z, rx, ry, rz, col, seed, jitter=0.18):
        rnd = random.Random(seed)
        verts = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        tris = [(0, 2, 4), (4, 2, 1), (1, 2, 5), (5, 2, 0), (0, 4, 3), (4, 1, 3), (1, 5, 3), (5, 0, 3)]
        mids = {}

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in mids:
                va, vb = verts[a], verts[b]
                verts.append(_norm(((va[0] + vb[0]) / 2, (va[1] + vb[1]) / 2, (va[2] + vb[2]) / 2)))
                mids[key] = len(verts) - 1
            return mids[key]

        new_tris = []
        for a, b, c in tris:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new_tris += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        pts = []
        for vx, vy, vz in verts:
            k = 1 + rnd.uniform(-jitter, jitter)
            pts.append((x + vx * rx * k, y + vy * ry * k, z + vz * rz * k))
        for a, b, c in new_tris:
            tint = rnd.uniform(0.92, 1.08)
            self.face([pts[a], pts[b], pts[c]], tuple(min(1, ch * tint) for ch in col), (x, y, z))

    def build(self, parent=None, **kwargs):
        chunks = self.done + ([(self.v, self.t, self.c)] if self.v else [])
        root = Entity(parent=parent, **kwargs) if parent is not None else Entity(**kwargs)
        for v, t, c in chunks:
            e = Entity(parent=root, model=Mesh(vertices=v, triangles=t, colors=c))
            e.double_sided = True
        return root


def build_ground(world):
    n = 150
    step = W.SIZE / n
    heights = [[world.ground_height(i * step, j * step) for i in range(n + 1)] for j in range(n + 1)]
    shadow = [[0.0] * (n + 1) for _ in range(n + 1)]
    for x, z, s, *_ in world.trees:
        sx, sz = x - SUN[0] * 2.5 * s, z - SUN[2] * 2.5 * s
        rad = 3.2 * s
        for j in range(max(0, int((sz - rad) / step)), min(n, int((sz + rad) / step)) + 1):
            for i in range(max(0, int((sx - rad) / step)), min(n, int((sx + rad) / step)) + 1):
                d = math.hypot(i * step - sx, j * step - sz) / rad
                if d < 1:
                    shadow[j][i] = max(shadow[j][i], (1 - d) * 0.45)

    rnd = random.Random(3)
    verts, cols, tris = [], [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, z = i * step, j * step
            h = heights[j][i]
            hl = heights[j][max(0, i - 1)]
            hr = heights[j][min(n, i + 1)]
            hd = heights[max(0, j - 1)][i]
            hu = heights[min(n, j + 1)][i]
            normal = _norm((hl - hr, 2 * step, hd - hu))
            patch = 0.5 + 0.5 * math.sin(x * 0.07 + math.cos(z * 0.05) * 2) * math.cos(z * 0.06)
            g = (0.30 + 0.06 * patch + rnd.uniform(-0.02, 0.02),
                 0.56 + 0.08 * patch + rnd.uniform(-0.03, 0.03),
                 0.22 + 0.04 * patch)
            k = world.lake_k(x, z)
            if k < 1.35:
                t = min(1.0, (1.35 - k) / 0.25)
                sand = (0.80, 0.72, 0.50) if k > 1.0 else (0.55, 0.50, 0.38)
                g = tuple(g[c] * (1 - t) + sand[c] * t for c in range(3))
            dark = 1 - shadow[j][i]
            col = shade(g, normal)
            verts.append((x, h, z))
            cols.append(Color(col[0] * dark, col[1] * dark, col[2] * dark, 1))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b, c, d = a + 1, a + n + 1, a + n + 2
            tris += [a, b, d, a, d, c]
    e = Entity(model=Mesh(vertices=verts, triangles=tris, colors=cols))
    e.double_sided = True
    return e


def build_water(world):
    mb = MeshBuilder()
    for lx, lz, rx, rz in world.lakes:
        segs = 40
        for ring, (k0, k1, col) in enumerate(((1.18, 0.75, rgb(70, 150, 200)), (0.75, 0.0, rgb(45, 115, 175)))):
            for i in range(segs):
                a0, a1 = i / segs * math.tau, (i + 1) / segs * math.tau
                pts = [(lx + math.cos(a0) * rx * k0, W.WATER_Y, lz + math.sin(a0) * rz * k0),
                       (lx + math.cos(a1) * rx * k0, W.WATER_Y, lz + math.sin(a1) * rz * k0),
                       (lx + math.cos(a1) * rx * k1, W.WATER_Y, lz + math.sin(a1) * rz * k1),
                       (lx + math.cos(a0) * rx * k1, W.WATER_Y, lz + math.sin(a0) * rz * k1)]
                if k1 == 0:
                    pts = pts[:3]
                mb.face(pts, col, normal=(0, 1, 0))
    return mb.build()


def build_roads(world):
    mb = MeshBuilder()
    up = (0, 1, 0)
    layers = (
        (W.ROAD_W / 2 + 1.3, 0.02, rgb(150, 132, 95)),
        (W.ROAD_W / 2 + 0.3, 0.04, rgb(235, 235, 228)),
        (W.ROAD_W / 2, 0.06, rgb(78, 80, 88)),
        (W.ROAD_W / 2 - 1.6, 0.065, rgb(86, 88, 96)),
    )
    for path in world.paths:
        normals = []
        for i in range(len(path)):
            (ax, az), (bx, bz) = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
            length = math.hypot(bx - ax, bz - az) or 1
            normals.append((-(bz - az) / length, (bx - ax) / length))
        ys = [world.ground_height(x, z) for x, z in path]
        for half, lift, col in layers:
            for i in range(len(path) - 1):
                (x0, z0), (x1, z1) = path[i], path[i + 1]
                (n0x, n0z), (n1x, n1z) = normals[i], normals[i + 1]
                y0, y1 = ys[i] + lift, ys[i + 1] + lift
                mb.face([(x0 - n0x * half, y0, z0 - n0z * half), (x0 + n0x * half, y0, z0 + n0z * half),
                         (x1 + n1x * half, y1, z1 + n1z * half), (x1 - n1x * half, y1, z1 - n1z * half)],
                        col, normal=up)
        walked = 0.0
        for i in range(len(path) - 1):
            if walked % 5.0 < 3.0:
                (x0, z0), (x1, z1) = path[i], path[i + 1]
                (n0x, n0z), (n1x, n1z) = normals[i], normals[i + 1]
                y0, y1 = ys[i] + 0.08, ys[i + 1] + 0.08
                w = 0.1
                mb.face([(x0 - n0x * w, y0, z0 - n0z * w), (x0 + n0x * w, y0, z0 + n0z * w),
                         (x1 + n1x * w, y1, z1 + n1z * w), (x1 - n1x * w, y1, z1 - n1z * w)],
                        rgb(240, 210, 80), normal=up)
            walked += W.ROAD_STEP
    return mb.build()


TREE_GREENS = [
    [rgb(34, 92, 48), rgb(44, 110, 56), rgb(56, 128, 64)],
    [rgb(58, 128, 52), rgb(80, 150, 60), rgb(110, 165, 64)],
]


def build_trees(world):
    mb = MeshBuilder()
    bark = rgb(105, 72, 45)
    for x, z, s, kind, variant, _ in world.trees:
        y = world.ground_height(x, z) - 0.2
        green = TREE_GREENS[kind][variant]
        if kind == 0:
            mb.cylinder(x, y, z, 0.28 * s, 0.2 * s, 1.8 * s, bark, segs=6)
            for k, (base, r, h) in enumerate(((1.0, 2.1, 2.6), (2.3, 1.65, 2.3), (3.5, 1.15, 2.0))):
                tier = tuple(min(1, c * (1 + 0.06 * k)) for c in green)
                mb.cylinder(x, y + base * s, z, r * s, 0, h * s, tier, segs=8)
        else:
            mb.cylinder(x, y, z, 0.32 * s, 0.24 * s, 2.8 * s, bark, segs=6)
            seed = int(x * 31 + z * 17)
            mb.blob(x, y + 3.6 * s, z, 2.0 * s, 1.6 * s, 2.0 * s, green, seed)
            mb.blob(x + 0.9 * s, y + 4.4 * s, z - 0.5 * s, 1.3 * s, 1.1 * s, 1.3 * s,
                    tuple(min(1, c * 1.1) for c in green), seed + 1)
            mb.blob(x - 0.8 * s, y + 4.1 * s, z + 0.7 * s, 1.2 * s, 1.0 * s, 1.2 * s, green, seed + 2)
    return mb.build()


def build_decor(world):
    mb = MeshBuilder()
    for x, z, r, seed in world.rocks:
        y = world.ground_height(x, z)
        mb.blob(x, y + r * 0.25, z, r, r * 0.7, r * 0.9, rgb(128, 126, 122), seed, jitter=0.3)
    for x, z, r, seed in world.bushes:
        y = world.ground_height(x, z)
        mb.blob(x, y + r * 0.45, z, r * 1.2, r * 0.8, r * 1.2, rgb(52, 120, 50), seed, jitter=0.25)
    grass = [rgb(70, 140, 55), rgb(90, 160, 62), rgb(60, 125, 48)]
    for idx, (x, z, s, a) in enumerate(world.tufts):
        y = world.ground_height(x, z)
        col = grass[idx % 3]
        for k in range(3):
            ang = a + k * 2.1
            dx, dz = math.cos(ang) * 0.12 * s, math.sin(ang) * 0.12 * s
            tip = (x + math.cos(ang) * 0.18 * s, y + 0.55 * s, z + math.sin(ang) * 0.18 * s)
            mb.face([(x - dz, y, z + dx), (x + dz, y, z - dx), tip], col, normal=(0, 1, 0))
    petals = [rgb(250, 250, 250), rgb(250, 215, 60), rgb(230, 90, 125), rgb(165, 120, 235)]
    for x, z, kind in world.flowers:
        y = world.ground_height(x, z)
        mb.box(x, y + 0.12, z, 0.03, 0.24, 0.03, rgb(60, 130, 50))
        mb.box(x, y + 0.26, z, 0.16, 0.06, 0.16, petals[kind])
    return mb.build()


def build_outskirts(world):
    mb = MeshBuilder()
    far, edge = 900.0, W.SIZE
    grass = rgb(72, 138, 58)
    for x0, z0, x1, z1 in ((-far, -far, edge + far, 0), (-far, edge, edge + far, edge + far),
                           (-far, 0, 0, edge), (edge, 0, edge + far, edge)):
        mb.face([(x0, -0.05, z0), (x1, -0.05, z0), (x1, -0.05, z1), (x0, -0.05, z1)], grass, normal=(0, 1, 0))
    rnd = random.Random(5)
    for _ in range(900):
        side = rnd.randrange(4)
        a, d = rnd.uniform(-30, edge + 30), rnd.uniform(1.5, 45)
        x, z = [(a, -d), (a, edge + d), (-d, a), (edge + d, a)][side]
        s = rnd.uniform(0.9, 1.6)
        green = TREE_GREENS[0][rnd.randrange(3)]
        mb.cylinder(x, -0.2, z, 0.3 * s, 0.2 * s, 1.8 * s, rgb(105, 72, 45), segs=5)
        mb.cylinder(x, 0.9 * s, z, 2.2 * s, 0, 3.0 * s, green, segs=7)
        mb.cylinder(x, 2.4 * s, z, 1.6 * s, 0, 2.6 * s, green, segs=7)
    return mb.build()


def build_garage(world):
    mb = MeshBuilder()
    g = world.garage
    gx, gz, hx, hz = g['x'], g['z'], g['hx'], g['hz']
    y = world.ground_height(gx, gz)
    wall, trim, roof = rgb(225, 215, 195), rgb(120, 85, 60), rgb(160, 55, 45)
    h = 4.2
    mb.box(gx + hx - 0.15, y + h / 2, gz, 0.3, h, hz * 2, wall)
    for sz in (-1, 1):
        mb.box(gx, y + h / 2, gz + sz * (hz - 0.15), hx * 2, h, 0.3, wall)
        mb.box(gx - hx + 0.15, y + h / 2, gz + sz * (hz - 1.1), 0.3, h, 1.9, wall)
    mb.box(gx - hx + 0.15, y + h - 0.45, gz, 0.3, 0.9, hz * 2, wall)
    mb.box(gx - hx + 0.12, y + h - 0.95, gz, 0.36, 0.12, hz * 2 - 3.8, trim)
    mb.box(gx + 0.5, y + 0.02, gz, hx * 2 - 1.2, 0.04, hz * 2 - 0.6, rgb(90, 90, 95))
    mb.box(gx + 1.5, y + 1.4, gz + hz - 1.0, 3.5, 2.8, 0.8, rgb(70, 75, 90))
    for k in range(4):
        mb.box(gx + 0.2 + k * 0.9, y + 0.5, gz - hz + 1.0, 0.7, 1.0, 0.7, rgb(200, 60, 40) if k % 2 else rgb(60, 90, 160))
    for sz in (-1, 1):
        a0, a1 = (gx - hx - 0.6, y + h, gz + sz * (hz + 0.6)), (gx + hx + 0.6, y + h, gz + sz * (hz + 0.6))
        b0, b1 = (gx - hx - 0.6, y + h + 1.6, gz), (gx + hx + 0.6, y + h + 1.6, gz)
        mb.face([a0, a1, b1, b0], roof, center=(gx, y + h - 2, gz))
    for sx in (-1, 1):
        x = gx + sx * hx
        mb.face([(x, y + h, gz - hz), (x, y + h, gz + hz), (x, y + h + 1.6, gz)], wall, normal=(sx, 0, 0))
    px, pz = world.garage_pad
    py = world.ground_height(px, pz)
    mb.box(px + 1, py + 0.03, pz, 9, 0.06, 14, rgb(170, 170, 168))
    for sz in (-1, 1):
        mb.box(px + 1, py + 0.07, pz + sz * 6.8, 9, 0.02, 0.2, rgb(240, 200, 40))
    mb.box(px - 3.4, py + 0.07, pz, 0.2, 0.02, 13.6, rgb(240, 200, 40))
    for sz in (-1, 1):
        mb.box(gx - hx - 0.25, y + 3.2, gz + sz * 2.4, 0.3, 0.3, 0.3, rgb(255, 240, 180))
    return mb.build()


def build_clouds():
    mb = MeshBuilder()
    rnd = random.Random(11)
    for _ in range(18):
        cx, cy, cz = rnd.uniform(-60, W.SIZE + 60), rnd.uniform(65, 85), rnd.uniform(-60, W.SIZE + 60)
        for _ in range(rnd.randint(3, 6)):
            mb.box(cx + rnd.uniform(-12, 12), cy + rnd.uniform(-1.5, 1.5), cz + rnd.uniform(-7, 7),
                   rnd.uniform(8, 18), rnd.uniform(2.5, 4.5), rnd.uniform(6, 12), (1, 1, 1))
    return mb.build()


def coin_mesh():
    mb = MeshBuilder()
    mb.cylinder(0, 0, 0, 0.57, 0.57, 0.1, rgb(215, 150, 25), segs=24, cap_col=rgb(255, 205, 50), axis='x')
    mb.cylinder(0, 0, 0, 0.36, 0.36, 0.14, rgb(240, 180, 40), segs=24, cap_col=rgb(255, 228, 110), axis='x')
    v, t, c = mb.v, mb.t, mb.c
    m = Mesh(vertices=v, triangles=t, colors=c)
    m.setTwoSided(True)
    return m


def minimap_image(world, size=256):
    img = Image.new('RGB', (size, size), (78, 140, 62))
    d = ImageDraw.Draw(img)
    k = size / W.SIZE

    def px(x, z):
        return (x * k, size - z * k)

    for x, z, s, *_ in world.trees:
        cx, cy = px(x, z)
        d.ellipse((cx - 2.2 * s, cy - 2.2 * s, cx + 2.2 * s, cy + 2.2 * s), fill=(48, 105, 50))
    for lx, lz, rx, rz in world.lakes:
        cx, cy = px(lx, lz)
        d.ellipse((cx - rx * k - 2, cy - rz * k - 2, cx + rx * k + 2, cy + rz * k + 2), fill=(200, 180, 125))
        d.ellipse((cx - rx * k, cy - rz * k, cx + rx * k, cy + rz * k), fill=(50, 125, 190))
    g = world.garage
    gx0, gy0 = px(g['x'] - g['hx'], g['z'] + g['hz'])
    gx1, gy1 = px(g['x'] + g['hx'], g['z'] - g['hz'])
    d.rectangle((gx0 - 1, gy0 - 1, gx1 + 1, gy1 + 1), fill=(240, 200, 40))
    d.rectangle((gx0 + 1, gy0 + 1, gx1 - 1, gy1 - 1), fill=(160, 55, 45))
    for path in world.paths:
        pts = [px(x, z) for x, z in path[::4]]
        d.line(pts, fill=(235, 235, 228), width=int(W.ROAD_W * k) + 3, joint='curve')
        d.line(pts, fill=(90, 92, 100), width=int(W.ROAD_W * k) + 1, joint='curve')
    return img.convert("RGBA")
