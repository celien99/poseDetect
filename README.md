# poseDetect

Enterprise-oriented skeleton for seat inspection operator action detection based on Ultralytics YOLO pose models.

## Target Scenario

The system verifies whether an operator follows the required inspection procedure around a seat-testing device, for example:

- touching the seat side surface with a hand;
- lifting the seat bottom for inspection;
- extending to more SOP-driven actions in later phases.

## Recommended Technical Architecture

This repository adopts a two-stage design suitable for enterprise projects:

1. `YOLO pose model` extracts operator keypoints.
2. `Seat region definitions` describe operational zones such as side surface and bottom surface.
3. `Rule engine` converts pose + region geometry into auditable action decisions.
4. `Training and inference modules` remain separated for maintainability and future service deployment.
5. `JSON report output` enables integration with MES, traceability, and post-event review.

This design is easier to validate and explain than trying to train a single end-to-end action class directly from limited industrial data.

## Project Structure

- `src/seat_inspection/main.py` — enterprise entry for training and inference
- `src/seat_inspection/__main__.py` — package entry for `python -m seat_inspection`
- `configs/runtime.example.json` — enterprise runtime config example
- `src/seat_inspection/config.py` — training, rule, and inference configuration with remarks
- `src/seat_inspection/runtime_config.py` — JSON config loader
- `src/seat_inspection/training.py` — YOLO pose training wrapper
- `src/seat_inspection/inference.py` — video inference and JSON export
- `src/seat_inspection/rules.py` — industrial action rule evaluator
- `src/seat_inspection/engine.py` — action recognition engine
- `src/seat_inspection/reporting.py` — action report writer
- `tests/test_rules.py` — rule-based action tests
- `tests/test_runtime_config.py` — runtime config parsing tests

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

## Training

Train by runtime config:

```bash
python -m seat_inspection train --config configs/runtime.example.json
```

## Dataset Collection

Capture frames from an MVS camera or a video source, auto-label them with the current pose model, and build a YOLO pose dataset:

```bash
python -m seat_inspection collect --config configs/runtime.example.json
```

This command creates:

- `datasets/seat_pose/images/train`
- `datasets/seat_pose/images/val`
- `datasets/seat_pose/labels/train`
- `datasets/seat_pose/labels/val`
- `datasets/seat_pose/dataset.yaml`
- `datasets/seat_pose/capture_manifest.json`

## Inference

Run video inference and export JSON results:

```bash
python -m seat_inspection infer --config configs/runtime.example.json
```

Run single-image inference:

```bash
python -m seat_inspection infer-image --config configs/runtime.example.json
```

Output artifacts:

- `outputs/action_results.json` — frame-by-frame action decisions
- `outputs/action_preview.mp4` — annotated review video when `save_visualization` is enabled

## Runtime Config

`configs/runtime.example.json` contains three sections:

- `training` — YOLO training parameters
- `rules` — action rule thresholds and hold-frame settings
- `inference` — video source, seat regions, and output paths
- `image_inference` — single-image source, seat regions, and output paths

`inference.source` can now also point to an MVS industrial camera by using a source string such as `mvs://0?timeout_ms=1000`.

`rules.actions` can define custom actions without changing Python code. The built-in action kinds are:

- `touch_region`
- `lift_region`

For fixed industrial cameras, `seat_regions` should be calibrated from the real device view and versioned with your deployment package.

## Enterprise Implementation Notes

For your real seat inspection project, the dataset should include:

- operator pose samples from the actual production camera angle;
- seat detection or manually defined seat regions;
- SOP action definitions with acceptance criteria;
- video segments for normal, missed, and incorrect actions.

Recommended rollout path:

1. run `collect` against the real camera angle to bootstrap a pose dataset;
2. manually review and correct the generated labels when needed;
3. run `train` on the generated `dataset.yaml`;
4. run `infer` on the same camera setup and tune the rule thresholds.

## Testing

```bash
pytest
```

## Windows Test Machine Guide

For Windows deployment and Hikrobot MVS camera bring-up, see:

- [WINDOWS_TEST_GUIDE.md](WINDOWS_TEST_GUIDE.md)


## Editable Install

After `pip install -e .`, you can also use the console command:

```bash
seat-inspection --help
seat-inspection train --config configs/runtime.example.json
seat-inspection infer --config configs/runtime.example.json
```
