package app.lagar.ui.common

import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.layer_agency
import app.lagar.resources.layer_agency_desc
import app.lagar.resources.layer_case_law
import app.lagar.resources.layer_case_law_desc
import app.lagar.resources.layer_eu
import app.lagar.resources.layer_eu_desc
import app.lagar.resources.layer_fundamental
import app.lagar.resources.layer_fundamental_desc
import app.lagar.resources.layer_municipality
import app.lagar.resources.layer_municipality_desc
import app.lagar.resources.layer_region
import app.lagar.resources.layer_region_desc
import app.lagar.resources.layer_service
import app.lagar.resources.layer_service_desc
import app.lagar.resources.layer_sfs_act
import app.lagar.resources.layer_sfs_act_desc
import app.lagar.resources.layer_sfs_ordinance
import app.lagar.resources.layer_sfs_ordinance_desc
import org.jetbrains.compose.resources.StringResource

internal fun DisplayLayer.nameRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.layer_fundamental
    DisplayLayer.SfsAct -> Res.string.layer_sfs_act
    DisplayLayer.SfsOrdinance -> Res.string.layer_sfs_ordinance
    DisplayLayer.Agency -> Res.string.layer_agency
    DisplayLayer.CaseLaw -> Res.string.layer_case_law
    DisplayLayer.Eu -> Res.string.layer_eu
    DisplayLayer.Region -> Res.string.layer_region
    DisplayLayer.Municipality -> Res.string.layer_municipality
    DisplayLayer.Service -> Res.string.layer_service
}

internal fun DisplayLayer.descriptionRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.layer_fundamental_desc
    DisplayLayer.SfsAct -> Res.string.layer_sfs_act_desc
    DisplayLayer.SfsOrdinance -> Res.string.layer_sfs_ordinance_desc
    DisplayLayer.Agency -> Res.string.layer_agency_desc
    DisplayLayer.CaseLaw -> Res.string.layer_case_law_desc
    DisplayLayer.Eu -> Res.string.layer_eu_desc
    DisplayLayer.Region -> Res.string.layer_region_desc
    DisplayLayer.Municipality -> Res.string.layer_municipality_desc
    DisplayLayer.Service -> Res.string.layer_service_desc
}

/** 1-based position in the order of norms. */
internal val DisplayLayer.level: Int get() = ordinal + 1
