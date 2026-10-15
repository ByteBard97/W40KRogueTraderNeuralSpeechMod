# Voice Pedalboard static demo

The `/pedalboard` page of the Voice Studio, built as a standalone site: no server, no signup, no network calls other than loading its own files.

TODO: the project license must be chosen before this is published anywhere. No LICENSE file exists and none is claimed.

## Build and run

```
npm run demo:build     # writes dist-demo/ (git-ignored)
npm run demo:dev       # dev server, opens /demo.html
python3 -m http.server -d dist-demo 8940   # any static host works the same way
```

Browsers only allow the audio worklet on https or localhost, so host it on https (GitHub Pages, Netlify, and so on).

## How it differs from the Studio page

- `vite.demo.config.ts` aliases `api/client` to `src/demo/demoApi.ts`, so the unchanged store reads bundled data and saves graphs to localStorage.
- At build time a plugin reads `tools/fx_lab/faust/blocks.lib`, `catalog.json` and `tools/fx_lab/starters/*.json` into `demo-data.json`, and copies the vendored FaustWasm and libfaust files (unmodified) into `faustwasm/` and `libfaust-wasm/`. Nothing is duplicated in git.
- Audio input is a built-in synthetic test signal, a file picker or drop, or a 6 second microphone recording. There is no game audio. A reference voice is optional and is analysed in the browser (`src/demo/analyse.ts`).
- `THIRD_PARTY_NOTICES.md` (this folder) is copied to the output root. Update it if dependencies or blocks change.
