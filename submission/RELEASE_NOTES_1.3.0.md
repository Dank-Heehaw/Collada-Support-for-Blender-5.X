# Collada Support 1.3.0

## Changes

- **New import Profile option:** **General** (default, unchanged) or **Cabinet Vision**
- **Cabinet Vision COLLADA import:** `<library_nodes>` + `<instance_node>` instancing, `<polygons>` / `<ph>` / `<h>` polygons with holes (hardware bores and routed cutouts), panels joined per part (faces + edgebanding + boring/dado) with seams welded
- **Assembly-aware collections** named from Cabinet Vision's own labels, with redundant wrapper levels collapsed; unabsorbed bores share a **Bores** collection per assembly
- **Hardware-aware bore absorption** into the correct structural panel (never into hinge hardware), with bore UVs rotated onto the panel
- **DADO/NOTCH geometry** routed to a hidden **CV Hidden Features** collection; BORE geometry stays merged and visible
- **Cabinet Vision options:** Join Parts, Merge Vertices by Distance, Hide Dado/Notch Feature Geometry, Fix Hidden Dado/Notch Faces, Clean Topology, Mark Hard Edges as Seams, Flip UV (V Axis)
- **Legacy exports:** non-finite floats from old Microsoft C runtimes (`-1.#IND`, `1.#QNAN`, `-1.#J`, …) are coerced to `0.0` and reported instead of aborting the import
- **General importer** also recovers `<polygons>` holes when `<ph>` data is present (no change for pre-triangulated exports such as SketchUp)
- Package id / folder: **`collada_support`**; dependencies remain wheels-only (no pip, no network permission)

## Attribution

The Cabinet Vision profile (`collada_support/import_cabinet_vision.py`) is derived from
[Cabinet-Vision-to-Blender](https://github.com/ihartred-cpu/Cabinet-Vision-to-Blender)
by **ihartred-cpu**, reused under the **MIT** license. See `THIRD_PARTY_LICENSES.md`.

## Planned for 2.0

Native OpenCOLLADA-style **export** options are not in 1.3.0. Planned for **2.0**:

- Selection Only, Include Children, Include Armatures, Include Shape Keys
- Global Orientation: Apply, Forward Axis, Up Axis
- Texture Options: Copy, UV Only Selected Map
- Geom / Arm / Anim / Extra export panels

Install **`blender_collada_support.zip`** (or `collada_support.zip`) from Releases (not GitHub **Code → Download ZIP**).
