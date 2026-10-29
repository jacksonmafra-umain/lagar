@file:Suppress("UNUSED_PARAMETER")

package app.lagar.ui.common

import androidx.compose.runtime.Composable

internal actual fun searchShortcutKeys(): ShortcutKeys? = null

@Composable
internal actual fun SearchShortcutEffect(onTrigger: () -> Unit) = Unit
