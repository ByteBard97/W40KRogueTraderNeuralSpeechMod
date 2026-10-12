#!/usr/bin/env python3
"""Export Idira's character meshes (bind pose, with UVs) from the equipment bundle as OBJ files.

  export_idira_meshes.py BUNDLE OUTDIR
Run with a Python that has UnityPy. BUNDLE is Bundles/equipment.orig; OUTDIR e.g. data/atlas_upscale/blender/meshes.
"""
import sys
from pathlib import Path

import UnityPy


def main():
    bundle, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    seen = set()
    for obj in UnityPy.load(bundle).objects:
        if obj.type.name != "Mesh":
            continue
        mesh = obj.read()
        if "idira" not in mesh.m_Name.lower() or mesh.m_Name in seen:
            continue
        seen.add(mesh.m_Name)
        (out / f"{mesh.m_Name}.obj").write_text(mesh.export())
        print(mesh.m_Name, "->", out / f"{mesh.m_Name}.obj")


if __name__ == "__main__":
    main()
