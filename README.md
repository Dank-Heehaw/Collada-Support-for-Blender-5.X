# Collada Support for Blender 5.X

Restores **COLLADA** import and export for Blender 5 after native OpenCOLLADA support was removed.

**Current version: 2.0.3** — Mesh-API export (no BMesh), skin import, Blender 4.5-aligned options, FBX-style File Browser panels. History: **[CHANGELOG.md](CHANGELOG.md)**. Remaining work: **[TODO.md](TODO.md)**.

**Project:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X  
**Issues:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues  
**License:** [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)

## Install

Download **only** the release asset:

**[`blender_collada_support.zip`](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/latest/download/blender_collada_support.zip)**

Do **not** use GitHub **Code → Download ZIP** (source tree, not installable).

1. In Blender 5: **Edit → Preferences → Add-ons → Install from Disk…**
2. Select **`blender_collada_support.zip`**. Do not extract it first.
3. Enable **Collada Support**. **pycollada is bundled** — no pip install.
4. If you already had an older zip: **Remove** the add-on, **quit Blender fully**, then Install from Disk again. Confirm Preferences shows **2.0.3**.

Menus: **File → Import → COLLADA (.dae, .zae, .kmz, .zip)** and **File → Export → COLLADA (.dae, .zae)**.

Import **Transformations → Parenting** (default) recreates SketchUp-style groups. **Multiply** flattens; **Apply** bakes transforms into mesh data.

## What it covers

Import/export of meshes, UVs, vertex colors, Principled materials, textures, cameras, lights, bind-pose armatures/skins (`instance_controller`), morph target geometries, and ZAE/KMZ archives. Mesh export uses Blender’s Mesh API only (no BMesh). Options match Blender 4.5 names in FBX-style collapsible panels.

Full version history is in [CHANGELOG.md](CHANGELOG.md). Known gaps and local resource paths are in [TODO.md](TODO.md). Zip build, wheels, and test checklist: [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

Built from the pycollada lineage ([ldo](https://github.com/ldo/blender_pycollada_importexport) → [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport)), with import hardening guided by Blender **4.5** native COLLADA patterns. Upstream: [pycollada](https://github.com/pycollada/pycollada).
