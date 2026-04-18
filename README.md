# poseDetect

`poseDetect` is a focused multi-camera, multi-view seat inspection project.

The repository keeps one production runtime path and one setup path:

- setup path: trigger all configured cameras to capture reference photos, then annotate seat regions on each photo
- runtime path: run multi-camera inference, fuse actions across views, and export a shared workflow result

Single-camera inference, image inference, calibration, dataset collection, and training are no longer part of this repository.

## What The Project Does

Current retained capabilities:

- multi-camera collaborative inference
- MVS industrial camera input through `mvs://...`
- setup capture from all configured cameras
- interactive seat-region annotation per camera photo
- operator detection from either an explicit person model or pose model boxes
- pose-based seat operation recognition
- multi-view action fusion with `any`, `all`, and `majority`
- workflow state output such as `OK`, `NG`, and `PENDING`
- light primary-operator tracking and cross-camera operator association
- JSON reporting with action segments and per-camera runtime stats

Current built-in action types:

- `touch_region`
- `lift_region`

## Current Boundary

This repository is designed for fixed industrial views.

- Default seat localization uses configured `seat_regions`.
- Optional `seat_model_path` can detect the overall seat box and remap sub-regions.
- The system is rule-driven, not an end-to-end action classification project.
- Multi-person robustness is improved, but this is still a lightweight primary-operator tracking approach rather than a full re-identification system.

## Project Structure

- `src/seat_inspection/main.py`: CLI entry
- `src/seat_inspection/camera_setup.py`: multi-camera setup capture and seat-region annotation
- `src/seat_inspection/inference.py`: multi-camera orchestration
- `src/seat_inspection/pipeline.py`: per-camera processing chain
- `src/seat_inspection/multi_camera.py`: cross-camera action fusion
- `src/seat_inspection/tracking.py`: primary-operator tracking and association
- `src/seat_inspection/rules.py`: rule-based action evaluation
- `src/seat_inspection/state_machine.py`: workflow state progression
- `src/seat_inspection/reporting.py`: JSON export
- `src/media_inputs/`: unified stream abstraction
- `src/mvsCamera/`: Hikrobot MVS integration
- `configs/multi_camera_setup.example.json`: setup capture config example
- `configs/runtime.multi_camera.example.json`: generic inference config example
- `configs/runtime.multi_camera.mvs.json`: multi-MVS inference config example

## Environment

Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Setup Workflow

Use this workflow when seat regions are not configured yet.

### 1. Prepare a setup config

Example:

```json
{
  "multi_camera_setup": {
    "cameras": [
      {
        "name": "front",
        "source": "mvs://0?timeout_ms=1000"
      },
      {
        "name": "side",
        "source": "mvs://1?timeout_ms=1000"
      }
    ]
  }
}
```

Reference file:

- `configs/multi_camera_setup.example.json`

### 2. Trigger all configured cameras to capture photos

Fast path: run the entire setup in one command

```bash
python -m seat_inspection setup-seat-regions \
  --setup-config configs/multi_camera_setup.example.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --capture-dir outputs/setup_capture \
  --annotation-output outputs/setup_capture/seat_regions.annotations.json
```

Optional: write the updated runtime config to a new file

```bash
python -m seat_inspection setup-seat-regions \
  --setup-config configs/multi_camera_setup.example.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --capture-dir outputs/setup_capture \
  --annotation-output outputs/setup_capture/seat_regions.annotations.json \
  --output-runtime-config configs/runtime.multi_camera.ready.json
```

This guided command will:

- capture one photo from every configured camera
- open each photo for seat region annotation
- write annotated `seat_regions` back into the runtime config

Manual step-by-step mode:

```bash
python -m seat_inspection capture-setup \
  --config configs/multi_camera_setup.example.json \
  --output-dir outputs/setup_capture
```

This command:

- opens every configured camera
- captures one reference frame per camera
- saves images such as `front.jpg`, `side.jpg`
- writes `capture_manifest.json`

### 3. Annotate seat regions on each captured photo

```bash
python -m seat_inspection annotate-setup \
  --capture-dir outputs/setup_capture \
  --output outputs/setup_capture/seat_regions.annotations.json
```

For each camera image, the tool will ask you to draw:

1. `overall`
2. `side_surface`
3. `bottom_surface`

The output file contains:

- per-camera `seat_regions`
- a ready-to-copy `multi_camera_inference_patch`

### 4. Apply the annotations back into the runtime config

Update the runtime config in place:

```bash
python -m seat_inspection apply-setup \
  --annotations outputs/setup_capture/seat_regions.annotations.json \
  --runtime-config configs/runtime.multi_camera.example.json
```

Or write the updated runtime config to a new file:

```bash
python -m seat_inspection apply-setup \
  --annotations outputs/setup_capture/seat_regions.annotations.json \
  --runtime-config configs/runtime.multi_camera.example.json \
  --output configs/runtime.multi_camera.ready.json
```

The command matches cameras by `name` and writes each annotated `seat_regions` into:

- `multi_camera_inference.cameras[i].seat_regions`

## Inference Workflow

Run collaborative inference with a configured runtime file:

```bash
python -m seat_inspection infer --config configs/runtime.multi_camera.example.json
```

Or:

```bash
seat-inspection infer --config configs/runtime.multi_camera.example.json
```

## Runtime Config

Only two top-level runtime config blocks remain:

- `rules`
- `multi_camera_inference`

Each camera in `multi_camera_inference.cameras` can define:

- `name`
- `source`
- `seat_regions`
- optional `pose_model_path`
- optional `person_model_path`
- optional `seat_model_path`
- optional `confidence`
- optional `iou`
- optional `device`

Shared multi-camera settings include:

- default pose model
- fusion strategy
- minimum active camera count
- consecutive read failure tolerance
- workflow state machine
- live preview options
- visualization output

## How `seat_regions` Should Be Drawn

- `overall`: the full seat body visible in the current camera view
- `side_surface`: the seat side area used for touch operation judgement
- `bottom_surface`: the lower area used for lift or support judgement

Practical advice:

- keep boxes tight enough to avoid large background area
- do not make `side_surface` and `bottom_surface` identical unless the real operation areas overlap
- annotate separately for each camera because perspective changes
- if the camera is fixed, annotate once and reuse the same coordinates

## Outputs

The runtime exports a fused JSON report that includes:

- frame-by-frame fused action decisions
- action reason counts
- contiguous action segments
- workflow result
- active camera list per fused frame
- associated operator id
- per-camera runtime statistics in metadata

When visualization is enabled, the preview also shows:

- seat regions
- selected operator box and track id
- fused operator association id
- per-camera placeholders for dropped or offline views

## Documentation Policy

The README files are now the source of truth for this repository.

- `README.md` describes the English project view
- `README_ZH.md` describes the Chinese project view
- the old standalone docs have been removed
