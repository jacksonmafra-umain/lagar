package app.lagar.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.backhandler.BackHandler
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavHostController
import androidx.navigation.NavOptionsBuilder
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.toRoute
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.domain.count
import app.lagar.resources.Res
import app.lagar.settings.BookmarkStore
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.SearchShortcutEffect
import app.lagar.ui.hierarki.HierarkiRoute
import app.lagar.ui.hierarki.MinistriesRoute
import app.lagar.ui.home.HomeRoute
import app.lagar.ui.home.ScopeSheet
import app.lagar.ui.list.LayerListRoute
import app.lagar.ui.list.LocalityFilter
import app.lagar.ui.list.MinistryFilter
import app.lagar.ui.navigation.AdvancedSearch
import app.lagar.ui.navigation.Hierarki
import app.lagar.ui.navigation.LayerList
import app.lagar.ui.navigation.Ministries
import app.lagar.ui.navigation.OnboardingScope
import app.lagar.ui.navigation.OnboardingWelcome
import app.lagar.ui.navigation.Reader
import app.lagar.ui.navigation.Search
import app.lagar.ui.navigation.Settings
import app.lagar.ui.navigation.Sparade
import app.lagar.ui.navigation.Splash
import app.lagar.ui.navigation.Tjanster
import app.lagar.ui.navigation.Utforska
import app.lagar.ui.onboarding.OnboardingViewModel
import app.lagar.ui.onboarding.ScopeStepRoute
import app.lagar.ui.onboarding.SplashRoute
import app.lagar.ui.onboarding.WelcomeRoute
import app.lagar.ui.reader.ReaderRoute
import app.lagar.ui.search.AdvancedSearchRoute
import app.lagar.ui.search.SearchRoute
import app.lagar.ui.search.toRoute
import app.lagar.ui.settings.SettingsRoute
import app.lagar.ui.sparade.SparadeRoute
import app.lagar.ui.tjanster.TjansterScreen
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel

/**
 * Four-tab shell. The [navController] and [hazeState] are owned by the caller, above the locale
 * provider, so a language switch keeps the back stack. [startLink] (a shared web link) opens once the
 * splash is done.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AppShell(
    navController: NavHostController,
    hazeState: HazeState,
    onToggleTheme: () -> Unit,
    startLink: Reader? = null,
) {
    val scope = rememberCoroutineScope()
    val preferences = koinInject<UserPreferences>()
    val activeScope by preferences.scope.collectAsState()
    val locality by preferences.locality.collectAsState()
    val geo = koinInject<GeoRepository>()
    val localityNames by produceState(emptyMap<Scope, String?>(), locality) {
        value = Scope.entries.associateWith { geo.localityName(it, locality) }
    }
    val repository = koinInject<LagarRepository>()
    // Counts are decoration: a failed index load just hides the badges.
    val scopeCounts by produceState<Map<Scope, Int>?>(null) {
        value = try {
            val index = repository.index()
            Scope.entries.associateWith { index.count(it) }
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }
    val bookmarks by koinInject<BookmarkStore>().bookmarks.collectAsState()
    var showScopeSheet by remember { mutableStateOf(false) }
    var sheetScope by remember { mutableStateOf<Scope?>(null) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val backStackEntry by navController.currentBackStackEntryAsState()
    val destination = backStackEntry?.destination
    val selectedTab = Tab.entries.firstOrNull { destination?.hasRoute(it.route::class) == true }

    val density = LocalDensity.current
    var topBarPx by remember { mutableStateOf(0) }
    var bottomBarPx by remember { mutableStateOf(0) }
    var widthPx by remember { mutableStateOf(0) }
    val wide = with(density) { widthPx.toDp() } >= ShellDimens.WideBreakpoint
    val padding = with(density) { PaddingValues(top = topBarPx.toDp(), bottom = if (wide) 0.dp else bottomBarPx.toDp()) }

    // A second tap during the transition would push a duplicate entry; only navigate from a settled screen.
    fun navigateWhenResumed(route: Any, builder: NavOptionsBuilder.() -> Unit = {}) {
        if (navController.currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
            navController.navigate(route, builder)
        }
    }

    // The steps share one OnboardingViewModel, kept by the Welcome entry, which stays on the stack until onboarding ends.
    @Composable
    fun onboardingEntry(entry: NavBackStackEntry) = remember(entry) { navController.getBackStackEntry<OnboardingWelcome>() }

    // Onboarding is removed from the stack so that back from Home does not return to it.
    // [persist] runs only from a settled screen, so a double tap cannot store the choices twice.
    fun leaveOnboarding(persist: () -> Unit) {
        if (navController.currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
            persist()
            navController.navigate(Utforska) { popUpTo(OnboardingWelcome) { inclusive = true } }
        }
    }

    // Back to the previous onboarding step; only from a settled screen, so a double tap cannot pop past Welcome.
    fun previousOnboardingStep() {
        if (navController.currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
            navController.popBackStack()
        }
    }

    fun selectTab(tab: Tab) {
        navController.navigate(tab.route) {
            popUpTo(Utforska) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun openLayer(layer: DisplayLayer) = navigateWhenResumed(LayerList(layer.apiLayer, layer.apiType))

    // From the wide top bar and the home's scope row: a scope whose place is chosen applies at once; one without a
    // place opens the sheet on it, where the place is picked. The active scope is left as it is.
    fun selectScope(next: Scope) {
        if (next == activeScope) return
        when (val action = drawerScopeAction(next, activeScope, locality)) {
            is DrawerScopeAction.Apply -> preferences.setScope(action.scope)
            is DrawerScopeAction.OpenSheet -> {
                sheetScope = action.scope
                showScopeSheet = true
            }
        }
    }

    fun selectWide(item: WideNav) {
        Tab.entries.firstOrNull { it.route == item.route }?.let(::selectTab) ?: navigateWhenResumed(item.route)
    }

    BackHandler(enabled = drawerState.isOpen) { scope.launch { drawerState.close() } }

    // Web only: Cmd/Ctrl+K focuses the search field when search is open, and opens search from any screen past onboarding.
    var searchFocusRequests by remember { mutableIntStateOf(0) }
    SearchShortcutEffect {
        when {
            destination?.hasRoute(Search::class) == true -> searchFocusRequests++
            destination == null || destination.hasRoute(Splash::class) || !preferences.onboardingDone.value -> Unit
            else -> {
                if (drawerState.isOpen) scope.launch { drawerState.close() }
                showScopeSheet = false
                navigateWhenResumed(Search())
            }
        }
    }

    // The web canvas can first lay out at 0×0 (a hidden tab, or a pane still opening). A drawer measured then anchors
    // its closed position at offset 0 and stays drawn over the screen once the window grows, so the shell is only
    // composed once it has a real width.
    var hasWidth by remember { mutableStateOf(false) }
    Box(
        Modifier.fillMaxSize().onSizeChanged {
            if (it.width > 0) hasWidth = true
            widthPx = it.width
        },
    ) {
        if (hasWidth) ModalNavigationDrawer(
            drawerState = drawerState,
            gesturesEnabled = selectedTab != null,
            drawerContent = {
                LagarDrawerContent(
                    hazeState = hazeState,
                    activeScope = activeScope,
                    localityNames = localityNames,
                    scopeCounts = scopeCounts,
                    savedCount = bookmarks.size,
                    selected = DrawerEntry.entries.firstOrNull { destination?.hasRoute(it.route::class) == true },
                    onSelectScope = { target ->
                        scope.launch { drawerState.close() }
                        when (val action = drawerScopeAction(target, activeScope, locality)) {
                            is DrawerScopeAction.Apply -> preferences.setScope(action.scope)
                            is DrawerScopeAction.OpenSheet -> {
                                sheetScope = action.scope
                                showScopeSheet = true
                            }
                        }
                    },
                    onNavigate = { entry ->
                        scope.launch { drawerState.close() }
                        Tab.entries.firstOrNull { it.route == entry.route }?.let(::selectTab)
                            ?: navController.navigate(entry.route) { launchSingleTop = true }
                    },
                )
            },
        ) {
            Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
                CompositionLocalProvider(
                    LocalShellPadding provides if (selectedTab != null) padding else PaddingValues(),
                    LocalWideLayout provides wide,
                ) {
                    NavHost(
                        navController = navController,
                        startDestination = Splash,
                        modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    ) {
                        composable<Splash> {
                            SplashRoute(onLoaded = {
                                val next: Any = if (preferences.onboardingDone.value) Utforska else OnboardingWelcome
                                navController.navigate(next) { popUpTo(Splash) { inclusive = true } }
                                // A shared link opens its document on top, so back leads into the app.
                                startLink?.let { navController.navigate(it) }
                            })
                        }
                        composable<OnboardingWelcome> { entry ->
                            val onboarding = koinViewModel<OnboardingViewModel>(viewModelStoreOwner = entry)
                            WelcomeRoute(
                                viewModel = onboarding,
                                onContinue = { navigateWhenResumed(OnboardingScope) },
                                onSkip = { leaveOnboarding(onboarding::skip) },
                            )
                        }
                        composable<OnboardingScope> { entry ->
                            val onboarding = koinViewModel<OnboardingViewModel>(viewModelStoreOwner = onboardingEntry(entry))
                            ScopeStepRoute(
                                viewModel = onboarding,
                                onDone = ::leaveOnboarding,
                                onBack = ::previousOnboardingStep,
                            )
                        }
                        composable<Utforska> {
                            HomeRoute(
                                onOpenLayer = ::openLayer,
                                onOpenDocument = { navigateWhenResumed(Reader(it)) },
                                onOpenSearch = { navigateWhenResumed(Search(text = it)) },
                                onOpenAdvancedSearch = { navigateWhenResumed(AdvancedSearch) },
                                onChooseLocation = { showScopeSheet = true },
                                onOpenLocality = { layer, code, name ->
                                    navigateWhenResumed(LayerList(layer.apiLayer, code = code, codeName = name))
                                },
                                onSelectScope = ::selectScope,
                            )
                        }
                        composable<Hierarki> {
                            HierarkiRoute(
                                onOpenLayer = ::openLayer,
                                onBrowseByMinistry = { layer ->
                                    layer.apiType?.let { navigateWhenResumed(Ministries(layer.apiLayer, it)) }
                                },
                            )
                        }
                        composable<Sparade> { SparadeRoute(onOpen = { id, anchor -> navigateWhenResumed(Reader(id, anchor)) }) }
                        composable<Tjanster> { TjansterScreen() }
                        composable<LayerList> { entry ->
                            val route = entry.toRoute<LayerList>()
                            LayerListRoute(
                                layer = route.layer,
                                type = route.type,
                                ministry = route.ministry?.let { MinistryFilter(it, route.ministryName ?: it) },
                                locality = route.code?.let { LocalityFilter(it, route.codeName ?: it) },
                                onBack = { navController.popBackStack() },
                                onOpenDocument = { navigateWhenResumed(Reader(it)) },
                            )
                        }
                        composable<Ministries> { entry ->
                            val route = entry.toRoute<Ministries>()
                            MinistriesRoute(
                                layer = route.layer,
                                type = route.type,
                                onBack = { navController.popBackStack() },
                                onOpenMinistry = {
                                    navigateWhenResumed(LayerList(route.layer, route.type, ministry = it.id, ministryName = it.name))
                                },
                            )
                        }
                        composable<Reader> { entry ->
                            val route = entry.toRoute<Reader>()
                            ReaderRoute(
                                id = route.id,
                                anchor = route.anchor,
                                onBack = { navController.popBackStack() },
                                onOpenDocument = { navigateWhenResumed(Reader(it)) },
                            )
                        }
                        composable<Search> { entry ->
                            SearchRoute(
                                route = entry.toRoute<Search>(),
                                onBack = { navController.popBackStack() },
                                onOpenDocument = { navigateWhenResumed(Reader(it)) },
                                onOpenAdvancedSearch = { navigateWhenResumed(AdvancedSearch) },
                                focusRequests = searchFocusRequests,
                            )
                        }
                        composable<AdvancedSearch> {
                            AdvancedSearchRoute(
                                onBack = { navController.popBackStack() },
                                onSearch = { query ->
                                    // The form is replaced by the results, so back from them skips it.
                                    navigateWhenResumed(query.toRoute()) { popUpTo<AdvancedSearch> { inclusive = true } }
                                },
                            )
                        }
                        composable<Settings> { SettingsRoute(onBack = { navController.popBackStack() }) }
                    }
                }
                if (selectedTab != null && wide) {
                    WideTopBar(
                        hazeState = hazeState,
                        selected = WideNav.entries.firstOrNull { destination?.hasRoute(it.route::class) == true },
                        scope = activeScope,
                        onSelect = ::selectWide,
                        onSelectScope = ::selectScope,
                        onOpenSearch = { navigateWhenResumed(Search()) },
                        onToggleTheme = onToggleTheme,
                        onMenuClick = { scope.launch { drawerState.open() } },
                        modifier = Modifier.align(Alignment.TopCenter).onSizeChanged { topBarPx = it.height },
                    )
                } else if (selectedTab != null) {
                    LagarTopBar(
                        hazeState = hazeState,
                        onMenuClick = { scope.launch { drawerState.open() } },
                        onToggleTheme = onToggleTheme,
                        onOpenSearch = { navigateWhenResumed(Search()) },
                        scope = activeScope,
                        onOpenScopeSheet = { showScopeSheet = true },
                        modifier = Modifier.align(Alignment.TopCenter).onSizeChanged { topBarPx = it.height },
                    )
                    LagarBottomBar(
                        selected = selectedTab,
                        hazeState = hazeState,
                        onSelect = ::selectTab,
                        modifier = Modifier.align(Alignment.BottomCenter).onSizeChanged { bottomBarPx = it.height },
                    )
                }
                if (showScopeSheet) {
                    ScopeSheet(
                        initialScope = sheetScope,
                        onDismiss = {
                            showScopeSheet = false
                            sheetScope = null
                        },
                    )
                }
            }
        }
    }
}
