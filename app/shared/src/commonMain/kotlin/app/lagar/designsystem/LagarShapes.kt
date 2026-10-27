package app.lagar.designsystem

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import app.lagar.designsystem.generated.RadiusTokens

/** `default` (8dp) for chips and buttons, `lg` (16dp) for cards, `xl` (24dp) for overlays and sheets. */
internal fun lagarShapes(): Shapes = Shapes(
    extraSmall = RoundedCornerShape(RadiusTokens.sm),
    small = RoundedCornerShape(RadiusTokens.default),
    medium = RoundedCornerShape(RadiusTokens.md),
    large = RoundedCornerShape(RadiusTokens.lg),
    extraLarge = RoundedCornerShape(RadiusTokens.xl),
)
