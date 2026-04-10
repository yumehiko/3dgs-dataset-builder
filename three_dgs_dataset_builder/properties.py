import bpy


class ThreeDGSSettings(bpy.types.PropertyGroup):
    save_path: bpy.props.StringProperty(
        name="Save Path",
        subtype="DIR_PATH",
        description="Base directory where the dataset folder will be created",
    )
    dataset_name: bpy.props.StringProperty(
        name="Dataset Name",
        default="dataset",
        description="Output folder name inside the save path",
    )
    include_extension: bpy.props.BoolProperty(
        name="Include Extension",
        default=True,
        description="Include .png in JSON image paths",
    )
    target_collection: bpy.props.PointerProperty(
        name="Target Collection",
        type=bpy.types.Collection,
        description="Collection whose mesh objects are rendered and sampled",
    )
    focus_object: bpy.props.PointerProperty(
        name="Focus Object",
        type=bpy.types.Object,
        description="Optional object for the camera to look at; uses world origin when empty",
    )
    total_frames: bpy.props.IntProperty(
        name="Total Frames",
        default=100,
        min=1,
        soft_max=1000,
        description="Number of randomized camera views to render",
    )
    min_radius: bpy.props.FloatProperty(
        name="Min Radius",
        default=1.0,
        min=0.001,
        soft_max=100.0,
        description="Minimum camera distance from the focus point",
    )
    max_radius: bpy.props.FloatProperty(
        name="Max Radius",
        default=2.0,
        min=0.001,
        soft_max=100.0,
        description="Maximum camera distance from the focus point",
    )
    close_up_ratio: bpy.props.FloatProperty(
        name="Close-up Ratio",
        default=0.3,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Fraction of frames biased toward the minimum radius",
    )
    view_distribution: bpy.props.EnumProperty(
        name="View Distribution",
        items=(
            ("FULL_SPHERE", "Full Sphere", "Sample across the full sphere"),
            ("UPPER_HEMISPHERE", "Upper Hemisphere", "Sample only on the +Z hemisphere"),
        ),
        default="FULL_SPHERE",
        description="Spatial distribution of randomized camera viewpoints",
    )
    point_sample_count: bpy.props.IntProperty(
        name="Sample Count",
        default=50000,
        min=1,
        soft_max=1000000,
        description="Number of surface samples exported to points3d.ply",
    )
    is_running: bpy.props.BoolProperty(
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    cancel_requested: bpy.props.BoolProperty(
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    status_text: bpy.props.StringProperty(
        default="Idle",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    progress_current: bpy.props.IntProperty(
        default=0,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    progress_total: bpy.props.IntProperty(
        default=0,
        options={"HIDDEN", "SKIP_SAVE"},
    )
