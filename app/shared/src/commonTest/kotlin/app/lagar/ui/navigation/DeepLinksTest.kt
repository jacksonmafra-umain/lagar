package app.lagar.ui.navigation

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class DeepLinksTest {
    @Test
    fun buildsLinksWithAndWithoutAnchor() {
        assertEquals("https://jacksonmafra-umain.github.io/lagar/?doc=sfs-1962-700&p=k3p1", readerLink(WEB_APP_URL, "sfs-1962-700", "k3p1"))
        assertEquals("https://jacksonmafra-umain.github.io/lagar/?doc=sfs-1974-152", readerLink(WEB_APP_URL, "sfs-1974-152"))
    }

    @Test
    fun replacesTheQueryAndFragmentOfTheBase() {
        assertEquals("http://localhost:8080/?doc=sfs-1-1&p=p2", readerLink("http://localhost:8080/?sample&doc=x#top", "sfs-1-1", "p2"))
    }

    @Test
    fun parsesALinkBackIntoARoute() {
        assertEquals(Reader("sfs-1962-700", "k3p1"), parseReaderLink("?doc=sfs-1962-700&p=k3p1"))
        assertEquals(Reader("sfs-n2019-2"), parseReaderLink("doc=sfs-n2019-2"))
        assertEquals(Reader("sfs-1962-700", "k1p3-2"), parseReaderLink("?sample&p=k1p3-2&doc=sfs-1962-700"))
        val link = readerLink(WEB_APP_URL, "sfs-1962-700", "k2ap4")
        assertEquals(Reader("sfs-1962-700", "k2ap4"), parseReaderLink(link.substringAfter('?')))
    }

    @Test
    fun rejectsMissingOrInvalidValues() {
        assertNull(parseReaderLink(""))
        assertNull(parseReaderLink("?sample"))
        assertNull(parseReaderLink("?doc="))
        assertNull(parseReaderLink("?doc=../../etc"))
        assertNull(parseReaderLink("?doc=SFS-1962-700"))
        assertEquals(Reader("sfs-1962-700"), parseReaderLink("?doc=sfs-1962-700&p=%3Cscript%3E"))
    }
}
