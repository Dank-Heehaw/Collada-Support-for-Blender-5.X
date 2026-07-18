# Collada Support 1.0.3 — Initial release

First public release of **Collada Support for Blender 5.X** on the Blender Extensions Platform.

## Highlights

- Restores **COLLADA import and export** after Blender 5 removed native OpenCOLLADA support
- **Import**: `.dae`, `.zae`, `.kmz`, and `.zip` (archives with an embedded `.dae`)
- **Export**: `.dae` and `.zae`, COLLADA **1.4.1** or **1.5.0**
- **pycollada bundled as wheels** — enable the extension and use File → Import/Export; no manual pip step in normal use
- Import path hardened with Blender 4.5–style mesh validation and safer batch writes (fewer crashes on bad geometry)

## Import

- Triangle / polylist meshes, UVs, basic materials, textures
- Cameras and lights
- SketchUp and common transform handling
- Per-object error isolation so one bad mesh is less likely to abort the whole file

## Export

- Meshes and Principled materials
- Parenting
- Optional textures and ZAE packaging

## Known limitations

- Skin / armature / animation not supported yet
- Not full feature parity with the former native OpenCOLLADA importer/exporter
- Nested ZAE sub-archives not supported
- Very large files remain limited by XML parse performance

## Credits

pycollada lineage (ldo → B5Collada) and the [pycollada](https://github.com/pycollada/pycollada) library. Licensed **GPL-3.0-or-later**.
