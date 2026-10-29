package app.lagar.ui.home

import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.home_search_example
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class SearchExampleTest {
    @Test
    fun nationalLawsAreOnlyTheNationellExample() {
        assertEquals(Res.string.home_search_example, Scope.Nationell.searchExampleRes())
        assertNotEquals(Res.string.home_search_example, Scope.Region.searchExampleRes())
        assertNotEquals(Res.string.home_search_example, Scope.Kommun.searchExampleRes())
        assertNotEquals(Scope.Region.searchExampleRes(), Scope.Kommun.searchExampleRes())
    }
}
