# 3DGS Dataset Builder

3DGS Dataset Builder is a Blender 5.x addon for exporting training datasets that can be loaded directly into Brush.

The current release is `v0.3.0`. The primary target is **Brush / Nerfstudio-style dataset compatibility**, not a general-purpose 3DGS exporter.

## What It Exports

Each dataset contains:

* `images/*.png`
* `transforms_train.json`
* `transforms_test.json`
* `points3d.ply`
* `metadata.json`

## Workflow

The addon renders randomized camera views around a target collection and exports a surface-sampled point cloud for initialization.

Main UI fields:

* `Save Path`
* `Dataset Name`
* `Include Extension`
* `Target Collection`
* `Focus Object`
* `Total Frames`
* `Min Radius` / `Max Radius`
* `Close-up Ratio`
* `View Distribution`
* `Sample Count`

## Brush Compatibility

The current implementation is intentionally Brush-oriented.

* `transform_matrix` is written from the Blender world matrix as-is.
* The exporter does not pre-convert camera transforms to OpenCV format.
* `Include Extension` must stay enabled for Brush compatibility.
* `points3d.ply` is written into the dataset directory so Brush can find it through `ply_file_path` or same-directory lookup.

## Material Support

Initial point colors are intentionally limited to simple, predictable cases.

Works best with:

* UV-unwrapped meshes
* `Principled BSDF`
* `Base Color` driven by a flat color or an image texture

Weaker cases:

* complex node graphs
* glass / transmission / reflection-heavy looks
* procedural-texture-driven materials
* missing UVs

When image texture sampling is not available, the exporter falls back to `Base Color`. If that is not usable, it falls back to a near-white color.

## Metadata

`metadata.json` stores lightweight diagnostic information for each successful export, including:

* addon version
* export timestamp
* frame count
* point sample count
* target collection name
* output image resolution
* render engine
* warning list
* fallback material summary

Example shape:

```json
{
  "addon_version": "0.3.0",
  "export_timestamp": "2026-04-10T12:34:56Z",
  "dataset_name": "example",
  "target_collection": "Collection",
  "frame_count": 100,
  "point_sample_count": 50000,
  "image_resolution": {
    "width": 1024,
    "height": 1024
  },
  "render_engine": "CYCLES",
  "warnings": [
    {
      "code": "material_base_color_fallback",
      "message": "Material 'Mat_A' does not use a supported image texture chain; using base color fallback."
    }
  ],
  "materials": {
    "fallback_material_count": 1,
    "fallback_triangle_count": 120,
    "fallback_materials": [
      {
        "name": "Mat_A",
        "triangle_count": 120
      }
    ]
  }
}
```

## Limitations

* This project is still optimized for Brush, not for multi-target 3DGS export.
* Initial point color quality drops on complex materials.
* Rendering still happens synchronously per frame even though execution is modal.
* `metadata.json` is written only for successful exports.
* Fallback reporting currently stops at warning and aggregate counts, not deep node-level diagnosis.

## Additional Docs

* Future plans: [docs/roadmap.md](/Users/okamura-yumehiko/repository/3dgs-dataset-builder/docs/roadmap.md)
* Release history: [docs/releases.md](/Users/okamura-yumehiko/repository/3dgs-dataset-builder/docs/releases.md)
* Maintainer notes: [docs/development.md](/Users/okamura-yumehiko/repository/3dgs-dataset-builder/docs/development.md)
