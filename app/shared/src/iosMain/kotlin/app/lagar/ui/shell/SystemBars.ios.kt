package app.lagar.ui.shell

import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.uikit.LocalUIViewController
import platform.UIKit.UIUserInterfaceStyle

@Composable
internal actual fun SystemBarAppearance(darkTheme: Boolean) {
    val controller = LocalUIViewController.current
    // Forcing the interface style makes the automatic status bar style follow the app theme.
    SideEffect {
        controller.overrideUserInterfaceStyle = if (darkTheme) {
            UIUserInterfaceStyle.UIUserInterfaceStyleDark
        } else {
            UIUserInterfaceStyle.UIUserInterfaceStyleLight
        }
    }
}
