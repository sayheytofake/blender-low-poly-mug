import bpy
import os
import math
import tempfile
from mathutils import Vector

OUTPUT_DIR = tempfile.gettempdir()
PNG_PATH = os.path.join(OUTPUT_DIR, "low_poly_mug.png")
BLEND_PATH = os.path.join(OUTPUT_DIR, "low_poly_mug.blend")

def select_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def aim_at(obj, target=(0, 0, 0)):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").euler

def make_material(name, color, roughness=0.65, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        return mat

    if len(color) == 3:
        color = tuple(list(color) + [1.0])

    bsdf.inputs["Base Color"].default_value = tuple(color)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat

def set_flat_shading(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = False
    if hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = False
    obj.data.update()

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def set_render_engine(scene):
    # Blender 4.x uses EEVEE Next; older versions use EEVEE.
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            return engine
        except Exception:
            pass

    scene.render.engine = "CYCLES"
    return "CYCLES"

def inspect_render(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = img.pixels[:]
    n = w * h

    total = 0.0
    total_sq = 0.0
    non_bright = 0

    for i in range(n):
        r = px[i * 4]
        g = px[i * 4 + 1]
        b = px[i * 4 + 2]
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        total += lum
        total_sq += lum * lum
        if min(r, g, b) < 0.95:
            non_bright += 1

    mean = total / n
    stddev = math.sqrt(max(total_sq / n - mean * mean, 0.0))
    ratio = non_bright / n

    try:
        bpy.data.images.remove(img, do_unlink=True)
    except TypeError:
        bpy.data.images.remove(img)

    return mean, stddev, ratio

# -------------------------
# Scene setup
# -------------------------
scene = bpy.context.scene
clear_scene()

ceramic_mat = make_material("Matte_Ceramic", (0.82, 0.86, 0.90), roughness=0.62)
ground_mat = make_material("Ground_Grey", (0.25, 0.27, 0.30), roughness=0.90)

# -------------------------
# Low-poly mug body
# -------------------------
bpy.ops.mesh.primitive_cylinder_add(
    vertices=16,
    radius=0.55,
    depth=1.15,
    end_fill_type='NGON',
    location=(0, 0, 1.15 / 2)
)
mug = bpy.context.object
mug.name = "LowPoly_Mug_Body"

# Inner cavity cutter
bpy.ops.mesh.primitive_cylinder_add(
    vertices=16,
    radius=0.44,
    depth=1.00,
    end_fill_type='NGON',
    location=(0, 0, 0.62)
)
cutter = bpy.context.object
cutter.name = "Mug_Cavity_Cutter"

select_only(mug)
mod = mug.modifiers.new(name="Inner Cavity", type='BOOLEAN')
mod.object = cutter
mod.operation = 'DIFFERENCE'
bpy.ops.object.modifier_apply(modifier=mod.name)

bpy.data.objects.remove(cutter, do_unlink=True)
mug.data.materials.append(ceramic_mat)
set_flat_shading(mug)

# -------------------------
# Low-poly handle
# -------------------------
curve = bpy.data.curves.new("Mug_Handle_Curve", type='CURVE')
curve.dimensions = '3D'
curve.resolution_u = 10
curve.render_resolution_u = 10
curve.bevel_depth = 0.065
curve.bevel_resolution = 4
curve.fill_mode = 'FULL'

spline = curve.splines.new('BEZIER')
spline.bezier_points.add(3)  # total 4 points

coords = [
    (0.48, 0.00, 0.38),
    (0.98, 0.00, 0.32),
    (1.08, 0.00, 0.72),
    (0.48, 0.00, 0.82),
]

for point, co in zip(spline.bezier_points, coords):
    point.co = co
    point.handle_left_type = 'AUTO'
    point.handle_right_type = 'AUTO'

handle_curve_obj = bpy.data.objects.new("Mug_Handle_Curve_Object", curve)
bpy.context.collection.objects.link(handle_curve_obj)

select_only(handle_curve_obj)
bpy.ops.object.convert(target='MESH')
handle = bpy.context.object
handle.name = "LowPoly_Mug_Handle"
handle.data.materials.append(ceramic_mat)
set_flat_shading(handle)

# -------------------------
# Ground plane
# -------------------------
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, -0.01))
ground = bpy.context.object
ground.name = "Ground"
ground.data.materials.append(ground_mat)
set_flat_shading(ground)

# -------------------------
# Camera
# -------------------------
cam_data = bpy.data.cameras.new("Mug_Camera")
cam = bpy.data.objects.new("Mug_Camera_Object", cam_data)
bpy.context.collection.objects.link(cam)

cam.location = (2.8, -2.9, 1.8)
cam_data.lens = 50
aim_at(cam, (0, 0, 0.62))
scene.camera = cam

# -------------------------
# Lights
# -------------------------
key_data = bpy.data.lights.new("Key_Light", type='AREA')
key_data.energy = 350
key_data.size = 3.0
key = bpy.data.objects.new("Key_Light_Object", key_data)
bpy.context.collection.objects.link(key)
key.location = (2.5, -2.0, 3.0)
aim_at(key, (0, 0, 0.6))

fill_data = bpy.data.lights.new("Fill_Light", type='AREA')
fill_data.energy = 120
fill_data.size = 2.5
fill = bpy.data.objects.new("Fill_Light_Object", fill_data)
bpy.context.collection.objects.link(fill)
fill.location = (-2.0, 1.5, 1.5)
aim_at(fill, (0, 0, 0.6))

# -------------------------
# Render settings
# -------------------------
scene.world.color = (0.38, 0.42, 0.46)
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = PNG_PATH
scene.render.film_transparent = False

try:
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
except Exception:
    pass

engine = set_render_engine(scene)

if engine == "CYCLES":
    scene.cycles.samples = 64
else:
    try:
        scene.eevee_next.taa_render_samples = 64
    except Exception:
        pass
    try:
        scene.eevee.taa_render_samples = 64
    except Exception:
        pass

# -------------------------
# First render
# -------------------------
bpy.ops.render.render(write_still=True)
print(f"Render saved to: {PNG_PATH}")

# -------------------------
# Automated inspection + fix/rerender if needed
# -------------------------
mean, stddev, ratio = inspect_render(PNG_PATH)
print(f"Initial inspection: mean_luma={mean:.3f}, stddev={stddev:.3f}, non_bright_ratio={ratio:.2f}")

if (mean < 0.08 or stddev < 0.02) or (mean > 0.97 and stddev < 0.02):
    print("Render looked blank/dark/overexposed; adjusting lights and rerendering.")

    if mean > 0.97:
        key_data.energy *= 0.45
        fill_data.energy *= 0.45
        scene.world.color = (0.18, 0.20, 0.22)
    else:
        key_data.energy *= 2.2
        fill_data.energy *= 2.2
        scene.world.color = (0.55, 0.58, 0.62)

    bpy.ops.render.render(write_still=True)
    mean, stddev, ratio = inspect_render(PNG_PATH)
    print(f"Second inspection: mean_luma={mean:.3f}, stddev={stddev:.3f}, non_bright_ratio={ratio:.2f}")
else:
    print("Automated inspection passed: render is nonblank with visible contrast.")

# -------------------------
# Save Blender file
# -------------------------
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
print(f"Blender file saved to: {BLEND_PATH}")
