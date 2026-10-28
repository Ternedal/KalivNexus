# Kaliv Nexus baseline import

This branch is reserved for importing the **v0.50.0** source baseline. It is **not yet a working application checkout**.

## Import requirements

- Import the entire tested v0.50.0 source archive, including Python package, tests, Compose and GitHub Actions workflows.
- Exclude local caches, bytecode, secrets, and generated artifacts.
- Run `python -m pytest -q` and verify the reported result (247 tests passed in the source build).
- Run the Docker isolation workflow on a real Docker host; local Python tests do **not** prove isolation.
- Create a draft pull request against `main` only after the source import has been pushed.
- Do not merge before required CI checks pass and the changes have been reviewed.

## Status

- Branch reserved: yes.
- Source code imported: **no**.
- GitHub Actions isolation run: **no**.
- Production readiness: **not claimed**.

ModelRig and other Kaliv repositories are out of scope for this import.
