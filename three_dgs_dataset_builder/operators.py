from pathlib import Path

import bpy

from .builder import (
    BuildSession,
    DatasetBuildError,
    begin_dataset_build,
    cleanup_dataset_build,
    has_remaining_frames,
    prepare_point_sampling,
    render_next_frame,
    sample_point_chunk,
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
    _point_chunk_size = 2000

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

        self._phase = "RENDER"
        settings.is_running = True
        settings.cancel_requested = False
        settings.progress_current = 0
        settings.progress_total = snapshot.total_frames + snapshot.point_sample_count + 1
        settings.status_text = f"Rendering 0 / {snapshot.total_frames}"
        context.window_manager.progress_begin(0, settings.progress_total)
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
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

        if settings.cancel_requested:
            self.report({"WARNING"}, "Dataset generation cancelled.")
            self._finish(context, cancelled=True)
            return {"CANCELLED"}

        try:
            if self._phase == "RENDER":
                rendered = render_next_frame(self._session)
                settings.progress_current = rendered
                settings.status_text = f"Rendering {rendered} / {self._session.snapshot.total_frames}"
                context.window_manager.progress_update(settings.progress_current)
                if not has_remaining_frames(self._session):
                    self._phase = "POINTS_PREP"

            elif self._phase == "POINTS_PREP":
                prepare_point_sampling(context, self._session)
                self._phase = "POINTS"
                settings.status_text = (
                    f"Sampling points 0 / {self._session.snapshot.point_sample_count}"
                )

            elif self._phase == "POINTS":
                complete = sample_point_chunk(self._session, chunk_size=self._point_chunk_size)
                point_state = self._session.point_state
                settings.progress_current = self._session.snapshot.total_frames + point_state.sampled_count
                settings.status_text = (
                    f"Sampling points {point_state.sampled_count} / {self._session.snapshot.point_sample_count}"
                )
                context.window_manager.progress_update(settings.progress_current)
                if complete:
                    self._phase = "WRITE"

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
            self.report({"ERROR"}, str(exc))
            self._finish(context, cancelled=True)
            return {"CANCELLED"}
        except Exception as exc:  # pragma: no cover - Blender runtime only.
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

        if self._session is not None:
            cleanup_dataset_build(self._session)
            self._session = None

        if cancelled:
            settings.status_text = "Cancelled"
        settings.is_running = False
        settings.cancel_requested = False
        self._phase = "IDLE"
        self._tag_redraw(context)

    def _tag_redraw(self, context) -> None:
        screen = context.window.screen if context.window else None
        if screen is None:
            return
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


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
