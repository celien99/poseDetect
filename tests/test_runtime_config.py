import json

from seat_inspection.runtime_config import load_runtime_config


def test_load_runtime_config_builds_nested_dataclasses(tmp_path) -> None:
    config_path = tmp_path / "runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "training": {
                    "model_path": "model.pt",
                    "data_config": "dataset.yaml"
                },
                "rules": {
                    "touch_hold_frames": 2
                },
                "inference": {
                    "pose_model_path": "model.pt",
                    "source": "demo.mp4",
                    "output_json_path": "outputs/result.json",
                    "save_visualization": False,
                    "seat_regions": {
                        "overall": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                        "side_surface": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                        "bottom_surface": {"x1": 9, "y1": 10, "x2": 11, "y2": 12}
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    runtime = load_runtime_config(str(config_path))

    assert runtime.training is not None
    assert runtime.training.model_path == "model.pt"
    assert runtime.rules.touch_hold_frames == 2
    assert runtime.inference is not None
    assert runtime.inference.seat_regions.side_surface.x1 == 5.0
