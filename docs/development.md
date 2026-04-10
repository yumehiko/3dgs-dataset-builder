# Development Notes

This document is for maintainers, not addon users.

## Local Commands

Project-level helper commands:

* `make test`
* `make package`

`make package` recreates `dist/three_dgs_dataset_builder.zip`, which is the Blender addon package to upload to a GitHub Release.

## Release Notes

Release assets:

* upload `three_dgs_dataset_builder.zip`
* upload `dist/three_dgs_dataset_builder.zip`
* do not rely on GitHub's auto-generated source archives as the Blender install package

Typical release flow:

```bash
make package
git push origin main
git push origin <tag>
gh release create <tag> dist/three_dgs_dataset_builder.zip --title <tag> --notes "<tag> release"
```

## Documentation Split

* `README.md` is user-facing
* `docs/roadmap.md` is future-facing only
* `docs/releases.md` tracks completed milestones

## Runtime Notes

Current export execution is split across Blender and a worker process:

* frame rendering is scheduled through Blender render jobs from the modal operator
* point sampling snapshots Blender mesh / material / texture state into plain Python data first
* the heavy point sampling loop then runs in a separate Python worker process
* Blender UI progress during point sampling comes from polling worker-written progress files

Implications for maintainers:

* do not pass `bpy` objects directly into the worker process
* keep Blender-only access inside the snapshot preparation path in `builder.py`
* if point sampling behavior changes, keep the synchronous fallback and worker path logically aligned
