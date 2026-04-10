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
