# Collada Support 2.0.1

## Changes

- **Crash fix:** COLLADA export no longer calls `ensure_lookup_table` on bmesh loops (`BMLoopSeq` has no such method in Blender 5). Lookup tables are ensured only on verts/edges/faces when those APIs exist.
- **Original Blender 4.5 COLLADA alignment:** export operator options, defaults, and Main/Geom/Arm/Anim/Extra UI match `WM_OT_collada_export`. Mesh/normal/UV/color sources, material symbols, texture copy, named nodes, armatures/skins, bind-shape matrices, and morph target geometries follow the C++ exporter semantics.
- **Import:** native option names (`import_units`, `custom_normals`, armature flags) and mesh/material names from COLLADA `name` / `-mesh` suffixes.

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
