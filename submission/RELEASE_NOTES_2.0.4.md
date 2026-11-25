# Collada Support 2.0.4

## Changes

- **Texture Copy:** relative Blender image paths (`//tex.png`) now copy correctly on Windows. Export uses `bpy.path.abspath` / `bpy.path.basename` instead of `os.path.basename`, which treated `//` as a UNC path and produced an empty filename.
- **Scripted export:** `bpy.ops.export_scene.collada(filepath=...)` without `directory=` no longer fails with an empty-path `WinError 3`. The output directory is derived from `filepath` when needed, and created if missing.

**Install:** remove the old add-on, quit Blender fully, then **Install from Disk** `blender_collada_support.zip` from Releases (not GitHub **Code → Download ZIP**). Confirm Preferences shows **2.0.4**.

**Full changelog** (2.0.0–2.0.4 and earlier): https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/blob/master/CHANGELOG.md
