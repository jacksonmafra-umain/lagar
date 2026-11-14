package app.lagar.ui.tjanster

import app.lagar.data.ServiceSummary

/**
 * What the service detail screen shows: the catalogue entry [service], the [lead] paragraph of the official page as
 * the corpus keeps it (Swedish, never translated; null when the body has none), the day the page was last read and
 * where the service is offered for the user's chosen län and kommun ([place], null when it is not offered there).
 */
data class ServiceDetail(
    val service: ServiceSummary,
    val lead: String?,
    val fetchedOn: String?,
    val place: ServicePlace? = null,
)

/**
 * The lead paragraph of a service document body. The corpus writes a heading, the lead as published and a
 * `Källa:` link line, so every paragraph but the heading and the source line is kept, each joined onto one line.
 */
fun serviceLead(body: String): String? = body
    .split(Regex("\\n\\s*\\n"))
    .map { paragraph -> paragraph.lines().joinToString(" ") { it.trim() }.trim() }
    .filter { it.isNotEmpty() && !it.startsWith("#") && !it.startsWith(SOURCE_LINE) }
    .joinToString("\n\n")
    .ifEmpty { null }

/** The date part of a `fetched_at` timestamp (`2026-11-13T12:59:59Z` gives `2026-11-13`); null when it is blank. */
fun fetchDate(fetchedAt: String?): String? = fetchedAt?.substringBefore('T')?.takeIf { it.isNotBlank() }

/** Where "Gå till tjänsten" leads: the page where the service starts when there is one, else the official page. */
val ServiceSummary.startUrl: String get() = serviceUrl?.takeIf { it.isNotBlank() } ?: source

private const val SOURCE_LINE = "Källa:"
