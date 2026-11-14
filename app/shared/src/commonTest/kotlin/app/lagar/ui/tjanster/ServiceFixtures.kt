package app.lagar.ui.tjanster

import app.lagar.data.ServiceSummary

/** A service of the test catalogue; only the fields the Tjänster tab reads matter. */
internal fun service(
    id: String,
    title: String,
    issuer: String,
    audience: List<String> = listOf("private"),
    topics: List<String> = emptyList(),
    scope: String = "national",
    template: Boolean = false,
    regionCode: String? = null,
    municipalityCode: String? = null,
) = ServiceSummary(
    id = id,
    title = title,
    issuer = issuer,
    audience = audience,
    topics = topics,
    channels = listOf("online"),
    scope = scope,
    template = template,
    regionCode = regionCode,
    municipalityCode = municipalityCode,
    source = "https://example.se/$id",
    basedOn = emptyList(),
)

/** Two national services, a kommun template and a region template, as in the corpus. */
internal val sampleServices = listOf(
    service("service-foraldrapenning", "Föräldrapenning", "Försäkringskassan", topics = listOf("family", "work")),
    service("service-f-skatt", "Ansök om F-skatt", "Skatteverket", audience = listOf("business"), topics = listOf("business", "tax")),
    service("service-bygglov", "Bygglov", "Kommunen", audience = listOf("private", "business"), topics = listOf("housing"), scope = "municipality", template = true),
    service("service-vardgaranti", "Vårdgaranti", "Regionen", topics = listOf("health"), scope = "region", template = true),
)
