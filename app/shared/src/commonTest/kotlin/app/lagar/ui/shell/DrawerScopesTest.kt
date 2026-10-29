package app.lagar.ui.shell

import app.lagar.domain.Locality
import app.lagar.domain.Scope
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class DrawerScopesTest {
    private val none = Locality(null, null)
    private val regionOnly = Locality("01", null)
    private val full = Locality("01", "0114")

    @Test
    fun nationellSwitchesInOneTap() {
        assertEquals(DrawerScopeAction.Apply(Scope.Nationell), drawerScopeAction(Scope.Nationell, Scope.Kommun, none))
    }

    @Test
    fun regionWithStoredLanSwitchesInOneTap() {
        assertEquals(DrawerScopeAction.Apply(Scope.Region), drawerScopeAction(Scope.Region, Scope.Nationell, regionOnly))
    }

    @Test
    fun regionWithoutLanOpensTheSheet() {
        assertEquals(DrawerScopeAction.OpenSheet(Scope.Region), drawerScopeAction(Scope.Region, Scope.Nationell, none))
    }

    @Test
    fun kommunNeedsAStoredKommun() {
        assertEquals(DrawerScopeAction.OpenSheet(Scope.Kommun), drawerScopeAction(Scope.Kommun, Scope.Nationell, regionOnly))
        assertEquals(DrawerScopeAction.Apply(Scope.Kommun), drawerScopeAction(Scope.Kommun, Scope.Region, full))
    }

    @Test
    fun theActiveScopeOpensTheSheetToChangeItsLocality() {
        Scope.entries.forEach { assertEquals(DrawerScopeAction.OpenSheet(it), drawerScopeAction(it, it, full)) }
    }

    @Test
    fun savedBadgeHidesAtZero() {
        assertNull(savedBadgeCount(0))
        assertEquals(1, savedBadgeCount(1))
        assertEquals(12, savedBadgeCount(12))
    }
}
