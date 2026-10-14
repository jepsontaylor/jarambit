"""Specimen, transfer, mass, lineage, and generic passport records.

Alloy name does not license a route or finish transfer. A matching digest
does not grant a route that the qualification did not cover. Same-target
consistency does not grant validation. No physical property is invented.
"""
import json
import math
from pathlib import Path

from assurance.testing.contracts import scientific_hash

_SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

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


def _finite_number(value):
    """True for a finite int or float. Booleans and strings are not numbers."""
    if type(value) is bool or type(value) not in (int, float):
        return False
    return math.isfinite(value)


def _digest(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _schema_document(name):
    return json.loads((_SCHEMAS / name).read_text(encoding="utf-8"))


def _matches_schema(value, spec):
    if "const" in spec and value != spec["const"]:
        return False
    if "enum" in spec and value not in spec["enum"]:
        return False
    declared = spec.get("type")
    if declared == "string":
        if type(value) is not str:
            return False
        if "minLength" in spec and len(value) < spec["minLength"]:
            return False
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            return False
        return True
    if declared == "number":
        if not _finite_number(value):
            return False
        if "minimum" in spec and value < spec["minimum"]:
            return False
        return True
    if declared == "array":
        if type(value) is not list:
            return False
        item = spec.get("items")
        if type(item) is dict:
            return all(_matches_schema(entry, item) for entry in value)
        return True
    if declared == "object":
        if type(value) is not dict:
            return False
        properties = spec.get("properties") or {}
        if spec.get("additionalProperties") is False and any(
            key not in properties for key in value
        ):
            return False
        for key in spec.get("required") or []:
            if key not in value:
                return False
        for key, child in properties.items():
            if key in value and not _matches_schema(value[key], child):
                return False
        return True
    if "oneOf" in spec:
        return any(_matches_schema(value, branch) for branch in spec["oneOf"])
    return True


def schema_refusal(record, filename):
    """Return a reason when record disagrees with the closed schema, else None.

    The envelope field `schema` is optional. Frozen records omit it. When it
    is present it must equal the schema const.
    """
    if type(record) is not dict:
        return "record_not_an_object"
    spec = _schema_document(filename)
    if not _matches_schema(record, spec):
        return "schema_rejected"
    return None


def validate_specimen(passport, registry, claim=None):
    """§4.2 identity. An unknown route stays unknown."""
    if type(passport) is not dict:
        return _refuse("unknown_applicability", material_state="unknown")
    if type(registry) is not list:
        return _refuse("registry_malformed", material_state="unknown")
    specimen_id = passport.get("id")
    lot = passport.get("material_lot")
    for other in registry:
        if type(other) is not dict:
            return _refuse("registry_malformed", material_state="unknown")
        if other.get("id") == specimen_id and other.get("material_lot") != lot:
            return _refuse("specimen_id_collision")
    route = passport.get("process_route")
    if _unknown(route) or type(route) is not str or not route or route == "unknown":
        return _refuse("unknown_applicability", material_state="unknown")
    reason = schema_refusal(passport, "specimen.v1.json")
    if reason is not None:
        return _refuse(reason, material_state="unknown")
    return {"material_state": "identified", "outcome": "accepted"}


def _covered_routes(qualification):
    """Explicit route set. A legacy scope string contributes exact tokens only."""
    declared = qualification.get("covered_routes")
    if declared is not None:
        if type(declared) is not list or any(type(item) is not str or not item for item in declared):
            return None
        return declared
    scope = qualification.get("scope")
    if type(scope) is not str:
        return []
    return scope.split()


def check_transfer(qualification, passport):
    """Bind the qualification digest, then an explicit route and surface set.

    The alloy string is not read. Coverage is membership of the passport route
    in covered_routes, or in the exact whitespace tokens of a legacy scope.
    Empty, absent, and reversed coverage all refuse.
    """
    if type(qualification) is not dict or type(passport) is not dict:
        return _refuse("qualification_not_an_object")
    digest = scientific_hash(passport)
    if digest != qualification.get("passport_sha256"):
        return _refuse("qualification_dependency_invalidated")
    route = passport.get("process_route")
    routes = _covered_routes(qualification)
    if routes is None or type(route) is not str or route not in routes:
        return _refuse("unapproved_route_transfer")
    surfaces = qualification.get("covered_surfaces")
    if surfaces is not None:
        if (
            type(surfaces) is not list
            or passport.get("surface_process") not in surfaces
        ):
            return _refuse("unapproved_route_transfer")
    return {"outcome": "accepted"}


def validate_mass(records, requested):
    """Each configuration is its own measurement. Derived mass is not a substitute."""
    if type(records) is not list:
        return _refuse("mass_records_malformed")
    measured = []
    for record in records:
        if type(record) is not dict:
            return _refuse("mass_records_malformed")
        if record.get("configuration") != requested:
            continue
        if record.get("role") not in _MEASURED_ROLES or not record.get("uncertainty"):
            continue
        measured.append(record)
    if not measured:
        return _refuse("unmeasured_configuration_substitution")
    if len(measured) != 1:
        return _refuse("conflicting_configuration_measurements")
    value = measured[0].get("value_g")
    if not _finite_number(value) or value < 0:
        return _refuse("mass_value_invalid")
    return {
        "configuration": requested,
        "outcome": "accepted",
        "value_g": value,
    }


def load_historical(record, claim=None):
    """Pre-schema rows stay display-only. They cannot qualify a new claim."""
    if type(record) is not dict or claim is not None or record.get("schema") != 0:
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


def _lineage_cycle(observations):
    by_id = {}
    for observation in observations:
        identity = observation.get("id")
        if type(identity) is not str or identity in by_id:
            return True
        by_id[identity] = observation
    for origin in by_id:
        seen = set()
        cursor = origin
        while cursor is not None:
            if cursor in seen:
                return True
            seen.add(cursor)
            record = by_id.get(cursor)
            if record is None:
                break
            parents = record.get("parents") or []
            if type(parents) is not list:
                return True
            if not parents:
                break
            if len(parents) != 1 or type(parents[0]) is not str:
                cursor = None
                for parent in parents:
                    if type(parent) is not str or parent not in by_id or parent in seen:
                        return True
                break
            cursor = parents[0]
    return False


def validate_validation_lineage(claim, lineage=None, observations=None):
    """Count independent units by specimen, not by session or raw-hash row."""
    if type(claim) is not dict:
        return _refuse("claim_not_an_object")
    if observations is not None:
        if type(observations) is not list or any(type(item) is not dict for item in observations):
            return _refuse("observations_malformed")
        claimed = claim.get("independent_observations")
        screened = _observation_units(observations)
        if type(screened) is dict:
            return screened
        derived = screened
        identities = {
            observation.get("id")
            for observation in observations
            if type(observation.get("id")) is str
        }
        if derived and claimed is not None and claimed > 1:
            return _refuse("derived_copy_counted_independent")
        if derived and claimed == 1:
            if _lineage_cycle(observations):
                return _refuse("lineage_cycle")
            links = []
            for observation in derived:
                parents = observation.get("parents") or []
                if type(parents) is not list or not parents:
                    return _refuse("orphan_parent")
                for parent in parents:
                    if type(parent) is not str or parent not in identities or parent == observation.get("id"):
                        return _refuse("orphan_parent")
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
        specimens = []
        for observation in raws:
            specimen = observation.get("specimen")
            if type(specimen) is not str or not specimen:
                return _refuse("observations_malformed")
            if specimen not in specimens:
                specimens.append(specimen)
        if claimed is not None and claimed != len(specimens):
            return _refuse("duplicate_acquisition_counted_independent")
        return {"independent_units": len(specimens), "outcome": "accepted"}
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
    reason = schema_refusal(record, "material_state.v1.json")
    if reason is not None:
        return _refuse(reason, completion="incomplete", lab_pass=False)
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
    reason = schema_refusal(plan, "test_plan.v1.json")
    if reason is not None:
        return _refuse(reason, completion="incomplete", lab_pass=False)
    return {
        "completion": "incomplete",
        "lab_pass": False,
        "outcome": "accepted",
    }
