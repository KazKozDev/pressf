# Releasing PressF Desktop

The build gracefully degrades: with **no credentials set** you get today's unsigned dev
`.dmg` (Gatekeeper will warn; right-click → Open once). With credentials present the same
command produces a **signed + notarized** build.

## Dev build (unsigned)

```bash
cd app
npm run dist            # → app/release/PressF-<version>-arm64.dmg  (unsigned)
```

## Signed + notarized build

Set the signing/notarization env vars, then run the same command. electron-builder picks
them up automatically; the `mac.hardenedRuntime` + entitlements are already configured.

```bash
export CSC_LINK=/path/to/DeveloperIDApplication.p12      # or base64 via CSC_LINK
export CSC_KEY_PASSWORD=…                                # p12 password
export APPLE_ID=you@example.com
export APPLE_APP_SPECIFIC_PASSWORD=abcd-efgh-ijkl-mnop   # app-specific password
export APPLE_TEAM_ID=XXXXXXXXXX

# enable notarization for this build (config default is off):
#   set "mac.notarize" to { "teamId": "$APPLE_TEAM_ID" } in package.json, or pass via CLI
npm run dist
```

Artifact lands in `app/release/`. Verify:

```bash
codesign --verify --deep --strict --verbose=2 "app/release/mac-arm64/PressF.app"
spctl -a -vv "app/release/mac-arm64/PressF.app"        # should say "accepted / notarized"
```

## Auto-update

The app checks for updates on launch **only** when a feed is configured — otherwise it is
a silent no-op (and never runs in dev or e2e). Configure a feed by either:

- `PRESSF_UPDATE_FEED=https://.../update/` (generic feed), or
- a `build.publish` block (e.g. GitHub Releases) in `package.json` + `GH_TOKEN` at publish
  time (`electron-builder --publish always`).

Uploaded release assets must include the `latest-mac.yml` electron-builder emits so the
updater can detect new versions.

## Version bump

Bump `version` in `app/package.json` before `npm run dist`; the updater compares against it.
