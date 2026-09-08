"""Export a verified YOLO26 checkpoint using the manifest-pinned build toolchain."""

from __future__ import annotations

import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    manifest_path, checkpoint_path, output_path = map(Path, sys.argv[1:])
    artifact = json.loads(manifest_path.read_text())["artifacts"][0]
    export = artifact["export"]
    if f"{sys.version_info.major}.{sys.version_info.minor}" != export["python"]:
        raise ValueError("export Python version does not match the manifest")
    for package, expected in export["packages"].items():
        if version(package).removesuffix("+cpu") != expected:
            raise ValueError(
                f"export package version does not match the manifest: {package}"
            )
    checkpoint = artifact["source_checkpoint"]
    with checkpoint_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if (
        checkpoint_path.stat().st_size != checkpoint["size_bytes"]
        or digest != checkpoint["sha256"]
    ):
        raise ValueError("source checkpoint does not match the manifest")
    if export["metadata"] != "remove_all":
        raise ValueError("unsupported ONNX metadata canonicalization")

    import onnx
    from ultralytics import YOLO

    result = YOLO(str(checkpoint_path)).export(
        format="onnx",
        device=export["device"],
        imgsz=export["imgsz"],
        batch=export["batch"],
        half=export["half"],
        dynamic=export["dynamic"],
        simplify=export["simplify"],
        opset=export["opset"],
        nms=export["nms"],
        end2end=export["end2end"],
    )
    model = onnx.load(result)
    del model.metadata_props[:]
    onnx.checker.check_model(model)
    onnx.save(model, output_path)


if __name__ == "__main__":
    main()
