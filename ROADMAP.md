# Roadmap — OpenCOLLADA parity

Staged plan toward Blender 4.5 / OpenCOLLADA feature parity. Static mesh I/O is stabilized first; skin and animation wait on dedicated design.

## Release plan

| Version | Focus |
| --- | --- |
| **1.1.0–1.1.3** | Static correctness + Extensions compliance / package id `collada_support` |
| **1.2.0–1.2.2** | Working wheels-only release; leaner Parenting Empties + import progress (1.2.1); no `sys.path` / `sys.modules` changes (1.2.2) |
| **1.3.0** | Morph / shape-key **import** (then export) |
| **1.4.0** | Armature + skin controller **import** (first slice: one Skin, one skeleton; matrix bone anim later). Bind-pose `instance_controller` mesh + JOINT Armature/weights also ships in **2.0.0** ([#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3)). |
| **1.5.0** | Armature + skin **export** (bind-pose slice also ships in **2.0.0**) |
| **1.6–1.7** | Animation import/export (raw XML layer; pycollada lacks sampler/channel parsing) |
| **2.0.0** | Native-style export options (Main/Geom/Arm/Extra), static scene parity, bind-pose skin export |
| **2.0.1** | Blender 5 `BMLoopSeq` crash fix; operator/ID/skin/morph semantics matched to the 4.5 C++ exporter |
| **2.0.2** | Combined release: #3 skin import + export fidelity + 4.5 alignment + BMLoopSeq crash fix + FBX-style collapsible export UI |
| **2.0.3** (current / `master`) | Mesh export rewritten on Blender Mesh API (no BMesh); persistent BMLoopSeq crash on Blender 5 fixed; includes 2.0.2 combined I/O |

### Export options in **2.0.1**

Match Blender 4.5’s COLLADA exporter Main panel (and Geom/Arm/Extra):

- Selection Only, Include Children, Include Armatures, Include Shape Keys
- Global Orientation: Apply, Up Axis
- Texture Options: Copy, UV Only Selected Map
- Geom: Apply Modifiers, Triangulate, Use Object Instances
- Arm: Deform Bones Only; bind-pose JOINT + skin export
- Extra: Blender profile, custom properties, COLLADA version / ZAE

Animation tabs and morph-target libraries remain later.

## What 1.1.0 fixed vs still pending

**Fixed in 1.1.0**

- Multi-material export: primitive indices/vcounts filtered per material slot
- Empty material slots guarded (no crash on unbound `slot.material`)
- Selection-only export: selected objects are not suppressed by unselected parents; descendants of selected roots are included
- Atomic write for `.dae` / `.zae` (temp file + replace; zip closed on failure)
- Ortho cameras: export `xmag`/`ymag = ortho_scale / 2`; import applies unit scale (and half→full conversion)
- pycollada broken-ref / parse issues summarized in operator reports
- Export asset unit from Blender `unit_settings.scale_length`

**Still pending (later releases)**

- Morph target library + animation (see below)
- Custom split-normal attributes beyond smooth/flat
- Nested ZAE sub-archives
- Broader interop suite vs Blender 4.5 native files

## Rig notes (from design)

Planned modules (not in 1.1.0):

- `collada_rig.py`
- `import_rig.py`
- `collada_animation.py`
- `export_rig.py`

Design constraints:

- Use inverse-bind matrices for bone rest; bake bind-shape; normalize weights; Armature modifier
- Animation needs dedicated XML parsing (`pycollada` `Animation.load` does not build samplers/channels)
- First rig slice (**1.4.0**): **import-only**, one controller, **PARENT** mode, LINEAR/STEP matrix channels

Bind-pose skin **import** (controller geometry + JOINT Armature/weights, no animation) landed in **2.0.0** to fix [#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3). Bind-pose skin **export** (JOINT nodes, inverse bind matrices, vertex weights) landed in **2.0.0** and was aligned to native IDs/bind-shape in **2.0.1**. Morph **target geometries** export in 2.0.1; animation libraries still wait on the milestones above.
