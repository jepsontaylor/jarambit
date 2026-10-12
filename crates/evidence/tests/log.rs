//! PR-0.29.1: the evidence log survives crashes as a valid prefix.
use jarambit_evidence::*;

fn manifest() -> RunManifest { RunManifest::new("test", 7, "RS-karambit-v1").param("pop", 4).param("gens", 3) }

fn write_gens(path: &str, gens: usize, slow: bool) {
    let mut l = EvidenceLog::create(path, &manifest()).unwrap();
    let mut fresh = 0u64;
    for gen in 0..gens {
        for k in 0..20u64 { fresh += 1; l.event(Event::Eval { gen, island: 0, id: fresh, parents: vec![k], op: "mutate".into(), op_version: OP_VERSION, fit: Some(0.5), aes_pass: true, legal: k % 2 == 0, mass_g: Some(75.0), fem_status: "complete".into() }); }
        l.event(Event::GenEnd { gen, fresh_evals: fresh, appearances: fresh, archive_cells: gen, best_id: Some(fresh), best_fit: Some(1.0) });
        l.end_gen();
        if slow { std::thread::sleep(std::time::Duration::from_micros(300)); }
    }
}

/// A valid prefix: RunStart first, then whole generations (each ending in GenEnd with consecutive gen numbers).
fn assert_valid_prefix(r: &ReadLog) {
    let ev = &r.events;
    if ev.is_empty() { return; }
    assert!(matches!(ev[0], Event::RunStart { .. }));
    let mut gen_expected = 0usize; let mut in_gen = 0usize;
    for e in &ev[1..] { match e {
        Event::Eval { gen, .. } => { assert_eq!(*gen, gen_expected); in_gen += 1; }
        Event::GenEnd { gen, .. } => { assert_eq!(*gen, gen_expected); assert_eq!(in_gen, 20); gen_expected += 1; in_gen = 0; }
        _ => panic!("unexpected {e:?}") } }
    assert_eq!(in_gen, 0, "a generation was cut in half");
    assert_eq!(r.frames, gen_expected + 1);
}

#[test]
fn roundtrip_and_manifest_hash() {
    let d = std::env::temp_dir().join(format!("jev_rt_{}", std::process::id())); std::fs::create_dir_all(&d).unwrap();
    let p = d.join("a.jevl"); write_gens(p.to_str().unwrap(), 5, false);
    let r = read_log(p.to_str().unwrap()).unwrap(); assert!(!r.torn_tail); assert_eq!(r.frames, 6); assert_valid_prefix(&r);
    match &r.events[0] { Event::RunStart { manifest: m, manifest_sha256 } => { assert_eq!(m, &manifest()); assert_eq!(manifest_sha256, &manifest().sha256()); } _ => unreachable!() }
    assert_ne!(manifest().sha256(), manifest().param("pop", 5).sha256());
}

#[test]
fn obs_and_verdict_serde() {
    assert_eq!(serde_json::to_string(&Obs::finite(f64::NAN)).unwrap(), r#"{"status":"failed","reason":"non-finite"}"#);
    assert_eq!(serde_json::to_string(&Obs::<f64>::NotEvaluated).unwrap(), r#"{"status":"not_evaluated"}"#);
    let v = Verdict { requirement_set: "RS-karambit-v1".into(), group: "promotion".into(), outcome: Outcome::Fail { reasons: vec!["seq".into()] } };
    let s = serde_json::to_string(&v).unwrap(); assert!(s.contains("\"outcome\":\"fail\"") && s.contains("\"group\":\"promotion\""));
    assert_eq!(serde_json::from_str::<Verdict>(&s).unwrap(), v);
}

#[test]
fn truncation_at_any_byte_is_a_valid_prefix() {
    let d = std::env::temp_dir().join(format!("jev_tr_{}", std::process::id())); std::fs::create_dir_all(&d).unwrap();
    let p = d.join("a.jevl"); write_gens(p.to_str().unwrap(), 12, false);
    let full = std::fs::read(&p).unwrap();
    let mut x: u64 = 0x9e3779b97f4a7c15;
    for _ in 0..100 { x ^= x << 13; x ^= x >> 7; x ^= x << 17; let cut = (x % full.len() as u64) as usize;
        let r = read_bytes(&full[..cut]).unwrap(); assert_valid_prefix(&r); }
    // flipped byte inside the last frame -> that frame dropped, rest intact
    let mut bad = full.clone(); let n = bad.len(); bad[n - 3] ^= 0xff;
    let r = read_bytes(&bad).unwrap(); assert!(r.torn_tail); assert_eq!(r.frames, 12); assert_valid_prefix(&r);
}

/// Child mode for the kill -9 test: writes generations until killed.
#[test]
fn kill_child_writer() {
    if let Ok(p) = std::env::var("JEV_KILL_CHILD") { write_gens(&p, 100_000, true); }
}

#[cfg(unix)]
#[test]
fn kill_dash_9_leaves_valid_prefix_100_trials() {
    let exe = std::env::current_exe().unwrap();
    let d = std::env::temp_dir().join(format!("jev_kill_{}", std::process::id())); std::fs::create_dir_all(&d).unwrap();
    let mut x: u64 = 0x2545f4914f6cdd1d; let mut nonempty = 0;
    for t in 0..100 {
        let p = d.join(format!("k{t}.jevl"));
        let mut c = std::process::Command::new(&exe).args(["--exact", "kill_child_writer", "--nocapture", "--test-threads=1"]).env("JEV_KILL_CHILD", &p)
            .stdout(std::process::Stdio::null()).stderr(std::process::Stdio::null()).spawn().unwrap();
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        // Wait (bounded, 10 s) until the child has written at least 2 frames, then kill after a random 0-40 ms, so the
        // kill lands mid-log even on a heavily loaded CI host (fixed sleeps were flaky under load: fsync latency).
        let t0 = std::time::Instant::now();
        while t0.elapsed() < std::time::Duration::from_secs(10) {
            if let Ok(b) = std::fs::read(&p) { if read_bytes(&b).map_or(false, |r| r.frames >= 2) { break; } }
            std::thread::sleep(std::time::Duration::from_millis(2));
        }
        std::thread::sleep(std::time::Duration::from_millis(x % 40));
        c.kill().unwrap(); c.wait().unwrap(); // Child::kill = SIGKILL on unix
        if let Ok(b) = std::fs::read(&p) { let r = read_bytes(&b).unwrap(); assert_valid_prefix(&r); if r.frames > 1 { nonempty += 1; } }
    }
    assert!(nonempty >= 50, "only {nonempty}/100 trials got past the first generation; the test is not exercising the log");
    std::fs::remove_dir_all(&d).ok();
}
