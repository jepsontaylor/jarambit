//! jarambit-evidence (PR-0.29.1): run manifest, typed observations, scoped verdicts, and an append-only
//! event log so any published candidate can replay its creation / evaluation / selection history.
//!
//! Log format (`*.jevl`): a sequence of frames, one per generation, each
//! `[magic "JEV1"][u32 LE compressed length][u64 LE FNV-1a of the compressed bytes][zstd frame]`.
//! The zstd frame holds JSON Lines, one [`Event`] per line. Every frame is written with one `write_all`
//! and then `fsync`ed, so a crash (kill -9) leaves a valid prefix plus at most one torn tail frame,
//! which [`read_log`] detects (length / hash) and drops.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::io::Write;
pub mod identity;
pub mod assurance;

pub type Id = u64;
/// Version of the variation-operator semantics recorded with every birth (bump when operators change).
pub const OP_VERSION: u32 = 1;
pub const SCHEMA: u32 = 1;
const MAGIC: &[u8; 4] = b"JEV1";

/// Everything that determines a run. Its SHA-256 (canonical JSON) binds logs and checkpoints to the run.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RunManifest {
    pub schema: u32,
    pub tool: String,
    pub tool_version: String,
    pub requirement_set: String,
    pub op_version: u32,
    pub command: String,
    pub seed: u64,
    /// Remaining knobs (pop, gens, threads, fem area, env overrides ...), sorted by key.
    pub params: BTreeMap<String, serde_json::Value>,
    /// Absent in JEV1 historical manifests; absence can never qualify a new scientific claim.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scientific: Option<identity::ScientificIdentity>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub runtime: Option<identity::RuntimeMetadata>,
}
impl RunManifest {
    pub fn new(command: &str, seed: u64, requirement_set: &str) -> Self {
        RunManifest { schema: SCHEMA, tool: "jarambit".into(), tool_version: include_str!("../../../docs/VERSION").trim().into(), requirement_set: requirement_set.into(),
            op_version: OP_VERSION, command: command.into(), seed, params: BTreeMap::new(), scientific: None, runtime: None }
    }
    pub fn param(mut self, k: &str, v: impl Into<serde_json::Value>) -> Self { self.params.insert(k.into(), v.into()); self }
    pub fn canonical_json(&self) -> String { serde_json::to_string(self).expect("manifest serialises") }
    pub fn sha256(&self) -> String { hex(&Sha256::digest(self.canonical_json().as_bytes())) }
    pub fn qualified(command: &str, seed: u64, identity: identity::ScientificIdentity) -> Result<Self, String> {
        identity.check()?;
        let mut m = Self::new(command, seed, &identity.requirements[0].id);
        m.schema = 2; m.scientific = Some(identity); Ok(m)
    }
    /// Historical records remain readable with their original hash; only checked v2 identity qualifies.
    pub fn scientific_sha256(&self) -> Result<String, String> {
        if self.schema != 2 { return Err("historical_or_unsupported_manifest".into()); }
        let identity = self.scientific.as_ref().ok_or("scientific_identity_missing")?;
        if identity.requirements.first().map(|r| r.id.as_str()) != Some(self.requirement_set.as_str()) { return Err("manifest_requirement_mismatch".into()); }
        identity.check()?;
        identity::scientific_hash(&serde_json::json!({"identity": identity, "seed": self.seed,
            "command": self.command, "op_version": self.op_version, "params": self.params}))
    }
    pub fn ingest_qualified(bytes: &[u8]) -> Result<Self, String> {
        let value = identity::strict_json(bytes)?;
        let fields = value.as_object().ok_or("manifest object required")?;
        let allowed = ["schema", "tool", "tool_version", "requirement_set", "op_version", "command", "seed", "params", "scientific", "runtime"];
        if fields.keys().any(|key| !allowed.contains(&key.as_str())) { return Err("unknown qualified manifest field".into()); }
        let manifest: Self = serde_json::from_value(value).map_err(|e| e.to_string())?;
        manifest.scientific_sha256()?; Ok(manifest)
    }
}
pub fn hex(b: &[u8]) -> String { b.iter().map(|x| format!("{x:02x}")).collect() }

/// A typed observation: a value, or an explicit reason it is absent. Never a silent default.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Obs<T> {
    Value { value: T },
    NotEvaluated,
    Failed { reason: String },
}
impl Obs<f64> {
    /// Finite -> Value; non-finite -> Failed("non-finite").
    pub fn finite(x: f64) -> Self { if x.is_finite() { Obs::Value { value: x } } else { Obs::Failed { reason: "non-finite".into() } } }
}
impl<T: Clone> Obs<T> {
    pub fn value(&self) -> Option<T> { match self { Obs::Value { value } => Some(value.clone()), _ => None } }
}

/// A verdict is always scoped to a requirement set and a group (see requirements/*.toml).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Verdict {
    pub requirement_set: String,
    pub group: String,
    #[serde(flatten)]
    pub outcome: Outcome,
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "outcome", rename_all = "snake_case")]
pub enum Outcome { Pass, Fail { reasons: Vec<String> }, Incomplete { missing: Vec<String> } }

/// Log events. `Eval` = a fresh evaluation (a birth); `Elite` / `Migration` = re-appearances of existing ids.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(tag = "ev", rename_all = "snake_case")]
pub enum Event {
    RunStart { manifest: RunManifest, manifest_sha256: String },
    Eval { gen: usize, island: usize, id: Id, parents: Vec<Id>, op: String, op_version: u32, fit: Option<f64>, aes_pass: bool, legal: bool, mass_g: Option<f64>, fem_status: String },
    Elite { gen: usize, island: usize, id: Id },
    Migration { gen: usize, from: usize, to: usize, ids: Vec<Id> },
    GenEnd { gen: usize, fresh_evals: u64, appearances: u64, archive_cells: usize, best_id: Option<Id>, best_fit: Option<f64> },
    RunEnd { fresh_evals: u64, appearances: u64 },
}

/// Where a search loop sends its events. `end_gen` marks a durability point.
pub trait Sink { fn event(&mut self, e: Event); fn end_gen(&mut self) {} }
/// Discards everything (default when no log is requested).
pub struct NullSink;
impl Sink for NullSink { fn event(&mut self, _: Event) {} }
/// Keeps events in memory (tests).
#[derive(Default)]
pub struct VecSink { pub events: Vec<Event>, pub gens_closed: usize }
impl Sink for VecSink { fn event(&mut self, e: Event) { self.events.push(e); } fn end_gen(&mut self) { self.gens_closed += 1; } }

fn fnv1a(b: &[u8]) -> u64 { let mut h: u64 = 0xcbf29ce484222325; for &x in b { h ^= x as u64; h = h.wrapping_mul(0x100000001b3); } h }

/// Append-only, fsync-per-generation event log.
pub struct EvidenceLog { f: std::fs::File, buf: Vec<u8>, pub frames: usize, err: Option<String> }
impl EvidenceLog {
    /// Create (truncate) `path` and durably write the RunStart frame.
    pub fn create(path: &str, manifest: &RunManifest) -> std::io::Result<Self> {
        let f = std::fs::OpenOptions::new().create(true).write(true).truncate(true).open(path)?;
        let mut l = EvidenceLog { f, buf: Vec::new(), frames: 0, err: None };
        l.event(Event::RunStart { manifest: manifest.clone(), manifest_sha256: manifest.sha256() });
        l.flush_frame()?; Ok(l)
    }
    fn flush_frame(&mut self) -> std::io::Result<()> {
        if self.buf.is_empty() { return Ok(()); }
        let z = zstd::bulk::compress(&self.buf, 3)?;
        let mut fr = Vec::with_capacity(z.len() + 16);
        fr.extend_from_slice(MAGIC); fr.extend_from_slice(&(z.len() as u32).to_le_bytes()); fr.extend_from_slice(&fnv1a(&z).to_le_bytes()); fr.extend_from_slice(&z);
        self.f.write_all(&fr)?; self.f.sync_data()?; self.buf.clear(); self.frames += 1; Ok(())
    }
    /// First I/O error seen (the search never panics on logging; the CLI reports this at the end).
    pub fn error(&self) -> Option<&str> { self.err.as_deref() }
}
impl Sink for EvidenceLog {
    fn event(&mut self, e: Event) { serde_json::to_writer(&mut self.buf, &e).expect("event serialises"); self.buf.push(b'\n'); }
    fn end_gen(&mut self) { if let Err(e) = self.flush_frame() { self.err.get_or_insert(e.to_string()); } }
}
impl Drop for EvidenceLog { fn drop(&mut self) { let _ = self.flush_frame(); } }

/// Result of reading a log: the events of every intact frame, and whether a torn / corrupt tail was dropped.
#[derive(Debug)]
pub struct ReadLog { pub events: Vec<Event>, pub frames: usize, pub torn_tail: bool }

pub fn read_bytes(b: &[u8]) -> Result<ReadLog, String> {
    let (mut i, mut events, mut frames) = (0usize, Vec::new(), 0usize);
    while i < b.len() {
        if b.len() - i < 16 || &b[i..i + 4] != MAGIC { return Ok(ReadLog { events, frames, torn_tail: true }); }
        let n = u32::from_le_bytes(b[i + 4..i + 8].try_into().unwrap()) as usize;
        let h = u64::from_le_bytes(b[i + 8..i + 16].try_into().unwrap());
        if b.len() - i - 16 < n || fnv1a(&b[i + 16..i + 16 + n]) != h { return Ok(ReadLog { events, frames, torn_tail: true }); }
        let raw = zstd::stream::decode_all(&b[i + 16..i + 16 + n]).map_err(|e| format!("frame {frames}: {e}"))?;
        for line in raw.split(|c| *c == b'\n').filter(|l| !l.is_empty()) {
            events.push(serde_json::from_slice(line).map_err(|e| format!("frame {frames}: {e}"))?);
        }
        frames += 1; i += 16 + n;
    }
    Ok(ReadLog { events, frames, torn_tail: false })
}
pub fn read_log(path: &str) -> Result<ReadLog, String> { read_bytes(&std::fs::read(path).map_err(|e| format!("{path}: {e}"))?) }
