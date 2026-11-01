package app.lagar.ui.navigation

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class WebPathsTest {
    @Test
    fun writesReadablePaths() {
        assertEquals("/utforska", webPath(Utforska))
        assertEquals("/reader/sfs-1962-700", webPath(Reader("sfs-1962-700")))
        assertEquals("/reader/sfs-1962-700?p=k3p1", webPath(Reader("sfs-1962-700", "k3p1")))
        assertEquals("/ministries/sfs/statute", webPath(Ministries("sfs", "statute")))
        assertEquals("/search?q=hyra%20bostad&vacatioLegis=1", webPath(Search(text = "hyra bostad", vacatioLegis = true)))
        assertEquals("/layer/municipality?code=0180&codeName=Stockholms%20kommun", webPath(LayerList("municipality", code = "0180", codeName = "Stockholms kommun")))
    }

    @Test
    fun leavesTheSplashAndOnboardingOut() {
        assertNull(webPath(Splash))
        assertNull(webPath(OnboardingWelcome))
        assertNull(webPath(OnboardingScope))
    }

    @Test
    fun readsEveryRouteBack() {
        val routes = listOf(
            Utforska, Hierarki, Sparade, Tjanster, Settings, AdvancedSearch,
            Reader("sfs-1962-700"), Reader("sfs-1962-700", "k2ap4"),
            LayerList("sfs", "statute", ministry = "ju", ministryName = "Justitiedepartementet"),
            LayerList("region", code = "01", codeName = "Stockholms län"),
            Ministries("sfs", "ordinance"),
            Search(),
            Search(
                text = "miljö & hälsa?",
                types = "statute,ordinance",
                from = "2020-01-01",
                to = "2024-12-31",
                mode = "title",
                status = "in_force",
                inForceFrom = "2021-01-01",
                inForceTo = "2022-01-01",
                vacatioLegis = true,
                sort = "date",
            ),
        )
        for (route in routes) assertEquals(route, parseWebPath("#" + webPath(route)!!), "round trip of $route")
    }

    @Test
    fun acceptsTheFragmentWithOrWithoutHash() {
        assertEquals(Hierarki, parseWebPath("/hierarki"))
        assertEquals(Hierarki, parseWebPath("#/hierarki"))
        assertEquals(Hierarki, parseWebPath("#hierarki"))
    }

    @Test
    fun rejectsUnknownOrMalformedPaths() {
        assertNull(parseWebPath(""))
        assertNull(parseWebPath("#"))
        assertNull(parseWebPath("#/nowhere"))
        assertNull(parseWebPath("#/reader"))
        assertNull(parseWebPath("#/reader/a/b"))
        assertNull(parseWebPath("#/hierarki/extra"))
        assertNull(parseWebPath("#/ministries/sfs"))
    }

    @Test
    fun ignoresUnknownParametersAndKeepsBadEscapes() {
        assertEquals(Reader("sfs-1962-700", "k1p1"), parseWebPath("#/reader/sfs-1962-700?utm=x&p=k1p1"))
        assertEquals(Search(text = "100%"), parseWebPath("#/search?q=100%"))
        assertEquals(Search(text = "a b"), parseWebPath("#/search?q=a+b"))
    }

    @Test
    fun encodesUtf8() {
        assertEquals("%C3%A5%C3%A4%C3%B6", encode("åäö"))
        assertEquals("åäö", decode("%C3%A5%C3%A4%C3%B6"))
        assertEquals("Gävle kommun", decode(encode("Gävle kommun")))
    }
}
