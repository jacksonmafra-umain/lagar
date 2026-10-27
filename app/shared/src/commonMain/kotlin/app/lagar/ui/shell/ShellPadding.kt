package app.lagar.ui.shell

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.runtime.compositionLocalOf

/** Space taken by the floating top and bottom bars; screens apply it as content padding. */
internal val LocalShellPadding = compositionLocalOf { PaddingValues() }
