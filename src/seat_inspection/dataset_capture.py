from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
from media_inputs import open_frame_stream

from .config import CollectionConfig

COCO_PERSON_KEYPOINT_SHAPE = [17, 3]
COCO_PERSON_FLIP_IDX = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]


@dataclass(slots=True)
class DatasetCaptureSummary:
    """数据采集完成后的摘要统计。"""

    saved_images: int
    train_images: int
    val_images: int
    skipped_frames: int
    dataset_yaml_path: str
    output_dir: str


def capture_pose_dataset(config: CollectionConfig) -> DatasetCaptureSummary:
    """从视频或 MVS 相机采集图像并自动生成 YOLO pose 数据集。"""
    from ultralytics import YOLO

    _validate_collection_config(config)
    dataset_root = Path(config.output_dir)
    dataset_yaml_path = Path(config.dataset_yaml_path or dataset_root / "dataset.yaml")
    _prepare_output_dir(dataset_root, overwrite=config.overwrite)

    model = YOLO(config.pose_model_path)
    stream = open_frame_stream(config.source)
    if not stream.is_opened():
        raise ValueError(f"Unable to open collection source: {config.source}")

    rng = random.Random(config.random_seed)  # 固定随机种子，便于复现 train/val 划分
    frame_index = 0
    saved_images = 0
    skipped_frames = 0
    train_images = 0
    val_images = 0
    manifest: list[dict[str, object]] = []  # 记录每张图像来源，方便追溯问题样本

    try:
        while saved_images < config.max_images:
            media_frame = stream.read_frame()
            if media_frame is None:
                break

            frame_index = media_frame.frame_index
            if frame_index % config.save_every_n_frames != 0:
                continue

            result = model.predict(
                media_frame.image,
                conf=config.confidence,
                iou=config.iou,
                device=config.device,
                verbose=False,
            )[0]
            if not _has_pose_instances(result):
                skipped_frames += 1
                continue

            split = _choose_split(rng, config.train_split, train_images, val_images)
            saved_images += 1
            image_stem = f"frame_{saved_images:06d}"
            image_path = dataset_root / "images" / split / f"{image_stem}.jpg"
            label_path = dataset_root / "labels" / split / f"{image_stem}.txt"

            cv2.imwrite(str(image_path), media_frame.image)
            if label_path.exists():
                label_path.unlink()
            result.save_txt(label_path, save_conf=False)

            if not label_path.exists():
                image_path.unlink(missing_ok=True)
                saved_images -= 1
                skipped_frames += 1
                continue

            if split == "train":
                train_images += 1
            else:
                val_images += 1

            manifest.append(
                {
                    "image": str(image_path),
                    "label": str(label_path),
                    "split": split,
                    "source_frame_index": frame_index,
                }
            )
    finally:
        stream.release()

    if saved_images == 0:
        raise ValueError("No labeled pose samples were captured; dataset was not created")

    train_images, val_images = _ensure_non_empty_splits(dataset_root, train_images, val_images, manifest)
    _write_dataset_yaml(dataset_root, dataset_yaml_path)
    _write_manifest(dataset_root / "capture_manifest.json", config, manifest)

    return DatasetCaptureSummary(
        saved_images=saved_images,
        train_images=train_images,
        val_images=val_images,
        skipped_frames=skipped_frames,
        dataset_yaml_path=str(dataset_yaml_path),
        output_dir=str(dataset_root),
    )


def _validate_collection_config(config: CollectionConfig) -> None:
    """校验采集参数是否合法。"""
    if config.save_every_n_frames <= 0:
        raise ValueError("save_every_n_frames must be greater than 0")
    if config.max_images <= 0:
        raise ValueError("max_images must be greater than 0")
    if not 0.0 < config.train_split < 1.0:
        raise ValueError("train_split must be between 0 and 1")


def _prepare_output_dir(dataset_root: Path, overwrite: bool) -> None:
    """准备输出目录结构，必要时清空旧数据集。"""
    if dataset_root.exists() and any(dataset_root.iterdir()):
        if not overwrite:
            raise ValueError(
                f"Output directory already exists and is not empty: {dataset_root}. "
                "Set collection.overwrite=true to replace it.",
            )
        shutil.rmtree(dataset_root)

    for split in ("train", "val"):
        (dataset_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_root / "labels" / split).mkdir(parents=True, exist_ok=True)


def _has_pose_instances(result) -> bool:
    """判断当前帧是否成功检测到可保存的人体姿态。"""
    keypoints = getattr(result, "keypoints", None)
    boxes = getattr(result, "boxes", None)
    return bool(
        keypoints is not None
        and getattr(keypoints, "data", None) is not None
        and len(keypoints.data) > 0
        and boxes is not None
        and len(boxes) > 0
    )


def _choose_split(
    rng: random.Random,
    train_split: float,
    train_images: int,
    val_images: int,
) -> str:
    """按目标比例选择 train/val，并尽量保证两个集合都非空。"""
    if train_images == 0:
        return "train"
    if val_images == 0 and train_images >= 4:
        return "val"
    return "train" if rng.random() < train_split else "val"


def _ensure_non_empty_splits(
    dataset_root: Path,
    train_images: int,
    val_images: int,
    manifest: list[dict[str, object]],
) -> tuple[int, int]:
    """在极小样本场景下兜底，确保 train/val 至少各有一张图。"""
    if train_images > 0 and val_images > 0:
        return train_images, val_images

    if len(manifest) < 2:
        if not manifest:
            return train_images, val_images
        source_split = str(manifest[0]["split"])
        target_split = "val" if source_split == "train" else "train"
        image_path = Path(str(manifest[0]["image"]))
        label_path = Path(str(manifest[0]["label"]))
        copied_image_path = dataset_root / "images" / target_split / image_path.name
        copied_label_path = dataset_root / "labels" / target_split / label_path.name
        shutil.copy2(image_path, copied_image_path)
        shutil.copy2(label_path, copied_label_path)
        if source_split == "train":
            val_images += 1
        else:
            train_images += 1
        return train_images, val_images

    source_split = "train" if val_images == 0 else "val"
    target_split = "val" if val_images == 0 else "train"
    candidate = next(item for item in reversed(manifest) if item["split"] == source_split)

    image_path = Path(str(candidate["image"]))
    label_path = Path(str(candidate["label"]))
    target_image_path = dataset_root / "images" / target_split / image_path.name
    target_label_path = dataset_root / "labels" / target_split / label_path.name

    image_path.rename(target_image_path)
    label_path.rename(target_label_path)
    candidate["image"] = str(target_image_path)
    candidate["label"] = str(target_label_path)
    candidate["split"] = target_split

    if source_split == "train":
        train_images -= 1
        val_images += 1
    else:
        val_images -= 1
        train_images += 1
    return train_images, val_images


def _write_dataset_yaml(dataset_root: Path, dataset_yaml_path: Path) -> None:
    """生成 Ultralytics 训练所需的数据集 YAML 文件。"""
    dataset_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_yaml_path.write_text(
        "\n".join(
            [
                f"path: {dataset_root.resolve()}",
                "train: images/train",
                "val: images/val",
                "nc: 1",
                "names:",
                "  0: person",
                f"kpt_shape: {COCO_PERSON_KEYPOINT_SHAPE}",
                f"flip_idx: {COCO_PERSON_FLIP_IDX}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_manifest(
    manifest_path: Path,
    config: CollectionConfig,
    manifest: list[dict[str, object]],
) -> None:
    """保存采集清单，记录源配置和每个样本的来源帧。"""
    manifest_path.write_text(
        json.dumps(
            {
                "source": config.source,
                "pose_model_path": config.pose_model_path,
                "max_images": config.max_images,
                "save_every_n_frames": config.save_every_n_frames,
                "items": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
