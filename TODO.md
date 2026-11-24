# TODO — Collada Support for Blender 5.X

**Target:** 2.0.3 (current installable release on `master`)  
**Branch:** `release/2.0.3` (from `release/2.0.2`)  
**Last shipped:** 2.0.3 (`38b4b16` and docs on this line)  
Living checklist. Longer history and parity plan live in [ROADMAP.md](ROADMAP.md).

---

## Resources

**GitHub:** https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X

### Addon / working tree

- `F:\Projects\Addons\Blender-Collade-Support`
- Installable zip: `F:\Projects\Addons\Blender-Collade-Support\dist\blender_collada_support.zip`

### Blender 4.5 source (original COLLADA C++ I/O)

Scan the whole `io\collada` folder — `MeshExporter` and related files live there, not only the files below. There is **no** `blender.exe` in this source tree.

- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada.cpp`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada.h`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada_internal.cpp`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada_internal.h`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada_utils.cpp`
- `F:\Projects\Addons\blender-4.5.16\source\blender\io\collada\collada_utils.h`
- Operator/UI: `F:\Projects\Addons\blender-4.5.16\source\blender\editors\io\io_collada.cc`
- `F:\Projects\Addons\blender-4.5.16\source\blender\editors\io\io_collada.hh`
- Export presets: `F:\Projects\Addons\blender-4.5.16\scripts\presets\operator\wm.collada_export`
- Python tests: `F:\Projects\Addons\blender-4.5.16\tests\python\collada`

### Blender executables

- **Blender 4.5** (native COLLADA compare / source tree): `F:\Projects\Addons\blender-4.5.16` — source tree present; no `blender.exe` at repo root or under `bin/` (COLLADA sources remain under `source\blender\io\collada`)
- **Steam Blender 5** (user test target): `C:\Games\steamapps\common\Blender\blender.exe` — **missing** (folder not on disk)

---

## In progress

_(none — 2.0.3 is the shipped Mesh-API export rewrite)_

---

## Done

- [x] **2.0.3 mesh export rewrite** — drop BMesh, use Mesh API only
  - Shipped Python has **no** `ensure_lookup_table` calls and **no** `import bmesh` in `export_collada.py`
  - Only remaining addon hit is the required warning comment on `encode_mesh`
  - Install path: **Remove add-on → quit Blender → Install from Disk** (overwrite is not enough)
- [x] Confirm 2.0.3 zip has **zero** `ensure_lookup_table` calls (required comment only); user must Remove → quit → Install from Disk
- [x] Version bumps through **2.0.3** (`blender_manifest.toml`, `bl_info`, authoring_tool string)
- [x] Issue [#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) skin import (`instance_controller` / bind-pose meshes) — merged into `release/2.0.2`
- [x] Export fidelity vs original Blender COLLADA (per-loop normals, vertex colors, named nodes, modifiers, triangulate, texture copy, bind-pose skins)
- [x] 2.0.1 operator / ID / skin / morph alignment with Blender 4.5 C++ exporter
- [x] Combined working branch `release/2.0.2` ([PR #10](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/pull/10))
  - Issue [#5](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/5) Google Earth extras already represented
  - Cabinet Vision PR skipped
- [x] Export UI: FBX-style collapsible sections instead of cramped Main / Geom / Arm / Anim / Extra tabs
- [x] [CHANGELOG.md](CHANGELOG.md) and `submission/` notes in sync with 2.0.0 / 2.0.1 / 2.0.2 / 2.0.3

---

## Remaining gaps

### Export

- [ ] Animation / action libraries (`include_animations` is accepted but not fully written)
- [ ] OpenSim extras (beyond current joint rest tweaks)
- [ ] Custom split-normals beyond smooth / flat
- [ ] Nested ZAE sub-archives
- [ ] Bone-parented object offsets

### Import / round-trip

- [ ] Armature import chain flags are exposed but unused until skin import is fully verified
- [ ] Round-trip testing vs Blender 4.5 native COLLADA

### Not in this line

- Cabinet Vision import profile (`cursor/cabinet-vision-collada-import-5f95`, draft PR #2) — keep off `master` until it is a real release
- Standalone Google Earth PR #6 — extras already represented in 2.0.2+; do not merge that branch if it would regress 2.0.3
