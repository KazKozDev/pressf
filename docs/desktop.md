# Desktop app

The Electron app is a graphical layer over the same local projects and CLI. It supports the five evaluation modes, blind pairwise comparison, import, review, calibration, exports, and project settings.

## Run locally

Run from the repository root after the Python environment is installed:

```bash
cd app
npm install
npm run dev
```

The desktop process looks for `../.venv/bin/lazy`; without that environment it falls back to a `lazy` executable on `PATH`.

## Test, build, and package

Run these commands from `app/`:

```bash
npm test
npm run build
npm run dist   # macOS arm64 DMG
```

For packaging, signing, notarization, and auto-update details, see [RELEASE.md](../app/RELEASE.md). The in-app help is also available as [DOCS.md](../app/DOCS.md).
