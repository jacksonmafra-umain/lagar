package app.lagar.ui.reader

import app.lagar.data.Amendment
import app.lagar.data.DocumentMeta
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class AmendmentRowsTest {
    private fun meta(amendedBy: List<String> = emptyList(), amendments: List<Amendment>? = null) = DocumentMeta(
        id = "sfs-1962-700", title = "Brottsbalk", type = "act", layer = "sfs", number = "1962:700",
        issued = null, repealed = null, amendedBy = amendedBy, ministry = null, eli = null, language = "sv",
        authoritative = false, source = "https://example.org", sourceSha256 = "", fetchedAt = "", amendments = amendments,
    )

    @Test
    fun prefersTheRegisterList() {
        val rows = amendmentRows(
            meta(
                amendedBy = listOf("1983:240"),
                amendments = listOf(
                    Amendment("1970:225", title = "Lag (1970:225) om ändring i brottsbalken", scope = "ändr. 3 kap 1 §", inForce = "1970-07-01"),
                    Amendment("1983:240", inForce = "1983-07-01", inForceRaw = "1983-07-01 överg.best."),
                    Amendment("2026:1", inForceRaw = "den dag regeringen bestämmer"),
                ),
            ),
        )
        assertEquals(
            listOf(
                AmendmentRow("1970:225", "Lag (1970:225) om ändring i brottsbalken", "1970-07-01", "ändr. 3 kap 1 §"),
                AmendmentRow("1983:240", inForce = "1983-07-01 överg.best."),
                AmendmentRow("2026:1", inForce = "den dag regeringen bestämmer"),
            ),
            rows,
        )
    }

    @Test
    fun fallsBackToAmendedByWhenTheRegisterIsMissingOrEmpty() {
        val expected = listOf(AmendmentRow("1970:225"), AmendmentRow("1983:240"))
        assertEquals(expected, amendmentRows(meta(amendedBy = listOf("1970:225", "1983:240"))))
        assertEquals(expected, amendmentRows(meta(amendedBy = listOf("1970:225", "1983:240"), amendments = emptyList())))
        assertEquals(emptyList(), amendmentRows(meta()))
    }

    @Test
    fun derivesCorpusIdsFromSfsNumbers() {
        assertEquals("sfs-1983-240", sfsDocumentId("1983:240"))
        assertEquals("sfs-n2019-2", sfsDocumentId("N2019:2"))
        assertNull(sfsDocumentId("Prop. 1975/76:209"))
        assertNull(sfsDocumentId("83:240"))
    }
}
