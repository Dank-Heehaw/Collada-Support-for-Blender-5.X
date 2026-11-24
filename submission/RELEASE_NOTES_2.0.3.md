# Collada Support 2.0.3

## Changes

- **Mesh export rewritten** on Blender’s Mesh API (`obj.to_mesh` / evaluated mesh, `vertices`, `polygons`, `loops`, `uv_layers`, `color_attributes`, `loop_triangles`). BMesh is no longer used for COLLADA mesh export.
- **Crash fix:** persistent BMLoopSeq crash on Blender 5 is gone because the exporter never builds or indexes BMesh loops.
- Named nodes, materials, texture copy, skins/controllers, morphs, and the FBX-style Include/Transform/Geometry/Armature/Animation options are unchanged — rebuilt on Mesh data.

**Full changelog** : https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/blob/master/CHANGELOG.md
