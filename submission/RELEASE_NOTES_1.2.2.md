# Collada Support 1.2.2

## Changes

- Remove all runtime `sys.path` and `sys.modules` manipulation (including NumPy site-packages reordering)
- pycollada is imported normally; wheels remain listed in the extension manifest for Blender to load
