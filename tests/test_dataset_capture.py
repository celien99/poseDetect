from pathlib import Path

import pytest

from seat_inspection.dataset_capture import _ensure_non_empty_splits, _write_dataset_yaml


def test_write_dataset_yaml_creates_pose_training_config(tmp_path) -> None:
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()
    yaml_path = dataset_root / "dataset.yaml"

    _write_dataset_yaml(dataset_root, yaml_path)

    content = yaml_path.read_text(encoding="utf-8")
    assert "train: images/train" in content
    assert "val: images/val" in content
    assert "kpt_shape: [17, 3]" in content


def test_ensure_non_empty_splits_moves_one_sample_to_val(tmp_path) -> None:
    dataset_root = tmp_path / "dataset"
    train_images_dir = dataset_root / "images" / "train"
    train_labels_dir = dataset_root / "labels" / "train"
    val_images_dir = dataset_root / "images" / "val"
    val_labels_dir = dataset_root / "labels" / "val"
    train_images_dir.mkdir(parents=True)
    train_labels_dir.mkdir(parents=True)
    val_images_dir.mkdir(parents=True)
    val_labels_dir.mkdir(parents=True)

    image_paths = []
    label_paths = []
    for index in range(2):
        image_path = train_images_dir / f"frame_{index:06d}.jpg"
        label_path = train_labels_dir / f"frame_{index:06d}.txt"
        image_path.write_bytes(b"img")
        label_path.write_text("0 0.5 0.5 0.2 0.2", encoding="utf-8")
        image_paths.append(image_path)
        label_paths.append(label_path)

    manifest = [
        {"image": str(image_paths[0]), "label": str(label_paths[0]), "split": "train"},
        {"image": str(image_paths[1]), "label": str(label_paths[1]), "split": "train"},
    ]

    train_count, val_count = _ensure_non_empty_splits(dataset_root, 2, 0, manifest)

    assert train_count == 1
    assert val_count == 1
    assert Path(str(manifest[-1]["image"])).parent == val_images_dir


def test_ensure_non_empty_splits_rejects_single_sample_duplication(tmp_path) -> None:
    dataset_root = tmp_path / "dataset"
    train_images_dir = dataset_root / "images" / "train"
    train_labels_dir = dataset_root / "labels" / "train"
    train_images_dir.mkdir(parents=True)
    train_labels_dir.mkdir(parents=True)

    image_path = train_images_dir / "frame_000000.jpg"
    label_path = train_labels_dir / "frame_000000.txt"
    image_path.write_bytes(b"img")
    label_path.write_text("0 0.5 0.5 0.2 0.2", encoding="utf-8")

    manifest = [
        {"image": str(image_path), "label": str(label_path), "split": "train"},
    ]

    with pytest.raises(ValueError, match="At least 2 labeled samples are required"):
        _ensure_non_empty_splits(dataset_root, 1, 0, manifest)
