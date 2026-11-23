import sys
import os
import math
from numbers import \
    Real
import io
import time
import zipfile
import tempfile
import shutil
import traceback

import bpy
from mathutils import Matrix, Vector

from collada import Collada
from collada.camera import PerspectiveCamera, OrthographicCamera
from collada.common import DaeBrokenRefError, DaeObject, tag
from collada.light import AmbientLight, DirectionalLight, PointLight, SpotLight
from collada.material import Map
from collada.polylist import Polylist, BoundPolylist
from collada.primitive import BoundPrimitive
from collada.controller import BoundMorph, BoundSkin, Morph, Skin
from collada.scene import (
    Scene, Node, NodeNode, CameraNode, ControllerNode, GeometryNode, LightNode,
)
from collada.triangleset import TriangleSet, BoundTriangleSet
from collada.xmlutil import etree as ElementTree

try :
    import numpy as np
except ImportError :
    np = None
#end try

MAX_NAME_LENGTH = 63 # note this is bytes, not characters
DEG = math.pi / 180 # angle unit conversion factor

# Match Blender 4.5 MeshImporter::is_nice_mesh: reject/skip bad topology
# instead of feeding invalid loops into from_pydata (common crash source).
def _sanitize_faces(faces, nverts, smooth_shade = None, material_assignments = None, uvcoords = None) :
    clean_faces = []
    clean_smooth = []
    clean_mats = []
    clean_uvs = None if uvcoords is None else [[] for _ in uvcoords]
    rejected = 0
    for i, face in enumerate(faces) :
        if face is None :
            rejected += 1
            continue
        #end if
        try :
            idxs = tuple(int(v) for v in face)
        except (TypeError, ValueError) :
            rejected += 1
            continue
        #end try
        if len(idxs) < 3 :
            rejected += 1
            continue
        #end if
        if any(v < 0 or v >= nverts for v in idxs) :
            rejected += 1
            continue
        #end if
        if len(set(idxs)) < 3 :
            rejected += 1
            continue
        #end if
        clean_faces.append(idxs)
        if smooth_shade is not None :
            clean_smooth.append(bool(smooth_shade[i]) if i < len(smooth_shade) else False)
        #end if
        if material_assignments is not None :
            clean_mats.append(material_assignments[i] if i < len(material_assignments) else 0)
        #end if
        if clean_uvs is not None :
            for layer_i, layer in enumerate(uvcoords) :
                if i < len(layer) :
                    coords = layer[i]
                    # Pad/truncate UV corners to face length.
                    if len(coords) >= len(idxs) :
                        clean_uvs[layer_i].append([tuple(coords[j]) for j in range(len(idxs))])
                    else :
                        pad = list(coords) + [(0.0, 0.0)] * (len(idxs) - len(coords))
                        clean_uvs[layer_i].append([tuple(c) for c in pad])
                    #end if
                else :
                    clean_uvs[layer_i].append([(0.0, 0.0)] * len(idxs))
                #end if
            #end for
        #end if
    #end for
    return clean_faces, clean_smooth, clean_mats, clean_uvs, rejected
#end _sanitize_faces

def _face_index_list(prim) :
    "Fast face index extraction; avoid per-triangle Python objects when possible."
    vi = getattr(prim, "vertex_index", None)
    if vi is not None :
        try :
            if np is not None :
                arr = np.asarray(vi)
                if arr.size == 0 :
                    return []
                #end if
                if arr.ndim == 2 :
                    return [tuple(int(x) for x in row) for row in arr]
                #end if
            #end if
            return [tuple(int(x) for x in row) for row in vi]
        except Exception :
            pass
        #end try
    #end if
    # Fallback: pycollada element iteration (slow on large meshes).
    return [tuple(int(x) for x in getattr(elt, "indices")) for elt in prim]
#end _face_index_list

def set_shader_input(shader, names, value) :
    "Set the first matching Principled BSDF input among Blender version aliases."
    if isinstance(names, str) :
        names = (names,)
    #end if
    for name in names :
        sock = shader.inputs.get(name)
        if sock is not None :
            sock.default_value = value
            return True
        #end if
    #end for
    return False
#end set_shader_input

def link_shader_input(node_graph, from_socket, shader, names) :
    "Link to the first matching Principled BSDF input among version aliases."
    if isinstance(names, str) :
        names = (names,)
    #end if
    for name in names :
        sock = shader.inputs.get(name)
        if sock is not None :
            node_graph.links.new(from_socket, sock)
            return True
        #end if
    #end for
    return False
#end link_shader_input

def set_material_transparency(b_mat, alpha) :
    "Apply alpha-related material flags across Blender 4.x / 5.x APIs."
    if hasattr(b_mat, "blend_method") :
        try :
            b_mat.blend_method = "BLEND"
        except (TypeError, ValueError) :
            pass
        #end try
    #end if
    if hasattr(b_mat, "surface_render_method") :
        try :
            b_mat.surface_render_method = "BLENDED"
        except (TypeError, ValueError) :
            pass
        #end try
    #end if
    if len(b_mat.diffuse_color) > 3 :
        b_mat.diffuse_color[3] = alpha
    #end if
#end set_material_transparency

class DATABLOCK :
    ARMATURE = "ARMATURE"
    CAMERA = "CAMERA"
    EMPTY = "EMPTY"
    LAMP = "LAMP"
    MATERIAL = "MATERIAL"
    MESH = "MESH"
    SCENE = "SCENE"
#end DATABLOCK

# Scene-graph instance types that become Blender objects (not group Empties).
# ControllerNode was previously skipped, which dropped every skinned mesh.
_INSTANCE_NODES = (CameraNode, ControllerNode, GeometryNode, LightNode)

def unurlid(uid) :
    assert uid.startswith("#")
    return uid[1:]
#end unurlid

def collada_label(obj) :
    "Human-readable COLLADA label: prefer XML name (SketchUp groups), then id."
    xml = getattr(obj, "xmlnode", None)
    if xml is not None :
        label = xml.get("name")
        if label :
            return label
        #end if
    #end if
    label = getattr(obj, "name", None)
    if label :
        return label
    #end if
    label = getattr(obj, "id", None)
    if label :
        return label
    #end if
    return None
#end collada_label

def _matrix_is_identity(mat, eps = 1e-5) :
    "True when mat is effectively a 4x4 identity (after unit conversion)."
    for i in range(4) :
        for j in range(4) :
            expect = 1.0 if i == j else 0.0
            if abs(mat[i][j] - expect) > eps :
                return False
            #end if
        #end for
    #end for
    return True
#end _matrix_is_identity

def _node_has_meaningful_name(src) :
    """
    True when the COLLADA node has a useful display name worth keeping as an Empty.
    Bare/missing names and names that only echo the XML id are not meaningful.
    """
    xml = getattr(src, "xmlnode", None)
    name = None
    nid = getattr(src, "id", None)
    if xml is not None :
        name = xml.get("name")
        if not nid :
            nid = xml.get("id")
        #end if
    #end if
    if not name :
        return False
    #end if
    if nid and name == nid :
        return False
    #end if
    # Machine-style ids (ID123, node_45) are not worth an Empty by themselves.
    compact = name.replace("-", "").replace("_", "")
    if compact.upper().startswith("ID") and compact[2:].isalnum() :
        return False
    #end if
    if name.lower().startswith("node") and compact[4:].isdigit() :
        return False
    #end if
    return True
#end _node_has_meaningful_name

def _node_src(node) :
    return node.node if isinstance(node, NodeNode) else node
#end _node_src

def _node_is_joint(src) :
    "True when a COLLADA <node> is a JOINT (skin skeleton bone)."
    xml = getattr(src, "xmlnode", None)
    if xml is None :
        return False
    #end if
    return (xml.get("type") or "").upper() == "JOINT"
#end _node_is_joint

def _joint_key(src) :
    "Preferred skin-joint identifier: sid, then id, then name."
    xml = getattr(src, "xmlnode", None)
    if xml is None :
        return getattr(src, "id", None)
    #end if
    return xml.get("sid") or xml.get("id") or xml.get("name")
#end _joint_key

def _xml_skeleton_id(xmlnode) :
    "Read <skeleton>#JointId</skeleton> from an instance_controller, if present."
    if xmlnode is None :
        return None
    #end if
    skel = xmlnode.find(tag("skeleton"))
    if skel is None or not (skel.text or "").strip() :
        return None
    #end if
    return (skel.text or "").strip().lstrip("#")
#end _xml_skeleton_id

def _float_weight(value) :
    "pycollada weight sources yield scalars or 1-element arrays."
    try :
        return float(value)
    except (TypeError, ValueError) :
        pass
    #end try
    try :
        return float(value[0])
    except Exception :
        return 0.0
    #end try
#end _float_weight

def _bound_geometry_from_controller(bctl) :
    "Resolve a bound/unbound skin or morph controller to BoundGeometry."
    if isinstance(bctl, BoundSkin) :
        return getattr(bctl, "geometry", None)
    #end if
    if isinstance(bctl, BoundMorph) :
        morph = getattr(bctl, "original", None)
        src_geom = getattr(morph, "source_geometry", None)
        if src_geom is None :
            return None
        #end if
        matrix = getattr(bctl, "matrix", None)
        materials = getattr(bctl, "materialnodebysymbol", None) or {}
        try :
            return src_geom.bind(matrix, materials)
        except Exception :
            return None
        #end try
    #end if
    if isinstance(bctl, Skin) :
        geom = getattr(bctl, "geometry", None)
        if geom is None :
            return None
        #end if
        try :
            return geom.bind(bctl.bind_shape_matrix, {})
        except Exception :
            return None
        #end try
    #end if
    if isinstance(bctl, Morph) :
        src_geom = getattr(bctl, "source_geometry", None)
        if src_geom is None :
            return None
        #end if
        try :
            identity = np.identity(4) if np is not None else \
                ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
            return src_geom.bind(identity, {})
        except Exception :
            return None
        #end try
    #end if
    return getattr(bctl, "geometry", None)
#end _bound_geometry_from_controller

def _controller_skin(bctl) :
    if isinstance(bctl, BoundSkin) :
        return bctl.skin
    #end if
    if isinstance(bctl, Skin) :
        return bctl
    #end if
    return getattr(bctl, "skin", None)
#end _controller_skin

def _controller_skeleton_map(scene) :
    "Map controller id → skeleton joint id from instance_controller elements."
    mapping = {}

    def walk(node) :
        if isinstance(node, ControllerNode) :
            cid = getattr(getattr(node, "controller", None), "id", None)
            skel = _xml_skeleton_id(getattr(node, "xmlnode", None))
            if cid and skel :
                mapping[cid] = skel
            #end if
        #end if
        children = ()
        if isinstance(node, Scene) :
            children = node.nodes
        elif isinstance(node, Node) :
            children = node.children
        elif isinstance(node, NodeNode) :
            children = node.node.children
        #end if
        for child in children :
            walk(child)
        #end for
    #end walk

    if scene is not None :
        walk(scene)
    #end if
    return mapping
#end _controller_skeleton_map

def _controller_object_matrix(bctl) :
    "Instance matrix including bind_shape so rest-pose verts line up with joints."
    mat = Matrix.Identity(4)
    raw = getattr(bctl, "matrix", None)
    if raw is not None :
        try :
            mat = Matrix(raw)
        except Exception :
            mat = Matrix.Identity(4)
        #end try
    #end if
    skin = _controller_skin(bctl)
    bsm = getattr(skin, "bind_shape_matrix", None) if skin is not None else None
    if bsm is not None :
        try :
            mat = mat @ Matrix(bsm)
        except Exception :
            pass
        #end try
    #end if
    return mat
#end _controller_object_matrix

class _ImportProgress :
    "Best-effort Blender status-bar progress for long COLLADA imports."

    def __init__(self, wm, total_steps = 100) :
        self.wm = wm
        self.total_steps = max(int(total_steps), 1)
        self.current = 0
        self._active = False
        if self.wm is not None :
            try :
                self.wm.progress_begin(0, 100)
                self._active = True
                self.wm.progress_update(0)
            except Exception :
                self._active = False
            #end try
        #end if
    #end __init__

    def update_fraction(self, fraction) :
        if not self._active :
            return
        #end if
        pct = max(0, min(100, int(round(fraction * 100.0))))
        try :
            self.wm.progress_update(pct)
        except Exception :
            pass
        #end try
    #end update_fraction

    def set_steps(self, total_steps) :
        self.total_steps = max(int(total_steps), 1)
        self.current = 0
    #end set_steps

    def step(self, n = 1) :
        self.current = min(self.current + n, self.total_steps)
        self.update_fraction(self.current / float(self.total_steps))
    #end step

    def end(self) :
        if not self._active :
            return
        #end if
        try :
            self.wm.progress_end()
        except Exception :
            pass
        #end try
        self._active = False
    #end end
#end _ImportProgress

def find_main_shader(in_datablock, type_name) :
    node_graph = in_datablock.node_tree
    shader = list(n for n in node_graph.nodes if n.type == type_name)[0]
    return shader, node_graph
#end find_main_shader

class ColladaImport :
    def __init__(self, ctx, collada, filepath, **kwargs) :
        root_elem = collada.xmlnode.getroot()
        if root_elem.tag.startswith('{'):
            # Format: {namespace_uri}tagname → extract namespace_uri
            namespace_uri = root_elem.tag[1:].split('}')[0]
        else:
            # Fallback to official COLLADA namespace (per spec)
            namespace_uri = "http://www.collada.org/2005/11/COLLADASchema"
        self.DAE_NS = {"dae": namespace_uri}
        
        basename = os.path.basename(filepath)
        self._ctx = ctx
        self._collada = collada
        self._recognize_blender_extensions = kwargs["recognize_blender_extensions"]
        self._transformation = kwargs["transformation"]
        self._name_map = {}
        self._name_revmap = {}
        self._untitledcount = 0
        self._units = collada.assetInfo.unitmeter
        if self._units == None :
            self._units = 1
        #end if
        orient = collada.assetInfo.upaxis
        if orient == "Z_UP" :
            self._orient = Matrix.Identity(4)
        elif orient == "X_UP" :
            self._orient = Matrix.Rotation(120 * DEG, 4, Vector(1, -1, 1))
        else : # "Y_UP" or unspecified
            self._orient = Matrix.Rotation(90 * DEG, 4, "X")
        #end if
        self._id_prefixes = None
        root_technique = self.get_blender_technique(True, self._collada.xmlnode.getroot())
        if root_technique != None :
            id_prefixes = root_technique.find(tag("id_prefixes"))
            if id_prefixes != None :
                self._id_prefixes = {}
                for prefix in id_prefixes.findall(tag("prefix")) :
                    name = prefix.get("name")
                    value = prefix.get("value")
                    if name != None and value != None :
                        self._id_prefixes[name] = value
                    #end if
                #end for
            #end if
        #end if
        self._imported = {}
        self._collection = bpy.data.collections.new(basename)
        self._ctx.scene.collection.children.link(self._collection)
        # Skin / controller tracking (issue #3): instance_controller meshes + JOINT empties.
        self._skin_imports = []
        self._joint_records = []
    #end __init__

    def get_blender_technique(self, as_extra, obj) :
        # experimental: add Blender-specific attributes via a custom <technique>.
        blendstuff = None
        if self._recognize_blender_extensions :
            if isinstance(obj, DaeObject) :
                obj = obj.xmlnode
            #end if
            if as_extra :
                parent = obj.find(tag("extra"))
            else :
                parent = obj
            #end if
            if parent != None :
                blendstuff = parent.find(tag("technique") + "[@profile=\"BLENDER028\"]")
            #end if
        #end if
        return blendstuff
    #end get_blender_technique

    def apply_blender_technique(self, as_extra, obj, b_data, attribs) :
        # get and apply any custom technique settings for this object.
        blendstuff = self.get_blender_technique(as_extra, obj)
        if blendstuff != None :
            for tagname, parse, attrname in attribs :
                if hasattr(b_data, attrname) :
                    subtag = blendstuff.find(tag(tagname))
                    if subtag != None :
                        try :
                            setattr(b_data, attrname, parse(subtag.text))
                        except ValueError as err :
                            sys.stderr.write \
                              (
                                    "import_collada: error setting %s attribute for %s: %s\n"
                                %
                                    (
                                        attrname,
                                        b_data.name,
                                        str(err)
                                    )
                              )
                        #end try
                    #end if
                #end if
            #end for
        #end if
        return blendstuff != None
    #end apply_blender_technique

    def name(self, prefix_name, obj) :
        "Trying to get efficient and human readable name, working around" \
        " Blender’s object name limitations."

        def truncate_bytes(s, maxlen) :
            "returns string s truncated as necessary so its UTF-8 encoding" \
            " does not exceed maxlen bytes."
            b = s.encode()[:maxlen]
            while True :
                try :
                    s = b.decode()
                except UnicodeDecodeError as err :
                    # assume truncated UTF-8 encoding
                    b = b[:err.start]
                else :
                    break
                #end try
            #end while
            return s
        #end truncate_bytes

    #begin name
        # Prefer COLLADA name for Empties/groups (SketchUp), otherwise id.
        label = collada_label(obj)
        if prefix_name == DATABLOCK.EMPTY and label :
            origname = label
        elif hasattr(obj, "id") and obj.id != None :
            origname = obj.id
            if self._id_prefixes != None :
                prefix = self._id_prefixes.get(prefix_name)
                if prefix != None and origname.startswith(prefix) :
                    origname = origname[len(prefix):]
                #end if
            #end if
        elif label :
            origname = label
        else :
            origname = None
        #end if
        if origname != None :
            # Key by type+id when available so duplicate group names stay distinct.
            map_key = (prefix_name, getattr(obj, "id", None) or origname)
            if map_key in self._name_map :
                usename = self._name_map[map_key]
            else :
                usename = truncate_bytes(str(origname), MAX_NAME_LENGTH)
                seq = 0
                while usename in self._name_revmap :
                    seq += 1
                    suffix = "-%0.3d" % seq
                    suffix_len = len(suffix.encode())
                    assert suffix_len < MAX_NAME_LENGTH
                    usename = \
                        "%s%s" % (truncate_bytes(str(origname), MAX_NAME_LENGTH - suffix_len), suffix)
                #end while
                self._name_map[map_key] = usename
                self._name_revmap[usename] = map_key
            #end if
        else :
            origname = id(obj) # non-string type to avoid conflicting with any actual XML ID
            if origname in self._name_map :
                usename = self._name_map[origname]
            else :
                self._untitledcount += 1
                usename = "untitled %0.3d" % self._untitledcount
                  # space in name means it can never conflict with any actual XML ID
                self._name_map[origname] = usename
                self._name_revmap[usename] = origname
            #end if
        #end if
        return usename
    #end name

    def get_already_imported(self, category, b_name) :
        result = None
        names = self._imported.get(category)
        if names != None :
            result = names.get(b_name)
        #end if
        return result
    #end get_already_imported

    def set_already_imported(self, category, b_name, b_name_assigned) :
        if not self._transform("APPLY") :
            if category not in self._imported :
                self._imported[category] = {}
            #end if
            names = self._imported[category]
            assert b_name not in names
            names[b_name] = b_name_assigned
        #end if
    #end set_already_imported

    def _transform(self, t) :
        return self._transformation == t
    #end _transform

    def _convert_units_matrix(self, mat) :
        "converts the translation part of Matrix mat from the specified" \
        " units in the Collada file to Blender units."
        mat = mat.copy()
        for i in range(3) :
            mat[i][3] *= self._units
        #end for
        return mat
    #end _convert_units_matrix

    def _convert_units_verts(self, verts) :
        "converts a sequence of vectors from the specified" \
        " units in the Collada file to Blender units."
        return \
            list(self._units * Vector(v) for v in verts)
    #end _convert_units_verts

    def camera(self, bcam) :

        def fudge_div(num, den) :
            # needed to cope with some problem files.
            try :
                result = num / den
            except ZeroDivisionError :
                result = num
            #end if
            return result
        #end fudge_div

    #begin camera
        b_name = self.name(DATABLOCK.CAMERA, bcam.original)
        # todo: shared datablocks
        b_cam = bpy.data.cameras.new(b_name)
        b_obj = bpy.data.objects.new(b_cam.name, b_cam)
        if isinstance(bcam.original, PerspectiveCamera) :
            b_cam.type = "PERSP"
            prop = b_cam.bl_rna.properties.get("lens_unit")
            if "DEGREES" in prop.enum_items :
                b_cam.lens_unit = "DEGREES"
            elif "FOV" in prop.enum_items :
                b_cam.lens_unit = "FOV"
            else :
                b_cam.lens_unit = prop.default
            #end if
            # I don’t actually support preservation of aspect ratios,
            # since in Blender that is a rendering setting, not a
            # camera setting. For now I just use the maximum of the
            # horizontal and vertical views.
            b_cam.angle = \
                max \
                  (( # “None” marks cases which shouldn’t occur
                        None, # bcam.aspect_ratio = None and bcam.yfov = None and bcam.xfov = None
                        None, # bcam.aspect_ratio = None and bcam.yfov = None and bcam.xfov ≠ None
                        None, # bcam.aspect_ratio = None and bcam.yfov ≠ None and bcam.xfov = None
                        lambda : (bcam.yfov * DEG, bcam.xfov * DEG),
                          # bcam.aspect_ratio = None and bcam.yfov ≠ None and bcam.xfov ≠ None
                        None, # bcam.aspect_ratio ≠ None and bcam.yfov = None and bcam.xfov = None
                        lambda :
                            (
                                2 * math.atan(fudge_div(math.tan(bcam.xfov * DEG / 2),  bcam.aspect_ratio)),
                                bcam.xfov * DEG
                            ),
                          # bcam.aspect_ratio ≠ None and bcam.yfov = None and bcam.xfov ≠ None
                        lambda :
                            (
                                bcam.yfov * DEG,
                                2 * math.atan(math.tan(bcam.yfov * DEG / 2) * bcam.aspect_ratio)
                            ),
                          # bcam.aspect_ratio ≠ None and bcam.yfov ≠ None and bcam.xfov = None
                        None, # bcam.aspect_ratio ≠ None and bcam.yfov ≠ None and bcam.xfov ≠ None
                  )[
                        (bcam.aspect_ratio != None) << 2
                    |
                        (bcam.yfov != None) << 1
                    |
                        (bcam.xfov != None)
                  ]()
                )
        elif isinstance(bcam.original, OrthographicCamera) :
            b_cam.type = "ORTHO"
            # xmag/ymag are half-extents (Blender 4.5); ortho_scale is full width.
            half = \
                max \
                  (( # “None” marks cases which shouldn’t occur
                        None, # bcam.aspect_ratio = None and bcam.ymag = None and bcam.xmag = None
                        None, # bcam.aspect_ratio = None and bcam.ymag = None and bcam.xmag ≠ None
                        None, # bcam.aspect_ratio = None and bcam.ymag ≠ None and bcam.xmag = None
                        lambda : (bcam.ymag, bcam.xmag),
                          # bcam.aspect_ratio = None and bcam.ymag ≠ None and bcam.xmag ≠ None
                        None, # bcam.aspect_ratio ≠ None and bcam.ymag = None and bcam.xmag = None
                        lambda : (fudge_div(bcam.xmag, bcam.aspect_ratio), bcam.xmag),
                          # bcam.aspect_ratio ≠ None and bcam.ymag = None and bcam.xmag ≠ None
                        lambda : (bcam.ymag, bcam.ymag * bcam.aspect_ratio),
                          # bcam.aspect_ratio ≠ None and bcam.ymag ≠ None and bcam.xmag = None
                        None, # bcam.aspect_ratio ≠ None and bcam.ymag ≠ None and bcam.xmag ≠ None
                  )[
                        (bcam.aspect_ratio != None) << 2
                    |
                        (bcam.ymag != None) << 1
                    |
                        (bcam.xmag != None)
                  ]()
                )
            b_cam.ortho_scale = 2.0 * half * self._units
        #end if
        if bcam.znear != None :
            b_cam.clip_start = self._units * bcam.znear
        #end if
        if bcam.zfar != None :
            b_cam.clip_end = self._units * bcam.zfar
        #end if
        self._collection.objects.link(b_obj)
        return b_obj
    #end camera

    def light(self, blight) :
        result = None
        b_name = self.name(DATABLOCK.LAMP, blight.original)
        # todo: shared datablocks
        light_type = tuple \
          (
            elt
            for elt in
                (
                    (AmbientLight, "POINT"),
                    (DirectionalLight, "SUN"),
                    (PointLight, "POINT"),
                    (SpotLight, "SPOT"),
                )
            if isinstance(blight.original, elt[0])
          )
        if len(light_type) != 0 :
            light_type = light_type[0]
            b_light = bpy.data.lights.new(b_name, type = light_type[1])
            b_light.color = blight.original.color[:3]
            if isinstance(blight.original, AmbientLight) :
                # implement as a very large “point” light source
                # Alternatively, could use this to set background intensity instead.
                b_light.shadow_soft_size = 10000 # the larger, the softer the terminators
                b_light.use_shadow = False
                b_light.use_nodes = True # note: Cycles-only
                b_light.cycles.cast_shadow = False
                b_shader, node_graph = find_main_shader(b_light, "EMISSION")
                node_x, node_y = b_shader.location
                falloff = node_graph.nodes.new("ShaderNodeLightFalloff")
                falloff.location = (node_x - 200, node_y)
                falloff.inputs["Strength"].default_value = b_shader.inputs["Strength"].default_value
                node_graph.links.new \
                  (
                    falloff.outputs["Constant"],
                    b_shader.inputs["Strength"],
                  )
            else :
                for attr, battr, conv in \
                    (
                        ("falloff_ang", "spot_size", lambda ang : ang * DEG),
                        ("falloff_exp", "spot_blend", lambda exp : 1 / (1 + exp)),
                          # some reasonable conversion
                    ) \
                :
                    if hasattr(b_light, battr) :
                        val = getattr(blight, attr, None)
                        if val != None :
                            setattr(b_light, battr, conv(val))
                        #end if
                    #end if
                #end for
                atten = filter \
                  (
                    lambda val : val[1] != None and val[1] != 0,
                    (
                        (a[0], getattr(blight, a[1], None))
                        for a in ((0, "constant_att"), (1, "linear_att"), (2, "quad_att"))
                    )
                  )
                # Note I can implement only one falloff factor; trying to perform
                # various arithmetic on the different outputs from the ShaderNodeLightFalloff
                # node doesn’t seem to produce meaningful results.
                atten = sorted(atten, key = lambda a : a[1], reverse = True)
                  # stable sort to prefer constant over linear over quadratic
                if len(atten) != 0 :
                    pow, factor = atten[0]
                    b_light.use_nodes = True # note: Cycles-only
                    b_shader, node_graph = find_main_shader(b_light, "EMISSION")
                    node_x, node_y = b_shader.location
                    falloff = node_graph.nodes.new("ShaderNodeLightFalloff")
                    falloff.location = (node_x - 200, node_y)
                    falloff.inputs["Strength"].default_value = \
                        b_shader.inputs["Strength"].default_value / factor
                    node_graph.links.new \
                      (
                        falloff.outputs[("Constant", "Linear", "Quadratic")[pow]],
                        b_shader.inputs["Strength"],
                      )
                #end if
                self.apply_blender_technique \
                  (
                    True,
                    blight.original,
                    b_light,
                    [
                        ("angle", float, "angle"),
                        ("power", float, "energy"),
                        ("shadow_soft_size", float, "shadow_soft_size"),
                        ("spot_blend", float, "spot_blend"),
                        ("spot_size", float, "spot_size"),
                    ]
                  )
            #end if
            b_obj = bpy.data.objects.new(b_name, b_light)
            self._collection.objects.link(b_obj)
            result = b_obj
        #end if
        return result
    #end light

    def geometry(self, bgeom) :

        def is_flat_face(normal) :
            if not normal :
                return True
            #end if
            a = Vector(normal[0])
            for n in normal[1:] :
                dp = a.dot(Vector(n))
                if dp < 0.99999 or dp > 1.00001 :
                    return False
                #end if
            #end for
            return True
        #end is_flat_face

    #begin geometry
        blendstuff = self.get_blender_technique(True, bgeom.original.xmlnode)
        b_materials = {}
        for sym, matnode in bgeom.materialnodebysymbol.items() :
            mat = matnode.target
            b_matname = self.name(DATABLOCK.MATERIAL, mat)
            existing = bpy.data.materials.get(b_matname)
            if existing is None :
                b_matname = self.material(mat, b_matname)
                existing = bpy.data.materials.get(b_matname)
            #end if
            b_materials[sym] = existing
        #end for

        if self._transform("APPLY") :
            primitives = bgeom.primitives()
            b_meshname = self.name(DATABLOCK.MESH, bgeom)
        else :
            primitives = bgeom.original.primitives
            b_meshname = self.name(DATABLOCK.MESH, bgeom.original)
        #end if
        materials = []
        already = self.get_already_imported("MESH", b_meshname)
        new_mesh = self._transform("APPLY") or already is None
        if new_mesh :
            verts = []
            vert_starts = {}
            faces = []
            smooth_shade = []
            got_normals = False
            material_assignments = []
            uvcoords = None
            uvcoord_ids = None
            # Large meshes: skip O(faces*corners) flat-shade probes (native
            # importer either uses custom normals or leaves shading alone).
            detect_smooth = True
            for p in primitives :
                if isinstance(p, BoundPrimitive) :
                    b_mat_key = p.original.material
                    op = p.original
                else :
                    b_mat_key = p.material
                    op = p
                #end if
                b_mat = b_materials.get(b_mat_key, None)
                materials.append(b_mat)

                if not isinstance(p, (TriangleSet, BoundTriangleSet, Polylist, BoundPolylist)) :
                    continue
                #end if
                if "VERTEX" not in op.sources or not op.sources["VERTEX"] :
                    continue
                #end if

                these_faces = _face_index_list(p)
                if not these_faces :
                    continue
                #end if

                verts_source_id = op.sources["VERTEX"][0][2]
                if verts_source_id in vert_starts :
                    vert_start = vert_starts[verts_source_id]
                else :
                    vert_start = len(verts)
                    vert_starts[verts_source_id] = vert_start
                    try :
                        verts.extend(tuple(v) for v in p.vertex)
                    except Exception as exc :
                        sys.stderr.write(
                            "import_collada: skipped vertices for %s: %s\n"
                            % (b_meshname, exc)
                        )
                        continue
                    #end try
                #end if

                nfaces = len(these_faces)
                if detect_smooth and nfaces > 20000 :
                    detect_smooth = False
                #end if

                these_smooth_shade = [True] * nfaces
                these_material_assignments = [len(materials) - 1] * nfaces
                has_normals = getattr(p, "normal", None) is not None
                if has_normals and detect_smooth :
                    try :
                        these_normcoords = list(p.normal)
                        ni = getattr(p, "normal_index", None)
                        if ni is None :
                            these_normindices = [
                                tuple(getattr(elt, "normal_indices")) for elt in p
                            ]
                        else :
                            these_normindices = [tuple(int(x) for x in row) for row in ni]
                        #end if
                        if len(these_normindices) == nfaces :
                            for i in range(nfaces) :
                                try :
                                    these_smooth_shade[i] = not is_flat_face(
                                        [
                                            these_normcoords[j]
                                            for j in these_normindices[i]
                                        ]
                                    )
                                except Exception :
                                    these_smooth_shade[i] = True
                                #end try
                            #end for
                        #end if
                        got_normals = True
                    except Exception :
                        got_normals = True  # still mark smooth-capable
                    #end try
                elif has_normals :
                    got_normals = True
                #end if

                if "TEXCOORD" in op.sources and len(op.sources["TEXCOORD"]) != 0 :
                    n_uv = len(op.sources["TEXCOORD"])
                    if uvcoords is None :
                        uvcoords = [
                            [[(0.0, 0.0)] * len(f) for f in faces]
                            for _ in range(n_uv)
                        ]
                        uvcoord_ids = tuple(s[2] for s in op.sources["TEXCOORD"])
                    elif len(uvcoords) != n_uv :
                        sys.stderr.write(
                            "import_collada: UV layer count mismatch in %s; "
                            "ignoring extra UV sets\n" % b_meshname
                        )
                    #end if
                    if uvcoords is not None and len(uvcoords) == n_uv :
                        # Prefer index arrays over Triangle object iteration.
                        wrote = False
                        try :
                            tex_sets = getattr(p, "texcoord_indexset", None)
                            tex_src = getattr(p, "texcoordset", None)
                            if tex_sets is not None and tex_src is not None :
                                for layer_i in range(min(n_uv, len(tex_sets))) :
                                    idxs = tex_sets[layer_i]
                                    src = tex_src[layer_i]
                                    for fi in range(nfaces) :
                                        corners = these_faces[fi]
                                        # tex index row length should match corner count
                                        row = idxs[fi] if fi < len(idxs) else None
                                        if row is None :
                                            uvcoords[layer_i].append(
                                                [(0.0, 0.0)] * len(corners)
                                            )
                                        else :
                                            uvcoords[layer_i].append(
                                                [
                                                    tuple(src[int(ti)])[:2]
                                                    if 0 <= int(ti) < len(src)
                                                    else (0.0, 0.0)
                                                    for ti in row
                                                ]
                                            )
                                        #end if
                                    #end for
                                #end for
                                wrote = True
                            #end if
                        except Exception :
                            wrote = False
                        #end try
                        if not wrote :
                            try :
                                for face in p :
                                    for layer, coords in zip(uvcoords, face.texcoords) :
                                        layer.append([tuple(v) for v in coords])
                                    #end for
                                #end for
                            except Exception :
                                for face in these_faces :
                                    for layer in uvcoords :
                                        layer.append([(0.0, 0.0)] * len(face))
                                    #end for
                                #end for
                            #end try
                        #end if
                elif uvcoords is not None :
                    for face in these_faces :
                        for layer in uvcoords :
                            layer.append([(0.0, 0.0)] * len(face))
                        #end for
                    #end for
                #end if

                faces.extend(tuple(i + vert_start for i in f) for f in these_faces)
                smooth_shade.extend(these_smooth_shade)
                material_assignments.extend(these_material_assignments)
            #end for

            faces, smooth_shade, material_assignments, uvcoords, rejected = _sanitize_faces(
                faces, len(verts), smooth_shade, material_assignments, uvcoords
            )
            if rejected :
                sys.stderr.write(
                    "import_collada: rejected %d invalid face(s) in %s\n"
                    % (rejected, b_meshname)
                )
            #end if

            b_mesh = bpy.data.meshes.new(b_meshname)
            self.set_already_imported("MESH", b_meshname, b_mesh.name)
            try :
                b_mesh.from_pydata(
                    self._convert_units_verts(verts),
                    [],
                    faces,
                )
            except Exception as exc :
                sys.stderr.write(
                    "import_collada: from_pydata failed for %s: %s\n"
                    % (b_meshname, exc)
                )
                # Last-resort empty mesh so the object still exists.
                b_mesh.from_pydata([], [], [])
            #end try
            # Native importer validates topology; do the same before custom data.
            try :
                b_mesh.validate(clean_customdata = True)
            except TypeError :
                b_mesh.validate()
            #end try

            if got_normals and smooth_shade and len(smooth_shade) == len(b_mesh.polygons) :
                try :
                    b_mesh.polygons.foreach_set("use_smooth", smooth_shade)
                except Exception :
                    for i, f in enumerate(b_mesh.polygons) :
                        if i < len(smooth_shade) :
                            f.use_smooth = smooth_shade[i]
                        #end if
                    #end for
                #end try
            elif got_normals :
                try :
                    b_mesh.polygons.foreach_set(
                        "use_smooth", [True] * len(b_mesh.polygons)
                    )
                except Exception :
                    pass
                #end try
            #end if

            if uvcoords is not None and b_mesh.polygons :
                uv_layers_names = {}
                if blendstuff is not None :
                    layer_names = blendstuff.find(tag("layer_names"))
                    if layer_names is not None :
                        for name_entry in layer_names.findall(tag("name")) :
                            if name_entry.get("type") == "UV" :
                                layer_name = name_entry.get("name")
                                layer_refid = name_entry.get("refid")
                                if layer_name is not None and layer_refid is not None :
                                    uv_layers_names[layer_refid] = layer_name
                                #end if
                            #end if
                        #end for
                    #end if
                #end if
                for layer, refid in zip(uvcoords, uvcoord_ids or ()) :
                    layer_name = uv_layers_names.get(unurlid(refid)) if refid else None
                    uv = b_mesh.uv_layers.new(do_init = False)
                    if layer_name is not None :
                        uv.name = layer_name
                    #end if
                    # Batch UV write (avoids per-loop attribute churn).
                    flat = []
                    ok = True
                    for i, face in enumerate(b_mesh.polygons) :
                        coords = layer[i] if i < len(layer) else None
                        if coords is None or len(coords) < face.loop_total :
                            ok = False
                            break
                        #end if
                        for j in range(face.loop_total) :
                            flat.extend((float(coords[j][0]), float(coords[j][1])))
                        #end for
                    #end for
                    if ok and len(flat) == len(uv.data) * 2 :
                        try :
                            uv.data.foreach_set("uv", flat)
                        except Exception :
                            ok = False
                        #end try
                    else :
                        ok = False
                    #end if
                    if not ok :
                        for i, face in enumerate(b_mesh.polygons) :
                            if i >= len(layer) :
                                break
                            #end if
                            coords = layer[i]
                            loop_start = face.loop_start
                            for j in range(min(face.loop_total, len(coords))) :
                                uv.data[loop_start + j].uv = coords[j]
                            #end for
                        #end for
                    #end if
                #end for
            #end if

            if material_assignments and len(material_assignments) == len(b_mesh.polygons) :
                try :
                    b_mesh.polygons.foreach_set("material_index", material_assignments)
                except Exception :
                    for i, face in enumerate(b_mesh.polygons) :
                        face.material_index = material_assignments[i]
                    #end for
                #end try
            #end if
            b_mesh.update()
        else :
            b_mesh = bpy.data.meshes[already]
            for p in primitives :
                if isinstance(p, BoundPrimitive) :
                    b_mat_key = p.original.material
                else :
                    b_mat_key = p.material
                #end if
                materials.append(b_materials.get(b_mat_key, None))
            #end for
        #end if

        b_obj = bpy.data.objects.new(b_meshname, b_mesh)
        self._collection.objects.link(b_obj)

        # Blender 4.5 assigns materials via BKE — never bpy.ops.material_slot_add
        # (ops + active-object thrashing is a primary crash/hang cause).
        if new_mesh :
            for m in materials :
                b_mesh.materials.append(m)
            #end for
        else :
            while len(b_obj.material_slots) < len(materials) :
                b_obj.data.materials.append(None)
            #end while
            for i, m in enumerate(materials) :
                if i < len(b_obj.material_slots) :
                    b_obj.material_slots[i].link = "OBJECT"
                    b_obj.material_slots[i].material = m
                #end if
            #end for
        #end if

        # Native importer does not enter Edit Mode for normals during import.
        # calc_loop_triangles is enough to stabilize topology for display.
        if self._transform("APPLY") and new_mesh :
            try :
                b_mesh.calc_loop_triangles()
            except Exception :
                pass
            #end try
        #end if

        return b_obj
    #end geometry

    def controller(self, bctl) :
        "Instantiate the geometry referenced by a skin/morph controller (bind pose)."
        bgeom = _bound_geometry_from_controller(bctl)
        if bgeom is None :
            sys.stderr.write(
                "import_collada: skipped controller %s (no resolvable geometry)\n"
                % (getattr(bctl, "id", None) or type(bctl).__name__)
            )
            return None
        #end if
        b_obj = self.geometry(bgeom)
        skin = _controller_skin(bctl)
        self._skin_imports.append(
            {
                "bound": bctl,
                "b_obj": b_obj,
                "skin": skin,
                "controller_id": getattr(bctl, "id", None),
            }
        )
        return b_obj
    #end controller

    obj_type_handlers = \
        [
            ("camera", camera, CameraNode),
            ("light", light, LightNode),
            ("geometry", geometry, GeometryNode),
            ("controller", controller, ControllerNode),
        ]

    class Material :
        "interpretation of Collada material settings. Can be subclassed by" \
        " importer subclasses."

        def __init__(self, parent, mat, b_name) :
            self.parent = parent
            self.tempdir = None
            rendering = \
                { # initialize at instantiation time to allow overriding by subclasses
                    "blinn" : self.rendering_blinn,
                    "constant" : self.rendering_constant,
                    "lambert" : self.rendering_lambert,
                    "phong" : self.rendering_phong,
                }
            # self.mat = mat # not needed
            self.images = {}
            effect = mat.effect
            self.effect = effect
            b_mat = bpy.data.materials.new(b_name)
            self.b_mat = b_mat
            self.name = b_mat.name # name actually assigned by Blender
            b_mat.use_nodes = True
            b_shader = find_main_shader(b_mat, "BSDF_PRINCIPLED")[0]
            self.b_shader = b_shader
            self.node_x, self.node_y = b_shader.location
            self.node_x -= 350
            self.node_y += 200
            self.tex_coords_src = None
            rendering[effect.shadingtype]()
            if hasattr(b_mat, "use_backface_culling") :
                b_mat.use_backface_culling = not effect.double_sided
            #end if
            if isinstance(effect.emission, tuple) :
                set_shader_input(b_shader, ("Emission Color", "Emission"), effect.emission)
            # Map option NYI for now
            #end if
            self.rendering_transparency()
            self.rendering_reflectivity()
            self.rendering_emission()
        #end __init__

        def rendering_constant(self) :
            self.color_or_texture(
                self.effect.diffuse, "diffuse", ("Emission Color", "Emission")
            )
        #end rendering_constant

        def rendering_lambert(self) :
            self.rendering_diffuse()
            b_shader = self.b_shader
            set_shader_input(b_shader, ("Specular IOR Level", "Specular"), 0)
            set_shader_input(b_shader, "Metallic", 0)
            set_shader_input(b_shader, "Roughness", 1)
        #end rendering_lambert

        def rendering_phong(self) :
            self.rendering_diffuse()
            self.rendering_specular(False)
        #end rendering_phong

        def rendering_blinn(self) :
            self.rendering_diffuse()
            self.rendering_specular(True)
        #end rendering_blinn

        def rendering_diffuse(self) :
            self.color_or_texture(self.effect.diffuse, "diffuse", "Base Color", True)
        #end rendering_diffuse

        def rendering_specular(self, blinn = False) :
            # for the difference between Blinn (actually Blinn-Phong) and Phong shaders,
            # see <https://en.wikipedia.org/wiki/Blinn%E2%80%93Phong_reflection_model>
            effect = self.effect
            b_shader = self.b_shader
            if isinstance(effect.specular, tuple) :
                set_shader_input(b_shader, ("Specular IOR Level", "Specular"), 1.0)
                set_shader_input(b_shader, "Base Color", effect.specular)
                  # might clash with diffuse colour, but hey
            # Map option NYI for now
            #end if
            if isinstance(effect.shininess, Real) :
                set_shader_input(
                    b_shader,
                    "Roughness",
                    (1, 1 / 4)[blinn] / (1 + effect.shininess),
                )
            # Map option NYI for now
            #end if
        #end rendering_specular

        def rendering_reflectivity(self) :
            effect = self.effect
            b_shader = self.b_shader
            if isinstance(effect.reflectivity, Real) and effect.reflectivity > 0 :
                set_shader_input(
                    b_shader, ("Specular IOR Level", "Specular"), effect.reflectivity
                )
                if effect.reflective != None :
                    self.color_or_texture(effect.reflective, "reflective", "Base Color")
                      # might clash with diffuse colour, but hey
                #end if
            #end if
        #end rendering_reflectivity

        def rendering_transparency(self) :
            effect = self.effect
            if effect.transparency == None :
                return
            opaque_mode = effect.opaque_mode
            flip = opaque_mode in ("A_ZERO", "RGB_ZERO")
            # RGB_ONE/ZERO opacity modes NYI, treat as A_ONE/ZERO modes for now
            b_mat = self.b_mat
            b_shader = self.b_shader
            if isinstance(effect.transparency, Real) :
                alpha = effect.transparency
                if flip :
                    alpha = 1 - alpha
                #end if
                if self.parent._ctx.scene.render.engine == "CYCLES" :
                    # This setting is ignored by Eevee
                    set_shader_input(
                        b_shader, ("Transmission Weight", "Transmission"), 1 - alpha
                    )
                else :
                    # This setting would affect Cycles as well,
                    # which is why I don’t do both.
                    set_shader_input(b_shader, "Alpha", alpha)
                #end if
                if alpha < 1.0 :
                    set_material_transparency(b_mat, alpha)
                #end if
            #end if
            if isinstance(effect.index_of_refraction, Real) :
                set_shader_input(b_shader, "IOR", effect.index_of_refraction)
            #end if
        #end rendering_transparency

        def rendering_emission(self) :
            self.color_or_texture(
                self.effect.emission, "emission", ("Emission Color", "Emission")
            )
        #end rendering_emission

        def color_or_texture(self, color_or_texture, tex_name, shader_input_name, set_mat_color = False) :
            # does common handling of a shader input (color_or_texture) which might be
            # supplied by a Map or an (R, G, B, A) tuple. set_mat_color indicates
            # whether to try to set the viewport material colour as well.

            def try_texture(c_image) :
                basename = os.path.basename(c_image.path)
                imgfile_name = os.path.join(self.create_tempdir(), basename)
                image = None # to begin with
                if isinstance(c_image.data, bytes) :
                    imgfile = open(imgfile_name, "wb")
                    imgfile.write(c_image.data)
                    imgfile.close()
                    imgfile = None
                    try :
                        image = bpy.data.images.load(imgfile_name)
                    except RuntimeError as fail :
                        sys.stderr.write \
                          (
                                "Error trying to load image file %s from %s: %s\n"
                            %
                                (repr(c_image.path), repr(imgfile_name), str(fail))
                          )
                    #end try
                else :
                    sys.stderr.write \
                      (
                            "No data %s for image file %s\n"
                        %
                            (repr(c_image.data), repr(c_image.path))
                      )
                #end if
                if image != None :
                    node_graph = self.b_mat.node_tree
                    image.pack()
                    # wipe all traces of original file path
                    image.filepath = "//textures/%s" % basename
                    image.filepath_raw = image.filepath
                    for item in image.packed_files :
                        item.filepath = image.filepath
                    #end for
                    # todo: use image alpha as shader alpha (diffuse texture only)
                    tex_image = node_graph.nodes.new("ShaderNodeTexImage")
                    tex_image.location = (self.node_x, self.node_y)
                    self.node_y -= 200
                    tex_image.image = image
                    if self.tex_coords_src == None :
                        tex_coords_node = node_graph.nodes.new("ShaderNodeTexCoord")
                        tex_coords_node.location = (self.node_x - 400, self.node_y)
                        fanout_node = node_graph.nodes.new("NodeReroute")
                        fanout_node.location = (self.node_x - 200, self.node_y - 200)
                        node_graph.links.new \
                          (
                            tex_coords_node.outputs["UV"],
                            fanout_node.inputs[0]
                          )
                        self.tex_coords_src = fanout_node.outputs[0]
                    #end if
                    node_graph.links.new(self.tex_coords_src, tex_image.inputs[0])
                    self.images[tex_name] = image
                    mtex = tex_image.outputs["Color"]
                else :
                    mtex = None
                #end if
                # could delete imgfile_name at this point
                return mtex
            #end try_texture

        #begin color_or_texture
            if isinstance(color_or_texture, Map) :
                image = color_or_texture.sampler.surface.image
                mtex = try_texture(image)
                if mtex == None :
                    mtex = (1, 0, 1, 1) # same hideous colour Blender uses
                #end if
            elif isinstance(color_or_texture, tuple) :
                mtex = color_or_texture
            else :
                mtex = None
            #end if
            if isinstance(mtex, tuple) :
                set_shader_input(self.b_shader, shader_input_name, mtex)
                if set_mat_color :
                    self.b_mat.diffuse_color[:3] = mtex[:3]
                #end if
            elif isinstance(mtex, bpy.types.NodeSocket) :
                link_shader_input(
                    self.b_mat.node_tree, mtex, self.b_shader, shader_input_name
                )
            #end if
        #end color_or_texture

        def create_tempdir(self) :
            if self.tempdir == None :
                self.tempdir = tempfile.mkdtemp(prefix = "bpycollada-import-")
            #end if
            return self.tempdir
        #end create_tempdir

        def cleanup_tempdir(self) :
            if self.tempdir != None :
                shutil.rmtree(self.tempdir, ignore_errors = True)
                self.tempdir = None
            #end if
        #end cleanup_tempdir

    #end Material

    def material(self, mat, b_name) :
        matctx = type(self).Material(self, mat, b_name)
          # all material setup happens here
        matctx.cleanup_tempdir()
        return matctx.name
    #end material

    def _attach_with_local_matrix(self, b_obj, parent, local_mat) :
        "Parent first, then set local matrix (Blender 4.5-style hierarchy)."
        # local_mat must already be in Blender units.
        if b_obj.name not in self._collection.objects :
            self._collection.objects.link(b_obj)
        #end if
        if parent != None :
            b_obj.parent = parent
            b_obj.matrix_local = local_mat
        else :
            b_obj.matrix_world = self._orient @ local_mat
        #end if
        return b_obj
    #end _attach_with_local_matrix

    def parent_node(self, node, parent, node_matrix = None) :
        if isinstance(node, (Node, NodeNode)) :
            # SketchUp groups are <node name="group_N"> — keep that outliner name.
            src = node.node if isinstance(node, NodeNode) else node
            b_obj = bpy.data.objects.new(self.name(DATABLOCK.EMPTY, src), None)
            local = self._convert_units_matrix(Matrix(src.matrix))
            if node_matrix != None :
                local = node_matrix @ local
            #end if
            self._attach_with_local_matrix(b_obj, parent, local)
            if _node_is_joint(src) :
                xml = getattr(src, "xmlnode", None)
                self._joint_records.append(
                    {
                        "src": src,
                        "b_obj": b_obj,
                        "id": xml.get("id") if xml is not None else getattr(src, "id", None),
                        "sid": xml.get("sid") if xml is not None else None,
                        "name": xml.get("name") if xml is not None else getattr(src, "name", None),
                    }
                )
            #end if
            parent = b_obj
        else :
            handle_type = tuple(h for h in self.obj_type_handlers if isinstance(node, h[2]))
            if len(handle_type) != 0 :
                handle_type = handle_type[0]
                bobj = list(node.objects(handle_type[0]))
                if len(bobj) != 1 :
                    return parent
                #end if
                bobj = bobj[0]
                b_obj = handle_type[1](self, bobj)
                if b_obj != None :
                    if isinstance(node, ControllerNode) :
                        local = self._convert_units_matrix(_controller_object_matrix(bobj))
                        skel = _xml_skeleton_id(getattr(node, "xmlnode", None))
                        if self._skin_imports :
                            self._skin_imports[-1]["skeleton"] = skel
                        #end if
                    else :
                        local = Matrix.Identity(4)
                        if hasattr(bobj, "matrix") and bobj.matrix is not None :
                            local = self._convert_units_matrix(Matrix(bobj.matrix))
                        #end if
                    #end if
                    if node_matrix != None :
                        local = node_matrix @ local
                    #end if
                    self._attach_with_local_matrix(b_obj, parent, local)
                    parent = b_obj
                #end if
            #end if
        #end if
        return parent
    #end parent_node

    def _apply_skin_weights(self, b_obj, skin, name_map = None) :
        "Create vertex groups from COLLADA <vertex_weights> (bind-pose influences)."
        if b_obj is None or skin is None or b_obj.data is None :
            return 0
        #end if
        nverts = len(b_obj.data.vertices)
        joint_index = getattr(skin, "joint_index", None)
        weight_index = getattr(skin, "weight_index", None)
        if not joint_index or not weight_index :
            return 0
        #end if
        n = min(nverts, len(joint_index), len(weight_index))
        if n == 0 :
            return 0
        #end if
        if len(joint_index) != nverts :
            sys.stderr.write(
                "import_collada: skin %s vertex count %d != mesh %d; "
                "assigning overlapping weights only\n"
                % (getattr(skin, "id", "?"), len(joint_index), nverts)
            )
        #end if
        groups = {}
        assigned = 0
        for vi in range(n) :
            jrow = joint_index[vi]
            wrow = weight_index[vi]
            try :
                pairs = zip(jrow, wrow)
            except TypeError :
                continue
            #end try
            for ji, wi in pairs :
                try :
                    jname = str(skin.weight_joints[int(ji)])
                    weight = _float_weight(skin.weights[int(wi)])
                except Exception :
                    continue
                #end try
                if name_map :
                    jname = name_map.get(jname, jname)
                #end if
                if not jname or weight <= 0.0 :
                    continue
                #end if
                vg = groups.get(jname)
                if vg is None :
                    try :
                        vg = b_obj.vertex_groups.new(name = jname)
                    except RuntimeError :
                        vg = b_obj.vertex_groups.get(jname)
                    #end try
                    groups[jname] = vg
                #end if
                if vg is None :
                    continue
                #end if
                try :
                    vg.add([vi], float(weight), "REPLACE")
                except Exception :
                    continue
                #end try
            #end for
            assigned += 1
        #end for
        return assigned
    #end _apply_skin_weights

    def _joint_lookup(self) :
        "Map COLLADA joint id/sid/name → Empty object created during Parenting."
        by_key = {}
        for rec in self._joint_records :
            b_obj = rec.get("b_obj")
            if b_obj is None :
                continue
            #end if
            for key in (rec.get("sid"), rec.get("id"), rec.get("name")) :
                if key :
                    by_key[key] = rec
                #end if
            #end for
        #end for
        return by_key
    #end _joint_lookup

    def _collect_joint_tree(self, root_rec, by_key = None) :
        "Depth-first joint records under a skeleton root Empty."
        root_obj = root_rec["b_obj"]
        joint_objs = set(rec["b_obj"] for rec in self._joint_records if rec.get("b_obj") is not None)
        ordered = []
        seen = set()

        def walk(obj) :
            if obj is None or obj in seen or obj not in joint_objs :
                return
            #end if
            seen.add(obj)
            rec = None
            for r in self._joint_records :
                if r.get("b_obj") == obj :
                    rec = r
                    break
                #end if
            #end for
            if rec is None :
                return
            #end if
            ordered.append(rec)
            children = list(obj.children)
            children.sort(key = lambda c : c.name)
            for child in children :
                walk(child)
            #end for
        #end walk

        walk(root_obj)
        return ordered
    #end _collect_joint_tree

    def _safe_mode_set(self, mode) :
        ctx = self._ctx
        view_layer = getattr(ctx, "view_layer", None)
        active = view_layer.objects.active if view_layer is not None else None
        if active is not None and hasattr(ctx, "temp_override") :
            try :
                with ctx.temp_override(active_object = active, object = active) :
                    bpy.ops.object.mode_set(mode = mode)
                    return True
                #end with
            except Exception :
                pass
            #end try
        #end if
        try :
            bpy.ops.object.mode_set(mode = mode)
            return True
        except Exception as exc :
            sys.stderr.write("import_collada: mode_set(%s) failed: %s\n" % (mode, exc))
            return False
        #end try
    #end _safe_mode_set

    def _create_armature_from_joint_empties(self, root_rec, joint_recs) :
        "Build one Armature whose bones match the JOINT Empty hierarchy."
        ctx = self._ctx
        view_layer = getattr(ctx, "view_layer", None)
        if view_layer is None or not joint_recs :
            return None, {}
        #end if
        root_obj = root_rec["b_obj"]
        arm_name = self.name(
            DATABLOCK.ARMATURE,
            root_rec.get("src") or root_obj,
        )
        arm_data = bpy.data.armatures.new(arm_name)
        arm_obj = bpy.data.objects.new(arm_data.name, arm_data)
        self._collection.objects.link(arm_obj)
        parent = root_obj.parent
        if parent is not None :
            arm_obj.parent = parent
            arm_obj.matrix_world = parent.matrix_world.copy()
        else :
            arm_obj.matrix_world = Matrix.Identity(4)
        #end if

        prev_active = view_layer.objects.active
        prev_selected = [o for o in getattr(ctx, "selected_objects", [])]
        try :
            try :
                bpy.ops.object.mode_set(mode = "OBJECT")
            except Exception :
                pass
            #end try
            for obj in list(prev_selected) :
                try :
                    obj.select_set(False)
                except Exception :
                    pass
                #end try
            #end for
            view_layer.objects.active = arm_obj
            try :
                arm_obj.select_set(True)
            except Exception :
                pass
            #end try
            if not self._safe_mode_set("EDIT") :
                try :
                    bpy.data.objects.remove(arm_obj, do_unlink = True)
                    bpy.data.armatures.remove(arm_data)
                except Exception :
                    pass
                #end try
                return None, {}
            #end if

            ebs = arm_data.edit_bones
            bones = {}
            name_map = {}
            arm_inv = arm_obj.matrix_world.inverted()
            rec_by_obj = dict((rec["b_obj"], rec) for rec in joint_recs)

            for rec in joint_recs :
                empty = rec["b_obj"]
                raw_name = rec.get("sid") or rec.get("id") or rec.get("name") or empty.name
                bone_name = str(raw_name)[:MAX_NAME_LENGTH]
                try :
                    eb = ebs.new(bone_name)
                except Exception :
                    eb = ebs.new(empty.name[:MAX_NAME_LENGTH])
                #end try
                mat = arm_inv @ empty.matrix_world
                head = mat.to_translation()
                child_heads = []
                for child in empty.children :
                    if child in rec_by_obj :
                        child_heads.append((arm_inv @ child.matrix_world).to_translation())
                    #end if
                #end for
                tail = None
                if child_heads :
                    # Aim at the nearest joint child so the bone is visible.
                    child_heads.sort(key = lambda p : (p - head).length)
                    candidate = child_heads[0]
                    if (candidate - head).length > 1e-4 * max(self._units, 1e-6) :
                        tail = candidate
                    #end if
                #end if
                if tail is None :
                    y_axis = mat.to_3x3() @ Vector((0.0, 1.0, 0.0))
                    if y_axis.length < 1e-8 :
                        y_axis = Vector((0.0, 0.0, 1.0))
                    #end if
                    y_axis.normalize()
                    length = 0.05 * max(self._units, 1.0)
                    parent_empty = empty.parent
                    if parent_empty is not None and parent_empty in rec_by_obj :
                        parent_head = (arm_inv @ parent_empty.matrix_world).to_translation()
                        inherited = (head - parent_head).length
                        if inherited > length :
                            length = inherited * 0.5
                        #end if
                    #end if
                    tail = head + y_axis * length
                #end if
                if (tail - head).length < 1e-6 :
                    tail = head + Vector((0.0, 0.0, 0.05 * max(self._units, 1.0)))
                #end if
                eb.head = head
                eb.tail = tail
                eb.use_connect = False
                parent_empty = empty.parent
                if parent_empty in bones :
                    eb.parent = bones[parent_empty]
                #end if
                bones[empty] = eb
                actual = eb.name
                for key in (rec.get("sid"), rec.get("id"), rec.get("name"), raw_name) :
                    if key :
                        name_map[str(key)] = actual
                    #end if
                #end for
            #end for
        finally :
            try :
                if getattr(ctx, "mode", "") == "EDIT_ARMATURE" :
                    self._safe_mode_set("OBJECT")
                #end if
            except Exception :
                try :
                    bpy.ops.object.mode_set(mode = "OBJECT")
                except Exception :
                    pass
                #end try
            #end try
            try :
                arm_obj.select_set(False)
            except Exception :
                pass
            #end try
            for obj in prev_selected :
                try :
                    obj.select_set(True)
                except Exception :
                    pass
                #end try
            #end for
            view_layer.objects.active = prev_active
        #end try
        return arm_obj, name_map
    #end _create_armature_from_joint_empties

    def _reparent_nonjoint_children(self, joint_recs, arm_obj, name_map) :
        "Keep accessory NODE empties (weapon sockets, etc.) on the matching bone."
        joint_objs = set(rec["b_obj"] for rec in joint_recs)
        for rec in joint_recs :
            empty = rec["b_obj"]
            bone_name = name_map.get(rec.get("sid")) or name_map.get(rec.get("id")) or name_map.get(rec.get("name"))
            if not bone_name :
                continue
            #end if
            for child in list(empty.children) :
                if child in joint_objs :
                    continue
                #end if
                try :
                    mw = child.matrix_world.copy()
                    child.parent = arm_obj
                    child.parent_type = "BONE"
                    child.parent_bone = bone_name
                    child.matrix_world = mw
                except Exception as exc :
                    sys.stderr.write(
                        "import_collada: could not reparent %s to bone %s: %s\n"
                        % (child.name, bone_name, exc)
                    )
                #end try
            #end for
        #end for
    #end _reparent_nonjoint_children

    def _remove_joint_empties(self, joint_recs) :
        for rec in joint_recs :
            empty = rec.get("b_obj")
            if empty is None :
                continue
            #end if
            try :
                bpy.data.objects.remove(empty, do_unlink = True)
            except Exception :
                try :
                    empty.user_clear()
                    bpy.data.objects.remove(empty)
                except Exception :
                    pass
                #end try
            #end try
        #end for
    #end _remove_joint_empties

    def _add_armature_modifier(self, b_obj, arm_obj) :
        if b_obj is None or arm_obj is None :
            return
        #end if
        try :
            mod = b_obj.modifiers.new("Armature", "ARMATURE")
            mod.object = arm_obj
            mod.use_vertex_groups = True
        except Exception as exc :
            sys.stderr.write(
                "import_collada: Armature modifier failed on %s: %s\n"
                % (b_obj.name, exc)
            )
        #end try
    #end _add_armature_modifier

    def _resolve_skeleton_root(self, by_key, skeleton_id) :
        if skeleton_id and skeleton_id in by_key :
            return by_key[skeleton_id]
        #end if
        # Fall back to a joint Empty whose parent is not a joint.
        joint_objs = set(rec["b_obj"] for rec in self._joint_records if rec.get("b_obj") is not None)
        for rec in self._joint_records :
            parent = rec["b_obj"].parent if rec.get("b_obj") is not None else None
            if parent is None or parent not in joint_objs :
                return rec
            #end if
        #end for
        return self._joint_records[0] if self._joint_records else None
    #end _resolve_skeleton_root

    def _harvest_collada_joints(self) :
        "Walk the COLLADA scene and return joint dicts with blender-space worlds."
        harvested = []
        scene = getattr(self._collada, "scene", None)
        if scene is None :
            return harvested
        #end if

        def walk(node, parent_world, parent_joint_key) :
            if isinstance(node, Scene) :
                for child in node.nodes :
                    walk(child, None, None)
                #end for
                return
            #end if
            if isinstance(node, NodeNode) :
                walk(node.node, parent_world, parent_joint_key)
                return
            #end if
            if not isinstance(node, Node) :
                return
            #end if
            local = self._convert_units_matrix(Matrix(node.matrix))
            if parent_world is None :
                world = self._orient @ local
            else :
                world = parent_world @ local
            #end if
            key = parent_joint_key
            if _node_is_joint(node) :
                xml = getattr(node, "xmlnode", None)
                rec = {
                    "src": node,
                    "world": world,
                    "id": xml.get("id") if xml is not None else getattr(node, "id", None),
                    "sid": xml.get("sid") if xml is not None else None,
                    "name": xml.get("name") if xml is not None else getattr(node, "name", None),
                    "parent_key": parent_joint_key,
                }
                harvested.append(rec)
                key = rec.get("sid") or rec.get("id") or rec.get("name")
            #end if
            for child in node.children :
                walk(child, world, key)
            #end for
        #end walk

        walk(scene, None, None)
        return harvested
    #end _harvest_collada_joints

    def _armature_from_collada_scene(self) :
        "MUL/APPLY fallback: build an Armature from JOINT node world matrices."
        harvested = self._harvest_collada_joints()
        if not harvested :
            return None, {}
        #end if
        ctx = self._ctx
        view_layer = getattr(ctx, "view_layer", None)
        if view_layer is None :
            return None, {}
        #end if
        root = harvested[0]
        arm_name = self.name(DATABLOCK.ARMATURE, root.get("src"))
        arm_data = bpy.data.armatures.new(arm_name)
        arm_obj = bpy.data.objects.new(arm_data.name, arm_data)
        self._collection.objects.link(arm_obj)
        arm_obj.matrix_world = Matrix.Identity(4)
        prev_active = view_layer.objects.active
        try :
            try :
                bpy.ops.object.mode_set(mode = "OBJECT")
            except Exception :
                pass
            #end try
            view_layer.objects.active = arm_obj
            try :
                arm_obj.select_set(True)
            except Exception :
                pass
            #end try
            if not self._safe_mode_set("EDIT") :
                try :
                    bpy.data.objects.remove(arm_obj, do_unlink = True)
                except Exception :
                    pass
                #end try
                return None, {}
            #end if
            ebs = arm_data.edit_bones
            bones = {}
            name_map = {}
            for rec in harvested :
                raw_name = rec.get("sid") or rec.get("id") or rec.get("name") or "joint"
                try :
                    eb = ebs.new(str(raw_name)[:MAX_NAME_LENGTH])
                except Exception :
                    continue
                #end try
                mat = rec["world"]
                head = mat.to_translation()
                child_heads = [
                    child["world"].to_translation()
                    for child in harvested
                    if child.get("parent_key") in (rec.get("sid"), rec.get("id"), rec.get("name"))
                ]
                tail = None
                if child_heads :
                    child_heads.sort(key = lambda p : (p - head).length)
                    if (child_heads[0] - head).length > 1e-4 :
                        tail = child_heads[0]
                    #end if
                #end if
                if tail is None :
                    y_axis = mat.to_3x3() @ Vector((0.0, 1.0, 0.0))
                    if y_axis.length < 1e-8 :
                        y_axis = Vector((0.0, 0.0, 1.0))
                    #end if
                    y_axis.normalize()
                    tail = head + y_axis * (0.05 * max(self._units, 1.0))
                #end if
                eb.head = head
                eb.tail = tail
                eb.use_connect = False
                parent_key = rec.get("parent_key")
                if parent_key in bones :
                    eb.parent = bones[parent_key]
                #end if
                actual = eb.name
                for key in (rec.get("sid"), rec.get("id"), rec.get("name"), raw_name) :
                    if key :
                        bones[key] = eb
                        name_map[str(key)] = actual
                    #end if
                #end for
            #end for
        finally :
            try :
                self._safe_mode_set("OBJECT")
            except Exception :
                pass
            #end try
            try :
                arm_obj.select_set(False)
            except Exception :
                pass
            #end try
            view_layer.objects.active = prev_active
        #end try
        return arm_obj, name_map
    #end _armature_from_collada_scene

    def finalize_skins(self) :
        """
        After objects exist: build an Armature from JOINT nodes, assign skin
        weights (using final bone names), bind meshes, and remove placeholder
        joint Empties.
        """
        if not self._skin_imports :
            return
        #end if

        def weight_and_bind(arm_obj, name_map, skeleton_id = None) :
            n = 0
            for rec in self._skin_imports :
                rec_skel = rec.get("skeleton")
                if skeleton_id and rec_skel and rec_skel != skeleton_id :
                    continue
                #end if
                b_obj = rec.get("b_obj")
                skin = rec.get("skin")
                if b_obj is None or skin is None :
                    continue
                #end if
                n += 1 if self._apply_skin_weights(b_obj, skin, name_map) else 0
                self._add_armature_modifier(b_obj, arm_obj)
            #end for
            return n
        #end weight_and_bind

        if not self._joint_records :
            arm_obj, name_map = self._armature_from_collada_scene()
            if arm_obj is not None :
                weighted = weight_and_bind(arm_obj, name_map)
                sys.stderr.write(
                    "import_collada: instantiated %d controller mesh(es), "
                    "weighted %d, created Armature from COLLADA JOINT nodes\n"
                    % (len(self._skin_imports), weighted)
                )
            else :
                weighted = 0
                for rec in self._skin_imports :
                    weighted += 1 if self._apply_skin_weights(rec.get("b_obj"), rec.get("skin")) else 0
                #end for
                sys.stderr.write(
                    "import_collada: imported %d controller mesh(es); no JOINT nodes "
                    "to convert into an Armature\n" % len(self._skin_imports)
                )
            #end if
            return
        #end if

        by_key = self._joint_lookup()
        # One armature per distinct skeleton root referenced by controllers.
        skeleton_ids = []
        for rec in self._skin_imports :
            sid = rec.get("skeleton")
            if sid and sid not in skeleton_ids :
                skeleton_ids.append(sid)
            #end if
        #end for
        if not skeleton_ids :
            skeleton_ids.append(None)
        #end if

        built = []
        used_joints = set()
        weighted = 0
        for skel_id in skeleton_ids :
            root_rec = self._resolve_skeleton_root(by_key, skel_id)
            if root_rec is None or root_rec["b_obj"] in used_joints :
                continue
            #end if
            joint_recs = self._collect_joint_tree(root_rec, by_key)
            if not joint_recs :
                continue
            #end if
            arm_obj, name_map = self._create_armature_from_joint_empties(root_rec, joint_recs)
            if arm_obj is None :
                sys.stderr.write(
                    "import_collada: could not create Armature for skeleton %s; "
                    "leaving JOINT Empties in place\n" % (skel_id or "?")
                )
                continue
            #end if
            weighted += weight_and_bind(arm_obj, name_map, skel_id)
            self._reparent_nonjoint_children(joint_recs, arm_obj, name_map)
            built.append((arm_obj, joint_recs))
            for rec in joint_recs :
                used_joints.add(rec["b_obj"])
            #end for
        #end for

        for arm_obj, joint_recs in built :
            self._remove_joint_empties(joint_recs)
        #end for

        if not built :
            for rec in self._skin_imports :
                weighted += 1 if self._apply_skin_weights(rec.get("b_obj"), rec.get("skin")) else 0
            #end for
        #end if

        sys.stderr.write(
            "import_collada: instantiated %d controller mesh(es), "
            "weighted %d, created %d Armature(s) from JOINT nodes\n"
            % (len(self._skin_imports), weighted, len(built))
        )
    #end finalize_skins

    @classmethod
    def match(celf, collada) :
        return True
    #end match

#end ColladaImport

class SketchUpImport(ColladaImport) :
    "SketchUp specific COLLADA import."

    SK_DAE_NS = {"dae" : "http://www.collada.org/2005/11/COLLADASchema"}
      # SketchUp only uses Collada 1.4.1, as far as I know

    class Material(ColladaImport.Material) :
        "SketchUp-specific material handling."

        def rendering_phong(self) :
            super().rendering_lambert()
        #end rendering_phong

        def rendering_transparency(self) :
            effect = self.effect
            # get opaque_mode setting direct from XML, avoiding pycollada-provided default
            transparent = effect.xmlnode.find(".//" + tag("transparent"))
            if transparent != None :
                opaque_mode = transparent.get("opaque")
            else :
                opaque_mode = None
            #end if
            # fudge for some disappearing SketchUp models
            if (
                    opaque_mode == None
                and
                    isinstance(effect.transparent, tuple)
                and
                    isinstance(effect.transparency, Real)
                and
                    tuple(effect.transparent) == (1, 1, 1, 1)
                and
                    effect.transparency == 0
            ) :
                effect.transparency = 1
            #end if
            super().rendering_transparency()
        #end rendering_transparency

        def rendering_reflectivity(self) :
            "There are no reflectivity controls in SketchUp."
            if not self.parent.match_test2(self.effect.xmlnode) :
                super().rendering_reflectivity()
            #end if
        #end rendering_reflectivity

    #end Material

    @classmethod
    def match_test2(celf, xml) :
        namespace_uri = "http://www.collada.org/2005/11/COLLADASchema"
        for elem in xml.iter():
            if elem.tag == f"{{{namespace_uri}}}technique":
                if elem.get("profile") == "GOOGLEEARTH":
                    return True
        return False
    #end match_test2

    @classmethod
    def match(celf, collada) :
        "Does this look like a Collada file from SketchUp."

        def test1(xml) :
            t1 = xml.find(".//dae:instance_visual_scene", namespaces = celf.SK_DAE_NS)
            if t1 != None :
                t1 = t1.get("url")
            #end if
            t2 = xml.find(".//dae:authoring_tool", namespaces = celf.SK_DAE_NS)
            if t2 != None :
                t2 = t2.text
            #end if
            return \
                any \
                  (
                    "SketchUp" in s
                    for s in (t1, t2)
                    if s != None
                  )
        #end test1

    #begin match
        xml = collada.xmlnode
        return test1(xml) or celf.match_test2(xml)
    #end match

#end SketchUpImport

VENDOR_SPECIFIC = \
    [
        SketchUpImport,
    ]

def get_import(collada) :
    "returns a suitable importer for the given Collada object according" \
    " to any vendor-specific features found."
    for i in VENDOR_SPECIFIC :
        if i.match(collada) :
            return i
    #end for
    return ColladaImport
#end get_import

def _zip_norm(name) :
    "Normalize archive member paths for lookup."
    return name.replace("\\", "/").lstrip("./")
#end _zip_norm

def _zip_find_member(names, wanted) :
    "Find a zip member matching wanted path (case-insensitive, slash-normalized)."
    wanted_n = _zip_norm(wanted).lower()
    by_norm = {_zip_norm(n).lower(): n for n in names}
    if wanted_n in by_norm :
        return by_norm[wanted_n]
    #end if
    # Match by basename if unique.
    base = os.path.basename(wanted_n)
    hits = [n for n in names if os.path.basename(_zip_norm(n)).lower() == base]
    if len(hits) == 1 :
        return hits[0]
    #end if
    return None
#end _zip_find_member

def _zip_pick_dae_root(zf) :
    "Resolve the primary .dae inside a ZAE/KMZ/ZIP archive."
    names = zf.namelist()
    # 1) Official ZAE manifest.xml
    manifest_name = _zip_find_member(names, "manifest.xml")
    if manifest_name is not None :
        try :
            manifest = ElementTree.ElementTree(file = io.BytesIO(zf.read(manifest_name)))
            root = manifest.getroot()
            dae_root = (root.text or "").strip()
            if not dae_root and len(root) :
                # Some writers nest the path in a child element.
                dae_root = ("".join(root.itertext()) or "").strip()
            #end if
            if dae_root :
                # Strip URL fragment (#...) if present.
                dae_root = dae_root.split("#", 1)[0].strip()
                member = _zip_find_member(names, dae_root)
                if member is not None :
                    return member
                #end if
            #end if
        except Exception as exc :
            sys.stderr.write("Could not parse archive manifest.xml: %s\n" % exc)
        #end try
    #end if

    dae_members = \
        [
            n for n in names
            if _zip_norm(n).lower().endswith(".dae") and not n.endswith("/")
        ]
    if not dae_members :
        raise RuntimeError("Archive contains no .dae file")
    #end if

    preferred = \
        (
            "doc.dae",
            "scene.dae",
            "model.dae",
            "models/model.dae",
        )
    for pref in preferred :
        hit = _zip_find_member(dae_members, pref)
        if hit is not None :
            return hit
        #end if
    #end for

    # Prefer a top-level .dae over nested ones.
    top = [n for n in dae_members if "/" not in _zip_norm(n)]
    if top :
        return sorted(top, key = lambda n : _zip_norm(n).lower())[0]
    #end if
    return sorted(dae_members, key = lambda n : _zip_norm(n).lower())[0]
#end _zip_pick_dae_root

def open_collada_archive(filepath, collada_ignore) :
    "Open a .zae / .kmz / .zip COLLADA archive and return a Collada document."
    zf = zipfile.ZipFile(filepath)
    try :
        dae_root = _zip_pick_dae_root(zf)
        name_map = {_zip_norm(n).lower(): n for n in zf.namelist()}
        dae_dir = os.path.dirname(_zip_norm(dae_root))
        sys.stderr.write("COLLADA archive root: %s\n" % dae_root)

        def aux_file_loader(fname) :
            # pycollada may pass relative texture/image paths.
            candidates = []
            raw = (fname or "").split("#", 1)[0].strip()
            if not raw :
                raise IOError("Empty auxiliary file reference")
            #end if
            # Strip file:// prefixes.
            if raw.lower().startswith("file:") :
                raw = raw.split(":", 1)[1]
                if raw.startswith("///") :
                    raw = raw[3:]
                elif raw.startswith("//") :
                    raw = raw[2:]
                #end if
            #end if
            raw_n = _zip_norm(raw)
            candidates.append(raw_n)
            if dae_dir :
                candidates.append(_zip_norm("/".join((dae_dir, raw_n))))
            #end if
            candidates.append(os.path.basename(raw_n))
            for cand in candidates :
                key = cand.lower()
                if key in name_map :
                    return zf.read(name_map[key])
                #end if
                base = os.path.basename(cand).lower()
                hits = \
                    [
                        real for norm, real in name_map.items()
                        if os.path.basename(norm) == base
                    ]
                if len(hits) == 1 :
                    return zf.read(hits[0])
                #end if
            #end for
            raise IOError("Missing file in archive: %s" % fname)
        #end aux_file_loader

        c = Collada \
          (
            filename = io.BytesIO(zf.read(dae_root)),
            aux_file_loader = aux_file_loader,
            ignore = collada_ignore,
          )
        # Keep the ZipFile alive for any deferred texture loads.
        c._blender_collada_zip = zf
        return c
    except Exception :
        zf.close()
        raise
    #end try
#end open_collada_archive

def close_collada_archive(collada) :
    zf = getattr(collada, "_blender_collada_zip", None)
    if zf is not None :
        try :
            zf.close()
        except Exception :
            pass
        #end try
        try :
            delattr(collada, "_blender_collada_zip")
        except Exception :
            pass
        #end try
    #end if
#end close_collada_archive

def _summarize_collada_errors(collada, limit = 8) :
    "Build a short operator-friendly summary of pycollada errors/warnings."
    errs = list(getattr(collada, "errors", None) or [])
    if not errs :
        return None, 0
    #end if
    # Group by exception type / message prefix for a compact report.
    counts = {}
    samples = []
    for err in errs :
        key = type(err).__name__
        msg = str(err).strip() or key
        counts[key] = counts.get(key, 0) + 1
        if len(samples) < limit :
            samples.append("%s: %s" % (key, msg[:120]))
        #end if
    #end for
    parts = ["%s×%d" % (k, counts[k]) for k in sorted(counts.keys())]
    summary = "COLLADA parse issues (%d): %s" % (len(errs), ", ".join(parts))
    detail = "; ".join(samples)
    if len(errs) > limit :
        detail += "; …"
    #end if
    return "%s — %s" % (summary, detail), len(errs)
#end _summarize_collada_errors

def load(op, ctx, is_zae, filepath, **kwargs) :

    def get_obj_matrix(obj) :

        def direction_matrix(direction) :
            # calculation follows an answer from
            # <https://math.stackexchange.com/questions/180418/calculate-rotation-matrix-to-align-vector-a-to-vector-b-in-3d>
            reference = Vector((0, 0, -1))
            direction = Vector(tuple(direction))
            direction.resize_3d()
            direction.normalize()
            cross = reference.cross(direction)
            fac = Matrix \
              (
                [
                    [0, - cross.z, cross.y, 0],
                    [cross.z, 0, - cross.x, 0],
                    [- cross.y, cross.x, 0, 0,],
                    [0, 0, 0, 1]
                ]
              )
            try :
                result = \
                  (
                        Matrix.Identity(4)
                    +
                        fac
                    +
                        1 / (1 + reference @ direction) * (fac @ fac)
                  )
            except ZeroDivisionError :
                result = Matrix.Rotation(180 * DEG, 4, "X")
                  # actually any rotation axis in plane perpendicular to reference will work
            #end try
            return result
        #end direction_matrix

    #begin get_obj_matrix
        # fixme: BoundSpotLight also has an up direction vector I should probably take into account
        if hasattr(obj, "matrix") :
            result = Matrix(obj.matrix)
        elif hasattr(obj, "position") or hasattr(obj, "direction") :
            result = Matrix.Identity(4)
            if hasattr(obj, "direction") :
                result = direction_matrix(obj.direction)
            #end if
            if hasattr(obj, "position") :
                result = Matrix.Translation(obj.position) @ result
            #end if
        else :
            result = None
        #end if
        return result
    #end get_obj_matrix

    last_update = None
    update_interval = 0.25
    obj_count = nr_objs = 0
    progress = None

    def count_hierarchy_nodes(node) :
        "Pre-count Node/Scene steps for Parenting-mode progress."
        total = 1
        children = ()
        if isinstance(node, Scene) :
            children = node.nodes
        elif isinstance(node, Node) :
            children = node.children
        elif isinstance(node, NodeNode) :
            children = node.node.children
        #end if
        for child in children :
            if isinstance(child, (Scene, Node, NodeNode) + _INSTANCE_NODES) :
                total += count_hierarchy_nodes(child)
            #end if
        #end for
        return total
    #end count_hierarchy_nodes

    def traverse_children(self, node, action, parent, accum_matrix = None) :
        nonlocal last_update, obj_count, progress
        obj_count += 1
        if progress is not None :
            progress.step(1)
        #end if
        now = time.time()
        if now - last_update >= update_interval :
            sys.stderr.write("created %d objects\n" % obj_count)
            last_update = now
        #end if
        children = ()
        empty_children = ()
        nonempty_children = ()
        node_matrix = None
        is_group_node = False
        rule = tuple \
          (
            entry
            for entry in
                (
                    (Scene, lambda node : node.nodes, False),
                    (Node, lambda node : node.children, True),
                    (NodeNode, lambda node : node.node.children, True),
                )
            if isinstance(node, entry[0])
          )
        if len(rule) != 0 :
            rule = rule[0]
            children = rule[1](node)
            is_group_node = rule[2]
            if is_group_node :
                empty_children = tuple \
                  ( # children which would be represented as Empty objects
                    c
                    for c in children
                    if isinstance(c, (Node, NodeNode))
                  )
                nonempty_children = tuple \
                  ( # children which would be presented as objects other than Empties
                    c
                    for c in children
                    if isinstance(c, _INSTANCE_NODES)
                  )
                src = _node_src(node)
                node_matrix = self._convert_units_matrix(Matrix(src.matrix))
            #end if
        #end if
        if accum_matrix is not None :
            if node_matrix is not None :
                combined = accum_matrix @ node_matrix
            else :
                combined = accum_matrix
            #end if
        else :
            combined = node_matrix
        #end if

        # Collapse pass-through group nodes: identity transform, no meaningful
        # name, and a single child (another group or one object). Fold the
        # transform into descendants instead of creating an Empty.
        if (
            is_group_node
            and combined is not None
            and len(children) == 1
            and _matrix_is_identity(combined)
            and not _node_has_meaningful_name(_node_src(node))
        ) :
            child = children[0]
            if isinstance(child, (Node, NodeNode)) :
                traverse_children(self, child, action, parent, combined)
            elif isinstance(child, _INSTANCE_NODES) :
                action(child, parent, combined)
            #end if
            return
        #end if

        if combined is not None and len(nonempty_children) == 1 :
            # make the nonempty child the parent of the other children,
            # instead of creating an Empty for this Node.
            new_parent = action(nonempty_children[0], parent, combined)
            for child in empty_children :
                traverse_children(self, child, action, new_parent, None)
            #end for
        else :
            # create an Empty for this Node (or process Scene).
            # For group nodes, pass accum so outer collapsed transforms apply.
            if is_group_node and accum_matrix is not None :
                new_parent = action(node, parent, accum_matrix)
            else :
                new_parent = action(node, parent)
            #end if
            for child in children :
                traverse_children(self, child, action, new_parent, None)
            #end for
        #end if
    #end traverse_children

#begin load
    start_time = time.time()
    collada_ignore = [DaeBrokenRefError]
    archive_exts = (".zae", ".kmz", ".zip")
    is_archive = is_zae or filepath.lower().endswith(archive_exts)
    c = None
    wm = getattr(ctx, "window_manager", None)
    progress = _ImportProgress(wm, 100)
    try :
        # Phase A: parse COLLADA / archive (synchronous; UI may still stall here).
        progress.update_fraction(0.02)
        if is_archive :
            try :
                c = open_collada_archive(filepath, collada_ignore)
            except Exception as exc :
                sys.stderr.write("COLLADA archive import failed: %s\n" % exc)
                if op is not None :
                    op.report({"ERROR"}, "COLLADA archive import failed: %s" % exc)
                #end if
                return {"CANCELLED"}
            #end try
        else :
            c = Collada(filepath, ignore = collada_ignore)
        #end if
        progress.update_fraction(0.15)
        err_report, err_count = _summarize_collada_errors(c)
        if err_report :
            sys.stderr.write("%s\n" % err_report)
            if op is not None :
                # Broken refs are ignored for load continuity; still surface them.
                op.report({"WARNING"}, err_report[:500])
            #end if
        #end if
        now = time.time()
        sys.stderr.write("Time to load .dae file = %.2fs\n" % (now - start_time))
        start_time = now
        progress.update_fraction(0.18)
        importer = get_import(c)(ctx, c, filepath, **kwargs)
        tf = importer._transformation
        created = 0
        failed = 0
        progress.update_fraction(0.20)
        controller_skeletons = _controller_skeleton_map(c.scene)
        if tf in ("MUL", "APPLY") :
            all_jobs = []
            for handle_type in importer.obj_type_handlers :
                objs = list(c.scene.objects(handle_type[0]))
                all_jobs.append((handle_type, objs))
            #end for
            total_objs = sum(len(objs) for _, objs in all_jobs) or 1
            # Object creation spans 20%..100% of the bar.
            progress.set_steps(total_objs)
            # Remap step() into the creation band via custom stepping below.
            done = 0
            for handle_type, objs in all_jobs :
                nr_objs = len(objs)
                last_update = start_time
                for i, obj in enumerate(objs) :
                    try :
                        b_obj = handle_type[1](importer, obj)
                    except Exception as exc :
                        failed += 1
                        sys.stderr.write(
                            "import_collada: failed %s %d/%d: %s\n"
                            % (handle_type[0], i + 1, nr_objs, exc)
                        )
                        traceback.print_exc()
                        done += 1
                        progress.update_fraction(0.20 + 0.80 * (done / float(total_objs)))
                        continue
                    #end try
                    if b_obj is None :
                        done += 1
                        progress.update_fraction(0.20 + 0.80 * (done / float(total_objs)))
                        continue
                    #end if
                    created += 1
                    done += 1
                    if handle_type[0] == "controller" and importer._skin_imports :
                        cid = getattr(obj, "id", None)
                        if cid and cid in controller_skeletons :
                            importer._skin_imports[-1]["skeleton"] = controller_skeletons[cid]
                        #end if
                    #end if
                    progress.update_fraction(0.20 + 0.80 * (done / float(total_objs)))
                    now = time.time()
                    if now - last_update >= update_interval :
                        sys.stderr.write(
                            "created %s objects %d/%d\n"
                            % (handle_type[0], i + 1, nr_objs)
                        )
                        last_update = now
                    #end if
                    if tf == "MUL" :
                        if handle_type[0] == "controller" :
                            tf_mat = importer._convert_units_matrix(
                                _controller_object_matrix(obj)
                            )
                        else :
                            tf_mat = get_obj_matrix(obj)
                            if tf_mat is not None :
                                tf_mat = importer._convert_units_matrix(tf_mat)
                            #end if
                        #end if
                        if tf_mat is not None :
                            b_obj.matrix_world = importer._orient @ tf_mat
                        #end if
                    #end if
                #end for
            #end for
        elif tf == "PARENT" :
            last_update = start_time
            try :
                total_nodes = count_hierarchy_nodes(c.scene) or 1
                # Hierarchy walk spans 20%..100%; step() uses 0..total_nodes then remap.
                hierarchy_steps = {"n": 0, "total": total_nodes}

                def parent_progress_step(n = 1) :
                    hierarchy_steps["n"] = min(
                        hierarchy_steps["n"] + n, hierarchy_steps["total"]
                    )
                    progress.update_fraction(
                        0.20
                        + 0.80
                        * (hierarchy_steps["n"] / float(hierarchy_steps["total"]))
                    )
                #end parent_progress_step

                # Rebind progress.step used inside traverse_children.
                progress.step = parent_progress_step
                traverse_children(importer, c.scene, importer.parent_node, None)
            except Exception as exc :
                sys.stderr.write("import_collada: hierarchy import failed: %s\n" % exc)
                traceback.print_exc()
                if op is not None :
                    op.report({"ERROR"}, "Hierarchy import failed: %s" % exc)
                #end if
                return {"CANCELLED"}
            #end try
        #end if
        for rec in importer._skin_imports :
            if rec.get("skeleton") :
                continue
            #end if
            cid = rec.get("controller_id")
            if cid and cid in controller_skeletons :
                rec["skeleton"] = controller_skeletons[cid]
            #end if
        #end for
        try :
            importer.finalize_skins()
        except Exception as exc :
            sys.stderr.write("import_collada: skin/armature finalize failed: %s\n" % exc)
            traceback.print_exc()
        #end try
        progress.update_fraction(1.0)
        now = time.time()
        sys.stderr.write("Time to import to Blender = %.2fs\n" % (now - start_time))
        if op is not None :
            if failed and created :
                op.report(
                    {"WARNING"},
                    "Imported with %d object error(s); see System Console" % failed,
                )
            elif failed and not created :
                op.report({"ERROR"}, "Import failed for all objects; see System Console")
                return {"CANCELLED"}
            elif importer._skin_imports :
                op.report(
                    {"INFO"},
                    "Imported %d skinned mesh(es) from instance_controller"
                    % len(importer._skin_imports),
                )
            elif err_count and not failed :
                # Already reported parse issues above; keep a brief success note.
                op.report(
                    {"INFO"},
                    "Import finished with %d ignored COLLADA warning(s)" % err_count,
                )
            #end if
        #end if
        return {"FINISHED"}
    finally :
        if progress is not None :
            progress.end()
        #end if
        if c is not None :
            close_collada_archive(c)
        #end if
    #end try
#end load
