# Collada Support 2.0.2

## Changes

- **Crash fix:** Blender 5 export no longer calls `ensure_lookup_table` on bmesh loops (`BMLoopSeq` has no such method). Lookup tables are ensured only on verts/edges/faces when that API exists and is callable. **Remove the old add-on first**, then Install from Disk — overwriting a previous zip can leave 2.0.0/2.0.1 code loaded.
- **Export UI:** File Browser options use FBX-style collapsible sections (Include, Transform, Geometry, Armature, Animation, Extra) instead of cramped Main/Geom/Arm/Anim/Extra tabs.
- **Skin import (#3):** `<instance_controller>` / `<skin>` meshes import as bind-pose geometry plus an Armature and weights.
- **Export fidelity + original Blender 4.5 COLLADA alignment:** native operator options/defaults, IDs, skins, morph targets, XML declaration, A_ONE transparency (Google Earth), triangulate.

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
