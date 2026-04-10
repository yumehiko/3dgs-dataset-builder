# Technical Background

This document explains the current export format, runtime behavior, and known technical limitations. For installation and basic usage, see [README.md](../README.md).

## Scope

The addon currently targets Brush / Nerfstudio-style dataset export from Blender collections.

It is intentionally not a general-purpose 3DGS exporter. The design favors predictable output for a specific downstream workflow over broad compatibility.

## Dataset Format

Each dataset contains:

* `images/*.png`
* `transforms_train.json`
* `transforms_test.json`
* `points3d.ply`
* `metadata.json`

`transforms_train.json` stores the exported camera frames, and `transforms_test.json` is currently emitted as the same camera metadata with an empty `frames` array.

## Brush Compatibility

The current implementation is Brush-oriented.

* `transform_matrix` is written from the Blender world matrix as-is
* camera transforms are not pre-converted to OpenCV format
* `Include Extension` must stay enabled for Brush compatibility
* `points3d.ply` is written into the dataset directory so Brush can find it through `ply_file_path` or same-directory lookup

## Material And Point Color Sampling

Initial point colors are intentionally limited to simple, predictable cases.

Works best with:

* UV-unwrapped meshes
* `Principled BSDF`
* `Base Color` driven by a flat color or an image texture

Weaker cases:

* complex node graphs
* glass, transmission, or reflection-heavy looks
* procedural-texture-driven materials
* missing UVs

When image texture sampling is not available, the exporter falls back to `Base Color`. If that is not usable, it falls back to a near-white color.

## Metadata

`metadata.json` stores lightweight diagnostic information for successful exports, including:

* addon version
* export timestamp
* dataset name
* target collection
* frame count
* point sample count
* output image resolution
* render engine
* warning list
* fallback material summary

Example shape:

```json
{
  "addon_version": "0.3.3",
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

## Runtime Architecture

Current export execution is split across Blender and a worker process:

* frame rendering is scheduled through Blender render jobs from the modal operator
* point sampling snapshots Blender mesh, material, and texture state into plain Python data first
* the heavy point sampling loop then runs in a separate Python worker process
* Blender UI progress during point sampling comes from polling worker-written progress files

This keeps the export workflow more responsive than a fully synchronous implementation, but large scenes can still pause during the one-time snapshot step before the worker starts.

## Current Limitations

* the project is still optimized for Brush, not multi-target export
* initial point color quality drops on complex materials
* rendering is still dispatched one frame at a time
* large scenes can still take noticeable time during point-sampling preparation
* `metadata.json` is written only for successful exports
* fallback reporting is aggregate-oriented, not deep node-level diagnosis
