# -*- coding: utf-8 -*-

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter


_thread_local = threading.local()


def load_labels(path: Path) -> list[str]:
    labels = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            parts = line.split()

            if len(parts) >= 2 and parts[0].isdigit():
                labels.append(" ".join(parts[1:]))
            else:
                labels.append(line)

    return labels


def _get_runtime(model_path: str):

    model_path = Path(model_path)
    labels_path = model_path.with_name("labels.txt")

    current_model = getattr(
        _thread_local,
        "model_path",
        None
    )

    if current_model != str(model_path):

        interpreter = Interpreter(
            model_path=str(model_path),
            num_threads=1
        )

        interpreter.allocate_tensors()

        _thread_local.model_path = str(model_path)
        _thread_local.interpreter = interpreter
        _thread_local.input_details = interpreter.get_input_details()
        _thread_local.output_details = interpreter.get_output_details()
        _thread_local.labels = load_labels(labels_path)

    return (
        _thread_local.interpreter,
        _thread_local.input_details,
        _thread_local.output_details,
        _thread_local.labels
    )


def classify_crop(
    crop_bgr,
    model_path
):

    (
        interpreter,
        input_details,
        output_details,
        labels
    ) = _get_runtime(model_path)

    input_shape = input_details[0]["shape"]

    height = int(input_shape[1])
    width = int(input_shape[2])

    input_dtype = input_details[0]["dtype"]

    img = cv2.cvtColor(
        crop_bgr,
        cv2.COLOR_BGR2RGB
    )

    img = cv2.resize(
        img,
        (width, height)
    )

    input_data = np.expand_dims(
        img,
        axis=0
    ).astype(np.float32)

    input_scale, input_zero_point = (
        input_details[0]["quantization"]
    )

    if input_dtype == np.float32:

        input_data /= 255.0

    else:

        if input_scale < 0.01:
            input_data /= 255.0

        input_data = (
            input_data / input_scale
            + input_zero_point
        )

        input_data = np.round(
            input_data
        )

        info = np.iinfo(input_dtype)

        input_data = np.clip(
            input_data,
            info.min,
            info.max
        ).astype(input_dtype)

    interpreter.set_tensor(
        input_details[0]["index"],
        input_data
    )

    interpreter.invoke()

    output_data = interpreter.get_tensor(
        output_details[0]["index"]
    )[0]

    if output_details[0]["dtype"] != np.float32:

        scale, zero_point = (
            output_details[0]["quantization"]
        )

        output_data = scale * (
            output_data.astype(np.float32)
            - zero_point
        )

    scores = output_data.astype(float)

    best_index = int(
        np.argmax(scores)
    )

    best_label = labels[best_index]
    best_score = float(scores[best_index])

    return best_label, best_score


def reject_crop(
    crop_bgr,
    model_path,
    threshold
):

    label, score = classify_crop(
        crop_bgr,
        model_path
    )

    normalized_label = (
        label
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )

    reject = (
        normalized_label == "no-insect"
        and score >= threshold
    )

    return reject, label, score