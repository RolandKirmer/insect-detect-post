# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import shutil
import textwrap
from datetime import datetime
from pathlib import Path


# =====================================================
# PATHS
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parent

SRC_DIR = (
    PROJECT_ROOT
    / "src"
    / "insectdetect_post"
)

CONFIG_FILE = SRC_DIR / "config.py"
IMAGE_PROCESSOR = SRC_DIR / "image_processor.py"
PIPELINE_RUNNER = SRC_DIR / "pipeline_runner.py"
GUI_FILE = SRC_DIR / "post_processing_gui.py"
INSECT_FILTER_FILE = SRC_DIR / "insect_filter.py"


# =====================================================
# HELPERS
# =====================================================

def read_file(path: Path) -> str:
    return path.read_text(
        encoding="utf-8"
    )


def write_file(
    path: Path,
    text: str
) -> None:

    path.write_text(
        text,
        encoding="utf-8"
    )


def check_syntax(
    text: str,
    filename: str
) -> None:

    compile(
        text,
        filename,
        "exec"
    )


def make_backup() -> Path:

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_root = (
        PROJECT_ROOT
        / f"insect_filter_backup_{timestamp}"
    )

    files = [
        CONFIG_FILE,
        IMAGE_PROCESSOR,
        PIPELINE_RUNNER,
        GUI_FILE,
    ]

    for path in files:

        relative = path.relative_to(
            PROJECT_ROOT
        )

        target = (
            backup_root
            / relative
        )

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            path,
            target
        )

    return backup_root


# =====================================================
# CONFIG.PY
# =====================================================

def remove_config_class(
    text: str,
    class_name: str
) -> str:

    pattern = re.compile(
        rf"(?ms)^class {re.escape(class_name)}\(BaseModel\):\n"
        rf".*?(?=^class |\Z)"
    )

    return pattern.sub(
        "",
        text,
        count=1
    )


def patch_config(
    text: str
) -> str:

    print()
    print("Patching config.py...")

    # -------------------------------------------------
    # Remove old versions if already present
    # -------------------------------------------------

    text = remove_config_class(
        text,
        "SaveNoInsectCropsConfig"
    )

    text = remove_config_class(
        text,
        "InsectFilterConfig"
    )

    # -------------------------------------------------
    # Add clean config classes
    # -------------------------------------------------

    marker = "class OverlayConfig(BaseModel):"

    if marker not in text:
        raise RuntimeError(
            "Could not find OverlayConfig "
            "in config.py"
        )

    block = '''class SaveNoInsectCropsConfig(BaseModel):
    """Optionally save crops rejected as No-Insect."""
    enabled: bool = False
    output_path: str = ""


class InsectFilterConfig(BaseModel):
    """Filter generated crops with an Insect / No-Insect TFLite model."""
    enabled: bool = False
    threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0
    )
    model_path: str = ""
    save_no_insect_crops: SaveNoInsectCropsConfig = SaveNoInsectCropsConfig()


'''

    text = text.replace(
        marker,
        block + marker,
        1
    )

    # -------------------------------------------------
    # Add insect_filter to ProcessingConfig
    # -------------------------------------------------

    match = re.search(
        r"(?ms)^class ProcessingConfig\(BaseModel\):\n"
        r".*?(?=^class |\Z)",
        text
    )

    if not match:
        raise RuntimeError(
            "Could not find ProcessingConfig"
        )

    processing_block = match.group(0)

    # Remove an old field if present
    processing_block = re.sub(
        r"^    insect_filter:.*\n",
        "",
        processing_block,
        flags=re.MULTILINE
    )

    crop_line = (
        "    crop: CropConfig = CropConfig()\n"
    )

    if crop_line not in processing_block:
        raise RuntimeError(
            "Could not find crop field "
            "inside ProcessingConfig"
        )

    processing_block = processing_block.replace(
        crop_line,
        crop_line
        + "    insect_filter: InsectFilterConfig = "
          "InsectFilterConfig()\n",
        1
    )

    text = (
        text[:match.start()]
        + processing_block
        + text[match.end():]
    )

    print("  OK: InsectFilterConfig added")
    print("  OK: threshold added")
    print("  OK: model path added")
    print("  OK: optional No-Insect output added")

    return text


# =====================================================
# IMAGE_PROCESSOR.PY
# =====================================================

def patch_image_processor(
    text: str
) -> str:

    print()
    print("Patching image_processor.py...")

    # -------------------------------------------------
    # IMPORT
    # -------------------------------------------------

    import_line = (
        "from insectdetect_post.insect_filter "
        "import reject_crop"
    )

    if import_line not in text:

        marker = (
            "from insectdetect_post.exceptions "
            "import PipelineCancelled"
        )

        if marker not in text:
            raise RuntimeError(
                "Could not find import insertion "
                "point in image_processor.py"
            )

        text = text.replace(
            marker,
            marker
            + "\n"
            + import_line,
            1
        )

    print("  OK: reject_crop imported")

    # -------------------------------------------------
    # POSTCONFIG
    # -------------------------------------------------

    match = re.search(
        r"(?ms)^@dataclass\nclass PostConfig:\n"
        r".*?(?=^def make_bbox_square)",
        text
    )

    if not match:
        raise RuntimeError(
            "Could not find PostConfig"
        )

    post_block = match.group(0)

    field_names = [
        "insect_filter_enabled",
        "insect_filter_threshold",
        "insect_filter_model_path",
        "save_no_insect_crops",
        "no_insect_output_path",
    ]

    # Remove previous versions of these fields
    for field in field_names:

        post_block = re.sub(
            rf"^    {field}:.*\n",
            "",
            post_block,
            flags=re.MULTILINE
        )

    filter_fields = '''    insect_filter_enabled: bool = False
    insect_filter_threshold: float = 0.90
    insect_filter_model_path: str = ""

    save_no_insect_crops: bool = False
    no_insect_output_path: str = ""

'''

    img_ext_marker = (
        '    img_ext: str = ".jpg"\n'
    )

    if img_ext_marker not in post_block:
        raise RuntimeError(
            "Could not find img_ext "
            "inside PostConfig"
        )

    post_block = post_block.replace(
        img_ext_marker,
        filter_fields
        + img_ext_marker,
        1
    )

    text = (
        text[:match.start()]
        + post_block
        + text[match.end():]
    )

    print("  OK: PostConfig extended")

    # -------------------------------------------------
    # FILTER CROP
    # -------------------------------------------------

    # If our filter is already present, do not duplicate it
    if (
        "# INSECT / NO-INSECT FILTER"
        in text
    ):

        print(
            "  OK: crop filter already present"
        )

        return text

    crop_pattern = re.compile(
        r"^(?P<indent>[ \t]*)"
        r"crop = img\[y0:y1, x0:x1\]\s*$",
        re.MULTILINE
    )

    crop_match = crop_pattern.search(
        text
    )

    if not crop_match:
        raise RuntimeError(
            "Could not find crop creation line"
        )

    indent = crop_match.group(
        "indent"
    )

    filter_code = '''# =====================================================
# INSECT / NO-INSECT FILTER
# =====================================================

if post_config.insect_filter_enabled:

    reject, filter_label, filter_score = reject_crop(
        crop,
        model_path=post_config.insect_filter_model_path,
        threshold=post_config.insect_filter_threshold
    )

    if reject:

        logger.debug(
            "Rejected crop %s: %s %.4f",
            crop_filename,
            filter_label,
            filter_score
        )

        # =============================================
        # OPTIONAL: SAVE REJECTED NO-INSECT CROP
        # =============================================

        if (
            post_config.save_no_insect_crops
            and post_config.no_insect_output_path
        ):

            relative_folder = (
                img_path.parent.relative_to(
                    context.root_path
                )
            )

            no_insect_folder = (
                Path(
                    post_config.no_insect_output_path
                )
                / relative_folder
            )

            no_insect_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            score_txt = (
                f"{filter_score:.4f}"
                .replace(".", "p")
            )

            no_insect_name = (
                f"{Path(crop_filename).stem}"
                f"_No-Insect_{score_txt}"
                f"{post_config.img_ext}"
            )

            cv2.imwrite(
                str(
                    no_insect_folder
                    / no_insect_name
                ),
                crop
            )

        # Rejected crop is not added to normal crops
        continue
'''

    indented_filter = textwrap.indent(
        filter_code,
        indent
    )

    insertion_pos = crop_match.end()

    text = (
        text[:insertion_pos]
        + "\n\n"
        + indented_filter
        + text[insertion_pos:]
    )

    print(
        "  OK: Insect/No-Insect filter "
        "added before crop saving"
    )

    return text


# =====================================================
# PIPELINE_RUNNER.PY
# =====================================================

def patch_pipeline_runner(
    text: str
) -> str:

    print()
    print("Patching pipeline_runner.py...")

    # -------------------------------------------------
    # Find PostConfig(...) in _process_images()
    # -------------------------------------------------

    pattern = re.compile(
        r"(?ms)"
        r"(?P<start>"
        r"        post_config = PostConfig\(\n"
        r")"
        r"(?P<body>.*?)"
        r"(?P<end>"
        r"^        \)"
        r")"
    )

    match = pattern.search(
        text
    )

    if not match:
        raise RuntimeError(
            "Could not find PostConfig(...) "
            "inside pipeline_runner.py"
        )

    body = match.group(
        "body"
    )

    # Remove existing insect filter arguments
    # by reconstructing from existing lines
    lines = body.splitlines()

    filter_argument_names = (
        "insect_filter_enabled=",
        "insect_filter_threshold=",
        "insect_filter_model_path=",
        "save_no_insect_crops=",
        "no_insect_output_path=",
    )

    cleaned = []
    skip_nested = False
    paren_balance = 0

    i = 0

    while i < len(lines):

        line = lines[i]

        stripped = line.strip()

        if any(
            stripped.startswith(name)
            for name in filter_argument_names
        ):

            balance = (
                line.count("(")
                - line.count(")")
            )

            i += 1

            while (
                i < len(lines)
                and balance > 0
            ):

                balance += (
                    lines[i].count("(")
                    - lines[i].count(")")
                )

                i += 1

            continue

        cleaned.append(
            line
        )

        i += 1

    # Remove trailing blank lines
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    # Ensure previous last argument has comma
    if cleaned:

        last = cleaned[-1]

        if not last.rstrip().endswith(","):
            cleaned[-1] = (
                last.rstrip()
                + ","
            )

    new_args = [
        "",
        "            insect_filter_enabled=(",
        "                self.config.processing.insect_filter.enabled",
        "            ),",
        "",
        "            insect_filter_threshold=(",
        "                self.config.processing.insect_filter.threshold",
        "            ),",
        "",
        "            insect_filter_model_path=(",
        "                self.config.processing.insect_filter.model_path",
        "            ),",
        "",
        "            save_no_insect_crops=(",
        "                self.config",
        "                .processing",
        "                .insect_filter",
        "                .save_no_insect_crops",
        "                .enabled",
        "            ),",
        "",
        "            no_insect_output_path=(",
        "                self.config",
        "                .processing",
        "                .insect_filter",
        "                .save_no_insect_crops",
        "                .output_path",
        "            ),",
    ]

    cleaned.extend(
        new_args
    )

    new_body = (
        "\n".join(cleaned)
        + "\n"
    )

    replacement = (
        match.group("start")
        + new_body
        + match.group("end")
    )

    text = (
        text[:match.start()]
        + replacement
        + text[match.end():]
    )

    print(
        "  OK: filter settings passed "
        "to PostConfig"
    )

    return text


# =====================================================
# GUI
# =====================================================

def patch_gui(
    text: str
) -> str:

    print()
    print("Patching post_processing_gui.py...")

    # -------------------------------------------------
    # THRESHOLD CONSTRAINT
    # -------------------------------------------------

    constraint = (
        '"processing.insect_filter.threshold",'
    )

    if constraint not in text:

        marker = (
            "_CONSTRAINT_PATHS: list[str] = [\n"
        )

        if marker not in text:
            raise RuntimeError(
                "Could not find _CONSTRAINT_PATHS"
            )

        text = text.replace(
            marker,
            marker
            + "    "
            + constraint
            + "\n",
            1
        )

    print(
        "  OK: threshold constraint added"
    )

    # -------------------------------------------------
    # GUI ATTRIBUTE DECLARATIONS
    # -------------------------------------------------

    if (
        "insect_filter_box: Any"
        not in text
    ):

        marker = (
            "    crop_box: Any\n"
        )

        if marker not in text:
            raise RuntimeError(
                "Could not find crop_box attribute"
            )

        text = text.replace(
            marker,
            marker
            + "    insect_filter_box: Any\n"
            + "    save_no_insect_crops_box: Any\n",
            1
        )

    print(
        "  OK: GUI attributes added"
    )

    # -------------------------------------------------
    # REPLACE PROCESSING GUI METHOD
    # -------------------------------------------------

    method_pattern = re.compile(
        r"(?ms)"
        r"^    def _create_processing_params\(self\) -> None:\n"
        r".*?"
        r"(?=^    def _create_classification_params\(self\) -> None:)"
    )

    match = method_pattern.search(
        text
    )

    if not match:
        raise RuntimeError(
            "Could not find "
            "_create_processing_params()"
        )

    new_method = '''    def _create_processing_params(self) -> None:
        """Create parameter forms for image processing settings."""

        # =================================================
        # CROP
        # =================================================

        crop_form, self.crop_box = create_param_form(
            self.processing_form,
            "crop",
            "Crop Detections",
            tooltip=(
                "Save individual detections as separate .jpg files - "
                "cropped from original frames, or copied as-is for "
                "detections that only have an existing crop file"
            )
        )

        crop_method_select = ComboParameter(
            "method"
        )

        crop_method_select.set_label(
            "Crop Method"
        )

        crop_method_select.set_items(
            ("square", "original")
        )

        crop_method_select.set_default(
            _DEFAULTS.processing.crop.method
        )

        crop_method_select.setToolTip(
            "'square' avoids distortion during resizing "
            "for classification and is recommended"
        )

        crop_form.add_parameter(
            crop_method_select
        )

        # =================================================
        # INSECT / NO-INSECT FILTER
        # =================================================

        (
            insect_filter_form,
            self.insect_filter_box
        ) = create_param_form(
            self.processing_form,
            "insect_filter",
            "Insect / No-Insect Filter",
            tooltip=(
                "Reject crops classified as No-Insect "
                "before further classification"
            )
        )

        lo, hi = _get_constraints(
            "processing.insect_filter.threshold"
        )

        insect_filter_form.add_parameter(
            create_num_param(
                "threshold",
                "No-Insect Confidence",
                min_val=lo,
                max_val=hi,
                default=(
                    _DEFAULTS
                    .processing
                    .insect_filter
                    .threshold
                ),
                param_type="float",
                tooltip=(
                    "Reject crop if No-Insect confidence "
                    "is at least this value"
                )
            )
        )

        # =================================================
        # MODEL PATH
        # =================================================

        model_path_param = PathParameter(
            "model_path"
        )

        model_path_param.set_label(
            "TFLite Model"
        )

        model_path_param.set_method(
            PathParameter.Method.OPEN_FILE
        )

        model_path_param.setToolTip(
            "Path to the trained.tflite model"
        )

        insect_filter_form.add_parameter(
            model_path_param
        )

        # =================================================
        # SAVE NO-INSECT CROPS
        # =================================================

        (
            save_form,
            self.save_no_insect_crops_box
        ) = create_param_form(
            insect_filter_form,
            "save_no_insect_crops",
            "Save No-Insect Crops",
            tooltip=(
                "Save rejected No-Insect crops "
                "to a separate directory"
            )
        )

        output_path_param = PathParameter(
            "output_path"
        )

        output_path_param.set_label(
            "Output Path"
        )

        output_path_param.set_method(
            PathParameter.Method.EXISTING_DIR
        )

        output_path_param.setToolTip(
            "Destination for rejected No-Insect crops"
        )

        save_form.add_parameter(
            output_path_param
        )

        # =================================================
        # OVERLAY
        # =================================================

        _, self.overlay_box = create_param_form(
            self.processing_form,
            "overlay",
            "Draw Overlays",
            tooltip=(
                "Draw overlays on full frames "
                "(bounding box, label, confidence, track ID)"
            )
        )

        if self.crop_box:
            self.crop_box.checkbox.toggled.connect(
                self._on_crop_checkbox_toggle
            )

'''

    text = (
        text[:match.start()]
        + new_method
        + text[match.end():]
    )

    print(
        "  OK: GUI controls added"
    )
    print(
        "  OK: OPEN_FILE used for TFLite model"
    )

    return text


# =====================================================
# VALIDATION
# =====================================================

def validate_result(
    config_text: str,
    image_text: str,
    pipeline_text: str,
    gui_text: str
) -> None:

    required_config = [
        "class InsectFilterConfig",
        "class SaveNoInsectCropsConfig",
        "insect_filter: InsectFilterConfig",
        "threshold: float",
        "model_path: str",
    ]

    required_image = [
        "from insectdetect_post.insect_filter import reject_crop",
        "insect_filter_enabled",
        "insect_filter_threshold",
        "insect_filter_model_path",
        "save_no_insect_crops",
        "no_insect_output_path",
        "reject_crop(",
    ]

    required_pipeline = [
        "insect_filter_enabled=",
        "insect_filter_threshold=",
        "insect_filter_model_path=",
        "save_no_insect_crops=",
        "no_insect_output_path=",
    ]

    required_gui = [
        "processing.insect_filter.threshold",
        "Insect / No-Insect Filter",
        "No-Insect Confidence",
        "TFLite Model",
        "Save No-Insect Crops",
        "PathParameter.Method.OPEN_FILE",
    ]

    groups = [
        (
            "config.py",
            config_text,
            required_config
        ),
        (
            "image_processor.py",
            image_text,
            required_image
        ),
        (
            "pipeline_runner.py",
            pipeline_text,
            required_pipeline
        ),
        (
            "post_processing_gui.py",
            gui_text,
            required_gui
        ),
    ]

    for filename, text, required in groups:

        missing = [
            value
            for value in required
            if value not in text
        ]

        if missing:

            raise RuntimeError(
                f"{filename}: missing expected "
                f"changes: {missing}"
            )


# =====================================================
# MAIN
# =====================================================

def main() -> None:

    print("=" * 65)
    print("INSECT / NO-INSECT FILTER UPDATER")
    print("=" * 65)

    # -------------------------------------------------
    # Check project
    # -------------------------------------------------

    required_files = [
        CONFIG_FILE,
        IMAGE_PROCESSOR,
        PIPELINE_RUNNER,
        GUI_FILE,
        INSECT_FILTER_FILE,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"Required file not found:\n{path}"
            )

    print()
    print(
        "Found insect_filter.py:"
    )
    print(
        INSECT_FILTER_FILE
    )

    # -------------------------------------------------
    # Backup
    # -------------------------------------------------

    backup = make_backup()

    print()
    print("Backup created:")
    print(backup)

    # -------------------------------------------------
    # Read
    # -------------------------------------------------

    config_text = read_file(
        CONFIG_FILE
    )

    image_text = read_file(
        IMAGE_PROCESSOR
    )

    pipeline_text = read_file(
        PIPELINE_RUNNER
    )

    gui_text = read_file(
        GUI_FILE
    )

    # -------------------------------------------------
    # Patch
    # -------------------------------------------------

    config_text = patch_config(
        config_text
    )

    image_text = patch_image_processor(
        image_text
    )

    pipeline_text = patch_pipeline_runner(
        pipeline_text
    )

    gui_text = patch_gui(
        gui_text
    )

    # -------------------------------------------------
    # Validate
    # -------------------------------------------------

    print()
    print("Validating changes...")

    validate_result(
        config_text,
        image_text,
        pipeline_text,
        gui_text
    )

    # -------------------------------------------------
    # Syntax check BEFORE writing
    # -------------------------------------------------

    check_syntax(
        config_text,
        str(CONFIG_FILE)
    )

    check_syntax(
        image_text,
        str(IMAGE_PROCESSOR)
    )

    check_syntax(
        pipeline_text,
        str(PIPELINE_RUNNER)
    )

    check_syntax(
        gui_text,
        str(GUI_FILE)
    )

    print(
        "  OK: Python syntax valid"
    )

    # -------------------------------------------------
    # Write
    # -------------------------------------------------

    write_file(
        CONFIG_FILE,
        config_text
    )

    write_file(
        IMAGE_PROCESSOR,
        image_text
    )

    write_file(
        PIPELINE_RUNNER,
        pipeline_text
    )

    write_file(
        GUI_FILE,
        gui_text
    )

    # -------------------------------------------------
    # DONE
    # -------------------------------------------------

    print()
    print("=" * 65)
    print("UPDATE COMPLETE")
    print("=" * 65)

    print()
    print("Added:")
    print(
        "1. Insect/No-Insect on/off switch"
    )
    print(
        "2. Adjustable No-Insect threshold"
    )
    print(
        "3. Selectable TFLite model path"
    )
    print(
        "4. Optional saving of rejected crops"
    )
    print(
        "5. Selectable No-Insect output path"
    )
    print(
        "6. Filter directly before normal crop saving"
    )
    print(
        "7. GUI controls for all settings"
    )

    print()
    print("Backup:")
    print(backup)

    print()
    print("Start GUI:")
    print(
        "uv run --no-sync gui"
    )


if __name__ == "__main__":
    main()