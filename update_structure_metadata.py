# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path


# =====================================================
# PROJECT
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parent

IMAGE_PROCESSOR = (
    PROJECT_ROOT
    / "src"
    / "insectdetect_post"
    / "image_processor.py"
)

PIPELINE_RUNNER = (
    PROJECT_ROOT
    / "src"
    / "insectdetect_post"
    / "pipeline_runner.py"
)


# =====================================================
# HELPERS
# =====================================================

def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def check_syntax(text: str, filename: str) -> None:
    compile(text, filename, "exec")


def make_backup() -> Path:

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_root = (
        PROJECT_ROOT
        / f"structure_metadata_backup_{timestamp}"
    )

    for path in [
        IMAGE_PROCESSOR,
        PIPELINE_RUNNER,
    ]:

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
# REMOVE OLD LOCAL METADATA METHOD
# =====================================================

def remove_old_metadata_method(
    text: str
) -> str:

    lines = text.splitlines(
        keepends=True
    )

    result = []

    i = 0

    while i < len(lines):

        line = lines[i]

        if re.match(
            r"^    def _write_local_metadata_copies\s*\(",
            line
        ):

            print(
                "Removing old "
                "_write_local_metadata_copies()..."
            )

            i += 1

            while i < len(lines):

                # next class method
                if re.match(
                    r"^    def "
                    r"[A-Za-z_][A-Za-z0-9_]*\s*\(",
                    lines[i]
                ):
                    break

                i += 1

            continue

        result.append(line)

        i += 1

    return "".join(result)


# =====================================================
# REMOVE OLD FUNCTION CALL
# =====================================================

def remove_old_metadata_calls(
    text: str
) -> str:

    lines = text.splitlines(
        keepends=True
    )

    result = []

    i = 0

    while i < len(lines):

        line = lines[i]

        if (
            "self._write_local_metadata_copies("
            in line
            and
            "def _write_local_metadata_copies"
            not in line
        ):

            print(
                "Removing old call to "
                "_write_local_metadata_copies()..."
            )

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

        result.append(line)

        i += 1

    return "".join(result)


# =====================================================
# PATCH IMAGE PROCESSOR
# =====================================================

def patch_image_processor(
    text: str
) -> str:

    print()
    print(
        "Patching image_processor.py..."
    )

    # -------------------------------------------------
    # already patched?
    # -------------------------------------------------

    if (
        "relative_folder = "
        "img_path.parent.relative_to(context.root_path)"
        in text
    ):

        print(
            "  OK: crop folder structure "
            "already patched"
        )

        return text

    # -------------------------------------------------
    # Find crop filename
    # -------------------------------------------------

    lines = text.splitlines(
        keepends=True
    )

    crop_index = None
    generate_index = None

    for i, line in enumerate(lines):

        if (
            "crop_filename"
            in line
            and
            "track_id"
            in line
        ):

            crop_index = i

            for j in range(
                i + 1,
                min(
                    i + 20,
                    len(lines)
                )
            ):

                if (
                    "# Generate crop"
                    in lines[j]
                ):
                    generate_index = j
                    break

            if generate_index is not None:
                break

    if (
        crop_index is None
        or generate_index is None
    ):

        raise RuntimeError(
            "Could not find crop output block "
            "in image_processor.py"
        )

    line = lines[crop_index]

    indent = line[
        :len(line) - len(line.lstrip())
    ]

    new_block = [
        "\n",

        f"{indent}"
        "# Preserve original folder structure\n",

        f"{indent}"
        "relative_folder = "
        "img_path.parent.relative_to("
        "context.root_path"
        ")\n",

        "\n",

        f"{indent}"
        "out_path = (\n",

        f"{indent}"
        "    crops_dir\n",

        f"{indent}"
        "    / relative_folder\n",

        f"{indent}"
        "    / str(label)\n",

        f"{indent}"
        "    / crop_filename\n",

        f"{indent}"
        ")\n",

        "\n",

        f"{indent}"
        "out_path.parent.mkdir(\n",

        f"{indent}"
        "    parents=True,\n",

        f"{indent}"
        "    exist_ok=True\n",

        f"{indent}"
        ")\n",

        "\n",
    ]

    lines = (
        lines[:crop_index + 1]
        + new_block
        + lines[generate_index:]
    )

    text = "".join(lines)

    print(
        "  OK: crop folder structure added"
    )

    return text


# =====================================================
# PATCH PIPELINE RUNNER
# =====================================================

def patch_pipeline_runner(
    text: str
) -> str:

    print()
    print(
        "Patching pipeline_runner.py..."
    )

    # =================================================
    # REMOVE OLD PATCHES
    # =================================================

    text = remove_old_metadata_method(
        text
    )

    text = remove_old_metadata_calls(
        text
    )

    # =================================================
    # ADD CANDIDATES PATH VARIABLE
    # =================================================

    if (
        "self._candidates_metadata_path"
        not in text
    ):

        old = (
            "        self._classified_metadata_path: "
            "Path | None = None\n"
            "        self._final_metadata_path_value: "
            "Path | None = None\n"
        )

        new = (
            "        self._classified_metadata_path: "
            "Path | None = None\n"
            "        self._candidates_metadata_path: "
            "Path | None = None\n"
            "        self._final_metadata_path_value: "
            "Path | None = None\n"
        )

        if old not in text:

            raise RuntimeError(
                "Could not find metadata "
                "path definitions."
            )

        text = text.replace(
            old,
            new,
            1
        )

    print(
        "  OK: candidates path available"
    )

    # =================================================
    # STORE CANDIDATES PATH
    # =================================================

    if (
        "self._candidates_metadata_path = "
        "result[\"candidates_path\"]"
        not in text
        and
        "self._candidates_metadata_path = "
        "result['candidates_path']"
        not in text
    ):

        patterns = [

            (
                "        self._final_metadata_path_value "
                "= result['final_path']\n",
                "        self._candidates_metadata_path "
                "= result['candidates_path']\n"
                "        self._final_metadata_path_value "
                "= result['final_path']\n"
            ),

            (
                '        self._final_metadata_path_value '
                '= result["final_path"]\n',
                '        self._candidates_metadata_path '
                '= result["candidates_path"]\n'
                '        self._final_metadata_path_value '
                '= result["final_path"]\n'
            ),
        ]

        replaced = False

        for old, new in patterns:

            if old in text:

                text = text.replace(
                    old,
                    new,
                    1
                )

                replaced = True
                break

        if not replaced:

            raise RuntimeError(
                "Could not find "
                "_final_metadata_path_value assignment."
            )

    print(
        "  OK: candidates path stored"
    )

    # =================================================
    # LOCAL METADATA METHOD
    # =================================================

    method = '''
    def _write_local_metadata_copies(self) -> None:
        """Write the four global metadata CSVs into each source folder."""

        global_csvs = [
            self._merged_metadata_path,
            self._classified_metadata_path,
            self._candidates_metadata_path,
            self._final_metadata_path_value,
        ]

        global_csvs = [
            path
            for path in global_csvs
            if path is not None and path.exists()
        ]

        if not global_csvs:
            logger.warning(
                "No metadata CSVs available "
                "for local copies"
            )
            return

        folder_key_frames = {}

        # =============================================
        # READ ORIGINAL METADATA
        # =============================================

        for meta_path in self.context.metadata_files:

            try:
                source_df = pl.read_csv(
                    meta_path,
                    glob=False
                )

            except Exception:
                logger.exception(
                    "Could not read source metadata: %s",
                    meta_path
                )
                continue

            if (
                "device_id" not in source_df.columns
                or
                "session_id" not in source_df.columns
            ):
                logger.warning(
                    "device_id/session_id missing: %s",
                    meta_path
                )
                continue

            # -----------------------------------------
            # IMPORTANT:
            # use identical datatypes for joins
            # -----------------------------------------

            source_df = source_df.with_columns(
                [
                    pl.col("device_id").cast(
                        pl.Utf8,
                        strict=False
                    ),
                    pl.col("session_id").cast(
                        pl.Utf8,
                        strict=False
                    ),
                ]
            )

            relative_folder = (
                meta_path.parent.relative_to(
                    self.source_dir
                )
            )

            keys = (
                source_df
                .select(
                    [
                        "device_id",
                        "session_id",
                    ]
                )
                .drop_nulls()
                .unique()
            )

            if len(keys) == 0:
                continue

            folder_key_frames.setdefault(
                relative_folder,
                []
            ).append(keys)

        # =============================================
        # WRITE LOCAL CSV FILES
        # =============================================

        for (
            relative_folder,
            key_frames
        ) in folder_key_frames.items():

            keys = pl.concat(
                key_frames,
                how="vertical"
            ).unique()

            target_folder = (
                self.layout.crops_dir
                / relative_folder
            )

            target_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            for global_csv in global_csvs:

                try:

                    df = pl.read_csv(
                        global_csv,
                        glob=False
                    )

                    if (
                        "device_id" not in df.columns
                        or
                        "session_id" not in df.columns
                    ):
                        continue

                    # ---------------------------------
                    # SAME TYPES AS SOURCE KEYS
                    # ---------------------------------

                    df = df.with_columns(
                        [
                            pl.col("device_id").cast(
                                pl.Utf8,
                                strict=False
                            ),
                            pl.col("session_id").cast(
                                pl.Utf8,
                                strict=False
                            ),
                        ]
                    )

                    local_df = df.join(
                        keys,
                        on=[
                            "device_id",
                            "session_id",
                        ],
                        how="semi"
                    )

                    local_path = (
                        target_folder
                        / global_csv.name
                    )

                    local_df.write_csv(
                        local_path
                    )

                except Exception:

                    logger.exception(
                        "Could not create local metadata "
                        "copy from %s for %s",
                        global_csv,
                        target_folder
                    )

            logger.info(
                "Saved local metadata CSVs: %s",
                target_folder
            )

'''

    # -------------------------------------------------
    # Insert before another known method
    # -------------------------------------------------

    marker = (
        "    def _sort_crops_wrapper("
    )

    index = text.find(marker)

    if index == -1:

        raise RuntimeError(
            "Could not find insertion point "
            "_sort_crops_wrapper()."
        )

    text = (
        text[:index]
        + method
        + "\n"
        + text[index:]
    )

    print(
        "  OK: local metadata method added"
    )

    # =================================================
    # CALL LOCAL METADATA AFTER METADATA PROCESSING
    # =================================================

    if (
        "self._write_local_metadata_copies()"
        not in text
    ):

        marker = (
            '        logger.info("  - removed %d '
            '(below weighted prediction probability threshold)", '
            "result['pred_tracks_removed'])\n"
            )

        if marker not in text:
            raise RuntimeError(
                "Could not find end of _process_metadata()."
                )

        replacement = (
            marker
            + "\n"
            + "        self._write_local_metadata_copies()\n"
            )

        text = text.replace(
            marker,
            replacement,
            1
            )

    print(
        "  OK: local metadata call added to _process_metadata"
        )

    return text


# =====================================================
# MAIN
# =====================================================

def main():

    print("=" * 60)
    print(
        "UPDATE: folder structure + local metadata"
    )
    print("=" * 60)

    # =================================================
    # CHECK FILES
    # =================================================

    if not IMAGE_PROCESSOR.exists():
        raise FileNotFoundError(
            IMAGE_PROCESSOR
        )

    if not PIPELINE_RUNNER.exists():
        raise FileNotFoundError(
            PIPELINE_RUNNER
        )

    # =================================================
    # BACKUP
    # =================================================

    backup = make_backup()

    print()
    print("Backup created:")
    print(backup)

    # =================================================
    # READ
    # =================================================

    image_text = read_file(
        IMAGE_PROCESSOR
    )

    runner_text = read_file(
        PIPELINE_RUNNER
    )

    # =================================================
    # PATCH
    # =================================================

    image_text = patch_image_processor(
        image_text
    )

    runner_text = patch_pipeline_runner(
        runner_text
    )

    # =================================================
    # SYNTAX CHECK
    # =================================================

    print()
    print("Checking syntax...")

    check_syntax(
        image_text,
        str(IMAGE_PROCESSOR)
    )

    check_syntax(
        runner_text,
        str(PIPELINE_RUNNER)
    )

    print(
        "  OK: Python syntax valid"
    )

    # =================================================
    # WRITE
    # =================================================

    write_file(
        IMAGE_PROCESSOR,
        image_text
    )

    write_file(
        PIPELINE_RUNNER,
        runner_text
    )

    # =================================================
    # DONE
    # =================================================

    print()
    print("=" * 60)
    print("UPDATE COMPLETE")
    print("=" * 60)

    print()
    print("Changes:")
    print(
        "1. Crop folder structure preserved"
    )
    print(
        "2. Four metadata CSVs remain global"
    )
    print(
        "3. Four metadata CSVs also saved locally"
    )
    print(
        "4. device_id/session_id join fixed"
    )
    print(
        "5. Old candidates_path/final_path call removed"
    )

    print()
    print("Backup:")
    print(backup)

    print()
    print("Start GUI with:")
    print(
        "uv run --no-sync gui"
    )


if __name__ == "__main__":
    main()