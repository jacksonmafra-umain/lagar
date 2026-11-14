package app.lagar.ui.tjanster

import app.lagar.data.ServiceSummary
import app.lagar.domain.Locality

/** The life-event topics of the service vocabulary, in the order the chips show them; [key] is the API value. */
enum class ServiceTopic(val key: String) {
    Family("family"),
    Work("work"),
    Business("business"),
    Housing("housing"),
    Health("health"),
    Tax("tax"),
    Vehicles("vehicles"),
    Education("education"),
    Migration("migration"),
    SocialSupport("social_support"),
    Environment("environment"),
    Legal("legal"),
}

/** Who a service is for: everyone ([All]), private individuals or businesses; [key] is the API value. */
enum class ServiceAudience(val key: String?) {
    All(null),
    Private("private"),
    Business("business"),
}

/**
 * Where a service is offered, as its card badge shows it. [Region] and [Kommun] carry the name of the user's chosen
 * län or kommun, or null when none is chosen (the badge then reads "your county" / "your municipality"). A template
 * kommun service also carries the chosen kommun's [Kommun.website], which [KommunLink] opens; null when the kommun has
 * none listed or none is chosen.
 */
sealed interface ServicePlace {
    data object National : ServicePlace

    data class Region(val name: String?) : ServicePlace

    data class Kommun(val name: String?, val website: String? = null) : ServicePlace
}

/** One card of the Tjänster tab: the [service] and where it is offered. */
data class ServiceEntry(val service: ServiceSummary, val place: ServicePlace)

/**
 * The user's chosen län and kommun with their names, which label the template services, and the kommun's website,
 * which template kommun services link to. A code whose name is unknown (not in the bundled geo file) counts as not
 * chosen, and so has no website.
 */
data class ServiceLocality(
    val regionCode: String? = null,
    val regionName: String? = null,
    val kommunCode: String? = null,
    val kommunName: String? = null,
    val kommunWebsite: String? = null,
) {
    companion object {
        val None = ServiceLocality()

        fun of(locality: Locality, regionName: String?, kommunName: String?, kommunWebsite: String? = null) = ServiceLocality(
            regionCode = locality.regionCode.takeIf { regionName != null },
            regionName = regionName,
            kommunCode = locality.kommunCode.takeIf { kommunName != null },
            kommunName = kommunName,
            kommunWebsite = kommunWebsite.takeIf { kommunName != null },
        )
    }
}

/**
 * The services the tab lists for [locality], in catalogue order. National services are always listed. A template
 * service (one every region or kommun must offer) is listed for everyone and labelled with the chosen län or
 * kommun; a kommun template also carries the chosen kommun's website. A service of one region or kommun is listed only
 * when it is the chosen one; an unknown scope is skipped.
 */
fun serviceEntries(services: List<ServiceSummary>, locality: ServiceLocality): List<ServiceEntry> = services.mapNotNull { service ->
    val place = when (service.scope) {
        SCOPE_NATIONAL -> ServicePlace.National
        SCOPE_REGION -> when {
            service.template -> ServicePlace.Region(locality.regionName)
            locality.regionCode != null && service.regionCode == locality.regionCode -> ServicePlace.Region(locality.regionName)
            else -> null
        }
        SCOPE_MUNICIPALITY -> when {
            service.template -> ServicePlace.Kommun(locality.kommunName, locality.kommunWebsite)
            locality.kommunCode != null && service.municipalityCode == locality.kommunCode -> ServicePlace.Kommun(locality.kommunName)
            else -> null
        }
        else -> null
    }
    place?.let { ServiceEntry(service, it) }
}

/** What the user filters the list by: free text over title and issuer, one topic (or none) and the audience. */
data class ServiceFilter(
    val query: String = "",
    val topic: ServiceTopic? = null,
    val audience: ServiceAudience = ServiceAudience.All,
)

/**
 * The [entries] that pass [filter]: every word of the query appears, ignoring case, in the title or the issuer, and
 * the service has the topic and is for the audience. Order is kept.
 */
fun filterServices(entries: List<ServiceEntry>, filter: ServiceFilter): List<ServiceEntry> {
    val words = filter.query.lowercase().split(' ').filter { it.isNotBlank() }
    return entries.filter { entry ->
        val service = entry.service
        val haystack = "${service.title} ${service.issuer}".lowercase()
        words.all { it in haystack } &&
            (filter.topic == null || filter.topic.key in service.topics) &&
            (filter.audience.key == null || filter.audience.key in service.audience)
    }
}

private const val SCOPE_NATIONAL = "national"
private const val SCOPE_REGION = "region"
private const val SCOPE_MUNICIPALITY = "municipality"
