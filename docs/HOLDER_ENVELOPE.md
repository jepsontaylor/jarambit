# Assumed sheath / fixed-blade holder envelope (SWITCHBACK, hiking/utility)

These are **design assumptions** baked into `crates/genotype` (bounds), `crates/redteam` (`holder` module + `Reject::Holder`) and the fitness. Change only with a WHITEPAPER revision; never loosen silently.

| Item | Assumption | Where enforced |
|---|---|---|
| Holder type | Open-top pop-in fixed-blade holder, thermoformed shell (Kydex-like), two shells riveted, blade-down carry | doc only |
| Shell wall | 1.2–2.0 mm (gene `holder_wall`) | genotype bounds |
| Stack thickness | knife t + 2·wall + 2·0.2 mm clearance ≤ **9.0 mm** | redteam `MAX_STACK_MM` |
| Knife planform envelope | x-span ≤ **100 mm**, y-span (OAL) ≤ **200 mm** | redteam `MAX_KNIFE_W_MM/H_MM` |
| Positive stop | tang/ricasso **shoulders** step ≥ 0.8 mm/side (gene `shoulder_w` 0.8–2.5) | redteam |
| Thickness lands | unsharpened flat **ricasso** both faces, 5–15 mm (gene `ricasso_len`), full stock thickness (no bevel) — holder friction faces bear here | redteam |
| Friction faces | holder contacts grip faces for 8–30 mm below shoulder (gene `friction_len`) | genotype repair + redteam |
| Retention | V-detent notch on grip edge, depth 0.4–1.2 mm and ≤ 15 % of handle width, located **inside** the friction zone; holder carries a matching **retention nub** (pop-in click) | redteam |
| Draw access | ≥ **30 mm** of grip + the whole finger ring stay outside the holder | redteam `MIN_EXPOSED_GRIP_MM` |
| Drain | holder tip-pocket drain hole Ø 3–6 mm (gene `drain_d`) at the lowest point of the blade pocket | redteam (min) |
| Brand pad | flat pad on grip face, below the detent, never under the friction zone's nub | redteam `BrandPad` |

Pop-in force proxy (`redteam::holder_forces`): Kydex-like shell, E = 2.2 GPa, nub tab 12 mm wide, snap length 10 mm, so `F_ins = 6.6 · wall³ · detent` (N, mm). Draw is the return stroke, 0.55× insertion. Window: insertion 3–80 N, draw 1.5–45 N. Checked on the nominal design and on every MC sample (wall and detent are tolerance-perturbed). The window covers the legal gene box; shells outside it are rejected.
