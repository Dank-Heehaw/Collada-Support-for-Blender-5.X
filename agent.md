# agent.md — Collada Support for Blender 5.X

Living agent brief for this repo. Read this first, then [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [submission/SUBMISSION.md](submission/SUBMISSION.md). Do not invent maintainer emails; use values already in the repo.

## Current

| Item | Value |
| --- | --- |
| Version | **2.0.4** |
| Branch | `master` |
| Package id | `collada_support` (do **not** change; live listing uses this) |
| Zip | `F:\Projects\Addons\Blender-Collade-Support\dist\blender_collada_support.zip` |
| Live listing | [extensions.blender.org/add-ons/collada-support](https://extensions.blender.org/add-ons/collada-support/) — upload **2.0.4** (path fixes after 2.0.3) |
| `blender_version_min` | `5.0.0` |
| License | SPDX `GPL-3.0-or-later` ([LICENSE](LICENSE)) |

## Resources

- **GitHub:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
- **Issues:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues
- **Extensions docs:** https://docs.blender.org/manual/en/latest/advanced/extensions/
- **Add-on guidelines:** https://developer.blender.org/docs/handbook/extensions/addon_guidelines/
- **Workspace:** `F:\Projects\Addons\Blender-Collade-Support`
- **Steam Blender 5 (working exe):** `C:\Games\Steam\steamapps\common\Blender\blender.exe` — used for `blender --command extension build` / `validate`
- **Guessed Steam path (missing):** `C:\Games\steamapps\common\Blender\blender.exe` — do not use
- **Blender 4.5.16:** `F:\Projects\Addons\blender-4.5.16` — **source tree only**, no `blender.exe`. Native COLLADA C++ lives under `source\blender\io\collada` (scan the whole folder). Operators: `source\blender\editors\io\io_collada.cc`. This tree is **reference only**; do not edit it.

## Status

### Shipped (do not re-open)

- [x] **2.0.4** Windows relative texture-copy (`//`) + scripted `directory=` fallback
- [x] **2.0.3** Mesh-API export (no BMesh, no `ensure_lookup_table` calls; warning comment only)
- [x] **2.0.2** FBX-style File Browser panels; combined I/O zip
- [x] **2.0.1** operator / ID / skin / morph alignment with Blender 4.5 C++ exporter
- [x] **2.0.0** export fidelity (loop normals, vertex colors, named nodes, modifiers, triangulate, texture copy, bind-pose skins)
- [x] [#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) skin **import** (`instance_controller` / bind-pose Armature + weights)
- [x] Morph **target geometry** export (2.0.1)
- [x] 1.1.0 static correctness (see changelog)
- [x] Repo LICENSE + `collada_support/LICENSE` (GPL-3.0)
- [x] Manifest fields for Extensions (`id`, `version`, `tagline`, `copyright`, `wheels`, `[permissions]`, `[build]`)
- [x] Rebuild zip with `blender --command extension build` (manifest at zip root)

### Remaining feature gaps

- [ ] Animation / action libraries (`include_animations` is accepted but not written). Needs a raw XML layer — `pycollada` `Animation.load` does not build samplers/channels
- [ ] OpenSim extras (beyond current joint rest tweaks)
- [ ] Custom split-normals beyond smooth / flat
- [ ] Nested ZAE sub-archives
- [ ] Bone-parented object offsets
- [ ] Morph / shape-key **import** (export of morph target geometries is in 2.0.1)
- [ ] Armature import chain flags are exposed but unused until skin import is fully verified
- [ ] Round-trip testing vs Blender 4.5 native COLLADA
- [ ] Broader interop suite vs native 4.5 files

Planned modules (not in 2.0.4): `collada_rig.py`, `import_rig.py`, `collada_animation.py`, `export_rig.py`.

### Not in this line

- Cabinet Vision import profile (`cursor/cabinet-vision-collada-import-5f95`, draft PR #2) — keep off `master`
- Standalone Google Earth PR #6 — extras already in 2.0.2+; do not merge that branch if it would regress 2.0.4

## Extensions update checklist

Official: [Creating Extensions](https://docs.blender.org/manual/en/latest/advanced/extensions/), [Getting started](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html), [Add-ons](https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html), [Add-on guidelines](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/). Listing: https://extensions.blender.org/add-ons/collada-support/ (id `collada_support` → upload **2.0.4**). Paste-ready copy is in [submission/SUBMISSION.md](submission/SUBMISSION.md).

### Package / repo (done here)

- [x] `blender_manifest.toml` required fields: `schema_version`, `id`, `version`, `name`, `tagline` (≤64 chars, no end punctuation), `maintainer`, `type`, `blender_version_min`, `license`
- [x] Optional filled: `website`, `tags` (`Import-Export`, `Pipeline`), `copyright` (`Year Name`), `wheels` (unmodified PyPI, forward slashes), `[permissions].files` (≤64 chars, no period), `[build]` excludes
- [x] No empty optional fields; no `platforms` (wheels are `py3-none-any`); no `network` permission
- [x] `id` unchanged (`collada_support`); `version` 2.0.4; `blender_version_min` `5.0.0`
- [x] `bl_info["version"]` matches manifest `(2, 0, 4)`
- [x] GPL-3.0-or-later LICENSE in repo and package
- [x] Relative imports; no `sys.path` / `sys.modules` mutation; wheels listed in manifest
- [x] File I/O is import/export + `tempfile` (not the add-on directory); `files` permission declared
- [x] No `__pycache__` / `.pyc` in zip
- [x] Zip built with `blender --command extension build` — `blender_manifest.toml` and `__init__.py` at **zip root**
- [x] Icon `submission/icon.png` 256×256 PNG; featured `submission/featured.png` ≥1920×1080 16:9; preview `submission/preview_import.png` 1920×1080
- [x] Listing description in `submission/DESCRIPTION.md`; version notes = CHANGELOG **[2.0.4]**

### Still human-only on extensions.blender.org

- [ ] Log in with **Blender ID** (account `Dank_Heehaw` already owns the listing)
- [ ] Open [Collada Support](https://extensions.blender.org/add-ons/collada-support/) → **Manage / Edit → Upload new version** (not the public Submit form — that rejects a duplicate `id`)
- [ ] Direct URL if logged in: https://extensions.blender.org/add-ons/collada-support/manage/versions/new/
- [ ] Upload `dist/blender_collada_support.zip`
- [ ] Confirm website form shows version **2.0.4** and `blender_version_min` **5.0.0**
- [ ] Paste **tagline**, **description**, **support URL**, **2.0.4 changelog** from [submission/SUBMISSION.md](submission/SUBMISSION.md)
- [ ] Keep or re-upload icon / featured / preview if the form asks (sizes already match)
- [ ] Submit the version for review and watch the approval queue / email
- [ ] After approval: in Blender, Get Extensions → Check for Updates; confirm Preferences shows **2.0.4**
- [ ] Optional GitHub Release asset for the same zip (not required for the platform)

No listing fee. Do not pay anything to publish. Do not force-push. Do not change `id`.

## Install / test 2.0.4

1. Build (from repo root, Steam Blender):

```powershell
& "C:\Games\Steam\steamapps\common\Blender\blender.exe" --command extension build --source-dir collada_support --output-filepath dist/blender_collada_support.zip
& "C:\Games\Steam\steamapps\common\Blender\blender.exe" --command extension validate dist/blender_collada_support.zip
```

2. **Remove** old Collada Support → **quit Blender fully** → **Install from Disk** `dist/blender_collada_support.zip`. Overwrite is not enough.
3. Confirm Preferences shows **2.0.4**.
4. Smoke: cube + `//tex.png` with Texture Copy; `bpy.ops.export_scene.collada(filepath=r"C:\temp\out.dae")` without `directory=`.

## Do not touch

- Adobe temp files and `.ai` binaries (unless a guideline requires a PNG size we cannot meet with existing `submission/*.png`)
- `F:\Projects\Addons\blender-4.5.16` — reference source only, no exe
- `id = "collada_support"` and live listing URLs
- Unmodified PyPI wheels under `collada_support/wheels/`
- `dist/` is gitignored local output
- Git config, force-push, `--no-verify`
- Cabinet Vision / PR #6 branches on `master`
