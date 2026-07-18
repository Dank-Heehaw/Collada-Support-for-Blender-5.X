# Roadmap — OpenCOLLADA parity

Staged plan toward Blender 4.5 / OpenCOLLADA feature parity. Static mesh I/O is stabilized first; skin and animation wait on dedicated design.

## Release plan

| Version | Focus |
| --- | --- |
| **1.1.0–1.1.2** (current) | Static correctness (1.1.0) + Extensions compliance / package id `collada_support` (1.1.1–1.1.2) |
| **1.2.0** | Static scene parity — custom/split normals, vertex colors, modifiers / evaluated-mesh options, UV bindings, units/axis options, native Blender profile extras |
| **1.3.0** | Morph / shape-key **import** (then export) |
| **1.4.0** | Armature + skin controller **import** (first slice: one Skin, one skeleton; matrix bone anim later) |
| **1.5.0** | Armature + skin **export** |
| **1.6–1.7** | Animation import/export (raw XML layer; pycollada lacks sampler/channel parsing) |
| **2.0** | Parity candidate + interoperability suite |

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

- Skin / armature / morph / animation (see below)
- Custom split normals, vertex colors, modifier evaluation options
- Full UV-binding and units/axis option parity with the old native exporter
- Nested ZAE sub-archives
- Interop test suite (target **2.0**)

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

Do not land armature/skin/morph/animation work until the corresponding release milestone above.
