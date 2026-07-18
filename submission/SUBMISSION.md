# Blender Extensions Platform — Submission checklist

Copy each section into the **Submit add-on for approval** form. Upload files from the paths listed below.

| Field / asset | Value or path |
| --- | --- |
| Package id | `collada_support` |
| Version | `1.0.4` |
| Display name | Collada Support for Blender 5.X |
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

If the remote is not pushed yet, create and push with:

```powershell
cd F:\Projects\Addons\Blender-Collade-Support
gh auth login
gh repo create Collada-Support-for-Blender-5.X --public --description "Collada Support for Blender 5.X" --source=. --remote=origin --push
```

---

## 3. Initial version release notes (Markdown)

Paste the full contents of:

`F:\Projects\Addons\Blender-Collade-Support\submission\RELEASE_NOTES_1.0.4.md`

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
# Collada Support for Blender 5.X

Restores **COLLADA** import and export for Blender 5 after native OpenCOLLADA support was removed.

Use this add-on when you need to open or save `.dae` files (and related archives) in Blender 5.0 and newer.

## Features

- **Import** COLLADA scenes: triangle and polylist meshes, UVs, basic materials, textures, cameras, and lights
- **Export** meshes, Principled BSDF materials, parenting, optional textures, and ZAE packages
- **Archive formats**: `.zae` (official COLLADA zip), `.kmz` (Earth/Warehouse-style), and generic `.zip` containing a `.dae`
- **COLLADA versions** on export: 1.4.1 or 1.5.0
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
- No custom split-normals parity with Blender’s former `use_custom_normals` option
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

## Quick paste — Release notes (1.0.4)

```markdown
# Collada Support 1.0.4

## Changes

- Website / docs now point at this project’s GitHub repo: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
- Preferences no longer present **Install pycollada** as a first-time install step (wheels are bundled)
- Optional network fallback is labeled **Update / Reinstall pycollada**
- Clearer import/export errors when bundled pycollada fails to load (direct users to Preferences → Update / Reinstall)
```

---

## File index

```
F:\Projects\Addons\Blender-Collade-Support\submission\
  SUBMISSION.md              ← this checklist
  DESCRIPTION.md             ← form: Description
  RELEASE_NOTES_1.0.4.md     ← form: Initial version release notes
  RELEASE_NOTES_1.0.3.md     ← earlier notes (kept for reference)
  icon.png                   ← 256×256
  featured.png               ← 1920×1080
  preview_import.png         ← 1920×1080 (optional preview)
```
