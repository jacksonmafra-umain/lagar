package app.lagar.domain

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
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

    @Test
    fun everyApiTypeMapsToTheLevelOfItsLayer() {
        API_TYPES.forEach { (type, layer) ->
            val level = DisplayLayer.forType(type)
            if (type == "other_statute" || type == "treaty") {
                assertNull(level)
            } else {
                assertEquals(DisplayLayer.fromRoute(layer, type), level, type)
                assertEquals(layer, level?.apiLayer, type)
            }
        }
    }

    @Test
    fun newLayerTypesHaveTheirOwnLevel() {
        assertEquals(DisplayLayer.CaseLaw, DisplayLayer.forType("case_report"))
        assertEquals(DisplayLayer.CaseLaw, DisplayLayer.forType("case_notice"))
        assertEquals(DisplayLayer.Eu, DisplayLayer.forType("eu_regulation"))
        assertEquals(DisplayLayer.Eu, DisplayLayer.forType("eu_directive"))
        assertEquals(DisplayLayer.Eu, DisplayLayer.forType("eu_decision"))
        assertEquals(DisplayLayer.Eu, DisplayLayer.forType("eu_judgment"))
        assertEquals(DisplayLayer.Agency, DisplayLayer.forType("agency_regulation"))
        assertEquals(DisplayLayer.Region, DisplayLayer.forType("county_regulation"))
        assertEquals(DisplayLayer.Municipality, DisplayLayer.forType("municipal_regulation"))
        assertNull(DisplayLayer.forType("bylaw"))
    }

    @Test
    fun sfsActsCountIncludesTheOtherStatutes() {
        val index = ApiIndex(
            1,
            "2026-10-29T00:00:00Z",
            listOf(
                ApiLayer("fundamental", 4, emptyList()),
                ApiLayer("sfs", 100, listOf(ApiSeries("act", 48), ApiSeries("ordinance", 40), ApiSeries("other_statute", 12))),
            ),
        )
        assertEquals(60, index.count(DisplayLayer.SfsAct))
        assertEquals(40, index.count(DisplayLayer.SfsOrdinance))
        assertEquals(12, index.otherStatuteCount())
        assertEquals(4, index.count(DisplayLayer.Fundamental))
        // Every SFS document is counted once across the levels.
        assertEquals(104, DisplayLayer.entries.sumOf { index.count(it) })
    }

    @Test
    fun countsWithoutOtherStatutesAreUnchanged() {
        val index = ApiIndex(1, "2026-10-29T00:00:00Z", listOf(ApiLayer("sfs", 6, listOf(ApiSeries("act", 6)))))
        assertEquals(6, index.count(DisplayLayer.SfsAct))
        assertEquals(0, index.otherStatuteCount())
    }

    @Test
    fun onlySfsSeriesHaveAMinistryIndex() {
        assertEquals(
            listOf(DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance),
            DisplayLayer.entries.filter { it.hasMinistryIndex },
        )
    }

    companion object {
        /** The API's closed type vocabulary (docs/api.md), type to layer. */
        val API_TYPES = mapOf(
            "fundamental_law" to "fundamental",
            "act" to "sfs",
            "ordinance" to "sfs",
            "other_statute" to "sfs",
            "treaty" to "sfs",
            "agency_regulation" to "agency",
            "case_report" to "case_law",
            "case_notice" to "case_law",
            "eu_regulation" to "eu",
            "eu_directive" to "eu",
            "eu_decision" to "eu",
            "eu_judgment" to "eu",
            "county_regulation" to "region",
            "municipal_regulation" to "municipality",
        )
    }
}
