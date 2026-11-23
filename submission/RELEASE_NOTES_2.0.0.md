# Collada Support 2.0.0

## Changes

- **Import skinned COLLADA meshes** (`<instance_controller>` / `<skin>`). Files that only reference geometry through controllers no longer import as an Empty joint tree with no mesh ([#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3)).
- **Bind-pose Armature:** `type="JOINT"` nodes become a Blender Armature; vertex groups come from `<vertex_weights>`; an Armature modifier binds each controller mesh. Animation is not imported.

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
