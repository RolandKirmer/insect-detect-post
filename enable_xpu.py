from pathlib import Path
from datetime import datetime
import re
import shutil
import subprocess
import tomllib

# PATHS

ROOT = Path(__file__).resolve().parent

PYPROJECT = ROOT / "pyproject.toml"
CONFIG = ROOT / "src" / "insectdetect_post" / "config.py"
GUI = ROOT / "src" / "insectdetect_post" / "post_processing_gui.py"

for file in (PYPROJECT, CONFIG, GUI):
    if not file.exists():
        raise FileNotFoundError(f"Nicht gefunden: {file}")

# READ

pyproject = PYPROJECT.read_text(encoding="utf-8")
config = CONFIG.read_text(encoding="utf-8")
gui = GUI.read_text(encoding="utf-8")

# PYPROJECT: XPU EXTRA

xpu_match = re.search(
    r'(?ms)^xpu\s*=\s*\[.*?^\]',
    pyproject
)

xpu_block = '''xpu = [
    "onnx >=1.22.0,<2",
    "onnxruntime >=1.28.0,<2",
    "torch >=2.13.0,<3",
    "torchvision >=0.28.0,<1",
    "triton-xpu ==3.7.2",
]'''

if xpu_match:
    pyproject = (
        pyproject[:xpu_match.start()]
        + xpu_block
        + pyproject[xpu_match.end():]
    )
else:
    if "[project.scripts]" not in pyproject:
        raise RuntimeError("[project.scripts] nicht gefunden.")

    pyproject = pyproject.replace(
        "[project.scripts]",
        xpu_block + "\n[project.scripts]",
        1
    )

# PYPROJECT: WINDOWS ENVIRONMENT + CONFLICT

start = pyproject.find("[tool.uv]")
end = pyproject.find("[tool.uv.sources]")

if start == -1 or end == -1:
    raise RuntimeError("[tool.uv] oder [tool.uv.sources] nicht gefunden.")

uv_section = pyproject[start:end]

# Only resolve Windows

environment_block = '''environments = [
    "sys_platform == 'win32'"
]'''

if re.search(r'(?ms)^environments\s*=\s*\[.*?^\]', uv_section):
    uv_section = re.sub(
        r'(?ms)^environments\s*=\s*\[.*?^\]',
        environment_block,
        uv_section,
        count=1
    )
else:
    if "package = true" in uv_section:
        uv_section = uv_section.replace(
            "package = true",
            "package = true\n" + environment_block,
            1
        )
    else:
        uv_section = uv_section.replace(
            "[tool.uv]",
            "[tool.uv]\n" + environment_block,
            1
        )

# XPU conflict

if '{ extra = "xpu" }' not in uv_section:

    old = '{ extra = "cuda132" },'

    if old not in uv_section:
        raise RuntimeError("cuda132 conflict nicht gefunden.")

    uv_section = uv_section.replace(
        old,
        old + '\n        { extra = "xpu" },',
        1
    )


pyproject = pyproject[:start] + uv_section + pyproject[end:]

# PYPROJECT: SOURCES

start = pyproject.find("[tool.uv.sources]")
end = pyproject.find("[[tool.uv.index]]", start)

if start == -1 or end == -1:
    raise RuntimeError("[tool.uv.sources] nicht gefunden.")

sources = pyproject[start:end]


def add_xpu_to_array(text, package):
    pattern = re.compile(
        rf'(?ms)^({re.escape(package)}\s*=\s*\[)(.*?)(^\])'
    )

    match = pattern.search(text)

    if not match:
        raise RuntimeError(f"{package} source block nicht gefunden.")

    body = match.group(2)

    if 'extra = "xpu"' not in body:
        body = (
            body.rstrip()
            + '\n    { index = "pytorch-xpu", extra = "xpu" },\n'
        )

    return (
        text[:match.start()]
        + match.group(1)
        + body
        + match.group(3)
        + text[match.end():]
    )


sources = add_xpu_to_array(sources, "torch")
sources = add_xpu_to_array(sources, "torchvision")

# Important: Triton must explicitly use XPU index

if "triton-xpu" not in sources:
    sources = sources.rstrip() + '''

triton-xpu = { index = "pytorch-xpu" }

'''


pyproject = pyproject[:start] + sources + pyproject[end:]

# PYPROJECT: XPU INDEX

xpu_index_block = '''[[tool.uv.index]]
name = "pytorch-xpu"
url = "https://download.pytorch.org/whl/xpu"
explicit = true
'''

pattern = re.compile(
    r'(?ms)\[\[tool\.uv\.index\]\]\s*\n'
    r'name\s*=\s*"pytorch-xpu".*?'
    r'(?=\n\[\[tool\.uv\.index\]\]|\n\[tool\.ruff\]|\Z)'
)

match = pattern.search(pyproject)

if match:
    pyproject = (
        pyproject[:match.start()]
        + xpu_index_block.rstrip()
        + "\n"
        + pyproject[match.end():]
    )
else:
    if "[tool.ruff]" in pyproject:
        pyproject = pyproject.replace(
            "[tool.ruff]",
            xpu_index_block + "\n[tool.ruff]",
            1
        )
    else:
        pyproject += "\n" + xpu_index_block

# CONFIG.PY

config = re.sub(
    r'device:\s*Literal\[[^\]]+\]\s*=\s*"cpu"',
    'device: Literal["cpu", "cuda", "xpu"] = "cpu"',
    config,
    count=1
)

config = config.replace(
    "- device: Device for model inference. 'cuda' requires a GPU with CUDA support.",
    "- device: Device for model inference. 'cuda' uses NVIDIA CUDA, 'xpu' uses Intel GPU."
)


if 'Literal["cpu", "cuda", "xpu"]' not in config:
    raise RuntimeError("XPU konnte in config.py nicht eingetragen werden.")

# GUI: XPU VARIABLE

if "self._xpu_available" not in gui:

    old = "        self._cuda_available: bool | None = None"

    if old not in gui:
        raise RuntimeError("_cuda_available nicht gefunden.")

    gui = gui.replace(
        old,
        old + "\n        self._xpu_available: bool | None = None",
        1
    )

# GUI: DEVICE PROPERTY

device_pattern = re.compile(
    r'(?ms)    @property\n'
    r'    def device\(self\) -> str:.*?'
    r'(?=    @property\n    def _is_crop_enabled)'
)

device_code = '''    @property
    def device(self) -> str:
        """Get the selected compute device."""
        if self.gpu_checkbox.isChecked():

            if self._cuda_available:
                return "cuda"

            if self._xpu_available:
                return "xpu"

        return "cpu"

'''

gui, count = device_pattern.subn(
    device_code,
    gui,
    count=1
)

if count == 0:
    raise RuntimeError("device property nicht gefunden.")

# GUI: GPU INITIALIZATION

init_pattern = re.compile(
    r'(?ms)    def _initialize_after_display\(self\) -> None:.*?'
    r'(?=    def _create_ui_layout\(self\) -> None:)'
)

init_code = '''    def _initialize_after_display(self) -> None:
        """Initialize GPU check and load config after GUI is displayed."""

        self.status_updated.emit(
            "Checking GPU availability and loading config..."
        )

        QApplication.processEvents()

        try:
            import torch

            self._cuda_available = torch.cuda.is_available()

            self._xpu_available = (
                hasattr(torch, "xpu")
                and torch.xpu.is_available()
            )

            logger.info(
                "GPU/CUDA %s",
                "available" if self._cuda_available else "not available"
            )

            logger.info(
                "GPU/Intel XPU %s",
                "available" if self._xpu_available else "not available"
            )

        except ImportError:

            self._cuda_available = False
            self._xpu_available = False

            logger.info(
                "PyTorch not installed, GPU disabled"
            )

        gpu_available = bool(
            self._cuda_available
            or self._xpu_available
        )

        self.gpu_checkbox.setEnabled(
            gpu_available
        )

        self._load_config(
            self.config_active
        )

        status = (
            "GPU available"
            if gpu_available
            else "GPU not available"
        )

        self.status_updated.emit(
            f"Ready - {status}"
        )

        self.source_path_param.value_changed.connect(
            self._on_source_path_change
        )

        self.output_path_param.value_changed.connect(
            self._on_output_path_change
        )

'''

gui, count = init_pattern.subn(
    init_code,
    gui,
    count=1
)

if count == 0:
    raise RuntimeError("_initialize_after_display nicht gefunden.")

# GUI: GPU CHECKBOX

gui = gui.replace(
    'self.gpu_checkbox.setToolTip("Enable GPU (Requires NVIDIA GPU + CUDA)")',
    'self.gpu_checkbox.setToolTip("Enable GPU (NVIDIA CUDA or Intel XPU)")'
)

gui = gui.replace(
    "self.gpu_checkbox.setEnabled(False)  # will be updated after CUDA check",
    "self.gpu_checkbox.setEnabled(False)  # updated after GPU check"
)

# GUI: RE-ENABLE GPU AFTER UI UNLOCK

gui = gui.replace(
'''        if self._cuda_available:
            self.gpu_checkbox.setEnabled(True)''',

'''        if self._cuda_available or self._xpu_available:
            self.gpu_checkbox.setEnabled(True)'''
)

# GUI: CONFIG DEVICE HANDLING

config_device_pattern = re.compile(
    r'(?ms)        config_device = self\._config_updates\.get'
    r'\("device", "cpu"\).*?'
    r'(?=\n        # Populate parameter forms)'
)

config_device_code = '''        config_device = self._config_updates.get("device", "cpu")

        if (
            self._cuda_available is not None
            and self._xpu_available is not None
        ):

            if (
                config_device == "cuda"
                and not self._cuda_available
            ):

                logger.warning(
                    "Config specifies 'cuda' but CUDA is not available"
                )

                QMessageBox.warning(
                    self,
                    "GPU/CUDA Not Available",
                    "Configuration is set to use CUDA, "
                    "but CUDA is not available.\\n\\n"
                    "Device has been changed to CPU."
                )

                self._config_updates["device"] = "cpu"
                config_device = "cpu"

            elif (
                config_device == "xpu"
                and not self._xpu_available
            ):

                logger.warning(
                    "Config specifies 'xpu' but Intel XPU is not available"
                )

                QMessageBox.warning(
                    self,
                    "Intel XPU Not Available",
                    "Configuration is set to use Intel XPU, "
                    "but XPU is not available.\\n\\n"
                    "Device has been changed to CPU."
                )

                self._config_updates["device"] = "cpu"
                config_device = "cpu"

            elif (
                config_device == "cpu"
                and (
                    self._cuda_available
                    or self._xpu_available
                )
            ):

                gpu_type = (
                    "CUDA"
                    if self._cuda_available
                    else "Intel XPU"
                )

                logger.info(
                    "%s GPU is available but config uses CPU",
                    gpu_type
                )

                QMessageBox.information(
                    self,
                    "GPU Available",
                    f"{gpu_type} GPU detected!\\n\\n"
                    "Your configuration currently uses CPU.\\n"
                    "Enable GPU acceleration to use the GPU."
                )

        self.gpu_checkbox.setChecked(
            config_device in ("cuda", "xpu")
        )
'''

gui, count = config_device_pattern.subn(
    lambda m: config_device_code,
    gui,
    count=1
)

if count == 0:
    raise RuntimeError("Config-device-Block nicht gefunden.")

# VALIDATE BEFORE WRITING

# TOML syntax
tomllib.loads(pyproject)

# Python syntax
compile(
    config,
    str(CONFIG),
    "exec"
)

compile(
    gui,
    str(GUI),
    "exec"
)

print("Syntaxprüfung erfolgreich.")

# BACKUP

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

backup = ROOT / (
    f"xpu_backup_{timestamp}"
)

for file in (
    PYPROJECT,
    CONFIG,
    GUI
):

    relative = file.relative_to(
        ROOT
    )

    destination = (
        backup
        / relative
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        file,
        destination
    )


print()
print("Backup erstellt:")
print(backup)

# WRITE CHANGES

PYPROJECT.write_text(
    pyproject,
    encoding="utf-8"
)

CONFIG.write_text(
    config,
    encoding="utf-8"
)

GUI.write_text(
    gui,
    encoding="utf-8"
)


print()
print("=" * 70)
print("XPU PATCH ERFOLGREICH")
print("=" * 70)

# UV SYNC AUTOMATICALLY

print()
print("Installiere XPU-Abhängigkeiten...")
print()

result = subprocess.run(
    [
        "uv",
        "sync",
        "--extra",
        "xpu"
    ],
    cwd=ROOT
)

if result.returncode != 0:

    print()
    print("=" * 70)
    print("UV SYNC FEHLGESCHLAGEN")
    print("=" * 70)
    print()
    print("Die Dateien wurden gepatcht.")
    print("Backup:")
    print(backup)

    raise SystemExit(
        result.returncode
    )

# TEST XPU

print()
print("=" * 70)
print("TESTE INTEL XPU")
print("=" * 70)
print()

test_code = r'''
import torch

print("PyTorch:", torch.__version__)
print("XPU available:", torch.xpu.is_available())

if torch.xpu.is_available():
    print("Intel GPU:", torch.xpu.get_device_name(0))
'''

result = subprocess.run(
    [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-c",
        test_code
    ],
    cwd=ROOT
)

# FINISHED

print()
print("=" * 70)

if result.returncode == 0:
    print("FERTIG")
    print()
    print("Starte die GUI jetzt mit:")
    print()
    print("uv run --no-sync gui")
else:
    print("XPU-TEST FEHLGESCHLAGEN")

print("=" * 70)