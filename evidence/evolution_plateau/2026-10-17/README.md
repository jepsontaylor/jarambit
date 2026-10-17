# Genome-search plateau snapshot

Read-only captures at 08:02 UTC on 2026-10-17. Each host manifest records the original root, capture time and exact file hashes. These are diagnostic observations of failed/provisional searches, **not current certificates**. Referenced STEP/STL, meshes and solver sidecars remain in the originating wave directories; this subset cannot independently re-certify a design. No running job or source file was changed to collect it.

Reproduce counts, rankings, gate failures and metric ranges, while verifying every captured file:

```bash
python3 evidence/evolution_plateau/2026-10-17/summarize.py
```

| Wave | Snapshot status | Births / rankable, by round | Completed assessments |
|---|---|---|---:|
| xbabe2 w298 | Final leaderboard | 68/53, 64/63, 64/63 | 6 |
| xbabe2 w300 | First screen; assessment pending | 100/64 | 0 |
| xbabe3 w401c3 | Final leaderboard + RESULT.md | 52/45, 48/47 | 4 |
| xbabe3 w402c3 | First screen; second assessment pending | 52/44 | 1 |

Scorecards record source commits: w298 `ae86f188`, xbabe3 waves `6438f077`. The live w300 source was main `9d641600` (COMMS handoff); its snapshot has no completed scorecard. Historical failures are not promoted across certification-policy identities.

All eleven completed assessments fail the same six engineering gates: certified hiker/hunter, strict hunter, tip-only twist, strict tip-submodel twist and independent solid tip. The eight failed RS groups additionally expose fatigue, human loads, measured sharpness and point profile. Mass spans 82.861–83.325 g, independent solid-tip SF 0.6361–0.6716, strict hunter SF 0.6381–0.6512, human twist SF 0.05748–0.05906, spine SF 0.22312–0.23345, fatigue SF 0.45737–0.48302 and strict tip twist SF 0.47517–0.53044. Every measured bore radius is 1.300199 mm; sharpness maximum apex is 0.20262–0.20598 mm and half-angle 25.3618–28.4815 degrees; all point profiles fail monotonicity. These numbers come from the captured scorecard/RS JSONs, not estimates. Battery counts are 11–12/18; neither final leaderboard has a qualified design.

The first four ranked w298 parents are all p14; the p10 family disappears from subsequent births. The reverse happens in w401c3: all four are p10, and round two has no p14. Round-zero ring-wall proposals span 4.736–6.985 mm in w298, but round-one births all use 5.20079683 mm. Distinct CSVs also overstate exploration: w298 starts with 56 unique rows out of 68 births, w401c3 with 44/52. The w298/w401c3 initial seeds share 5.9 mm stock, the same ring wall, 0.18 mm apex and the through-machined architecture. The w300 control family has no rankable survivors among 25 births. The retained geometry-only `rejection_probe.rs` / `rejection_probe.json` replay diagnoses all 25: aesthetics pass, but the frozen 200 x 100 mm holder envelope fails (20 have a best oriented box of 201.5 x 99.4 mm). Thus increasing the ring wall to satisfy the bore rule needs coordinated outline evolution; isolated ring/angle redraws do not repair this constraint. The probe input/source/output hashes are in `probe_manifest.json`; it runs no FEM or certification.

Source inspection explains the stall: broad ring/angle redraws occur only in round zero; targeted tip/knot/control-point steps start at 0.0105/0.00875/0.021 mm and shrink with round count. Non-P1 knot changes are erased by the existing clamp. Only 2–3 rounds and top-k=2 are used in the completed waves. Stage-1 sums coarse normalized structural/bore deficits but omits measured sharpness/point and independent solid-tip results. Failed Stage-2 assessments do not influence parent selection. For w298, the best coarse deficit improves from 3.104828 to 3.068920 while solid-tip SF declines from 0.6693 to 0.6361. More rounds alone do not establish useful progress.

The accompanying engine fix retains all qualified genomes, takes one distinct rankable parent per available family, then fills to at least four provisional parents in screen order. It prevents the observed family loss without changing any physical model, qualification verdict, threshold, bound, mutation or collar rule. Family labels come from seed filenames; preserving them does not guarantee phenotypic diversity or feasibility.

For future owner-scheduled waves, first compare identical seeds/budgets with this selection fix, recording family survival and distinct active phenotypes. Next evaluate coupled ring-wall/outline and broader **existing-domain genome mutations**, rejection reasons and per-gate deficit components, including measured edge/point constraints before expensive solves. Increase rounds/top-k only when distinct valid phenotypes improve the binding deficits. Do not restart the captured waves or treat search ranking as qualification. Collar construction remains awaiting owner sign-off.
