package app.lagar.ui.common

import app.lagar.domain.DisplayLayer
import app.lagar.domain.DisplayLayerTest
import app.lagar.resources.Res
import app.lagar.resources.layer_fundamental_examples
import app.lagar.resources.layer_sfs_act_authority
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
    fun everyLevelHasItsOwnAuthorityAndExamples() {
        val authorities = DisplayLayer.entries.map { it.authorityRes() }
        val examples = DisplayLayer.entries.map { it.examplesRes() }
        assertEquals(DisplayLayer.entries.size, authorities.toSet().size)
        assertEquals(DisplayLayer.entries.size, examples.toSet().size)
        assertEquals(Res.string.layer_sfs_act_authority, DisplayLayer.SfsAct.authorityRes())
        assertEquals(Res.string.layer_fundamental_examples, DisplayLayer.Fundamental.examplesRes())
    }

    @Test
    fun unknownTypesReadAsOtherStatute() {
        assertEquals(Res.string.type_other_statute, typeNameRes("bylaw"))
    }
}
