package app.lagar.ui.hierarki

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.domain.DisplayLayer
import kotlin.test.Test
import kotlin.test.assertEquals

class LayerSummaryTest {
    private val index = ApiIndex(
        1,
        "2026-10-29T00:00:00Z",
        listOf(
            ApiLayer("fundamental", 4, emptyList()),
            ApiLayer("sfs", 100, listOf(ApiSeries("act", 48), ApiSeries("ordinance", 40), ApiSeries("other_statute", 12))),
            ApiLayer("case_law", 7, listOf(ApiSeries("case_report", 5), ApiSeries("case_notice", 2))),
        ),
    )

    @Test
    fun summariesFollowTheHierarchyAndAddUpToTheIndex() {
        val summaries = index.layerSummaries()
        assertEquals(DisplayLayer.entries, summaries.map { it.layer })
        assertEquals(index.layers.sumOf { it.count }, summaries.sumOf { it.count })
    }

    @Test
    fun sfsActsCarryTheOtherStatutesTheyInclude() {
        val acts = index.layerSummaries().single { it.layer == DisplayLayer.SfsAct }
        assertEquals(LayerSummary(DisplayLayer.SfsAct, 60, otherStatutes = 12), acts)
        assertEquals(0, index.layerSummaries().filter { it.layer != DisplayLayer.SfsAct }.sumOf { it.otherStatutes })
    }
}
