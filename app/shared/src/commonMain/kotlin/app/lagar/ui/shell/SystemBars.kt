package app.lagar.ui.shell

import androidx.compose.runtime.Composable

/**
 * Makes the status and navigation bar content (clock, battery, home indicator) readable on the
 * app's own surface. [darkTheme] is the resolved app theme, which can differ from the system theme.
 */
@Composable
internal expect fun SystemBarAppearance(darkTheme: Boolean)
