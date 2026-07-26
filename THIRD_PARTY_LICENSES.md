# Third-party licenses

**Collada Support for Blender 5.X** is licensed **GPL-3.0-or-later**. It also
incorporates or bundles the third-party code below, under the licenses shown.

## Cabinet-Vision-to-Blender (MIT)

`collada_support/import_cabinet_vision.py` — the Cabinet Vision import profile —
is derived from [Cabinet-Vision-to-Blender](https://github.com/ihartred-cpu/Cabinet-Vision-to-Blender)
by **ihartred-cpu**. The COLLADA parsing, physical-part joining, assembly
collection naming, bore absorption, hidden dado/notch repair and post-process
passes follow that project's design; the module header carries the same notice.

```
MIT License

Copyright (c) 2026 ihartred-cpu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## pycollada, python-dateutil, six (bundled wheels)

`collada_support/wheels/` ships unmodified PyPI wheels, listed in
`blender_manifest.toml`:

| Wheel | License |
| --- | --- |
| [pycollada](https://github.com/pycollada/pycollada) | BSD-3-Clause |
| [python-dateutil](https://github.com/dateutil/dateutil) | Apache-2.0 / BSD-3-Clause (dual) |
| [six](https://github.com/benjaminp/six) | MIT |

## Upstream lineage (GPL)

The general COLLADA import/export path descends from
[blender_pycollada_importexport](https://github.com/ldo/blender_pycollada_importexport)
(Tim Knip, Dusan Maliarik, Lawrence D'Oliveiro and contributors) and
[B5Collada](https://github.com/KimsFerdy/blender_pycollada_importexport)
(Kims Ferdy), both GPL-licensed.
