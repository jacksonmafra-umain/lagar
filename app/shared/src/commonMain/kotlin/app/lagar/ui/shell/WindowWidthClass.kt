package app.lagar.ui.shell

import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.unit.Dp

/**
 * Width bands of the window, after the Material window size classes. Compact windows (phones in portrait) use the
 * bottom bar, medium windows (tablets, phones in landscape) a navigation rail, expanded windows the wide top bar.
 */
internal enum class WindowWidthClass {
    Compact,
    Medium,
    Expanded,
    ;

    companion object {
        fun of(width: Dp): WindowWidthClass = when {
            width < ShellDimens.MediumBreakpoint -> Compact
            width < ShellDimens.WideBreakpoint -> Medium
            else -> Expanded
        }
    }
}

/** Width class of the window the shell lays out in. Set by [AppShell]. */
internal val LocalWindowWidthClass = compositionLocalOf { WindowWidthClass.Compact }
