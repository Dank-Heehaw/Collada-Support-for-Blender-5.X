# Collada Support for Blender 5.X

Restores **COLLADA** import and export for Blender 5 after native OpenCOLLADA support was removed.

**Project:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X  
**Issues / support:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues  
**License:** [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)

Built from the pycollada lineage ([ldo](https://github.com/ldo/blender_pycollada_importexport) → [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport)), with import hardening guided by Blender **4.5’s** native COLLADA importer patterns.

## Download (what to install)

**Blender users must download this file only:**

**[`blender_collada_support.zip`](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases/latest/download/blender_collada_support.zip)**

| Do download | Do **not** download |
| --- | --- |
| Release asset **`blender_collada_support.zip`** | GitHub green **Code → Download ZIP** (source tree, not installable) |
| From [Releases](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/releases) | Cloning the repo unless you are developing |

## Install (Blender 5.x)

1. Download **`blender_collada_support.zip`** from the release link above.
2. In Blender 5: **Edit → Preferences → Add-ons → Install from Disk…**  
   (wording may be **Install…** depending on build).
3. Select the downloaded **`blender_collada_support.zip`**. **Do not extract it first.**
4. Enable **Blender Collada Support**.
5. **pycollada is bundled** as wheels inside the zip — no separate pip install for normal use.

Optional fallback in add-on Preferences: **Update / Reinstall pycollada** (network) if bundled wheels fail to load or need refreshing.

### Menus

- **File → Import → COLLADA (.dae, .zae, .kmz, .zip)**
- **File → Export → COLLADA (.dae, .zae)**

## Supported formats

### Import

| Format | Notes |
| --- | --- |
| **`.dae`** | Standard COLLADA document |
| **`.zae`** | Official COLLADA zip (`manifest.xml` or auto-picked `.dae`) |
| **`.kmz`** | Earth / Warehouse-style zip with embedded `.dae` + textures |
| **`.zip`** | Any zip that contains at least one `.dae` |

Import also covers triangle/polylist meshes, UVs, basic materials, textures (when resolvable), cameras, lights, and SketchUp-oriented quirks where possible.

### Export

| Format | Notes |
| --- | --- |
| **`.dae`** | COLLADA **1.4.1** or **1.5.0** |
| **`.zae`** | Zip package; can include textures |

Export covers meshes, Principled BSDF materials (Blender 5 socket names), object parenting, optional textures, and ZAE packaging.

### Import transform modes

In the import file browser, **Transformations**:

| Mode | Behavior |
| --- | --- |
| **Multiply** (default) | Applies node transforms as object world matrices (flatter Outliner) |
| **Parenting** | Recreates COLLADA node hierarchy with empties / parenting (closer to Blender 4.5 group trees) |
| **Apply** | Bakes transforms into mesh data |

For SketchUp / Warehouse scenes where hierarchy matters, try **Parenting**.

## Bundled pycollada

The extension ships unmodified PyPI wheels (`pycollada`, `python-dateutil`, `six`) listed in `blender_manifest.toml`. Blender extracts them into the extension’s site-packages on install.

If import/export reports that pycollada failed to load:

1. Confirm you installed the **release** zip, not the source archive.
2. Open **Preferences → Add-ons → Blender Collada Support**.
3. Use **Update / Reinstall pycollada**.
4. Restart Blender if needed.

## Known limitations

- No skin / armature / animation import or export yet
- No full custom split-normals parity with Blender’s former native option
- Very large files remain CPU-bound during XML parse (pycollada)
- Nested ZAE sub-archives are not supported
- Not full feature parity with the old OpenCOLLADA importer/exporter
- Hierarchy under **Multiply** will look flatter than Blender 4.5 LTS; use **Parenting** when needed

## Troubleshooting

1. Open Blender’s **Window → Toggle System Console** (Windows) or start Blender from a terminal.
2. Reproduce the import/export and copy the console text.
3. Open an issue: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues

Please include:

- Blender version (e.g. 5.0 / 5.2)
- Add-on version (see Preferences; currently **1.0.4**)
- Input/output format (`.dae` / `.zae` / `.kmz` / `.zip`)
- Import **Transformations** mode if relevant
- Full console output
- Expected vs actual result
- A **small reproducible sample** file if you can share one (or a link)

## Repository layout

```
blender_collada_support/   # installable extension (manifest, I/O, wheels/)
dist/                      # rebuilt blender_collada_support.zip (local; not in git)
submission/                # Blender Extensions Platform listing materials
CONTRIBUTING.md            # developer workflow
CHANGELOG.md               # release history
```

## Credits

- [blender_pycollada_importexport](https://github.com/ldo/blender_pycollada_importexport) — Tim Knip, Dusan Maliarik, Lawrence D’Oliveiro, and contributors  
- [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport) — Kims Ferdy  
- [pycollada](https://github.com/pycollada/pycollada)  
- Blender 4.5 native COLLADA importer patterns (behavioral reference)

## License

**GPL-3.0-or-later**
