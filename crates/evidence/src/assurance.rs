//! Required evidence closure, exact observable binding, and append-only review revocation.
use crate::identity::{check_id, scientific_hash, ContentRef, MaterialState, ScientificIdentity};
use crate::{Outcome, Verdict};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, PartialOrd)]
pub struct Finite(f64);
impl Finite {
    pub fn new(x: f64) -> Result<Self, String> { if x.is_finite() { Ok(Self(x)) } else { Err("nonfinite_value".into()) } }
    pub fn get(self) -> f64 { self.0 }
}
impl Serialize for Finite { fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> { s.serialize_f64(self.0) } }
impl<'de> Deserialize<'de> for Finite {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct Number;
        impl<'de> serde::de::Visitor<'de> for Number {
            type Value = Finite;
            fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { f.write_str("a finite binary64 number") }
            fn visit_f64<E: serde::de::Error>(self, x: f64) -> Result<Finite, E> { Finite::new(x).map_err(E::custom) }
            fn visit_u64<E: serde::de::Error>(self, x: u64) -> Result<Finite, E> {
                let f = x as f64; if f as u128 != x as u128 { return Err(E::custom("inexact integer scalar")); } self.visit_f64(f)
            }
            fn visit_i64<E: serde::de::Error>(self, x: i64) -> Result<Finite, E> {
                let f = x as f64; if f as i128 != x as i128 { return Err(E::custom("inexact integer scalar")); } self.visit_f64(f)
            }
        }
        d.deserialize_any(Number)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Unit { Dimensionless, Gram, Millimetre, Newton, NewtonMillimetre, NewtonPerGram, Megapascal, Second, Celsius }
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservableSpec { pub quantity: String, pub unit: Unit, pub frame: String, pub region: String, pub recovery: String }
impl ObservableSpec {
    fn check(&self) -> Result<(), String> { for x in [&self.quantity, &self.frame, &self.region, &self.recovery] { check_id(x)?; } Ok(()) }
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceIdentity { pub scientific: ScientificIdentity, pub model: ContentRef, pub observable: ObservableSpec }
impl EvidenceIdentity {
    pub fn check(&self) -> Result<(), String> { self.scientific.check()?; self.model.check()?; self.observable.check() }
    fn refs(&self) -> Vec<&ContentRef> { let mut r = self.scientific.refs(); r.push(&self.model); r }
}

macro_rules! states { ($name:ident, $($v:ident),+) => {
    #[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
    #[serde(rename_all = "snake_case")]
    pub enum $name { $($v),+ }
}; }
states!(Execution, Succeeded, Failed, NotRun);
states!(Numerical, Verified, Unverified, Invalid);
states!(Validation, NotPerformed, Validated, Invalid);
states!(Origin, Simulation, Measurement, Synthetic);
states!(EvidenceClass, SoftwareContract, NumericalVerification, PhysicalValidation, Research);
states!(ArtifactKind, Source, SolverOutput, Acquisition, Synthetic);
states!(ReviewAction, Approved, Reopened, Revoked, Superseded);
states!(Role, Required, Optional, RecordOnly);
states!(Comparison, AtLeast, AtMost);

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EvidenceState { pub execution: Execution, pub numerical: Numerical, pub validation: Validation }
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Uncertainty {
    pub kind: String, pub amount: Finite, pub method: String, pub domain: String,
    pub dependence: String, pub coverage_interpretation: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservationRef { pub id: String, pub sha256: String }
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observation {
    pub schema: u32, pub id: String, pub producer: String, pub identity: EvidenceIdentity,
    pub value: Option<Finite>, pub not_applicable_reason: Option<String>, pub source: ContentRef,
    pub origin: Origin, pub evidence_class: EvidenceClass, pub state: EvidenceState,
    pub dependencies: Vec<ObservationRef>, pub uncertainty: Vec<Uncertainty>,
}
/// Non-circular evaluator/acquisition envelope; a bare legacy scalar is historical only.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceRecord {
    pub schema: u32, pub identity_sha256: String, pub producer: String,
    pub value: Option<Finite>, pub not_applicable_reason: Option<String>, pub origin: Origin,
    pub evidence_class: EvidenceClass, pub state: EvidenceState,
    pub dependencies: Vec<ObservationRef>, pub uncertainty: Vec<Uncertainty>,
}
impl Observation {
    pub fn check(&self) -> Result<(), String> {
        if self.schema != 2 { return Err("unsupported_observation_schema".into()); }
        check_id(&self.id)?; check_id(&self.producer)?; self.identity.check()?; self.source.check()?;
        if let Some(reason) = &self.not_applicable_reason {
            if reason.trim().is_empty() || self.value.is_some() { return Err("invalid_not_applicable".into()); }
        }
        let mut seen = BTreeSet::new();
        for d in &self.dependencies {
            check_id(&d.id)?;
            if !crate::identity::is_hash(&d.sha256) || !seen.insert(&d.id) { return Err("invalid_or_duplicate_dependency".into()); }
        }
        for u in &self.uncertainty {
            if u.amount.get() < 0.0 { return Err("negative_uncertainty".into()); }
            for x in [&u.kind, &u.method, &u.domain, &u.dependence, &u.coverage_interpretation] { check_id(x)?; }
        }
        if self.state.validation == Validation::Validated {
            if self.origin != Origin::Measurement || self.evidence_class != EvidenceClass::PhysicalValidation
                || matches!(self.identity.scientific.material, MaterialState::Unknown { .. })
                || !matches!(self.identity.scientific.subject, crate::identity::SubjectRef::Specimen { .. }) {
                return Err("unsupported_physical_validation".into());
            }
        }
        if self.origin == Origin::Synthetic && self.evidence_class != EvidenceClass::SoftwareContract && self.evidence_class != EvidenceClass::Research {
            return Err("synthetic_cannot_qualify_numerical_or_physical".into());
        }
        Ok(())
    }
    pub fn sha256(&self) -> Result<String, String> { self.check()?; scientific_hash(self) }
    pub fn source_record(&self) -> Result<SourceRecord, String> {
        self.check()?;
        Ok(SourceRecord { schema: 2, identity_sha256: scientific_hash(&self.identity)?, producer: self.producer.clone(),
            value: self.value, not_applicable_reason: self.not_applicable_reason.clone(), origin: self.origin.clone(),
            evidence_class: self.evidence_class.clone(), state: self.state.clone(), dependencies: self.dependencies.clone(),
            uncertainty: self.uncertainty.clone() })
    }
}

pub fn ingest_observation(bytes: &[u8]) -> Result<Observation, String> {
    let o: Observation = crate::identity::strict_decode(bytes)?;
    o.check()?; Ok(o)
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReviewEvent {
    pub sequence: u64, pub observation: String, pub observation_sha256: String,
    pub action: ReviewAction, pub reviewer: String, pub receipt: ContentRef,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Threshold { pub comparison: Comparison, pub value: Finite }
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Criterion {
    pub id: String, pub role: Role, pub observation: String, pub identity: EvidenceIdentity,
    pub required_class: EvidenceClass, pub threshold: Option<Threshold>, pub allow_not_applicable: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExpectedInventory { pub id: String, pub requirement_set: String, pub group: String, pub requirements: Vec<ContentRef>, pub criteria: Vec<Criterion> }
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ClaimRecord { pub id: String, pub inventory: ContentRef, pub requirement_set: String, pub group: String }

/// Explicit caller trust boundary: the reference/requirements come from approved configuration,
/// never the incoming claim. Admission pins the complete criterion content, including roles/NA.
/// This type is deliberately not deserializable and exposes no mutable policy fields.
pub struct TrustedInventory { reference: ContentRef, canonical_sha256: String }
impl TrustedInventory {
    pub fn from_approved_bytes(reference: ContentRef, approved_requirements: &[ContentRef], bytes: &[u8]) -> Result<Self, String> {
        reference.check()?;
        if ContentRef::from_bytes(&reference.id, &reference.revision, bytes) != reference { return Err("approved_policy_bytes_mismatch".into()); }
        let expected: ExpectedInventory = crate::identity::strict_decode(bytes)?;
        check_id(&expected.requirement_set)?; check_id(&expected.group)?;
        if expected.id != reference.id || expected.requirements != approved_requirements || expected.criteria.is_empty() { return Err("approved_policy_scope_mismatch".into()); }
        crate::identity::unique_ids(expected.requirements.iter().map(|r| r.id.as_str()))?;
        crate::identity::unique_ids(expected.criteria.iter().map(|r| r.id.as_str()))?;
        for r in approved_requirements { r.check()?; }
        Ok(Self { reference, canonical_sha256: scientific_hash(&expected)? })
    }
}

/// Bytes, kind and content reference are checked together; a claimed hash alone is insufficient.
#[derive(Clone, Debug)]
pub struct Artifact { reference: ContentRef, bytes: Vec<u8>, kind: ArtifactKind }
impl Artifact {
    pub fn reference(&self) -> &ContentRef { &self.reference }
    pub fn new(reference: ContentRef, bytes: Vec<u8>, kind: ArtifactKind) -> Result<Self, String> {
        reference.check()?;
        if ContentRef::from_bytes(&reference.id, &reference.revision, &bytes) != reference { return Err("artifact_hash_mismatch".into()); }
        Ok(Self { reference, bytes, kind })
    }
}
#[derive(Default)]
pub struct Registry { pub artifacts: Vec<Artifact>, pub observations: Vec<Observation>, pub reviews: Vec<ReviewEvent>, inventory_authority: Option<TrustedInventory> }
impl Registry {
    /// The caller installs an authenticated policy root separately from submitted evidence.
    pub fn install_approved_inventory(&mut self, authority: TrustedInventory) { self.inventory_authority = Some(authority); }
}
#[derive(Debug)]
pub struct Resolution { pub verdict: Verdict, pub publication_eligible: bool, pub release_authorized: bool }

pub fn resolve_claim(claim: &ClaimRecord, expected: &ExpectedInventory, registry: &Registry) -> Resolution {
    fn resolve(claim: &ClaimRecord, ex: &ExpectedInventory, reg: &Registry) -> Result<Outcome, String> {
        check_id(&claim.id)?; check_id(&claim.group)?; check_id(&ex.id)?;
        if claim.inventory.id != ex.id || ex.requirements.is_empty() || ex.criteria.is_empty() { return Err("missing_expected_inventory".into()); }
        let authority = reg.inventory_authority.as_ref().ok_or("inventory_policy_authority_missing")?;
        if claim.inventory != authority.reference || scientific_hash(ex)? != authority.canonical_sha256 { return Err("frozen_inventory_policy_mismatch".into()); }
        if claim.requirement_set != ex.requirement_set || claim.group != ex.group { return Err("claim_scope_mismatch".into()); }
        if !ex.requirements.iter().any(|r| r.id == claim.requirement_set) { return Err("requirement_scope_mismatch".into()); }
        let mut artifacts = BTreeMap::new();
        crate::identity::unique_ids(reg.artifacts.iter().map(|a| a.reference.id.as_str())).map_err(|_| "duplicate_artifact_id_or_normalization_collision")?;
        for a in &reg.artifacts {
            if artifacts.insert(a.reference.id.clone(), a).is_some() { return Err("duplicate_artifact_id".into()); }
        }
        let bind = |r: &ContentRef| -> Result<(), String> {
            r.check()?;
            let a = artifacts.get(&r.id).ok_or("missing_artifact")?;
            if &a.reference != r || ContentRef::from_bytes(&r.id, &r.revision, &a.bytes) != *r { return Err("artifact_identity_mismatch".into()); }
            Ok(())
        };
        for r in &ex.requirements { bind(r)?; }
        let mut observations = BTreeMap::new();
        crate::identity::unique_ids(reg.observations.iter().map(|o| o.id.as_str())).map_err(|_| "duplicate_observation_id_or_normalization_collision")?;
        for o in &reg.observations { if observations.insert(o.id.clone(), o).is_some() { return Err("duplicate_observation_id".into()); } }
        let mut reviews = BTreeMap::new(); let mut last_sequence = None;
        for e in &reg.reviews {
            if last_sequence.map_or(false, |last| e.sequence <= last) { return Err("review_sequence_not_append_only".into()); }
            last_sequence = Some(e.sequence); check_id(&e.reviewer)?; e.receipt.check()?;
            if !crate::identity::is_hash(&e.observation_sha256) { return Err("invalid_review_target".into()); }
            reviews.insert(e.observation.clone(), e);
        }
        struct Walk<'a> { obs: &'a BTreeMap<String, &'a Observation>, reviews: &'a BTreeMap<String, &'a ReviewEvent>,
            artifacts: &'a BTreeMap<String, &'a Artifact>, visiting: BTreeSet<String>, checked: BTreeSet<String> }
        impl Walk<'_> {
            fn visit(&mut self, id: &str) -> Result<(), String> {
                if self.checked.contains(id) { return Ok(()); }
                if !self.visiting.insert(id.into()) { return Err("dependency_cycle".into()); }
                let o = *self.obs.get(id).ok_or("missing_observation")?;
                o.check()?;
                for d in &o.dependencies {
                    self.visit(&d.id)?;
                    if self.obs[&d.id].sha256()? != d.sha256 { return Err("dependency_identity_mismatch".into()); }
                }
                for r in o.identity.refs().into_iter().chain(std::iter::once(&o.source)) {
                    let a = self.artifacts.get(&r.id).ok_or("missing_artifact")?;
                    if &a.reference != r { return Err("artifact_identity_mismatch".into()); }
                }
                if o.state.execution != Execution::Succeeded || o.state.numerical != Numerical::Verified || o.state.validation == Validation::Invalid { return Err("invalid_or_unexecuted_observation".into()); }
                let a = self.artifacts.get(&o.source.id).ok_or("missing_source")?;
                let source: SourceRecord = crate::identity::strict_decode(&a.bytes).map_err(|_| "source_record_missing_or_invalid")?;
                if scientific_hash(&source)? != scientific_hash(&o.source_record()?)? { return Err("source_observation_binding_mismatch".into()); }
                if (o.origin == Origin::Measurement && a.kind != ArtifactKind::Acquisition)
                    || (o.origin == Origin::Simulation && a.kind != ArtifactKind::SolverOutput)
                    || (o.origin == Origin::Synthetic && a.kind != ArtifactKind::Synthetic) { return Err("source_origin_mismatch".into()); }
                let review = self.reviews.get(id).ok_or("review_missing")?;
                let receipt = self.artifacts.get(&review.receipt.id).ok_or("review_artifact_missing")?;
                if receipt.reference != review.receipt { return Err("review_artifact_identity_mismatch".into()); }
                if review.action != ReviewAction::Approved || review.observation_sha256 != o.sha256()? { return Err("review_revoked_or_stale".into()); }
                if crate::identity::same_id(&review.reviewer, &o.producer) { return Err("review_not_independent".into()); }
                self.visiting.remove(id); self.checked.insert(id.into()); Ok(())
            }
        }
        let mut ids = BTreeSet::new(); let mut required = 0; let mut missing = Vec::new(); let mut failed = Vec::new();
        for c in &ex.criteria {
            check_id(&c.id)?; c.identity.check()?;
            if !ids.insert(&c.id) { return Err("duplicate_criterion_id".into()); }
            if c.identity.scientific.requirements != ex.requirements { return Err("criterion_requirement_mismatch".into()); }
            if c.role != Role::Required { continue; }
            required += 1;
            let mut walk = Walk { obs: &observations, reviews: &reviews, artifacts: &artifacts, visiting: BTreeSet::new(), checked: BTreeSet::new() };
            if let Err(e) = walk.visit(&c.observation) { missing.push(format!("{}:{e}", c.id)); continue; }
            let o = observations[&c.observation];
            if o.identity != c.identity || o.evidence_class != c.required_class { missing.push(format!("{}:scope_or_class_mismatch", c.id)); continue; }
            if c.required_class == EvidenceClass::PhysicalValidation && o.state.validation != Validation::Validated { missing.push(format!("{}:physical_validation_missing", c.id)); continue; }
            // S13 owns authenticated laboratory/passport reduction. Declared acquisition metadata alone
            // cannot activate that provider or establish a currently qualified physical result.
            if c.required_class == EvidenceClass::PhysicalValidation { missing.push(format!("{}:physical_qualification_provider_unavailable", c.id)); continue; }
            if o.not_applicable_reason.is_some() {
                if !c.allow_not_applicable { missing.push(format!("{}:not_applicable_forbidden", c.id)); }
                continue;
            }
            let (Some(v), Some(t)) = (o.value, &c.threshold) else { missing.push(format!("{}:value_or_threshold_missing", c.id)); continue; };
            let met = match t.comparison { Comparison::AtLeast => v >= t.value, Comparison::AtMost => v <= t.value };
            if !met { failed.push(c.id.clone()); }
        }
        if required == 0 { return Err("empty_required_inventory".into()); }
        if !missing.is_empty() { Ok(Outcome::Incomplete { missing }) }
        else if !failed.is_empty() { Ok(Outcome::Fail { reasons: failed }) } else { Ok(Outcome::Pass) }
    }
    let outcome = resolve(claim, expected, registry).unwrap_or_else(|e| Outcome::Incomplete { missing: vec![e] });
    Resolution { publication_eligible: matches!(outcome, Outcome::Pass), release_authorized: false,
        verdict: Verdict { requirement_set: claim.requirement_set.clone(), group: claim.group.clone(), outcome } }
}
