package app.lagar.ui.shell

import androidx.compose.ui.unit.dp

/** Component sizes of the shell; spacing between elements comes from `LagarTheme.spacing`. */
internal object ShellDimens {
    val TouchTarget = 48.dp
    val TabMinHeight = 56.dp
    val TopBarMinHeight = 64.dp
    val DrawerWidth = 320.dp
    val IconSize = 24.dp
    val SmallIconSize = 20.dp
    val AvatarSize = 32.dp
    val DrawerLogoSize = 40.dp
    val Hairline = 1.dp
    val ActiveBorder = 2.dp
    val TextGap = 2.dp
    val PillPaddingVertical = 6.dp

    /** Window width from which the desktop layout is used. */
    val WideBreakpoint = 1024.dp

    /** Bar width from which the wide top bar has room for the scope switch. */
    val FullScopeSwitchWidth = 1360.dp

    /** Bar width from which the wide top bar's search button shows its label (when the scope switch is hidden). */
    val SearchLabelWidth = 1200.dp
    val MaxContentWidth = 1280.dp
    val LogoSize = 40.dp
}
