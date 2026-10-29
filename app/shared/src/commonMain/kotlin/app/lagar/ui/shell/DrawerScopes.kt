package app.lagar.ui.shell

import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.hasLocality

/** What a tap on a scope row in the drawer does. */
internal sealed interface DrawerScopeAction {
    /** Switch straight to [scope]; the stored locality already covers it. */
    data class Apply(val scope: Scope) : DrawerScopeAction

    /** Open the scope sheet with [scope] preselected, so the user can pick or change its locality. */
    data class OpenSheet(val scope: Scope) : DrawerScopeAction
}

/**
 * Maps a tap on the [target] scope row. A scope without its locality, or the scope already in use
 * (to change its locality), opens the sheet; any other scope switches in one tap. Scopes without
 * documents yet switch like any other, as in the scope sheet.
 */
internal fun drawerScopeAction(target: Scope, active: Scope, locality: Locality): DrawerScopeAction =
    if (target == active || !target.hasLocality(locality)) {
        DrawerScopeAction.OpenSheet(target)
    } else {
        DrawerScopeAction.Apply(target)
    }

/** The badge on the Saved entry: the number of bookmarks, or none when there are none. */
internal fun savedBadgeCount(bookmarks: Int): Int? = bookmarks.takeIf { it > 0 }
