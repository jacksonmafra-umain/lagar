package app.lagar.ui

/**
 * Base class of the Compose UI tests (`runComposeUiTest`): on the Android host it runs them under Robolectric,
 * which provides the activity they draw in; the other targets need nothing.
 */
expect abstract class UiTest()

/**
 * Skips a Compose UI test class on wasmJs: the browser test runner does not serve the Compose resources, so
 * string resources never load there. The class still runs on the Android host and iOS.
 */
expect annotation class IgnoreOnWasm()
