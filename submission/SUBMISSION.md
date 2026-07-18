# Blender Extensions Platform — Submission checklist

Copy each section into the **Submit add-on for approval** form. Upload files from the paths listed below.

| Field / asset | Value or path |
| --- | --- |
| Package id | `collada_support` |
| Version | `1.1.3` |
| Display name | Collada Support |
| License | GPL-3.0-or-later |

---

## 1. Description (Markdown)

Paste the full contents of:

`F:\Projects\Addons\Blender-Collade-Support\submission\DESCRIPTION.md`

---

## 2. Support URL

Use this issues tracker on the Extensions form:

```
https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues
```

Repo home (also set as `website` / `doc_url` in the package):

```
https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
```

---

## 3. Version release notes (Markdown)

Paste the full contents of:

`F:\Projects\Addons\Blender-Collade-Support\submission\RELEASE_NOTES_1.1.3.md`

---

## 4. Icon (256×256 PNG)

Upload:

`F:\Projects\Addons\Blender-Collade-Support\submission\icon.png`

- Format: PNG  
- Size: **256×256**

---

## 5. Featured image (≥1920×1080, 16:9)

Upload:

`F:\Projects\Addons\Blender-Collade-Support\submission\featured.png`

- Format: PNG  
- Size: **1920×1080** (16:9)

---

## 6. Optional previews

Upload (optional but recommended):

`F:\Projects\Addons\Blender-Collade-Support\submission\preview_import.png`

- Format: PNG  
- Size: **1920×1080**  
- Shows a File → Import → COLLADA concept mockup

You can add a second preview later (e.g. Export menu / sample scene) if the form allows multiple images.

---

## Quick paste — Description

```markdown
# Collada Support

Restores **COLLADA** import and export for Blender 5 after native OpenCOLLADA support was removed.

**Homepage:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X  
**Support / issues:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues

Use this add-on when you need to open or save `.dae` files (and related archives) in Blender 5.0 and newer.

## Features

- **Import** COLLADA scenes: triangle and polylist meshes, UVs, basic materials, textures, cameras, and lights
- **Export** meshes, Principled BSDF materials, parenting, optional textures, and ZAE packages
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

- No skin / armature / animation import or export yet (not full OpenCOLLADA parity)
- No morph / shape-key I/O yet
- No custom split-normals / vertex-color parity with the old native importer
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
```

---

## Quick paste — Release notes (1.1.3)

```markdown
# Collada Support 1.1.3

## Changes

- Removed the add-on preferences status panel
- Removed failed-load text from the File → Import and Export menu labels
- Import/export attempts now report the underlying pycollada import error
- Package id and folder remain **`collada_support`**

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
```

---

## File index

```
F:\Projects\Addons\Blender-Collade-Support\submission\
  SUBMISSION.md              ← this checklist
  DESCRIPTION.md             ← form: Description
  RELEASE_NOTES_1.1.3.md     ← form: Version release notes
  RELEASE_NOTES_1.1.2.md     ← earlier notes (kept for reference)
  RELEASE_NOTES_1.0.4.md     ← earlier notes (kept for reference)
  RELEASE_NOTES_1.0.3.md     ← earlier notes (kept for reference)
  icon.png                   ← 256×256
  featured.png               ← 1920×1080
  preview_import.png         ← 1920×1080 (optional preview)
```
