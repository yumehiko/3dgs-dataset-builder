import bpy

from . import bl_info


class THREE_DGS_PT_dataset_panel(bpy.types.Panel):
    bl_label = "3DGS Dataset"
    bl_idname = "THREE_DGS_PT_dataset_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3DGS Dataset"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.three_dgs_settings
        version = ".".join(str(part) for part in bl_info["version"])

        header_box = layout.box()
        header_box.label(text=f"Addon Version: {version}")

        dataset_box = layout.box()
        dataset_box.label(text="Dataset")
        dataset_box.prop(settings, "save_path")
        dataset_box.prop(settings, "dataset_name")
        dataset_box.prop(settings, "include_extension")

        camera_box = layout.box()
        camera_box.label(text="Camera Sampling")
        camera_box.prop(settings, "target_collection")
        camera_box.prop(settings, "focus_object")
        camera_box.prop(settings, "total_frames")
        camera_box.prop(settings, "view_distribution")
        radius_row = camera_box.row(align=True)
        radius_row.prop(settings, "min_radius")
        radius_row.prop(settings, "max_radius")
        camera_box.prop(settings, "close_up_ratio")

        point_box = layout.box()
        point_box.label(text="Point Cloud")
        point_box.prop(settings, "point_sample_count")

        layout.separator()
        status_box = layout.box()
        status_box.label(text="Status")
        status_box.label(text=settings.status_text or "Idle")
        if settings.is_running and settings.progress_total > 0:
            status_box.label(text=f"{settings.progress_current} / {settings.progress_total}")

        action_row = layout.row()
        if settings.is_running:
            action_row.operator("three_dgs.cancel_dataset_generation", icon="CANCEL")
        else:
            action_row.operator("three_dgs.generate_dataset", icon="RENDER_STILL")
