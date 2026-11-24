# Changelog

All notable changes to **Collada Support for Blender 5.X** are documented here.

## [2.0.3] — 2026-11-23

Current installable release. Rewrites mesh export on Blender’s **Mesh** API (`obj.to_mesh` / evaluated mesh, `vertices`, `polygons`, `loops`, `uv_layers`, `color_attributes`, `loop_triangles`). BMesh is no longer imported or used in the exporter, so Blender 5 cannot hit `'BMLoopSeq' object has no attribute 'ensure_lookup_table'`. The shipped Python has **no** `ensure_lookup_table` calls (only a warning comment on `encode_mesh`).

**Includes everything from 2.0.2:** [#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) skin import, 2.0.0 export fidelity, 2.0.1 Blender 4.5 operator/ID/skin/morph alignment, and FBX-style collapsible File Browser panels (Include, Transform, Geometry, Armature, Animation, Extra). Cabinet Vision draft work is **not** in this line.

**Install:** remove the old add-on, **quit Blender fully**, then **Install from Disk** `dist/blender_collada_support.zip` (2.0.3). Confirm Preferences shows **2.0.3**. Reloading over a previous zip can leave old 2.0.0–2.0.2 exporter code loaded.

## [2.0.2] — 2026-11-23

Single installable release that combines skin import, export fidelity, Blender 4.5 operator alignment, a harder Blender 5 export crash fix, and an FBX-style export UI.

**Crash.** Export still failed with `'BMLoopSeq' object has no attribute 'ensure_lookup_table'` after 2.0.1 when Blender kept old add-on code or a zip still contained `loops.ensure_lookup_table`. 2.0.2 never calls `ensure_lookup_table` on loops: only `verts` / `edges` / `faces`, only if that method exists and is callable, and never if the sequence type name contains `Loop`. Loop data is read by iterating `face.loops` / `b_mesh.loops`.

**UI.** Export (and import) File Browser options use collapsible sections like the FBX exporter (`layout.panel`: Include, Transform, Geometry, Armature, Animation, Extra) instead of a cramped Main/Geom/Arm/Anim/Extra tab row. All previous properties are still present.

**Also in this zip**

- **[#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) skin import:** `<instance_controller>` / `<skin>` meshes import as bind-pose geometry plus an Armature and weights (not an Empty joint tree)
- **2.0.0 export fidelity:** per-loop normals, vertex colors, named nodes, modifiers, triangulate, texture copy, bind-pose skin export, XML declaration, A_ONE transparency (Google Earth no longer treats the diffuse map as opacity)
- **2.0.1 original COLLADA alignment:** native 4.5 operator names/defaults, IDs, bind-shape matrices, morph target geometries

**Install:** remove the old add-on first (**Preferences → Add-ons → Collada Support → Remove**), then **Install from Disk** `dist/blender_collada_support.zip`. Overwriting a previous zip in place can leave 2.0.0/2.0.1 code loaded.

## [2.0.1] — 2026-11-23

Crash fix plus export/import alignment with Blender 4.5’s original C++ COLLADA operator (`io_collada.cc` / `source/blender/io/collada`).

**Crash.** Export died with `'BMLoopSeq' object has no attribute 'ensure_lookup_table'`. In Blender 5, `ensure_lookup_table` exists on verts/edges/faces (when present) but **not** on loops. A helper now ensures only those sequences and never calls it on `BMLoopSeq`.

**Original-implementation alignment**

- Export operator properties, defaults, and Main/Geom/Arm/Anim/Extra tabs use the native 4.5 names (`selected`, `use_texture_copies`, `use_blender_profile`, forward/up axes, transform type, OpenSim, precision, animation flags, …)
- Native-style IDs: `{name}-mesh`, `{name}-material`/`-effect`, `{name}-camera`/`-light`, joint `{arm}_{bone}` / SID, skin `{arm}_{obj}-skin`, source suffixes `-positions`/`-normals`/`-map`/`-colors`
- Primitive material symbols and UV `bind_vertex_input` names match GeometryExporter / InstanceWriter
- Texture copies go next to the `.dae` (not a `textures/` subfolder); asset up-axis is always `Z_UP` with Y-forward Z-up as the conversion default
- Skinned meshes write identity node transforms and a real `<bind_shape_matrix>`; inverse bind matrices are rest-pose world inverses in COLLADA column-major order; skeleton URLs point at root JOINT ids
- Include Shape Keys exports morph target geometries + a morph controller (no longer bakes the mix into the basis)
- Invisible objects are skipped; sort-by-name, limit-precision, decomposed TRS, and deform-bones-only follow the C++ exporter
- Import operator exposes native options (`import_units`, `custom_normals`, armature chain flags) and prefers COLLADA `name` plus stripping `-mesh`/`-material` suffixes

**Test plan**

1. Install `dist/blender_collada_support.zip` via **Install from Disk** and confirm Preferences shows **2.0.1**.
2. Default cube with mixed smooth/flat faces: Export COLLADA — must not crash; re-import keeps smoothness.
3. Textured mesh with Copy enabled: image sits beside the `.dae`.
4. Mesh + Armature + weights: DAE contains `<skin>`, JOINT nodes, and `#Armature_Bone` skeleton URLs.

**Still not full OpenCOLLADA parity:** sampled/key animation libraries (`include_animations` is accepted but not yet written), OpenSim extras beyond joint rest tweaks, custom split-normal attributes beyond smooth/flat, nested ZAE, bone-parented object offsets.

## [2.0.0] — 2026-11-23

Feature slice (not tagged as a standalone zip). Export fidelity toward the original Blender 4.5 COLLADA exporter so round-tripped scenes keep the same data, plus import of skinned COLLADA files that previously produced only joint Empties. First installable combined zip is **2.0.2**; current zip is **2.0.3**.

**Root cause.** Geometry wrote VERTEX and NORMAL at the same primitive offset, so only one averaged vertex normal survived and flat/smooth shading was lost. Vertex colors were never written. Scene nodes were anonymous, so object names dropped. Meshes came from unevaluated `Object.data` (no modifiers, no curve conversion). Armatures were skipped entirely (`obj_type_handlers` had no ARMATURE), so skins/weights never left Blender. Texture Copy defaulted off. pycollada omitted the XML declaration. Transmission reused the diffuse map as `<transparent>`, which other tools treat as an opacity texture.

**Restored (practical native parity)**

- Per-loop normals (smooth vertex vs flat face) with separate VERTEX/NORMAL offsets
- Vertex color layers as COLOR (RGBA); import reads them back
- Named visual-scene nodes from the Blender object
- Native-style Main/Geom/Arm/Extra export options: Selection Only, Include Children, Include Armatures, Include Shape Keys, Apply Global Orientation, Up axis, Texture Copy (default on), Only Selected UV Map, Apply Modifiers, Triangulate (default on), Use Object Instances, Deform Bones Only, Custom Properties
- Evaluated meshes (modifiers / current shapekey mix); curves, text, surfaces, metaballs convert to mesh
- Armature as JOINT nodes plus `<skin>` / `instance_controller` (bind pose, inverse bind matrices, vertex weights)
- XML declaration; A_ONE transparency instead of a diffuse-as-opacity map; lambert no longer writes phong-only children
- Object custom properties in the Blender extra profile

**[#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) — instance_controller meshes were skipped.** Scene walking only instantiated `instance_geometry` (plus cameras/lights). Game/DCC files that reference every mesh through `<instance_controller>` / `<skin>` therefore imported as a joint hierarchy of Empties and no mesh. Import now resolves skin and morph controllers to their source geometry and creates the bind-pose mesh in Parenting, Multiply, and Apply modes.

- **Bind-pose armature import:** `type="JOINT"` nodes are converted to a Blender Armature, vertex groups are filled from `<vertex_weights>`, and an Armature modifier is added. Placeholder joint Empties are removed after the bones exist. Animation channels are still not imported.

**Test plan**

1. Install `dist/blender_collada_support.zip` via **Install from Disk** and confirm Preferences shows **2.0.0**.
2. Default cube: Export COLLADA, re-import (Parenting). Mesh, UVs (if unwrapped), and materials survive; file starts with `<?xml`.
3. Mixed smooth/flat cube: re-import keeps face smoothness (not all-smooth).
4. Mesh with a vertex-color layer: export/re-import retains COLOR.
5. Textured Principled material with Copy enabled: image is written beside the `.dae` and bound on re-import.
6. Parent empty → mesh: hierarchy names round-trip.
7. Mesh + Armature + weights: export contains `<library_controllers>` / `<skin>`; re-import shows joints and groups.
8. Optional: same scene from Blender 4.5 native COLLADA vs this add-on; compare sources (normals, COLOR, JOINT, up-axis).

**Still not full OpenCOLLADA parity:** animation/actions, morph target library export, custom split-normal attributes beyond smooth/flat, nested ZAE, decomposed TRS vs matrix, Second Life OpenSim extras.

## [1.2.2] — 2026-08-16

Blender Extensions Platform: no runtime `sys.path` / `sys.modules` changes.

- Remove NumPy site-packages reordering and module-cache purging. Blender loads bundled wheels; pycollada is imported normally.

## [1.2.1] — 2026-07-18

Import UX for large SketchUp / Warehouse files.

- **Leaner Parenting hierarchy:** collapse pass-through COLLADA nodes that have an identity transform, no meaningful name, and a single child (fold into descendants instead of creating Empties). Named groups, non-identity transforms, and multi-child branches are preserved.
- **Import progress:** show Blender status-bar progress across parse / prepare / object-creation phases (XML parse remains synchronous, so a short Not Responding stretch is still possible before the bar advances)

## [1.2.0] — 2026-07-18

Working import/export release after Extensions packaging and pycollada load fixes.

- Prefer Blender’s bundled NumPy over broken leftovers in `scripts/modules` (fixes `numpy.lib._twodim_base_impl` / pycollada load failures)
- Remove add-on preferences status panel and failed-load menu labels
- Report the underlying pycollada import error when an import or export is attempted

### Planned for **2.0** (not in 1.2.0)

Native OpenCOLLADA-style **export** operator options (Main tab and related), including:

- **Selection Only** / **Include Children** / **Include Armatures** / **Include Shape Keys**
- **Global Orientation:** Apply, Forward Axis, Up Axis
- **Texture Options:** Copy, UV Only Selected Map
- Full **Geom** / **Arm** / **Anim** / **Extra** export panels toward Blender 4.5 parity

## [1.1.3] — 2026-07-18

- Remove add-on preferences status panel and failed-load menu labels
- Report the underlying pycollada import error when an import or export is attempted

## [1.1.2] — 2026-07-18

- Package folder / extension id renamed to `collada_support` (version bump for Extensions resubmit)

## [1.1.1] — 2026-07-18

Blender Extensions Platform compliance.

- Extension **title** no longer includes the word “Blender” (`name = "Collada Support"`)
- Remove pip install / update operator and all `sys.path` / `site.addsitedir` module-path manipulation
- Dependencies ship **only** as bundled wheels; drop unused `network` permission

## [1.1.0] — 2026-07-18

Static correctness fixes toward Blender 4.5 parity (remaining gaps now live in [TODO.md](TODO.md)).

- **Multi-material export:** primitive indices/vcounts filtered to faces for each material slot
- **Empty material slots:** guard unbound `slot.material` instead of crashing on `.name`
- **Selection-only export:** selected objects export even when parent is unselected; descendants of selected roots included
- **Atomic write:** DAE/ZAE written to a temp file then replaced; zip closed and temp removed on failure
- **Ortho cameras:** export `xmag`/`ymag = ortho_scale / 2`; import converts half-extent and applies unit scale
- **Parse warnings:** summarize pycollada broken refs / errors in operator reports
- **Units:** export asset `unitmeter` from Blender `unit_settings.scale_length`
- Document staged parity plan (later folded into `TODO.md`)

## [1.0.5] — 2026-07-18

- Default import **Transformations** mode is now **Parenting** (matches Blender 4.5 group trees)
- Parenting uses COLLADA/SketchUp `name` attributes for Empties (`SketchUp`, `group_0`, …) instead of only XML ids
- Local matrices applied after parenting to preserve hierarchy transforms

## [1.0.4] — 2026-07-18

- Point `website` / `doc_url` at https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
- Preferences: remove first-time **Install pycollada** action; keep **Update / Reinstall pycollada** as optional network fallback
- Clearer errors when bundled pycollada fails to load
- Project cleanup (drop local `reference/` clones from the working tree; keep installable package lean)
- Extensions submission materials under `submission/`
- README download guidance: install **`blender_collada_support.zip`** from Releases, not GitHub **Code → Download ZIP**

## [1.0.3] — 2026-07-18

- Set extension license to **`SPDX:GPL-3.0-or-later`** (required by Blender Extensions Platform)
- Version bump for Extensions install / approval packaging

## [1.0.2] — 2026-07-18

First snapshot published in this repository.

- Bundled **pycollada** (+ `python-dateutil`, `six`) as wheels in the extension package
- Archive import for **`.zae` / `.kmz` / `.zip`** (manifest or auto-picked `.dae`, in-archive textures)
- Import hardening aligned with Blender 4.5 native patterns:
  - Avoid `bpy.ops` / active-object thrash during mesh import
  - Sanitize invalid faces before mesh creation; `mesh.validate()`
  - Batch `foreach_set` for smooth flags, material indices, UVs
  - Per-object error isolation
- Import/export operators for COLLADA under File → Import / Export
- Transform modes: Multiply, Parenting, Apply

## [1.0.1] — 2026-07

- Initial packaging direction: ship **pycollada by default** via Blender extension wheels so users are not required to pip-install for normal use
- Early Blender 5.x operator / preferences scaffolding (superseded by 1.0.2+ packaging in this repo)

[2.0.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v2.0.3
[2.0.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v2.0.2
[2.0.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v2.0.1
[2.0.0]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.2.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.2.2
[1.2.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.2.1
[1.2.0]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.2.0
[1.1.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.3
[1.1.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.2
[1.1.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.1
[1.1.0]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.0
[1.0.5]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.0.4]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.4
[1.0.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.3
[1.0.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.0.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
