import os
import math
import enum
import re
import io
import time
import tempfile
import zipfile
import numpy as np
import bpy
from mathutils import Matrix, Vector

from collada import Collada
from collada.camera import PerspectiveCamera, OrthographicCamera
from collada.common import DaeObject, E
from collada.geometry import Geometry
from collada.light import DirectionalLight, PointLight, SpotLight
from collada.material import CImage, Effect, Map, Material, Sampler2D, Surface
from collada.scene import Node, Scene
from collada.scene import CameraNode, ControllerNode, GeometryNode, LightNode, MaterialNode
from collada.scene import MatrixTransform
try :
    from collada.scene import RotateTransform, ScaleTransform, TranslateTransform
except ImportError :
    RotateTransform = ScaleTransform = TranslateTransform = None
#end try
from bpy_extras.io_utils import axis_conversion
from collada.source import FloatSource, InputList
from collada.xmlutil import etree as ElementTree

DEG = math.pi / 180 # angle unit conversion factor

XML_DECLARATION = b'<?xml version="1.0" encoding="utf-8"?>\n'
  # pycollada Collada.write() emits the root with no declaration.
  # Native Blender COLLADA always wrote one; several readers require it.

# profile_COMMON: children allowed inside each shader (COLLADA 1.4.1).
# pycollada Effect.__init__ fills specular/shininess/transparent with defaults
# and Effect.save() writes every non-None supported property into the shader.
PROFILE_COMMON_SHADER_PROPS = \
    {
        "constant" : frozenset
          ((
            "emission", "reflective", "reflectivity",
            "transparent", "transparency", "index_of_refraction",
          )),
        "lambert" : frozenset
          ((
            "emission", "ambient", "diffuse",
            "reflective", "reflectivity",
            "transparent", "transparency", "index_of_refraction",
          )),
        "phong" : frozenset
          ((
            "emission", "ambient", "diffuse", "specular", "shininess",
            "reflective", "reflectivity",
            "transparent", "transparency", "index_of_refraction",
          )),
        "blinn" : frozenset
          ((
            "emission", "ambient", "diffuse", "specular", "shininess",
            "reflective", "reflectivity",
            "transparent", "transparency", "index_of_refraction",
          )),
    }

OPAQUE_WHITE = (1.0, 1.0, 1.0, 1.0)
  # A_ONE <transparent> color: opacity comes from <transparency>, not a texture.

MESH_CONVERT_TYPES = frozenset(("MESH", "CURVE", "SURFACE", "META", "FONT"))
NATIVE_EXPORT_TYPES = frozenset(("MESH", "CAMERA", "LIGHT", "EMPTY", "ARMATURE"))
  # SceneExporter::writeNode object types. Curves/text/meta still convert to mesh.
LIMITTED_PRECISION = 6
  # collada_utils.h LIMITTED_PRECISION
SEMANTIC_SUFFIX = \
    {
        "POSITION" : "-positions",
        "VERTEX" : "-vertices",
        "NORMAL" : "-normals",
        "TEXCOORD" : "-map",
        "COLOR" : "-colors",
    }
  # COLLADASW::InputSemantic::getSuffixBySemantic
SKIN_CONTROLLER_ID_SUFFIX = "-skin"
JOINTS_SOURCE_ID_SUFFIX = "-joints"
BIND_POSES_SOURCE_ID_SUFFIX = "-bind_poses"
WEIGHTS_SOURCE_ID_SUFFIX = "-weights"
MORPH_CONTROLLER_ID_SUFFIX = "-morph"
TARGETS_SOURCE_ID_SUFFIX = "-morph-targets"

def ensure_xml_declaration(data) :
    "Prefix an XML declaration when pycollada omitted it."
    if isinstance(data, str) :
        data = data.encode("utf-8")
    #end if
    if data.lstrip().startswith(b"<?xml") :
        return data
    #end if
    return XML_DECLARATION + data
#end ensure_xml_declaration

def sanitize_effect(effect, shader, explicit_props) :
    "Drop pycollada defaults and properties illegal for this shader."
    allowed = PROFILE_COMMON_SHADER_PROPS.get(shader)
    if allowed is None :
        return
    #end if
    for prop in Effect.supported :
        value = getattr(effect, prop, None)
        if value is None :
            continue
        #end if
        if prop not in allowed :
            setattr(effect, prop, None)
            continue
        #end if
        if prop in explicit_props :
            continue
        #end if
        if prop in ("specular", "ambient", "emission", "reflective", "transparent") :
            if isinstance(value, (tuple, list)) and all(float(c) == 0.0 for c in value[:3]) :
                setattr(effect, prop, None)
            #end if
        elif prop in ("shininess", "reflectivity") and float(value) == 0.0 :
            setattr(effect, prop, None)
        #end if
    #end for
#end sanitize_effect

class _SkinControllerExport :
    "Minimal pycollada controller stand-in; Skin.save() is not implemented."

    def __init__(self, id, xmlnode) :
        self.id = id
        self.xmlnode = xmlnode
    #end __init__

    def save(self) :
        if self.xmlnode is not None :
            self.xmlnode.set("id", self.id)
        #end if
    #end save

#end _SkinControllerExport

XML_NCNAMESTART_CHARS = \
    r"\u0041-\u005A\u005F\u0061-\u007A\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF" \
    r"\u0370-\u037D\u037F-\u1FFF\u200C\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF" \
    r"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
      # valid chars that can start an NCName, as per the xml:id spec;
      # these are all of NameStartChar (see section 2.3 of the XML 1.0
      # or 1.1 specs) except “:”.
XML_NCNAMEREST_CHARS = r"\u002D\u002E\u0030-\u0039\u00B7\u0300-\u036F\u203F\u2040"
      # valid chars that, together with XML_NCNAMESTART_CHARS, can make up the rest of an NCName.

class DATABLOCK(enum.Enum) :
    # Note on uniqueness of IDs: Blender’s datablock names have to be
    # unique among datablocks of the same type, so these can be used as
    # IDs in XML, with a different prefix for each datablock type.
    ARMATURE = "AR"
    CAMERA = "CA"
    EMPTY = "EM" # actually there is no type-specific datablock for these
    LAMP = "LA"
    MATERIAL = "MA"
    MESH = "ME"
    OBJECT = "OB"
    SCENE = "SCE"
    INTERNAL_ID = "IID" # for things which have no names in Blender

    def nameid(self, name) :
        celf = type(self)
        if self not in celf._name_maps :
            celf._name_maps[self] = {}
            celf._name_revmaps[self] = {}
        #end if
        name_map = celf._name_maps[self]
        name_revmap = celf._name_revmaps[self]
        if name in name_map :
            clean_name = name_map[name]
        elif len(name) == 0 :
            # allowed for generating id-prefix-mapping table
            clean_name = ""
        else :
            clean_char = "_" # permissible anywhere in an XML ID
            base_clean_name = \
                (
                    re.sub("^[^" + XML_NCNAMESTART_CHARS + "]$", clean_char, name[0])
                +
                    re.sub("[^" + XML_NCNAMESTART_CHARS + XML_NCNAMEREST_CHARS + "]", clean_char, name[1:])
                )
            clean_name = base_clean_name
            seq = 0
            while clean_name in name_revmap :
                seq += 1
                clean_name = "%s-%0.3d" % (base_clean_name, seq)
            #end while
            name_map[name] = clean_name
            name_revmap[clean_name] = name
        #end if
        return \
            "%s-%s" % (self.value, clean_name)
    #end nameid

    @property
    def internal_only(self) :
        "indicates IDs of this type are not used to name Blender objects on (re)import."
        return self == DATABLOCK.INTERNAL_ID
    #end internal_only

#end DATABLOCK
DATABLOCK._name_maps = {}
DATABLOCK._name_revmaps = {}

class EXT_FILE(enum.Enum) :

    TEXTURE = "textures"

    @property
    def subdir(self) :
        return self.value
    #end subdir

#end EXT_FILE

def idurl(uid) :
    return "#" + uid
#end idurl

def _mesh_poly_loop_indices(poly) :
    "Loop indices for a MeshPolygon (Blender Mesh, not BMesh)."
    indices = getattr(poly, "loop_indices", None)
    if indices is not None :
        return indices
    #end if
    return range(poly.loop_start, poly.loop_start + poly.loop_total)
#end _mesh_poly_loop_indices

def _mesh_face_is_smooth(mesh, poly) :
    "True when the face uses vertex/corner normals (not a sharp/flat face)."
    attr = getattr(mesh, "attributes", None)
    if attr is not None :
        sharp = attr.get("sharp_face")
        if sharp is not None :
            try :
                return not bool(sharp.data[poly.index].value)
            except (AttributeError, IndexError, TypeError) :
                pass
            #end try
        #end if
    #end if
    if hasattr(poly, "use_smooth") :
        return bool(poly.use_smooth)
    #end if
    return True
#end _mesh_face_is_smooth

def _mesh_loop_normal(mesh, loop_index, vert_index) :
    try :
        corners = mesh.corner_normals
        if corners is not None and loop_index < len(corners) :
            vec = Vector(corners[loop_index].vector)
            if vec.length_squared > 1e-16 :
                return vec
            #end if
        #end if
    except (AttributeError, IndexError, TypeError) :
        pass
    #end try
    loop = mesh.loops[loop_index]
    if hasattr(loop, "normal") :
        try :
            vec = Vector(loop.normal)
            if vec.length_squared > 1e-16 :
                return vec
            #end if
        except (AttributeError, TypeError) :
            pass
        #end try
    #end if
    return Vector(mesh.vertices[vert_index].normal)
#end _mesh_loop_normal

def _mesh_color_layers(mesh) :
    "Corner or point color layers as (name, domain, data_seq)."
    layers = []
    attrs = getattr(mesh, "color_attributes", None)
    if attrs :
        for attr in attrs :
            domain = getattr(attr, "domain", "CORNER")
            if domain in ("CORNER", "POINT") :
                layers.append((attr.name, domain, attr.data))
            #end if
        #end for
        if layers :
            return layers
        #end if
    #end if
    vcols = getattr(mesh, "vertex_colors", None)
    if vcols :
        for vc in vcols :
            layers.append((vc.name, "CORNER", vc.data))
        #end for
    #end if
    return layers
#end _mesh_color_layers

def _color_components(item) :
    col = getattr(item, "color", item)
    r = float(col[0])
    g = float(col[1])
    b = float(col[2])
    a = float(col[3]) if len(col) > 3 else 1.0
    if r > 1.0 or g > 1.0 or b > 1.0 or a > 1.0 :
        r, g, b, a = r / 255.0, g / 255.0, b / 255.0, a / 255.0
    #end if
    return r, g, b, a
#end _color_components

def _mesh_loose_edges(mesh) :
    loose = []
    has_flag = False
    for edge in mesh.edges :
        if hasattr(edge, "is_loose") :
            has_flag = True
            if edge.is_loose :
                loose.append(edge)
            #end if
        #end if
    #end for
    if has_flag :
        return loose
    #end if
    used = set()
    for poly in mesh.polygons :
        verts = poly.vertices
        n = len(verts)
        for i in range(n) :
            a = verts[i]
            b = verts[(i + 1) % n]
            used.add((a, b) if a < b else (b, a))
        #end for
    #end for
    for edge in mesh.edges :
        a, b = edge.vertices
        key = (a, b) if a < b else (b, a)
        if key not in used :
            loose.append(edge)
        #end if
    #end for
    return loose
#end _mesh_loose_edges

def translate_id(name) :
    "Native collada_internal::translate_id: XML id without a datablock prefix."
    if name is None :
        name = ""
    #end if
    name = str(name)
    if len(name) == 0 :
        return "unnamed"
    #end if
    return DATABLOCK.INTERNAL_ID.nameid(name)[len(DATABLOCK.INTERNAL_ID.value) + 1:]
#end translate_id

def geometry_id(b_obj, use_instantiation) :
    data = getattr(b_obj, "data", None)
    geom_name = data.name if (use_instantiation and data is not None and getattr(data, "name", None)) else b_obj.name
    return translate_id(geom_name) + "-mesh"
#end geometry_id

def material_id(b_mat) :
    return translate_id(b_mat.name) + "-material"
#end material_id

def effect_id(b_mat) :
    return translate_id(b_mat.name) + "-effect"
#end effect_id

def camera_id(b_obj) :
    return translate_id(b_obj.name) + "-camera"
#end camera_id

def light_id(b_obj) :
    return translate_id(b_obj.name) + "-light"
#end light_id

def joint_node_id(arm_obj, bone) :
    return translate_id(arm_obj.name + "_" + bone.name)
#end joint_node_id

def joint_sid(bone) :
    return translate_id(bone.name)
#end joint_sid

def skin_controller_id(arm_obj, b_obj) :
    return translate_id(arm_obj.name) + "_" + translate_id(b_obj.name) + SKIN_CONTROLLER_ID_SUFFIX
#end skin_controller_id

def morph_controller_id(b_obj) :
    return translate_id(b_obj.name) + MORPH_CONTROLLER_ID_SUFFIX
#end morph_controller_id

def source_id(geom_id, semantic, extra = "") :
    return geom_id + SEMANTIC_SUFFIX[semantic] + extra
#end source_id

def _unit_name(unit_settings) :
    "DocumentExporter asset unit name from Blender unit_settings."
    scale = float(getattr(unit_settings, "scale_length", 1.0) or 1.0)
    system = getattr(unit_settings, "system", "METRIC")
    if system in ("NONE", "METRIC") :
        return \
            {
                0.001 : "millimeter",
                0.01 : "centimeter",
                0.1 : "decimeter",
                1.0 : "meter",
                1000.0 : "kilometer",
            }.get(scale, "meter")
    #end if
    if system == "IMPERIAL" :
        return \
            {
                0.0254 : "inch",
                0.3048 : "foot",
                0.9144 : "yard",
            }.get(scale, "meter")
    #end if
    return "meter"
#end _unit_name

def _global_orientation_matrix(forward, up) :
    "BCMatrix(forward, up): convert user axes to native default Y-forward Z-up."
    try :
        m3 = axis_conversion(from_forward = forward, from_up = up, to_forward = "Y", to_up = "Z")
        return m3.to_4x4()
    except Exception :
        return Matrix.Identity(4)
    #end try
#end _global_orientation_matrix

def _limit_precision_matrix(mat) :
    out = mat.copy()
    for i in range(4) :
        for j in range(4) :
            out[i][j] = round(float(out[i][j]), LIMITTED_PRECISION)
        #end for
    #end for
    return out
#end _limit_precision_matrix

def _dae_matrix_floats(mat, precision = None) :
    "COLLADA column-major 16-float list (native UnitConverter::mat4_to_dae)."
    t = mat.transposed()
    return _fmt_floats([e for r in tuple(map(tuple, t)) for e in r], precision)
#end _dae_matrix_floats

def _bone_rest_local(bone) :
    "Parent-relative rest matrix (ArmatureExporter::add_bone_transform)."
    rest = bone.matrix_local.copy()
    if bone.parent is None :
        return rest
    #end if
    try :
        return bone.parent.matrix_local.inverted() @ rest
    except ValueError :
        return rest
    #end try
#end _bone_rest_local

def _object_visible(obj) :
    try :
        return obj.visible_get()
    except Exception :
        return not getattr(obj, "hide_viewport", False)
    #end try
#end _object_visible

def _armature_object(b_obj) :
    "Armature Object driving this mesh, if any."
    if b_obj is None :
        return None
    #end if
    if b_obj.type == "ARMATURE" :
        return b_obj
    #end if
    parent = b_obj.parent
    if parent is not None and parent.type == "ARMATURE" and b_obj.parent_type in ("ARMATURE", "BONE") :
        return parent
    #end if
    for mod in getattr(b_obj, "modifiers", []) :
        if getattr(mod, "type", None) == "ARMATURE" and getattr(mod, "object", None) is not None :
            return mod.object
        #end if
    #end for
    return None
#end _armature_object

def _fmt_floats(values, precision = None) :
    if precision is None :
        return " ".join(str(float(v)) for v in values)
    #end if
    fmt = "%%.%df" % precision
    return " ".join(fmt % float(v) for v in values)
#end _fmt_floats

class ColladaExport :

    def __init__(self, objects, filepath, directory, kwargs) :
        # Native DocumentExporter::exportCurrentScene calls clear_global_id_map().
        DATABLOCK._name_maps.clear()
        DATABLOCK._name_revmaps.clear()
        self._is_zae = kwargs.get("export_as", "dae") == "zae"
        self._export_textures = bool(kwargs.get("use_texture_copies", True))
        self._add_blender_extensions = bool(kwargs.get("use_blender_profile", True))
        self._filepath = filepath
        self._dir = directory
        self._ext_files_map = {}
        self._ext_files_revmap = {}
        # Atomic write: build into a temp path, then replace the destination.
        # Prefer the destination directory so os.replace stays on the same volume.
        out_dir = None
        if directory and os.path.isdir(directory) :
            out_dir = directory
        else :
            parent = os.path.dirname(filepath)
            if parent and os.path.isdir(parent) :
                out_dir = parent
            #end if
        #end if
        fd, self._temp_filepath = tempfile.mkstemp(
            suffix = ".zae" if self._is_zae else ".dae",
            prefix = ".collada_export_",
            dir = out_dir,
        )
        os.close(fd)
        self._zip = None
        self._zipattr = None
        try :
            if self._is_zae :
                self._zip = zipfile.ZipFile(self._temp_filepath, "w")
                class ZipAttr :
                    compress_type = zipfile.ZIP_DEFLATED
                    file_attr = 0o100644 << 16
                    date_time = time.gmtime()[:6]
                    scene_name = "scene.dae"

                    @classmethod
                    def new_item(celf, filename) :
                        item = zipfile.ZipInfo()
                        item.compress_type = celf.compress_type
                        item.external_attr = celf.file_attr
                        item.date_time = celf.date_time
                        item.filename = filename
                        return item
                    #end new_item

                #end ZipAttr
                self._zipattr = ZipAttr
                # First item in archive is uncompressed and named “mimetype”, and
                # contents is MIME type for archive. This way it ends up at a fixed
                # offset (filename at 30 bytes from start, contents at 38 bytes) for
                # easy detection by format-sniffing tools. This convention is used
                # by ODF and other formats similarly based on Zip archives.
                mimetype = zipfile.ZipInfo()
                mimetype.filename = "mimetype"
                mimetype.compress_type = zipfile.ZIP_STORED
                mimetype.external_attr = ZipAttr.file_attr
                mimetype.date_time = (2020, 8, 23, 1, 33, 52)
                  # about when I started getting .zae export working
                self._zip.writestr(mimetype, b"model/vnd.collada+xml+zip")
                  # extrapolating from the fact that the official type for .dae files
                  # is “model/vnd.collada+xml”
            #end if
        except Exception :
            self.abort_temp()
            raise
        #end try
        self._forward_axis = kwargs.get("export_global_forward_selection", "Y")
        self._up_axis = kwargs.get("export_global_up_selection", "Z")
        self._apply_global_orientation = bool(kwargs.get("apply_global_orientation", False))
        self._orient = _global_orientation_matrix(self._forward_axis, self._up_axis)
        self._selected_only = bool(kwargs.get("selected", False))
        self._include_children = bool(kwargs.get("include_children", False))
        self._include_armatures = bool(kwargs.get("include_armatures", False))
        self._include_shapekeys = bool(kwargs.get("include_shapekeys", False))
        self._apply_modifiers = bool(kwargs.get("apply_modifiers", False))
        self._export_mesh_type = kwargs.get("export_mesh_type_selection", "view")
        self._triangulate = bool(kwargs.get("triangulate", True))
        self._active_uv_only = bool(kwargs.get("active_uv_only", False))
        self._use_object_instantiation = bool(kwargs.get("use_object_instantiation", True))
        self._deform_bones_only = bool(kwargs.get("deform_bones_only", False))
        self._open_sim = bool(kwargs.get("open_sim", False))
        self._sort_by_name = bool(kwargs.get("sort_by_name", False))
        self._limit_precision = bool(kwargs.get("limit_precision", False))
        self._keep_bind_info = bool(kwargs.get("keep_bind_info", False))
        self._include_animations = bool(kwargs.get("include_animations", True))
        self._export_animation_type = kwargs.get("export_animation_type_selection", "sample")
        object_xform = kwargs.get("export_object_transformation_type_selection", "matrix")
        anim_xform = kwargs.get("export_animation_transformation_type_selection", "matrix")
        if self._export_animation_type != "sample" :
            anim_xform = "decomposed"
        #end if
        if self._include_animations :
            object_xform = anim_xform
        #end if
        self._object_transformation_type = object_xform
        self._export_custom_props = self._add_blender_extensions
        # Selection-only: selected objects whose parent is unselected are still
        # exported as roots (1.1.0 / Blender 4.5). Include Children / Include
        # Armatures match the native exporter Main panel (both default off).
        if self._selected_only :
            export_names = set(o.name for o in objects if o.select_get())
            if self._include_children :
                stack = []
                for obj in objects :
                    if obj.name in export_names :
                        stack.extend(obj.children)
                    #end if
                #end for
                while stack :
                    child = stack.pop()
                    if child.name not in export_names :
                        export_names.add(child.name)
                        stack.extend(child.children)
                    #end if
                #end while
                # Native: select armature + Include Children also pulls rigged meshes.
                for obj in objects :
                    arm = _armature_object(obj)
                    if arm is not None and arm.name in export_names :
                        export_names.add(obj.name)
                    #end if
                #end for
            #end if
            if self._include_armatures :
                for obj in list(objects) :
                    if obj.name not in export_names :
                        continue
                    #end if
                    arm = _armature_object(obj)
                    if arm is not None :
                        export_names.add(arm.name)
                    #end if
                #end for
            #end if
            self._export_names = export_names
            export_objects = [o for o in objects if o.name in export_names]
        else :
            self._export_names = None
            export_objects = list(objects)
        #end if
        # Native BKE_object_relational_superset skips invisible objects.
        export_objects = [o for o in export_objects if _object_visible(o)]
        if self._sort_by_name :
            export_objects.sort(key = lambda o : o.name)
        #end if
        obj_children = {}
        for obj in export_objects :
            parent = obj.parent
            # Treat as root when parent is missing or not in the export set.
            if parent == None or (
                    self._export_names is not None
                and
                    parent.name not in self._export_names
            ) :
                parentname = None
            else :
                parentname = parent.name
            #end if
            if parentname not in obj_children :
                obj_children[parentname] = set()
            #end if
            obj_children[parentname].add(obj.name)
        #end for
        self._obj_children = obj_children
        self._geometries = {}
        self._materials = {}
        self._armature_ids = {}
        self._armature_root_joints = {}
        self._skin_controllers = {}
        self._temp_meshes = []
        for obj in export_objects :
            if obj.type == "ARMATURE" :
                self._armature_ids[obj.name] = translate_id(obj.name)
            #end if
        #end for
        self._collada = Collada()
        self._collada.xmlnode.getroot().set("version", kwargs.get("collada_version", "1.4.1"))
        # Scene units from Blender (native DocumentExporter always writes Z_UP).
        unit_settings = bpy.context.scene.unit_settings
        scale_length = float(getattr(unit_settings, "scale_length", 1.0) or 1.0)
        self._collada.assetInfo.unitmeter = scale_length
        self._collada.assetInfo.unitname = _unit_name(unit_settings)
        self._collada.assetInfo.upaxis = "Z_UP"
        try :
            self._collada.assetInfo.contributors[0].authoring_tool = \
                "Blender %s Collada Support 2.0.2" % bpy.app.version_string
        except Exception :
            pass
        #end try
        self._collada.assetInfo.save()
        root_technique = self.blender_technique(True, self._collada.xmlnode.getroot())
        if root_technique != None :
            prefixes = E.id_prefixes()
            for k in sorted(DATABLOCK.__members__.keys()) :
                v = DATABLOCK[k]
                if not v.internal_only :
                    prefix = E.prefix(name = k, value = v.nameid(""))
                    prefixes.append(prefix)
                #end if
            #end for
            root_technique.append(prefixes)
        #end if

        scene_name = translate_id(bpy.context.scene.name)
        self._scene = Scene(scene_name, [])
        self._collada.scenes.append(self._scene)
        self._collada.scene = self._scene
        self._id_seq = 0

    #end __init__

    def abort_temp(self) :
        "Close any open zip and remove the temp output on failure."
        if self._zip is not None :
            try :
                self._zip.close()
            except Exception :
                pass
            #end try
            self._zip = None
        #end if
        temp = getattr(self, "_temp_filepath", None)
        if temp and os.path.isfile(temp) :
            try :
                os.remove(temp)
            except OSError :
                pass
            #end try
        #end if
        self._free_temp_meshes()
    #end abort_temp

    def write_ext_file(self, category, obj_name, filename, contents) :
        if category not in self._ext_files_map :
            self._ext_files_map[category] = {}
            self._ext_files_revmap[category] = {}
        #end if
        ext_files_map = self._ext_files_map[category]
        ext_files_revmap = self._ext_files_revmap[category]
        if obj_name in ext_files_map :
            # already encountered this external file
            out_filename = ext_files_map[obj_name]
        else :
            if not self._is_zae :
                # Native ImagesExporter copies into the same folder as the .dae.
                outdir = self._dir
                os.makedirs(outdir, exist_ok = True)
            #end if
            base_out_filename = filename if not self._is_zae else os.path.join(category.subdir, filename)
            out_filename = base_out_filename
            seq = 0
            while out_filename in ext_files_revmap :
                if seq == 0 :
                    base_parts = os.path.splitext(base_out_filename)
                #end if
                seq += 1
                assert seq < 1000000 # impose some ridiculous but finite upper limit
                out_filename = "%s-%0.3d%s" % (base_parts[0], seq, base_parts[1])
            #end while
            ext_files_map[obj_name] = out_filename
            ext_files_revmap[out_filename] = obj_name
            if self._is_zae :
                item = self._zipattr.new_item(out_filename)
                self._zip.writestr(item, contents)
            else :
                out = open(os.path.join(self._dir, out_filename), "wb")
                out.write(contents)
                out.close()
            #end if
        #end if
        return out_filename
    #end write_ext_file

    def collada_bytes(self) :
        buf = io.BytesIO()
        self._collada.write(buf)
        return ensure_xml_declaration(buf.getvalue())
    #end collada_bytes

    def _free_temp_meshes(self) :
        meshes = getattr(self, "_temp_meshes", None)
        if not meshes :
            return
        #end if
        for mesh in meshes :
            try :
                bpy.data.meshes.remove(mesh)
            except Exception :
                pass
            #end try
        #end for
        self._temp_meshes = []
    #end _free_temp_meshes

    def save(self) :
        try :
            dae_bytes = self.collada_bytes()
            if self._is_zae :
                item = self._zipattr.new_item(self._zipattr.scene_name)
                self._zip.writestr(item, dae_bytes)
                manifest = ElementTree.Element("dae_root")
                manifest.text = self._zipattr.scene_name
                item = self._zipattr.new_item("manifest.xml")
                self._zip.writestr(item, ElementTree.tostring(manifest))
                self._zip.close()
                self._zip = None
            else :
                out = open(self._temp_filepath, "wb")
                out.write(dae_bytes)
                out.close()
            #end if
            os.replace(self._temp_filepath, self._filepath)
        except Exception :
            self.abort_temp()
            raise
        finally :
            self._free_temp_meshes()
        #end try
    #end save

    def blender_technique(self, as_extra, obj) :
        # experimental: add Blender-specific attributes via a custom <technique>.
        if self._add_blender_extensions :
            if isinstance(obj, DaeObject) :
                obj = obj.xmlnode
            #end if
            blendstuff = E.technique(profile = "BLENDER028")
            if as_extra :
                parent = E.extra()
            else :
                parent = obj
            #end if
            parent.append(blendstuff)
            if as_extra :
                obj.append(parent)
            #end if
        else :
            blendstuff = None
        #end if
        return blendstuff
    #end blender_technique

    def obj_blender_technique(self, as_extra, obj, b_data, attribs) :
        # save any custom technique settings for this object.
        blendstuff = self.blender_technique(as_extra, obj)
        if blendstuff != None :
            for tagname, attrname in attribs :
                if hasattr(b_data, attrname) :
                    subtag = getattr(E, tagname)(str(getattr(b_data, attrname)))
                    blendstuff.append(subtag)
                #end if
            #end for
        #end if
    #end obj_blender_technique

    def next_internal_id(self) :
        self._id_seq += 1
        return DATABLOCK.INTERNAL_ID.nameid("%0.5d" % self._id_seq)
    #end next_internal_id

    def node(self, b_matrix = None, b_obj = None) :
        # Native SceneExporter: node id/name = translate_id(object name).
        if b_obj is not None :
            node_id = translate_id(b_obj.name)
            xml = E.node(id = node_id, name = b_obj.name)
            node = Node(id = node_id, name = b_obj.name, xmlnode = xml)
        else :
            node = Node(id = None, xmlnode = E.node())
        #end if
        if b_matrix != None :
            self._append_node_transform(node, b_matrix)
        #end if
        node.save()
        return node
    #end node

    def _append_node_transform(self, node, b_matrix) :
        mat = b_matrix.copy()
        if self._limit_precision :
            mat = _limit_precision_matrix(mat)
        #end if
        if (
                self._object_transformation_type == "decomposed"
            and
                TranslateTransform is not None
        ) :
            loc, rot, scale = mat.decompose()
            eul = rot.to_euler("XYZ")
            node.transforms.append(ScaleTransform(float(scale.x), float(scale.y), float(scale.z)))
            node.transforms.append(RotateTransform(0.0, 0.0, 1.0, float(eul.z / DEG)))
            node.transforms.append(RotateTransform(0.0, 1.0, 0.0, float(eul.y / DEG)))
            node.transforms.append(RotateTransform(1.0, 0.0, 0.0, float(eul.x / DEG)))
            node.transforms.append(TranslateTransform(float(loc.x), float(loc.y), float(loc.z)))
        else :
            xform = self.matrix(mat)
            try :
                xform.xmlnode.set("sid", "transform")
            except Exception :
                pass
            #end try
            node.transforms.append(xform)
        #end if
    #end _append_node_transform

    def _export_object_extras(self, node, b_obj) :
        if not self._add_blender_extensions or not self._export_custom_props :
            return
        #end if
        keys = [k for k in b_obj.keys() if not k.startswith("_")]
        if not keys :
            return
        #end if
        blendstuff = self.blender_technique(True, node)
        if blendstuff is None :
            return
        #end if
        props = E.custom_properties()
        for key in keys :
            try :
                value = b_obj[key]
            except Exception :
                continue
            #end try
            if hasattr(value, "to_list") :
                try :
                    value = value.to_list()
                except Exception :
                    pass
                #end try
            #end if
            text = str(value)
            if len(text) > 512 :
                text = text[:512]
            #end if
            props.append(E.property(text, name = str(key)))
        #end for
        if len(props) :
            blendstuff.append(props)
        #end if
    #end _export_object_extras

    def obj_camera(self, b_obj) :
        result = []
        b_cam = b_obj.data
        if b_cam.type == "PERSP" :
            cam_class = PerspectiveCamera
            args = \
                {
                    "xfov" : b_cam.angle_x / DEG,
                    "yfov" : b_cam.angle_y / DEG,
                }
        elif b_cam.type == "ORTHO" :
            cam_class = OrthographicCamera
            # Match Blender 4.5 CamerasExporter: xmag/ymag are half of ortho_scale.
            half = b_cam.ortho_scale / 2.0
            args = \
                {
                    "xmag" : half,
                    "ymag" : half,
                }
        else :
            cam_class = None
        #end if
        if cam_class != None :
            # todo: shared datablock
            cam = cam_class \
              (
                id = camera_id(b_obj),
                znear = b_cam.clip_start,
                zfar = b_cam.clip_end,
                **args
              )
            self._collada.cameras.append(cam)
            result.append(CameraNode(cam))
        #end if
        return result
    #end obj_camera

    def obj_light(self, b_obj) :
        result = []
        b_light = b_obj.data
        light_type = tuple \
          (
            t for t in
                (
                    ("POINT", PointLight),
                    ("SPOT", SpotLight),
                    ("SUN", DirectionalLight),
                )
            if b_light.type == t[0]
          )
        if len(light_type) != 0 :
            light_type = light_type[0][1]
        else :
            light_type = None
        #end if
        if light_type != None :
            # todo: shared datablock
            light = light_type \
              (
                light_id(b_obj),
                color = tuple(b_light.color) + (1,)
              )
            for attr, battr, conv in \
                (
                  # conversions are inverses of those done in importer
                    ("falloff_ang", "spot_size", lambda ang : ang / DEG),
                    ("falloff_exp", "spot_blend", lambda blend : 1 / max(blend, 0.00001) - 1),
                      # some very small-magnitude positive value to avoid division by zero
                ) \
            :
                if hasattr(b_light, battr) and hasattr(light, attr) :
                    setattr(light, attr, conv(getattr(b_light, battr)))
                #end if
            #end for
            if b_light.use_nodes :
                node_graph = b_light.node_tree
                the_node = list(n for n in node_graph.nodes if n.type == "OUTPUT_LIGHT")[0]
                trace_path = iter \
                  (
                    (
                        ("Surface", "EMISSION"),
                        ("Strength", "LIGHT_FALLOFF"),
                    )
                  )
                found = False
                while True :
                    trace = next(trace_path, None)
                    if trace == None :
                        if not the_node.inputs["Strength"].is_linked :
                            found = True
                        #end if
                        break
                    #end if
                    input_name, want_shader_type = trace
                    input = the_node.inputs[input_name]
                    if not input.is_linked :
                        break
                    links = input.links
                      # note docs say this takes O(N) in total nr links in node graph to compute
                    if len(links) == 0 :
                        break
                    the_node = links[0].from_node
                    if the_node.type != want_shader_type :
                        break
                    output_name = links[0].from_socket.name
                #end while
                if found :
                    strength = the_node.inputs["Strength"].default_value
                    if strength != 0 :
                        atten = \
                            {
                                "Constant" : "constant_att",
                                "Linear" : "linear_att",
                                "Quadratic" : "quad_att",
                            }.get(output_name)
                        if atten != None and hasattr(light, atten) :
                            setattr(light, atten, 1 / strength)
                        #end if
                    #end if
                #end if
            #end if
            self.obj_blender_technique \
              (
                True,
                light,
                b_light,
                [
                    ("angle", "angle"),
                    ("power", "energy"),
                    ("shadow_soft_size", "shadow_soft_size"),
                    ("spot_blend", "spot_blend"),
                    ("spot_size", "spot_size"),
                ]
              )
            self._collada.lights.append(light)
            result.append(LightNode(light))
        #end if
        return result
    #end obj_light

    def obj_empty(self, b_obj) :
        result = Node(id = translate_id(b_obj.name), name = b_obj.name)
        return [result]
    #end obj_empty

    def _will_export_skin(self, b_obj) :
        if b_obj.type != "MESH" :
            return False
        #end if
        arm = _armature_object(b_obj)
        if arm is None or not b_obj.vertex_groups :
            return False
        #end if
        if self._export_names is not None and arm.name not in self._export_names :
            return False
        #end if
        return True
    #end _will_export_skin

    def _release_export_mesh(self, mesh_state) :
        "Free a temporary evaluated Mesh from _object_to_mesh."
        if mesh_state is None :
            return
        #end if
        eval_obj, owned_mesh = mesh_state[1], mesh_state[2]
        if eval_obj is not None :
            try :
                eval_obj.to_mesh_clear()
            except Exception :
                pass
            #end try
        #end if
        if owned_mesh is not None :
            try :
                bpy.data.meshes.remove(owned_mesh)
            except Exception :
                pass
            #end try
        #end if
    #end _release_export_mesh

    def _object_to_mesh(self, b_obj) :
        "Evaluated Mesh for export (modifiers, curve conversion). Never BMesh."
        will_skin = self._will_export_skin(b_obj)
        # Native bc_get_mesh_copy evaluates only when apply_modifiers is on.
        # Shape keys are extra morph geometries, not a baked mix.
        need_eval = b_obj.type != "MESH" or self._apply_modifiers
        muted = []
        src_mesh = None
        eval_obj = None
        owned_mesh = None
        try :
            if need_eval :
                for mod in getattr(b_obj, "modifiers", []) :
                    # Rest-pose skin: do not bake Armature deformation into the mesh.
                    mute = (will_skin and mod.type == "ARMATURE") or (
                        not self._apply_modifiers and mod.type != "ARMATURE"
                    )
                    if mute and getattr(mod, "show_viewport", False) :
                        mod.show_viewport = False
                        muted.append(mod)
                    #end if
                #end for
                if muted :
                    bpy.context.view_layer.update()
                #end if
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = b_obj.evaluated_get(depsgraph)
                try :
                    src_mesh = eval_obj.to_mesh \
                      (
                        preserve_all_data_layers = True,
                        depsgraph = depsgraph,
                      )
                except Exception :
                    src_mesh = None
                #end try
                if src_mesh is None :
                    try :
                        eval_obj.to_mesh_clear()
                    except Exception :
                        pass
                    #end try
                    eval_obj = None
                    try :
                        owned_mesh = bpy.data.meshes.new_from_object \
                          (
                            b_obj.evaluated_get(depsgraph),
                            preserve_all_data_layers = True,
                            depsgraph = depsgraph,
                          )
                        src_mesh = owned_mesh
                    except Exception :
                        src_mesh = getattr(b_obj, "data", None) if b_obj.type == "MESH" else None
                        owned_mesh = None
                    #end try
                #end if
            elif b_obj.type == "MESH" :
                src_mesh = b_obj.data
            #end if
        finally :
            for mod in muted :
                try :
                    mod.show_viewport = True
                except Exception :
                    pass
                #end try
            #end for
        #end try
        return src_mesh, eval_obj, owned_mesh
    #end _object_to_mesh

    def obj_mesh(self, b_obj) :

        def make_slotname(slotindex) :
            # Blender doesn’t name material slots, but Collada does
            return "slot%.3d" % slotindex
        #end make_slotname

        def unique_normal_index(store, vec) :
            if self._apply_global_orientation :
                vec = self._orient.to_3x3() @ vec
            #end if
            if vec.length_squared < 1e-16 :
                vec = Vector((0.0, 0.0, 1.0))
            else :
                vec = vec.normalized()
            #end if
            prec = LIMITTED_PRECISION if self._limit_precision else 6
            key = (round(vec.x, prec), round(vec.y, prec), round(vec.z, prec))
            idx = store[0].get(key)
            if idx is None :
                idx = len(store[1])
                store[0][key] = idx
                store[1].append((float(vec.x), float(vec.y), float(vec.z)))
            #end if
            return idx
        #end unique_normal_index

        def encode_mesh(b_mesh, geom_id, geom_name, b_material_slots, positions = None) :
            # Blender 5 BMLoopSeq has no ensure_lookup_table; do not use BMesh for COLLADA mesh export.
            # Use evaluated Mesh (vertices/polygons/loops/uv_layers) like native GeometryExporter.

            def vert_co(index) :
                if positions is not None and index < len(positions) :
                    co = Vector(positions[index])
                else :
                    co = Vector(b_mesh.vertices[index].co)
                #end if
                if self._apply_global_orientation :
                    co = self._orient @ co
                #end if
                if self._limit_precision :
                    co = Vector((round(co.x, LIMITTED_PRECISION), round(co.y, LIMITTED_PRECISION), round(co.z, LIMITTED_PRECISION)))
                #end if
                return co
            #end vert_co

            def prim_corners(prim) :
                loops = getattr(prim, "loops", None)
                if loops is not None :
                    return list(loops), list(prim.vertices)
                #end if
                loop_ids = list(_mesh_poly_loop_indices(prim))
                vert_ids = [b_mesh.loops[li].vertex_index for li in loop_ids]
                return loop_ids, vert_ids
            #end prim_corners

        #begin encode_mesh
            sources = []
            nverts = len(b_mesh.vertices)
            nloops = len(b_mesh.loops)
            vert_srcid = source_id(geom_id, "POSITION")
            sources.append \
              (
                FloatSource
                  (
                    id = vert_srcid,
                    data = np.array([c for i in range(nverts) for c in vert_co(i)]),
                    components = ("X", "Y", "Z")
                  )
              )
            # Native GeometryExporter: per-loop normals. VERTEX and NORMAL must
            # use different offsets so flat faces keep a face normal instead of
            # a single averaged vertex normal.
            norm_store = ({}, [])
            loop_norm_idx = [0] * nloops
            for poly in b_mesh.polygons :
                loop_ids = _mesh_poly_loop_indices(poly)
                if _mesh_face_is_smooth(b_mesh, poly) :
                    for li in loop_ids :
                        vi = b_mesh.loops[li].vertex_index
                        loop_norm_idx[li] = unique_normal_index \
                          (
                            norm_store,
                            _mesh_loop_normal(b_mesh, li, vi),
                          )
                    #end for
                else :
                    ni = unique_normal_index(norm_store, Vector(poly.normal))
                    for li in loop_ids :
                        loop_norm_idx[li] = ni
                    #end for
                #end if
            #end for
            if not norm_store[1] :
                norm_store[1].append((0.0, 0.0, 1.0))
            #end if
            vnorm_srcid = source_id(geom_id, "NORMAL")
            sources.append \
              (
                FloatSource
                  (
                    id = vnorm_srcid,
                    data = np.array([c for n in norm_store[1] for c in n]),
                    components = ("X", "Y", "Z")
                  )
              )
            uv_ids = []
            uv_layers = list(getattr(b_mesh, "uv_layers", []))
            active_uv = getattr(b_mesh.uv_layers, "active", None) if uv_layers else None
            active_uv_name = active_uv.name if active_uv is not None else None
            if self._active_uv_only and active_uv_name is not None :
                uv_layers = [layer for layer in uv_layers if layer.name == active_uv_name]
            #end if
            for uv_i, uvlayer in enumerate(uv_layers) :
                extra = "" if self._active_uv_only else ("-%d" % uv_i)
                uv_name = source_id(geom_id, "TEXCOORD", extra)
                uv_ids.append((uv_name, uvlayer.name))
                uv_data = [0.0] * (nloops * 2)
                for i, luv in enumerate(uvlayer.data) :
                    uv = luv.uv
                    uv_data[i * 2] = float(uv[0])
                    uv_data[i * 2 + 1] = float(uv[1])
                #end for
                sources.append \
                  (
                    FloatSource
                      (
                        id = uv_name,
                        data = np.array(uv_data),
                        components = ("S", "T")
                      )
                  )
            #end for
            color_ids = []
            for b_colname, domain, coldata in _mesh_color_layers(b_mesh) :
                col_id = source_id(geom_id, "COLOR", "-" + translate_id(b_colname))
                color_ids.append((col_id, b_colname))
                col_data = [0.0] * (nloops * 4)
                if domain == "POINT" :
                    for loop in b_mesh.loops :
                        r, g, b, a = _color_components(coldata[loop.vertex_index])
                        base = loop.index * 4
                        col_data[base] = r
                        col_data[base + 1] = g
                        col_data[base + 2] = b
                        col_data[base + 3] = a
                    #end for
                else :
                    for i, item in enumerate(coldata) :
                        if i >= nloops :
                            break
                        #end if
                        r, g, b, a = _color_components(item)
                        base = i * 4
                        col_data[base] = r
                        col_data[base + 1] = g
                        col_data[base + 2] = b
                        col_data[base + 3] = a
                    #end for
                #end if
                sources.append \
                  (
                    FloatSource
                      (
                        id = col_id,
                        data = np.array(col_data),
                        components = ("R", "G", "B", "A")
                      )
                  )
            #end for
            geom = Geometry(self._collada, geom_id, geom_name, sources)
            blendstuff = self.blender_technique(True, geom)
            if blendstuff != None :
                names = E.layer_names()
                for u in uv_ids :
                    names.append(E.name(name = u[1], refid = u[0], type = "UV"))
                #end for
                for c in color_ids :
                    names.append(E.name(name = c[1], refid = c[0], type = "COLOR"))
                #end for
                blendstuff.append(names)
            #end if

            use_tris = bool(self._triangulate)
            if use_tris :
                try :
                    b_mesh.calc_loop_triangles()
                except Exception :
                    pass
                #end try
            #end if
            for slotindex in range(max(len(b_material_slots), 1)) :
                if use_tris :
                    assigned = \
                        [
                            t
                            for t in b_mesh.loop_triangles
                            if t.material_index == slotindex
                        ]
                else :
                    assigned = \
                        [
                            p
                            for p in b_mesh.polygons
                            if p.material_index == slotindex
                        ]
                #end if
                if any(assigned) :
                    # Native: primitive material symbol is get_material_id(ma).
                    mat = None
                    if slotindex < len(b_material_slots) :
                        mat = b_material_slots[slotindex].material
                    #end if
                    symbol = material_id(mat) if mat is not None else make_slotname(slotindex)
                    # Native stride: VERTEX, NORMAL, then UV/COLOR sharing the
                    # loop index (separate offsets when both UV and COLOR exist).
                    ilist = InputList()
                    ilist.addInput(0, "VERTEX", idurl(vert_srcid))
                    ilist.addInput(1, "NORMAL", idurl(vnorm_srcid))
                    for uv_i, u in enumerate(uv_ids) :
                        uv_set = 0 if self._active_uv_only else uv_i
                        ilist.addInput(2, "TEXCOORD", idurl(u[0]), uv_set)
                    #end for
                    color_offset = 3 if uv_ids else 2
                    color_set = 0
                    for c in color_ids :
                        ilist.addInput(color_offset, "COLOR", idurl(c[0]), color_set)
                        color_set += 1
                    #end for
                    extra_uv = bool(uv_ids)
                    extra_color = bool(color_ids)
                    indices = []
                    vcounts = []
                    all_tris = True
                    for prim in assigned :
                        loop_ids, vert_ids = prim_corners(prim)
                        if len(vert_ids) != 3 :
                            all_tris = False
                        #end if
                        vcounts.append(len(vert_ids))
                        for vi, li in zip(vert_ids, loop_ids) :
                            indices.append(int(vi))
                            indices.append(loop_norm_idx[li] if li < len(loop_norm_idx) else 0)
                            if extra_uv :
                                indices.append(int(li))
                            #end if
                            if extra_color :
                                indices.append(int(li))
                            #end if
                        #end for
                    #end for
                    indices = np.array(indices)
                    if all_tris :
                        p = geom.createTriangleSet(indices, ilist, symbol)
                    else :
                        p = geom.createPolylist(indices, vcounts, ilist, symbol)
                    #end if
                    geom.primitives.append(p)
                #end if
            #end for
            # Native createLooseEdgeList: wire edges as <lines>.
            loose = _mesh_loose_edges(b_mesh)
            if loose :
                line_ilist = InputList()
                line_ilist.addInput(0, "VERTEX", idurl(vert_srcid))
                line_idx = []
                for edge in loose :
                    a, b = edge.vertices
                    line_idx.extend((int(b), int(a)))
                #end for
                try :
                    lines = geom.createLineSet(np.array(line_idx), line_ilist, "")
                    geom.primitives.append(lines)
                except Exception :
                    pass
                #end try
            #end if

            self._collada.geometries.append(geom)
            return geom
        #end encode_mesh

    #begin obj_mesh
        b_mesh_name = getattr(b_obj.data, "name", b_obj.name)
        b_material_slots = b_obj.material_slots
        geom_id = geometry_id(b_obj, self._use_object_instantiation)
        geom_key = geom_id
        geom = self._geometries.get(geom_key, None)
        b_mesh = None
        mesh_state = None
        if not geom :
            b_mesh, eval_obj, owned_mesh = self._object_to_mesh(b_obj)
            mesh_state = (b_mesh, eval_obj, owned_mesh)
            if b_mesh is None :
                self._release_export_mesh(mesh_state)
                return []
            #end if
            geom_name = b_mesh_name if self._use_object_instantiation else b_obj.name
            geom = encode_mesh(b_mesh, geom_id, geom_name, b_material_slots)
            self._geometries[geom_key] = geom
            if self._include_shapekeys and b_obj.type == "MESH" :
                keys = getattr(b_obj.data, "shape_keys", None)
                blocks = list(keys.key_blocks)[1:] if keys is not None else []
                morph_ids = []
                morph_weights = []
                for kb in blocks :
                    morph_id = geometry_id(b_obj, False) + "_morph_" + translate_id(kb.name)
                    if morph_id in self._geometries :
                        morph_ids.append(morph_id)
                        morph_weights.append(float(kb.value))
                        continue
                    #end if
                    n = min(len(b_mesh.vertices), len(kb.data))
                    morph_pos = [Vector(kb.data[i].co) for i in range(n)]
                    if n < len(b_mesh.vertices) :
                        morph_pos.extend \
                          (
                            Vector(b_mesh.vertices[i].co)
                            for i in range(n, len(b_mesh.vertices))
                          )
                    #end if
                    encode_mesh(b_mesh, morph_id, kb.name, b_material_slots, positions = morph_pos)
                    self._geometries[morph_id] = True
                    morph_ids.append(morph_id)
                    morph_weights.append(float(kb.value))
                #end for
                if morph_ids :
                    self._make_morph_controller(b_obj, geom, morph_ids, morph_weights)
                #end if
            #end if
        #end if
        matnodes = []
        src_mesh = getattr(b_obj, "data", None)
        uv_names = []
        if src_mesh is not None and hasattr(src_mesh, "uv_layers") :
            layers = list(src_mesh.uv_layers)
            if self._active_uv_only and src_mesh.uv_layers.active is not None :
                layers = [src_mesh.uv_layers.active]
            #end if
            uv_names = [uv.name for uv in layers]
        #end if
        for slotindex, slot in enumerate(b_material_slots) :
            # Empty material slots: skip binding (primitive symbol may still exist).
            if slot.material is None :
                continue
            #end if
            sname = slot.material.name
            if sname not in self._materials :
                self._materials[sname] = self.material(slot.material)
            #end if
            # Native InstanceWriter: bind_vertex_input uses the UV map name.
            inputs = [(uv_names[i], "TEXCOORD", str(i)) for i in range(len(uv_names))]
            matnodes.append \
              (
                MaterialNode
                  (
                    material_id(slot.material),
                    self._materials[sname],
                    inputs = inputs,
                  )
              )
        #end for
        skin = None
        if self._will_export_skin(b_obj) :
            if b_mesh is None :
                b_mesh, eval_obj, owned_mesh = self._object_to_mesh(b_obj)
                mesh_state = (b_mesh, eval_obj, owned_mesh)
            #end if
            if b_mesh is not None :
                skin = self._make_skin_controller(b_obj, geom, b_mesh)
            #end if
        #end if
        self._release_export_mesh(mesh_state)
        if skin is not None :
            cnode = ControllerNode(skin, matnodes)
            arm = _armature_object(b_obj)
            root_ids = self._armature_root_joints.get(arm.name, []) if arm is not None else []
            if not root_ids and arm is not None :
                skel_id = self._armature_ids.get(arm.name)
                if skel_id :
                    root_ids = [skel_id]
                #end if
            #end if
            for skel_id in reversed(root_ids) :
                cnode.xmlnode.insert(0, E.skeleton(idurl(skel_id)))
            #end for
            cnode.save()
            return [cnode]
        #end if
        return [GeometryNode(geom, matnodes)]
    #end obj_mesh

    def obj_armature(self, b_obj) :
        arm = b_obj.data
        bone_nodes = {}
        for bone in arm.bones :
            if self._deform_bones_only and not bone.use_deform :
                continue
            #end if
            nid = joint_node_id(b_obj, bone)
            sid = joint_sid(bone)
            xml = E.node(id = nid, name = bone.name, sid = sid, type = "JOINT")
            node = Node(id = nid, name = bone.name, xmlnode = xml)
            rest = _bone_rest_local(bone)
            if self._open_sim :
                loc, _rot, scale = rest.decompose()
                rest = Matrix.Translation(loc) @ Matrix.Diagonal(scale.to_4d())
            #end if
            self._append_node_transform(node, rest)
            if self._add_blender_extensions :
                extra = self.blender_technique(True, node)
                if extra is not None and bone.parent is not None and bone.use_connect :
                    extra.append(E.connect("true"))
                #end if
            #end if
            node.save()
            bone_nodes[bone.name] = node
        #end for
        roots = []
        root_ids = []
        for bone in arm.bones :
            node = bone_nodes.get(bone.name)
            if node is None :
                continue
            #end if
            if bone.parent is not None and bone.parent.name in bone_nodes :
                bone_nodes[bone.parent.name].children.append(node)
                bone_nodes[bone.parent.name].save()
            else :
                roots.append(node)
                root_ids.append(joint_node_id(b_obj, bone))
            #end if
        #end for
        arm_id = translate_id(b_obj.name)
        wrapper = Node(id = arm_id, name = b_obj.name)
        for root in roots :
            wrapper.children.append(root)
        #end for
        wrapper.save()
        self._armature_ids[b_obj.name] = arm_id
        self._armature_root_joints[b_obj.name] = root_ids
        return [wrapper]
    #end obj_armature

    def _make_skin_controller(self, b_obj, geom, b_mesh) :
        arm_obj = _armature_object(b_obj)
        if arm_obj is None or geom is None :
            return None
        #end if
        bones = []
        for bone in arm_obj.data.bones :
            if self._deform_bones_only and not bone.use_deform :
                continue
            #end if
            bones.append(bone)
        #end for
        if not bones :
            return None
        #end if
        joint_sids = [joint_sid(bone) for bone in bones]
        name_to_index = dict((bone.name, i) for i, bone in enumerate(bones))
        inv_binds = []
        arm_world = arm_obj.matrix_world
        prec = LIMITTED_PRECISION if self._limit_precision else None
        for bone in bones :
            rest_world = arm_world @ bone.matrix_local
            if self._apply_global_orientation :
                rest_world = self._orient @ rest_world
            #end if
            try :
                inv = rest_world.inverted()
            except ValueError :
                inv = Matrix.Identity(4)
            #end if
            inv_binds.extend(_dae_matrix_floats(inv, prec).split())
        #end for
        nverts = len(b_mesh.vertices)
        if nverts == 0 :
            return None
        #end if
        vcounts = []
        v_indices = []
        weights = []
        # Vertex order matches the Mesh position source (same indices as mesh.vertices).
        for vert in b_mesh.vertices :
            influences = []
            for group in b_obj.vertex_groups :
                jidx = name_to_index.get(group.name)
                if jidx is None :
                    continue
                #end if
                try :
                    w = group.weight(vert.index)
                except RuntimeError :
                    w = 0.0
                #end try
                if w > 1e-8 :
                    influences.append((jidx, w))
                #end if
            #end for
            if not influences :
                # Native ControllerExporter: vcount 0 when the vertex has no bone weights.
                vcounts.append(0)
                continue
            #end if
            total = sum(w for _j, w in influences) or 1.0
            vcounts.append(len(influences))
            for jidx, w in influences :
                widx = len(weights)
                weights.append(w / total)
                v_indices.extend((jidx, widx))
            #end for
        #end for
        ctl_id = skin_controller_id(arm_obj, b_obj)
        joints_id = ctl_id + JOINTS_SOURCE_ID_SUFFIX
        binds_id = ctl_id + BIND_POSES_SOURCE_ID_SUFFIX
        weights_id = ctl_id + WEIGHTS_SOURCE_ID_SUFFIX
        joints_src = E.source \
          (
            E.Name_array(" ".join(joint_sids), count = str(len(joint_sids)), id = joints_id + "-array"),
            E.technique_common
              (
                E.accessor
                  (
                    E.param(type = "Name", name = "JOINT"),
                    count = str(len(joint_sids)),
                    stride = "1",
                    source = idurl(joints_id + "-array"),
                  )
              ),
            id = joints_id,
          )
        binds_src = E.source \
          (
            E.float_array(" ".join(inv_binds), count = str(len(inv_binds)), id = binds_id + "-array"),
            E.technique_common
              (
                E.accessor
                  (
                    E.param(type = "float4x4", name = "TRANSFORM"),
                    count = str(len(joint_sids)),
                    stride = "16",
                    source = idurl(binds_id + "-array"),
                  )
              ),
            id = binds_id,
          )
        weights_src = E.source \
          (
            E.float_array(_fmt_floats(weights), count = str(len(weights)), id = weights_id + "-array"),
            E.technique_common
              (
                E.accessor
                  (
                    E.param(type = "float", name = "WEIGHT"),
                    count = str(len(weights)),
                    stride = "1",
                    source = idurl(weights_id + "-array"),
                  )
              ),
            id = weights_id,
          )
        bind_mat = b_obj.matrix_local.copy()
        if not self._apply_global_orientation :
            bind_mat = self._orient @ bind_mat
        #end if
        if self._limit_precision :
            bind_mat = _limit_precision_matrix(bind_mat)
        #end if
        bind_shape = E.bind_shape_matrix(_dae_matrix_floats(bind_mat, prec))
        skin = E.skin \
          (
            bind_shape,
            joints_src,
            binds_src,
            weights_src,
            E.joints
              (
                E.input(semantic = "JOINT", source = idurl(joints_id)),
                E.input(semantic = "INV_BIND_MATRIX", source = idurl(binds_id)),
              ),
            E.vertex_weights
              (
                E.input(semantic = "JOINT", source = idurl(joints_id), offset = "0"),
                E.input(semantic = "WEIGHT", source = idurl(weights_id), offset = "1"),
                E.vcount(" ".join(str(c) for c in vcounts)),
                E.v(" ".join(str(i) for i in v_indices)),
                count = str(nverts),
              ),
            source = idurl(geom.id),
          )
        xml = E.controller(skin, id = ctl_id, name = arm_obj.name)
        controller = _SkinControllerExport(ctl_id, xml)
        self._collada.controllers.append(controller)
        self._skin_controllers[b_obj.name] = controller
        return controller
    #end _make_skin_controller

    def _make_morph_controller(self, b_obj, geom, morph_ids, morph_weights) :
        "Native ControllerExporter::export_morph_controller (targets after the basis)."
        if geom is None or not morph_ids :
            return None
        #end if
        ctl_id = morph_controller_id(b_obj)
        targets_id = translate_id(b_obj.name) + TARGETS_SOURCE_ID_SUFFIX
        weights_id = translate_id(b_obj.name) + WEIGHTS_SOURCE_ID_SUFFIX
        n = len(morph_ids)
        targets_src = E.source \
          (
            E.IDREF_array(" ".join(morph_ids), count = str(n), id = targets_id + "-array"),
            E.technique_common
              (
                E.accessor
                  (
                    E.param(type = "IDREF", name = "IDREF"),
                    count = str(n),
                    stride = "1",
                    source = idurl(targets_id + "-array"),
                  )
              ),
            id = targets_id,
          )
        weights_src = E.source \
          (
            E.float_array(_fmt_floats(morph_weights), count = str(n), id = weights_id + "-array"),
            E.technique_common
              (
                E.accessor
                  (
                    E.param(type = "float", name = "MORPH_WEIGHT"),
                    count = str(n),
                    stride = "1",
                    source = idurl(weights_id + "-array"),
                  )
              ),
            id = weights_id,
          )
        morph = E.morph \
          (
            targets_src,
            weights_src,
            E.targets
              (
                E.input(semantic = "MORPH_TARGET", source = idurl(targets_id)),
                E.input(semantic = "MORPH_WEIGHT", source = idurl(weights_id)),
              ),
            source = idurl(geom.id),
            method = "NORMALIZED",
          )
        xml = E.controller(morph, id = ctl_id, name = b_obj.name + "-morph")
        controller = _SkinControllerExport(ctl_id, xml)
        self._collada.controllers.append(controller)
        return controller
    #end _make_morph_controller

    obj_type_handlers = \
        {
            "ARMATURE" : (obj_armature, DATABLOCK.ARMATURE),
            "CAMERA" : (obj_camera, DATABLOCK.CAMERA),
            "CURVE" : (obj_mesh, DATABLOCK.MESH),
            "EMPTY" : (obj_empty, DATABLOCK.EMPTY),
            "FONT" : (obj_mesh, DATABLOCK.MESH),
            "LIGHT" : (obj_light, DATABLOCK.LAMP),
            "MESH" : (obj_mesh, DATABLOCK.MESH),
            "META" : (obj_mesh, DATABLOCK.MESH),
            "SURFACE" : (obj_mesh, DATABLOCK.MESH),
        }

    def object(self, b_obj, parent = None) :
        handle_type = self.obj_type_handlers.get(b_obj.type)
        if handle_type != None :
            if parent != None :
                b_matrix = b_obj.matrix_local
            elif self._apply_global_orientation :
                b_matrix = self._orient @ b_obj.matrix_world
            else :
                b_matrix = b_obj.matrix_world
            #end if

            # Native: skinned mesh nodes write identity; bind_shape_matrix holds the rest.
            if self._will_export_skin(b_obj) :
                b_matrix = Matrix.Identity(4)
            #end if
            obj = handle_type[0](self, b_obj)
            is_node = len(obj) == 1 and isinstance(obj[0], Node)
            if is_node :
                obj = obj[0]
                assert b_matrix != None
                self._append_node_transform(obj, b_matrix)
                node = obj
            else :
                node = self.node(b_matrix, b_obj)
            #end if
            self._export_object_extras(node, b_obj)
            children = self._obj_children.get(b_obj.name)
            if children != None :
                for childname in sorted(children) :
                    self.object(bpy.data.objects[childname], parent = node)
                #end for
            #end if
            if parent != None :
                parent.children.append(node)
            else :
                self._scene.nodes.append(node)
            #end if
            if not is_node :
                node.children.extend(obj)
            #end if
        #end if
    #end object

    def material(self, b_mat) :
        shader = "lambert"
        effect_kwargs = \
            {
                "diffuse" : tuple(b_mat.diffuse_color[:3]),
                "double_sided" : not getattr(b_mat, "use_backface_culling", True),
            }
        effect_params = []
        if b_mat.diffuse_color[3] != 1.0 :
            effect_kwargs["transparency"] = b_mat.diffuse_color[3]
            effect_kwargs["transparent"] = OPAQUE_WHITE
        #end if
        if b_mat.use_nodes :
            b_shader = list(n for n in b_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            if len(b_shader) == 1 :
                # assume node setup somewhat resembles what importer creates
                b_shader = b_shader[0]
            else :
                b_shader = None
            #end if
            if b_shader != None :
                def get_input(name) :
                    names = name if isinstance(name, (tuple, list)) else (name,)
                    for candidate in names :
                        input = b_shader.inputs.get(candidate)
                        if input is not None and not input.is_linked :
                            return input.default_value
                        #end if
                    #end for
                    return None
                #end get_input

                def get_input_map(name) :
                    names = name if isinstance(name, (tuple, list)) else (name,)
                    map = None # to begin with
                    for candidate in names :
                        input = b_shader.inputs.get(candidate)
                        if input is None or not input.is_linked :
                            continue
                        #end if
                        links = input.links
                          # note docs say this takes O(N) in total nr links in node graph to compute
                        teximage = list \
                          (
                            l.from_node for l in links
                            if isinstance(l.from_node, bpy.types.ShaderNodeTexImage) and l.from_socket.name == "Color"
                          )
                        if len(teximage) != 0 :
                            teximage = teximage[0].image
                            if teximage.packed_file != None :
                                contents = teximage.packed_file.data
                            else :
                                contents = open(bpy.path.abspath(teximage.filepath), "rb").read()
                            #end if
                            out_filepath = self.write_ext_file \
                              (
                                category = EXT_FILE.TEXTURE,
                                obj_name = teximage.name,
                                filename = os.path.basename(teximage.filepath),
                                contents = contents
                              )
                            img_id = translate_id(teximage.name)
                            image = CImage(id = img_id, path = out_filepath)
                            surface = Surface(id = img_id + "-surface", img = image)
                            sampler = Sampler2D(id = img_id + "-sampler", surface = surface)
                            map = Map(sampler = sampler, texcoord = "ACTIVE_UV")
                            effect_params.extend([image, surface, sampler])
                            break
                        #end if
                    #end for
                    return map
                #end get_input_map

                value = get_input("Base Color")
                if value != None :
                    effect_kwargs["diffuse"] = value[:3]
                elif self._export_textures :
                    map = get_input_map("Base Color")
                    if map != None :
                        effect_kwargs["diffuse"] = map
                    #end if
                #end if
                # todo: support maps for more inputs
                value = get_input("Metallic")
                metallic = True
                if value == None or value == 0 :
                    value = get_input(("Specular IOR Level", "Specular"))
                    metallic = False
                #end if
                if value != None and value != 0 :
                    shader = "phong" # do I care about “blinn”?
                    if metallic :
                        effect_kwargs["reflective"] = effect_kwargs["diffuse"]
                    else :
                        effect_kwargs["reflective"] = (1, 1, 1)
                    #end if
                    effect_kwargs["reflectivity"] = value
                #end if
                value = get_input("Alpha")
                if value != None and value != 1.0 :
                    effect_kwargs["transparency"] = value
                    effect_kwargs["transparent"] = OPAQUE_WHITE
                      # overridden by Transmission (below) if any
                #end if
                value = get_input(("Transmission Weight", "Transmission"))
                if value != None and value != 0 :
                    effect_kwargs["transparency"] = value
                    # Never reuse the diffuse map as <transparent>. Native
                    # COLLADA uses an A_ONE color; a texture here makes RGB
                    # images with no alpha render fully invisible.
                    effect_kwargs["transparent"] = OPAQUE_WHITE
                    value = get_input("IOR")
                    if value != None :
                        effect_kwargs["index_of_refraction"] = value
                    #end if
                #end if
            else :
                pass # give up for now
            #end if
        else :
            # quick fudge based only on Viewport Display settings
            if b_mat.metallic > 0 or b_mat.roughness < 1 :
                shader = "phong" # do I care about “blinn”?
                try :
                    shininess = 1 / b_mat.roughness - 1
                      # inverse of formula used in importer
                except ZeroDivisionError :
                    shininess = math.inf
                #end try
                shininess = min(shininess, 10000) # just some arbitrary finite upper limit
                effect_kwargs["reflectivity"] = b_mat.specular_intensity
                effect_kwargs["shininess"] = shininess
                if b_mat.metallic > 0 :
                    # not paying attention to actual value of b_mat.metallic!
                    effect_kwargs["reflective"] = b_mat.specular_color[:3]
                else :
                    effect_kwargs["reflective"] = (1, 1, 1)
                #end if
            #end if
        #end if
        effect = Effect(effect_id(b_mat), effect_params, shader, **effect_kwargs)
        sanitize_effect(effect, shader, set(effect_kwargs.keys()))
        mat = Material(material_id(b_mat), b_mat.name, effect)
        self._collada.effects.append(effect)
        self._collada.materials.append(mat)
        return mat
    #end material

    @staticmethod
    def matrix(b_matrix) :
        return \
            MatrixTransform \
              (
                np.array
                  (
                    [e for r in tuple(map(tuple, b_matrix)) for e in r],
                    dtype = np.float32
                  )
              )
    #end matrix

#end ColladaExport

def save(op, context, filepath, directory, **kwargs) :
    objects = context.scene.objects
    exporter = None
    try :
        exporter = ColladaExport(objects, filepath, directory, kwargs)
        # Export roots: objects with no parent in the export set (see __init__).
        roots = exporter._obj_children.get(None, ())
        for name in sorted(roots) :
            exporter.object(bpy.data.objects[name])
        #end for
        exporter.save()
    except Exception :
        if exporter is not None :
            exporter.abort_temp()
        #end if
        raise
    #end try
    return {"FINISHED"}
#end save
