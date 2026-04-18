# Repository Guidelines

## Project Structure & Module Organization
This repository is currently centered on runtime code under `src/`, with the main entry points in `src/seat_inspection/` and camera integration in `src/mvsCamera/`. Local environment artifacts live in `.venv/` and Python bytecode appears in `__pycache__/`; neither should be edited or committed.

## Build, Test, and Development Commands
- `python3 -m venv .venv` — create a local Python 3.10 virtual environment.
- `source .venv/bin/activate` — activate the environment before installing dependencies.
- `pip install -e .` — install the current runtime package in editable mode.
- `PYTHONPATH=src python3 -m seat_inspection --help` — check that the CLI entry can be imported and parsed.

This project does not currently define a separate build step, Makefile, or package manager workflow.

## Coding Style & Naming Conventions
Use Python 3.10+ and follow PEP 8: 4-space indentation, `snake_case` for functions and variables, and clear module names such as `train_pose.py`. Keep training configuration values explicit and close to where they are used. Avoid hardcoding machine-specific paths; prefer relative paths or constants near the top of the file.

## Validation Guidelines
This project does not keep an automated test suite. For changes to runtime logic, do a quick smoke check by validating imports, config loading, and basic command execution paths.

## Commit & Pull Request Guidelines
Git history is not available in this checkout, so use short, imperative commit messages such as `Add pose training config constants`. Pull requests should describe the training or config change, list commands run, and note any required model, dataset, or YAML files. Include logs, sample metrics, or screenshots when a change affects training behavior.

## Security & Configuration Tips
Do not commit datasets, model weights, secrets, or large generated outputs. Keep local-only files in `.venv/`, ignore cache directories, and document any new external dependencies in the PR description.
