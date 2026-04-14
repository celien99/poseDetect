# poseDetect

A minimal Python project for experimenting with Ultralytics YOLO pose training.

## Project Structure
- `example.py` — sample YOLO pose training script
- `src/` — reusable project code
- `tests/` — automated tests
- `AGENTS.md` — repository contribution guide

## Requirements
- Python 3.10+
- A virtual environment is recommended

## Quick Start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python example.py
```

## Notes
`example.py` expects Ultralytics model and dataset configuration files such as:
- `yolo26n-pose.yaml`
- `yolo26n-pose.pt`
- `coco8-pose.yaml`

Make sure those files are available locally before starting training.

## Development
If you add reusable modules, place them in `src/` and add tests in `tests/`.

Example test command:
```bash
pytest
```
