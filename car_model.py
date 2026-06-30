import math

from ursina import Color, Entity

from models import SUN, MeshBuilder, _cross, _norm, _sub, rgb

TRIM = rgb(32, 32, 36)
CHROME = rgb(215, 218, 225)
GLASS = (0.14, 0.2, 0.26)
HEADLINER = rgb(150, 146, 140)
HEADLIGHT = rgb(235, 245, 255)
TAILLIGHT = rgb(210, 25, 30)
GRILLE = rgb(18, 18, 22)

PAINTS = [('red', rgb(168, 18, 30)), ('white', rgb(232, 232, 235)), ('black', rgb(24, 24, 28)),
          ('silver', rgb(170, 175, 183)), ('blue', rgb(22, 62, 150)), ('sky', rgb(80, 150, 215)),
          ('green', rgb(28, 110, 62)), ('yellow', rgb(232, 186, 22)), ('orange', rgb(228, 98, 22)),
          ('purple', rgb(98, 40, 140))]
RIMS = [('silver', rgb(200, 204, 210)), ('black', rgb(32, 32, 36)), ('gold', rgb(212, 172, 64))]

HALF = _norm((SUN[0], SUN[1] + 0.8, SUN[2] + 0.4))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def paint(col, n, style='gloss', alpha=1.0):
    if style == 'emit':
        return Color(col[0], col[1], col[2], alpha)
    gloss, power = {'gloss': (0.55, 28), 'glass': (0.8, 40), 'matte': (0.08, 8)}[style]
    k = 0.42 + 0.45 * max(0.0, _dot(n, SUN)) + 0.15 * max(0.0, n[1])
    spec = max(0.0, _dot(n, HALF)) ** power * gloss
    return Color(min(1, col[0] * k + spec), min(1, col[1] * k + spec), min(1, col[2] * k + spec), alpha)


def _interp(keys, z):
    if z <= keys[0][0]:
        return keys[0][1]
    for (z0, v0), (z1, v1) in zip(keys, keys[1:]):
        if z <= z1:
            return v0 + (v1 - v0) * (z - z0) / (z1 - z0)
    return keys[-1][1]


def _smooth(vals, passes=4):
    for _ in range(passes):
        vals = [vals[0]] + [(vals[i - 1] + 2 * vals[i] + vals[i + 1]) / 4
                            for i in range(1, len(vals) - 1)] + [vals[-1]]
    return vals


def _se(c, p):
    return math.copysign(abs(c) ** (2 / p), c)


CABIN_SECTION = [(1.0, 0.0), (0.99, 0.06), (0.965, 0.35), (0.93, 0.62), (0.88, 0.82),
                 (0.80, 0.94), (0.66, 0.99), (0.35, 1.0), (0.0, 1.0)]
BOXY_SECTION = [(1.0, 0.0), (0.995, 0.05), (0.985, 0.4), (0.975, 0.7), (0.96, 0.88),
                (0.93, 0.96), (0.86, 1.0), (0.45, 1.0), (0.0, 1.0)]

SPECS = {
    'sedan': dict(
        color=0, price=0, half=2.47, se=4.0,
        top=[(-2.47, 0.90), (-2.44, 0.97), (-2.3, 1.01), (-1.45, 0.98), (0.95, 0.96), (1.4, 0.95), (1.9, 0.9),
             (2.25, 0.86), (2.4, 0.8), (2.47, 0.70)],
        bottom=[(-2.47, 0.40), (-2.4, 0.32), (2.3, 0.27), (2.47, 0.33)],
        width=[(-2.47, 0.80), (-2.42, 0.88), (-2.25, 0.92), (-1.5, 0.93), (1.5, 0.93), (2.2, 0.91), (2.4, 0.85),
               (2.47, 0.78)],
        open=(-1.40, 0.93),
        headlight=(2.08, 2.42, 0.3, 0.6, 0.5), grille=(2.3, -0.55, 0.3, 0.85), tail=(-2.38, 0.3, 0.62, 0.0),
        clad=-0.35,
        gh=dict(z=(-1.47, 0.97), bw=0.80, section=CABIN_SECTION, ws=0.2, rw=-0.62, side=(-1.02, 0.82),
                bpillar=(-0.24, -0.12), chrome=(-1.0, 0.82),
                roof=[(-1.47, 1.0), (-1.25, 1.13), (-0.9, 1.32), (-0.5, 1.43), (-0.1, 1.445), (0.2, 1.38),
                      (0.6, 1.17), (0.97, 0.98)]),
        wheel_r=0.36, wheel_w=0.24, wheel_x=0.80, arch_r=0.47, axles=[(1.42, True), (-1.42, False)],
        interior=dict(floor=0.36, belt=0.95, dash_z=0.74, seat_z=-0.22, rear_z=-1.1, zback=-1.5, zfront=0.9,
                      door_x=0.84),
        mirror=(0.99, 1.0, 0.78), seams=(0.93, -0.2, -1.25), handles=(0.3, -0.82), extras='sedan',
        phys=dict(max_road=22, max_off=11, accel=9, turn=75, circles=(1.4, -1.4), radius=1.0, reach=2.4,
                  cam=(9, 3.6), exit=2.3, view=7.5)),
    'crossover': dict(
        color=5, price=40, half=2.32, se=4.5,
        top=[(-2.32, 0.95), (-2.27, 1.06), (-2.1, 1.1), (0.85, 1.08), (1.3, 1.04), (1.9, 0.99), (2.2, 0.95),
             (2.32, 0.84)],
        bottom=[(-2.32, 0.52), (-2.22, 0.42), (2.15, 0.40), (2.32, 0.5)],
        width=[(-2.32, 0.84), (-2.2, 0.92), (-1.5, 0.94), (1.5, 0.94), (2.1, 0.92), (2.32, 0.84)],
        open=(-2.0, 0.83),
        headlight=(1.95, 2.28, 0.3, 0.6, 0.55), grille=(2.12, -0.5, 0.32, 0.8), tail=(-2.24, 0.35, 0.7, 0.55),
        clad=-0.15,
        gh=dict(z=(-2.06, 0.86), bw=0.82, section=CABIN_SECTION, ws=0.25, rw=-1.75, side=(-1.78, 0.72),
                bpillar=(-0.42, -0.3), chrome=None,
                roof=[(-2.06, 1.12), (-1.97, 1.5), (-1.7, 1.65), (-0.5, 1.69), (0.15, 1.66), (0.5, 1.45),
                      (0.86, 1.1)]),
        wheel_r=0.40, wheel_w=0.26, wheel_x=0.80, arch_r=0.52, axles=[(1.35, True), (-1.35, False)],
        interior=dict(floor=0.45, belt=1.08, dash_z=0.62, seat_z=-0.35, rear_z=-1.25, zback=-1.75, zfront=0.75,
                      door_x=0.85),
        mirror=(1.0, 1.13, 0.66), seams=(0.8, -0.36, -1.5), handles=(0.15, -0.95), extras='crossover',
        phys=dict(max_road=21, max_off=14, accel=8.5, turn=72, circles=(1.3, -1.3), radius=1.05, reach=2.5,
                  cam=(9.5, 4.0), exit=2.4, view=7.8)),
    'jeep': dict(
        color=6, price=60, half=2.3, se=7.0, smooth=2,
        top=[(-2.3, 1.14), (-2.26, 1.21), (-2.1, 1.23), (0.75, 1.22), (1.2, 1.2), (2.1, 1.17), (2.25, 1.1),
             (2.3, 0.98)],
        bottom=[(-2.3, 0.64), (-2.2, 0.54), (2.2, 0.54), (2.3, 0.64)],
        width=[(-2.3, 0.88), (-2.22, 0.95), (2.2, 0.95), (2.3, 0.88)],
        open=(-2.08, 0.74),
        headlight=None, grille=(2.25, -0.5, 0.45, 0.95), tail=(-2.26, 0.2, 0.75, 0.8), clad=-0.25,
        gh=dict(z=(-2.12, 0.76), bw=0.88, section=BOXY_SECTION, ws=0.4, rw=-1.98, side=(-1.92, 0.66),
                bpillar=(-0.52, -0.4), chrome=None,
                roof=[(-2.12, 1.23), (-2.06, 1.88), (-1.95, 1.97), (0.3, 1.97), (0.5, 1.9), (0.76, 1.23)]),
        wheel_r=0.46, wheel_w=0.32, wheel_x=0.84, arch_r=0.56, axles=[(1.42, True), (-1.38, False)],
        interior=dict(floor=0.64, belt=1.22, dash_z=0.55, seat_z=-0.42, rear_z=-1.32, zback=-1.95, zfront=0.66,
                      door_x=0.9),
        mirror=(1.04, 1.32, 0.6), seams=(0.66, -0.46, -1.9), handles=(0.1, -1.0), extras='jeep',
        phys=dict(max_road=19, max_off=17, accel=8, turn=68, circles=(1.3, -1.3), radius=1.1, reach=2.6,
                  cam=(10, 4.5), exit=2.5, view=8)),
    'pickup': dict(
        color=4, price=80, half=2.7, se=5.5, smooth=3,
        top=[(-2.7, 1.12), (-2.65, 1.19), (0.98, 1.19), (1.4, 1.16), (2.3, 1.11), (2.6, 1.02), (2.7, 0.88)],
        bottom=[(-2.7, 0.64), (-2.6, 0.56), (2.5, 0.52), (2.7, 0.62)],
        width=[(-2.7, 0.92), (-2.62, 0.97), (2.4, 0.97), (2.7, 0.88)],
        open=(-2.6, 0.97),
        headlight=(2.38, 2.68, 0.3, 0.68, 0.6), grille=(2.5, -0.5, 0.42, 0.9), tail=(-2.62, 0.1, 0.85, 0.85),
        clad=-0.3,
        gh=dict(z=(-0.62, 1.0), bw=0.9, section=BOXY_SECTION, ws=0.45, rw=-0.5, side=(-0.5, 0.86),
                bpillar=(0.1, 0.2), chrome=None,
                roof=[(-0.62, 1.2), (-0.56, 1.86), (-0.45, 1.92), (0.35, 1.92), (0.62, 1.76), (1.0, 1.2)]),
        wheel_r=0.44, wheel_w=0.3, wheel_x=0.84, arch_r=0.54, axles=[(1.75, True), (-1.65, False)],
        interior=dict(floor=0.62, belt=1.19, dash_z=0.78, seat_z=0.2, rear_z=None, zback=-0.55, zfront=0.9,
                      door_x=0.9),
        mirror=(1.06, 1.3, 0.86), seams=(0.86, 0.15), handles=(0.55, -0.15), extras='pickup',
        phys=dict(max_road=20, max_off=14, accel=7.5, turn=62, circles=(1.7, -1.7), radius=1.1, reach=2.6,
                  cam=(11, 4.8), exit=2.5, view=9.5)),
    'truck': dict(
        color=8, price=150, custom='truck',
        seat=(-0.6, 2.5, 1.85), steering=((-0.6, 2.25, 2.4), -55),
        hitch=1.3, trailer_axle=10.3,
        phys=dict(max_road=18, max_off=8, accel=4.5, turn=42, circles=(2.0, -1.6), radius=1.35, reach=3.2,
                  cam=(26, 11.0), exit=2.8, view=20)),
}
MODELS = ['sedan', 'crossover', 'jeep', 'pickup', 'truck']


class Profile:
    def __init__(self, spec):
        n = 72
        half = spec['half']
        passes = spec.get('smooth', 4)
        self.spec = spec
        self.se = spec['se']
        self.zs = [-half + i * 2 * half / (n - 1) for i in range(n)]
        self.top = _smooth([_interp(spec['top'], z) for z in self.zs], passes)
        self.w = _smooth([_interp(spec['width'], z) for z in self.zs], passes)
        self.bot = []
        r, ar = spec['wheel_r'], spec['arch_r']
        for z, b in zip(self.zs, _smooth([_interp(spec['bottom'], z) for z in self.zs], passes)):
            for az, _ in spec['axles']:
                if abs(z - az) < ar:
                    b = max(b, r + math.sqrt(ar ** 2 - (z - az) ** 2) * 0.95)
            self.bot.append(b)

    def at(self, values, z):
        zs = self.zs
        t = (z - zs[0]) / (zs[-1] - zs[0]) * (len(zs) - 1)
        i = max(0, min(len(zs) - 2, int(t)))
        f = min(1.0, max(0.0, t - i))
        return values[i] * (1 - f) + values[i + 1] * f

    def _yc_h(self, z):
        yb, yt = self.at(self.bot, z), self.at(self.top, z)
        return (yb + yt) / 2, (yt - yb) / 2

    def side_x(self, z, y):
        yc, h = self._yc_h(z)
        v = min(1.0, abs((y - yc) / h))
        return self.at(self.w, z) * (1 - v ** self.se) ** (1 / self.se)

    def body_y_at(self, z, x):
        yc, h = self._yc_h(z)
        u = min(1.0, abs(x / self.at(self.w, z)))
        return yc + h * (1 - u ** self.se) ** (1 / self.se)


def _loft(rows, centers, closed, classify, out, lining=None):
    R, K = len(rows), len(rows[0])
    acc = [[[0.0, 0.0, 0.0] for _ in range(K)] for _ in range(R)]
    quads = []
    for i in range(R - 1):
        ce = tuple((centers[i][j] + centers[i + 1][j]) / 2 for j in range(3))
        for k in range(K if closed else K - 1):
            k2 = (k + 1) % K
            pts = (rows[i][k], rows[i][k2], rows[i + 1][k2], rows[i + 1][k])
            n = _cross(_sub(pts[2], pts[0]), _sub(pts[3], pts[1]))
            fc = tuple(sum(p[j] for p in pts) / 4 for j in range(3))
            if _dot(n, _sub(fc, ce)) < 0:
                n = (-n[0], -n[1], -n[2])
            for ii, kk in ((i, k), (i, k2), (i + 1, k2), (i + 1, k)):
                a = acc[ii][kk]
                a[0] += n[0]
                a[1] += n[1]
                a[2] += n[2]
            quads.append((i, k, k2, pts, fc, _norm(n) if any(n) else (0, 1, 0)))
    norms = [[_norm(a) if any(a) else (0, 1, 0) for a in row] for row in acc]
    for i, k, k2, pts, fc, fn in quads:
        res = classify(i, k, fc, fn)
        if res is None:
            continue
        key, col, style = res
        alpha = 0.6 if key == 'glass' else 1.0
        ns = (norms[i][k], norms[i][k2], norms[i + 1][k2], norms[i + 1][k])
        out[key].smooth_face(list(pts), [paint(col, n, style, alpha) for n in ns])
        if lining is not None and key == 'body':
            inner = [(p[0] - n[0] * 0.015, p[1] - n[1] * 0.015, p[2] - n[2] * 0.015) for p, n in zip(pts, ns)]
            lining.smooth_face(inner, [paint(HEADLINER, (-n[0], -n[1], -n[2]), 'matte') for n in ns])


def _rounded_box(out, c, half, e, classify, lining=None, nu=32, nv=16):
    cx, cy, cz = c
    hx, hy, hz = half
    rows = []
    for j in range(nv + 1):
        v = -math.pi / 2 + math.pi * j / nv
        row = []
        for i in range(nu):
            u = -math.pi + math.tau * i / nu
            cv = _se(math.cos(v), e)
            row.append((cx + hx * cv * _se(math.cos(u), e), cy + hy * _se(math.sin(v), e),
                        cz + hz * cv * _se(math.sin(u), e)))
        rows.append(row)
    _loft(rows, [c] * len(rows), True, classify, out, lining)


def _body(prof, col, out):
    spec = prof.spec
    ring = 32
    rows, centers = [], []
    angles = [-math.pi / 2 + k / ring * math.tau for k in range(ring)]
    for z, w, yb, yt in zip(prof.zs, prof.w, prof.bot, prof.top):
        yc, h = (yb + yt) / 2, (yt - yb) / 2
        rows.append([(w * _se(math.cos(a), prof.se), yc + h * _se(math.sin(a), prof.se), z) for a in angles])
        centers.append((0, yc, z))
    hl, gr, tl, op = spec['headlight'], spec['grille'], spec['tail'], spec['open']

    def classify(i, k, fc, fn):
        z = (prof.zs[i] + prof.zs[i + 1]) / 2
        am = angles[k] + math.pi / ring
        s, ax = math.sin(am), abs(math.cos(am))
        if op[0] < z < op[1] and s > 0.78:
            return None
        if s < -0.55:
            return 'body', TRIM, 'matte'
        if hl and hl[0] < z < hl[1] and hl[2] < s < hl[3] and ax > hl[4]:
            return 'body', HEADLIGHT, 'emit'
        if z > gr[0] and gr[1] <= s < gr[2] and ax < gr[3]:
            return 'body', GRILLE, 'gloss'
        if z < tl[0] and tl[1] < s < tl[2] and ax >= tl[3]:
            return 'body', TAILLIGHT, 'emit'
        if s < spec['clad']:
            return 'body', TRIM, 'matte'
        return 'body', col, 'gloss'

    _loft(rows, centers, True, classify, out)
    for idx, cap_col, nz in ((-1, GRILLE, 1), (0, col, -1)):
        ring_pts, (cx, cy, cz) = rows[idx], centers[idx]
        c = paint(cap_col, (0, 0, nz))
        for k in range(ring):
            out['body'].smooth_face([(cx, cy, cz), ring_pts[k], ring_pts[(k + 1) % ring]], [c, c, c])


def _greenhouse(prof, col, out, lining):
    g = prof.spec['gh']
    n_slices = 40
    z0, z1 = g['z']
    gz = [z0 + i * (z1 - z0) / (n_slices - 1) for i in range(n_slices)]
    roof = _smooth([_interp(g['roof'], z) for z in gz], prof.spec.get('smooth', 4))
    bw, cs = g['bw'], g['section']
    half = len(cs) - 1
    section = [(-u, v) for u, v in cs] + [(u, v) for u, v in reversed(cs[:-1])]
    rows, centers = [], []
    for z, top in zip(gz, roof):
        yb = prof.body_y_at(z, bw) - 0.01
        h = max(0.002, top - yb)
        rows.append([(u * bw, yb + h * v, z) for u, v in section])
        centers.append((0, yb, z))

    def classify(i, k, fc, fn):
        z = (gz[i] + gz[i + 1]) / 2
        seg = min(k, 2 * half - 1 - k)
        side = g['side'][0] < z < g['side'][1]
        if seg == 0:
            return ('body', CHROME, 'gloss') if g['chrome'] and g['chrome'][0] < z < g['chrome'][1] \
                else ('body', col, 'gloss')
        if seg <= 4:
            if not side:
                return 'body', col, 'gloss'
            if g['bpillar'] and g['bpillar'][0] < z < g['bpillar'][1]:
                return 'body', TRIM, 'matte'
            return 'glass', GLASS, 'glass'
        if seg == 5:
            return 'body', col, 'gloss'
        if z > g['ws'] or z < g['rw']:
            return 'glass', GLASS, 'glass'
        return 'body', col, 'gloss'

    _loft(rows, centers, False, classify, out, lining)


def _common_details(mb, prof, col):
    spec = prof.spec
    dark_seam = tuple(c * 0.35 for c in col)
    mx, my, mz = spec['mirror']
    belt = spec['interior']['belt']
    for sx in (-1, 1):
        for z in spec['seams']:
            yb, yt = prof.at(prof.bot, z) + 0.06, prof.at(prof.top, z) - 0.03
            steps = 8
            for j in range(steps):
                y0, y1 = yb + (yt - yb) * j / steps, yb + (yt - yb) * (j + 1) / steps
                x0, x1 = prof.side_x(z, y0) + 0.004, prof.side_x(z, y1) + 0.004
                mb.face([(sx * x0, y0, z - 0.006), (sx * x0, y0, z + 0.006),
                         (sx * x1, y1, z + 0.006), (sx * x1, y1, z - 0.006)], dark_seam, normal=(sx, 0, 0))
        for z in spec['handles']:
            y = belt - 0.07
            mb.box(sx * (prof.side_x(z, y) + 0.01), y, z, 0.02, 0.03, 0.17, CHROME)
        mb.blob(sx * mx, my, mz, 0.11, 0.07, 0.13, col, 31 + sx, jitter=0.0)
        mb.box(sx * (mx - 0.07), my - 0.02, mz + 0.02, 0.12, 0.03, 0.06, TRIM)


def _plates(mb, half, y_front, y_rear):
    mb.box(0, y_rear, -half - 0.005, 0.52, 0.12, 0.012, rgb(70, 70, 75))
    mb.box(0, y_front, half + 0.005, 0.52, 0.12, 0.012, rgb(70, 70, 75))


def _extras_sedan(mb, prof, col):
    glow = Color(*TAILLIGHT, 1)
    mb.smooth_face([(-0.74, 0.79, -2.478), (0.74, 0.79, -2.478), (0.74, 0.84, -2.478), (-0.74, 0.84, -2.478)],
                   [glow] * 4)
    _plates(mb, 2.47, 0.5, 0.58)
    mb.box(0, 0.705, 2.475, 1.3, 0.018, 0.02, CHROME)
    for sx in (-1, 1):
        mb.box(sx * 0.62, 0.4, 2.45, 0.16, 0.04, 0.02, HEADLIGHT)


def _extras_crossover(mb, prof, col):
    for sx in (-1, 1):
        mb.box(sx * 0.55, 1.73, -0.7, 0.05, 0.05, 1.8, TRIM)
    mb.box(0, 1.6, -1.98, 1.3, 0.04, 0.22, col)
    mb.box(0, 0.48, 2.3, 0.9, 0.05, 0.05, CHROME)
    mb.box(0, 0.5, -2.31, 1.2, 0.05, 0.05, CHROME)
    _plates(mb, 2.32, 0.62, 0.78)


def _extras_jeep(mb, prof, col):
    for sx in (-1, 1):
        mb.cylinder(sx * 0.62, 0.98, 2.29, 0.17, 0.17, 0.06, CHROME, segs=16, axis='z')
        mb.cylinder(sx * 0.62, 0.98, 2.31, 0.13, 0.13, 0.06, HEADLIGHT, segs=16, axis='z')
    for j in range(7):
        mb.box(-0.36 + j * 0.12, 0.98, 2.305, 0.05, 0.3, 0.02, CHROME)
    mb.box(0, 0.62, 2.38, 1.9, 0.18, 0.18, TRIM)
    mb.box(0, 0.66, -2.36, 1.9, 0.16, 0.14, TRIM)
    mb.cylinder(0, 1.05, -2.44, 0.42, 0.42, 0.26, rgb(22, 22, 24), segs=20, axis='z')
    mb.cylinder(0, 1.05, -2.44, 0.26, 0.26, 0.28, rgb(150, 150, 155), segs=16, axis='z')
    for sx in (-1, 1):
        mb.box(sx * 0.7, 2.03, -0.8, 0.05, 0.06, 2.3, TRIM)
    for z in (-1.8, -0.8, 0.2):
        mb.box(0, 2.05, z, 1.45, 0.04, 0.05, TRIM)
    for az, _ in prof.spec['axles']:
        for sx in (-1, 1):
            mb.box(sx * 0.99, 1.04, az, 0.16, 0.07, 1.2, TRIM)
    mb.box(0, 0.8, -2.31, 0.52, 0.12, 0.012, rgb(70, 70, 75))


def _extras_pickup(mb, prof, col):
    mb.box(0, 0.9, -1.62, 1.86, 0.04, 2.04, rgb(40, 40, 44))
    mb.box(0, 1.05, -0.6, 1.85, 0.3, 0.04, col)
    for j in range(3):
        mb.box(0, 0.86 + j * 0.1, 2.71, 1.15, 0.03, 0.02, CHROME)
    mb.box(0, 0.64, 2.73, 1.9, 0.2, 0.15, CHROME)
    mb.box(0, 0.66, -2.72, 1.9, 0.16, 0.12, CHROME)
    mb.box(0, 1.07, -2.71, 0.3, 0.04, 0.02, TRIM)
    for sx in (-1, 1):
        mb.box(sx * 0.98, 0.5, 0.2, 0.14, 0.04, 1.5, TRIM)
    mb.box(0, 0.86, -2.715, 0.52, 0.12, 0.012, rgb(70, 70, 75))


def _interior(mb, spec):
    it = spec['interior']
    f, belt, dz, sz, rz = it['floor'], it['belt'], it['dash_z'], it['seat_z'], it['rear_z']
    dark, seat, lighter = rgb(30, 30, 34), rgb(58, 54, 52), rgb(48, 48, 54)
    zb, zf = it['zback'], it['zfront']
    mb.box(0, f, (zb + zf) / 2, 1.2, 0.04, zf - zb, dark)
    cuts = sorted({zb, zf} | {c for az, _ in spec['axles'] for c in (az - spec['arch_r'], az + spec['arch_r'])
                             if zb < c < zf})
    arch_top = spec['wheel_r'] + spec['arch_r'] * 0.95 + 0.03
    for z0, z1 in zip(cuts, cuts[1:]):
        zm = (z0 + z1) / 2
        ybot = arch_top if any(abs(zm - az) < spec['arch_r'] for az, _ in spec['axles']) else f + 0.2
        if ybot < belt - 0.05:
            for sx in (-1, 1):
                mb.box(sx * it['door_x'], (ybot + belt) / 2, zm, 0.05, belt - ybot, z1 - z0, lighter)
    mb.box(0, belt - 0.15, dz, 1.62, 0.24, 0.4, dark)
    mb.box(0, belt - 0.015, dz + 0.06, 1.62, 0.03, 0.32, lighter)
    mb.box(0, f + 0.14, sz + 0.37, 0.24, 0.24, 0.9, dark)
    for sx in (-0.4, 0.4):
        mb.box(sx, f + 0.16, sz, 0.5, 0.12, 0.52, seat)
        mb.box(sx, f + 0.5, sz - 0.3, 0.5, 0.6, 0.11, seat)
        mb.box(sx, f + 0.88, sz - 0.33, 0.26, 0.18, 0.09, seat)
    if rz is not None:
        mb.box(0, f + 0.16, rz, 1.4, 0.12, 0.48, seat)
        mb.box(0, f + 0.46, rz - 0.28, 1.4, 0.52, 0.1, seat)
    glow, glow_hi = Color(0.12, 0.38, 0.7, 1), Color(0.35, 0.65, 0.95, 1)
    zc = dz - 0.14
    mb.smooth_face([(-0.55, belt - 0.025, zc), (-0.25, belt - 0.025, zc), (-0.25, belt + 0.025, zc + 0.015),
                    (-0.55, belt + 0.025, zc + 0.015)], [glow, glow, glow_hi, glow_hi])
    zc = dz - 0.12
    mb.smooth_face([(0.0, belt - 0.02, zc), (0.28, belt - 0.02, zc), (0.28, belt + 0.07, zc + 0.025),
                    (0.0, belt + 0.07, zc + 0.025)], [glow, glow, glow_hi, glow_hi])


def _wheel(r, w, rim_col, dual=False):
    mb = MeshBuilder()
    tire, recess = rgb(22, 22, 24), rgb(45, 45, 50)
    mb.cylinder(0, 0, 0, r, r, w, tire, segs=24, cap_col=rgb(30, 30, 32), axis='x')
    if dual:
        mb.cylinder(0, 0, 0, r * 0.97, r * 0.97, w * 0.12 + 0.01, rgb(12, 12, 14), segs=24, axis='x')
    segs = 24
    f = w / 2
    for sx in (-1, 1):
        n = (sx, 0, 0)
        mb.face([(sx * (f + 0.005), math.cos(i / segs * math.tau) * r * 0.55, math.sin(i / segs * math.tau) * r * 0.55)
                 for i in range(segs)], recess, normal=n)
        for i in range(segs):
            a0, a1 = i / segs * math.tau, (i + 1) / segs * math.tau
            mb.face([(sx * (f + 0.01), math.cos(a0) * r * 0.53, math.sin(a0) * r * 0.53),
                     (sx * (f + 0.01), math.cos(a1) * r * 0.53, math.sin(a1) * r * 0.53),
                     (sx * (f + 0.01), math.cos(a1) * r * 0.69, math.sin(a1) * r * 0.69),
                     (sx * (f + 0.01), math.cos(a0) * r * 0.69, math.sin(a0) * r * 0.69)], rim_col, normal=n)
        for j in range(10):
            a = j / 10 * math.tau + (0.12 if j % 2 else -0.12)
            d, p, hw = (0, math.cos(a), math.sin(a)), (0, -math.sin(a), math.cos(a)), r * 0.05
            pts = [(sx * (f + 0.012), d[1] * rr + p[1] * o, d[2] * rr + p[2] * o)
                   for rr, o in ((r * 0.14, -hw), (r * 0.14, hw), (r * 0.55, hw * 1.6), (r * 0.55, -hw * 1.6))]
            mb.face(pts, rim_col, normal=n)
        mb.face([(sx * (f + 0.014), math.cos(i / 12 * math.tau) * r * 0.17, math.sin(i / 12 * math.tau) * r * 0.17)
                 for i in range(12)], rim_col, normal=n)
    return mb


def build_steering_wheel(parent):
    mb = MeshBuilder()
    dark = rgb(28, 28, 30)
    big, small, R, r = 28, 8, 0.18, 0.02
    for i in range(big):
        for j in range(small):
            quad, cols = [], []
            for ii, jj in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                a, b = ii / big * math.tau, jj / small * math.tau
                n = (math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b))
                quad.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a),
                             r * math.sin(b)))
                cols.append(paint(dark, n, 'matte'))
            mb.smooth_face(quad, cols)
    for a in (0.0, math.pi, -math.pi / 2):
        ca, sa = math.cos(a), math.sin(a)
        mb.face([(-sa * 0.025, ca * 0.025, 0), (sa * 0.025, -ca * 0.025, 0),
                 (ca * R + sa * 0.025, sa * R - ca * 0.025, 0), (ca * R - sa * 0.025, sa * R + ca * 0.025, 0)],
                rgb(50, 50, 55), normal=(0, 0, -1))
    mb.cylinder(0, 0, 0, 0.06, 0.06, 0.04, rgb(45, 45, 50), segs=12, axis='x')
    return mb.build(parent=parent)


def _shadow(parent, rx, rz, z=0.0):
    mb = MeshBuilder()
    centre, edge = Color(0, 0, 0, 0.45), Color(0, 0, 0, 0)
    segs = 24
    for i in range(segs):
        a0, a1 = i / segs * math.tau, (i + 1) / segs * math.tau
        mb.smooth_face([(0, 0.03, z), (math.cos(a0) * rx, 0.03, z + math.sin(a0) * rz),
                        (math.cos(a1) * rx, 0.03, z + math.sin(a1) * rz)], [centre, edge, edge])
    return mb.build(parent=parent)


def _build_truck(col, rim_col):
    out = {'body': MeshBuilder(), 'glass': MeshBuilder()}
    lining, interior = MeshBuilder(), MeshBuilder()
    body = out['body']

    def cab(i, k, fc, n):
        x, y, z = fc
        if n[2] > 0.55 and 2.15 < y < 3.0 and abs(x) < 1.08:
            return 'glass', GLASS, 'glass'
        if abs(n[0]) > 0.6 and 2.2 < y < 2.95 and z > 1.6:
            return 'glass', GLASS, 'glass'
        if n[2] > 0.5 and y < 1.45:
            return 'body', GRILLE, 'gloss'
        if n[1] < -0.6:
            return 'body', TRIM, 'matte'
        return 'body', col, 'gloss'

    _rounded_box(out, (0, 2.1, 2.05), (1.24, 1.12, 1.0), 6, cab, lining)
    _rounded_box(out, (0, 3.42, 1.75), (1.15, 0.3, 0.75), 5, lambda *a: ('body', col, 'gloss'))
    body.box(0, 0.85, 3.08, 2.4, 0.35, 0.18, rgb(70, 72, 78))
    for sx in (-1, 1):
        body.box(sx * 0.85, 1.05, 3.08, 0.4, 0.14, 0.04, HEADLIGHT)
        body.box(sx * 1.1, 1.05, 2.05, 0.35, 0.08, 1.15, TRIM)
        body.box(sx * 0.45, 0.85, -0.6, 0.18, 0.25, 6.2, rgb(40, 40, 44))
        body.cylinder(sx * 1.0, 0.95, 0.35, 0.3, 0.3, 1.2, CHROME, segs=16, axis='z')
        body.cylinder(sx * 1.05, 1.5, 0.95, 0.09, 0.09, 2.4, CHROME, segs=10)
        body.box(sx * 1.45, 2.6, 2.9, 0.08, 0.5, 0.2, TRIM)
        body.box(sx * 1.32, 2.85, 2.95, 0.3, 0.04, 0.04, TRIM)
        body.box(sx * 1.0, 0.6, -3.4, 0.5, 0.6, 0.04, TRIM)
        body.box(sx * 1.26, 1.25, 1.5, 0.12, 0.06, 0.4, rgb(70, 72, 78))
    for j in range(4):
        body.box(0, 1.12 + j * 0.1, 3.07, 1.4, 0.035, 0.02, CHROME)
    body.box(0, 1.18, -1.3, 1.4, 0.1, 1.2, rgb(40, 40, 44))
    interior.box(0, 2.0, 2.7, 2.2, 0.5, 0.5, rgb(30, 30, 34))
    interior.box(0, 1.2, 2.0, 2.3, 0.04, 1.8, rgb(30, 30, 34))
    for sx in (-0.6, 0.6):
        interior.box(sx, 1.62, 2.05, 0.55, 0.14, 0.55, rgb(58, 54, 52))
        interior.box(sx, 2.05, 1.72, 0.55, 0.75, 0.12, rgb(58, 54, 52))
    interior.box(0, 1.6, 1.2, 2.2, 0.5, 0.25, rgb(58, 54, 52))
    glow = Color(0.12, 0.38, 0.7, 1)
    interior.smooth_face([(-0.75, 2.26, 2.5), (-0.45, 2.26, 2.5), (-0.45, 2.32, 2.53), (-0.75, 2.32, 2.53)], [glow] * 4)

    t_out = {'body': MeshBuilder(), 'glass': MeshBuilder()}

    def trailer(i, k, fc, n):
        y = fc[1]
        if 1.75 < y < 1.95 and abs(n[1]) < 0.5:
            return 'body', col, 'gloss'
        return 'body', rgb(236, 236, 238), 'gloss'

    _rounded_box(t_out, (0, 2.75, -6.0), (1.28, 1.35, 6.6), 12, trailer)
    tb = t_out['body']
    tb.box(0, 1.28, -6.0, 0.9, 0.2, 12.4, rgb(40, 40, 44))
    for sx in (-1, 1):
        tb.box(sx * 0.6, 0.75, -1.5, 0.12, 1.0, 0.12, rgb(70, 72, 78))
        tb.box(sx * 0.8, 1.6, -12.62, 0.3, 0.12, 0.03, TAILLIGHT)
    tb.box(0, 2.75, -12.615, 0.03, 2.4, 0.02, rgb(150, 150, 155))
    tb.box(0, 0.75, -12.55, 2.2, 0.12, 0.1, rgb(70, 72, 78))
    return out, lining, interior, t_out


class Vehicle:
    def __init__(self):
        self.root = None
        self.glass = []
        self.wheels = []
        self.seat = (0, 1, 0)
        self.steering = ((0, 1, 0), -25)
        self.trailer = None
        self.trailer_wheels = []


def build_vehicle(model_id, color_idx=0, rim_idx=0):
    spec = SPECS[model_id]
    col = PAINTS[color_idx % len(PAINTS)][1]
    rim = RIMS[rim_idx % len(RIMS)][1]
    v = Vehicle()
    v.root = Entity()

    if spec.get('custom') == 'truck':
        out, lining, interior, t_out = _build_truck(col, rim)
        _shadow(v.root, 1.5, 3.4, 0.0)
        wheel_defs = [(1.07, 2.05, True, 0.52, 0.32, False), (0.98, -1.0, False, 0.52, 0.6, True),
                      (0.98, -2.3, False, 0.52, 0.6, True)]
        v.seat, v.steering = spec['seat'], spec['steering']
        v.trailer = Entity()
        _shadow(v.trailer, 1.5, 6.8, -6.0)
        t_out['body'].build(parent=v.trailer)
        for z in (-9.0, -10.3, -11.6):
            for sx in (-1, 1):
                holder = Entity(parent=v.trailer, position=(sx * 0.98, 0.5, z))
                _wheel(0.5, 0.55, rim, dual=True).build(parent=holder)
                v.trailer_wheels.append(holder)
    else:
        prof = Profile(spec)
        out = {'body': MeshBuilder(), 'glass': MeshBuilder()}
        lining, interior = MeshBuilder(), MeshBuilder()
        _body(prof, col, out)
        _greenhouse(prof, col, out, lining)
        _common_details(out['body'], prof, col)
        globals()['_extras_' + spec['extras']](out['body'], prof, col)
        _interior(interior, spec)
        _shadow(v.root, spec['half'] * 0.47, spec['half'] * 1.07)
        r, w, x = spec['wheel_r'], spec['wheel_w'], spec['wheel_x']
        wheel_defs = [(x, az, front, r, w, False) for az, front in spec['axles']]
        it = spec['interior']
        v.seat = (-0.4, it['floor'] + 0.86, it['seat_z'] - 0.03)
        v.steering = ((-0.4, it['belt'] - 0.02, it['dash_z'] - 0.34), -25)

    out['body'].build(parent=v.root)
    lining.build(parent=v.root)
    interior.build(parent=v.root)
    v.glass = list(out['glass'].build(parent=v.root).children)
    for x, z, front, r, w, dual in wheel_defs:
        for sx in (-1, 1):
            holder = Entity(parent=v.root, position=(sx * x, r, z))
            _wheel(r, w, rim, dual).build(parent=holder)
            v.wheels.append((holder, front))
    return v
