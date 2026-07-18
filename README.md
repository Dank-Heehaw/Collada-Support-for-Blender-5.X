# Collada Support for Blender 5.X

Restores **COLLADA (`.dae` / `.zae`) import and export** for Blender 5 after native OpenCOLLADA support was removed.

Built from the pycollada lineage ([ldo](https://github.com/ldo/blender_pycollada_importexport) → [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport)), with crash/perf hardening guided by Blender **4.5’s native** `MeshImporter` / `DocumentImporter` (batch mesh writes, topology validation, no `bpy.ops` during import).

## Install

1. Use `dist/blender_collada_support.zip` (or zip the `blender_collada_support` folder).
2. Blender 5: **Edit → Preferences → Add-ons → Install…** → select the zip.
3. Enable **Blender Collada Support**.
4. `pycollada` is **bundled as wheels** — no install step needed in normal use.
5. Preferences still offer a pip fallback if wheels fail to load.

Menus:

- **File → Import → COLLADA (.dae, .zae, .kmz, .zip)**
- **File → Export → COLLADA (.dae, .zae)**

## Archive import (ZAE / KMZ / ZIP)

| Format | Behavior |
|---|---|
| **`.zae`** | Official COLLADA zip (`manifest.xml` or auto-picked `.dae`) |
| **`.kmz`** | Earth/Warehouse-style zip with embedded `.dae` + textures |
| **`.zip`** | Any zip containing a `.dae` |

## Import hardening (v1.0.2)

Aligned with Blender 4.5 native importer patterns:

- No `bpy.ops` / Edit Mode / active-object thrashing during import
- Invalid faces rejected before `from_pydata` (out-of-range, degenerate, &lt;3 verts)
- `mesh.validate()` after mesh creation
- Batch `foreach_set` for smooth flags, material indices, and UVs
- Per-object error isolation so one bad mesh does not abort the whole file
- Faster face-index paths (avoid per-triangle Python objects when possible)

## What works today

**Import:** triangle/polylist meshes, UVs, basic materials, textures, cameras/lights, SketchUp quirks, transform modes, archives.

**Export:** meshes, Principled materials, parenting, optional textures/ZAE, COLLADA 1.4.1 or 1.5.0.

## Remaining limitations

- No skin / armature / animation (ekztal-style rig import not ported yet)
- No custom split normals parity with native `use_custom_normals`
- Very large scenes still CPU-bound in pycollada XML parse
- Nested ZAE sub-archives not supported
- Not full feature parity with OpenCOLLADA

## Development layout

```
blender_collada_support/     # installable package (includes wheels/)
reference/                   # upstream clones (not shipped)
dist/                        # distributable zip
```

## License

GPL-2.0-or-later (same family as the upstream Blender / pycollada add-ons).
