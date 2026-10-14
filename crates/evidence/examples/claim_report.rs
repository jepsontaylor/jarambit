//! Closed two-file S03 bridge. Caller admission D is external to this executable.
//! The embedded synthetic authority A grants software-fixture authority only.
use jarambit_evidence::assurance::{
    resolve_claim, Artifact, ArtifactKind, ClaimRecord, ExpectedInventory, Observation,
    Registry, ReviewEvent, ReviewScope, TrustedInventory, TrustedReview,
};
use jarambit_evidence::identity::{is_hash, scientific_hash, strict_decode, ContentRef};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::path::Path;

const LIMIT: usize = 1_048_576;
const CORPUS_LIMIT: usize = 8_388_608;
const BOOTSTRAP: &str = include_str!("../../../assurance/registry/trusted-bootstrap.v1.json");

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    schema: u32,
    claim: ClaimRecord,
    expected: ExpectedInventory,
    artifacts: Vec<ArtifactWire>,
    observations: Vec<Observation>,
    reviews: Vec<ReviewEvent>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ArtifactWire { reference: ContentRef, bytes_utf8: String, kind: ArtifactKind }
#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ApprovedRaw { reference: ContentRef, raw_utf8: String }
#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ApprovedReview {
    reference: ContentRef, approved_reviewer: String, approved_scope: ReviewScope, raw_utf8: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Bootstrap { schema: u32, provider: String, entries: BTreeMap<String, BootstrapEntry> }
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct BootstrapEntry {
    schema: u32, id: String, scope: ReviewScope, approved_inventory: ApprovedRaw,
    approved_requirements: Vec<ApprovedRaw>, approved_reviews: Vec<ApprovedReview>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawRoot { raw_utf8: String, raw_sha256: String }
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ActualBuild { stage: String, source_closure_sha256: Option<String>, binary_sha256: Option<String> }
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Roots { registry: RawRoot, reporting_policy: RawRoot, resolver_source_build_recipe: RawRoot, actual_build: ActualBuild }
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ReportContext {
    candidate_id: String, trusted_candidate_id: String, subject_sha256: String,
    current_registry: BTreeMap<String, String>, requested_evidence_class: String,
    physical_validation: String, mass_scope: String,
    #[serde(rename = "G1")]
    g1: BTreeMap<String, Value>,
    historical_D1: Option<Value>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Authority {
    schema: u32, bootstrap_id: String, provider: String,
    approved_inventory: ApprovedRaw, approved_requirements: Vec<ApprovedRaw>,
    approved_reviews: Vec<ApprovedReview>, roots: Roots, report_context: ReportContext,
}

fn hash(bytes: &[u8]) -> String { jarambit_evidence::hex(&Sha256::digest(bytes)) }
fn require(ok: bool, reason: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(reason.into()) }
}
fn read(path: &Path) -> Result<Vec<u8>, String> {
    let f = std::fs::File::open(path).map_err(|e| format!("missing_input:{e}"))?;
    let mut bytes = Vec::new();
    f.take((LIMIT + 1) as u64).read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    require(bytes.len() <= LIMIT, "payload_too_large")?;
    Ok(bytes)
}
fn closed(value: &Value, keys: &[&str]) -> Result<(), String> {
    let obj = value.as_object().ok_or("object_required")?;
    let expected: BTreeSet<_> = keys.iter().copied().collect();
    require(obj.keys().map(String::as_str).collect::<BTreeSet<_>>() == expected, "unknown_nested_authority_field")
}
fn raw_root(root: &RawRoot) -> Result<Value, String> {
    require(hash(root.raw_utf8.as_bytes()) == root.raw_sha256, "raw_root_hash_mismatch")?;
    strict_decode(root.raw_utf8.as_bytes())
}
fn context(context: &ReportContext) -> Result<(), String> {
    for id in [&context.candidate_id, &context.trusted_candidate_id, &context.requested_evidence_class, &context.physical_validation, &context.mass_scope] {
        jarambit_evidence::identity::check_id(id)?;
    }
    require(is_hash(&context.subject_sha256), "report_context_subject_hash")?;
    for (candidate, state) in &context.current_registry {
        jarambit_evidence::identity::check_id(candidate)?;
        jarambit_evidence::identity::check_id(state)?;
    }
    let keys: BTreeSet<_> = ["solid_tip_sf_nodal_max", "plate_tipsub_screen_sf", "twist_tipzone_sf_strict", "spg", "aes_score", "mass_g", "seq_ratio"].into_iter().collect();
    require(context.g1.keys().all(|k| keys.contains(k.as_str())), "metric_context_keys")?;
    // G1 is reporting-only. Ops validates its numeric domains without changing
    // this unrelated SF Resolution (including invalid AES or missing inputs).
    if let Some(history) = &context.historical_D1 {
        closed(history, &["label", "strict_lateral_N", "strict_tip_sf", "seq_ratio", "promote_eligible", "scope"])?;
    }
    Ok(())
}

fn run(request_path: &Path, authority_path: &Path) -> Result<Value, String> {
    let request_bytes = read(request_path)?;
    let authority_bytes = read(authority_path)?;
    let request: Request = strict_decode(&request_bytes).map_err(|e| -> String {
        if e.contains("unknown field") { "unknown_request_field".into() }
        else { "strict_scalar_ingress".into() }
    })?;
    let authority: Authority = strict_decode(&authority_bytes).map_err(|_| "unknown_authority_field")?;
    require(request.schema == 2 && authority.schema == 2, "wire_schema")?;
    require(authority.provider == "explicit_local_synthetic_fixture_trust_not_external_authentication", "untrusted_authority_root")?;
    require(BOOTSTRAP.len() <= CORPUS_LIMIT, "compiled_corpus_limit")?;
    // The corpus is immutable compile-time A, independently pinned by D. Each
    // supplied request/authority/raw record uses S01's bounded strict decoder.
    let bootstrap: Bootstrap = serde_json::from_str(BOOTSTRAP).map_err(|e| e.to_string())?;
    require(bootstrap.schema == 1 && bootstrap.provider == "local_synthetic_only", "compiled_bootstrap_schema")?;
    let entry = bootstrap.entries.get(&authority.bootstrap_id).ok_or("untrusted_authority_root")?;
    require(entry.schema == 1 && entry.id == authority.bootstrap_id, "compiled_entry_schema")?;
    require(entry.scope.group == "software_fixture" && entry.scope.requirement_set == "RS-T02-fixture", "synthetic_authority_scope")?;
    require(authority.approved_inventory == entry.approved_inventory
        && authority.approved_requirements == entry.approved_requirements
        && authority.approved_reviews == entry.approved_reviews, "untrusted_authority_root")?;
    context(&authority.report_context)?;
    let registry_root = raw_root(&authority.roots.registry)?;
    closed(&registry_root, &["schema", "revision", "candidates", "candidate_subjects", "current_by_scope", "class"])?;
    let policy = raw_root(&authority.roots.reporting_policy)?;
    closed(&policy, &["authority", "authority_wire_keys", "bootstrap", "candidate_current_scope", "canonical_wire", "deny_unknown", "fixture_evidence_class", "fixture_requirement", "layer_rule", "max_bytes", "max_depth", "max_nodes", "metric_display_contract", "output_refused_keys", "output_resolved_keys", "physical_provider", "report_canonicalization", "request_wire_keys", "revision", "runtime_cache_rule", "schema"])?;
    let recipe = raw_root(&authority.roots.resolver_source_build_recipe)?;
    let actual = &authority.roots.actual_build;
    let source_hash = actual.source_closure_sha256.as_deref().ok_or("unbuilt_source_or_binary")?;
    let binary_hash = actual.binary_sha256.as_deref().ok_or("unbuilt_source_or_binary")?;
    require(actual.stage == "runtime_admitted" && is_hash(source_hash) && is_hash(binary_hash), "unbuilt_source_or_binary")?;
    closed(&recipe, &["schema", "stage", "source_closure_sha256", "source_head", "build_argv", "build_environment", "compiler_files", "dependency_files"])?;
    require(recipe["schema"].as_u64() == Some(1) && recipe["stage"] == "source_bound_build" && recipe["source_closure_sha256"] == source_hash, "unbuilt_source_or_binary")?;
    let executable = std::env::current_exe().map_err(|e| e.to_string())?;
    require(hash(&std::fs::read(executable).map_err(|e| e.to_string())?) == binary_hash, "untrusted_binary")?;
    // B is bound by independently approved external D. A payload alone cannot
    // approve B; direct invocation is not a report/caller qualification receipt.
    let mut registry = Registry::default();
    let requirements: Vec<ContentRef> = entry.approved_requirements.iter().map(|r| r.reference.clone()).collect();
    for r in &entry.approved_requirements {
        require(ContentRef::from_bytes(&r.reference.id, &r.reference.revision, r.raw_utf8.as_bytes()) == r.reference, "compiled_requirement_bytes")?;
    }
    registry.install_approved_inventory(TrustedInventory::from_approved_bytes(
        entry.approved_inventory.reference.clone(), &requirements,
        authority.approved_inventory.raw_utf8.as_bytes(),
    )?);
    for review in &entry.approved_reviews {
        registry.install_approved_review(TrustedReview::from_approved_bytes(
            review.reference.clone(), &review.approved_reviewer, &review.approved_scope,
            review.raw_utf8.as_bytes(),
        )?);
    }
    for a in request.artifacts {
        registry.artifacts.push(Artifact::new(a.reference, a.bytes_utf8.into_bytes(), a.kind)?);
    }
    for o in &request.observations {
        if o.identity.observable.quantity == "safety_factor" {
            if let Some(value) = o.value { require(value.get() >= 0.0, "invalid_scalar_domain")?; }
        }
    }
    registry.observations = request.observations;
    registry.reviews = request.reviews;
    let resolved = resolve_claim(&request.claim, &request.expected, &registry);
    let entry_value = serde_json::to_value(entry).map_err(|e| e.to_string())?;
    let entry_raw = format!("{}\n", serde_json::to_string(&entry_value).map_err(|e| e.to_string())?);
    // Assert the same S01 identity machinery is available; no custom verdict or
    // threshold implementation is substituted for resolve_claim.
    scientific_hash(&request.expected)?;
    Ok(json!({"schema":1,"kind":"resolved","claim_id":request.claim.id,
        "verdict":resolved.verdict,"publication_eligible":resolved.publication_eligible,
        "release_authorized":resolved.release_authorized,
        "input_binding":{
            "request_raw_sha256":hash(&request_bytes),"authority_raw_sha256":hash(&authority_bytes),
            "compiled_trust_dataset_raw_sha256":hash(BOOTSTRAP.as_bytes()),
            "trusted_entry_raw_sha256":hash(entry_raw.as_bytes()),
            "registry_raw_sha256":authority.roots.registry.raw_sha256,
            "reporting_policy_raw_sha256":authority.roots.reporting_policy.raw_sha256,
            "resolver_source_build_recipe_raw_sha256":authority.roots.resolver_source_build_recipe.raw_sha256,
            "actual_resolver_source_closure_sha256":source_hash,
            "actual_resolver_binary_sha256":binary_hash
        }}))
}

fn main() {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    let result = if args.len() != 2 || args.iter().any(|a| a.to_string_lossy().starts_with("--")) {
        Err("two_positional_files_required_no_override".into())
    } else { run(Path::new(&args[0]), Path::new(&args[1])) };
    match result {
        Ok(value) => { println!("{}", value); }
        Err(reason) => { println!("{}", json!({"schema":1,"kind":"refused","reason":reason})); std::process::exit(2); }
    }
}
