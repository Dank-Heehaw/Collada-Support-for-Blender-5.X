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
    "name": "Blender Collada Support",
    "author": "Tim Knip, Dusan Maliarik, Lawrence D'Oliveiro, Kims Ferdy, Blender Collade Support",
    "version": (1, 0, 5),
    "blender": (5, 0, 0),
    "location": "File > Import, File > Export",
    "description": "Import and export COLLADA (.dae / .zae) after native support was removed in Blender 5",
    "category": "Import-Export",
    "doc_url": "https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X",
}

import importlib
import os
import site
import subprocess
import sys

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    StringProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Detect add-on reload (Blender keeps module dicts around).
_ADDON_RELOAD = "HAS_COLLADA" in globals()


def _modules_path():
    paths = bpy.utils.script_paths(subdir="modules")
    if paths:
        return paths[0]
    return os.path.join(bpy.utils.resource_path("USER"), "scripts", "modules")


def _ensure_modules_path():
    path = _modules_path()
    os.makedirs(path, exist_ok=True)
    if path not in sys.path:
        # Keep Blender Extension wheel paths ahead of this legacy fallback.
        sys.path.append(path)
    site.addsitedir(path)
    return path


_ensure_modules_path()

def _refresh_collada_status():
    global HAS_COLLADA
    try:
        import collada  # noqa: F401

        HAS_COLLADA = True
    except ImportError:
        HAS_COLLADA = False
    return HAS_COLLADA


HAS_COLLADA = False
_refresh_collada_status()

# Reload I/O modules only when pycollada is available (they import it at top level).
if _ADDON_RELOAD and HAS_COLLADA:
    from . import export_collada, import_collada

    importlib.reload(import_collada)
    importlib.reload(export_collada)


class COLLADA_OT_install_pycollada(bpy.types.Operator):
    """Update or reinstall pycollada in Blender's user modules folder"""

    bl_idname = "collada_support.install_pycollada"
    bl_label = "Update / Reinstall pycollada"
    bl_options = {"REGISTER"}

    def execute(self, context):
        modules_path = _ensure_modules_path()
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--target",
            modules_path,
            "pycollada",
        ]
        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            self.report({"ERROR"}, f"Failed to run pip: {exc}")
            return {"CANCELLED"}

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            self.report(
                {"ERROR"},
                f"pip install failed ({completed.returncode}). {detail[-400:]}",
            )
            return {"CANCELLED"}

        # Drop cached failed imports so the next check can succeed.
        for key in list(sys.modules):
            if key == "collada" or key.startswith("collada."):
                del sys.modules[key]

        if not _refresh_collada_status():
            self.report(
                {"ERROR"},
                "pycollada installed but still not importable. Restart Blender.",
            )
            return {"CANCELLED"}

        self.report({"INFO"}, f"pycollada updated/reinstalled in {modules_path}")
        return {"FINISHED"}


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

    def execute(self, context):
        if not _refresh_collada_status():
            self.report(
                {"ERROR"},
                "Bundled pycollada failed to load. Open Preferences > Add-ons > "
                "Blender Collada Support and use Update / Reinstall pycollada.",
            )
            return {"CANCELLED"}

        from . import import_collada

        kwargs = self.as_keywords(ignore=("filter_glob", "files"))
        if not os.path.isfile(kwargs["filepath"]):
            self.report({"ERROR"}, f"Not a file: {kwargs['filepath']}")
            return {"CANCELLED"}
        lower = self.filepath.lower()
        is_archive = lower.endswith((".zae", ".kmz", ".zip"))
        return import_collada.load(self, context, is_archive, **kwargs)


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
            self.report(
                {"ERROR"},
                "Bundled pycollada failed to load. Open Preferences > Add-ons > "
                "Blender Collada Support and use Update / Reinstall pycollada.",
            )
            return {"CANCELLED"}

        from . import export_collada

        kwargs = self.as_keywords(ignore=("filter_glob",))
        if os.path.exists(self.filepath) and not os.path.isfile(self.filepath):
            self.report({"ERROR"}, f"Not a file: {kwargs['filepath']}")
            return {"CANCELLED"}
        return export_collada.save(self, context, **kwargs)


class ColladaSupportPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        modules_path = _ensure_modules_path()

        box = layout.box()
        box.label(text="Python modules path", icon="FILE_FOLDER")
        box.label(text=modules_path)

        if not HAS_COLLADA:
            layout.label(text="Bundled pycollada failed to load.", icon="ERROR")
            layout.operator(
                COLLADA_OT_install_pycollada.bl_idname,
                text="Update / Reinstall pycollada",
                icon="FILE_REFRESH",
            )
            tip = layout.box()
            tip.label(text="This optional network fallback replaces the bundled copy.")
            tip.label(text="Restart Blender after updating or reinstalling.")
        else:
            import collada

            version = getattr(collada, "__version__", "unknown")
            layout.label(text=f"pycollada ready (version {version})", icon="CHECKMARK")
            layout.label(text="Bundled wheels are active; network update is optional.")
            layout.operator(
                COLLADA_OT_install_pycollada.bl_idname,
                text="Update / Reinstall pycollada",
                icon="FILE_REFRESH",
            )


classes = (
    COLLADA_OT_install_pycollada,
    IMPORT_OT_collada,
    EXPORT_OT_collada,
    ColladaSupportPreferences,
)


def menu_func_import(self, context):
    label = (
        "COLLADA (.dae, .zae, .kmz, .zip)"
        if HAS_COLLADA
        else "COLLADA (.dae) [bundled pycollada failed]"
    )
    self.layout.operator(IMPORT_OT_collada.bl_idname, text=label)


def menu_func_export(self, context):
    label = (
        "COLLADA (.dae, .zae)"
        if HAS_COLLADA
        else "COLLADA (.dae) [bundled pycollada failed]"
    )
    self.layout.operator(EXPORT_OT_collada.bl_idname, text=label)


def register():
    _ensure_modules_path()
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
