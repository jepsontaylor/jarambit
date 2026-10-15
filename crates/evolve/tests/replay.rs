//! PR-0.29.2: lossless, manifest-bound checkpoint/resume.
//! interrupted at gens {3, 7, 12} then resumed == uninterrupted (bitwise genomes + observations, 3 seeds);
//! changing any manifest field refuses resume; --resume without a checkpoint is an error; --fork branches deliberately.
use jarambit_evolve::{try_run, Config};

fn cfg(seed: u64, path: &str) -> Config {
    let mut c = Config::new(6, 14, 8, 2, seed); c.islands = 2; c.migrate_every = 3; c.checkpoint = Some(path.into()); c
}

struct TempDir {
    parent: std::path::PathBuf,
    dir: std::path::PathBuf,
}
impl TempDir {
    fn new(tag: &str) -> Self {
        let parent = std::env::temp_dir().join(format!("jarambit_replay_{}", std::process::id()));
        let dir = parent.join(tag);
        std::fs::create_dir_all(&dir).unwrap();
        Self { parent, dir }
    }
    fn path(&self, name: &str) -> String {
        self.dir.join(name).to_string_lossy().into_owned()
    }
}
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
        let _ = std::fs::remove_dir(&self.parent);
    }
}

#[test]
fn interrupted_then_resumed_equals_uninterrupted_bitwise() {
    let td = TempDir::new("bitwise");
    for seed in [1u64, 42, 9001] {
        let full = td.path(&format!("full_{seed}.ckpt"));
        let (b_full, f_full) = try_run(&cfg(seed, &full), |_| {}).unwrap();
        let want = std::fs::read(&full).unwrap();
        for stop in [3usize, 7, 12] {
            let p = td.path(&format!("int_{seed}_{stop}.ckpt"));
            let mut c = cfg(seed, &p); c.stop_after = Some(stop); try_run(&c, |_| {}).unwrap();
            assert!(std::fs::read_to_string(&p).unwrap().contains(&format!("\nnext_gen {stop}\n")));
            let mut c = cfg(seed, &p); c.resume = true;
            let mut gens_logged = Vec::new();
            let (b, f) = try_run(&c, |s| gens_logged.push(s.gen)).unwrap();
            assert_eq!(gens_logged.first(), Some(&stop), "resume continues at the interrupted generation");
            assert_eq!(std::fs::read(&p).unwrap(), want, "seed {seed} stop {stop}: final checkpoint (populations, rng, archive; f64 bits) differs");
            assert_eq!(b.fit.to_bits(), b_full.fit.to_bits()); assert_eq!(b.g.to_vec().iter().map(|x| x.to_bits()).collect::<Vec<_>>(), b_full.g.to_vec().iter().map(|x| x.to_bits()).collect::<Vec<_>>());
            assert_eq!(f.len(), f_full.len());
        }
    }
}

#[test]
fn any_manifest_change_refuses_resume() {
    let td = TempDir::new("manifest");
    let p = td.path("m.ckpt");
    let mut c = cfg(5, &p); c.stop_after = Some(2); try_run(&c, |_| {}).unwrap();
    let base = jarambit_evolve::manifest(&cfg(5, &p));
    let edits: Vec<(&str, Box<dyn Fn(&mut Config)>)> = vec![
        ("pop", Box::new(|c| c.pop = 7)), ("gens", Box::new(|c| c.gens = 15)), ("mc_samples", Box::new(|c| c.mc_samples = 9)), ("seed", Box::new(|c| c.seed = 6)),
        ("islands", Box::new(|c| c.islands = 3)), ("migrate_every", Box::new(|c| c.migrate_every = 4)), ("fem", Box::new(|c| c.fem = true)), ("fine", Box::new(|c| c.fine = true)),
        ("seeds", Box::new(|c| c.seeds.push(jarambit_genotype::Genotype::random(&mut jarambit_genotype::Rng(3))))),
    ];
    for (name, f) in &edits {
        let mut c = cfg(5, &p); f(&mut c); c.resume = true;
        assert_ne!(jarambit_evolve::manifest(&c).sha256(), base.sha256(), "{name} not in manifest");
        let e = try_run(&c, |_| {}).err().unwrap_or_else(|| panic!("{name}: resume accepted"));
        assert!(e.contains("manifest mismatch") || e.contains("islands"), "{name}: {e}");
    }
    // the remaining manifest fields are code constants (schema, tool, tool_version, requirement_set, op_version,
    // command, floors_n, calib_mesh_bias, search_area): editing them in the checkpoint must also refuse
    let txt = std::fs::read_to_string(&p).unwrap();
    for (from, to) in [("\"op_version\":1", "\"op_version\":2"), ("\"floors_n\":\"180/260/1500\"", "\"floors_n\":\"180/250/1500\""), ("\"command\":\"evolve\"", "\"command\":\"evolvx\""), ("\"search_area\":2.0", "\"search_area\":4.0")] {
        assert!(txt.contains(from), "{from} not in manifest json");
        let q = td.path("m_edit.ckpt");
        // tamper the manifest JSON AND recompute nothing: the stored sha no longer matches this run's sha either way
        let man_line = txt.lines().find(|l| l.starts_with("manifest ")).unwrap();
        let mut m: jarambit_evidence::RunManifest = serde_json::from_str(&man_line["manifest ".len()..].replace(from, to)).unwrap();
        let fake = txt.replace(man_line, &format!("manifest {}", m.canonical_json())).replace(&base.sha256(), &m.sha256());
        std::fs::write(&q, fake).unwrap(); m.seed = 0;
        let mut c = cfg(5, &q); c.resume = true;
        assert!(try_run(&c, |_| {}).unwrap_err().contains("manifest mismatch"), "{from}");
    }
    // unchanged config resumes fine
    let mut c = cfg(5, &p); c.resume = true; c.stop_after = Some(3); try_run(&c, |_| {}).unwrap();
}

#[test]
fn resume_without_checkpoint_is_an_error_and_fork_is_explicit() {
    let td = TempDir::new("fork");
    let p = td.path("absent.ckpt"); let _ = std::fs::remove_file(&p);
    let mut c = cfg(8, &p); c.resume = true;
    assert!(try_run(&c, |_| {}).unwrap_err().contains("does not exist"));
    // torn checkpoint
    let mut c = cfg(8, &p); c.stop_after = Some(2); try_run(&c, |_| {}).unwrap();
    let t = std::fs::read_to_string(&p).unwrap(); std::fs::write(&p, &t[..t.len() - 40]).unwrap();
    let mut c = cfg(8, &p); c.resume = true; assert!(try_run(&c, |_| {}).is_err());
    std::fs::write(&p, &t).unwrap();
    // fork: different gens is accepted only with fork, and the fork records its parent manifest
    let mut c = cfg(8, &p); c.gens = 16; c.resume = true; assert!(try_run(&c, |_| {}).is_err());
    let mut c = cfg(8, &p); c.gens = 16; c.fork = true; c.stop_after = Some(4); try_run(&c, |_| {}).unwrap();
    let t2 = std::fs::read_to_string(&p).unwrap();
    assert!(t2.contains("forked_from_manifest_sha256") && t2.contains("\"forked_at_gen\":2"));
}
