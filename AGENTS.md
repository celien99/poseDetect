# Repository Guidelines

## Project Structure & Module Organization
This repository is currently centered on a single training script, `example.py`, which uses Ultralytics YOLO pose models. Local environment artifacts live in `.venv/` and Python bytecode appears in `__pycache__/`; neither should be edited or committed. Keep model and dataset references (`yolo26n-pose.yaml`, `yolo26n-pose.pt`, `coco8-pose.yaml`) alongside the script or move them into clearly named folders such as `models/` or `configs/` if the project grows. If you add reusable code, prefer a `src/` package and mirror tests under `tests/`.

## Build, Test, and Development Commands
- `python3 -m venv .venv` — create a local Python 3.10 virtual environment.
- `source .venv/bin/activate` — activate the environment before installing dependencies.
- `pip install ultralytics` — install the core training dependency.
- `python example.py` — run the pose-training example using the configured model and dataset files.

This project does not currently define a separate build step, Makefile, or package manager workflow.

## Coding Style & Naming Conventions
Use Python 3.10+ and follow PEP 8: 4-space indentation, `snake_case` for functions and variables, and clear module names such as `train_pose.py`. Keep training configuration values explicit and close to where they are used. Avoid hardcoding machine-specific paths; prefer relative paths or constants near the top of the file.

## Testing Guidelines
There is no automated test suite yet. For changes to training logic, do a quick smoke check before long runs by validating imports, file paths, and a shortened training configuration. If you add reusable helpers, place tests in `tests/test_*.py` and use `pytest`.

## Commit & Pull Request Guidelines
Git history is not available in this checkout, so use short, imperative commit messages such as `Add pose training config constants`. Pull requests should describe the training or config change, list commands run, and note any required model, dataset, or YAML files. Include logs, sample metrics, or screenshots when a change affects training behavior.

## Security & Configuration Tips
Do not commit datasets, model weights, secrets, or large generated outputs. Keep local-only files in `.venv/`, ignore cache directories, and document any new external dependencies in the PR description.
