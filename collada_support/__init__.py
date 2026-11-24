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
    "version": (2, 0, 3),
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
    IntProperty,
    StringProperty,
)
from bpy_extras.io_utils import ExportHelper, ImportHelper

# Detect add-on reload (Blender keeps module dicts around).
_ADDON_RELOAD = "HAS_COLLADA" in globals()


def _collada_import_error():
    """Return ImportError from loading pycollada, or None on success."""
    try:
        import collada  # noqa: F401

        return None
    except ImportError as exc:
        return exc


def _refresh_collada_status():
    global HAS_COLLADA, COLLADA_IMPORT_ERROR
    COLLADA_IMPORT_ERROR = _collada_import_error()
    HAS_COLLADA = COLLADA_IMPORT_ERROR is None
    return HAS_COLLADA


HAS_COLLADA = False
COLLADA_IMPORT_ERROR = None
_refresh_collada_status()


def _operator_panel(layout, idname, title, default_closed=False):
    """Collapsible File Browser section (FBX/glTF style). Falls back to a box."""
    panel = getattr(layout, "panel", None)
    if callable(panel):
        header, body = panel(idname, default_closed=default_closed)
        if header is not None:
            header.label(text=title)
        return body
    box = layout.box()
    box.label(text=title)
    return box

# Reload I/O modules only when pycollada is available (they import it at top level).
if _ADDON_RELOAD and HAS_COLLADA:
    from . import export_collada, import_collada

    importlib.reload(import_collada)
    importlib.reload(export_collada)


class IMPORT_OT_collada(bpy.types.Operator, ImportHelper):
    """Import a COLLADA (.dae / .zae / .kmz / .zip) file"""

    bl_idname = "import_scene.collada"
    bl_label = "Import COLLADA"
    bl_options = {"UNDO", "PRESET"}

    filter_glob: StringProperty(
        default="*.dae;*.zae;*.kmz;*.zip",
        options={"HIDDEN"},
    )
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )
    directory: StringProperty(subtype="DIR_PATH")

    # Native WM_OT_collada_import names/defaults, plus this add-on's hierarchy mode.
    import_units: BoolProperty(
        name="Import Units",
        description=(
            "If disabled match import to Blender's current Unit settings, "
            "otherwise use the settings from the Imported scene"
        ),
        default=False,
    )
    custom_normals: BoolProperty(
        name="Custom Normals",
        description="Import custom normals, if available (otherwise Blender will compute them)",
        default=True,
    )
    fix_orientation: BoolProperty(
        name="Fix Leaf Bones",
        description="Fix Orientation of Leaf Bones (Collada does only support Joints)",
        default=False,
    )
    find_chains: BoolProperty(
        name="Find Bone Chains",
        description="Find best matching Bone Chains and ensure bones in chain are connected",
        default=False,
    )
    auto_connect: BoolProperty(
        name="Auto Connect",
        description="Set use_connect for parent bones which have exactly one child bone",
        default=False,
    )
    min_chain_length: IntProperty(
        name="Minimum Chain Length",
        description="When searching Bone Chains disregard chains of length below this value",
        default=0,
        min=0,
    )
    keep_bind_info: BoolProperty(
        name="Keep Bind Info",
        description=(
            "Store Bindpose information in custom bone properties for later use "
            "during Collada export"
        ),
        default=False,
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

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        data = _operator_panel(layout, "COLLADA_import_data", "Include")
        if data:
            data.prop(self, "import_units")
            data.prop(self, "custom_normals")
            data.prop(self, "transformation")
            data.prop(self, "recognize_blender_extensions")

        arm = _operator_panel(layout, "COLLADA_import_armature", "Armature")
        if arm:
            arm.prop(self, "fix_orientation")
            arm.prop(self, "find_chains")
            arm.prop(self, "auto_connect")
            arm.prop(self, "min_chain_length")
            arm.prop(self, "keep_bind_info")

    def execute(self, context):
        if not _refresh_collada_status():
            detail = COLLADA_IMPORT_ERROR or "unknown import error"
            self.report({"ERROR"}, f"pycollada is not available: {detail}")
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
    bl_options = {"UNDO", "PRESET"}

    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})
    directory: StringProperty(subtype="DIR_PATH")

    # Property names/defaults match WM_OT_collada_export in Blender 4.5 io_collada.cc.
    # Kept hidden so old operator presets still load; UI uses collapsible panels.
    prop_bc_export_ui_section: EnumProperty(
        name="Export Section",
        description="Unused; export options use collapsible panels instead of tabs",
        items=(
            ("main", "Main", "Data export section"),
            ("geometry", "Geom", "Geometry export section"),
            ("armature", "Arm", "Armature export section"),
            ("animation", "Anim", "Animation export section"),
            ("collada", "Extra", "Collada export section"),
        ),
        default="main",
        options={"HIDDEN"},
    )
    selected: BoolProperty(
        name="Selection Only",
        description="Export only selected elements",
        default=False,
    )
    include_children: BoolProperty(
        name="Include Children",
        description="Export all children of selected objects (even if not selected)",
        default=False,
    )
    include_armatures: BoolProperty(
        name="Include Armatures",
        description="Export related armatures (even if not selected)",
        default=False,
    )
    include_shapekeys: BoolProperty(
        name="Include Shape Keys",
        description="Export all Shape Keys from Mesh Objects",
        default=False,
    )
    apply_global_orientation: BoolProperty(
        name="Apply Global Orientation",
        description=(
            "Rotate all root objects to match the global orientation settings "
            "otherwise set the global orientation per Collada asset"
        ),
        default=False,
    )
    export_global_forward_selection: EnumProperty(
        name="Global Forward Axis",
        description="Global Forward axis for export",
        items=(
            ("X", "X", "Global Forward is positive X Axis"),
            ("Y", "Y", "Global Forward is positive Y Axis"),
            ("Z", "Z", "Global Forward is positive Z Axis"),
            ("-X", "-X", "Global Forward is negative X Axis"),
            ("-Y", "-Y", "Global Forward is negative Y Axis"),
            ("-Z", "-Z", "Global Forward is negative Z Axis"),
        ),
        default="Y",
    )
    export_global_up_selection: EnumProperty(
        name="Global Up Axis",
        description="Global Up axis for export",
        items=(
            ("X", "X", "Global UP is positive X Axis"),
            ("Y", "Y", "Global UP is positive Y Axis"),
            ("Z", "Z", "Global UP is positive Z Axis"),
            ("-X", "-X", "Global UP is negative X Axis"),
            ("-Y", "-Y", "Global UP is negative Y Axis"),
            ("-Z", "-Z", "Global UP is negative Z Axis"),
        ),
        default="Z",
    )
    use_texture_copies: BoolProperty(
        name="Copy",
        description="Copy textures to same folder where the .dae file is exported",
        default=True,
    )
    active_uv_only: BoolProperty(
        name="Only Selected UV Map",
        description="Export only the selected UV Map",
        default=False,
    )
    triangulate: BoolProperty(
        name="Triangulate",
        description="Export polygons (quads and n-gons) as triangles",
        default=True,
    )
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers to exported mesh (non destructive)",
        default=False,
    )
    export_mesh_type_selection: EnumProperty(
        name="Resolution",
        description="Modifier resolution for export",
        items=(
            ("view", "Viewport", "Apply modifier's viewport settings"),
            ("render", "Render", "Apply modifier's render settings"),
        ),
        default="view",
    )
    export_object_transformation_type_selection: EnumProperty(
        name="Transform",
        description="Object Transformation type for translation, scale and rotation",
        items=(
            ("matrix", "Matrix", "Use <matrix> representation for exported transformations"),
            (
                "decomposed",
                "Decomposed",
                "Use <rotate>, <translate> and <scale> representation for exported transformations",
            ),
        ),
        default="matrix",
    )
    use_object_instantiation: BoolProperty(
        name="Use Object Instances",
        description="Instantiate multiple Objects from same Data",
        default=True,
    )
    use_blender_profile: BoolProperty(
        name="Use Blender Profile",
        description=(
            "Export additional Blender specific information (for material, shaders, bones, etc.)"
        ),
        default=True,
    )
    sort_by_name: BoolProperty(
        name="Sort by Object name",
        description="Sort exported data by Object name",
        default=False,
    )
    limit_precision: BoolProperty(
        name="Limit Precision",
        description="Reduce the precision of the exported data to 6 digits",
        default=False,
    )
    deform_bones_only: BoolProperty(
        name="Deform Bones Only",
        description="Only export deforming bones with armatures",
        default=False,
    )
    open_sim: BoolProperty(
        name="Export to SL/OpenSim",
        description=(
            "Compatibility mode for Second Life, OpenSimulator and other compatible online worlds"
        ),
        default=False,
    )
    include_animations: BoolProperty(
        name="Include Animations",
        description=(
            "Export animations if available (exporting animations will enforce the decomposition "
            "of node transforms into <translation> <rotation> and <scale> components)"
        ),
        default=True,
    )
    export_animation_type_selection: EnumProperty(
        name="Key Type",
        description="Type for exported animations (use sample keys or Curve keys)",
        items=(
            ("sample", "Samples", "Export Sampled points guided by sampling rate"),
            ("keys", "Curves", "Export Curves (note: guided by curve keys)"),
        ),
        default="sample",
    )
    export_animation_transformation_type_selection: EnumProperty(
        name="Transform",
        description=(
            "Transformation type for translation, scale and rotation. "
            "Note: The Animation transformation type is always equal to the "
            "Object transformation type in Geometry"
        ),
        items=(
            ("matrix", "Matrix", "Use <matrix> representation for exported transformations"),
            (
                "decomposed",
                "Decomposed",
                "Use <rotate>, <translate> and <scale> representation for exported transformations",
            ),
        ),
        default="matrix",
    )
    sampling_rate: IntProperty(
        name="Sampling Rate",
        description="The distance between 2 keyframes (1 to key every frame)",
        default=1,
        min=1,
    )
    keep_smooth_curves: BoolProperty(
        name="Keep Smooth curves",
        description="Export also the curve handles (if available)",
        default=False,
    )
    keep_keyframes: BoolProperty(
        name="Keep Keyframes",
        description="Use existing keyframes as additional sample points",
        default=False,
    )
    keep_flat_curves: BoolProperty(
        name="All Keyed Curves",
        description="Export also curves which have only one key or are totally flat",
        default=False,
    )
    include_all_actions: BoolProperty(
        name="Include all Actions",
        description="Export also unassigned actions (this allows you to export entire animation libraries)",
        default=True,
    )
    keep_bind_info: BoolProperty(
        name="Keep Bind Info",
        description=(
            "Store Bindpose information in custom bone properties for later use during Collada export"
        ),
        default=False,
    )
    # Add-on extras beyond the 4.5 operator (ZAE packaging / schema version).
    collada_version: EnumProperty(
        name="Collada Version",
        description="Version number written into the COLLADA file",
        items=(
            ("1.4.1", "1.4.1", ""),
            ("1.5.0", "1.5.0", ""),
        ),
        default="1.4.1",
    )
    export_as: EnumProperty(
        name="Export as",
        items=(
            ("dae", "DAE", "Separate COLLADA XML file"),
            ("zae", "ZAE", "Zip archive containing the scene and textures"),
        ),
        default="dae",
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        include = _operator_panel(layout, "COLLADA_export_include", "Include")
        if include:
            col = include.column(heading="Limit to", align=True)
            col.prop(self, "selected")
            sub = col.column(align=True)
            sub.enabled = self.selected
            sub.prop(self, "include_children")
            sub.prop(self, "include_armatures")
            include.prop(self, "include_shapekeys")

        transform = _operator_panel(layout, "COLLADA_export_transform", "Transform")
        if transform:
            transform.prop(self, "apply_global_orientation")
            transform.prop(self, "export_global_forward_selection")
            transform.prop(self, "export_global_up_selection")
            transform.prop(self, "export_object_transformation_type_selection")

        geom = _operator_panel(layout, "COLLADA_export_geometry", "Geometry")
        if geom:
            geom.prop(self, "triangulate")
            row = geom.row(heading="Modifiers", align=True)
            row.prop(self, "apply_modifiers", text="")
            sub = row.row(align=True)
            sub.enabled = self.apply_modifiers
            sub.prop(self, "export_mesh_type_selection", text="")
            geom.prop(self, "use_object_instantiation")

        arm = _operator_panel(
            layout, "COLLADA_export_armature", "Armature", default_closed=True
        )
        if arm:
            arm.prop(self, "deform_bones_only")

        anim = _operator_panel(
            layout, "COLLADA_export_animation", "Animation", default_closed=True
        )
        if anim:
            anim.prop(self, "include_animations")
            col = anim.column(align=True)
            col.enabled = self.include_animations
            col.prop(self, "export_animation_type_selection", expand=True)
            col.prop(self, "export_animation_transformation_type_selection")
            sub = col.column(align=True)
            sub.enabled = (
                self.include_animations
                and self.export_animation_type_selection == "sample"
            )
            sub.prop(self, "sampling_rate")
            sub.prop(self, "keep_keyframes")
            col.prop(self, "keep_flat_curves")
            col.prop(self, "include_all_actions")
            col.prop(self, "keep_smooth_curves")

        extra = _operator_panel(layout, "COLLADA_export_extra", "Extra")
        if extra:
            extra.prop(self, "use_texture_copies")
            extra.prop(self, "active_uv_only")
            extra.prop(self, "use_blender_profile")
            extra.prop(self, "open_sim")
            extra.prop(self, "sort_by_name")
            extra.prop(self, "keep_bind_info")
            extra.prop(self, "limit_precision")
            extra.prop(self, "collada_version")
            extra.prop(self, "export_as")

    def check(self, context):
        out_ext = ".zae" if self.export_as == "zae" else ".dae"
        changed = False
        if not self.filepath.endswith(out_ext):
            self.filepath = os.path.splitext(self.filepath)[0] + out_ext
            changed = True
        if self.export_as == "zae" and not self.use_texture_copies:
            self.use_texture_copies = True
            changed = True
        return changed

    def execute(self, context):
        if not _refresh_collada_status():
            detail = COLLADA_IMPORT_ERROR or "unknown import error"
            self.report({"ERROR"}, f"pycollada is not available: {detail}")
            return {"CANCELLED"}

        from . import export_collada

        kwargs = self.as_keywords(ignore=("filter_glob", "prop_bc_export_ui_section"))
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
