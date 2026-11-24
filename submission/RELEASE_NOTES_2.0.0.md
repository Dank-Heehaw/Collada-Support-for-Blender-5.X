# Collada Support 2.0.0

## Changes

- **Export fidelity** toward Blender 4.5 native COLLADA: per-loop normals, vertex colors, named object nodes, modifier evaluation, triangulate, texture copy, and native-style Main/Geom/Arm/Extra options.
- **Skin export:** armatures as JOINT nodes, bind-pose `<skin>` controllers, inverse bind matrices, and vertex weights.
- **Materials:** XML declaration; do not reuse the diffuse map as `<transparent>`; lambert effects no longer emit phong-only children.
- **Import:** vertex color layers (COLOR) round-trip with export.

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
