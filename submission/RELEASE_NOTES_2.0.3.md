# Collada Support 2.0.3

## Changes

- **Mesh export rewritten** on Blender’s Mesh API (`obj.to_mesh` / evaluated mesh, `vertices`, `polygons`, `loops`, `uv_layers`, `color_attributes`, `loop_triangles`). BMesh is no longer used for COLLADA mesh export.
- **Crash fix:** persistent BMLoopSeq crash on Blender 5 is gone because the exporter never builds or indexes BMesh loops. Shipped Python has no `ensure_lookup_table` calls.
- Named nodes, materials, texture copy, skins/controllers, morphs, and the FBX-style Include/Transform/Geometry/Armature/Animation/Extra options are unchanged — rebuilt on Mesh data.
- **Also includes 2.0.2:** skin import from `<instance_controller>` ([#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3)), export fidelity vs Blender 4.5 native COLLADA, native operator names/IDs, and FBX-style File Browser panels.

**Install:** remove the old add-on, quit Blender fully, then **Install from Disk** `blender_collada_support.zip`. Confirm Preferences shows **2.0.3**. Overwriting a previous zip in place can leave 2.0.0–2.0.2 code loaded.

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
