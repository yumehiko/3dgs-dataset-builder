# Releases

This document tracks completed milestones and released behavior.

## v0.3.4

Theme: crash triage and memory pressure reduction

Included:

* moved point sampling ahead of image rendering so suspected failures surface earlier in the export
* reduced point-sampling snapshot memory overhead by packing image pixels more tightly and avoiding extra serialization copies
* added `three_dgs_dataset_builder.log` with phase-level diagnostics, worker errors, and Python fatal-signal traces when available

Notes:

* very large scenes can still stress Blender-native render or texture caches outside the Python-side snapshot
* `three_dgs_dataset_builder.log` is written from export start and should be collected first when reporting a crash

## v0.3.3

Theme: documentation and sampling correctness

Included:

* expanded the main README with clearer installation, usage, and troubleshooting guidance
* added a Japanese README and a technical background document
* fixed point texture sampling so edge pixels can be reached correctly

Notes:

* runtime behavior is unchanged from the v0.3.2 worker-based export flow
* large assets can still pause during the one-time point-sampling snapshot step before the worker starts

## v0.3.2

Theme: responsive export workflow

Included:

* kept per-frame rendering on Blender render jobs instead of synchronous operator execution
* moved point sampling into a separate Python worker process with progress polling
* temporarily disabled render interface locking during dataset generation and restored it afterward

Notes:

* renders are still executed one frame at a time
* large assets can still pause during the one-time point-sampling snapshot step before the worker starts
* cancellation during an active frame is best-effort and may complete the current frame before stopping

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
