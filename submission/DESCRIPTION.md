# Collada Support

Restores **COLLADA** import and export for Blender 5 after native OpenCOLLADA support was removed.

**Homepage:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X  
**Support / issues:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues

Use this add-on when you need to open or save `.dae` files (and related archives) in Blender 5.0 and newer.

## Features

- **Import** COLLADA scenes: triangle and polylist meshes, UVs, vertex colors, basic materials, textures, cameras, and lights
- **Export** meshes (plus curves/text converted to mesh), Principled BSDF materials, parenting, UVs, vertex colors, loop normals, textures, bind-pose armatures/skins, and ZAE packages
- **Archive formats**: `.zae` (official COLLADA zip), `.kmz` (Earth/Warehouse-style), and generic `.zip` containing a `.dae`
- **COLLADA versions** on export: 1.4.1 or 1.5.0
- Import **Parenting** mode recreates SketchUp-style groups as Empties (default)
- SketchUp and common transform quirks handled where practical
- Import hardening inspired by Blender 4.5’s native importer patterns (safer mesh validation, fewer crashes on bad data)

## Install

1. Download the extension package (or `blender_collada_support.zip`).
2. In Blender 5: **Edit → Preferences → Get Extensions / Add-ons → Install from Disk…** and select the zip.
3. Enable **Collada Support**.
4. `pycollada` is **bundled as wheels** — dependencies are not installed via pip.
5. If wheels fail to load, reinstall the release zip (do not use pip).

Menus after install:

- **File → Import → COLLADA (.dae, .zae, .kmz, .zip)**
- **File → Export → COLLADA (.dae, .zae)**

## Formats

| Format | Role |
| --- | --- |
| `.dae` | Standard COLLADA document |
| `.zae` | Zipped COLLADA (`manifest.xml` or auto-picked `.dae`) |
| `.kmz` | Zip with embedded `.dae` and textures |
| `.zip` | Any zip that contains a `.dae` |

## Bundled dependency

This extension ships **pycollada** (and its small dependencies) as wheels inside the package so Blender can load them without a system Python install step.

## Limitations

- Skin **animation** and morph / shape-key library I/O are not implemented yet (bind-pose armature/skin **export** is in 2.0.0)
- Custom split-normal attributes beyond smooth vs flat faces are not full native parity
- Very large scenes remain CPU-bound during XML parse
- Nested ZAE sub-archives are not supported

## Credits

Built on the pycollada Blender lineage:

- [blender_pycollada_importexport](https://github.com/ldo/blender_pycollada_importexport) (Lawrence D'Oliveiro and earlier contributors)
- [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport) (Kims Ferdy)
- Upstream library: [pycollada](https://github.com/pycollada/pycollada)
- Import hardening lessons from Blender 4.5’s native COLLADA importer patterns and related community work

## License

**GPL-3.0-or-later**
