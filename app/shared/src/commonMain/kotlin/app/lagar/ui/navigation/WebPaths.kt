package app.lagar.ui.navigation

import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.toRoute

/*
 * The web app keeps each screen in the URL fragment (`#/reader/sfs-1962-700?p=k3p1`), so a refresh, a bookmark or a
 * copied address opens the same screen. A fragment never reaches the server, so the static hosting needs no rewrites.
 * The splash and onboarding have no path: they are never restored.
 */

/** The fragment path of [route] (without the `#`), or null for a screen that is not restored. */
fun webPath(route: Any): String? = when (route) {
    Utforska -> "/utforska"
    Hierarki -> "/hierarki"
    Sparade -> "/sparade"
    Tjanster -> "/tjanster"
    Settings -> "/settings"
    AdvancedSearch -> "/advanced-search"
    is Reader -> "/reader/${encode(route.id)}" + query("p" to route.anchor)
    is LayerList -> "/layer/${encode(route.layer)}" + query(
        "type" to route.type,
        "ministry" to route.ministry,
        "ministryName" to route.ministryName,
        "code" to route.code,
        "codeName" to route.codeName,
    )
    is Ministries -> "/ministries/${encode(route.layer)}/${encode(route.type)}"
    is Search -> "/search" + query(
        "q" to route.text.ifEmpty { null },
        "types" to route.types,
        "from" to route.from,
        "to" to route.to,
        "mode" to route.mode,
        "status" to route.status,
        "inForceFrom" to route.inForceFrom,
        "inForceTo" to route.inForceTo,
        "vacatioLegis" to if (route.vacatioLegis) "1" else null,
        "sort" to route.sort,
    )
    else -> null
}

/**
 * The route a fragment path asks for (with or without the leading `#`), or null when it names no screen.
 * Unknown query parameters are ignored, so an older or hand-edited address still opens what it can.
 */
fun parseWebPath(fragment: String): Any? {
    val path = fragment.removePrefix("#")
    val segments = path.substringBefore('?').split('/').filter { it.isNotEmpty() }.map(::decode)
    val params = parseQuery(path.substringAfter('?', missingDelimiterValue = ""))
    fun single(route: Any) = route.takeIf { segments.size == 1 }
    return when (segments.firstOrNull()) {
        "utforska" -> single(Utforska)
        "hierarki" -> single(Hierarki)
        "sparade" -> single(Sparade)
        "tjanster" -> single(Tjanster)
        "settings" -> single(Settings)
        "advanced-search" -> single(AdvancedSearch)
        "reader" -> segments.getOrNull(1)?.takeIf { segments.size == 2 }?.let { Reader(it, params["p"]) }
        "layer" -> segments.getOrNull(1)?.takeIf { segments.size == 2 }?.let {
            LayerList(it, params["type"], params["ministry"], params["ministryName"], params["code"], params["codeName"])
        }
        "ministries" -> if (segments.size == 3) Ministries(segments[1], segments[2]) else null
        "search" -> single(
            Search(
                text = params["q"].orEmpty(),
                types = params["types"],
                from = params["from"],
                to = params["to"],
                mode = params["mode"],
                status = params["status"],
                inForceFrom = params["inForceFrom"],
                inForceTo = params["inForceTo"],
                vacatioLegis = params["vacatioLegis"] == "1",
                sort = params["sort"],
            ),
        )
        else -> null
    }
}

/** The route of a back stack entry, for the screens [webPath] knows; null for the splash, onboarding and graphs. */
fun NavBackStackEntry.webRoute(): Any? {
    val destination = destination
    return when {
        destination.hasRoute<Utforska>() -> Utforska
        destination.hasRoute<Hierarki>() -> Hierarki
        destination.hasRoute<Sparade>() -> Sparade
        destination.hasRoute<Tjanster>() -> Tjanster
        destination.hasRoute<Settings>() -> Settings
        destination.hasRoute<AdvancedSearch>() -> AdvancedSearch
        destination.hasRoute<Reader>() -> toRoute<Reader>()
        destination.hasRoute<LayerList>() -> toRoute<LayerList>()
        destination.hasRoute<Ministries>() -> toRoute<Ministries>()
        destination.hasRoute<Search>() -> toRoute<Search>()
        else -> null
    }
}

private fun query(vararg pairs: Pair<String, String?>): String {
    val present = pairs.filter { it.second != null }
    if (present.isEmpty()) return ""
    return present.joinToString("&", prefix = "?") { (key, value) -> "$key=${encode(value!!)}" }
}

private fun parseQuery(query: String): Map<String, String> = query.split('&').mapNotNull { pair ->
    val key = pair.substringBefore('=')
    if (key.isEmpty()) null else key to decode(pair.substringAfter('=', missingDelimiterValue = ""))
}.toMap()

private const val UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
private const val HEX = "0123456789ABCDEF"

/** Percent-encodes everything but the URL's unreserved characters, as UTF-8. */
internal fun encode(value: String): String = buildString {
    for (byte in value.encodeToByteArray()) {
        val char = (byte.toInt() and 0xFF).toChar()
        if (char in UNRESERVED) {
            append(char)
        } else {
            val code = byte.toInt() and 0xFF
            append('%').append(HEX[code shr 4]).append(HEX[code and 0xF])
        }
    }
}

/** Reverses [encode]; `+` is read as a space, and a malformed escape is kept as it is. */
internal fun decode(value: String): String {
    val bytes = ArrayList<Byte>(value.length)
    var i = 0
    while (i < value.length) {
        val char = value[i]
        val escape = if (char == '%' && i + 2 < value.length) value.substring(i + 1, i + 3).toIntOrNull(16) else null
        when {
            escape != null -> {
                bytes.add(escape.toByte())
                i += 3
            }
            char == '+' -> {
                bytes.add(' '.code.toByte())
                i++
            }
            else -> {
                bytes.addAll(char.toString().encodeToByteArray().toList())
                i++
            }
        }
    }
    return bytes.toByteArray().decodeToString()
}
