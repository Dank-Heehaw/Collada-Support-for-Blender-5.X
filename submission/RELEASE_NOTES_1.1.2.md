# Collada Support 1.1.2

## Changes

- Extension package id / folder renamed to **`collada_support`** (Extensions Platform resubmit)
- Extension **title** is **Collada Support** (no “Blender” in the display name)
- Dependencies ship **only** as bundled wheels — no pip install, no `sys.path` / site-packages hacks, no network permission
- Includes **1.1.0** static correctness fixes: multi-material export, empty material slots, selection-only export, atomic DAE/ZAE write, ortho camera scale, scene unit export, parse-warning reports
- Default import **Transformations** mode remains **Parenting** (SketchUp-style groups)

Install **`blender_collada_support.zip`** from Releases (not GitHub **Code → Download ZIP**).
