"""Headless import checks for Collada Support (general + Cabinet Vision).

Run from the repository root:

    blender --background --factory-startup \\
        --python tests/run_headless_tests.py

Samples are generated automatically (see make_cv_samples.py) into
tests/_samples unless a directory is passed after `--`:

    blender --background --factory-startup \\
        --python tests/run_headless_tests.py -- /path/to/samples

Point it at a directory holding real Cabinet Vision exports to smoke-test
those instead; checks whose sample file is missing are skipped.

The general-profile checks need pycollada. If it is not importable, the
bundled wheels are unpacked into a temp directory and added to sys.path for
the test run only (the extension itself never manipulates sys.path).
"""

import os
import shutil
import sys
import tempfile
import time
import zipfile

import bpy

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

FAILURES = []
SKIPPED = []
_TEMP_DIRS = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s%s" % (status, label, (" -- %s" % detail) if detail else ""))
    if not condition:
        FAILURES.append(label)


def section(title):
    print("\n== %s ==" % title)


def sample(name):
    path = os.path.join(SAMPLE_DIR, name)
    if os.path.isfile(path):
        return path
    SKIPPED.append(name)
    print("[SKIP] missing sample %s" % path)
    return None


def unpack_wheels():
    "Make the bundled pycollada importable for the general-profile checks."
    try:
        import collada  # noqa: F401

        return True
    except ImportError:
        pass
    wheel_dir = os.path.join(REPO_ROOT, "collada_support", "wheels")
    if not os.path.isdir(wheel_dir):
        return False
    target = tempfile.mkdtemp(prefix="collada-support-test-wheels-")
    _TEMP_DIRS.append(target)
    for name in sorted(os.listdir(wheel_dir)):
        if name.endswith(".whl"):
            with zipfile.ZipFile(os.path.join(wheel_dir, name)) as zf:
                zf.extractall(target)
    sys.path.insert(0, target)
    try:
        import collada  # noqa: F401

        return True
    except ImportError as exc:
        print("could not load bundled pycollada: %s" % exc)
        return False


def reset_scene():
    bpy.ops.wm.read_homefile(use_empty=True)


def objects_named(prefix):
    return [obj for obj in bpy.data.objects if obj.name.split(".")[0] == prefix]


def first_named(prefix):
    found = objects_named(prefix)
    return found[0] if found else None


def total_area(obj):
    return sum(poly.area for poly in obj.data.polygons)


def collection_names():
    return {col.name.split(".")[0] for col in bpy.data.collections}


def mesh_polygon_counts():
    return sorted(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SAMPLE_DIR = argv[0] if argv else os.path.join(REPO_ROOT, "tests", "_samples")
if not argv:
    sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
    import make_cv_samples

    make_cv_samples.main(SAMPLE_DIR)

HAS_PYCOLLADA = unpack_wheels()

import collada_support  # noqa: E402

collada_support.register()

try:
    section("registration")
    check("import operator registered", hasattr(bpy.ops.import_scene, "collada"))
    check("export operator registered", hasattr(bpy.ops.export_scene, "collada"))

    import_rna = bpy.ops.import_scene.collada.get_rna_type()
    profiles = {item.identifier for item in import_rna.properties["profile"].enum_items}
    check(
        "profile enum has both paths",
        profiles == {"GENERAL", "CABINET_VISION"},
        str(sorted(profiles)),
    )
    check(
        "profile defaults to General",
        import_rna.properties["profile"].default == "GENERAL",
    )
    for prop in (
        "cv_join_parts",
        "cv_merge_by_distance",
        "cv_merge_distance",
        "cv_clean_topology",
        "cv_fix_hidden_dados",
        "cv_hide_feature_parts",
        "cv_flip_uv_v",
        "cv_mark_hard_edges",
    ):
        check("Cabinet Vision option %s exists" % prop, prop in import_rna.properties)

    manifest = open(
        os.path.join(REPO_ROOT, "collada_support", "blender_manifest.toml")
    ).read()
    check(
        "manifest and bl_info versions match",
        'version = "%d.%d.%d"' % collada_support.bl_info["version"] in manifest,
        str(collada_support.bl_info["version"]),
    )

    path = sample("cv_sample.dae")
    if path:
        section("Cabinet Vision profile: defaults")
        reset_scene()
        result = bpy.ops.import_scene.collada(filepath=path, profile="CABINET_VISION")
        check("import finished", result == {"FINISHED"}, str(result))
        cols = collection_names()
        check("root collection named from the file", "cv_sample" in cols, str(sorted(cols)))
        check("assembly collection from the CV label", "Base Cabinet Assembly" in cols)
        check("part-type collections", {"TO", "BT"} <= cols)

        hidden = next(
            (c for c in bpy.data.collections if c.name.startswith("CV Hidden Features")),
            None,
        )
        check("hidden features collection exists", hidden is not None)
        if hidden is not None:
            check(
                "hidden features collection is hidden",
                hidden.hide_viewport and hidden.hide_render,
            )
            check(
                "dado geometry routed to the hidden collection",
                [o.name.split(".")[0] for o in hidden.objects] == ["UBDADO"],
                str([o.name for o in hidden.objects]),
            )

        panel = first_named("TO")
        check("panel named from its CV part type", panel is not None)
        if panel is not None:
            # 8 triangles from tessellating the square-with-square-hole, plus
            # the bore quad merged into the same object.
            check(
                "panel merged the bore and tessellated the hole",
                len(panel.data.polygons) == 9,
                "polygons=%d" % len(panel.data.polygons),
            )
            check(
                "hole is cut out of the panel area",
                abs(total_area(panel) - 0.97) < 1e-5,
                "area=%.5f (expected 0.97)" % total_area(panel),
            )
            check("panel has a UV layer", len(panel.data.uv_layers) == 1)
            check(
                "panel material bound from the CV material",
                any(m and m.name.startswith("Maple") for m in panel.data.materials),
                str([m.name if m else None for m in panel.data.materials]),
            )
        bottom = first_named("BT")
        check(
            "polylist part imported",
            bottom is not None and len(bottom.data.polygons) == 1,
        )

        section("Cabinet Vision profile: joining and hiding disabled")
        reset_scene()
        result = bpy.ops.import_scene.collada(
            filepath=path,
            profile="CABINET_VISION",
            cv_join_parts=False,
            cv_hide_feature_parts=False,
            cv_merge_by_distance=False,
            cv_mark_hard_edges=False,
        )
        check("import finished", result == {"FINISHED"}, str(result))
        names = sorted(o.name.split(".")[0] for o in bpy.data.objects)
        check(
            "parts stay separate",
            names == ["BT", "LFVBORE", "TO", "UBDADO"],
            str(names),
        )

        section("Cabinet Vision profile: optional passes")
        reset_scene()
        result = bpy.ops.import_scene.collada(
            filepath=path,
            profile="CABINET_VISION",
            cv_clean_topology=True,
            cv_fix_hidden_dados=True,
            cv_flip_uv_v=True,
        )
        check("import with every pass finished", result == {"FINISHED"}, str(result))

        if HAS_PYCOLLADA:
            section("general profile: library nodes and polygons with holes")
            reset_scene()
            result = bpy.ops.import_scene.collada(filepath=path, profile="GENERAL")
            check("import finished", result == {"FINISHED"}, str(result))
            counts = mesh_polygon_counts()
            check(
                "library node instances resolved",
                len(counts) == 4,
                "polygon counts=%s" % counts,
            )
            check(
                "polygons with holes tessellated",
                counts.count(8) == 1,
                "polygon counts=%s" % counts,
            )
            hole_mesh = next(
                (
                    o
                    for o in bpy.data.objects
                    if o.type == "MESH" and len(o.data.polygons) == 8
                ),
                None,
            )
            if hole_mesh is not None:
                check(
                    "hole area matches",
                    abs(total_area(hole_mesh) - 0.96) < 1e-5,
                    "area=%.5f" % total_area(hole_mesh),
                )
                check("UVs kept", len(hole_mesh.data.uv_layers) == 1)

            for mode in ("MUL", "APPLY"):
                reset_scene()
                result = bpy.ops.import_scene.collada(
                    filepath=path, profile="GENERAL", transformation=mode
                )
                check(
                    "general import in %s mode finished" % mode,
                    result == {"FINISHED"},
                    str(result),
                )
                check(
                    "general import in %s mode created meshes" % mode,
                    any(o.type == "MESH" for o in bpy.data.objects),
                )
        else:
            print("[SKIP] general profile checks (pycollada unavailable)")

    path = sample("cv_legacy.dae")
    if path:
        section("Cabinet Vision profile: legacy non-finite floats")
        reset_scene()
        result = bpy.ops.import_scene.collada(filepath=path, profile="CABINET_VISION")
        check("'-1.#IND' export imports", result == {"FINISHED"}, str(result))
        check("panel still built", first_named("TO") is not None)

    path = sample("cv_sample.zae")
    if path:
        section("Cabinet Vision profile: .zae archive")
        reset_scene()
        result = bpy.ops.import_scene.collada(filepath=path, profile="CABINET_VISION")
        check("archive import finished", result == {"FINISHED"}, str(result))
        check("panel built from the archive", first_named("TO") is not None)

    path = sample("cv_absorb.dae")
    if path:
        section("Cabinet Vision profile: sibling bore absorption")
        reset_scene()
        result = bpy.ops.import_scene.collada(filepath=path, profile="CABINET_VISION")
        check("import finished", result == {"FINISHED"}, str(result))
        slabs = objects_named("S_DSLAB")
        check("both door slabs built", len(slabs) == 2, str([o.name for o in slabs]))
        check(
            "each slab absorbed its bore",
            all(len(o.data.polygons) == 2 for o in slabs),
            str([(o.name, len(o.data.polygons)) for o in slabs]),
        )
        check(
            "no standalone bore objects left",
            not [o for o in bpy.data.objects if "BORE" in o.name.upper()],
            str(sorted(o.name for o in bpy.data.objects)),
        )
        arm = first_named("_HGARM")
        check(
            "hinge hardware stays its own object",
            arm is not None and len(arm.data.polygons) == 1,
        )

    path = sample("cv_stress.dae")
    if path:
        section("Cabinet Vision profile: stress import")
        reset_scene()
        start = time.time()
        result = bpy.ops.import_scene.collada(filepath=path, profile="CABINET_VISION")
        elapsed = time.time() - start
        check("import finished", result == {"FINISHED"}, str(result))
        panels = objects_named("TO")
        check("one merged object per part", len(panels) == 1000, "objects=%d" % len(panels))
        check(
            "each part merged face, edgeband and bore",
            {len(o.data.polygons) for o in panels} == {10},
            str(sorted({len(o.data.polygons) for o in panels})),
        )
        hidden = next(
            (c for c in bpy.data.collections if c.name.startswith("CV Hidden Features")),
            None,
        )
        check(
            "dado geometry hidden for every part",
            hidden is not None and len(hidden.objects) == len(panels),
            "hidden=%d" % (len(hidden.objects) if hidden else 0),
        )
        print(
            "stress import took %.2fs for %d objects"
            % (elapsed, len(bpy.data.objects))
        )
        check("stress import under 60s", elapsed < 60.0, "%.2fs" % elapsed)

    if HAS_PYCOLLADA:
        path = sample("cv_sample.dae")
        if path:
            section("export still runs")
            reset_scene()
            bpy.ops.import_scene.collada(filepath=path, profile="GENERAL")
            out = os.path.join(tempfile.mkdtemp(prefix="collada-support-test-"), "out.dae")
            _TEMP_DIRS.append(os.path.dirname(out))
            result = bpy.ops.export_scene.collada(filepath=out)
            check("export finished", result == {"FINISHED"}, str(result))
            reset_scene()
            result = bpy.ops.import_scene.collada(filepath=out, profile="GENERAL")
            check("exported file re-imports", result == {"FINISHED"}, str(result))

        section("export round-trip with and without a UV layer")
        out_dir = tempfile.mkdtemp(prefix="collada-support-test-")
        _TEMP_DIRS.append(out_dir)
        for label, keep_uv in (("with UVs", True), ("without UVs", False)):
            reset_scene()
            bpy.ops.mesh.primitive_cube_add()
            mesh = bpy.context.active_object.data
            if not keep_uv:
                while mesh.uv_layers:
                    mesh.uv_layers.remove(mesh.uv_layers[0])
            bpy.ops.object.select_all(action="SELECT")
            out = os.path.join(out_dir, "cube_%s.dae" % keep_uv)
            result = bpy.ops.export_scene.collada(filepath=out)
            check("cube %s exports" % label, result == {"FINISHED"}, str(result))
            reset_scene()
            result = bpy.ops.import_scene.collada(filepath=out, profile="GENERAL")
            check("cube %s re-imports" % label, result == {"FINISHED"}, str(result))
            meshes = [o for o in bpy.data.objects if o.type == "MESH"]
            counts = [(len(o.data.vertices), len(o.data.polygons)) for o in meshes]
            check(
                "cube %s survives the round-trip" % label,
                counts == [(8, 6)],
                str(counts),
            )

    print("\n%d failure(s), %d skipped sample(s)" % (len(FAILURES), len(SKIPPED)))
    for name in FAILURES:
        print("  FAILED:", name)
finally:
    for temp in _TEMP_DIRS:
        shutil.rmtree(temp, ignore_errors=True)

sys.exit(1 if FAILURES else 0)
