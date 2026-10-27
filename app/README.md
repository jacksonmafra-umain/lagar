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
