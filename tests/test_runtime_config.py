import json

from seat_inspection.runtime_config import load_runtime_config


def test_load_runtime_config_builds_multi_camera_bundle(tmp_path) -> None:
    config_path = tmp_path / "runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": {
                    "touch_hold_frames": 2
                },
                "multi_camera_inference": {
                    "pose_model_path": "pose.pt",
                    "show_window": True,
                    "max_consecutive_read_failures": 5,
                    "min_active_cameras": 2,
                    "fusion": {
                        "touch_action_strategy": "any",
                        "lift_action_strategy": "majority",
                        "time_tolerance_ms": 80.0
                    },
                    "keypoint_processing": {
                        "enabled": True,
                        "smoothing_window": 5,
                        "interpolate_missing": True,
                        "max_missing_frames": 3,
                        "min_confidence": 0.2
                    },
                    "state_machine": {
                        "enabled": True,
                        "require_all_steps": True,
                        "steps": [
                            {
                                "name": "step1",
                                "action": "touch_side_surface",
                                "min_frames": 2
                            }
                        ]
                    },
                    "cameras": [
                        {
                            "name": "front",
                            "source": "mvs://0?timeout_ms=1000",
                            "seat_regions": {
                                "overall": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                                "side_surface": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                                "bottom_surface": {"x1": 9, "y1": 10, "x2": 11, "y2": 12}
                            }
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    runtime = load_runtime_config(str(config_path))

    assert runtime.multi_camera_inference is not None
    assert runtime.rules.actions[0].name == "touch_side_surface"
    assert runtime.rules.actions[0].hold_frames == 2
    assert runtime.multi_camera_inference.keypoint_processing.smoothing_window == 5
    assert runtime.multi_camera_inference.state_machine.steps[0].name == "step1"
    assert runtime.multi_camera_inference.cameras[0].seat_regions.side_surface.x1 == 5.0
    assert runtime.multi_camera_inference.max_consecutive_read_failures == 5
    assert runtime.multi_camera_inference.min_active_cameras == 2


def test_load_runtime_config_builds_multi_camera_inference(tmp_path) -> None:
    config_path = tmp_path / "runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "multi_camera_inference": {
                    "pose_model_path": "pose.pt",
                    "show_window": True,
                    "fusion": {
                        "touch_action_strategy": "any",
                        "lift_action_strategy": "majority",
                        "time_tolerance_ms": 80.0
                    },
                    "cameras": [
                        {
                            "name": "front",
                            "source": "mvs://0?timeout_ms=1000",
                            "seat_regions": {
                                "overall": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                                "side_surface": {"x1": 5, "y1": 6, "x2": 7, "y2": 8},
                                "bottom_surface": {"x1": 9, "y1": 10, "x2": 11, "y2": 12}
                            }
                        },
                        {
                            "name": "side",
                            "source": "mvs://1?timeout_ms=1000",
                            "seat_regions": {
                                "overall": {"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                                "side_surface": {"x1": 50, "y1": 60, "x2": 70, "y2": 80},
                                "bottom_surface": {"x1": 90, "y1": 100, "x2": 110, "y2": 120}
                            }
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    runtime = load_runtime_config(str(config_path))

    assert runtime.multi_camera_inference is not None
    assert runtime.multi_camera_inference.show_window is True
    assert runtime.multi_camera_inference.fusion.lift_action_strategy == "majority"
    assert runtime.multi_camera_inference.cameras[0].source == "mvs://0?timeout_ms=1000"
    assert runtime.multi_camera_inference.cameras[1].seat_regions.bottom_surface.x2 == 110.0
