package app.lagar.designsystem

import kotlin.test.Test
import kotlin.test.assertEquals

class GlassFillTest {
    @Test
    fun cardIsTranslucentWithoutBlur() {
        assertEquals(GlassFill.Translucent, glassFill(GlassTier.Card, hasBlurSource = false, reduceTransparency = false))
        assertEquals(GlassFill.Translucent, glassFill(GlassTier.Card, hasBlurSource = true, reduceTransparency = false))
    }

    @Test
    fun barsAndOverlaysBlurWhenThereIsContentBehind() {
        assertEquals(GlassFill.Blurred, glassFill(GlassTier.Bar, hasBlurSource = true, reduceTransparency = false))
        assertEquals(GlassFill.Blurred, glassFill(GlassTier.Overlay, hasBlurSource = true, reduceTransparency = false))
    }

    @Test
    fun barsAndOverlaysWithNothingToBlurAreOpaque() {
        assertEquals(GlassFill.Opaque, glassFill(GlassTier.Bar, hasBlurSource = false, reduceTransparency = false))
        assertEquals(GlassFill.Opaque, glassFill(GlassTier.Overlay, hasBlurSource = false, reduceTransparency = false))
    }

    @Test
    fun reduceTransparencyMakesEveryTierOpaque() {
        GlassTier.entries.forEach { tier ->
            assertEquals(GlassFill.Opaque, glassFill(tier, hasBlurSource = true, reduceTransparency = true))
            assertEquals(GlassFill.Opaque, glassFill(tier, hasBlurSource = false, reduceTransparency = true))
        }
    }
}
