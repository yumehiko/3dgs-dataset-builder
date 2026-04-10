from pathlib import Path

import bpy

from .builder import (
    BuildSession,
    cancel_point_sampling_worker,
    DatasetBuildError,
    begin_dataset_build,
    cleanup_dataset_build,
    finalize_rendered_frame,
    has_remaining_frames,
    poll_point_sampling_worker,
    prepare_point_sampling,
    prepare_next_frame_render,
    start_point_sampling_worker,
    write_outputs,
)
from .core.models import DatasetSettingsSnapshot
from .core.validation import validate_settings


class THREE_DGS_OT_generate_dataset(bpy.types.Operator):
    bl_idname = "three_dgs.generate_dataset"
    bl_label = "Generate Dataset"
    bl_description = "Render images, transforms JSON, and point cloud for 3DGS training"
    bl_options = {"REGISTER"}

    _timer = None
    _session: BuildSession | None = None
    _phase = "IDLE"
    _pending_frame_index: int | None = None
    _render_inflight = False
    _render_finished = False
    _render_cancelled = False

    def invoke(self, context, event):
        settings = context.scene.three_dgs_settings
        if settings.is_running:
            self.report({"WARNING"}, "Dataset generation is already running.")
            return {"CANCELLED"}

        resolved_save_path = bpy.path.abspath(settings.save_path).strip()
        snapshot = DatasetSettingsSnapshot(
            save_path=resolved_save_path,
            dataset_name=settings.dataset_name.strip(),
            include_extension=bool(settings.include_extension),
            total_frames=int(settings.total_frames),
            min_radius=float(settings.min_radius),
            max_radius=float(settings.max_radius),
            close_up_ratio=float(settings.close_up_ratio),
            view_distribution=str(settings.view_distribution),
            point_sample_count=int(settings.point_sample_count),
        )

        errors = validate_settings(snapshot)
        if settings.target_collection is None:
            errors.append("Target Collection is required.")

        if errors:
            for message in errors:
                self.report({"ERROR"}, message)
            return {"CANCELLED"}

        output_dir = Path(snapshot.save_path).expanduser() / snapshot.dataset_name

        try:
            self._session = begin_dataset_build(
                context=context,
                settings=settings,
                snapshot=snapshot,
                output_dir=output_dir,
            )
        except DatasetBuildError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:  # pragma: no cover - Blender runtime only.
            self.report({"ERROR"}, f"Unexpected failure: {exc}")
            return {"CANCELLED"}

        self._phase = "POINTS_PREP"
        self._pending_frame_index = None
        self._render_inflight = False
        self._render_finished = False
        self._render_cancelled = False
        _set_active_generator(self)
        _ensure_render_handlers_registered()
        settings.is_running = True
        settings.cancel_requested = False
        settings.progress_current = 0
        settings.progress_total = snapshot.total_frames + snapshot.point_sample_count + 1
        settings.status_text = "Preparing point sampling"
        context.window_manager.progress_begin(0, settings.progress_total)
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, f"Diagnostics log: {self._session.diagnostics.log_path}")
        self._tag_redraw(context)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return self.invoke(context, None)

    def modal(self, context, event):
        settings = context.scene.three_dgs_settings

        if event.type == "ESC":
            settings.cancel_requested = True

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if settings.cancel_requested and not self._render_inflight:
            self.report({"WARNING"}, "Dataset generation cancelled.")
            self._finish(context, cancelled=True)
            return {"CANCELLED"}

        try:
            if self._phase == "POINTS_PREP":
                prepare_point_sampling(context, self._session)
                start_point_sampling_worker(self._session)
                self._phase = "POINTS"
                settings.status_text = (
                    f"Sampling points 0 / {self._session.snapshot.point_sample_count}"
                )

            elif self._phase == "POINTS":
                if settings.cancel_requested:
                    cancel_point_sampling_worker(self._session)
                    self.report({"WARNING"}, "Dataset generation cancelled.")
                    self._finish(context, cancelled=True)
                    return {"CANCELLED"}
                complete = poll_point_sampling_worker(self._session)
                point_state = self._session.point_state
                settings.progress_current = point_state.sampled_count
                settings.status_text = (
                    f"Sampling points {point_state.sampled_count} / {self._session.snapshot.point_sample_count}"
                )
                context.window_manager.progress_update(settings.progress_current)
                if complete:
                    self._phase = "RENDER"

            elif self._phase == "RENDER":
                if self._render_inflight and _is_render_job_running():
                    self._tag_redraw(context)
                    return {"RUNNING_MODAL"}

                if self._render_cancelled:
                    if settings.cancel_requested:
                        self.report({"WARNING"}, "Dataset generation cancelled.")
                    else:
                        self.report({"ERROR"}, "Render job was cancelled before completion.")
                    self._finish(context, cancelled=True)
                    return {"CANCELLED"}

                if self._render_finished:
                    if self._pending_frame_index is None:
                        raise DatasetBuildError("Render completion was reported without a pending frame.")
                    rendered = finalize_rendered_frame(self._session, self._pending_frame_index)
                    self._pending_frame_index = None
                    self._render_inflight = False
                    self._render_finished = False
                    settings.progress_current = self._session.snapshot.point_sample_count + rendered
                    settings.status_text = f"Rendering {rendered} / {self._session.snapshot.total_frames}"
                    context.window_manager.progress_update(settings.progress_current)
                    if settings.cancel_requested:
                        self.report({"WARNING"}, "Dataset generation cancelled.")
                        self._finish(context, cancelled=True)
                        return {"CANCELLED"}
                    if not has_remaining_frames(self._session):
                        self._phase = "WRITE"

                elif not self._render_inflight:
                    if settings.cancel_requested:
                        self.report({"WARNING"}, "Dataset generation cancelled.")
                        self._finish(context, cancelled=True)
                        return {"CANCELLED"}
                    self._start_next_render(context)

            elif self._phase == "WRITE":
                result = write_outputs(self._session)
                settings.progress_current = settings.progress_total
                settings.status_text = f"Completed {result.frame_count} frames / {result.point_count} points"
                context.window_manager.progress_update(settings.progress_total)
                for warning in result.warnings:
                    self.report({"WARNING"}, warning.message)
                self.report(
                    {"INFO"},
                    (
                        f"Generated {result.frame_count} frames and {result.point_count} points "
                        f"at {result.output_dir} "
                        f"(warnings: {len(result.warnings)}, "
                        f"fallback materials: {result.fallback_material_count}, "
                        f"fallback triangles: {result.fallback_triangle_count})"
                    ),
                )
                self._finish(context, cancelled=False)
                return {"FINISHED"}

        except DatasetBuildError as exc:
            if self._session is not None:
                self._session.diagnostics.error(f"Dataset build failed: {exc}")
            self.report({"ERROR"}, str(exc))
            self._finish(context, cancelled=True)
            return {"CANCELLED"}
        except Exception as exc:  # pragma: no cover - Blender runtime only.
            if self._session is not None:
                self._session.diagnostics.exception("Unexpected failure in modal dataset generation.")
            self.report({"ERROR"}, f"Unexpected failure: {exc}")
            self._finish(context, cancelled=True)
            return {"CANCELLED"}

        self._tag_redraw(context)
        return {"RUNNING_MODAL"}

    def _finish(self, context, cancelled: bool) -> None:
        settings = context.scene.three_dgs_settings
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window_manager.progress_end()
        _clear_active_generator(self)
        _remove_render_handlers()

        if self._session is not None:
            cleanup_dataset_build(self._session)
            self._session = None

        if cancelled:
            settings.status_text = "Cancelled"
        settings.is_running = False
        settings.cancel_requested = False
        settings.progress_current = 0 if cancelled else settings.progress_current
        self._phase = "IDLE"
        self._pending_frame_index = None
        self._render_inflight = False
        self._render_finished = False
        self._render_cancelled = False
        self._tag_redraw(context)

    def _tag_redraw(self, context) -> None:
        screen = context.window.screen if context.window else None
        if screen is None:
            return
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def _start_next_render(self, context) -> None:
        if _is_render_job_running():
            return
        frame_index = prepare_next_frame_render(self._session)
        self._pending_frame_index = frame_index
        self._render_inflight = True
        self._render_finished = False
        self._render_cancelled = False
        context.scene.three_dgs_settings.status_text = (
            f"Rendering {frame_index + 1} / {self._session.snapshot.total_frames}"
        )
        result = bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
        self._session.diagnostics.info(f"Render operator returned {sorted(result)} for frame {frame_index + 1}.")
        if "CANCELLED" in result:
            self._pending_frame_index = None
            self._render_inflight = False
            if _is_render_job_running():
                return
            raise DatasetBuildError("Failed to start the render job.")
        if "FINISHED" in result:
            self._render_finished = True


class THREE_DGS_OT_cancel_dataset_generation(bpy.types.Operator):
    bl_idname = "three_dgs.cancel_dataset_generation"
    bl_label = "Cancel Generation"
    bl_description = "Request cancellation after the current step finishes"

    @classmethod
    def poll(cls, context):
        return bool(getattr(context.scene, "three_dgs_settings", None)) and context.scene.three_dgs_settings.is_running

    def execute(self, context):
        context.scene.three_dgs_settings.cancel_requested = True
        context.scene.three_dgs_settings.status_text = "Cancelling..."
        return {"FINISHED"}


_ACTIVE_GENERATOR: THREE_DGS_OT_generate_dataset | None = None


def _set_active_generator(operator: THREE_DGS_OT_generate_dataset) -> None:
    global _ACTIVE_GENERATOR
    _ACTIVE_GENERATOR = operator


def _clear_active_generator(operator: THREE_DGS_OT_generate_dataset) -> None:
    global _ACTIVE_GENERATOR
    if _ACTIVE_GENERATOR is operator:
        _ACTIVE_GENERATOR = None


def _ensure_render_handlers_registered() -> None:
    if _on_render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(_on_render_complete)
    if _on_render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(_on_render_cancel)


def _remove_render_handlers() -> None:
    if _on_render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(_on_render_complete)
    if _on_render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(_on_render_cancel)


def _on_render_complete(*_args) -> None:
    if _ACTIVE_GENERATOR is None or not _ACTIVE_GENERATOR._render_inflight:
        return
    _ACTIVE_GENERATOR._render_finished = True


def _on_render_cancel(*_args) -> None:
    if _ACTIVE_GENERATOR is None or not _ACTIVE_GENERATOR._render_inflight:
        return
    _ACTIVE_GENERATOR._render_inflight = False
    _ACTIVE_GENERATOR._render_cancelled = True


def _is_render_job_running() -> bool:
    try:
        return bool(bpy.app.is_job_running("RENDER"))
    except Exception:
        return False
