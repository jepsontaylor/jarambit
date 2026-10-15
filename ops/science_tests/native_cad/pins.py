"""Asset pins copied from e150bb9 SHA256SUMS and README claims.

C.10c stays an archived diagnostic subject after the revert of that commit.
The bytes are identified by hash, not by continued presence on later main.
"""

PIN_COMMIT = "e150bb906e8b8a265077de60ee148f6ba773a83a"
DENSITY_G_PER_CC = 4.43
# Diagnostic band for tessellated STL versus the README gram claim.
# A pass here does not repair an open mesh or create a pipeline binding.
STL_README_REL_TOL = 0.01
# STEP volume uses the drawing convention mm^3 * 4.43e-3. Three-decimal
# README grams are about 0.0005 g, so 0.1% is a wide check around that claim.
STEP_README_REL_TOL = 0.001

SUBJECTS = {
    "C10a": {
        "role": "comparison_baseline",
        "archived": False,
        "readme": "designs/switchback/C10a/README.md",
        "step": "designs/switchback/C10a/cad/switchback_revC10a_ground.step",
        "stl": "designs/switchback/C10a/cad/switchback_revC10a_ground.stl",
        "step_sha256": "441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7",
        "stl_sha256": "0bcadad61bff550d9c527266e183440e8242c3a0222b9a89755cdc682b214411",
        "readme_mass_g": 64.841,
        "reported_fitness": 2.673,
        "genome_id": None,
        "claim_snippets": {
            "V6": "solved directly on C.10a",
            "identity": "C.10a is a B-rep, not a genome",
        },
    },
    "C92": {
        "role": "previous_release_candidate",
        "archived": False,
        "readme": "designs/switchback/C9.2/README.md",
        "step": "designs/switchback/C9.2/cad/switchback_revC9_2_ground.step",
        "stl": "designs/switchback/C9.2/cad/switchback_revC9_2_ground.stl",
        "step_sha256": "2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307",
        "stl_sha256": "10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847",
        "readme_mass_g": 66.764,
        "reported_fitness": None,
        "genome_id": None,
        "claim_snippets": {
            "identity": "C.9.2 is a B-rep, not a jarambit genome",
        },
    },
    "C93": {
        "role": "release_candidate",
        "archived": False,
        "readme": "designs/switchback/C9.3/README.md",
        "step": "designs/switchback/C9.3/cad/switchback_revC9_3_ground.step",
        "stl": "designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl",
        "step_sha256": "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919",
        "stl_sha256": "1aeda17eba396bcec7380ac27f7d20886d64d234f70ad8d3d0cc57aaf63d74ca",
        "readme_mass_g": 66.773,
        "reported_fitness": None,
        "genome_id": None,
        "claim_snippets": {
            "identity": "C.9.3 is a B-rep, not a jarambit genome",
        },
    },
    "C10c": {
        "role": "archived_diagnostic",
        "archived": True,
        "readme": "designs/switchback/C10c/README.md",
        "board": "designs/switchback/C10c/data/sr9_board.json",
        "step": "designs/switchback/C10c/cad/switchback_revC10c_ground.step",
        "stl": "designs/switchback/C10c/cad/switchback_revC10c_ground.stl",
        "step_sha256": "4211f35b1c04d795029c85bcd3fa6a81ed3456f774a935d419e326bc06d4eae4",
        "stl_sha256": "ac64a65dd653194d563a2026ffa42213846a9bda7cce7c52f80327da4c6e4700",
        "readme_mass_g": 67.089,
        "reported_fitness": 2.786,
        "genome_id": None,
        "sources": {
            "GateS": "B-rep ray probe",
            "V1": "w80d g2 carry",
            "V2": "record (C.10a 0.738)",
            "V3": "direct r0p2",
            "V4": "ring-refined × g2 ratio",
            "V5": "g2",
            "V6": "w80d submodel × g2 ratio",
            "V7": "w80d nose submodel",
        },
    },
}
