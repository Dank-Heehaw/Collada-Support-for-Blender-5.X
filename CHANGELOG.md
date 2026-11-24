# Changelog

All notable changes to **Collada Support for Blender 5.X** are documented here.

## [2.0.0] — unreleased

Export fidelity toward the original Blender 4.5 COLLADA exporter so round-tripped scenes keep the same data.

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

**Test plan**

1. Install `dist/blender_collada_support.zip` via **Install from Disk** and confirm Preferences shows **2.0.0**.
2. Default cube: Export COLLADA, re-import (Parenting). Mesh, UVs (if unwrapped), and materials survive; file starts with `<?xml`.
3. Mixed smooth/flat cube: re-import keeps face smoothness (not all-smooth).
4. Mesh with a vertex-color layer: export/re-import retains COLOR.
5. Textured Principled material with Copy enabled: image is written beside the `.dae` and bound on re-import.
6. Parent empty → mesh: hierarchy names round-trip.
7. Mesh + Armature + weights: export contains `<library_controllers>` / `<skin>`; re-import in a tool that reads controllers (or this add-on after the separate #3 import fix) shows joints and groups.
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

Static correctness fixes toward Blender 4.5 parity (see [ROADMAP.md](ROADMAP.md)).

- **Multi-material export:** primitive indices/vcounts filtered to faces for each material slot
- **Empty material slots:** guard unbound `slot.material` instead of crashing on `.name`
- **Selection-only export:** selected objects export even when parent is unselected; descendants of selected roots included
- **Atomic write:** DAE/ZAE written to a temp file then replaced; zip closed and temp removed on failure
- **Ortho cameras:** export `xmag`/`ymag = ortho_scale / 2`; import converts half-extent and applies unit scale
- **Parse warnings:** summarize pycollada broken refs / errors in operator reports
- **Units:** export asset `unitmeter` from Blender `unit_settings.scale_length`
- Document staged parity plan in `ROADMAP.md`

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
