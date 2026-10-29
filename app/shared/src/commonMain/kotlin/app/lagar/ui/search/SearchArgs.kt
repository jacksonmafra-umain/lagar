package app.lagar.ui.search

import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.SortOrder
import app.lagar.domain.StatusFilter
import app.lagar.ui.navigation.Search
import kotlinx.datetime.LocalDate

private const val TYPE_SEPARATOR = ","

/** Default-valued filters are left out so a plain text search keeps the short route. */
internal fun SearchQuery.toRoute() = Search(
    text = text,
    types = types.takeIf { it.isNotEmpty() }?.sorted()?.joinToString(TYPE_SEPARATOR),
    from = from?.toString(),
    to = to?.toString(),
    mode = mode.takeIf { it != SearchMode.All }?.name,
    status = status.takeIf { it != StatusFilter.All }?.name,
    inForceFrom = inForceFrom?.toString(),
    inForceTo = inForceTo?.toString(),
    vacatioLegis = vacatioLegis,
    sort = sort.takeIf { it != SortOrder.Relevance }?.name,
)

/** Unknown or malformed values fall back to the default instead of failing, as a route may be stale. */
internal fun Search.toQuery() = SearchQuery(
    text = text,
    types = types?.split(TYPE_SEPARATOR)?.filter { it.isNotEmpty() }?.toSet().orEmpty(),
    from = parseDate(from.orEmpty()),
    to = parseDate(to.orEmpty()),
    mode = SearchMode.entries.firstOrNull { it.name == mode } ?: SearchMode.All,
    status = StatusFilter.entries.firstOrNull { it.name == status } ?: StatusFilter.All,
    inForceFrom = parseDate(inForceFrom.orEmpty()),
    inForceTo = parseDate(inForceTo.orEmpty()),
    vacatioLegis = vacatioLegis,
    sort = SortOrder.entries.firstOrNull { it.name == sort } ?: SortOrder.Relevance,
)

/** A valid `yyyy-mm-dd` date, or null. */
internal fun parseDate(input: String): LocalDate? =
    try {
        LocalDate.parse(input.trim())
    } catch (_: IllegalArgumentException) {
        null
    }
