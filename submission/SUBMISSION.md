# Blender Extensions Platform — 2.0.4 **update** checklist

Live listing: https://extensions.blender.org/add-ons/collada-support/  
Package id: `collada_support` (already published). This is **Upload new version**, not a first-time Submit.

Full tracking checkboxes: [agent.md](../agent.md). Listing copy: [DESCRIPTION.md](DESCRIPTION.md). Version history: [CHANGELOG.md](../CHANGELOG.md).

| Field | Value |
| --- | --- |
| Package id | `collada_support` — **do not change** |
| Version | `2.0.4` |
| Display name | Collada Support |
| Tagline | `COLLADA (.dae) import and export for Blender 5` (47 chars, no end punctuation) |
| Maintainer (manifest) | `Collada Support for Blender 5.X` (no email in repo files) |
| Type | add-on |
| Tags | Import-Export, Pipeline |
| `blender_version_min` | `5.0.0` (listing: Blender 5.0 and newer) |
| License | GPL-3.0-or-later |
| Permissions | files — `Read/write COLLADA .dae/.zae/.kmz/.zip files and textures` |
| Zip | `F:\Projects\Addons\Blender-Collade-Support\dist\blender_collada_support.zip` |
| Zip layout | `blender_manifest.toml` and `__init__.py` at archive **root** (from `blender --command extension build`) |

---

## Website steps (human)

1. Log in to https://extensions.blender.org with the **Blender ID** that owns **Dank_Heehaw**.
2. Open the listing → **Manage / Edit → Upload new version**.  
   Direct: https://extensions.blender.org/add-ons/collada-support/manage/versions/new/  
   Do **not** use https://extensions.blender.org/submit/ — it rejects duplicate `id`.
3. Upload `dist/blender_collada_support.zip`.
4. Confirm the form reads version **2.0.4** and compatibility **Blender 5.0.0**.
5. Paste the fields below. Re-attach media if the form is empty.
6. Submit for review. Wait for moderation (no listing fee).
7. After approval: Blender → Get Extensions → Check for Updates.

---

## 1. Tagline (paste)

```
COLLADA (.dae) import and export for Blender 5
```

## 2. Description (Markdown)

Paste the full contents of `submission/DESCRIPTION.md`.

## 3. Support URL

```
https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/issues
```

Website / docs (`website` in the manifest):

```
https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X
```

## 4. Version release notes (Markdown) — paste from `RELEASE_NOTES_2.0.4.md`

```
# Collada Support 2.0.4

## Changes

- **Texture Copy:** relative Blender image paths (`//tex.png`) now copy correctly on Windows. Export uses `bpy.path.abspath` / `bpy.path.basename` instead of `os.path.basename`, which treated `//` as a UNC path and produced an empty filename.
- **Scripted export:** `bpy.ops.export_scene.collada(filepath=...)` without `directory=` no longer fails with an empty-path `WinError 3`. The output directory is derived from `filepath` when needed, and created if missing.

**Install:** remove the old add-on, quit Blender fully, then **Install from Disk** `blender_collada_support.zip` from Releases (not GitHub **Code → Download ZIP**). Confirm Preferences shows **2.0.4**.

**Full changelog** (2.0.0–2.0.4 and earlier): https://github.com/Dank-Heehaw/Collada-Support-for-Blender-5.X/blob/master/CHANGELOG.md
```

(Source of truth remains the **[2.0.4]** section of [CHANGELOG.md](../CHANGELOG.md).)

## 5. Icon (256×256 PNG)

`submission/icon.png` — PNG, **256×256**

## 6. Featured image (≥1920×1080, 16:9)

`submission/featured.png` — PNG, **1920×1080** (16:9)

## 7. Optional previews (16:9; at least one required for approval)

`submission/preview_import.png` — PNG, **1920×1080** (File → Import → COLLADA)

---

## File index

```
submission/
  SUBMISSION.md              ← this update checklist (paste values)
  DESCRIPTION.md             ← form: Description
  RELEASE_NOTES_2.0.4.md     ← form: Version release notes (also in CHANGELOG)
  icon.png                   ← 256×256
  featured.png               ← 1920×1080
  preview_import.png         ← 1920×1080 (preview)
```
