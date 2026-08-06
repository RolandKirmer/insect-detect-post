# Insect Detect Post - Post-processing of camera trap data

<img src="https://raw.githubusercontent.com/maxsitt/insect-detect-docs/main/docs/assets/logo.png" width="540" alt="Insect Detect logo">

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://choosealicense.com/licenses/agpl-3.0/)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![DOI Zenodo](https://zenodo.org/badge/DOI/10.5281/zenodo.21822140.svg)](https://doi.org/10.5281/zenodo.21822140)

This repository contains GUI-based software for post-processing of data captured
with the [Insect Detect](https://maxsitt.github.io/insect-detect-docs/) camera trap.
It turns the images and metadata captured by the camera trap into cropped,
classified and filtered results ready for analysis, by combining image processing,
AI-based classification and metadata aggregation into a single configurable pipeline.

## Features

- **Image processing** - crop individual detections from full frames (square or
  original aspect ratio) and/or draw bounding box + metadata overlays.
- **Classification** - classify cropped detections with either the
  [BioCLIP 2](https://imageomics.github.io/bioclip-2/) foundation model or a custom
  [Ultralytics](https://docs.ultralytics.com/tasks/classify) YOLO classification model.
- **Crop sorting** - automatically move cropped detections into subdirectories, either
  by each individual prediction or by the final prediction of the whole track.
- **Metadata processing** - aggregate image-level predictions into per-track results
  with weighted probabilities. Filter tracks by detection confidence, duration, and
  prediction probability.
- **Config profiles** - save, switch between and reuse multiple named configuration
  files (`.yaml`) for different processing setups.
- **Desktop GUI** - configure and run the pipeline with a PySide6-based interface
  that inspects the source dataset, reports live progress and supports cancelling
  a running pipeline at any time.

---

## Installation

### Prerequisites

> [!NOTE]
> Python does not need to be installed separately - `uv` automatically downloads
> and manages the required Python version for you when running `uv sync`.

**Install [uv](https://docs.astral.sh/uv/getting-started/installation/):**

Windows:

``` shell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Linux and macOS:

``` bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install [git](https://git-scm.com/install/):**

Windows:

``` shell
winget install --id Git.Git -e --source winget
```

Linux (Debian/Ubuntu):

``` bash
apt-get install git
```

macOS:

``` bash
brew install git
```

### Install post-processing software

Clone the `insect-detect-post` repository:

``` shell
git clone https://github.com/maxsitt/insect-detect-post
```

Open a Terminal in your `insect-detect-post` directory or change directory
(use full path after `cd`):

``` shell
cd insect-detect-post
```

There are three installation options:

1. CPU-only version:

    ``` shell
    uv sync --extra cpu
    ```

2. GPU with CUDA 13 support:

    ``` shell
    uv sync --extra cuda132
    ```

3. Legacy GPU with CUDA 12 support:

    ``` shell
    uv sync --extra cuda126
    ```

> [!NOTE]
> The `cuda132`/`cuda126` options require a matching NVIDIA GPU driver.
> Run `nvidia-smi` and check the reported `CUDA Version` (top right)
> to see the maximum CUDA version your installed driver supports.

---

## Usage

Start the GUI by running:

``` shell
uv run --no-sync gui
```

> [!IMPORTANT]
> Always include `--no-sync`. Running `uv run gui` without it re-syncs the environment
> without your chosen extra, which uninstalls PyTorch and the ONNX runtime.

1. **Select a source directory** - select a directory that contains images and
   metadata captured with the [`insect-detect`](https://github.com/maxsitt/insect-detect)
   software. Subdirectories are scanned recursively, so per-device/per-session folder
   structures are supported.
2. **Select an output directory** - all processed results are written here.
3. **Configure the pipeline** - enable/adjust the settings described in
   [Settings](#settings) below.
4. **Run the pipeline** - progress and log messages are shown live, and a run can
   be cancelled at any time.

Models and filter files (e.g. classification models, GBIF country filters) referenced
in the configuration are downloaded automatically on first use from the release assets.

### Configuration profiles

Configuration files are stored as `.yaml` files in the `configs/` directory. The
active profile is tracked in `configs/config_selector.yaml` and can be switched,
created or updated from the GUI, so different processing setups (e.g. per project
or per classifier) can be saved and reused without editing YAML by hand.

---

## Output

Each run creates a timestamped directory under `data_processed/` in your output directory:

``` text
data_processed/
└── 2026-08-05_14-30-12_<source>_processed/
    ├── 2026-08-05_14-30-12_<config>.json  # config snapshot for this run
    ├── 2026-08-05_14-30-12_run.log        # full log output
    ├── 2026-08-05_14-30-12_stats.json     # per-step durations
    ├── metadata/
    │   ├── <source>_metadata_merged.csv               # all source metadata, harmonized
    │   ├── <source>_metadata_merged_classified.csv    # + per-image predictions
    │   ├── ..._classified_candidates.csv              # per-track candidate predictions
    │   └── ..._classified_final.csv                   # one row per track (best prediction)
    └── images/
        ├── crops/      # cropped detections, optionally sorted into prediction subdirectories
        └── overlays/   # copies of full frames with bounding boxes + metadata drawn on
```

`..._classified_final.csv` is the file to use for analysis - one row per tracking ID with
its final prediction, weighted probability, duration and (optionally) estimated size.

---

## Settings

All settings are validated with [Pydantic](https://pydantic.dev/docs/) - out-of-range
numeric values are automatically clamped to their allowed bounds and a warning is
logged. `bioclip` and `ultralytics` are mutually exclusive (enable only one
classifier), as are `sort_crops` and `sort_tracks`. Crop sorting and metadata
processing both consume classification results, so they require one of the two
classifiers to be enabled. `metadata.filter_tracks.min_dur_s` must be less than
`max_dur_s`.

### General

| Setting       | Type / Options   | Default | Description                                                               |
|---------------|------------------|---------|---------------------------------------------------------------------------|
| `source_path` | `string \| null` | `null`  | Full path to the source directory containing images and metadata.         |
| `output_path` | `string \| null` | `null`  | Full path to the output directory where all results will be saved.        |
| `device`      | `cpu`, `cuda`    | `cpu`   | Device used for model inference. `cuda` requires a GPU with CUDA support. |

### Image Processing

Post-processing settings applied to full-frame images.

| Setting                      | Type / Options       | Default  | Description                                                                                                                                      |
|------------------------------|----------------------|----------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `processing.crop.enabled`    | `bool`               | `true`   | Save individual detections as separate crop files. Detections without a full image (crop-only datasets) are copied as-is.                        |
| `processing.crop.method`     | `square`, `original` | `square` | Crop method: `square` crops to a square bounding box, which can improve classification; `original` keeps the original bounding box aspect ratio. |
| `processing.overlay.enabled` | `bool`               | `false`  | Draw bounding boxes and metadata overlays on full images and save them as copies.                                                                |

### Classification

Classification settings applied to cropped detections.

| Setting                                            | Type / Options                                                      | Default                                          | Description                                                                                                                 |
|----------------------------------------------------|---------------------------------------------------------------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| `classification.bioclip.enabled`                   | `bool`                                                              | `true`                                           | Enable classification with the BioCLIP 2 model (via `pybioclip` package).                                                   |
| `classification.bioclip.batch_size`                | `int` (1-256)                                                       | `16`                                             | Batch size used for BioCLIP inference.                                                                                      |
| `classification.bioclip.rank`                      | `kingdom`, `phylum`, `class`, `order`, `family`, `genus`, `species` | `species`                                        | Predict to selected taxonomic level. For ranks above species, species-level probabilities are summed up to the target rank. |
| `classification.bioclip.filter_arthropods.enabled` | `bool`                                                              | `true`                                           | Restrict BioCLIP predictions to Arthropoda (or subtaxa) and/or GBIF occurrence in selected country.                         |
| `classification.bioclip.filter_arthropods.taxon`   | `Arthropoda`, `Insecta`                                             | `Arthropoda`                                     | Taxon that BioCLIP predictions are restricted to (currently only Arthropoda or Insecta are supported).                      |
| `classification.bioclip.filter_arthropods.country` | country code, or `all`                                              | `all`                                            | Country that BioCLIP Arthropoda predictions are restricted to (based on GBIF occurrence records). `all` for no restriction. |
| `classification.ultralytics.enabled`               | `bool`                                                              | `false`                                          | Enable classification with a custom Ultralytics YOLO classification model.                                                  |
| `classification.ultralytics.batch_size`            | `int` (1-256)                                                       | `16`                                             | Batch size used for Ultralytics inference.                                                                                  |
| `classification.ultralytics.model`                 | `string`                                                            | `platform_insect-detect_yolo26s-cls_v1-0-0.onnx` | Filename of the Ultralytics classification model, downloaded automatically from the models registry on first use.           |
| `classification.sort_crops.enabled`                | `bool`                                                              | `false`                                          | Move cropped detections into subdirectories based on the individual prediction.                                             |
| `classification.sort_tracks.enabled`               | `bool`                                                              | `true`                                           | Move all crops belonging to a track into one subdirectory based on the track's final prediction.                            |

#### Filter files

Country filters are built on first use by querying the GBIF occurrence API (this can
take a few minutes) and are then cached in `filters/`. The scripts that regenerate the
underlying reference data (`filters/resolve_gbif_country_codes.py`,
`filters/resolve_tol_gbif_species.py`) only need to be re-run when GBIF's country
enumeration or the BioCLIP Tree of Life version changes.

### Metadata Processing

Metadata processing settings applied to the final results.

| Setting                                         | Type / Options  | Default | Description                                                                           |
|-------------------------------------------------|-----------------|---------|---------------------------------------------------------------------------------------|
| `metadata.filter_tracks.enabled`                | `bool`          | `false` | Filter tracking IDs based on mean detection confidence and total tracking duration.   |
| `metadata.filter_tracks.min_det_conf`           | `float` (0-1)   | `0.2`   | Minimum mean detection confidence required to keep a tracking ID.                     |
| `metadata.filter_tracks.min_dur_s`              | `int` (0-600)   | `2`     | Minimum total tracking duration (seconds) required to keep a tracking ID.             |
| `metadata.filter_tracks.max_dur_s`              | `int` (1-21600) | `3600`  | Maximum total tracking duration (seconds) allowed to keep a tracking ID.              |
| `metadata.filter_predictions.enabled`           | `bool`          | `false` | Filter tracking IDs based on the weighted mean probability of the final prediction.   |
| `metadata.filter_predictions.min_prob_weighted` | `float` (0-1)   | `0.2`   | Minimum weighted mean probability required to keep a tracking ID.                     |
| `metadata.estimate_size.enabled`                | `bool`          | `false` | Estimate physical size based on bounding box dimensions and frame size (millimeters). |
| `metadata.estimate_size.frame_width_mm`         | `int` (10-1000) | `230`   | Physical width of the camera frame (millimeters).                                     |
| `metadata.estimate_size.frame_height_mm`        | `int` (10-1000) | `130`   | Physical height of the camera frame (millimeters).                                    |

---

## License

This repository is licensed under the terms of the GNU Affero General Public
License v3.0 ([GNU AGPLv3](https://choosealicense.com/licenses/agpl-3.0/)).
