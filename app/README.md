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

## Web base path

The distribution uses relative asset paths, so it can be served under any prefix, e.g. `/lagar/`
on GitHub Pages. Verified by serving the dist under `/lagar/` (index, JS, wasm and compose resources all load).
