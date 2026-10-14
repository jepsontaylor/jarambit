"""Specimen, transfer, mass, lineage, and generic passport records.

Alloy name does not license a route or finish transfer. A matching digest
does not grant a route that the qualification did not cover. Same-target
consistency does not grant validation. No physical property is invented.
"""
from assurance.testing.contracts import scientific_hash

_MEASURED_ROLES = {"raw_measurement"}
_FORBIDDEN_PROPERTY_KEYS = {
    "hardness",
    "modulus",
    "strength",
    "surface_finish_claim",
    "tensile",
    "yield_strength",
    "yield_strength_mpa",
}


def _refuse(reason, **extra):
    payload = {"outcome": "refused", "reason": reason}
    payload.update(extra)
    return payload


def _unknown(value):
    return type(value) is dict and "unknown" in value


def validate_specimen(passport, registry, claim=None):
    """§4.2 identity. An unknown route stays unknown."""
    specimen_id = passport.get("id")
    lot = passport.get("material_lot")
    for other in registry or []:
        if other.get("id") == specimen_id and other.get("material_lot") != lot:
            return _refuse("specimen_id_collision")
    route = passport.get("process_route")
    if _unknown(route) or type(route) is not str or not route:
        return _refuse("unknown_applicability", material_state="unknown")
    return {"material_state": "identified", "outcome": "accepted"}


def check_transfer(qualification, passport):
    """Bind the qualification to the passport bytes, then the route.

    Hash mismatch is qualification_dependency_invalidated. A digest that
    matches the presented additive passport is still refused against a
    wrought scope. The alloy string is not consulted.
    """
    digest = scientific_hash(passport)
    if digest != qualification.get("passport_sha256"):
        return _refuse("qualification_dependency_invalidated")
    route = passport.get("process_route")
    scope = qualification.get("scope") or ""
    if route == "additive_lpbf" and "wrought" in scope:
        return _refuse("unapproved_route_transfer")
    return {"outcome": "accepted"}


def validate_mass(records, requested):
    """Each configuration is its own measurement. Derived mass is not a substitute."""
    chosen = None
    for record in records or []:
        if record.get("configuration") == requested:
            chosen = record
            break
    if chosen is None or chosen.get("role") not in _MEASURED_ROLES or not chosen.get("uncertainty"):
        return _refuse("unmeasured_configuration_substitution")
    return {
        "configuration": requested,
        "outcome": "accepted",
        "value_g": chosen.get("value_g"),
    }


def load_historical(record, claim=None):
    """Pre-schema rows stay display-only. They cannot qualify a new claim."""
    if claim is not None or record.get("schema") != 0:
        return _refuse("historical_record_cannot_qualify_new_claim")
    return {
        "claim_eligible": False,
        "outcome": "accepted",
        "scope": "historical_display",
    }


def _observation_units(observations):
    for observation in observations:
        unit = observation.get("experimental_unit") or {}
        if observation.get("specimen") != unit.get("specimen"):
            return _refuse("specimen_field_disagrees_with_experimental_unit")
    for observation in observations:
        unit = observation.get("experimental_unit") or {}
        if _unknown(unit.get("session")) or _unknown(unit.get("operator")):
            return _refuse("grouping_unknown_not_independent", grouping="unknown")
    derived = [
        observation for observation in observations
        if observation.get("role") == "derived" or observation.get("parents")
    ]
    return derived


def validate_validation_lineage(claim, lineage=None, observations=None):
    """Count units from specimen, session, and raw identity. Hashes are not independence."""
    if observations is not None:
        claimed = claim.get("independent_observations")
        screened = _observation_units(observations)
        if type(screened) is dict:
            return screened
        derived = screened
        if derived and claimed is not None and claimed > 1:
            return _refuse("derived_copy_counted_independent")
        if derived and claimed == 1:
            links = []
            for observation in derived:
                for parent in observation.get("parents") or []:
                    if parent not in links:
                        links.append(parent)
            return {
                "independent_units": 1,
                "outcome": "accepted",
                "parent_links": links,
            }
        raws = [
            observation for observation in observations
            if observation.get("role") != "derived" and not observation.get("parents")
        ]
        hashes = [observation.get("raw_sha256") for observation in raws]
        if claimed is not None and claimed > len(set(hashes)):
            return _refuse("duplicate_acquisition_counted_independent")
        units = []
        for observation in raws:
            unit = observation.get("experimental_unit") or {}
            key = (
                observation.get("specimen"),
                unit.get("session"),
                observation.get("raw_sha256"),
            )
            if key not in units:
                units.append(key)
        if claimed is not None and claimed != len(units):
            return _refuse("duplicate_acquisition_counted_independent")
        return {"independent_units": len(units), "outcome": "accepted"}
    if lineage is None:
        return _refuse("lineage_absent")
    role = lineage.get("target_role")
    target = lineage.get("target", claim.get("target"))
    constraints = list(lineage.get("fit_constraints") or [])
    scope = claim.get("scope")
    if role == "derived_reduction":
        if scope == "implementation_consistency":
            return {"outcome": "accepted", "scope": "implementation_consistency"}
        return _refuse("consistency_relabeled_physical_validation")
    if role == "imposed_constraint" or target in constraints:
        return _refuse(
            "imposed_constraint_not_validation",
            scope="implementation_consistency",
        )
    if role == "withheld" and scope == "independent_validation":
        return {"outcome": "accepted", "scope": "independent_validation_candidate"}
    return _refuse("lineage_not_validation")


def validate_material_state(record):
    """Opaque route identity only. Numeric properties stay unmeasured."""
    if type(record) is not dict:
        return _refuse("physical_property_not_measured", completion="incomplete", lab_pass=False)
    properties = record.get("properties", {})
    if type(properties) is not dict:
        return _refuse("physical_property_not_measured", completion="incomplete", lab_pass=False)
    for key, value in properties.items():
        if key in _FORBIDDEN_PROPERTY_KEYS or type(value) in (int, float):
            return _refuse("physical_property_not_measured", completion="incomplete", lab_pass=False)
        if not _unknown(value) and key != "unknown":
            return _refuse("physical_property_not_measured", completion="incomplete", lab_pass=False)
    if record.get("state") not in ("identified", "unknown"):
        return _refuse("material_state_unknown", completion="incomplete", lab_pass=False)
    if not record.get("id") or not record.get("passport_id") or not record.get("route_id"):
        return _refuse("opaque_identity_required", completion="incomplete", lab_pass=False)
    return {
        "completion": "incomplete",
        "lab_pass": False,
        "outcome": "accepted",
        "state": record.get("state"),
    }


def validate_test_plan(plan):
    """Distinct fit and validation ids. A plan is not a laboratory pass."""
    if type(plan) is not dict:
        return _refuse("test_plan_incomplete", completion="incomplete", lab_pass=False)
    for banned in ("commissioning", "coupon_protocol", "protocol", "setpoint"):
        if banned in plan:
            return _refuse("commissioning_not_admitted", completion="incomplete", lab_pass=False)
    seen = {}
    for dataset in plan.get("datasets") or []:
        if type(dataset) is not dict:
            return _refuse("test_plan_incomplete", completion="incomplete", lab_pass=False)
        identity = dataset.get("id")
        role = dataset.get("role")
        if role not in ("fit", "validation", "exploratory") or not identity:
            return _refuse("test_plan_incomplete", completion="incomplete", lab_pass=False)
        if identity in seen and seen[identity] != role:
            return _refuse("fit_validation_not_distinct", completion="incomplete", lab_pass=False)
        seen[identity] = role
    roles = set(seen.values())
    if "fit" in roles and "validation" in roles and len(seen) < 2:
        return _refuse("fit_validation_not_distinct", completion="incomplete", lab_pass=False)
    return {
        "completion": "incomplete",
        "lab_pass": False,
        "outcome": "accepted",
    }
