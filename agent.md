# TODO — Collada Support for Blender 5.X

**Current:** 2.0.3 on `master` (`release/2.0.3`)  
Living checklist: remaining work, later design notes, and local resource paths. Release history is only in [CHANGELOG.md](CHANGELOG.md).

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

## Shipped (do not re-open)

- [x] **2.0.3** Mesh-API export (no BMesh, no `ensure_lookup_table` calls; warning comment only)
- [x] **2.0.2** FBX-style panels; combined I/O zip; Google Earth extras already represented ([#5](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/5))
- [x] **2.0.1** operator / ID / skin / morph alignment with Blender 4.5 C++ exporter (`io_collada.cc`)
- [x] **2.0.0** export fidelity (loop normals, vertex colors, named nodes, modifiers, triangulate, texture copy, bind-pose skins)
- [x] [#3](https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues/3) skin **import** (`instance_controller` / bind-pose Armature + weights)
- [x] Morph **target geometry** export (2.0.1); 1.1.0 static correctness (see changelog)

Install: **Remove add-on → quit Blender → Install from Disk** `dist/blender_collada_support.zip`. Overwrite is not enough.

---

## Remaining gaps

Former ROADMAP items that are still open. Bind-pose skin I/O already shipped in 2.0.0–2.0.1; animation is the next real slice.

### Export

- [ ] Animation / action libraries (`include_animations` is accepted but not written). Needs a raw XML layer — `pycollada` `Animation.load` does not build samplers/channels (old 1.6–1.7)
- [ ] OpenSim extras (beyond current joint rest tweaks)
- [ ] Custom split-normals beyond smooth / flat
- [ ] Nested ZAE sub-archives
- [ ] Bone-parented object offsets

### Import / round-trip

- [ ] Morph / shape-key **import** (export of morph target geometries is in 2.0.1; old 1.3.0)
- [ ] Armature import chain flags are exposed but unused until skin import is fully verified
- [ ] Round-trip testing vs Blender 4.5 native COLLADA
- [ ] Broader interop suite vs native 4.5 files

### Later design notes

Planned modules (not in 2.0.3): `collada_rig.py`, `import_rig.py`, `collada_animation.py`, `export_rig.py`.

Constraints: inverse-bind matrices for bone rest; bake bind-shape; normalize weights; Armature modifier. First animation slice was sketched as import-only, one controller, PARENT mode, LINEAR/STEP matrix channels.

### Not in this line

- Cabinet Vision import profile (`cursor/cabinet-vision-collada-import-5f95`, draft PR #2) — keep off `master`
- Standalone Google Earth PR #6 — extras already in 2.0.2+; do not merge that branch if it would regress 2.0.3
