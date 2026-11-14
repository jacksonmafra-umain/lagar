package app.lagar.ui.tjanster

import app.lagar.domain.Locality
import kotlin.test.Test
import kotlin.test.assertEquals

class ServiceFiltersTest {
    private val stockholm = ServiceLocality("01", "Stockholms län", "0180", "Stockholm")

    @Test
    fun nationalServicesAreAlwaysListed() {
        val entries = serviceEntries(sampleServices, ServiceLocality.None)
        assertEquals(
            listOf(ServicePlace.National, ServicePlace.National),
            entries.filter { !it.service.template }.map { it.place },
        )
    }

    @Test
    fun templatesCarryTheChosenNames() {
        val places = serviceEntries(sampleServices, stockholm).associate { it.service.id to it.place }
        assertEquals(ServicePlace.Kommun("Stockholm"), places["service-bygglov"])
        assertEquals(ServicePlace.Region("Stockholms län"), places["service-vardgaranti"])
    }

    @Test
    fun templatesWithoutAChoiceHaveNoName() {
        val places = serviceEntries(sampleServices, ServiceLocality.None).associate { it.service.id to it.place }
        assertEquals(ServicePlace.Kommun(null), places["service-bygglov"])
        assertEquals(ServicePlace.Region(null), places["service-vardgaranti"])
    }

    @Test
    fun localServicesOnlyForTheChosenLocality() {
        val own = service("service-0180-parkering", "Boendeparkering", "Stockholms stad", scope = "municipality", municipalityCode = "0180")
        val other = service("service-1480-parkering", "Boendeparkering", "Göteborgs stad", scope = "municipality", municipalityCode = "1480")
        val unknown = service("service-x", "X", "Y", scope = "galaxy")
        val ids = serviceEntries(listOf(own, other, unknown), stockholm).map { it.service.id }
        assertEquals(listOf("service-0180-parkering"), ids)
        assertEquals(emptyList(), serviceEntries(listOf(own), ServiceLocality.None))
    }

    @Test
    fun codeWithoutNameCountsAsNotChosen() {
        val chosen = ServiceLocality.of(Locality("01", "9999"), regionName = "Stockholms län", kommunName = null)
        assertEquals(ServiceLocality("01", "Stockholms län", null, null), chosen)
    }

    @Test
    fun filtersByWordsInTitleOrIssuer() {
        val entries = serviceEntries(sampleServices, stockholm)
        assertEquals(listOf("service-foraldrapenning"), ids(entries, ServiceFilter(query = "försäkrings")))
        assertEquals(listOf("service-f-skatt"), ids(entries, ServiceFilter(query = "  skatteverket F-SKATT ")))
        assertEquals(emptyList(), ids(entries, ServiceFilter(query = "skatteverket bygglov")))
    }

    @Test
    fun filtersByTopicAndAudience() {
        val entries = serviceEntries(sampleServices, stockholm)
        assertEquals(listOf("service-vardgaranti"), ids(entries, ServiceFilter(topic = ServiceTopic.Health)))
        assertEquals(listOf("service-f-skatt", "service-bygglov"), ids(entries, ServiceFilter(audience = ServiceAudience.Business)))
        assertEquals(
            listOf("service-bygglov"),
            ids(entries, ServiceFilter(topic = ServiceTopic.Housing, audience = ServiceAudience.Business)),
        )
        assertEquals(4, ids(entries, ServiceFilter()).size)
    }

    @Test
    fun topicKeysMatchTheVocabulary() {
        assertEquals(
            listOf(
                "family", "work", "business", "housing", "health", "tax", "vehicles", "education", "migration",
                "social_support", "environment", "legal",
            ),
            ServiceTopic.entries.map { it.key },
        )
    }

    private fun ids(entries: List<ServiceEntry>, filter: ServiceFilter) = filterServices(entries, filter).map { it.service.id }
}
