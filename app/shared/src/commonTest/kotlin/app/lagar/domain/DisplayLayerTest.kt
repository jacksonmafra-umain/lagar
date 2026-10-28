package app.lagar.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class DisplayLayerTest {
    @Test
    fun everyDisplayLayerRoundTripsThroughItsRoute() {
        DisplayLayer.entries.forEach {
            assertEquals(it, DisplayLayer.fromRoute(it.apiLayer, it.apiType))
        }
    }

    @Test
    fun sfsIsSplitByType() {
        assertEquals(DisplayLayer.SfsAct, DisplayLayer.fromRoute("sfs", "act"))
        assertEquals(DisplayLayer.SfsOrdinance, DisplayLayer.fromRoute("sfs", "ordinance"))
    }

    @Test
    fun untypedLayersIgnoreTheType() {
        assertEquals(DisplayLayer.Fundamental, DisplayLayer.fromRoute("fundamental", "fundamental_law"))
    }

    @Test
    fun unknownRoutesHaveNoLayer() {
        assertNull(DisplayLayer.fromRoute("sfs", null))
        assertNull(DisplayLayer.fromRoute("sfs", "bylaw"))
        assertNull(DisplayLayer.fromRoute("nope", null))
    }
}
