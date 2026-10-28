package app.lagar.ui.common

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance

/** White or near-black, whichever is more legible on this fill (all nine layers clear 3:1 either way). */
internal fun Color.iconColor(): Color = if (luminance() > ICON_SWITCH_LUMINANCE) DarkIcon else Color.White

private val DarkIcon = Color(0xFF14181F)

// Luminance where white and near-black give equal contrast on a fill (about 0.18).
private const val ICON_SWITCH_LUMINANCE = 0.18f
