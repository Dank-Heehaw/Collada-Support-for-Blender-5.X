# Changelog

All notable changes to **Collada Support for Blender 5.X** are documented here.

## [1.0.4] — 2026-07-18

- Point `website` / `doc_url` at https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
- Preferences: remove first-time **Install pycollada** action; keep **Update / Reinstall pycollada** as optional network fallback
- Clearer errors when bundled pycollada fails to load
- Project cleanup (drop local `reference/` clones from the working tree; keep installable package lean)
- Extensions submission materials under `submission/`
- README download guidance: install **`blender_collada_support.zip`** from Releases, not GitHub **Code → Download ZIP**

## [1.0.3] — 2026-07-18

- Set extension license to **`SPDX:GPL-3.0-or-later`** (required by Blender Extensions Platform)
- Version bump for Extensions install / approval packaging

## [1.0.2] — 2026-07-18

First snapshot published in this repository.

- Bundled **pycollada** (+ `python-dateutil`, `six`) as wheels in the extension package
- Archive import for **`.zae` / `.kmz` / `.zip`** (manifest or auto-picked `.dae`, in-archive textures)
- Import hardening aligned with Blender 4.5 native patterns:
  - Avoid `bpy.ops` / active-object thrash during mesh import
  - Sanitize invalid faces before mesh creation; `mesh.validate()`
  - Batch `foreach_set` for smooth flags, material indices, UVs
  - Per-object error isolation
- Import/export operators for COLLADA under File → Import / Export
- Transform modes: Multiply, Parenting, Apply

## [1.0.1] — 2026-07

- Initial packaging direction: ship **pycollada by default** via Blender extension wheels so users are not required to pip-install for normal use
- Early Blender 5.x operator / preferences scaffolding (superseded by 1.0.2+ packaging in this repo)

[1.0.4]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.4
[1.0.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.3
[1.0.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.0.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
