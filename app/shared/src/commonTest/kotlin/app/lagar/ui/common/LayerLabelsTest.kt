package app.lagar.ui.common

import app.lagar.domain.DisplayLayerTest
import app.lagar.resources.Res
import app.lagar.resources.type_case_report
import app.lagar.resources.type_eu_directive
import app.lagar.resources.type_municipal_regulation
import app.lagar.resources.type_other_statute
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class LayerLabelsTest {
    @Test
    fun everyApiTypeHasItsOwnName() {
        val names = DisplayLayerTest.API_TYPES.keys.map(::typeNameRes)
        assertEquals(names.size, names.toSet().size)
        DisplayLayerTest.API_TYPES.keys.filter { it != "other_statute" }.forEach {
            assertNotEquals(Res.string.type_other_statute, typeNameRes(it), it)
        }
    }

    @Test
    fun newTypesUseTheirNames() {
        assertEquals(Res.string.type_case_report, typeNameRes("case_report"))
        assertEquals(Res.string.type_eu_directive, typeNameRes("eu_directive"))
        assertEquals(Res.string.type_municipal_regulation, typeNameRes("municipal_regulation"))
    }

    @Test
    fun unknownTypesReadAsOtherStatute() {
        assertEquals(Res.string.type_other_statute, typeNameRes("bylaw"))
    }
}
