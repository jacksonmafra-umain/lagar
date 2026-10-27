package app.lagar.domain

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import kotlin.test.Test
import kotlin.test.assertEquals

class ScopeTest {
    private val index = ApiIndex(
        apiVersion = 1,
        builtAt = "2026-10-27T00:00:00Z",
        layers = listOf(
            ApiLayer("fundamental", 4, emptyList()),
            ApiLayer("sfs", 100, listOf(ApiSeries("act", 48), ApiSeries("ordinance", 50), ApiSeries("other_statute", 2))),
        ),
    )

    @Test
    fun countSumsLayers() {
        assertEquals(102, index.count(Scope.Nationell))
    }

    @Test
    fun regionAndKommunCountZero() {
        assertEquals(0, index.count(Scope.Region))
        assertEquals(0, index.count(Scope.Kommun))
    }
}
