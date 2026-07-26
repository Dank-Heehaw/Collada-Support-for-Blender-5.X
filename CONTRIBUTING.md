# Contributing

Thanks for helping improve **Collada Support for Blender 5.X**.

## Prerequisites

- Blender **5.0+** (development target)
- Git
- Optional: GitHub CLI (`gh`) for PRs/releases
- Do **not** vendor edited copies of PyPI wheels — keep them unmodified from PyPI

## Repository layout

| Path | Purpose |
| --- | --- |
| `collada_support/` | Installable extension package |
| `collada_support/blender_manifest.toml` | Extension metadata + `wheels` list |
| `collada_support/__init__.py` | Operators and menus |
| `collada_support/import_collada.py` | Import (general / SketchUp profile) |
| `collada_support/import_cabinet_vision.py` | Import (Cabinet Vision profile) |
| `collada_support/export_collada.py` | Export |
| `collada_support/wheels/` | Unmodified PyPI `.whl` files |
| `tests/` | Headless Blender checks + synthetic sample generator |
| `dist/` | Local build of the install zip (gitignored) |
| `submission/` | Extensions Platform listing assets |

## Development install

### Option A — Install from a local zip

1. Build the zip (see below).
2. Blender: **Edit → Preferences → Add-ons → Install from Disk…**
3. Select `dist/blender_collada_support.zip` (do not extract).
4. Enable the add-on.

### Option B — Symlink / copy the package folder

Copy or junction `collada_support` into Blender’s extensions/add-ons path for your version, then enable it in Preferences.

After code changes: **disable → enable** the add-on, or restart Blender. Prefer restarting after wheel or manifest changes.

## Build the distributable zip

The archive **root must be the folder** `collada_support/` (so Blender sees `collada_support/blender_manifest.toml` inside the zip).

PowerShell example from the repo root:

```powershell
New-Item -ItemType Directory -Path .\dist -Force | Out-Null
if (Test-Path .\dist\blender_collada_support.zip) {
  Remove-Item .\dist\blender_collada_support.zip -Force
}
Compress-Archive -Path .\collada_support -DestinationPath .\dist\blender_collada_support.zip
```

Verify entries look like:

- `collada_support/__init__.py`
- `collada_support/blender_manifest.toml`
- `collada_support/wheels/...`

**Wrong:** zipping the whole repo, or zipping so `__init__.py` sits at the zip root without the package folder.

## Wheels and manifest

- Keep wheels **unmodified** PyPI artifacts.
- Every wheel under `wheels/` must be listed in `blender_manifest.toml` under `wheels = [...]` with forward-slash paths.
- License for Extensions must remain **`SPDX:GPL-3.0-or-later`**.
- Keep `version` in `blender_manifest.toml` and `bl_info["version"]` in sync.

## Headless tests

From the repo root:

```bash
blender --background --factory-startup --python tests/run_headless_tests.py
```

The run exits non-zero on failure, so it works as a pre-commit / CI gate. It
covers operator registration, manifest ↔ `bl_info` version agreement, both
import profiles, and the Cabinet Vision options (join, merge by distance,
hidden feature routing, hole tessellation, library-node instancing, legacy
non-finite floats, `.zae` archives, a 1000-part stress import).

Samples are synthesized into `tests/_samples` (gitignored) by
`tests/make_cv_samples.py` — no binary fixtures are committed. To smoke-test
real exports instead, pass a directory holding them; checks whose sample file
is absent are reported as skipped rather than failing:

```bash
blender --background --factory-startup \
    --python tests/run_headless_tests.py -- /path/to/cv_exports
```

The general-profile checks need pycollada. When it is not already importable,
the harness unpacks `collada_support/wheels/` into a temp directory for the
test run only — the extension itself never touches `sys.path`.

## Validation / testing checklist

- [ ] Manifest parses; version matches `bl_info`
- [ ] Install zip via **Install from Disk** (unextracted)
- [ ] Import loose `.dae`
- [ ] Import `.zae` / `.kmz` / `.zip` containing a `.dae`
- [ ] Export `.dae` and optionally `.zae`
- [ ] Import **Parenting** mode preserves useful hierarchy on a group-heavy file (e.g. SketchUp)
- [ ] Import **Multiply** still places geometry correctly
- [ ] Import **Profile → Cabinet Vision** on a CV export: parts joined, bores present, assembly collections named
- [ ] Malformed / empty geometry does not crash Blender (check System Console)
- [ ] Watch Window → Toggle System Console for errors during I/O

## Coding conventions

- Match existing style in `import_collada.py` / `export_collada.py` when editing those files.
- Prefer Blender API data paths over `bpy.ops` during bulk import (crash/perf).
- Validate mesh topology before `from_pydata`; use `mesh.validate()` where appropriate.
- Prefer batch `foreach_set` for large attribute writes.
- Do not add secrets, auth logs, or local `reference/` clones to git.

## Issues and pull requests

- File bugs at https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues
- Use the bug report template when possible (Blender version, add-on version, format, transform mode, console log, sample).
- PRs: describe **why**, how you tested, and any format limitations.

## Credits and license

Contributions are accepted under **GPL-3.0-or-later**. Preserve upstream attribution for pycollada and the blender-pycollada / B5Collada lineage in README / release notes when relevant.
