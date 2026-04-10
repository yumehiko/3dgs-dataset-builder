# Roadmap

This document is for future work only. Released work is tracked in [releases.md](/Users/okamura-yumehiko/repository/3dgs-dataset-builder/docs/releases.md).

## v0.4

Theme: validation on real assets and practical tuning

Planned work:

* validate the exporter on multiple real production assets
* tune radius ranges, close-up ratio, frame count, and point count
* revisit default values based on actual Brush training behavior
* improve camera distribution and rendering defaults for practical use

Goal:

* move from test-scene validation toward stable results on real assets

## v0.5

Theme: better support for complex materials

Planned work:

* improve color extraction for more complex node graphs
* define clearer fallback rules for glass and view-dependent materials
* investigate support for procedural textures and multi-path node setups
* document what is exact and what is approximate in point color export

Goal:

* improve the visual quality of the initial point cloud
* make results more usable on assets with more complex materials

## Out Of Scope For Now

* multi-target export as a general-purpose 3DGS exporter
* reintroducing COLMAP compatibility or exporter-side OpenCV conversion
* depth map export
* lighting variation
