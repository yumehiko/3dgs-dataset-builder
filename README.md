# 3DGS Dataset Builder

Language: English | [日本語](README.ja.md)

3DGS Dataset Builder is a Blender 5.x addon that exports Brush-compatible training datasets from a Blender collection.

Current release: `v0.3.3`

## Overview

This addon is built for a narrow workflow:

* pick a collection in Blender
* render randomized camera views around it
* export matching camera transforms
* export a surface-sampled `points3d.ply` for initialization

If you want a general-purpose 3DGS exporter, this project is not aiming for that. It is currently optimized for Brush / Nerfstudio-style dataset layout.

## Installation

1. Download `three_dgs_dataset_builder.zip` from the project's GitHub Releases.
2. In Blender, open `Edit > Preferences > Add-ons`.
3. Click `Install from Disk`.
4. Select the downloaded zip file.
5. Enable `3DGS Dataset Builder`.

## Where To Find The UI

After enabling the addon:

1. Open the 3D Viewport.
2. Open the right sidebar with `N` if it is hidden.
3. Open the `3DGS Dataset` tab.

The panel path is `View3D > Sidebar > 3DGS Dataset`.

## Quick Start

1. Put the mesh objects you want to export into one collection.
2. Set Blender render resolution and render engine the way you want the output images to be generated.
3. In the addon panel, set `Save Path` and `Dataset Name`.
4. Select `Target Collection`.
5. Optionally select `Focus Object` if the cameras should look at a specific object instead of world origin.
6. Adjust frame count, camera radius, and point sample count.
7. Click `Generate Dataset`.
8. Wait for rendering, point sampling, and final file writing to finish.

## UI Reference

### Dataset

* `Save Path`: base directory where the dataset folder will be created
* `Dataset Name`: output folder name created under `Save Path`
* `Include Extension`: should stay enabled for Brush compatibility

### Camera Sampling

* `Target Collection`: collection whose mesh objects are rendered and sampled
* `Focus Object`: optional object the temporary camera points at; world origin is used when empty
* `Total Frames`: number of rendered training views
* `View Distribution`: `Full Sphere` or `Upper Hemisphere`
* `Min Radius` / `Max Radius`: minimum and maximum camera distance from the focus point
* `Close-up Ratio`: fraction of views biased toward the minimum radius

### Point Cloud

* `Sample Count`: number of surface samples written to `points3d.ply`

### Status And Actions

* `Status`: shows the current phase and progress
* `Generate Dataset`: starts export
* `Cancel Generation`: requests cancellation after the current step finishes

## Output Structure

Each export creates a dataset folder at `Save Path / Dataset Name`:

```text
my_dataset/
├── images/
│   ├── 00000.png
│   ├── 00001.png
│   └── ...
├── metadata.json
├── points3d.ply
├── transforms_test.json
└── transforms_train.json
```

Notes:

* `transforms_train.json` contains the rendered frames.
* `transforms_test.json` is written with an empty `frames` array.
* `metadata.json` is written only on successful export.

## Recommended Scene Setup

The addon works best when:

* the target collection actually contains mesh objects
* meshes are UV-unwrapped
* materials use `Principled BSDF`
* `Base Color` comes from a flat color or a simple image texture

Results are less predictable on complex node graphs, reflective or transmissive materials, procedural textures, or missing UVs.

## Troubleshooting

Common validation failures:

* `Save Path is required.`
* `Dataset Name is required.`
* `Target Collection is required.`
* `Target collection does not contain any mesh objects.`
* `Brush compatibility requires Include Extension to be enabled.`
* `Min Radius must be smaller than Max Radius.`

If export feels stalled on a large asset, the slow part is often the initial render pass or the one-time point-sampling preparation step before the worker process starts reporting progress.

## More Documentation

* Technical background and format notes: [docs/technical-background.md](docs/technical-background.md)
* Release history: [docs/releases.md](docs/releases.md)
* Future plans: [docs/roadmap.md](docs/roadmap.md)
* Maintainer notes: [docs/development.md](docs/development.md)

Packaging the addon with `make package` is maintainer-facing and documented in [docs/development.md](docs/development.md).
