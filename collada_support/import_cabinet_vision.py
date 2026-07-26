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
# Cabinet Vision (CV) COLLADA import profile.
#
# Derived from the Cabinet Vision to Blender importer by ihartred-cpu:
#   https://github.com/ihartred-cpu/Cabinet-Vision-to-Blender
# Reused here under the terms of its MIT license, reproduced in full:
#
#   MIT License
#
#   Copyright (c) 2026 ihartred-cpu
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the "Software"),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
#
# This profile reads the COLLADA document directly (ElementTree) instead of
# going through pycollada, because Cabinet Vision relies on two parts of the
# spec pycollada does not cover: <library_nodes> + <instance_node> (a part is
# defined once and instanced across assemblies) and <polygons>/<ph>/<h>
# (polygons with holes, used for panel faces with hardware bores and routed
# cutouts). It therefore also works when pycollada fails to load.

import math
import os
import re
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ElementTree
import zipfile

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

try:
    import numpy as np
except ImportError:
    np = None

VERBOSE = True


def _log(msg):
    if VERBOSE:
        sys.stderr.write("import_cabinet_vision: %s\n" % msg)


def _strip(url):
    return url.strip().lstrip("#") if url else ""


# Legacy Cabinet Vision exports (roughly a decade / several major versions
# old) were written by an older Microsoft C runtime that printed non-finite
# floating-point values using the CRT's own text spellings -- "-1.#IND"
# (indeterminate, i.e. NaN), "1.#QNAN", "1.#INF" -- plus limited-precision
# rounded forms like "-1.#J". Python's float() understands "nan"/"inf" but
# none of those, so a single such token in a <float_array> aborted the whole
# import. CV only emitted them where it could not compute a finite coordinate
# in the first place, so every non-finite value is coerced to 0.0 (collapsing
# the affected vertex to the part's local origin, where it can be spotted)
# and counted for a per-geometry warning.
def _parse_floats(text):
    """Parse whitespace-separated floats, tolerating legacy non-finite tokens.

    Returns (values, coerced_count). A malformed token that is not a
    recognizable non-finite spelling still raises, so real corruption is not
    masked: "#" never appears in a valid number, so it is the marker.
    """
    out = []
    coerced = 0
    for tok in text.split():
        try:
            val = float(tok)
            if not math.isfinite(val):
                val = 0.0
                coerced += 1
        except ValueError:
            if "#" in tok:
                val = 0.0
                coerced += 1
            else:
                raise
        out.append(val)
    return out, coerced


def _floats(text):
    return _parse_floats(text)[0]


def _ints(text):
    return [int(tok) for tok in text.split()]


def _cv_part_name(raw):
    """Extract the CV part-type code from a library node name.

    Cabinet Vision names library nodes like "N_TO-Sh3cc841e0_..."; the part
    type ("TO", "AS", "S_DSLAB", ...) is what a person recognizes.
    """
    if raw.startswith("N_") and "-" in raw:
        return raw[2:raw.index("-")]
    return raw


# Name fragments marking a leaf as a *feature* cut into a panel (a drilled
# hole, a dado groove, a notch) rather than an independent physical part.
# Cabinet Vision wraps every feature in its own nested "PA_" node -- even a
# single boring -- so nesting depth alone cannot tell "one panel with holes"
# apart from "an assembly of parts"; only the name can.
_FEATURE_KEYWORDS = ("BORE", "DADO", "NOTCH")

# Subset of the above routed to the hidden features collection rather than
# staying merged and visible. BORE is deliberately excluded: boring geometry
# belongs in the panel, unlike DADO/NOTCH pockets (e.g. "UBDADO") which are
# typically redundant duplicate geometry.
_HIDDEN_FEATURE_KEYWORDS = ("DADO", "NOTCH")

HIDDEN_FEATURES_COLLECTION = "CV Hidden Features"


def _is_feature_name(name):
    upper = name.upper()
    return any(k in upper for k in _FEATURE_KEYWORDS)


def _is_hidden_feature_name(name):
    upper = name.upper()
    return any(k in upper for k in _HIDDEN_FEATURE_KEYWORDS)


# CV's VN_ wrapper ids encode a human-readable assembly label
# ("Base_Cabinet_Assembly", ...) between the hash and a trailing instance
# number, e.g. "VN_Sh41fd5fc0_Base_Cabinet_Assembly_44_a".
_ASSEMBLY_LABEL_RE = re.compile(r"^VN_Sh[0-9a-fA-F]+_(.+?)_\d+(?:_[a-zA-Z])?$")


def _obj_alive(obj):
    """True when obj still refers to a live datablock.

    Objects consumed by an operator join leave dead references behind in the
    post-process tracking lists; touching one raises ReferenceError.
    """
    try:
        return obj.name in bpy.data.objects
    except ReferenceError:
        return False


class _Progress:
    "Best-effort status-bar progress; silently inert without a window manager."

    def __init__(self, wm):
        self.wm = wm
        self._active = False
        if wm is not None:
            try:
                wm.progress_begin(0, 100)
                wm.progress_update(0)
                self._active = True
            except Exception:
                self._active = False

    def update_fraction(self, fraction):
        if not self._active:
            return
        try:
            self.wm.progress_update(max(0, min(100, int(round(fraction * 100)))))
        except Exception:
            pass

    def end(self):
        if not self._active:
            return
        try:
            self.wm.progress_end()
        except Exception:
            pass
        self._active = False


# ──────────────────────────────────────────────────────────────
#  Parser
# ──────────────────────────────────────────────────────────────


class CabinetVisionParser:
    "Read a Cabinet Vision COLLADA document into plain Python structures."

    def __init__(self, filepath):
        self.filepath = filepath
        self.directory = os.path.dirname(os.path.abspath(filepath))
        self.up_axis = "Y_UP"
        self.unit_meter = 1.0
        self.images = {}
        self.effects = {}
        self.materials = {}
        self.geometries = {}
        self.lights = {}
        self.lib_nodes = {}
        self.scene_nodes = []
        self.coerced_floats = 0
        self._node_cache = {}
        self._instance_stack = set()
        root = ElementTree.parse(filepath).getroot()
        self._root = root
        self._ns = root.tag[1:root.tag.index("}")] if root.tag.startswith("{") else ""

    def _t(self, name):
        return "{%s}%s" % (self._ns, name) if self._ns else name

    def _find(self, elem, *path):
        for name in path:
            if elem is None:
                return None
            elem = elem.find(self._t(name))
        return elem

    def _all(self, elem, name):
        return elem.findall(self._t(name)) if elem is not None else []

    def parse(self):
        self._parse_asset()
        self._parse_images()
        self._parse_effects()
        self._parse_materials()
        self._parse_geometries()
        self._parse_lights()
        self._parse_library_nodes()
        self._parse_scene()
        _log(
            "up=%s unit=%s images=%d effects=%d materials=%d geometries=%d "
            "lights=%d library_nodes=%d scene_nodes=%d"
            % (
                self.up_axis,
                self.unit_meter,
                len(self.images),
                len(self.effects),
                len(self.materials),
                len(self.geometries),
                len(self.lights),
                len(self.lib_nodes),
                len(self.scene_nodes),
            )
        )

    def _parse_asset(self):
        asset = self._find(self._root, "asset")
        if asset is None:
            return
        up = self._find(asset, "up_axis")
        if up is not None and up.text:
            self.up_axis = up.text.strip().upper()
        unit = self._find(asset, "unit")
        if unit is not None:
            try:
                self.unit_meter = float(unit.get("meter", "1.0"))
            except ValueError:
                pass

    def _resolve_path(self, raw):
        path = raw.strip()
        for prefix in ("file:///", "file://"):
            if path.lower().startswith(prefix):
                path = path[len(prefix):]
                break
        path = path.replace("%20", " ").replace("%5C", "\\").replace("/", os.sep)
        if not os.path.isabs(path):
            path = os.path.join(self.directory, path)
        return os.path.normpath(path)

    def _parse_images(self):
        lib = self._find(self._root, "library_images")
        for img in self._all(lib, "image"):
            init = self._find(img, "init_from")
            if init is not None and init.text:
                self.images[img.get("id", "")] = self._resolve_path(init.text)

    def _parse_effects(self):
        lib = self._find(self._root, "library_effects")
        for eff in self._all(lib, "effect"):
            self.effects[eff.get("id", "")] = self._one_effect(eff)

    def _one_effect(self, eff_el):
        effect = {
            "color": (0.8, 0.8, 0.8, 1.0),
            "texture_path": None,
            "roughness": 0.5,
            "metallic": 0.0,
            "emission": (0.0, 0.0, 0.0),
        }
        profile = self._find(eff_el, "profile_COMMON")
        if profile is None:
            return effect

        surfaces = {}
        samplers = {}
        for param in self._all(profile, "newparam"):
            sid = param.get("sid", "")
            surface = self._find(param, "surface")
            if surface is not None:
                init = self._find(surface, "init_from")
                if init is not None and init.text:
                    surfaces[sid] = init.text.strip()
            sampler = self._find(param, "sampler2D")
            if sampler is not None:
                src = self._find(sampler, "source")
                if src is not None and src.text:
                    samplers[sid] = src.text.strip()

        def resolve_texture(ref):
            sampled = samplers.get(ref, ref)
            surface = surfaces.get(sampled, sampled)
            return self.images.get(surface) or self.images.get(ref)

        technique = self._find(profile, "technique")
        if technique is None:
            return effect
        shader = None
        for shader_type in ("phong", "lambert", "blinn", "constant"):
            shader = self._find(technique, shader_type)
            if shader is not None:
                break
        if shader is None:
            return effect

        diffuse = self._find(shader, "diffuse")
        if diffuse is not None:
            color_el = self._find(diffuse, "color")
            tex_el = self._find(diffuse, "texture")
            if color_el is not None and color_el.text:
                vals = _floats(color_el.text)
                if len(vals) >= 4:
                    effect["color"] = tuple(vals[:4])
                elif len(vals) == 3:
                    effect["color"] = (vals[0], vals[1], vals[2], 1.0)
            elif tex_el is not None:
                path = resolve_texture(tex_el.get("texture", ""))
                if path:
                    effect["texture_path"] = path
        shininess = self._find(shader, "shininess")
        if shininess is not None:
            float_el = self._find(shininess, "float")
            if float_el is not None and float_el.text:
                try:
                    effect["roughness"] = max(
                        0.0, min(1.0, 1.0 - float(float_el.text) / 128.0)
                    )
                except ValueError:
                    pass
        return effect

    def _parse_materials(self):
        lib = self._find(self._root, "library_materials")
        for mat in self._all(lib, "material"):
            mid = mat.get("id", "")
            entry = {"name": mat.get("name", mid)}
            inst = self._find(mat, "instance_effect")
            if inst is not None:
                entry.update(self.effects.get(_strip(inst.get("url", "")), {}))
            self.materials[mid] = entry

    def _float_source(self, src_el):
        "Decode a <source>'s <float_array> into stride-sized tuples."
        array_el = self._find(src_el, "float_array")
        if array_el is None or not array_el.text:
            return [], 0
        vals, coerced = _parse_floats(array_el.text)
        stride = 1
        accessor = self._find(src_el, "technique_common", "accessor")
        if accessor is not None:
            try:
                stride = max(1, int(accessor.get("stride", "1")))
            except ValueError:
                pass
        rows = [tuple(vals[i:i + stride]) for i in range(0, len(vals), stride)]
        return rows, coerced

    def _parse_geometries(self):
        lib = self._find(self._root, "library_geometries")
        for geom in self._all(lib, "geometry"):
            gid = geom.get("id", "")
            gname = geom.get("name", gid)
            mesh = self._find(geom, "mesh")
            if mesh is None:
                continue

            sources = {}
            coerced = 0
            for src in self._all(mesh, "source"):
                rows, src_coerced = self._float_source(src)
                coerced += src_coerced
                if rows:
                    sources[src.get("id", "").strip()] = rows

            verts_el = self._find(mesh, "vertices")
            pos_sid = None
            if verts_el is not None:
                for inp in self._all(verts_el, "input"):
                    if inp.get("semantic") == "POSITION":
                        pos_sid = _strip(inp.get("source", ""))
                        break

            prims = []
            for prim_type in ("polylist", "triangles", "polygons"):
                for prim in self._all(mesh, prim_type):
                    prims.append((prim_type, prim))

            self.geometries[gid] = {
                "name": gname,
                "sources": sources,
                "pos_sid": pos_sid,
                "prims": prims,
            }
            if coerced:
                self.coerced_floats += coerced
                _log(
                    "WARNING: geometry '%s' had %d non-finite value(s) "
                    "(legacy '-1.#IND'-style export); coerced to 0.0"
                    % (gname, coerced)
                )

    def _parse_lights(self):
        lib = self._find(self._root, "library_lights")
        for light in self._all(lib, "light"):
            lid = light.get("id", "")
            common = self._find(light, "technique_common")
            if common is None:
                continue
            entry = {
                "name": light.get("name", lid),
                "type": "POINT",
                "color": (1.0, 1.0, 1.0),
                "energy": 10.0,
            }
            for cv_type, bl_type in (
                ("point", "POINT"),
                ("directional", "SUN"),
                ("spot", "SPOT"),
                ("ambient", "SUN"),
            ):
                el = self._find(common, cv_type)
                if el is None:
                    continue
                entry["type"] = bl_type
                color_el = self._find(el, "color")
                if color_el is not None and color_el.text:
                    vals = _floats(color_el.text)
                    if len(vals) >= 3:
                        entry["color"] = tuple(vals[:3])
                if cv_type == "spot":
                    falloff = self._find(el, "falloff_angle")
                    if falloff is not None and falloff.text:
                        try:
                            entry["spot_size"] = math.radians(float(falloff.text))
                        except ValueError:
                            pass
                if cv_type == "point":
                    quad = self._find(el, "quadratic_attenuation")
                    if quad is not None and quad.text:
                        try:
                            att = float(quad.text)
                            if att > 1e-8:
                                entry["energy"] = min(1000.0, 1.0 / att)
                        except ValueError:
                            pass
                break
            self.lights[lid] = entry

    def _node_matrix(self, node_el):
        matrix = Matrix.Identity(4)
        for child in node_el:
            tag = child.tag.rpartition("}")[2]
            if not child.text or not child.text.strip():
                continue
            try:
                if tag == "matrix":
                    vals = _floats(child.text)
                    if len(vals) == 16:
                        matrix = matrix @ Matrix(
                            [vals[0:4], vals[4:8], vals[8:12], vals[12:16]]
                        )
                elif tag == "translate":
                    x, y, z = _floats(child.text)[:3]
                    matrix = matrix @ Matrix.Translation((x, y, z))
                elif tag == "rotate":
                    ax, ay, az, angle = _floats(child.text)[:4]
                    axis = Vector((ax, ay, az))
                    if axis.length > 1e-8:
                        matrix = matrix @ Matrix.Rotation(
                            math.radians(angle), 4, axis.normalized()
                        )
                elif tag == "scale":
                    sx, sy, sz = _floats(child.text)[:3]
                    matrix = matrix @ Matrix.Diagonal((sx, sy, sz, 1.0)).to_4x4()
            except (ValueError, ZeroDivisionError):
                continue
        return matrix

    def _parse_library_nodes(self):
        "Index every <node> inside <library_nodes> by id, for <instance_node>."
        lib = self._find(self._root, "library_nodes")
        for node in self._all(lib, "node"):
            nid = node.get("id", "").strip()
            if nid:
                self.lib_nodes[nid] = node

    def _parse_node(self, node_el):
        nid = node_el.get("id", "")
        name = _cv_part_name(node_el.get("name", nid) or nid or "Node")
        geometry_instances = []
        for inst in self._all(node_el, "instance_geometry"):
            symbol_map = {}
            common = self._find(inst, "bind_material", "technique_common")
            for bound in self._all(common, "instance_material"):
                symbol_map[bound.get("symbol", "")] = _strip(bound.get("target", ""))
            geometry_instances.append(
                {"gid": _strip(inst.get("url", "")), "mmap": symbol_map}
            )
        light_instances = [
            _strip(inst.get("url", ""))
            for inst in self._all(node_el, "instance_light")
            if _strip(inst.get("url", ""))
        ]
        children = [self._parse_node(child) for child in self._all(node_el, "node")]
        # Cabinet Vision defines each part once in <library_nodes> and
        # references it from the visual scene through <instance_node>.
        for inst in self._all(node_el, "instance_node"):
            resolved = self._instance_node(_strip(inst.get("url", "")))
            if resolved is not None:
                children.append(resolved)
        return {
            "name": name,
            "mat": self._node_matrix(node_el),
            "ginst": geometry_instances,
            "linst": light_instances,
            "children": children,
        }

    def _instance_node(self, ref_id):
        """Resolve one <instance_node> url against <library_nodes>.

        A library node instanced many times is parsed once and handed out as a
        shallow copy: the builder tracks direct children by identity while
        deciding which sibling absorbs a bore, so two instances of the same
        library node under one parent must not be the same dict.
        """
        node_el = self.lib_nodes.get(ref_id)
        if node_el is None:
            _log("WARNING: instance_node %r is not in library_nodes" % ref_id)
            return None
        if ref_id in self._instance_stack:
            _log("WARNING: instance_node %r is recursive; skipped" % ref_id)
            return None
        parsed = self._node_cache.get(ref_id)
        if parsed is None:
            self._instance_stack.add(ref_id)
            try:
                parsed = self._parse_node(node_el)
            finally:
                self._instance_stack.discard(ref_id)
            self._node_cache[ref_id] = parsed
        return dict(parsed)

    def _parse_scene(self):
        scene = self._find(self._root, "scene")
        instance = self._find(scene, "instance_visual_scene")
        if instance is None:
            return
        wanted = _strip(instance.get("url", ""))
        lib = self._find(self._root, "library_visual_scenes")
        for visual_scene in self._all(lib, "visual_scene"):
            if visual_scene.get("id") == wanted:
                self.scene_nodes = [
                    self._parse_node(node) for node in self._all(visual_scene, "node")
                ]
                break


# ──────────────────────────────────────────────────────────────
#  Builder
# ──────────────────────────────────────────────────────────────


class CabinetVisionBuilder:
    "Turn parsed Cabinet Vision nodes into Blender objects and collections."

    def __init__(
        self,
        parser,
        report_fn=None,
        join_parts=True,
        merge_distance=0.0001,
        hide_feature_parts=True,
        pack_images=False,
    ):
        self.p = parser
        self.report = report_fn or (lambda msg: None)
        self._join_parts = join_parts
        # Distance (Blender units, i.e. metres after CV's unit scale) within
        # which coincident vertices left over from merging independently
        # tessellated faces / edgebanding / boring are welded together.
        self._merge_distance = merge_distance
        self._hide_feature_parts = hide_feature_parts
        self._pack_images = pack_images

        self._materials = {}
        self._unknown_material = None
        self._geom_cache = {}
        self._texture_index = None
        self._created_objects = []
        self._joined_objects = []
        self._join_groups = []
        self._root_col = None
        self._hidden_col = None
        self.stats = {
            "objects": 0,
            "meshes": 0,
            "materials": 0,
            "skipped_geometries": 0,
        }

        if parser.up_axis == "Y_UP":
            self._orient = Matrix.Rotation(math.radians(90), 4, "X")
        elif parser.up_axis == "X_UP":
            self._orient = Matrix.Rotation(math.radians(90), 4, "Y")
        else:
            self._orient = Matrix.Identity(4)

    def build(self, context):
        name = os.path.splitext(os.path.basename(self.p.filepath))[0]
        self._root_col = bpy.data.collections.new(name)
        context.scene.collection.children.link(self._root_col)
        world = self._orient @ Matrix.Scale(self.p.unit_meter, 4)
        for node in self.p.scene_nodes:
            self._build_node(node, self._root_col, world)

    # ── materials & textures ──────────────────────────────────────────

    def _find_texture(self, path):
        if os.path.exists(path):
            return path
        base = os.path.basename(path)
        for sub in ("", "textures", "Textures", "images", "Images", "materials", "Maps"):
            candidate = os.path.join(self.p.directory, sub, base)
            if os.path.exists(candidate):
                return candidate
        # Fall back to a case-insensitive recursive search under the .dae's own
        # directory. The walk runs once and is cached as a filename index.
        if self._texture_index is None:
            self._texture_index = {}
            for root, _dirs, files in os.walk(self.p.directory):
                for fname in files:
                    self._texture_index.setdefault(
                        fname.lower(), os.path.join(root, fname)
                    )
        return self._texture_index.get(base.lower())

    def _make_material(self, mid, mdata):
        # Prefer the texture's filename stem (e.g. "BCW_MAPLE_cee3ec") as the
        # material name; CV material ids are hashes.
        texture_path = mdata.get("texture_path")
        if texture_path:
            mat_name = os.path.splitext(os.path.basename(texture_path))[0]
        else:
            mat_name = mdata.get("name") or mid
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (400, 0)
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        self._set_input(bsdf, "Roughness", mdata.get("roughness", 0.5))
        self._set_input(bsdf, "Metallic", mdata.get("metallic", 0.0))
        emission = mdata.get("emission", (0.0, 0.0, 0.0))
        if any(v > 0.001 for v in emission):
            self._set_input(
                bsdf, ("Emission Color", "Emission"), (*emission[:3], 1.0)
            )
            self._set_input(bsdf, "Emission Strength", 1.0)

        loaded = False
        if texture_path:
            resolved = self._find_texture(texture_path)
            if resolved:
                try:
                    image = bpy.data.images.load(resolved, check_existing=True)
                    image.colorspace_settings.name = "sRGB"
                    if self._pack_images:
                        # The .dae came out of an archive extracted to a temp
                        # directory that is removed when the import finishes.
                        image.pack()
                        image.filepath = "//textures/%s" % os.path.basename(resolved)
                        image.filepath_raw = image.filepath
                    coords = nodes.new("ShaderNodeTexCoord")
                    coords.location = (-600, 200)
                    tex = nodes.new("ShaderNodeTexImage")
                    tex.location = (-300, 200)
                    tex.image = image
                    links.new(coords.outputs["UV"], tex.inputs["Vector"])
                    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
                    loaded = True
                except Exception as exc:
                    _log("texture load failed for %s: %s" % (resolved, exc))
            else:
                _log(
                    "texture NOT FOUND for material '%s': %r (looked under %s)"
                    % (mat_name, texture_path, self.p.directory)
                )
        if not loaded:
            self._set_input(
                bsdf, "Base Color", mdata.get("color", (0.8, 0.8, 0.8, 1.0))
            )
        return mat

    @staticmethod
    def _set_input(shader, names, value):
        "Set the first matching shader input among Blender version aliases."
        if isinstance(names, str):
            names = (names,)
        for name in names:
            socket = shader.inputs.get(name)
            if socket is not None:
                socket.default_value = value
                return True
        return False

    def _material_for(self, mid):
        """Blender material for a COLLADA material id, created on first use.

        Unknown/missing ids share one fallback material instead of spawning a
        datablock per object.
        """
        if mid in self._materials:
            return self._materials[mid]
        mdata = self.p.materials.get(mid)
        if mdata is None:
            if self._unknown_material is None:
                self._unknown_material = bpy.data.materials.new(name="CV_Unknown")
                self._unknown_material.use_nodes = True
            return self._unknown_material
        mat = self._make_material(mid, mdata)
        self._materials[mid] = mat
        self.stats["materials"] += 1
        return mat

    # ── collections ───────────────────────────────────────────────────

    def _hidden_features_col(self):
        """Hidden collection for geometry that is not a visible part of its own.

        One per import (linked under this import's root collection) so repeat
        imports never share -- or re-show -- each other's hidden features.
        """
        if self._hidden_col is None:
            col = bpy.data.collections.new(HIDDEN_FEATURES_COLLECTION)
            self._root_col.children.link(col)
            col.hide_viewport = True
            col.hide_render = True
            self._hidden_col = col
        return self._hidden_col

    @staticmethod
    def _get_or_create_col(parent_col, name):
        for child in parent_col.children:
            if child.name == name:
                return child
        col = bpy.data.collections.new(name)
        parent_col.children.link(col)
        return col

    @staticmethod
    def _collection_key(part_name):
        """Collection-grouping key for a part-type name.

        Every *BORE sub-type (LFVBORE, LRVBORE, _HGCVBORE, ...) shares one
        "Bores" collection per assembly: CV has dozens of bore type codes, and
        grouping by literal name scatters what a person thinks of as one thing
        across many collections.
        """
        return "Bores" if "BORE" in part_name.upper() else part_name

    # ── physical-part detection ───────────────────────────────────────

    def _gather_leaf_names(self, node, out):
        "Depth-first collect the name of every geometry-bearing leaf."
        if node["ginst"]:
            out.append(node["name"])
        for child in node["children"]:
            self._gather_leaf_names(child, out)

    def _is_physical_part_root(self, node):
        """True when a PA_ wrapper represents exactly one physical part.

        It must have a direct, non-PA_ child carrying real panel geometry (a
        face or edgeband), and every nested PA_ child below it must contribute
        only boring/dado/notch features of that same panel.
        """
        direct_structural = any(
            not child["name"].startswith("PA_") and not _is_feature_name(child["name"])
            for child in node["children"]
        )
        if not direct_structural:
            return False
        for child in node["children"]:
            if child["name"].startswith("PA_"):
                names = []
                self._gather_leaf_names(child, names)
                if any(not _is_feature_name(n) for n in names):
                    return False
        return True

    def _pick_primary_name(self, node):
        """Name a merged part after its most common non-feature leaf (e.g. 'RU')."""
        names = []
        self._gather_leaf_names(node, names)
        pool = [n for n in names if not _is_feature_name(n)] or names
        if not pool:
            return node["name"]
        counts = {}
        for name in pool:
            counts[name] = counts.get(name, 0) + 1
        return max(counts.items(), key=lambda kv: kv[1])[0]

    def _first_vn_name(self, node):
        "Depth-first search for the first VN_ wrapper id under node."
        if node["name"].startswith("VN_"):
            return node["name"]
        for child in node["children"]:
            found = self._first_vn_name(child)
            if found:
                return found
        return None

    def _pick_assembly_name(self, node):
        vn_name = self._first_vn_name(node)
        if vn_name:
            match = _ASSEMBLY_LABEL_RE.match(vn_name)
            if match:
                label = match.group(1).replace("_", " ").strip()
                if label:
                    return label
        return "Assembly (%s)" % node["name"]

    # ── geometry decoding (once per gid, cached) ───────────────────────

    def _decode_geometry(self, gid):
        """Decode a <geometry> into local-space arrays, once per gid."""
        if gid in self._geom_cache:
            return self._geom_cache[gid]
        gdata = self.p.geometries.get(gid)
        if gdata is None:
            _log("WARNING: geometry '%s' not found" % gid)
            decoded = None
        else:
            decoded = self._decode_geometry_impl(gdata)
        if decoded is None:
            self.stats["skipped_geometries"] += 1
        self._geom_cache[gid] = decoded
        return decoded

    def _decode_geometry_impl(self, gdata):
        sources = gdata["sources"]
        pos_sid = gdata["pos_sid"]
        prims = gdata["prims"]
        gname = gdata["name"]
        tag = self.p._t

        if pos_sid and pos_sid not in sources:
            pos_sid = None
        if pos_sid is None:
            for _prim_type, prim_el in prims:
                for inp in prim_el.findall(tag("input")):
                    if inp.get("semantic", "") == "POSITION":
                        sid = _strip(inp.get("source", ""))
                        if sid in sources:
                            pos_sid = sid
                            break
                if pos_sid:
                    break
        if pos_sid is None:
            # Last resort: the first stride-3 source in the mesh.
            for sid, rows in sources.items():
                if rows and len(rows[0]) == 3:
                    pos_sid = sid
                    break
        if not pos_sid or pos_sid not in sources:
            msg = "'%s': no position source (sources: %s)" % (
                gname,
                list(sources.keys()),
            )
            _log("SKIP: %s" % msg)
            self.report(msg)
            return None

        pos = [row[:3] for row in sources[pos_sid]]
        if not pos:
            _log("SKIP: '%s': position source is empty" % gname)
            return None
        n_pos = len(pos)

        faces = []
        uvs = []
        symbols = []
        has_uvs = False

        for prim_type, prim_el in prims:
            symbol = prim_el.get("material", "")
            pos_off = 0
            uv_off = None
            uv_src = None
            max_off = 0
            found_pos = False

            for inp in prim_el.findall(tag("input")):
                semantic = inp.get("semantic", "")
                sid = _strip(inp.get("source", ""))
                try:
                    off = int(inp.get("offset", "0").strip())
                except ValueError:
                    off = 0
                max_off = max(max_off, off)
                if semantic in ("VERTEX", "POSITION"):
                    pos_off = off
                    found_pos = True
                    if semantic == "POSITION" and sid and sid != pos_sid and sid in sources:
                        pos_sid = sid
                        pos = [row[:3] for row in sources[sid]]
                        n_pos = len(pos)
                elif semantic == "TEXCOORD" and uv_off is None and sid in sources:
                    uv_off = off
                    uv_src = sources[sid]
                    has_uvs = True

            stride = max_off + 1
            if not found_pos:
                _log("'%s': no VERTEX/POSITION input in <%s>; skipped" % (gname, prim_type))
                continue

            p_el = prim_el.find(tag("p"))
            has_p = p_el is not None and (p_el.text or "").strip()
            # <polygons> can carry its faces inside <ph> elements instead of a
            # top-level <p>, so do not bail out early for that type.
            if not has_p and prim_type != "polygons":
                _log("'%s': no <p> data in <%s>; skipped" % (gname, prim_type))
                continue
            raw = _ints(p_el.text) if has_p else []

            decode = self._decode_corner_block
            if prim_type == "triangles":
                vcounts = [3] * int(prim_el.get("count", "0") or 0)
            elif prim_type == "polylist":
                vcount_el = prim_el.find(tag("vcount"))
                if vcount_el is not None and (vcount_el.text or "").strip():
                    vcounts = _ints(vcount_el.text)
                else:
                    count = int(prim_el.get("count", "0") or 0)
                    if count and len(raw) == count * 3 * stride:
                        vcounts = [3] * count
                    else:
                        _log("'%s': polylist without vcount; skipped" % gname)
                        continue
            elif prim_type == "polygons":
                sub_ps = prim_el.findall(tag("p"))
                ph_els = prim_el.findall(tag("ph"))
                if ph_els:
                    for ph_el in ph_els:
                        self._decode_polygon_with_holes(
                            ph_el, tag, stride, pos_off, uv_off, uv_src,
                            pos, n_pos, symbol, faces, uvs, symbols,
                        )
                    # Plain <p> children can sit alongside <ph> elements.
                    for sub_p in sub_ps:
                        self._append_simple_polygon(
                            sub_p, stride, pos_off, uv_off, uv_src, n_pos,
                            symbol, faces, uvs, symbols,
                        )
                    continue
                if len(sub_ps) > 1:
                    for sub_p in sub_ps:
                        self._append_simple_polygon(
                            sub_p, stride, pos_off, uv_off, uv_src, n_pos,
                            symbol, faces, uvs, symbols,
                        )
                    continue
                total_corners = len(raw) // stride
                for group in (3, 4):
                    if total_corners % group == 0:
                        vcounts = [group] * (total_corners // group)
                        break
                else:
                    vcounts = [total_corners]
            else:
                continue

            cursor = 0
            for vcount in vcounts:
                block_len = vcount * stride
                block = raw[cursor:cursor + block_len]
                cursor += block_len
                if len(block) < block_len:
                    break
                face, face_uvs = decode(
                    block, vcount, stride, pos_off, uv_off, uv_src, n_pos
                )
                if face:
                    faces.append(face)
                    uvs.append(face_uvs)
                    symbols.append(symbol)

        if not faces:
            msg = "'%s': 0 faces built" % gname
            _log("SKIP: %s" % msg)
            self.report(msg)
            return None

        if np is not None:
            positions = np.array(pos, dtype=np.float64)
        else:
            positions = [tuple(p) for p in pos]
        return {
            "name": gname,
            "pos": positions,
            "faces": faces,
            "uvs": uvs,
            "syms": symbols,
            "has_uvs": has_uvs,
        }

    def _append_simple_polygon(
        self, p_el, stride, pos_off, uv_off, uv_src, n_pos, symbol,
        faces, uvs, symbols,
    ):
        if not (p_el.text or "").strip():
            return
        raw = _ints(p_el.text)
        face, face_uvs = self._decode_corner_block(
            raw, len(raw) // stride, stride, pos_off, uv_off, uv_src, n_pos
        )
        if face:
            faces.append(face)
            uvs.append(face_uvs)
            symbols.append(symbol)

    def _decode_polygon_with_holes(
        self, ph_el, tag, stride, pos_off, uv_off, uv_src, pos, n_pos, symbol,
        faces, uvs, symbols,
    ):
        """Tessellate one <ph>: an outer contour plus its <h> hole contours.

        This is what makes hardware bores and routed cutouts exist at all --
        Cabinet Vision exports a drilled panel face as a polygon with holes,
        never as pre-triangulated geometry.
        """
        outer_el = ph_el.find(tag("p"))
        if outer_el is None or not (outer_el.text or "").strip():
            return
        raw = _ints(outer_el.text)
        outer_ids, outer_uvs = self._decode_corner_block(
            raw, len(raw) // stride, stride, pos_off, uv_off, uv_src, n_pos
        )
        if not outer_ids:
            return

        holes = []
        for hole_el in ph_el.findall(tag("h")):
            if not (hole_el.text or "").strip():
                continue
            hole_raw = _ints(hole_el.text)
            hole_ids, hole_uvs = self._decode_corner_block(
                hole_raw, len(hole_raw) // stride, stride, pos_off, uv_off,
                uv_src, n_pos,
            )
            if hole_ids:
                holes.append((hole_ids, hole_uvs))

        if not holes:
            faces.append(outer_ids)
            uvs.append(outer_uvs)
            symbols.append(symbol)
            return

        # tessellate_polygon indexes into the concatenated contour list, so
        # keep outer-then-holes order and map back through that.
        ring_ids = list(outer_ids)
        for hole_ids, _hole_uvs in holes:
            ring_ids.extend(hole_ids)
        uv_by_id = {}
        if outer_uvs:
            uv_by_id.update(zip(outer_ids, outer_uvs))
        for hole_ids, hole_uvs in holes:
            if hole_uvs:
                for vid, uv in zip(hole_ids, hole_uvs):
                    uv_by_id.setdefault(vid, uv)

        contours = [[Vector(pos[vid]) for vid in outer_ids]]
        contours.extend([Vector(pos[vid]) for vid in hole_ids] for hole_ids, _ in holes)
        try:
            tris = tessellate_polygon(contours)
        except Exception as exc:
            _log("tessellate_polygon failed (%s); using the outer contour" % exc)
            faces.append(outer_ids)
            uvs.append(outer_uvs)
            symbols.append(symbol)
            return
        for tri in tris:
            face = [ring_ids[tri[i]] for i in range(3)]
            if len(set(face)) < 3:
                continue
            faces.append(face)
            uvs.append(
                [uv_by_id.get(vid, (0.0, 0.0)) for vid in face] if uv_by_id else None
            )
            symbols.append(symbol)

    @staticmethod
    def _decode_corner_block(raw, n_corners, stride, pos_off, uv_off, uv_src, n_pos):
        "Split one index block into a vertex-index face and its UV corners."
        face = []
        face_uvs = [] if uv_src is not None else None
        for corner in range(n_corners):
            block = raw[corner * stride:(corner + 1) * stride]
            if len(block) < stride:
                return [], None
            index = block[pos_off]
            if index >= n_pos:
                index = n_pos - 1
            face.append(index)
            if face_uvs is not None and uv_off is not None and uv_off < len(block):
                uv_index = block[uv_off]
                uv = uv_src[uv_index] if uv_index < len(uv_src) else (0.0, 0.0)
                face_uvs.append((uv[0], uv[1]))
        if len(face) < 3 or len(set(face)) < 3:
            return [], None
        return face, face_uvs

    # ── mesh object construction ──────────────────────────────────────

    @staticmethod
    def _transform_positions(pos, world):
        "Transform decoded positions by a 4x4 matrix, as a list of triples."
        if np is not None:
            mat = np.array(world, dtype=np.float64)
            return pos @ mat[:3, :3].T + mat[:3, 3]
        return [tuple(world @ Vector(p)) for p in pos]

    def _build_mesh_object(self, name, instances):
        """Build ONE mesh object out of a list of geometry instances.

        An instance is (decoded, world_matrix, symbol_map[, instance_name]).
        A whole physical part -- panel faces plus edgebanding plus boring --
        is assembled directly here rather than as many temporary objects fed
        to the Join operator. World transforms are baked into the vertices.
        Returns (object or None, number of instances that contributed faces).
        """
        vert_blocks = []
        faces = []
        uv_pairs = []
        material_ids = []
        bore_uv_ranges = []
        has_uvs = False
        offset = 0
        used = 0

        for entry in instances:
            if len(entry) == 4:
                decoded, world, symbol_map, inst_name = entry
            else:
                decoded, world, symbol_map = entry
                inst_name = name
            if decoded is None or not decoded["faces"]:
                continue
            verts = self._transform_positions(decoded["pos"], world)
            vert_blocks.append(verts)
            if offset:
                faces.extend(
                    tuple(i + offset for i in face) for face in decoded["faces"]
                )
            else:
                faces.extend(decoded["faces"])
            uv_start = len(uv_pairs)
            for face, face_uvs in zip(decoded["faces"], decoded["uvs"]):
                if face_uvs:
                    uv_pairs.extend(face_uvs)
                else:
                    uv_pairs.extend((0.0, 0.0) for _ in face)
            if inst_name.upper().endswith("BORE"):
                bore_uv_ranges.append((uv_start, len(uv_pairs)))
            material_ids.extend(symbol_map.get(sym, "") for sym in decoded["syms"])
            has_uvs = has_uvs or decoded["has_uvs"]
            offset += len(verts)
            used += 1

        if not faces:
            return None, 0

        mesh = bpy.data.meshes.new(name=name)
        if np is not None:
            all_verts = np.vstack(vert_blocks).tolist()
        else:
            all_verts = [v for block in vert_blocks for v in block]
        mesh.from_pydata(all_verts, [], faces)
        try:
            mesh.validate(clean_customdata=False)
        except TypeError:
            mesh.validate()
        mesh.update()
        topology_intact = len(mesh.polygons) == len(faces)
        if not topology_intact:
            _log(
                "'%s': %d of %d face(s) rejected as invalid topology"
                % (name, len(faces) - len(mesh.polygons), len(faces))
            )

        if has_uvs and topology_intact:
            self._write_uvs(mesh, uv_pairs, bore_uv_ranges)

        slot_of = {}
        for mid in material_ids:
            if mid not in slot_of:
                slot_of[mid] = len(mesh.materials)
                mesh.materials.append(self._material_for(mid))
        if len(slot_of) > 1 and topology_intact:
            indices = [slot_of[mid] for mid in material_ids]
            if np is not None:
                indices = np.fromiter(indices, dtype=np.int32, count=len(indices))
            mesh.polygons.foreach_set("material_index", indices)

        obj = bpy.data.objects.new(name=name, object_data=mesh)
        obj.matrix_world = Matrix.Identity(4)
        self._created_objects.append(obj)
        self.stats["objects"] += 1
        self.stats["meshes"] += 1
        return obj, used

    def _write_uvs(self, mesh, uv_pairs, bore_uv_ranges):
        """Write the merged UV corners, rotating bore UVs onto the panel.

        Each bore is exported as its own separately tessellated cylinder whose
        UV parameterization does not line up with the flat panel it is drilled
        into; a 90 degree rotation aligns it. It is applied per contributing
        instance, not per merged object, because the merged object is named
        after the panel ("TO"/"SL"/"BT"), not after the bore.
        """
        layer = mesh.uv_layers.new(name="UVMap")
        if len(uv_pairs) != len(mesh.loops):
            _log("UV corner count does not match loops; UVs left unset")
            return
        if np is not None:
            uv = np.asarray(uv_pairs, dtype=np.float32)
            for lo, hi in bore_uv_ranges:
                uv[lo:hi] = np.column_stack((1.0 - uv[lo:hi, 1], uv[lo:hi, 0]))
            layer.data.foreach_set("uv", uv.ravel())
            return
        flat = []
        rotated = set()
        for lo, hi in bore_uv_ranges:
            rotated.update(range(lo, hi))
        for i, (u, v) in enumerate(uv_pairs):
            if i in rotated:
                u, v = 1.0 - v, u
            flat.extend((float(u), float(v)))
        layer.data.foreach_set("uv", flat)

    def _make_light(self, ldata, name, world):
        light = bpy.data.lights.new(name=name, type=ldata.get("type", "POINT"))
        light.color = ldata.get("color", (1.0, 1.0, 1.0))
        light.energy = ldata.get("energy", 10.0)
        if light.type == "SPOT" and "spot_size" in ldata:
            light.spot_size = ldata["spot_size"]
        obj = bpy.data.objects.new(name=name, object_data=light)
        obj.matrix_world = world
        self.stats["objects"] += 1
        return obj

    # ── scene walking ─────────────────────────────────────────────────

    def _gather_instances(self, node, world, meshes, lights):
        """Collect every geometry/light instance under node with world matrices.

        This is what lets a whole physical part become one mesh regardless of
        further PA_/VN_ nesting. DADO/NOTCH leaves (never BORE) are diverted
        to the hidden features collection when that option is on: Cabinet
        Vision nests them inside the very panel they cut into, so without this
        their geometry is fused into the panel mesh with no way to hide it
        afterwards.
        """
        if (
            self._hide_feature_parts
            and node["ginst"]
            and _is_hidden_feature_name(node["name"])
        ):
            hidden_col = self._hidden_features_col()
            for inst in node["ginst"]:
                decoded = self._decode_geometry(inst["gid"])
                obj, _used = self._build_mesh_object(
                    node["name"], [(decoded, world, inst["mmap"])]
                )
                if obj:
                    hidden_col.objects.link(obj)
            for child in node["children"]:
                self._gather_instances(child, world @ child["mat"], meshes, lights)
            return
        for inst in node["ginst"]:
            meshes.append(
                (
                    self._decode_geometry(inst["gid"]),
                    world,
                    inst["mmap"],
                    node["name"],
                )
            )
        for lid in node["linst"]:
            lights.append((lid, world))
        for child in node["children"]:
            self._gather_instances(child, world @ child["mat"], meshes, lights)

    def _build_physical_part(self, node, parent_col, world):
        """Build one physical part (faces + edgebanding + boring) as one mesh."""
        primary = self._pick_primary_name(node)
        col = self._get_or_create_col(parent_col, self._collection_key(primary))
        meshes, lights = [], []
        self._gather_instances(node, world, meshes, lights)
        obj, used = self._build_mesh_object(primary, meshes)
        if obj:
            col.objects.link(obj)
            if used > 1:
                # Independently tessellated sub-meshes were merged: queue the
                # result for seam welding and the optional clean-up passes.
                self._joined_objects.append(obj)
        for lid, light_world in lights:
            ldata = self.p.lights.get(lid)
            if ldata is None:
                _log("WARNING: light '%s' not found" % lid)
                continue
            col.objects.link(self._make_light(ldata, primary, light_world))

    def _build_node(self, node, parent_col, parent_world):
        world = parent_world @ node["mat"]
        name = node["name"]

        # Standalone dado/notch reference geometry (never BORE). CV normally
        # nests these inside the one panel they cut into, where the physical
        # part merge absorbs them. A feature shared across parts (e.g. a back
        # panel dado spanning both uprights) instead lands here as an ordinary
        # leaf: helper geometry, so it goes into the hidden collection rather
        # than cluttering the scene under its own name.
        if node["ginst"] and _is_hidden_feature_name(name):
            hidden_col = self._hidden_features_col()
            for inst in node["ginst"]:
                decoded = self._decode_geometry(inst["gid"])
                obj, _used = self._build_mesh_object(
                    name, [(decoded, world, inst["mmap"])]
                )
                if obj:
                    hidden_col.objects.link(obj)
            for child in node["children"]:
                self._build_node(child, hidden_col, world)
            return

        if name.startswith("PA_") and not node["ginst"]:
            self._build_assembly_wrapper(node, parent_col, world)
            return

        # A wrapper with no geometry of its own whose children all have clean
        # CV part names: group each part type into one shared collection inside
        # this node's OWN collection, so same-named parts from sibling nodes
        # elsewhere in the file do not pool together.
        if (
            not node["ginst"]
            and node["children"]
            and all(
                not child["name"].startswith(("VN_", "PA_"))
                for child in node["children"]
            )
        ):
            self._build_clean_collapse(node, parent_col, world)
            return

        if node["children"]:
            current = bpy.data.collections.new(name)
            parent_col.children.link(current)
        else:
            current = parent_col

        for inst in node["ginst"]:
            decoded = self._decode_geometry(inst["gid"])
            obj, _used = self._build_mesh_object(
                name, [(decoded, world, inst["mmap"])]
            )
            if obj:
                current.objects.link(obj)

        for child in node["children"]:
            self._build_node(child, current, world)

        for lid in node["linst"]:
            ldata = self.p.lights.get(lid)
            if ldata is None:
                _log("WARNING: light '%s' not found" % lid)
                continue
            current.objects.link(self._make_light(ldata, name, world))

    def _build_assembly_wrapper(self, node, parent_col, world):
        """Handle a PA_ wrapper: one physical part, or a group of parts.

        If the wrapper's direct children already include real panel geometry
        and every nested PA_ child contributes only features of that panel,
        this is exactly one physical part. Otherwise the wrapper groups
        distinct parts/sub-assemblies (a cabinet, a countertop, a run, a room)
        and gets a collection named from CV's own assembly label, so parts stay
        associated with the assembly they belong to.
        """
        if not (self._join_parts and node["children"]):
            for child in node["children"]:
                self._build_node(child, parent_col, world)
            return

        if self._is_physical_part_root(node):
            self._build_physical_part(node, parent_col, world)
            return

        # CV stacks several anonymous PA_ levels for what is conceptually one
        # assembly, each resolving to the same VN_-derived label. Reuse the
        # existing collection instead of fragmenting into ".001", ".002", ...
        assembly_col = self._get_or_create_col(
            parent_col, self._pick_assembly_name(node)
        )

        # CV sometimes exports a bore as its own PA_+VN_-wrapped sibling of the
        # part it is drilled into -- e.g. hinge bores under a "Molding_Door_NN"
        # wrapper, sibling to the door's real slab wrapper. Classify each
        # direct child by its own leaves first: a child whose entire subtree is
        # bore-only is a donor to be absorbed, not a part. Anything labelled
        # "Widget" (hinge arm/base hardware) is never a valid absorption target
        # even though it is not feature-named.
        target_candidates = []
        bore_only_children = []
        for child in node["children"]:
            leaves = []
            self._gather_leaf_names(child, leaves)
            structural = [n for n in leaves if not _is_feature_name(n)]
            bores = [
                n
                for n in leaves
                if _is_feature_name(n) and not _is_hidden_feature_name(n)
            ]
            if leaves and not structural and bores:
                bore_only_children.append(child)
                continue
            vn_name = self._first_vn_name(child)
            if not (vn_name and "widget" in vn_name.lower()):
                target_candidates.append(child)

        # Track objects through _created_objects rather than the collection's
        # own objects: a child that is not itself one physical part recurses
        # into its own nested sub-collection, so its objects never land
        # directly in assembly_col.
        objects_per_child = {}
        for child in node["children"]:
            before = len(self._created_objects)
            self._build_node(child, assembly_col, world)
            new_objects = self._created_objects[before:]
            if new_objects:
                objects_per_child[id(child)] = new_objects

        if (
            self._hide_feature_parts
            and bore_only_children
            and len(target_candidates) == 1
        ):
            target_objects = objects_per_child.get(id(target_candidates[0]), [])
            bore_objects = [
                obj
                for child in bore_only_children
                for obj in objects_per_child.get(id(child), [])
            ]
            if len(target_objects) == 1 and bore_objects:
                self._join_groups.append([target_objects[0]] + bore_objects)

    def _build_clean_collapse(self, node, parent_col, world):
        own_col = self._get_or_create_col(parent_col, node["name"])
        per_type = {}
        for child in node["children"]:
            # Where the object lands is keyed by _collection_key (bore
            # sub-types share one "Bores" collection); per_type stays keyed by
            # the real child name so bore absorption below is unaffected.
            part_col = self._get_or_create_col(
                own_col, self._collection_key(child["name"])
            )
            before = {obj.name for obj in part_col.objects}
            self._build_node(child, part_col, world)
            new_objects = [obj for obj in part_col.objects if obj.name not in before]
            if new_objects:
                per_type.setdefault(child["name"], []).extend(new_objects)

        # Bores landing here as flat siblings belong to whichever structural
        # part they are drilled into (typically a door/drawer-front slab like
        # "S_DSLAB"), not to hardware siblings grouped alongside them
        # ("_HGARM"/"_HGBASE" hinge arm and base are physical parts, not cuts).
        # Only absorb when exactly one unambiguous target exists.
        wrapper_type_names = {
            child["name"] for child in node["children"] if child["children"]
        }
        bore_types = [
            name
            for name in per_type
            if _is_feature_name(name) and not _is_hidden_feature_name(name)
        ]
        target_types = [
            name
            for name in per_type
            if name not in bore_types and name not in wrapper_type_names
        ]
        absorbed = set()
        if (
            bore_types
            and len(target_types) == 1
            and len(per_type[target_types[0]]) == 1
        ):
            target_obj = per_type[target_types[0]][0]
            bore_objects = [obj for name in bore_types for obj in per_type[name]]
            self._join_groups.append([target_obj] + bore_objects)
            absorbed = set(bore_types) | {target_types[0]}

        for type_name, objects in per_type.items():
            if type_name not in absorbed and len(objects) > 1:
                self._join_groups.append(objects)

    # ── post-processing ───────────────────────────────────────────────

    def join_part_groups(self, context):
        """Join the per-type groups queued by the clean-named collapse path.

        Physical parts do not come through here; they are built merged from
        the start.
        """
        if not self._join_groups:
            return
        view_layer = context.view_layer
        previous_active = view_layer.objects.active
        for obj in list(context.selected_objects):
            obj.select_set(False)
        for group in self._join_groups:
            valid = [
                obj for obj in group if _obj_alive(obj) and obj.name in view_layer.objects
            ]
            if len(valid) < 2:
                continue
            view_layer.objects.active = valid[0]
            for obj in valid:
                obj.select_set(True)
            try:
                bpy.ops.object.join()
                self._joined_objects.append(valid[0])
            except Exception as exc:
                _log("join failed: %s" % exc)
            if _obj_alive(valid[0]):
                valid[0].select_set(False)
        if previous_active is not None and _obj_alive(previous_active):
            view_layer.objects.active = previous_active

    def _live_meshes(self, objects):
        return [
            obj for obj in objects if _obj_alive(obj) and obj.type == "MESH"
        ]

    def weld_seams(self):
        """Weld the duplicate seam vertices that merging leaves behind.

        Each face/edgeband/bore is built from its own vertex list, so
        coincident points are not shared until welded.
        """
        if not self._merge_distance:
            return
        objects = self._live_meshes(self._joined_objects)
        if not objects:
            return
        removed_total = 0
        for obj in objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            before = len(bm.verts)
            bmesh.ops.remove_doubles(
                bm, verts=bm.verts, dist=self._merge_distance
            )
            removed = before - len(bm.verts)
            if removed:
                bm.to_mesh(obj.data)
                obj.data.update()
                removed_total += removed
            bm.free()
        if removed_total:
            _log(
                "merge by distance: welded %d duplicate vertices across %d objects"
                % (removed_total, len(objects))
            )

    def clean_topology(self, angle_limit=math.radians(5.0)):
        """Limited Dissolve + Tris to Quads on each merged object.

        Bore holes are tessellated by CV as fans of small triangles; on the
        flat panel area around them this collapses a lot of redundant
        triangulation. No vertex moves, but the number of faces bounding a
        hole does change, so this stays opt-in.
        """
        objects = self._live_meshes(self._joined_objects)
        if not objects:
            return
        before = after = 0
        for obj in objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            before += len(bm.faces)
            bmesh.ops.dissolve_limit(
                bm,
                angle_limit=angle_limit,
                use_dissolve_boundaries=False,
                verts=bm.verts,
                edges=bm.edges,
            )
            bmesh.ops.join_triangles(
                bm,
                faces=bm.faces,
                angle_face_threshold=math.radians(40),
                angle_shape_threshold=math.radians(40),
            )
            after += len(bm.faces)
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        _log(
            "clean topology: %d -> %d faces across %d merged objects"
            % (before, after, len(objects))
        )

    def flip_uvs(self):
        "Flip the V axis of the first UV layer on this import's objects only."
        for obj in self._live_meshes(self._created_objects):
            if not obj.data.uv_layers:
                continue
            layer = obj.data.uv_layers[0].data
            if np is not None:
                arr = np.empty(len(layer) * 2, dtype=np.float32)
                layer.foreach_get("uv", arr)
                arr[1::2] = 1.0 - arr[1::2]
                layer.foreach_set("uv", arr)
            else:
                flat = [0.0] * (len(layer) * 2)
                layer.foreach_get("uv", flat)
                flat[1::2] = [1.0 - v for v in flat[1::2]]
                layer.foreach_set("uv", flat)

    def mark_hard_edge_seams(self, angle_limit=math.radians(40.0)):
        """Mark edges whose faces meet at more than angle_limit as UV seams.

        Cabinet Vision panels are almost entirely rectilinear, so this lands
        seams where a face genuinely turns a corner -- panel face to edgeband,
        panel face to a merged bore's cylinder wall -- giving a later unwrap
        sensible cut lines. Boundary edges are left alone: there is no second
        face to measure against, and marking every open edge over-segments
        simple parts.
        """
        objects = self._live_meshes(self._created_objects)
        seams = edges = 0
        for obj in objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            edges += len(bm.edges)
            for edge in bm.edges:
                if len(edge.link_faces) == 2 and edge.calc_face_angle() > angle_limit:
                    edge.seam = True
                    seams += 1
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()
        _log(
            "mark hard edges as seams: %d/%d edges marked across %d objects"
            % (seams, edges, len(objects))
        )

    # ── hidden dado/notch repair ──────────────────────────────────────
    #
    # Some panels (typically uprights with a dado cut into their interior face
    # rather than a rabbet cut from an edge) import with the cut invisible.
    # Cabinet Vision builds the recessed floor and side walls of the pocket --
    # that geometry genuinely exists in the file -- but exports the panel's own
    # large flat face without a hole for it, so the pocket sits unseen behind
    # solid material. The signature is distinctive: a large flat face and a
    # much smaller, near-coincident, parallel face (the pocket floor) whose
    # footprint is fully inside the big face's. This cuts away just the
    # covering portion; it never invents geometry.

    @staticmethod
    def _planar_face_groups(bm, normal_round=2, offset_round=4):
        "Cluster faces into coplanar, co-facing groups."
        groups = {}
        for face in bm.faces:
            normal = face.normal
            if normal.length < 1e-6:
                continue
            normal = normal.normalized()
            nkey = (
                round(normal.x, normal_round),
                round(normal.y, normal_round),
                round(normal.z, normal_round),
            )
            offset = round(normal.dot(face.verts[0].co), offset_round)
            group = groups.setdefault(
                (nkey, offset), {"normal": normal, "faces": [], "area": 0.0}
            )
            group["faces"].append(face)
            group["area"] += face.calc_area()
        return groups

    @staticmethod
    def _perpendicular_basis(normal):
        "Two unit vectors spanning the plane perpendicular to normal."
        n = normal.normalized()
        ref = Vector((1.0, 0.0, 0.0))
        if abs(n.dot(ref)) > 0.9:
            ref = Vector((0.0, 1.0, 0.0))
        u = n.cross(ref).normalized()
        return u, n.cross(u).normalized()

    def _find_hidden_dado(
        self, bm, max_depth=0.05, max_area_ratio=0.25, containment_margin=0.01
    ):
        """Find one (covering face, recessed floor) pair, or None.

        max_depth bounds how far behind the big face the floor can sit (a
        dado/notch is shallow relative to its panel); max_area_ratio bounds how
        small the floor must be; containment_margin allows slack when checking
        that the floor sits inside the big face's footprint.
        """
        by_normal = {}
        for (nkey, offset), group in self._planar_face_groups(bm).items():
            by_normal.setdefault(nkey, []).append((offset, group))

        for entries in by_normal.values():
            if len(entries) < 2:
                continue
            entries.sort(key=lambda entry: -entry[1]["area"])
            bridge_offset, bridge = entries[0]
            if bridge["area"] < 1e-6:
                continue
            u_axis, v_axis = self._perpendicular_basis(bridge["normal"])
            origin = bridge["faces"][0].verts[0].co.copy()
            bridge_u = [
                (vert.co - origin).dot(u_axis)
                for face in bridge["faces"]
                for vert in face.verts
            ]
            bridge_v = [
                (vert.co - origin).dot(v_axis)
                for face in bridge["faces"]
                for vert in face.verts
            ]
            bridge_bounds = (
                min(bridge_u), max(bridge_u), min(bridge_v), max(bridge_v)
            )

            for floor_offset, floor in entries[1:]:
                depth = abs(floor_offset - bridge_offset)
                if depth < 1e-5 or depth > max_depth:
                    continue
                if floor["area"] > bridge["area"] * max_area_ratio:
                    continue
                floor_u = [
                    (vert.co - origin).dot(u_axis)
                    for face in floor["faces"]
                    for vert in face.verts
                ]
                floor_v = [
                    (vert.co - origin).dot(v_axis)
                    for face in floor["faces"]
                    for vert in face.verts
                ]
                floor_bounds = (
                    min(floor_u), max(floor_u), min(floor_v), max(floor_v)
                )
                if (
                    floor_bounds[0] < bridge_bounds[0] - containment_margin
                    or floor_bounds[1] > bridge_bounds[1] + containment_margin
                    or floor_bounds[2] < bridge_bounds[2] - containment_margin
                    or floor_bounds[3] > bridge_bounds[3] + containment_margin
                ):
                    continue  # not inside the big face's footprint: no match
                return {
                    "normal": bridge["normal"],
                    "offset": bridge_offset,
                    "u_axis": u_axis,
                    "v_axis": v_axis,
                    "origin": origin,
                    "bridge_bounds": bridge_bounds,
                    "u_lo": floor_bounds[0],
                    "u_hi": floor_bounds[1],
                    "v_lo": floor_bounds[2],
                    "v_hi": floor_bounds[3],
                }
        return None

    @staticmethod
    def _cut_one_hidden_dado(bm, match, edge_margin=1e-4):
        """Bisect the covering face group along the pocket's footprint and
        delete the portion directly over the floor, exposing it. Sides that
        already coincide with the panel's own edge are skipped."""
        normal = match["normal"]
        offset = match["offset"]
        u_axis = match["u_axis"]
        v_axis = match["v_axis"]
        origin = match["origin"]
        nkey = (round(normal.x, 2), round(normal.y, 2), round(normal.z, 2))

        def bridge_faces():
            out = []
            for face in bm.faces:
                if face.normal.length <= 1e-6:
                    continue
                unit = face.normal.normalized()
                key = (round(unit.x, 2), round(unit.y, 2), round(unit.z, 2))
                if key == nkey and abs(normal.dot(face.verts[0].co) - offset) < 1e-4:
                    out.append(face)
            return out

        bounds = match["bridge_bounds"]
        cuts = (
            (u_axis, match["u_lo"], bounds[0]),
            (u_axis, match["u_hi"], bounds[1]),
            (v_axis, match["v_lo"], bounds[2]),
            (v_axis, match["v_hi"], bounds[3]),
        )
        for axis, bound, edge in cuts:
            if abs(bound - edge) < edge_margin:
                continue  # the pocket already reaches the panel's own edge
            bmesh.ops.bisect_plane(
                bm,
                geom=list(bm.verts) + list(bm.edges) + bridge_faces(),
                dist=1e-6,
                plane_co=origin + axis * bound,
                plane_no=axis,
                clear_inner=False,
                clear_outer=False,
            )
            bm.faces.ensure_lookup_table()

        to_delete = []
        for face in bridge_faces():
            coords = [vert.co for vert in face.verts]
            center_u = sum((co - origin).dot(u_axis) for co in coords) / len(coords)
            center_v = sum((co - origin).dot(v_axis) for co in coords) / len(coords)
            if (
                match["u_lo"] - edge_margin < center_u < match["u_hi"] + edge_margin
                and match["v_lo"] - edge_margin < center_v < match["v_hi"] + edge_margin
            ):
                to_delete.append(face)
        count = len(to_delete)
        bmesh.ops.delete(bm, geom=to_delete, context="FACES")
        return count

    def fix_hidden_dado_faces(self, max_per_object=8):
        "Open up hidden dado/notch pockets on each merged part."
        cuts_total = objects_total = 0
        for obj in self._live_meshes(self._joined_objects):
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            cuts_here = 0
            for _attempt in range(max_per_object):
                match = self._find_hidden_dado(bm)
                if not match:
                    break
                cuts_here += self._cut_one_hidden_dado(bm, match)
            if cuts_here:
                bm.to_mesh(obj.data)
                obj.data.update()
                cuts_total += cuts_here
                objects_total += 1
            bm.free()
        if cuts_total:
            _log(
                "fix hidden dado/notch faces: opened %d face(s) across %d object(s)"
                % (cuts_total, objects_total)
            )


# ──────────────────────────────────────────────────────────────
#  Archive support
# ──────────────────────────────────────────────────────────────


def _norm_member(name):
    return name.replace("\\", "/").lstrip("./")


def _pick_archive_dae(zf):
    "Resolve the primary .dae inside a ZAE/KMZ/ZIP archive."
    names = [name for name in zf.namelist() if not name.endswith("/")]
    by_norm = {_norm_member(name).lower(): name for name in names}
    manifest = by_norm.get("manifest.xml")
    if manifest is not None:
        try:
            root = ElementTree.fromstring(zf.read(manifest))
            wanted = ("".join(root.itertext()) or "").strip().split("#", 1)[0].strip()
            member = by_norm.get(_norm_member(wanted).lower())
            if member is not None:
                return member
        except Exception as exc:
            _log("could not parse archive manifest.xml: %s" % exc)
    daes = [name for name in names if _norm_member(name).lower().endswith(".dae")]
    if not daes:
        raise RuntimeError("Archive contains no .dae file")
    top_level = [name for name in daes if "/" not in _norm_member(name)]
    pool = top_level or daes
    return sorted(pool, key=lambda name: _norm_member(name).lower())[0]


def _extract_archive(filepath):
    "Extract a COLLADA archive to a temp directory; return (dae_path, tempdir)."
    tempdir = tempfile.mkdtemp(prefix="collada-support-cv-")
    try:
        with zipfile.ZipFile(filepath) as zf:
            member = _pick_archive_dae(zf)
            zf.extractall(tempdir)
        dae_path = os.path.join(tempdir, *_norm_member(member).split("/"))
        if not os.path.isfile(dae_path):
            raise RuntimeError("Could not extract %s from the archive" % member)
        _log("archive COLLADA root: %s" % member)
        return dae_path, tempdir
    except Exception:
        shutil.rmtree(tempdir, ignore_errors=True)
        raise


# ──────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────


def load(
    op,
    ctx,
    is_archive,
    filepath,
    join_parts=True,
    merge_by_distance=True,
    merge_distance=0.0001,
    clean_topology=False,
    fix_hidden_dados=False,
    hide_feature_parts=True,
    flip_uv_v=False,
    mark_hard_edges=True,
    **_ignored
):
    "Import filepath using the Cabinet Vision profile."
    start = time.time()
    warnings = []
    tempdir = None
    progress = _Progress(getattr(ctx, "window_manager", None))
    try:
        dae_path = filepath
        if is_archive:
            dae_path, tempdir = _extract_archive(filepath)
        progress.update_fraction(0.05)

        parser = CabinetVisionParser(dae_path)
        parser.parse()
        progress.update_fraction(0.35)
        if not parser.scene_nodes:
            msg = "No visual scene nodes found in %s" % os.path.basename(filepath)
            _log(msg)
            if op is not None:
                op.report({"ERROR"}, msg)
            return {"CANCELLED"}

        builder = CabinetVisionBuilder(
            parser,
            report_fn=warnings.append,
            join_parts=join_parts,
            merge_distance=merge_distance if merge_by_distance else 0.0,
            hide_feature_parts=hide_feature_parts,
            pack_images=tempdir is not None,
        )
        builder.build(ctx)
        progress.update_fraction(0.80)
        builder.join_part_groups(ctx)
        builder.weld_seams()
        progress.update_fraction(0.88)
        if clean_topology:
            builder.clean_topology()
        if fix_hidden_dados:
            builder.fix_hidden_dado_faces()
        if flip_uv_v:
            builder.flip_uvs()
        if mark_hard_edges:
            builder.mark_hard_edge_seams()
        progress.update_fraction(1.0)

        summary = (
            "Cabinet Vision import: %d objects from %d geometries, "
            "%d materials in %.2fs"
            % (
                builder.stats["objects"],
                len(parser.geometries),
                builder.stats["materials"],
                time.time() - start,
            )
        )
        _log(summary)
        if op is not None:
            # Cap the per-geometry warnings; a broken export can produce one
            # for every geometry in the file.
            for warning in warnings[:8]:
                op.report({"WARNING"}, warning)
            if len(warnings) > 8:
                op.report(
                    {"WARNING"},
                    "%d more geometry warning(s); see the System Console"
                    % (len(warnings) - 8),
                )
            if parser.coerced_floats:
                op.report(
                    {"WARNING"},
                    "%d non-finite value(s) in this legacy export were "
                    "coerced to 0.0" % parser.coerced_floats,
                )
            op.report({"INFO"}, summary)
        return {"FINISHED"}
    except Exception as exc:
        import traceback

        traceback.print_exc()
        if op is not None:
            op.report({"ERROR"}, "Cabinet Vision import failed: %s" % exc)
        return {"CANCELLED"}
    finally:
        progress.end()
        if tempdir is not None:
            shutil.rmtree(tempdir, ignore_errors=True)
