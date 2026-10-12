"""Build (and optionally render) a Blender scene of Idira with swappable texture sets.

Headless:  blender -b -P blender_scene.py -- --out data/atlas_upscale/blender/idira.blend
           blender -b -P blender_scene.py -- --render out.png --diffuse idira_topaz_recover --normal idira_n_esrgan --view face
Interactive: open the .blend, press N in the 3D view, "Idira" tab: pick a diffuse set and a normal set, images reload in place.
(In the .blend the script is saved as a text block and re-registers on load: Text > Run Script once if the panel is missing.)

Diffuse sets are folders of <part>_d.png under data/atlas_upscale (idira_orig, idira_topaz_recover, ...). Normal sets are folders of
DXT5nm <part>_n.png (X in alpha, Y in green); they are converted to ordinary tangent-space RGB normals once, into blender/normals_cache.
"""
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2] if "__file__" in globals() and Path(__file__).exists() else Path(bpy.path.abspath("//")).resolve().parents[2]
DATA = ROOT / "data" / "atlas_upscale"
MESHES = DATA / "blender" / "meshes"
CACHE = DATA / "blender" / "normals_cache"
NORMAL_FOLDERS = ["idira_orig_nm", "idira_n_esrgan", "idira_n_sharp"]
PART_TEXTURE = {  # mesh name -> texture stem
    "HD_Head02Idira_F_HM": "HD_Head02Idira", "HB_Head02Idira_F_HM": "HD_Head02Idira", "EA_Ears02Idira_F_HM": "HD_Head02Idira",
    "HH_Hair02Idira_F_HM": "HH_HairIdira", "BT_Idira_F_HM": "BT_Idira", "CF_Idira_F_HM": "CF_Idira", "CL_Idira_F_HM": "CL_Idira",
    "LL_Idira_F_HM": "LL_Idira", "TS_Idira_F_HM": "TS_Idira", "UA_Idira_F_HM": "UA_Idira",
}
FLIP_V = "--flipv" in sys.argv
ATLAS = 4096  # mesh UVs are in 4096 atlas space; (x, y, w, h) of each part's rect, y from the bottom (from the F9 log)
RECTS = {
    "HD_Head02Idira": (0, 3256, 1370, 840), "HH_HairIdira": (2930, 2126, 1166, 1020), "CF_Idira": (3380, 886, 716, 490),
    "CL_Idira": (2180, 100, 564, 288), "BT_Idira": (0, 1346, 1370, 760), "TS_Idira": (1370, 3256, 1560, 840),
    "UA_Idira": (0, 2736, 1370, 520), "LL_Idira": (2930, 3146, 1166, 456),
}
PAIR = "--pair" in sys.argv
PAIR_SPACING = 0.34
SKIP_MESHES = {"CF_Idira_M_HM"} | ({"HB_Head02Idira_F_HM"} if "--nohb" in sys.argv else set())
VIEWS = {
    "pairbody": ((0.0, -1.5, 1.2), (0.0, 0.0, 1.15)), "pairlegs": ((0.0, -2.0, 0.7), (0.0, 0.0, 0.7)),
    "pairface": ((0.0, -0.95, 1.575), (0.0, 0.0, 1.565)), "pairmouth": ((0.0, -0.62, 1.54), (0.0, 0.0, 1.54)),
    "mouth": ((0.0, -0.32, 1.535), (0.0, 0.0, 1.535)),"face": ((0.0, -0.55, 1.58), (0.0, 0.0, 1.57)), "body": ((0.0, -2.6, 1.1), (0.0, 0.0, 1.05)), "torso": ((0.0, -0.9, 1.2), (0.0, 0.0, 1.15))}


def diffuse_sets():
    return sorted(p.name for p in DATA.glob("idira_*") if p.is_dir() and any(p.glob("*_d.png")))


def normal_sets():
    return [n for n in NORMAL_FOLDERS if (DATA / n).is_dir()]


def converted_normal(folder, stem):
    """DXT5nm -> RGB tangent-space normal PNG, cached. Returns a path or None."""
    src = DATA / folder / f"{stem}_n.png"
    if not src.exists():
        return None
    dst = CACHE / folder / f"{stem}_n.png"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        img = bpy.data.images.load(str(src), check_existing=False)
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        x, y = px[:, 3] * 2 - 1, px[:, 1] * 2 - 1
        z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
        px[:, 0], px[:, 1], px[:, 2], px[:, 3] = x * 0.5 + 0.5, y * 0.5 + 0.5, z * 0.5 + 0.5, 1.0
        bpy.data.images.remove(img)
        out = bpy.data.images.new("normal_convert", w, h, alpha=False, float_buffer=False)
        out.colorspace_settings.name = "Non-Color"
        out.pixels.foreach_set(px.ravel())
        dst.parent.mkdir(parents=True, exist_ok=True)
        out.filepath_raw = str(dst)
        out.file_format = "PNG"
        out.save()
        bpy.data.images.remove(out)
    return dst


def load_image(path, colorspace):
    """One image datablock per file path (set folders reuse file names)."""
    key = f"{path.parent.name}/{path.name}|{colorspace}"
    image = bpy.data.images.get(key)
    if image is None:
        image = bpy.data.images.load(str(path), check_existing=False)
        image.name = key
    else:
        image.filepath = str(path)
        image.reload()
    image.colorspace_settings.name = colorspace
    return image


def apply_sets(diffuse, normal, diffuse_b=None):
    for material in bpy.data.materials:
        stem = material.get("idira_stem")
        if not stem:
            continue
        diffuse_for = diffuse_b if (material.get("idira_slot") == 1 and diffuse_b) else diffuse
        d = DATA / diffuse_for / f"{stem}_d.png"
        d = d if d.exists() else DATA / "idira_orig" / f"{stem}_d.png"
        material.node_tree.nodes["diffuse"].image = load_image(d, "sRGB")
        n = converted_normal(normal, stem) if normal != "none" else None
        node = material.node_tree.nodes["normal_tex"]
        node.image = load_image(n, "Non-Color") if n else None
        material.node_tree.links.clear() if False else None
        material.node_tree.nodes["normal_map"].inputs["Strength"].default_value = 1.0 if n else 0.0


def make_material(mesh_name, stem, slot):
    material = bpy.data.materials.new(f"{mesh_name}_{slot}")
    material.use_nodes = True
    material["idira_stem"] = stem
    material["idira_slot"] = slot
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.6
    diffuse = nodes.new("ShaderNodeTexImage"); diffuse.name = "diffuse"
    normal_tex = nodes.new("ShaderNodeTexImage"); normal_tex.name = "normal_tex"
    normal_map = nodes.new("ShaderNodeNormalMap"); normal_map.name = "normal_map"
    coords = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping"); mapping.name = "uv_flip"
    mapping.inputs["Scale"].default_value[1] = -1 if FLIP_V else 1
    mapping.inputs["Location"].default_value[1] = 1 if FLIP_V else 0
    links.new(coords.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], diffuse.inputs["Vector"])
    links.new(mapping.outputs["Vector"], normal_tex.inputs["Vector"])
    links.new(diffuse.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return material


def remap_uvs(obj, rect):
    """Atlas-space UVs -> 0..1 over the part's own texture."""
    x, y, w, h = rect
    layer = obj.data.uv_layers.active
    uv = np.empty(len(layer.data) * 2, dtype=np.float32)
    layer.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    uv[:, 0] = (uv[:, 0] * ATLAS - x) / w
    uv[:, 1] = (uv[:, 1] * ATLAS - y) / h
    layer.data.foreach_set("uv", uv.ravel())


def build():
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    else:  # keep the UI, just empty the scene
        for datablocks in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
            for item in list(datablocks):
                datablocks.remove(item)
    for slot in range(2 if PAIR else 1):
        for obj_path in sorted(MESHES.glob("*.obj")):
            name = obj_path.stem
            if name in SKIP_MESHES or name not in PART_TEXTURE:
                continue
            bpy.ops.wm.obj_import(filepath=str(obj_path))
            obj = bpy.context.selected_objects[0]
            obj.name = f"{name}_{slot}"
            obj.data.materials.append(make_material(name, PART_TEXTURE[name], slot))
            remap_uvs(obj, RECTS[PART_TEXTURE[name]])
            if PAIR:
                obj.location.x = (slot - 0.5) * PAIR_SPACING
            for poly in obj.data.polygons:
                poly.use_smooth = True
    sun = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    sun.data.energy, sun.data.size = 80, 1.5
    sun.location = (0.6, -1.2, 1.9)
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy, fill.data.size = 25, 2
    fill.location = (-1.0, -1.0, 1.4)
    for light in (sun, fill):
        bpy.context.scene.collection.objects.link(light)
        constraint = light.constraints.new("TRACK_TO"); constraint.target = None
        light.rotation_euler = (1.45, 0, 0.5 if light is sun else -0.7)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    world = bpy.data.worlds.new("w"); world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.05, 1)
    bpy.context.scene.world = world
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
    sc.idira_diffuse = "idira_orig"; sc.idira_diffuse_b = "idira_topaz_recover"; sc.idira_normal = "idira_orig_nm"
    if PAIR:
        sc.render.resolution_x = 2400


def set_view(name):
    cam = bpy.context.scene.camera
    loc, target = VIEWS[name]
    cam.location = loc
    direction = np.array(target) - np.array(loc)
    import mathutils
    cam.rotation_euler = mathutils.Vector(direction).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 85 if name == "face" else 50


def on_change(self, context):
    apply_sets(context.scene.idira_diffuse, context.scene.idira_normal, context.scene.idira_diffuse_b)


class IDIRA_OT_reload(bpy.types.Operator):
    """Re-read every texture from disk (after changing a PNG) and refresh the set lists"""
    bl_idname, bl_label = "idira.reload", "Reload textures from disk"

    def execute(self, context):
        sc = context.scene
        apply_sets(sc.idira_diffuse, sc.idira_normal, sc.idira_diffuse_b if PAIR else None)
        return {"FINISHED"}


class IDIRA_PT_sets(bpy.types.Panel):
    bl_label, bl_idname, bl_space_type, bl_region_type, bl_category = "Texture sets", "IDIRA_PT_sets", "VIEW_3D", "UI", "Idira"

    def draw(self, context):
        self.layout.prop(context.scene, "idira_diffuse", text="Diffuse")
        if PAIR:
            self.layout.prop(context.scene, "idira_diffuse_b", text="Diffuse (right copy)")
        self.layout.prop(context.scene, "idira_normal", text="Normal")
        self.layout.operator("idira.reload")


def register():
    bpy.types.Scene.idira_diffuse = bpy.props.EnumProperty(items=lambda s, c: [(n, n, "") for n in diffuse_sets()], update=on_change)
    bpy.types.Scene.idira_diffuse_b = bpy.props.EnumProperty(items=lambda s, c: [(n, n, "") for n in diffuse_sets()], update=on_change)
    bpy.types.Scene.idira_normal = bpy.props.EnumProperty(items=lambda s, c: [(n, n, "") for n in normal_sets() + ["none"]], update=on_change)
    bpy.utils.register_class(IDIRA_OT_reload)
    bpy.utils.register_class(IDIRA_PT_sets)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = dict(zip(args[::2], args[1::2]))
    register()
    build()
    set_view(opt.get("--view", "face"))
    sc = bpy.context.scene
    if "--diffuse" in opt: sc.idira_diffuse = opt["--diffuse"]
    if "--diffuse-b" in opt: sc.idira_diffuse_b = opt["--diffuse-b"]
    if "--normal" in opt: sc.idira_normal = opt["--normal"]
    apply_sets(sc.idira_diffuse, sc.idira_normal, sc.idira_diffuse_b if PAIR else None)
    if "--out" in opt:
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(opt["--out"]).resolve()))
    if "--sets" in opt:  # one render per diffuse set: --render base.png --sets a,b,c -> base_a.png ...
        sc.render.engine = "CYCLES"; sc.cycles.samples = int(opt.get("--samples", 48)); sc.cycles.device = "CPU"
        base = Path(opt["--render"]).resolve()
        for name in opt["--sets"].split(","):
            sc.idira_diffuse = name
            apply_sets(name, sc.idira_normal)
            sc.render.filepath = str(base.with_name(f"{base.stem}_{name}{base.suffix}"))
            bpy.ops.render.render(write_still=True)
    elif "--render" in opt:
        sc.render.engine = "CYCLES"; sc.cycles.samples = int(opt.get("--samples", 48)); sc.cycles.device = "CPU"
        sc.render.filepath = str(Path(opt["--render"]).resolve())
        bpy.ops.render.render(write_still=True)


def show_in_window():
    """Interactive session: material preview, through the camera, then leave the user to orbit."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "MATERIAL"
                    space.region_3d.view_perspective = "CAMERA"


if __name__ == "__main__":
    if bpy.app.background:
        main()
    else:
        def start():
            main()
            show_in_window()
            return None
        bpy.app.timers.register(start, first_interval=1.5)
