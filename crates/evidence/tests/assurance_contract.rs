//! Synthetic contract controls: these never qualify the native product or a physical specimen.
use jarambit_evidence::{assurance::*, identity::*, *};
use serde_json::json;

fn fixture() -> (ClaimRecord, ExpectedInventory, Registry) {
    let mut reg = Registry::default();
    let mut add = |id: &str, kind| {
        let bytes = format!("synthetic control {id}").into_bytes();
        let reference = ContentRef::from_bytes(id, "fixture-v1", &bytes);
        reg.artifacts.push(Artifact::new(reference.clone(), bytes, kind).unwrap()); reference
    };
    let req = add("RS-fixture", ArtifactKind::Source);
    let identity = EvidenceIdentity {
        scientific: ScientificIdentity { schema: 2,
            subject: SubjectRef::NativeCad { artifact: add("box.step", ArtifactKind::Source),
                geometry_state: add("box.geometry", ArtifactKind::Source), format: CadFormat::Step, unit: LengthUnit::Millimetre },
            requirements: vec![req.clone()], source: add("source", ArtifactKind::Source),
            build: add("build", ArtifactKind::Source), cargo_lock: add("lock", ArtifactKind::Source),
            config: add("config", ArtifactKind::Source), evaluator: add("evaluator", ArtifactKind::Source),
            scenario: add("scenario", ArtifactKind::Source), objective: add("objective", ArtifactKind::Source),
            descriptor: add("descriptor", ArtifactKind::Source), material: MaterialState::Unknown { reason: "synthetic screening control".into() }, dependencies: vec![] },
        model: add("model", ArtifactKind::Source),
        observable: ObservableSpec { quantity: "safety_factor".into(), unit: Unit::Dimensionless,
            frame: "fixture_frame".into(), region: "fixture_roi".into(), recovery: "unrounded_scalar".into() },
    };
    let source = add("solver_output", ArtifactKind::SolverOutput);
    add("review_receipt", ArtifactKind::Source);
    let obs = Observation { schema: 2, id: "root".into(), producer: "fixture_solver".into(), identity: identity.clone(),
        value: Some(Finite::new(1.575).unwrap()), not_applicable_reason: None, source, origin: Origin::Simulation,
        evidence_class: EvidenceClass::NumericalVerification,
        state: EvidenceState { execution: Execution::Succeeded, numerical: Numerical::Verified, validation: Validation::NotPerformed },
        dependencies: vec![], uncertainty: vec![] };
    reg.observations.push(obs); approve(&mut reg, "root", 1);
    let ex = ExpectedInventory { id: "required_fixture_cases".into(), requirement_set: "RS-fixture".into(), group: "numerical_fixture".into(), requirements: vec![req], criteria: vec![Criterion {
        id: "case-1".into(), role: Role::Required, observation: "root".into(), identity,
        required_class: EvidenceClass::NumericalVerification,
        threshold: Some(Threshold { comparison: Comparison::AtLeast, value: Finite::new(1.575).unwrap() }), allow_not_applicable: false }] };
    let bytes = serde_json::to_vec(&ex).unwrap();
    let reference = ContentRef::from_bytes(&ex.id, "fixture-v1", &bytes);
    reg.install_approved_inventory(TrustedInventory::from_approved_bytes(reference.clone(), &ex.requirements, &bytes).unwrap());
    let claim = ClaimRecord { id: "fixture-claim".into(), inventory: reference, requirement_set: "RS-fixture".into(), group: "numerical_fixture".into() };
    (claim, ex, reg)
}
fn authorized_policy(c: &mut ClaimRecord, ex: &ExpectedInventory, r: &mut Registry) {
    let bytes = serde_json::to_vec(ex).unwrap();
    let reference = ContentRef::from_bytes(&ex.id, "fixture-authorized-v2", &bytes);
    r.install_approved_inventory(TrustedInventory::from_approved_bytes(reference.clone(), &ex.requirements, &bytes).unwrap());
    c.inventory = reference;
}
fn approve(reg: &mut Registry, id: &str, sequence: u64) {
    let bytes = b"synthetic control review_receipt";
    let (reference, raw, kind, hash) = {
        let obs = reg.observations.iter_mut().find(|o| o.id == id).unwrap();
        let raw = serde_json::to_vec(&obs.source_record().unwrap()).unwrap();
        obs.source = ContentRef::from_bytes(&format!("source-{id}"), "fixture-v1", &raw);
        let kind = match obs.origin { Origin::Simulation => ArtifactKind::SolverOutput,
            Origin::Measurement => ArtifactKind::Acquisition, Origin::Synthetic => ArtifactKind::Synthetic };
        (obs.source.clone(), raw, kind, obs.sha256().unwrap())
    };
    reg.artifacts.retain(|a| a.reference().id != reference.id);
    reg.artifacts.push(Artifact::new(reference, raw, kind).unwrap());
    reg.reviews.push(ReviewEvent { sequence, observation: id.into(), observation_sha256: hash,
        action: ReviewAction::Approved, reviewer: "independent_fixture_reviewer".into(),
        receipt: ContentRef::from_bytes("review_receipt", "fixture-v1", bytes) });
}
fn incomplete(c: &ClaimRecord, e: &ExpectedInventory, r: &Registry, reason: &str) {
    let out = resolve_claim(c, e, r);
    assert!(!out.publication_eligible && !out.release_authorized);
    match out.verdict.outcome { Outcome::Incomplete { missing } => assert!(missing.iter().any(|s| s.contains(reason)), "{missing:?}"), other => panic!("{other:?}") }
}

#[test]
fn complete_control_and_full_precision_boundary() {
    let (c, e, mut r) = fixture();
    assert!(matches!(resolve_claim(&c, &e, &r).verdict.outcome, Outcome::Pass));
    assert!(!resolve_claim(&c, &e, &r).release_authorized);
    r.observations[0].value = Some(Finite::new(1.5749999999999998).unwrap()); approve(&mut r, "root", 2);
    assert!(matches!(resolve_claim(&c, &e, &r).verdict.outcome, Outcome::Fail { .. }));
}

#[test]
fn missing_empty_duplicate_inventory_and_optional_display() {
    let (c, mut e, mut r) = fixture();
    r.observations.clear(); r.reviews.clear(); incomplete(&c, &e, &r, "missing_observation");
    let (c, _, r) = fixture(); e.criteria.clear(); incomplete(&c, &e, &r, "missing_expected_inventory");
    let (c, mut e, r) = fixture(); e.criteria.push(e.criteria[0].clone()); incomplete(&c, &e, &r, "frozen_inventory");
    let (mut c, mut e, mut r) = fixture(); let mut optional = e.criteria[0].clone();
    optional.id = "display-only".into(); optional.role = Role::Optional; optional.observation = "absent".into(); e.criteria.push(optional);
    authorized_policy(&mut c, &e, &mut r); assert!(resolve_claim(&c, &e, &r).publication_eligible);
    e.criteria[0].role = Role::RecordOnly; authorized_policy(&mut c, &e, &mut r); incomplete(&c, &e, &r, "empty_required_inventory");
}

#[test]
fn exact_identity_mutations_are_nonpassing() {
    for field in ["requirements", "evaluator", "config", "source", "build", "scenario", "model", "subject", "unit", "region", "recovery"] {
        let (c, e, mut r) = fixture();
        let o = &mut r.observations[0];
        match field {
            "requirements" => o.identity.scientific.requirements[0].sha256 = "0".repeat(64),
            "evaluator" => o.identity.scientific.evaluator.sha256 = "0".repeat(64),
            "config" => o.identity.scientific.config.revision = "different".into(),
            "source" => o.identity.scientific.source.sha256 = "0".repeat(64),
            "build" => o.identity.scientific.build.sha256 = "0".repeat(64),
            "scenario" => o.identity.scientific.scenario.sha256 = "0".repeat(64),
            "model" => o.identity.model.sha256 = "0".repeat(64),
            "subject" => if let SubjectRef::NativeCad { unit, .. } = &mut o.identity.scientific.subject { *unit = LengthUnit::Metre; },
            "unit" => o.identity.observable.unit = Unit::Megapascal,
            "region" => o.identity.observable.region = "wrong-region".into(),
            "recovery" => o.identity.observable.recovery = "smoothed-peak".into(),
            _ => unreachable!(),
        }
        approve(&mut r, "root", 2);
        assert!(!resolve_claim(&c, &e, &r).publication_eligible, "{field}");
    }
}

#[test]
fn w84_reopening_withdraws_transitive_support_without_discarding_value() {
    let (mut c, mut e, mut r) = fixture();
    let child = r.observations[0].clone();
    let mut parent = child.clone(); parent.id = "aggregate".into();
    parent.dependencies.push(ObservationRef { id: child.id.clone(), sha256: child.sha256().unwrap() });
    r.observations.push(parent); approve(&mut r, "aggregate", 2); e.criteria[0].observation = "aggregate".into();
    authorized_policy(&mut c, &e, &mut r);
    assert!(resolve_claim(&c, &e, &r).publication_eligible);
    let mut reopened = r.reviews[0].clone(); reopened.sequence = 3; reopened.action = ReviewAction::Reopened; r.reviews.push(reopened);
    incomplete(&c, &e, &r, "review_revoked_or_stale");
    assert_eq!(r.observations[0].value.unwrap().get(), 1.575);
}

#[test]
fn changed_dependency_needs_new_parent_binding_and_review() {
    let (mut c, mut e, mut r) = fixture();
    let mut parent = r.observations[0].clone(); parent.id = "parent".into();
    parent.dependencies.push(ObservationRef { id: "root".into(), sha256: r.observations[0].sha256().unwrap() });
    r.observations.push(parent); approve(&mut r, "parent", 2); e.criteria[0].observation = "parent".into();
    authorized_policy(&mut c, &e, &mut r);
    r.observations[0].value = Some(Finite::new(2.0).unwrap()); approve(&mut r, "root", 3);
    incomplete(&c, &e, &r, "dependency_identity_mismatch");
}

#[test]
fn cycles_missing_dependencies_duplicate_records_and_nonindependent_review() {
    let (c, e, mut r) = fixture();
    r.observations[0].dependencies.push(ObservationRef { id: "root".into(), sha256: "0".repeat(64) });
    incomplete(&c, &e, &r, "dependency_cycle");
    r.observations[0].dependencies[0].id = "missing".into(); incomplete(&c, &e, &r, "missing_observation");
    let (c, e, mut r) = fixture(); r.observations.push(r.observations[0].clone()); incomplete(&c, &e, &r, "duplicate_observation");
    let (c, e, mut r) = fixture(); r.reviews[0].reviewer = "fixture_solver".into(); incomplete(&c, &e, &r, "review_not_independent");
    let (c, e, mut r) = fixture(); r.reviews.push(r.reviews[0].clone()); incomplete(&c, &e, &r, "review_sequence");
}

#[test]
fn failed_unverified_and_missing_physical_evidence_never_pass() {
    let (mut c, mut e, mut r) = fixture();
    r.observations[0].state.execution = Execution::Failed; approve(&mut r, "root", 2);
    incomplete(&c, &e, &r, "invalid_or_unexecuted");
    r.observations[0].state.execution = Execution::Succeeded; r.observations[0].state.numerical = Numerical::Invalid; approve(&mut r, "root", 3);
    incomplete(&c, &e, &r, "invalid_or_unexecuted");
    r.observations[0].state.numerical = Numerical::Verified; approve(&mut r, "root", 4);
    e.criteria[0].required_class = EvidenceClass::PhysicalValidation; authorized_policy(&mut c, &e, &mut r); incomplete(&c, &e, &r, "scope_or_class_mismatch");
    r.observations[0].state.validation = Validation::Validated;
    assert_eq!(r.observations[0].check().unwrap_err(), "unsupported_physical_validation");
    assert!(ingest_observation(&serde_json::to_vec(&r.observations[0]).unwrap()).is_err());
}

#[test]
fn explicit_not_applicable_and_uncertainty_bounds() {
    let (mut c, mut e, mut r) = fixture();
    r.observations[0].value = None; r.observations[0].not_applicable_reason = Some("fixture-domain exemption".into()); approve(&mut r, "root", 2);
    incomplete(&c, &e, &r, "not_applicable_forbidden");
    e.criteria[0].allow_not_applicable = true; authorized_policy(&mut c, &e, &mut r); assert!(resolve_claim(&c, &e, &r).publication_eligible);
    r.observations[0].uncertainty.push(Uncertainty { kind: "discretization".into(), amount: Finite::new(-0.1).unwrap(),
        method: "fixture".into(), domain: "fixture".into(), dependence: "unknown".into(), coverage_interpretation: "not a confidence interval".into() });
    assert_eq!(r.observations[0].check().unwrap_err(), "negative_uncertainty");
}

#[test]
fn strict_ingest_nonfinite_boolean_unknown_and_bounds_controls() {
    for raw in ["NaN", "Infinity", "1e999", "1e-999", "18446744073709551616", "{\"a\":1,\"a\":2}", "[1,]", "1 2"] { assert!(strict_json(raw.as_bytes()).is_err(), "{raw}"); }
    for raw in ["true", "false", "null", "\"1.2\""] { assert!(strict_decode::<Finite>(raw.as_bytes()).is_err(), "{raw}"); }
    for x in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] { assert!(Finite::new(x).is_err()); }
    assert_eq!(strict_decode::<Finite>(b"0").unwrap().get(), 0.0);
    assert_eq!(strict_json(b"-0").unwrap().as_f64().unwrap().to_bits(), (-0.0f64).to_bits());
    assert!(strict_json(format!("{}0{}", "[".repeat(65), "]".repeat(65)).as_bytes()).is_err());
    assert!(strict_json(&vec![b' '; 1_048_577]).is_err());
    let (_, _, r) = fixture(); let mut value = serde_json::to_value(&r.observations[0]).unwrap();
    value["state"]["numerical"] = json!("healthy"); assert!(ingest_observation(&serde_json::to_vec(&value).unwrap()).is_err());
    value["state"]["numerical"] = json!("verified"); value["unexpected"] = json!(1); assert!(ingest_observation(&serde_json::to_vec(&value).unwrap()).is_err());
}

#[test]
fn historical_manifest_and_runtime_separation() {
    let old = r#"{"schema":1,"tool":"jarambit","tool_version":"0.31.0","requirement_set":"RS-fixture","op_version":1,"command":"test","seed":7,"params":{}}"#;
    let historical: RunManifest = serde_json::from_str(old).unwrap();
    assert_eq!(historical.canonical_json(), old); assert!(historical.scientific_sha256().is_err());
    let (_, e, _) = fixture();
    let mut qualified = RunManifest::qualified("test", 7, e.criteria[0].identity.scientific.clone()).unwrap();
    let hash = qualified.scientific_sha256().unwrap();
    qualified.runtime = Some(RuntimeMetadata { host: "another-host".into(), threads: 4, ..Default::default() });
    assert_eq!(hash, qualified.scientific_sha256().unwrap());
    qualified.seed += 1; assert_ne!(hash, qualified.scientific_sha256().unwrap());
    qualified.seed -= 1; qualified.params.insert("mesh_area".into(), json!(0.125)); assert_ne!(hash, qualified.scientific_sha256().unwrap());
    qualified.schema = 99; assert!(qualified.scientific_sha256().is_err());
}

#[test]
fn artifact_hash_and_unicode_specimen_identity() {
    let reference = ContentRef::from_bytes("fixture", "1", b"original");
    assert!(Artifact::new(reference.clone(), b"tampered".to_vec(), ArtifactKind::Source).is_err());
    let subject = SubjectRef::Specimen { id: "试样-é".into(), passport: reference }; subject.check().unwrap();
    assert_eq!(strict_decode::<SubjectRef>(&serde_json::to_vec(&subject).unwrap()).unwrap(), subject);
    let a = strict_json(br#"{"a":18446744073709551615,"b":1e0,"c":-0.0}"#).unwrap();
    let b = strict_json(br#"{"c":-0.0,"b":1.0,"a":18446744073709551615}"#).unwrap();
    assert_eq!(canonical_wire(&a).unwrap(), canonical_wire(&b).unwrap());
    assert_ne!(canonical_wire(&json!(-0.0)).unwrap(), canonical_wire(&json!(0.0)).unwrap());
}

#[test]
fn raw_scalar_or_subject_relabel_cannot_gain_support() {
    let (c, e, mut r) = fixture();
    r.observations[0].value = Some(Finite::new(2.0).unwrap());
    // Even a new metadata review cannot substitute for the unchanged raw scalar envelope.
    r.reviews[0].observation_sha256 = r.observations[0].sha256().unwrap();
    incomplete(&c, &e, &r, "source_observation_binding_mismatch");
    let (c, e, mut r) = fixture();
    let obs = &mut r.observations[0];
    obs.identity.scientific.subject = SubjectRef::Genome { representation: e.requirements[0].clone(), bits: vec!["3ff0000000000000".into()] };
    r.reviews[0].observation_sha256 = obs.sha256().unwrap();
    incomplete(&c, &e, &r, "source_observation_binding_mismatch");
}

#[test]
fn approved_inventory_content_cannot_be_mutated_or_self_rehashed() {
    let (mut c, mut e, mut r) = fixture();
    e.criteria[0].threshold.as_mut().unwrap().value = Finite::new(2.0).unwrap();
    authorized_policy(&mut c, &e, &mut r);
    assert!(matches!(resolve_claim(&c, &e, &r).verdict.outcome, Outcome::Fail { .. }));
    let mut weaker = e.clone(); weaker.criteria[0].threshold.as_mut().unwrap().value = Finite::new(1.0).unwrap();
    incomplete(&c, &weaker, &r, "frozen_inventory_policy_mismatch");
    let mut forged = c.clone(); forged.inventory = ContentRef::from_bytes(&weaker.id, &c.inventory.revision, &serde_json::to_vec(&weaker).unwrap());
    incomplete(&forged, &weaker, &r, "frozen_inventory_policy_mismatch");
    for role in [Role::Optional, Role::RecordOnly] {
        let mut changed = e.clone(); changed.criteria[0].role = role; incomplete(&c, &changed, &r, "frozen_inventory_policy_mismatch");
    }
    let mut changed = e.clone(); changed.criteria[0].allow_not_applicable = true;
    incomplete(&c, &changed, &r, "frozen_inventory_policy_mismatch");
    let mut second = e.criteria[0].clone(); second.id = "case-2".into(); e.criteria.push(second);
    authorized_policy(&mut c, &e, &mut r);
    e.criteria.pop(); incomplete(&c, &e, &r, "frozen_inventory_policy_mismatch");
    // Explicit authenticated-caller policy admission is a new identity, not an incoming self-rehash.
    authorized_policy(&mut c, &weaker, &mut r); assert!(resolve_claim(&c, &weaker, &r).publication_eligible);
    let (c, e, r) = fixture(); let mut untrusted = Registry::default();
    untrusted.artifacts = r.artifacts; untrusted.observations = r.observations; untrusted.reviews = r.reviews;
    incomplete(&c, &e, &untrusted, "inventory_policy_authority_missing");
    let (mut c, e, r) = fixture(); c.group = "physical_validation".into(); incomplete(&c, &e, &r, "claim_scope_mismatch");
}

#[test]
fn unicode_identity_collision_and_general_key_boundary_contract() {
    assert_eq!(unicode_normalization::UNICODE_VERSION, (15, 0, 0));
    assert!(strict_json("{\"é\":1,\"e\\u0301\":2}".as_bytes()).is_err());
    assert!(unique_ids(["é", "e\u{301}"]).is_err());
    let (_, e, _) = fixture(); let mut identity = e.criteria[0].identity.scientific.clone();
    let mut first = identity.requirements[0].clone(); first.id = "é".into();
    let mut second = first.clone(); second.id = "e\u{301}".into(); identity.requirements = vec![first, second];
    assert!(identity.check().is_err());
    for key in [String::new(), "\u{0000}".into(), "x".repeat(513)] {
        let value = json!({ key.clone(): "试样" }); let raw = serde_json::to_vec(&value).unwrap();
        assert_eq!(canonical_wire(&strict_json(&raw).unwrap()).unwrap(), canonical_wire(&value).unwrap());
        assert!(check_id(&key).is_err());
    }
    unique_ids(["试样-é"]).unwrap();
    assert_eq!(strict_decode::<Finite>(b"9007199254740993").unwrap_err().contains("inexact"), true);
}

/// Offline control runner supplies only its owned fixture path; no receipt argv is executed.
#[test]
fn wire_probe() {
    if let Ok(path) = std::env::var("JARAMBIT_SCIENCE_WIRE_INPUT") {
        let bytes = std::fs::read(path).unwrap();
        match strict_json(&bytes).and_then(|v| canonical_wire(&v)) {
            Ok(wire) => println!("SCIENCE_WIRE_HEX={}", hex(&wire)),
            Err(error) => println!("SCIENCE_WIRE_ERROR={error}"),
        }
    }
}

#[test]
fn failed_serialization_and_qualified_log_policy() {
    struct CannotSerialize;
    impl serde::Serialize for CannotSerialize {
        fn serialize<S: serde::Serializer>(&self, _: S) -> Result<S::Ok, S::Error> {
            Err(serde::ser::Error::custom("owned serialization failure"))
        }
    }
    assert!(scientific_hash(&CannotSerialize).is_err());
    let (_, e, _) = fixture();
    let m = RunManifest::qualified("fixture", 7, e.criteria[0].identity.scientific.clone()).unwrap();
    assert_eq!(RunManifest::ingest_qualified(&serde_json::to_vec(&m).unwrap()).unwrap().scientific_sha256(), m.scientific_sha256());
    let mut json = serde_json::to_value(&m).unwrap(); json["unknown"] = json!(1);
    assert!(RunManifest::ingest_qualified(&serde_json::to_vec(&json).unwrap()).is_err());
    let dir = std::env::temp_dir().join(format!("qualified_jev_{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap(); let path = dir.join("qualified.jevl");
    { let _log = EvidenceLog::create(path.to_str().unwrap(), &m).unwrap(); }
    let log = read_log(path.to_str().unwrap()).unwrap();
    match &log.events[0] { Event::RunStart { manifest, .. } => assert_eq!(manifest.scientific_sha256(), m.scientific_sha256()), _ => panic!("wrong frame") }
}
