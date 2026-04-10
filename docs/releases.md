# Releases

This document tracks completed milestones and released behavior.

## v0.3.1

Theme: responsive rendering workflow

Included:

* switched per-frame rendering from synchronous execution to Blender render jobs
* advanced the export pipeline through render completion and cancellation handlers
* temporarily disabled render interface locking during dataset generation and restored it afterward

Notes:

* renders are still executed one frame at a time
* cancellation during an active frame is best-effort and may complete the current frame before stopping

## v0.3.0

Theme: warning and metadata visibility

Included:

* structured warning records with `code` and `message`
* `metadata.json` for each successful dataset export
* fallback material summaries with unique material count and triangle usage count
* clearer completion reporting in Blender after export

Notes:

* `metadata.json` is written only for successful exports
* fallback reporting is still aggregate-oriented, not deep node-level analysis

## v0.2.0

Theme: first Brush-compatible export flow

Included:

* installable Blender addon
* Brush-compatible dataset export
* modal execution with progress display
* initial point positions and simple material color export
