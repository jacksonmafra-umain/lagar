# lagar app

Compose Multiplatform client (Android, iOS, web) for the lagar static JSON API.

## Layout

- `shared/` - Kotlin Multiplatform library with the UI (`app.lagar.App`); iOS framework name `Shared`
- `androidApp/` - Android application (`app.lagar`)
- `iosApp/` - Xcode project embedding the `Shared` framework
- `webApp/` - Kotlin/Wasm browser entry point

## Build

Requires JDK 21 and the Android SDK (`ANDROID_HOME`). From `app/`:

```sh
./gradlew :androidApp:assembleDebug
./gradlew :webApp:wasmJsBrowserDistribution   # output: webApp/build/dist/wasmJs/productionExecutable
./gradlew :webApp:wasmJsBrowserDevelopmentRun # serve locally
xcodebuild -project iosApp/iosApp.xcodeproj -scheme iosApp \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' build
```

The Xcode "Compile Kotlin Framework" phase runs Gradle with `$JAVA_HOME` if set, otherwise
JDK 21 from `/usr/libexec/java_home -v 21` (the build fails if no JDK 21 is installed).
Android builds also need `ANDROID_HOME` (or a `local.properties` with `sdk.dir`).

## Data source

Release builds read the API published to GitHub Pages (`DataSourceConfig.PUBLISHED_API`,
`https://jacksonmafra-umain.github.io/lagar/api/v1/`). Debug builds read the generated API from a local
server. Each platform picks its `DataSourceConfig` at its entry point and passes it to `App(...)`:

```sh
python3 -I api/build.py --corpus corpus --out /tmp/lagar/build/api/v1   # from the repo root
python3 -I -m http.server 8000 --directory /tmp/lagar/build
```

- **Android:** debug builds read `http://10.0.2.2:8000/api/v1/`, the emulator's alias for the host. Plain HTTP
  is allowed only in the debug source set (`androidApp/src/debug`), limited to `10.0.2.2`. A debug build on a
  physical device cannot reach `10.0.2.2` and shows the error state; use a release build, which reads the
  published API.
- **iOS:** debug builds read `http://localhost:8000/api/v1/`; the simulator shares the host network.
- **Web:** the page reads `api/v1/` next to itself, which is the Pages layout (`/lagar/` and `/lagar/api/v1/`).
  To try it locally, copy the dist and the API into one folder and serve that:

  ```sh
  mkdir -p /tmp/lagar/site && cp -R webApp/build/dist/wasmJs/productionExecutable/. /tmp/lagar/site/
  cp -R /tmp/lagar/build/api /tmp/lagar/site/
  python3 -I -m http.server 8001 --directory /tmp/lagar/site   # open http://localhost:8001/
  ```

  Add `?sample` to use the bundled sample instead. `python3 -I scripts/serve_local.py` (from the repo root) does
  the same without copying: it builds what is missing and serves the dist at `/` and the API at `/api/v1/`.

The bundled sample (`SampleRepository`) stays for tests and `?sample`. No build falls back to it silently,
because a 104-document sample shown as the catalogue would mislead; offline, the app shows its error state
with retry.

## Deployment

`.github/workflows/pages.yml` builds the API from `corpus/` and the web app on every push to `main` that
touches them, and publishes both to GitHub Pages: the app at `https://jacksonmafra-umain.github.io/lagar/`
and the API under `/lagar/api/v1/`.

## Web base path

The distribution uses relative asset paths, so it can be served under any prefix, e.g. `/lagar/`
on GitHub Pages. Verified by serving the dist under `/lagar/` (index, JS, wasm and compose resources all load).
The landing site on Vercel (<https://grundlagar.vercel.app>) also serves it under `/app/`; there
`landing/vercel.json` proxies `/app/api/v1/*` to the API on GitHub Pages.
