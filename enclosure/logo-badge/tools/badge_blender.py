# Builds the ChAIpi wordmark badge (logo No. 8) in Blender and exports STL/GLB plus a preview render.
# Run: Blender --background --factory-startup --python badge_blender.py -- wordmark.json dots.json OUTDIR
import bpy, bmesh, json, math, os, re, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
data = json.load(open(argv[0])); dots = json.load(open(argv[1])); OUT = argv[2]
os.makedirs(OUT, exist_ok=True)

K = dots['k']                      # mm per font unit (wordmark is 50 mm wide)
LETTER_H = 1.2                     # raised height of the letters, mm
PLATE_T = 1.6                      # badge plate thickness, mm
SINK = 0.2                         # letters sink into the plate so the one-piece print fuses
MARGIN_X, MARGIN_Y, RADIUS = 4.5, 3.8, 3.0

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 0.001; scene.unit_settings.length_unit = 'MILLIMETERS'

def tokens(d):
    for cmd, args in re.findall(r'([MLHVQCZ])([^MLHVQCZ]*)', d):
        nums = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?(?:e-?\d+)?', args)]
        yield cmd, nums

def contours_from_svg(d, ox):
    """Return contours as lists of cubic segments [(p0,c1,c2,p3)] in mm (y-up)."""
    out, cur, start, segs = [], None, None, []
    P = lambda x, y: Vector(((x + ox) * K, y * K, 0))
    fx = fy = 0.0
    def line(p):
        nonlocal cur
        segs.append((cur, cur.lerp(p, 1/3), cur.lerp(p, 2/3), p)); cur = p
    for cmd, n in tokens(d):
        if cmd == 'M':
            if segs: out.append(segs); segs = []
            fx, fy = n[0], n[1]; cur = start = P(fx, fy)
            for i in range(2, len(n), 2):           # implicit lineto after moveto
                fx, fy = n[i], n[i+1]; line(P(fx, fy))
        elif cmd == 'L':
            for i in range(0, len(n), 2):
                fx, fy = n[i], n[i+1]; line(P(fx, fy))
        elif cmd == 'H':
            for v in n: fx = v; line(P(fx, fy))
        elif cmd == 'V':
            for v in n: fy = v; line(P(fx, fy))
        elif cmd == 'Q':
            for i in range(0, len(n), 4):
                q = P(n[i], n[i+1]); fx, fy = n[i+2], n[i+3]; p = P(fx, fy)
                segs.append((cur, cur + (q - cur) * (2/3), p + (q - p) * (2/3), p)); cur = p
        elif cmd == 'C':
            for i in range(0, len(n), 6):
                c1 = P(n[i], n[i+1]); c2 = P(n[i+2], n[i+3]); fx, fy = n[i+4], n[i+5]; p = P(fx, fy)
                segs.append((cur, c1, c2, p)); cur = p
        elif cmd == 'Z':
            if cur is not None and start is not None and (cur - start).length > 1e-6:
                segs.append((cur, cur.lerp(start, 1/3), cur.lerp(start, 2/3), start))
            if segs: out.append(segs); segs = []
            cur = start
    if segs: out.append(segs)
    return out

def spark_contour(cx, cy, s):
    q = .16 * s
    pts = [(cx, cy - s), (cx + q, cy - q), (cx + s, cy), (cx + q, cy + q), (cx, cy + s), (cx - q, cy + q), (cx - s, cy), (cx - q, cy - q)]
    V = [Vector((x * K, y * K, 0)) for x, y in pts]
    segs = []
    for i in range(0, 8, 2):
        a, ctrl, b = V[i], V[i+1], V[(i+2) % 8]
        segs.append((a, a + (ctrl - a) * (2/3), b + (ctrl - b) * (2/3), b))
    return [segs]

def circle_contour(cx, cy, r):
    c = Vector((cx * K, cy * K, 0)); R = r * K; kk = 0.5523 * R; segs = []
    pts = [c + Vector((R, 0, 0)), c + Vector((0, R, 0)), c + Vector((-R, 0, 0)), c + Vector((0, -R, 0))]
    tans = [Vector((0, 1, 0)), Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((1, 0, 0))]
    for i in range(4):
        a, b = pts[i], pts[(i+1) % 4]
        segs.append((a, a + tans[i] * kk, b - tans[(i+1) % 4] * kk, b))
    return [segs]

def curve_object(name, contours, depth):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '2D'; cu.fill_mode = 'BOTH'
    cu.extrude = depth / 2; cu.resolution_u = 14
    for segs in contours:
        sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(segs) - 1); sp.use_cyclic_u = True
        for i, (p0, c1, c2, p3) in enumerate(segs):
            bp = sp.bezier_points[i]; bp.co = p0; bp.handle_right = c1; bp.handle_right_type = 'FREE'
            nxt = sp.bezier_points[(i + 1) % len(segs)]; nxt.handle_left = c2; nxt.handle_left_type = 'FREE'
    ob = bpy.data.objects.new(name, cu); scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    for o in scene.objects: o.select_set(o == ob)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    me = ob.data; bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bm.to_mesh(me); bm.free()
    ob.location.z = depth / 2
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return ob

# --- gather contours per colour role ---
roles = {'ink': [], 'accent': [], 'berry': []}
x = 0
for seg in data['segs']:
    for g in seg['glyphs']:
        roles[seg['role']] += contours_from_svg(g['svg'], x + g['x'])
    x += seg['adv']
roles['accent'] += spark_contour(dots['spark'][0], dots['spark'][1], dots['spark_r'])
roles['berry'] += circle_contour(dots['berry'][0], dots['berry'][1], dots['berry_r'])

parts = {r: curve_object('letters_' + r, c, LETTER_H) for r, c in roles.items()}

# --- bounding box of the artwork, for the plate ---
mins = Vector((1e9, 1e9, 0)); maxs = Vector((-1e9, -1e9, 0))
for ob in parts.values():
    for v in ob.data.vertices:
        mins.x = min(mins.x, v.co.x); mins.y = min(mins.y, v.co.y); maxs.x = max(maxs.x, v.co.x); maxs.y = max(maxs.y, v.co.y)
cx, cy = (mins.x + maxs.x) / 2, (mins.y + maxs.y) / 2
for ob in parts.values():                       # centre the artwork on the origin
    for v in ob.data.vertices: v.co.x -= cx; v.co.y -= cy
w, h = maxs.x - mins.x, maxs.y - mins.y
PW, PHt = w + 2 * MARGIN_X, h + 2 * MARGIN_Y

def plate(name, W_, H_, R_, T_):
    bm = bmesh.new(); pts = []
    for (sx, sy, a0) in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
        ccx, ccy = sx * (W_ / 2 - R_), sy * (H_ / 2 - R_)
        for k in range(13):
            a = math.radians(a0 + k * 7.5); pts.append((ccx + R_ * math.cos(a), ccy + R_ * math.sin(a)))
    vb = [bm.verts.new((px, py, 0)) for px, py in pts]; vt = [bm.verts.new((px, py, T_)) for px, py in pts]
    bm.faces.new(list(reversed(vb))); bm.faces.new(vt)
    n = len(pts)
    for i in range(n): bm.faces.new((vb[i], vb[(i+1) % n], vt[(i+1) % n], vt[i]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); return ob

base = plate('badge_plate', PW, PHt, RADIUS, PLATE_T)

def mat(name, rgb, rough=.45):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    return m
def srgb(hexs):
    c = [int(hexs[i:i+2], 16) / 255 for i in (1, 3, 5)]
    return tuple(((v + .055) / 1.055) ** 2.4 if v > .04045 else v / 12.92 for v in c)
MATS = {'ink': mat('cream', srgb('#f3ede6')), 'accent': mat('masala', srgb('#e7a54d')), 'berry': mat('raspberry', srgb('#f2557f')), 'plate': mat('shell', srgb('#3a2a22'), .6)}
base.data.materials.append(MATS['plate'])
for r, ob in parts.items(): ob.data.materials.append(MATS[r])

def export_stl(objs, path):
    for o in scene.objects: o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    try: bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0, apply_modifiers=True)
    except AttributeError: bpy.ops.export_mesh.stl(filepath=path, use_selection=True, global_scale=1.0)

# 1) inlay parts: letters only, 0 to 1.2 mm, to sit in a recess on the case lid
for r, ob in parts.items(): export_stl([ob], os.path.join(OUT, 'inlay_' + r + '.stl'))
# 2) badge: letters stand on the plate (sunk 0.2 mm so a single-colour print fuses)
for ob in parts.values():
    for v in ob.data.vertices: v.co.z += PLATE_T - SINK
export_stl([base], os.path.join(OUT, 'badge_plate.stl'))
for r, ob in parts.items(): export_stl([ob], os.path.join(OUT, 'badge_' + r + '.stl'))
export_stl([base] + list(parts.values()), os.path.join(OUT, 'badge_one_piece.stl'))

# coloured GLB for quick viewing
for o in scene.objects: o.select_set(True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, 'chaipi-badge.glb'), export_format='GLB', use_selection=True, export_yup=True)

# --- preview render ---
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (*srgb('#151214'), 1); world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.45
ground = plate('ground', 400, 400, 1, 0.01); ground.location.z = -0.02; ground.data.materials.append(mat('ground', srgb('#1c1719'), .8))
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 85; cam = bpy.data.objects.new('cam', cam_d); scene.collection.objects.link(cam); scene.camera = cam
dist = PW * 3.3
cam.location = (0, -dist * .62, dist * .78)
cam.rotation_euler = (Vector((0, 0, 0)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 1.4; sun.angle = math.radians(8)
so = bpy.data.objects.new('sun', sun); so.rotation_euler = (math.radians(38), math.radians(-22), math.radians(-30)); scene.collection.objects.link(so)
for (loc, en, size) in [((-120, -100, 180), 1.1e6, 80), ((140, 60, 120), 0.45e6, 60)]:
    ld = bpy.data.lights.new('l', 'AREA'); ld.energy = en; ld.size = size
    lo = bpy.data.objects.new('l', ld); lo.location = loc; scene.collection.objects.link(lo)
    lo.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 96
try: scene.cycles.use_denoising = True
except Exception: pass
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.view_settings.exposure = -0.4
scene.render.filepath = os.path.join(OUT, 'chaipi-badge-preview.png')
bpy.ops.render.render(write_still=True)
json.dump({'plate_mm': [round(PW, 2), round(PHt, 2), PLATE_T], 'artwork_mm': [round(w, 2), round(h, 2)], 'letter_height_mm': LETTER_H}, open(os.path.join(OUT, 'dimensions.json'), 'w'), indent=1)
print('BADGE DONE', round(PW, 2), 'x', round(PHt, 2), 'mm')
