package app.lagar.settings

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ReduceTransparencyTest {
    @Test
    fun systemFollowsThePlatform() {
        assertTrue(ReduceTransparency.System.resolve(systemEnabled = true))
        assertFalse(ReduceTransparency.System.resolve(systemEnabled = false))
    }

    @Test
    fun onAndOffOverrideThePlatform() {
        assertTrue(ReduceTransparency.On.resolve(systemEnabled = false))
        assertFalse(ReduceTransparency.Off.resolve(systemEnabled = true))
    }
}
