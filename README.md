# poseDetect

This repository now targets one mode only: multi-camera, multi-view collaborative seat inspection.

## Scope

The retained runtime path is:

1. open multiple video or MVS camera streams;
2. run pose estimation per camera;
3. evaluate action rules per camera;
4. fuse actions across views with `any`, `all`, or `majority`;
5. advance one shared workflow state machine and export a fused JSON report.

Single-camera inference, image inference, calibration, dataset collection, and training have been removed.

## Project Structure

- `src/seat_inspection/main.py` — CLI entry with `infer`
- `src/seat_inspection/inference.py` — multi-camera orchestration
- `src/seat_inspection/multi_camera.py` — cross-camera fusion
- `src/seat_inspection/pipeline.py` — per-camera processing pipeline
- `src/seat_inspection/rules.py` — action rule evaluation
- `src/seat_inspection/state_machine.py` — fused workflow status
- `src/seat_inspection/reporting.py` — JSON report export
- `src/media_inputs/` — unified stream abstraction
- `src/mvsCamera/` — Hikrobot MVS access layer
- `configs/runtime.multi_camera.example.json` — editable example config
- `configs/runtime.multi_camera.mvs.json` — MVS-oriented example config

## Environment

Use Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

## Run

```bash
python -m seat_inspection infer --config configs/runtime.multi_camera.example.json
```

Or:

```bash
seat-inspection infer --config configs/runtime.multi_camera.example.json
```

## Runtime Config

Only two top-level sections are kept:

- `rules`
- `multi_camera_inference`

Each camera under `multi_camera_inference.cameras` defines:

- `name`
- `source`
- `seat_regions`
- optional per-camera overrides for pose model, person model, seat model, confidence, IoU, and device

Shared multi-camera settings define:

- default pose model
- fusion strategy
- workflow state machine
- visualization output
- live preview behavior

## Notes

- `mvs://...` industrial camera sources are supported.
- Fixed seat regions remain the default mode.
- `seat_model_path` can still be enabled to map template seat regions from a detected overall seat box.
