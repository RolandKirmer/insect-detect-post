"""Helper functions for GUI widgets and their config values.

Source:   https://github.com/maxsitt/insect-detect-post
License:  GNU AGPLv3 (https://choosealicense.com/licenses/agpl-3.0/)
Author:   Maximilian Sittinger (https://github.com/maxsitt)
Docs:     https://maxsitt.github.io/insect-detect-docs/

Provides styled widget and parameter form factories, conversion between nested
config dicts and flat ParameterForm values, and source/output path validation.

Functions:
    create_groupbox(): Create a styled QGroupBox for a config ParameterForm.
    create_param_form(): Create a child parameter form and add it to the parent form.
    create_num_param(): Create a numeric parameter with slider.
    extract_enabled_values(): Extract enabled flags from nested dicts for ParameterForm compatibility.
    restore_enabled_values(): Restore enabled flags back into nested dicts for YAML compatibility.
    resolve_and_validate_path(): Resolve and validate a path string.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from PySide6.QtWidgets import QGroupBox, QVBoxLayout
from qt_parameters import CollapsibleBox, FloatParameter, IntParameter, ParameterForm


def create_groupbox(title: str, color: str, form: ParameterForm) -> QGroupBox:
    """Create a styled QGroupBox for a config ParameterForm.

    Args:
        title: Display title shown on the group box header.
        color: Border/accent color as a CSS color string (e.g. hex code).
        form: ParameterForm to embed inside the group box.

    Returns:
        Styled QGroupBox containing the given form.
    """
    box = QGroupBox(title)
    box.setStyleSheet(f"""
        QGroupBox {{
            border: 2px solid {color};
            border-radius: 8px;
            font-weight: bold;
            margin-top: 0.5em;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 5px;
            padding: 0 3px 0 3px;
        }}
    """)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 6, 0, 0)
    layout.addWidget(form)
    return box


def create_param_form(
    parent_form: ParameterForm,
    name: str,
    title: str,
    tooltip: str = "",
    has_checkbox: bool = True
) -> tuple[ParameterForm, CollapsibleBox]:
    """Create a child parameter form and add it to the parent form.

    Args:
        parent_form: Form to nest the new child form under.
        name: Internal parameter name of the child form.
        title: Display title shown on the collapsible box header.
        tooltip: Optional tooltip for the collapsible box.
        has_checkbox: Add a checkbox to the box header, tied to the section's enabled state.

    Returns:
        Tuple of (child form, its collapsible box container).
    """
    child_form = ParameterForm(name)
    form_box = parent_form.add_form(child_form, checkable=has_checkbox)
    form_box.set_title(title)
    form_box.set_collapsible(False)
    if tooltip:
        form_box.setToolTip(tooltip)
    return child_form, form_box


def create_num_param(
    name: str,
    label: str,
    min_val: float,
    max_val: float,
    default: float,
    param_type: Literal["int", "float"] = "int",
    tooltip: str = ""
) -> IntParameter | FloatParameter:
    """Create a numeric parameter with slider.

    Args:
        name: Internal parameter name.
        label: Display label shown next to the slider.
        min_val: Minimum value for both the line edit and slider.
        max_val: Maximum value for both the line edit and slider.
        default: Default value.
        param_type: "int" for an IntParameter, "float" for a FloatParameter.
        tooltip: Optional tooltip for the parameter.

    Returns:
        Configured IntParameter or FloatParameter instance.
    """
    param = FloatParameter(name) if param_type == "float" else IntParameter(name)
    param.set_label(label)
    if isinstance(param, FloatParameter):
        param.set_decimals(2)
        param.set_line_min(float(min_val))
        param.set_line_max(float(max_val))
        param.set_slider_min(float(min_val))
        param.set_slider_max(float(max_val))
        param.set_default(float(default))
    else:
        param.set_line_min(int(min_val))
        param.set_line_max(int(max_val))
        param.set_slider_min(int(min_val))
        param.set_slider_max(int(max_val))
        param.set_default(int(default))
    if tooltip:
        param.setToolTip(tooltip)
    return param


def extract_enabled_values(config: dict[str, Any]) -> dict[str, Any]:
    """Extract enabled flags from nested dicts for ParameterForm compatibility.

    Args:
        config: Config data as a nested dict (e.g. an AppConfig section dump).

    Returns:
        Flattened dict with a "<key>_enabled" entry alongside each nested "key" dict.
    """
    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict) and "enabled" in value:
            rest = {k: v for k, v in value.items() if k != "enabled"}
            result[key] = extract_enabled_values(rest)
            result[f"{key}_enabled"] = value["enabled"]
        else:
            result[key] = value
    return result


def restore_enabled_values(config: dict[str, Any]) -> dict[str, Any]:
    """Restore enabled flags back into nested dicts for YAML compatibility.

    Args:
        config: Config data as a flattened dict, as produced by extract_enabled_values().

    Returns:
        Nested dict matching the original config data structure.
    """
    result: dict[str, Any] = {}
    for key, value in config.items():
        if key.endswith("_enabled"):
            base_key = key[:-8]
            if base_key not in result:
                result[base_key] = {}
            result[base_key]["enabled"] = value
    for key, value in config.items():
        if not key.endswith("_enabled"):
            if isinstance(value, dict):
                nested = restore_enabled_values(value)
                if key in result:
                    result[key].update(nested)
                else:
                    result[key] = nested
            else:
                result[key] = value
    return result


def resolve_and_validate_path(path_str: str) -> Path | None:
    """Resolve and validate a path string.

    Args:
        path_str: Path string to validate.

    Returns:
        Resolved Path object if valid directory, None otherwise.
    """
    if not path_str or not path_str.strip():
        return None

    stripped = path_str.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        stripped = stripped[1:-1].strip()

    path_obj = Path(stripped)
    if not path_obj.is_absolute():
        path_obj = path_obj.resolve()

    return path_obj if path_obj.exists() and path_obj.is_dir() else None
