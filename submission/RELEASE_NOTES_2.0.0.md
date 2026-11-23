# Collada Support 2.0.0

## Changes

Google Earth / COLLADA 1.4.1 export interoperability (#5):

- Do not reuse the diffuse texture as `<transparent>` (RGB maps were invisible in Google Earth)
- Triangulate exported meshes so files emit `<triangles>` instead of `<polylist>`
- Omit pycollada default specular/shininess on `<lambert>` so files pass the 1.4.1 schema
- Write an XML declaration (`<?xml version="1.0" encoding="utf-8"?>`)
