package app.lagar.ui.home

import app.lagar.domain.DisplayLayer
import app.lagar.settings.UserFocus
import kotlin.test.Test
import kotlin.test.assertEquals

class KeyLawGroupOrderTest {
    @Test
    fun citizensAndStudentsGetTheHierarchyOrder() {
        val hierarchy = listOf(DisplayLayer.Fundamental, DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance)
        assertEquals(hierarchy, keyLawGroupOrder(UserFocus.Citizen))
        assertEquals(hierarchy, keyLawGroupOrder(UserFocus.Student))
    }

    @Test
    fun lawyersGetActsAndOrdinancesFirst() {
        assertEquals(listOf(DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance, DisplayLayer.Fundamental), keyLawGroupOrder(UserFocus.Lawyer))
    }

    @Test
    fun everyFocusShowsTheSameGroups() {
        UserFocus.entries.forEach { assertEquals(keyLawGroupOrder(UserFocus.Citizen).toSet(), keyLawGroupOrder(it).toSet()) }
    }
}
