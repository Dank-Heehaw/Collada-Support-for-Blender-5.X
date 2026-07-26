# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Based on blender-pycollada / B5Collada:
#   Tim Knip, Dusan Maliarik, Lawrence D'Oliveiro, Kims Ferdy
# Plus lessons from ekztal's Blender 5 DAE importer.

bl_info = {
    "name": "Collada Support",
    "author": "Waheed Khan, Collada Support for Blender 5.X",
    "version": (1, 3, 0),
    "blender": (5, 0, 0),
    "location": "File > Import, File > Export",
    "description": "Import and export COLLADA (.dae / .zae) after native support was removed in Blender 5",
    "category": "Import-Export",
    "doc_url": "https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X",
}

import importlib
import os

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    StringProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Detect add-on reload (Blender keeps module dicts around).
_ADDON_RELOAD = "HAS_COLLADA" in globals()


def _blender_python_site_packages():
    """Return Blender's bundled Python site-packages (working numpy), if present."""
    import sys

    candidates = []

    # Typical layout: <install_root>/<major.minor>/python/Lib/site-packages
    # binary_path is .../blender.exe (Steam and official zip installs).
    install_root = os.path.dirname(bpy.app.binary_path)
    version = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
    candidates.append(
        os.path.join(install_root, version, "python", "Lib", "site-packages")
    )

    # Also accept any python/Lib/site-packages already on sys.path.
    for path in sys.path:
        norm = path.replace("\\", "/").lower()
        if norm.endswith("/python/lib/site-packages"):
            candidates.append(path)

    for candidate in candidates:
        if candidate and os.path.isdir(os.path.join(candidate, "numpy")):
            return candidate
    return None


def _purge_numpy_modules():
    import sys

    for name in list(sys.modules):
        if name == "numpy" or name.startswith("numpy."):
            del sys.modules[name]


def _prefer_working_numpy():
    """
    Prefer Blender's bundled numpy over broken leftovers in scripts/modules.

    A partial pip install into scripts/modules can shadow Blender's numpy and
    break pycollada with errors like: No module named 'numpy.lib._twodim_base_impl'.
    """
    import sys

    site_packages = _blender_python_site_packages()
    if not site_packages:
        return

    # Drop any already-imported broken numpy before retrying.
    mod = sys.modules.get("numpy")
    if mod is not None:
        mod_file = (getattr(mod, "__file__", "") or "").replace("\\", "/")
        if "/scripts/modules/numpy" in mod_file:
            _purge_numpy_modules()

    if site_packages in sys.path:
        sys.path.remove(site_packages)
    sys.path.insert(0, site_packages)


def _collada_import_error():
    """Return ImportError from loading pycollada, or None on success."""
    import sys

    try:
        _prefer_working_numpy()
        import collada  # noqa: F401

        return None
    except ImportError as exc:
        # One retry after clearing a half-loaded numpy.
        try:
            _purge_numpy_modules()
            _prefer_working_numpy()
            import collada  # noqa: F401

            return None
        except ImportError as retry_exc:
            return retry_exc if retry_exc else exc


def _refresh_collada_status():
    global HAS_COLLADA, COLLADA_IMPORT_ERROR
    COLLADA_IMPORT_ERROR = _collada_import_error()
    HAS_COLLADA = COLLADA_IMPORT_ERROR is None
    return HAS_COLLADA


HAS_COLLADA = False
COLLADA_IMPORT_ERROR = None
_refresh_collada_status()

if _ADDON_RELOAD:
    # The Cabinet Vision profile reads COLLADA XML directly, so it reloads
    # (and works) whether or not pycollada is available.
    from . import import_cabinet_vision

    importlib.reload(import_cabinet_vision)

    # The general path imports pycollada at module level.
    if HAS_COLLADA:
        from . import export_collada, import_collada

        importlib.reload(import_collada)
        importlib.reload(export_collada)


class IMPORT_OT_collada(bpy.types.Operator, ImportHelper):
    """Import a COLLADA (.dae / .zae / .kmz / .zip) file"""

    bl_idname = "import_scene.collada"
    bl_label = "Import COLLADA"
    bl_options = {"UNDO"}

    filter_glob: StringProperty(
        default="*.dae;*.zae;*.kmz;*.zip",
        options={"HIDDEN"},
    )
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )
    directory: StringProperty(subtype="DIR_PATH")

    profile: EnumProperty(
        name="Profile",
        description="Which importer to use for this file",
        items=(
            (
                "GENERAL",
                "General",
                "General COLLADA import (SketchUp, exporters, DCC tools)",
            ),
            (
                "CABINET_VISION",
                "Cabinet Vision",
                "Cabinet Vision COLLADA export: library node instances, "
                "polygons with holes (bores/cutouts), joined panels and "
                "assembly collections",
            ),
        ),
        default="GENERAL",
    )

    recognize_blender_extensions: BoolProperty(
        name="Recognize Blender Extensions",
        description="Recognize extra info specific to Blender",
        default=True,
    )
    transformation: EnumProperty(
        name="Transformations",
        items=(
            (
                "PARENT",
                "Parenting",
                "Recreate COLLADA/SketchUp groups as parented Empties (matches Blender 4.5)",
            ),
            (
                "MUL",
                "Multiply",
                "Flatten hierarchy: apply node transforms as world matrices",
            ),
            ("APPLY", "Apply", "Bake transforms into mesh data"),
        ),
        default="PARENT",
    )

    cv_join_parts: BoolProperty(
        name="Join Parts",
        description=(
            "Merge each physical part's faces, edgebanding and boring/dado "
            "into a single selectable object"
        ),
        default=True,
    )
    cv_merge_by_distance: BoolProperty(
        name="Merge Vertices by Distance",
        description=(
            "After joining, weld the duplicate seam vertices left over from "
            "merging independently tessellated faces, edgebanding and boring"
        ),
        default=True,
    )
    cv_merge_distance: FloatProperty(
        name="Distance",
        description="Vertices closer together than this are welded",
        default=0.0001,
        min=0.0,
        precision=5,
        unit="LENGTH",
    )
    cv_clean_topology: BoolProperty(
        name="Clean Topology",
        description=(
            "Limited Dissolve plus Tris to Quads on each joined object. Off by "
            "default: it changes how many faces bound a bore hole (though it "
            "never moves a vertex), which matters when something downstream "
            "depends on Cabinet Vision's exact triangulation"
        ),
        default=False,
    )
    cv_fix_hidden_dados: BoolProperty(
        name="Fix Hidden Dado/Notch Faces",
        description=(
            "Cabinet Vision sometimes exports a panel's dado/notch pocket "
            "correctly but leaves the panel's own flat face uncut over it, "
            "hiding the pocket behind solid material. Find that pattern and "
            "cut the covering portion away. Off by default since it deletes "
            "geometry"
        ),
        default=False,
    )
    cv_hide_feature_parts: BoolProperty(
        name="Hide Dado/Notch Feature Geometry",
        description=(
            "Route DADO/NOTCH feature geometry (e.g. 'UBDADO') to a hidden "
            "'CV Hidden Features' collection instead of fusing it into the "
            "panel's merged mesh, since it is typically redundant duplicate "
            "geometry. BORE (boring/drilling) geometry always stays merged and "
            "visible. Turn off when a pocket only exists under one of these "
            "feature nodes and you rely on Fix Hidden Dado/Notch Faces"
        ),
        default=True,
    )
    cv_flip_uv_v: BoolProperty(
        name="Flip UV (V Axis)",
        description="Enable when textures appear upside-down",
        default=False,
    )
    cv_mark_hard_edges: BoolProperty(
        name="Mark Hard Edges as Seams",
        description=(
            "Mark every edge where two adjacent faces meet at more than about "
            "40 degrees as a UV seam, so a later unwrap has sensible cut lines "
            "without hand-marking every part. Only sets seam flags"
        ),
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "profile")
        layout.separator()
        if self.profile == "CABINET_VISION":
            layout.prop(self, "cv_join_parts")
            layout.prop(self, "cv_merge_by_distance")
            row = layout.row()
            row.enabled = self.cv_merge_by_distance
            row.prop(self, "cv_merge_distance")
            layout.prop(self, "cv_hide_feature_parts")
            layout.prop(self, "cv_fix_hidden_dados")
            layout.prop(self, "cv_clean_topology")
            layout.prop(self, "cv_mark_hard_edges")
            layout.prop(self, "cv_flip_uv_v")
        else:
            layout.prop(self, "transformation")
            layout.prop(self, "recognize_blender_extensions")

    def execute(self, context):
        if not os.path.isfile(self.filepath):
            self.report({"ERROR"}, f"Not a file: {self.filepath}")
            return {"CANCELLED"}
        is_archive = self.filepath.lower().endswith((".zae", ".kmz", ".zip"))

        if self.profile == "CABINET_VISION":
            # The Cabinet Vision profile parses the COLLADA XML itself, so it
            # does not need pycollada.
            from . import import_cabinet_vision

            return import_cabinet_vision.load(
                self,
                context,
                is_archive,
                self.filepath,
                join_parts=self.cv_join_parts,
                merge_by_distance=self.cv_merge_by_distance,
                merge_distance=self.cv_merge_distance,
                clean_topology=self.cv_clean_topology,
                fix_hidden_dados=self.cv_fix_hidden_dados,
                hide_feature_parts=self.cv_hide_feature_parts,
                flip_uv_v=self.cv_flip_uv_v,
                mark_hard_edges=self.cv_mark_hard_edges,
            )

        if not _refresh_collada_status():
            detail = COLLADA_IMPORT_ERROR or "unknown import error"
            self.report({"ERROR"}, f"pycollada is not available: {detail}")
            return {"CANCELLED"}

        from . import import_collada

        return import_collada.load(
            self,
            context,
            is_archive,
            self.filepath,
            recognize_blender_extensions=self.recognize_blender_extensions,
            transformation=self.transformation,
        )


class EXPORT_OT_collada(bpy.types.Operator, ExportHelper):
    """Export the scene as COLLADA (.dae / .zae)"""

    bl_idname = "export_scene.collada"
    bl_label = "Export COLLADA"
    bl_options = {"UNDO"}

    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH")

    collada_version: EnumProperty(
        name="Collada Version",
        description="Version number written into the COLLADA file",
        items=(
            ("1.4.1", "1.4.1", ""),
            ("1.5.0", "1.5.0", ""),
        ),
        default="1.4.1",
    )
    add_blender_extensions: BoolProperty(
        name="Add Blender Extensions",
        description="Include extra info specific to Blender",
        default=True,
    )
    export_as: EnumProperty(
        name="Export as",
        items=(
            ("dae", "DAE", "Separate COLLADA XML file"),
            ("zae", "ZAE", "Zip archive containing the scene and textures"),
        ),
        default="dae",
    )
    export_textures: BoolProperty(
        name="Export Textures",
        description="Write texture image files next to the DAE (or into the ZAE)",
        default=False,
    )
    up_axis: EnumProperty(
        name="Up",
        items=(
            ("X_UP", "X Up", ""),
            ("Y_UP", "Y Up", ""),
            ("Z_UP", "Z Up", ""),
        ),
        default="Z_UP",
    )
    use_selection: BoolProperty(
        name="Selection Only",
        description="Export selected objects only",
        default=False,
    )

    def check(self, context):
        out_ext = ".zae" if self.export_as == "zae" else ".dae"
        if not self.filepath.endswith(out_ext):
            self.filepath = os.path.splitext(self.filepath)[0] + out_ext
            self.export_textures = self.export_as == "zae"
            return True
        return False

    def execute(self, context):
        if not _refresh_collada_status():
            detail = COLLADA_IMPORT_ERROR or "unknown import error"
            self.report({"ERROR"}, f"pycollada is not available: {detail}")
            return {"CANCELLED"}

        from . import export_collada

        kwargs = self.as_keywords(ignore=("filter_glob",))
        if os.path.exists(self.filepath) and not os.path.isfile(self.filepath):
            self.report({"ERROR"}, f"Not a file: {kwargs['filepath']}")
            return {"CANCELLED"}
        try:
            return export_collada.save(self, context, **kwargs)
        except Exception as exc:
            self.report({"ERROR"}, f"COLLADA export failed: {exc}")
            return {"CANCELLED"}


classes = (
    IMPORT_OT_collada,
    EXPORT_OT_collada,
)


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_collada.bl_idname,
        text="COLLADA (.dae, .zae, .kmz, .zip)",
    )


def menu_func_export(self, context):
    self.layout.operator(
        EXPORT_OT_collada.bl_idname,
        text="COLLADA (.dae, .zae)",
    )


def register():
    _refresh_collada_status()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
