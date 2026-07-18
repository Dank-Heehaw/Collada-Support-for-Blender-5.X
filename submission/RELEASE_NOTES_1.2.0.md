# Collada Support 1.2.0

## Changes

- Prefer Blender’s bundled NumPy over broken leftovers in `scripts/modules` (fixes pycollada load failures)
- Remove add-on preferences status panel and failed-load menu labels
- Report the underlying pycollada import error when an import or export is attempted
- Package id / folder: **`collada_support`**

## Planned for 2.0

Native OpenCOLLADA-style **export** options are not in 1.2.0. Planned for **2.0**:

- Selection Only, Include Children, Include Armatures, Include Shape Keys
- Global Orientation: Apply, Forward Axis, Up Axis
- Texture Options: Copy, UV Only Selected Map
- Geom / Arm / Anim / Extra export panels

Install **`blender_collada_support.zip`** (or `collada_support.zip`) from Releases (not GitHub **Code → Download ZIP**).
