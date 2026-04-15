import argparse
import sys
from types import SimpleNamespace

import seat_inspection.main as main_module


class StubParser:
    def __init__(self, namespace: argparse.Namespace) -> None:
        self._namespace = namespace

    def parse_args(self) -> argparse.Namespace:
        return self._namespace


def test_main_calibrate_regions_does_not_require_config(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="calibrate-regions",
                source="mvs://sn/DA9184658?timeout_ms=1000",
                output="configs/seat_regions.cam_0.json",
                window_name="seat-region-calibration",
            ),
        ),
    )

    def fail_load_runtime_config(path: str) -> None:
        raise AssertionError(f"load_runtime_config should not be called, got {path}")

    monkeypatch.setattr(main_module, "load_runtime_config", fail_load_runtime_config)

    fake_calibration_module = SimpleNamespace(
        calibrate_seat_regions=lambda source, output_path, window_name: captured.update(
            {
                "source": source,
                "output_path": output_path,
                "window_name": window_name,
            },
        ),
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.calibration", fake_calibration_module)

    main_module.main()

    assert captured == {
        "source": "mvs://sn/DA9184658?timeout_ms=1000",
        "output_path": "configs/seat_regions.cam_0.json",
        "window_name": "seat-region-calibration",
    }
