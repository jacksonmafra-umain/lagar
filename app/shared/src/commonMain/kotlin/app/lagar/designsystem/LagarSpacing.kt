package app.lagar.designsystem

import androidx.compose.runtime.Immutable
import androidx.compose.ui.unit.Dp
import app.lagar.designsystem.generated.SpacingTokens

@Immutable
data class LagarSpacing(
    val gutter: Dp = SpacingTokens.gutter,
    val gutterMobile: Dp = SpacingTokens.gutterMobile,
    val margin: Dp = SpacingTokens.margin,
    val marginMobile: Dp = SpacingTokens.marginMobile,
    val xs: Dp = SpacingTokens.spaceXs,
    val sm: Dp = SpacingTokens.spaceSm,
    val md: Dp = SpacingTokens.spaceMd,
    val lg: Dp = SpacingTokens.spaceLg,
    val xl: Dp = SpacingTokens.spaceXl,
)
