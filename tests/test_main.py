import argparse
from types import SimpleNamespace

import seat_inspection.main as main_module


class StubParser:
    def __init__(self, namespace: argparse.Namespace) -> None:
        self._namespace = namespace

    def parse_args(self) -> argparse.Namespace:
        return self._namespace


def test_main_infer_runs_multi_camera_entry(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="infer",
                config="configs/runtime.multi_camera.example.json",
            ),
        ),
    )

    fake_runtime_config = SimpleNamespace(
        multi_camera_inference=SimpleNamespace(
            output_json_path="outputs/multi_camera_action_results.json",
        ),
        rules="rules-config",
    )
    monkeypatch.setattr(
        main_module,
        "load_runtime_config",
        lambda path: captured.update({"config_path": path}) or fake_runtime_config,
    )

    import sys

    fake_inference_module = SimpleNamespace(
        run_multi_camera_inference=lambda config, rules: captured.update(
            {
                "runtime_config": config,
                "rules": rules,
            },
        )
        or [object(), object()],
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.inference", fake_inference_module)

    main_module.main()

    stdout = capsys.readouterr().out
    assert captured["config_path"] == "configs/runtime.multi_camera.example.json"
    assert captured["runtime_config"] is fake_runtime_config.multi_camera_inference
    assert captured["rules"] == "rules-config"
    assert "2 fused frames processed" in stdout
