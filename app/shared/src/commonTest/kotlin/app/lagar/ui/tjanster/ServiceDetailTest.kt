package app.lagar.ui.tjanster

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ServiceDetailTest {
    @Test
    fun leadIsTheBodyWithoutHeadingAndSourceLine() {
        val body = "# Förskola\n\n" +
            "Hemkommunen ska erbjuda förskola till barn som inte har börjat i skolan.\n" +
            "Här hittar du information om rätten till förskola.\n\n" +
            "Källa: [Skolverket](https://www.skolverket.se/forskola)\n"
        assertEquals(
            "Hemkommunen ska erbjuda förskola till barn som inte har börjat i skolan. Här hittar du information om rätten till förskola.",
            serviceLead(body),
        )
    }

    @Test
    fun aBodyWithoutLeadHasNone() {
        assertNull(serviceLead("# Förskola\n\nKälla: [Skolverket](https://www.skolverket.se/)\n"))
        assertNull(serviceLead(""))
    }

    @Test
    fun fetchDateIsTheDayOfTheTimestamp() {
        assertEquals("2026-11-13", fetchDate("2026-11-13T12:59:59Z"))
        assertNull(fetchDate(null))
        assertNull(fetchDate(""))
    }

    @Test
    fun startUrlIsTheServiceUrlWhenSetElseTheSource() {
        val plain = service("service-a", "A", "Skatteverket")
        assertEquals("https://example.se/service-a", plain.startUrl)
        assertEquals("https://e.example.se/start", plain.copy(serviceUrl = "https://e.example.se/start").startUrl)
        assertEquals("https://example.se/service-a", plain.copy(serviceUrl = " ").startUrl)
    }
}
