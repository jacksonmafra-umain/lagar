package app.lagar.ui.shell

import androidx.compose.runtime.compositionLocalOf

/**
 * True inside the detail pane of a list-detail layout: a pushed screen shown there sits below the shell's top bar
 * and beside the list it was opened from, so its [app.lagar.ui.common.BackTopBar] drops the status bar inset and
 * the back button.
 */
internal val LocalDetailPane = compositionLocalOf { false }
