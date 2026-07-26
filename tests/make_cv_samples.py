"""Generate synthetic Cabinet Vision shaped COLLADA samples.

These stand in for real Cabinet Vision exports (which cannot be committed
here): they exercise <library_nodes> + <instance_node> instancing, <polygons>
with <ph>/<h> holes, feature nesting (bore/dado), sibling bore absorption,
hinge-hardware exclusion, legacy non-finite float tokens, and a .zae archive.

Usage:
    python3 tests/make_cv_samples.py [output_dir]

Default output directory is tests/_samples (gitignored).
"""

import os
import sys
import zipfile

HEADER = """<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <contributor><authoring_tool>Cabinet Vision Solid</authoring_tool></contributor>
    <unit meter="1.0" name="meter"/>
    <up_axis>Z_UP</up_axis>
  </asset>
  <library_effects>
    <effect id="eff_maple">
      <profile_COMMON>
        <technique sid="common">
          <phong>
            <diffuse><color>0.8 0.6 0.3 1</color></diffuse>
            <shininess><float>32</float></shininess>
          </phong>
        </technique>
      </profile_COMMON>
    </effect>
  </library_effects>
  <library_materials>
    <material id="mat_maple" name="Maple">
      <instance_effect url="#eff_maple"/>
    </material>
  </library_materials>
"""

FOOTER = """  <scene>
    <instance_visual_scene url="#cv_scene"/>
  </scene>
</COLLADA>
"""


def quad_geometry(gid, size, z, bad_float=None, uvs=False):
    "One flat quad as a <polylist>, optionally with a legacy non-finite token."
    positions = [(0, 0, z), (size, 0, z), (size, size, z), (0, size, z)]
    coords = ["%g" % v for p in positions for v in p]
    if bad_float is not None:
        coords[2] = bad_float
    return """    <geometry id="{gid}" name="{gid}">
      <mesh>
        <source id="{gid}_pos">
          <float_array id="{gid}_pos_a" count="12">{coords}</float_array>
          <technique_common>
            <accessor source="#{gid}_pos_a" count="4" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="{gid}_verts">
          <input semantic="POSITION" source="#{gid}_pos"/>
        </vertices>
        <polylist count="1" material="sym_maple">
          <input semantic="VERTEX" source="#{gid}_verts" offset="0"/>
          <vcount>4</vcount>
          <p>0 1 2 3</p>
        </polylist>
      </mesh>
    </geometry>
""".format(gid=gid, coords=" ".join(coords))


def panel_with_hole(gid="g_panel", z=0.0, with_uvs=True):
    """A 1x1 panel with a 0.2x0.2 hole, written as <polygons> + <ph>/<h>.

    Tessellating outer + hole gives 8 triangles and an area of 0.96.
    """
    positions = [
        (0, 0, z), (1, 0, z), (1, 1, z), (0, 1, z),
        (0.4, 0.4, z), (0.6, 0.4, z), (0.6, 0.6, z), (0.4, 0.6, z),
    ]
    coords = " ".join("%g" % v for p in positions for v in p)
    if not with_uvs:
        return """    <geometry id="{gid}" name="{gid}">
      <mesh>
        <source id="{gid}_pos">
          <float_array id="{gid}_pos_a" count="24">{coords}</float_array>
          <technique_common>
            <accessor source="#{gid}_pos_a" count="8" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="{gid}_verts">
          <input semantic="POSITION" source="#{gid}_pos"/>
        </vertices>
        <polygons count="1" material="sym_maple">
          <input semantic="VERTEX" source="#{gid}_verts" offset="0"/>
          <ph><p>0 1 2 3</p><h>4 5 6 7</h></ph>
        </polygons>
      </mesh>
    </geometry>
""".format(gid=gid, coords=coords)
    uv_coords = " ".join("%g %g" % (x, y) for x, y, _z in positions)
    return """    <geometry id="{gid}" name="{gid}">
      <mesh>
        <source id="{gid}_pos">
          <float_array id="{gid}_pos_a" count="24">{coords}</float_array>
          <technique_common>
            <accessor source="#{gid}_pos_a" count="8" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <source id="{gid}_uv">
          <float_array id="{gid}_uv_a" count="16">{uv_coords}</float_array>
          <technique_common>
            <accessor source="#{gid}_uv_a" count="8" stride="2">
              <param name="S" type="float"/><param name="T" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="{gid}_verts">
          <input semantic="POSITION" source="#{gid}_pos"/>
        </vertices>
        <polygons count="1" material="sym_maple">
          <input semantic="VERTEX" source="#{gid}_verts" offset="0"/>
          <input semantic="TEXCOORD" source="#{gid}_uv" offset="1"/>
          <ph>
            <p>0 0 1 1 2 2 3 3</p>
            <h>4 4 5 5 6 6 7 7</h>
          </ph>
        </polygons>
      </mesh>
    </geometry>
""".format(gid=gid, coords=coords, uv_coords=uv_coords)


CABINET_LIBRARY_NODES = """  <library_nodes>
    <node id="lib_face" name="N_TO-Sh3cc841e0_face">
      <instance_geometry url="#g_panel">
        <bind_material><technique_common>
          <instance_material symbol="sym_maple" target="#mat_maple"/>
        </technique_common></bind_material>
      </instance_geometry>
    </node>
    <node id="lib_bore" name="N_LFVBORE-Sh55aa11bb_bore">
      <instance_geometry url="#g_bore"/>
    </node>
    <node id="lib_dado" name="N_UBDADO-Sh77cc22dd_dado">
      <instance_geometry url="#g_dado"/>
    </node>
    <node id="lib_bottom" name="N_BT-Sh99ee33ff_bottom">
      <instance_geometry url="#g_bottom">
        <bind_material><technique_common>
          <instance_material symbol="sym_maple" target="#mat_maple"/>
        </technique_common></bind_material>
      </instance_geometry>
    </node>
  </library_nodes>
"""

CABINET_VISUAL_SCENE = """  <library_visual_scenes>
    <visual_scene id="cv_scene" name="cv_scene">
      <node id="pa_job" name="PA_job">
        <node id="pa_cabinet" name="PA_cabinet_1">
          <node id="pa_panel_to" name="PA_panel_to">
            <node id="vn_to" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_44_a">
              <instance_node url="#lib_face"/>
            </node>
            <node id="pa_bore" name="PA_bore_1">
              <node id="vn_bore" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_44_b">
                <instance_node url="#lib_bore"/>
              </node>
            </node>
            <node id="pa_dado" name="PA_dado_1">
              <node id="vn_dado" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_44_c">
                <instance_node url="#lib_dado"/>
              </node>
            </node>
          </node>
          <node id="pa_panel_bt" name="PA_panel_bt">
            <node id="vn_bt" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_44_d">
              <instance_node url="#lib_bottom"/>
            </node>
          </node>
        </node>
      </node>
    </visual_scene>
  </library_visual_scenes>
"""


def cabinet_geometries(bad_dado=False):
    return "  <library_geometries>\n%s%s%s%s  </library_geometries>\n" % (
        panel_with_hole(),
        quad_geometry("g_bore", 0.1, 0.05),
        quad_geometry(
            "g_dado", 0.2, 0.02, bad_float="-1.#IND" if bad_dado else None
        ),
        quad_geometry("g_bottom", 1.0, -0.5),
    )


def write_document(path, geometries, library_nodes, visual_scene, header=HEADER):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(header)
        handle.write(geometries)
        handle.write(library_nodes)
        handle.write(visual_scene)
        handle.write(FOOTER)
    print("wrote", path)
    return path


BARE_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit meter="1.0" name="meter"/><up_axis>Z_UP</up_axis></asset>
"""

ABSORB_LIBRARY_NODES = """  <library_nodes>
    <node id="lib_slab2" name="N_S_DSLAB-Shdd01_slab"><instance_geometry url="#g_slab2"/></node>
    <node id="lib_bore_b" name="N__HGAVBORE-Shdd02_bore"><instance_geometry url="#g_bore_b"/></node>
    <node id="lib_arm" name="N__HGARM-Shdd03_arm"><instance_geometry url="#g_arm"/></node>
  </library_nodes>
"""

# Two shapes Cabinet Vision uses for a bore that belongs to a panel but is
# exported beside it: a bare wrapper of clean-named siblings (Door_01) and a
# PA_ assembly where the bore has its own PA_+VN_ wrapper, next to hinge
# hardware that must never be treated as the absorption target.
ABSORB_VISUAL_SCENE = """  <library_visual_scenes><visual_scene id="cv_scene">
    <node id="door_01" name="Door_01">
      <node id="leaf_slab" name="N_S_DSLAB-Shcc01_slab">
        <instance_geometry url="#g_slab"/>
      </node>
      <node id="leaf_bore" name="N__HGAVBORE-Shcc02_bore">
        <instance_geometry url="#g_bore_a"/>
      </node>
    </node>
    <node id="pa_door_assembly" name="PA_door_assembly">
      <node id="pa_door_10" name="PA_door_10">
        <node id="vn_door_10" name="VN_Sh1a2b_Door_10_a">
          <instance_node url="#lib_slab2"/>
        </node>
      </node>
      <node id="pa_molding_10" name="PA_molding_door_10">
        <node id="vn_molding_10" name="VN_Sh1a2b_Molding_Door_10_b">
          <instance_node url="#lib_bore_b"/>
        </node>
      </node>
      <node id="pa_widget" name="PA_widget_arm">
        <node id="vn_widget" name="VN_Sh1a2b_Widget_Arm_11_a">
          <instance_node url="#lib_arm"/>
        </node>
      </node>
    </node>
  </visual_scene></library_visual_scenes>
"""

STRESS_LIBRARY_NODES = """  <library_nodes>
    <node id="lib_face" name="N_TO-Shaa01_face"><instance_geometry url="#g_panel"/></node>
    <node id="lib_eb" name="N_EB-Shaa02_eb"><instance_geometry url="#g_eb"/></node>
    <node id="lib_bore" name="N_LFVBORE-Shaa03_bore"><instance_geometry url="#g_bore"/></node>
    <node id="lib_dado" name="N_UBDADO-Shaa04_dado"><instance_geometry url="#g_dado"/></node>
  </library_nodes>
"""

STRESS_ASSEMBLIES = 40
STRESS_PARTS_PER_ASSEMBLY = 25


def stress_visual_scene():
    out = ['  <library_visual_scenes><visual_scene id="cv_scene">\n']
    out.append('    <node id="pa_job" name="PA_job">\n')
    for asm in range(STRESS_ASSEMBLIES):
        out.append('      <node id="pa_asm_%d" name="PA_assembly_%d">\n' % (asm, asm))
        for part in range(STRESS_PARTS_PER_ASSEMBLY):
            out.append(
                '        <node id="pa_part_{a}_{p}" name="PA_part_{a}_{p}">\n'
                "          <translate>{tx} {ty} 0</translate>\n"
                '          <node id="vn_{a}_{p}" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_{a}_a">\n'
                '            <instance_node url="#lib_face"/>\n'
                '            <instance_node url="#lib_eb"/>\n'
                "          </node>\n"
                '          <node id="pa_bore_{a}_{p}" name="PA_bore_{a}_{p}">\n'
                '            <node id="vnb_{a}_{p}" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_{a}_b">\n'
                '              <instance_node url="#lib_bore"/>\n'
                "            </node>\n"
                "          </node>\n"
                '          <node id="pa_dado_{a}_{p}" name="PA_dado_{a}_{p}">\n'
                '            <node id="vnd_{a}_{p}" name="VN_Sh41fd5fc0_Base_Cabinet_Assembly_{a}_c">\n'
                '              <instance_node url="#lib_dado"/>\n'
                "            </node>\n"
                "          </node>\n"
                "        </node>\n".format(
                    a=asm, p=part, tx="%g" % (part * 1.2), ty="%g" % (asm * 1.2)
                )
            )
        out.append("      </node>\n")
    out.append("    </node>\n")
    out.append("  </visual_scene></library_visual_scenes>\n")
    return "".join(out)


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)

    clean = write_document(
        os.path.join(out_dir, "cv_sample.dae"),
        cabinet_geometries(),
        CABINET_LIBRARY_NODES,
        CABINET_VISUAL_SCENE,
    )
    write_document(
        os.path.join(out_dir, "cv_legacy.dae"),
        cabinet_geometries(bad_dado=True),
        CABINET_LIBRARY_NODES,
        CABINET_VISUAL_SCENE,
    )

    archive = os.path.join(out_dir, "cv_sample.zae")
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("manifest.xml", "<dae_root>./models/cv_sample.dae</dae_root>")
        zf.write(clean, "models/cv_sample.dae")
    print("wrote", archive)

    absorb_geometries = "  <library_geometries>\n%s%s%s%s%s  </library_geometries>\n" % (
        quad_geometry("g_slab", 1.0, 0.0),
        quad_geometry("g_bore_a", 0.1, 0.01),
        quad_geometry("g_slab2", 1.0, 2.0),
        quad_geometry("g_bore_b", 0.1, 2.01),
        quad_geometry("g_arm", 0.2, 2.5),
    )
    write_document(
        os.path.join(out_dir, "cv_absorb.dae"),
        absorb_geometries,
        ABSORB_LIBRARY_NODES,
        ABSORB_VISUAL_SCENE,
        header=BARE_HEADER,
    )

    stress_geometries = "  <library_geometries>\n%s%s%s%s  </library_geometries>\n" % (
        panel_with_hole(with_uvs=False),
        quad_geometry("g_eb", 1.0, 0.02),
        quad_geometry("g_bore", 0.1, 0.03),
        quad_geometry("g_dado", 0.2, 0.04),
    )
    write_document(
        os.path.join(out_dir, "cv_stress.dae"),
        stress_geometries,
        STRESS_LIBRARY_NODES,
        stress_visual_scene(),
        header=BARE_HEADER,
    )
    print(
        "stress file has %d parts"
        % (STRESS_ASSEMBLIES * STRESS_PARTS_PER_ASSEMBLY)
    )


if __name__ == "__main__":
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_samples")
    main(sys.argv[1] if len(sys.argv) > 1 else default_dir)
