"""Blender addon entrypoint for 3DGS Dataset Builder."""

bl_info = {
    "name": "3DGS Dataset Builder",
    "author": "OpenAI Codex",
    "version": (0, 3, 4),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > 3DGS Dataset",
    "description": "Generate randomized 3DGS training datasets from Blender collections.",
    "category": "Import-Export",
}

try:
    import bpy
    from bpy.props import PointerProperty
except ImportError:  # pragma: no cover - only executed outside Blender.
    bpy = None
    PointerProperty = None

if bpy is not None:  # pragma: no branch - Blender runtime only.
    from .operators import (
        THREE_DGS_OT_cancel_dataset_generation,
        THREE_DGS_OT_generate_dataset,
    )
    from .panel import THREE_DGS_PT_dataset_panel
    from .properties import ThreeDGSSettings

    CLASSES = (
        ThreeDGSSettings,
        THREE_DGS_OT_generate_dataset,
        THREE_DGS_OT_cancel_dataset_generation,
        THREE_DGS_PT_dataset_panel,
    )


def register():
    if bpy is None:
        raise RuntimeError("Blender's bpy module is required to register this addon.")

    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.three_dgs_settings = PointerProperty(type=ThreeDGSSettings)


def unregister():
    if bpy is None:
        return

    if hasattr(bpy.types.Scene, "three_dgs_settings"):
        del bpy.types.Scene.three_dgs_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
