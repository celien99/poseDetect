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


def test_main_capture_setup_runs_capture_command(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="capture-setup",
                config="configs/multi_camera_setup.example.json",
                output_dir="outputs/setup_capture",
            ),
        ),
    )

    import sys

    fake_setup_module = SimpleNamespace(
        capture_multi_camera_snapshots=lambda config_path, output_dir: captured.update(
            {
                "config_path": config_path,
                "output_dir": output_dir,
            },
        )
        or SimpleNamespace(
            success_count=2,
            results=[object(), object()],
            manifest_path="outputs/setup_capture/capture_manifest.json",
        ),
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.camera_setup", fake_setup_module)

    main_module.main()

    stdout = capsys.readouterr().out
    assert captured["config_path"] == "configs/multi_camera_setup.example.json"
    assert captured["output_dir"] == "outputs/setup_capture"
    assert "2/2 cameras captured" in stdout


def test_main_annotate_setup_runs_annotation_command(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="annotate-setup",
                capture_dir="outputs/setup_capture",
                output="outputs/setup_capture/seat_regions.annotations.json",
            ),
        ),
    )

    import sys

    fake_setup_module = SimpleNamespace(
        annotate_multi_camera_snapshots=lambda capture_dir, output_path: captured.update(
            {
                "capture_dir": capture_dir,
                "output_path": output_path,
            },
        )
        or "outputs/setup_capture/seat_regions.annotations.json",
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.camera_setup", fake_setup_module)

    main_module.main()

    stdout = capsys.readouterr().out
    assert captured["capture_dir"] == "outputs/setup_capture"
    assert captured["output_path"] == "outputs/setup_capture/seat_regions.annotations.json"
    assert "Seat region annotation completed" in stdout


def test_main_apply_setup_runs_apply_command(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="apply-setup",
                annotations="outputs/setup_capture/seat_regions.annotations.json",
                runtime_config="configs/runtime.multi_camera.example.json",
                output="configs/runtime.multi_camera.updated.json",
            ),
        ),
    )

    import sys

    fake_setup_module = SimpleNamespace(
        apply_annotations_to_runtime_config=lambda annotation_path, runtime_config_path, output_path=None: captured.update(
            {
                "annotation_path": annotation_path,
                "runtime_config_path": runtime_config_path,
                "output_path": output_path,
            },
        )
        or "configs/runtime.multi_camera.updated.json",
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.camera_setup", fake_setup_module)

    main_module.main()

    stdout = capsys.readouterr().out
    assert captured["annotation_path"] == "outputs/setup_capture/seat_regions.annotations.json"
    assert captured["runtime_config_path"] == "configs/runtime.multi_camera.example.json"
    assert captured["output_path"] == "configs/runtime.multi_camera.updated.json"
    assert "Runtime config updated with seat regions" in stdout


def test_main_setup_seat_regions_runs_full_setup_command(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_module,
        "build_parser",
        lambda: StubParser(
            argparse.Namespace(
                command="setup-seat-regions",
                setup_config="configs/multi_camera_setup.example.json",
                runtime_config="configs/runtime.multi_camera.example.json",
                capture_dir="outputs/setup_capture",
                annotation_output="outputs/setup_capture/seat_regions.annotations.json",
                output_runtime_config="configs/runtime.multi_camera.ready.json",
            ),
        ),
    )

    import sys

    fake_setup_module = SimpleNamespace(
        setup_seat_regions=lambda setup_config_path, runtime_config_path, capture_dir, annotation_output_path, output_runtime_config_path=None: captured.update(
            {
                "setup_config_path": setup_config_path,
                "runtime_config_path": runtime_config_path,
                "capture_dir": capture_dir,
                "annotation_output_path": annotation_output_path,
                "output_runtime_config_path": output_runtime_config_path,
            },
        )
        or SimpleNamespace(
            capture_summary=SimpleNamespace(
                success_count=2,
                results=[object(), object()],
            ),
            annotation_path="outputs/setup_capture/seat_regions.annotations.json",
            runtime_config_output_path="configs/runtime.multi_camera.ready.json",
        ),
    )
    monkeypatch.setitem(sys.modules, "seat_inspection.camera_setup", fake_setup_module)

    main_module.main()

    stdout = capsys.readouterr().out
    assert captured["setup_config_path"] == "configs/multi_camera_setup.example.json"
    assert captured["runtime_config_path"] == "configs/runtime.multi_camera.example.json"
    assert captured["capture_dir"] == "outputs/setup_capture"
    assert captured["annotation_output_path"] == "outputs/setup_capture/seat_regions.annotations.json"
    assert captured["output_runtime_config_path"] == "configs/runtime.multi_camera.ready.json"
    assert "Seat region setup completed" in stdout
