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
4. Enable **Collada Support**.
5. **pycollada is bundled** as wheels inside the zip — no pip install or network setup.

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

Import also covers triangle/polylist meshes, UVs, basic materials, textures (when resolvable), cameras, lights, and SketchUp-oriented quirks where possible. Polygons with holes (`<polygons>` / `<ph>` / `<h>`) are tessellated so drilled or routed cutouts survive.

### Import profiles (1.3.0+)

The import file browser has a **Profile** option:

| Profile | Use for |
| --- | --- |
| **General** (default) | SketchUp, Warehouse, DCC and game-pipeline exports — unchanged 1.2.x behavior |
| **Cabinet Vision** | Cabinet Vision `.dae` exports |

**Cabinet Vision** covers what CV actually emits and generic importers skip:

- **`<library_nodes>` + `<instance_node>`** — a part defined once and instanced across assemblies (without this, generic importers find no geometry in the visual scene and produce nothing)
- **`<polygons>` / `<ph>` / `<h>`** — panel faces with hardware bores and routed cutouts
- **Joined parts** — each panel's faces, edgebanding and boring/dado become one selectable object, seams welded
- **Assembly-aware collections** — parts grouped under their cabinet / countertop / molding run from CV's own label; redundant stacked wrapper levels reuse one collection; unabsorbed bores share a **Bores** collection per assembly
- **Hardware-aware bores** — bores exported as siblings are absorbed into the structural panel they belong to (never into hinge hardware), with bore UVs rotated onto the panel
- **Hidden feature geometry** — DADO/NOTCH geometry goes to a hidden **CV Hidden Features** collection; BORE geometry stays merged and visible
- **Legacy exports** — non-finite floats from old Microsoft C runtimes (`-1.#IND`, `1.#QNAN`, `-1.#J`, …) are coerced to `0.0` and reported rather than aborting the import

Cabinet Vision options: **Join Parts**, **Merge Vertices by Distance** (+ **Distance**), **Hide Dado/Notch Feature Geometry**, **Fix Hidden Dado/Notch Faces**, **Clean Topology**, **Mark Hard Edges as Seams**, **Flip UV (V Axis)**.

The Cabinet Vision profile reads COLLADA XML directly instead of going through pycollada, so it also works if the bundled wheels fail to load.

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
| **Parenting** (default) | Recreates COLLADA/SketchUp **groups** as parented Empties (closer to Blender 4.5) |
| **Multiply** | Flattens hierarchy: applies node transforms as world matrices (long mesh list) |
| **Apply** | Bakes transforms into mesh data |

If you still see a flat list of `ID*` meshes, make sure **Transformations → Parenting** is selected (default from **1.0.5**). Transform modes apply to the **General** profile; the Cabinet Vision profile always bakes CV's node transforms into each part's mesh.

## Bundled pycollada

The extension ships unmodified PyPI wheels (`pycollada`, `python-dateutil`, `six`) listed in `blender_manifest.toml`. Blender extracts them into the extension’s site-packages on install.

If import/export reports that pycollada failed to load:

1. Confirm you installed the **release** zip, not the source archive.
2. Confirm `wheels/` is inside the zip (`pycollada`, `python-dateutil`, `six`).
3. Remove the extension and reinstall **`blender_collada_support.zip`** from Releases.
4. Restart Blender if needed.

## Known limitations

See **[ROADMAP.md](ROADMAP.md)** for the staged OpenCOLLADA parity plan (1.1 → 2.0).

**Fixed in 1.1.0 (static correctness):** multi-material export indices, empty material slots, selection-only export with unselected parents, atomic DAE/ZAE write, ortho camera scale, scene unit export, and surfaced pycollada parse warnings.

**Still pending:**

- Native OpenCOLLADA-style **export** Main options (Include Children/Armatures/Shape Keys, Global Orientation axes, Texture Copy / UV map) — planned **2.0**
- No skin / armature / animation import or export yet (planned 1.4–1.7; see roadmap)
- No morph / shape-key I/O yet (planned 1.3)
- No full custom split-normals / vertex-color parity (planned 2.0 with export panels)
- Very large files remain CPU-bound during XML parse (pycollada)
- Nested ZAE sub-archives are not supported
- Not full feature parity with the old OpenCOLLADA importer/exporter
- Hierarchy under **Multiply** is intentionally flat; use **Parenting** (default) for SketchUp-style groups
- Parenting still creates Empties for named groups / non-identity transforms; only identity unnamed single-child wrappers are collapsed (1.2.1+)
- Large-file XML parse can still freeze the UI briefly before the import progress bar advances
- Cabinet Vision profile is import-only (there is no CV-flavored export), and does not import CV cameras or reconstruct parametric data — it produces panel meshes, materials and collections
- Cabinet Vision hierarchy is expressed as collections, not parented Empties; **Transformations** does not apply to that profile

## Troubleshooting

1. Open Blender’s **Window → Toggle System Console** (Windows) or start Blender from a terminal.
2. Reproduce the import/export and copy the console text.
3. Open an issue: https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues

Please include:

- Blender version (e.g. 5.0 / 5.2)
- Add-on version (currently **1.3.0**)
- Input/output format (`.dae` / `.zae` / `.kmz` / `.zip`)
- Import **Profile** (General / Cabinet Vision) and **Transformations** mode if relevant
- Full console output
- Expected vs actual result
- A **small reproducible sample** file if you can share one (or a link)

## Repository layout

```
collada_support/           # installable extension (manifest, I/O, wheels/)
dist/                      # rebuilt blender_collada_support.zip (local; not in git)
submission/                # Blender Extensions Platform listing materials
CONTRIBUTING.md            # developer workflow
CHANGELOG.md               # release history
ROADMAP.md                 # staged OpenCOLLADA parity plan
THIRD_PARTY_LICENSES.md    # licenses of incorporated third-party code
```

## Credits

- [blender_pycollada_importexport](https://github.com/ldo/blender_pycollada_importexport) — Tim Knip, Dusan Maliarik, Lawrence D’Oliveiro, and contributors  
- [B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport) — Kims Ferdy  
- [pycollada](https://github.com/pycollada/pycollada)  
- [Cabinet-Vision-to-Blender](https://github.com/ihartred-cpu/Cabinet-Vision-to-Blender) — **ihartred-cpu**; the Cabinet Vision import profile (`collada_support/import_cabinet_vision.py`) is derived from that project and reused under the **MIT** license (see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md))  
- Blender 4.5 native COLLADA importer patterns (behavioral reference)

## License

**GPL-3.0-or-later**, except where noted in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
