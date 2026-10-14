# Test upgrade planning supplement

Read [TEST_UPGRADE_PLAN.md](TEST_UPGRADE_PLAN.md) for the full worker-ready plan. It integrates all ten new test documents with the original ten ideas, reliability specification and nineteen regression cases into Jarambit **1.0.0**.

- [TEST_WORK_PACKETS.json](TEST_WORK_PACKETS.json): twenty acceptance work units T00–T19, exact scopes, prerequisites and validation commands.
- [TEST_CASE_CATALOG.json](TEST_CASE_CATALOG.json): 178 proposed challenge groups with controls/oracles; not implemented tests or execution counts.
- [CI_GATE_POLICY.json](CI_GATE_POLICY.json): required contracts, numerical/lab/research tiers and conditional capability gates.
- [INPUT_COVERAGE.md](INPUT_COVERAGE.md) and [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json): all twenty-two source dispositions/hashes and current-source comparison.
- [LITERATURE_LEDGER.json](LITERATURE_LEDGER.json): twelve primary anchors checked for limited scope; other extracted citations remain unverified proposals.
- [HANDOFF.md](HANDOFF.md), [PLAN_RECEIPT.json](PLAN_RECEIPT.json), [PLAN_VALIDATION.json](PLAN_VALIDATION.json): dispatch/handoff, actions actually performed, and planning checks.
- [validate_test_plan.py](validate_test_plan.py): reproducible package validator; no solver or lab invocation.

This is a documentation plan. Runtime/schema/test implementation, physical experiments, dataset downloads and release actions have not started. Historical baseline results are kept unchanged in the parent package. T units belong to existing S owners; they do not grant overlapping runtime writes to a second worker.
