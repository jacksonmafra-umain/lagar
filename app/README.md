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

Release builds read the bundled sample (no hosted API exists yet). Debug builds read the generated API
from a local server; each platform picks its `DataSourceConfig` at its entry point and passes it to `App(...)`:

```sh
python3 -I api/build.py --corpus corpus --out /tmp/lagar/build/api/v1   # from the repo root
python3 -I -m http.server 8000 --directory /tmp/lagar/build
```

- Android: `BuildConfig.DEBUG` selects the API at `http://10.0.2.2:8000/api/v1/` (the emulator's alias for the host).
  Plain HTTP is allowed only in the debug source set (`androidApp/src/debug`), limited to `10.0.2.2`.
  A debug build on a physical device cannot reach `10.0.2.2` (or `localhost`) and shows the error state; use a
  release build (bundled sample) or point `DataSourceConfig` at a reachable base URL.
- iOS: `Platform.isDebugBinary` selects the API at `http://localhost:8000/api/v1/` (simulator shares the host network).
- Web: the sample is the default; open the page with `?api` to read `../api/v1/` instead. Copy the dist into the
  server root as `lagar/` (`cp -R webApp/build/dist/wasmJs/productionExecutable/. /tmp/lagar/build/lagar/`) and open
  `http://localhost:8000/lagar/?api`; same origin, so no CORS setup is needed.

## Web base path

The distribution uses relative asset paths, so it can be served under any prefix, e.g. `/lagar/`
on GitHub Pages. Verified by serving the dist under `/lagar/` (index, JS, wasm and compose resources all load).
