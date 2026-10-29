package app.lagar.ui.reader

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.Catalog
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Loads one document; a failure becomes [LoadState.Failed] whose retry reloads it. [linkedAmendments]
 * holds the amending SFS numbers that the API also publishes as documents, so the reader can link them;
 * [crossReferences] does the same for the documents the body cites. [work] scans the body for citations.
 */
class ReaderViewModel(
    private val repository: LagarRepository,
    private val catalog: Catalog,
    private val id: String,
    private val work: CoroutineDispatcher = Dispatchers.Default,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<DocumentResponse>>(LoadState.Loading)
    val state: StateFlow<LoadState<DocumentResponse>> = _state.asStateFlow()

    private val _linkedAmendments = MutableStateFlow<Map<String, String>>(emptyMap())

    /** Amending SFS number to the id of its document, for the numbers whose document exists. */
    val linkedAmendments: StateFlow<Map<String, String>> = _linkedAmendments.asStateFlow()

    private val _crossReferences = MutableStateFlow<Map<String, String>>(emptyMap())

    /**
     * Id to API `type` of each document the body cites that the API publishes; the reader links those
     * citations and colors them by the type's layer. Empty until resolved, and when the lookup fails.
     */
    val crossReferences: StateFlow<Map<String, String>> = _crossReferences.asStateFlow()

    private var job: Job? = null
    private var linkJob: Job? = null

    init {
        load()
    }

    private fun load() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            val document = try {
                repository.document(id)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _state.value = LoadState.Failed(retry = ::load)
                return@launch
            }
            _state.value = LoadState.Loaded(document)
            resolveCrossReferences(document.body)
        }
    }

    /**
     * Finds the documents [body] cites and keeps those the API publishes, through the national catalog
     * (shared with search and the amendment links, so it is loaded at most once per process). On failure
     * the citations stay plain text.
     */
    private suspend fun resolveCrossReferences(body: String) {
        val cited = withContext(work) { citedDocumentIds(body) } - id
        if (cited.isEmpty()) return
        try {
            val known = catalog.items(Scope.Nationell).associateBy({ it.id }, { it.type })
            _crossReferences.value = cited.mapNotNull { target -> known[target]?.let { target to it } }.toMap()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
        }
    }

    /**
     * Looks up which of [numbers] the API has as documents, through the national catalog (shared with
     * search, so it is loaded at most once per process). Runs once; on failure the numbers stay plain text
     * and the next call tries again.
     */
    fun resolveAmendmentLinks(numbers: List<String>) {
        if (linkJob?.isActive == true || _linkedAmendments.value.isNotEmpty()) return
        val candidates = numbers.mapNotNull { number -> sfsDocumentId(number)?.takeIf { it != id }?.let { number to it } }
        if (candidates.isEmpty()) return
        linkJob = viewModelScope.launch {
            try {
                val known = catalog.items(Scope.Nationell).mapTo(HashSet()) { it.id }
                _linkedAmendments.value = candidates.filter { it.second in known }.toMap()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
            }
        }
    }
}
