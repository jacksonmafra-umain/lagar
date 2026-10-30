package app.lagar.ui.common

import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.ic_gavel
import app.lagar.resources.ic_layer_apartment
import app.lagar.resources.ic_layer_badge
import app.lagar.resources.ic_layer_balance
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.ic_layer_description
import app.lagar.resources.ic_layer_hospital
import app.lagar.resources.ic_layer_shield
import app.lagar.resources.ic_layer_stars
import app.lagar.resources.layer_agency
import app.lagar.resources.layer_agency_authority
import app.lagar.resources.layer_agency_desc
import app.lagar.resources.layer_agency_examples
import app.lagar.resources.layer_case_law
import app.lagar.resources.layer_case_law_authority
import app.lagar.resources.layer_case_law_desc
import app.lagar.resources.layer_case_law_examples
import app.lagar.resources.layer_eu
import app.lagar.resources.layer_eu_authority
import app.lagar.resources.layer_eu_desc
import app.lagar.resources.layer_eu_examples
import app.lagar.resources.layer_fundamental
import app.lagar.resources.layer_fundamental_authority
import app.lagar.resources.layer_fundamental_desc
import app.lagar.resources.layer_fundamental_examples
import app.lagar.resources.layer_municipality
import app.lagar.resources.layer_municipality_authority
import app.lagar.resources.layer_municipality_desc
import app.lagar.resources.layer_municipality_examples
import app.lagar.resources.layer_region
import app.lagar.resources.layer_region_authority
import app.lagar.resources.layer_region_desc
import app.lagar.resources.layer_region_examples
import app.lagar.resources.layer_service
import app.lagar.resources.layer_service_authority
import app.lagar.resources.layer_service_desc
import app.lagar.resources.layer_service_examples
import app.lagar.resources.layer_sfs_act
import app.lagar.resources.layer_sfs_act_authority
import app.lagar.resources.layer_sfs_act_desc
import app.lagar.resources.layer_sfs_act_examples
import app.lagar.resources.layer_sfs_ordinance
import app.lagar.resources.layer_sfs_ordinance_authority
import app.lagar.resources.layer_sfs_ordinance_desc
import app.lagar.resources.layer_sfs_ordinance_examples
import app.lagar.resources.type_act
import app.lagar.resources.type_agency_regulation
import app.lagar.resources.type_case_notice
import app.lagar.resources.type_case_report
import app.lagar.resources.type_county_regulation
import app.lagar.resources.type_eu_decision
import app.lagar.resources.type_eu_directive
import app.lagar.resources.type_eu_judgment
import app.lagar.resources.type_eu_regulation
import app.lagar.resources.type_fundamental_law
import app.lagar.resources.type_municipal_regulation
import app.lagar.resources.type_ordinance
import app.lagar.resources.type_other_statute
import app.lagar.resources.type_treaty
import org.jetbrains.compose.resources.DrawableResource
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

/** Who issues or decides the norms of this level, as the short badge on its layer row. */
internal fun DisplayLayer.authorityRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.layer_fundamental_authority
    DisplayLayer.SfsAct -> Res.string.layer_sfs_act_authority
    DisplayLayer.SfsOrdinance -> Res.string.layer_sfs_ordinance_authority
    DisplayLayer.Agency -> Res.string.layer_agency_authority
    DisplayLayer.CaseLaw -> Res.string.layer_case_law_authority
    DisplayLayer.Eu -> Res.string.layer_eu_authority
    DisplayLayer.Region -> Res.string.layer_region_authority
    DisplayLayer.Municipality -> Res.string.layer_municipality_authority
    DisplayLayer.Service -> Res.string.layer_service_authority
}

/** Well-known norms of this level, listed on its layer row. */
internal fun DisplayLayer.examplesRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.layer_fundamental_examples
    DisplayLayer.SfsAct -> Res.string.layer_sfs_act_examples
    DisplayLayer.SfsOrdinance -> Res.string.layer_sfs_ordinance_examples
    DisplayLayer.Agency -> Res.string.layer_agency_examples
    DisplayLayer.CaseLaw -> Res.string.layer_case_law_examples
    DisplayLayer.Eu -> Res.string.layer_eu_examples
    DisplayLayer.Region -> Res.string.layer_region_examples
    DisplayLayer.Municipality -> Res.string.layer_municipality_examples
    DisplayLayer.Service -> Res.string.layer_service_examples
}

/** 1-based position in the order of norms. */
internal val DisplayLayer.level: Int get() = ordinal + 1

internal fun DisplayLayer.iconRes(): DrawableResource = when (this) {
    DisplayLayer.Fundamental -> Res.drawable.ic_layer_crown
    DisplayLayer.SfsAct -> Res.drawable.ic_layer_balance
    DisplayLayer.SfsOrdinance -> Res.drawable.ic_layer_description
    DisplayLayer.Agency -> Res.drawable.ic_layer_shield
    DisplayLayer.CaseLaw -> Res.drawable.ic_gavel
    DisplayLayer.Eu -> Res.drawable.ic_layer_stars
    DisplayLayer.Region -> Res.drawable.ic_layer_hospital
    DisplayLayer.Municipality -> Res.drawable.ic_layer_apartment
    DisplayLayer.Service -> Res.drawable.ic_layer_badge
}

/** Name of an API document `type`; any type without its own name reads as "other statute". */
internal fun typeNameRes(type: String): StringResource = when (type) {
    "fundamental_law" -> Res.string.type_fundamental_law
    "act" -> Res.string.type_act
    "ordinance" -> Res.string.type_ordinance
    "agency_regulation" -> Res.string.type_agency_regulation
    "case_report" -> Res.string.type_case_report
    "case_notice" -> Res.string.type_case_notice
    "eu_regulation" -> Res.string.type_eu_regulation
    "eu_directive" -> Res.string.type_eu_directive
    "eu_decision" -> Res.string.type_eu_decision
    "eu_judgment" -> Res.string.type_eu_judgment
    "county_regulation" -> Res.string.type_county_regulation
    "municipal_regulation" -> Res.string.type_municipal_regulation
    "treaty" -> Res.string.type_treaty
    else -> Res.string.type_other_statute
}
