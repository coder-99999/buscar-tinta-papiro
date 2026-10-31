# buscar-tinta-papiro (private)

No-AI search for weak ink hints in Vesuvius Challenge PHerc. 1447 surface-volume segments. Runs on Windows and Linux; the UI and reports are in Spanish.

- Full manual: [`docs/index.html`](docs/index.html). Open it locally; GitHub Pages is intentionally **not** enabled.
- Windows one-file exe: built by `.github/workflows/exe.yml` (PyInstaller, windows-latest). An optional Linux one-file binary comes from the ubuntu-latest job.
- Linux: `python3 -m venv ~/.venv-buscar-tinta && ~/.venv-buscar-tinta/bin/pip install numpy zarr tifffile matplotlib scipy`, then `./buscar_tinta_papiro.sh`.

**Data rule:** Vesuvius Challenge data is CC BY-NC 4.0. Do not publish any revelation of hidden text, or the related code, outside the official VC Discord without the Vesuvius Challenge's written approval. Do not redistribute the data.

Credits: Matteo Bulloni's first-letters-survey (MIT, orchestration and controls only, no ML); Omit (idea only); Vesuvius Challenge (data).
