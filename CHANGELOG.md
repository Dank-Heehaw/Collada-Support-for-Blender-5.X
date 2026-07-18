# Changelog

All notable changes to **Collada Support for Blender 5.X** are documented here.

## [1.2.0] — 2026-07-18

Working import/export release after Extensions packaging and pycollada load fixes.

- Prefer Blender’s bundled NumPy over broken leftovers in `scripts/modules` (fixes `numpy.lib._twodim_base_impl` / pycollada load failures)
- Remove add-on preferences status panel and failed-load menu labels
- Report the underlying pycollada import error when an import or export is attempted

### Planned for **2.0** (not in 1.2.0)

Native OpenCOLLADA-style **export** operator options (Main tab and related), including:

- **Selection Only** / **Include Children** / **Include Armatures** / **Include Shape Keys**
- **Global Orientation:** Apply, Forward Axis, Up Axis
- **Texture Options:** Copy, UV Only Selected Map
- Full **Geom** / **Arm** / **Anim** / **Extra** export panels toward Blender 4.5 parity

## [1.1.3] — 2026-07-18

- Remove add-on preferences status panel and failed-load menu labels
- Report the underlying pycollada import error when an import or export is attempted

## [1.1.2] — 2026-07-18

- Package folder / extension id renamed to `collada_support` (version bump for Extensions resubmit)

## [1.1.1] — 2026-07-18

Blender Extensions Platform compliance.

- Extension **title** no longer includes the word “Blender” (`name = "Collada Support"`)
- Remove pip install / update operator and all `sys.path` / `site.addsitedir` module-path manipulation
- Dependencies ship **only** as bundled wheels; drop unused `network` permission

## [1.1.0] — 2026-07-18

Static correctness fixes toward Blender 4.5 parity (see [ROADMAP.md](ROADMAP.md)).

- **Multi-material export:** primitive indices/vcounts filtered to faces for each material slot
- **Empty material slots:** guard unbound `slot.material` instead of crashing on `.name`
- **Selection-only export:** selected objects export even when parent is unselected; descendants of selected roots included
- **Atomic write:** DAE/ZAE written to a temp file then replaced; zip closed and temp removed on failure
- **Ortho cameras:** export `xmag`/`ymag = ortho_scale / 2`; import converts half-extent and applies unit scale
- **Parse warnings:** summarize pycollada broken refs / errors in operator reports
- **Units:** export asset `unitmeter` from Blender `unit_settings.scale_length`
- Document staged parity plan in `ROADMAP.md`

## [1.0.5] — 2026-07-18

- Default import **Transformations** mode is now **Parenting** (matches Blender 4.5 group trees)
- Parenting uses COLLADA/SketchUp `name` attributes for Empties (`SketchUp`, `group_0`, …) instead of only XML ids
- Local matrices applied after parenting to preserve hierarchy transforms

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

[1.2.0]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.2.0
[1.1.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.3
[1.1.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.2
[1.1.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.1
[1.1.0]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.1.0
[1.0.5]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.0.4]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.4
[1.0.3]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/tag/v1.0.3
[1.0.2]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/commits/master
[1.0.1]: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
