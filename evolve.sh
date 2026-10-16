#!/usr/bin/env bash
# ==============================================================================
# evolve.sh — Turnkey Automated Evolution Across ALL Engineering Gates
# ==============================================================================
# Evolves and certifies stronger, lighter Ti-6Al-4V karambit CADs natively in
# Rust with ZERO gate relaxation:
#   - 16/16 W_CAD_v2_ultrarunner_karambit hard gates
#   - 10/10 RS-karambit-v2 (all_hard = true: human-maximum 70 Nm twist / 1200 N
#     spine / 5000 N ring, 10^5-cycle R=0.1 fatigue SF >= 1.50, >=10.0 mm 3D
#     ring-bore bearing, sharp bevel law edge_t <= 0.20 mm & theta_1 <= 12 deg,
#     and 3D watertight B-rep needle-point check)
#   - 3D P2 quadratic tetrahedron (TET10) solid-tip submodel FEM (SF >= 1.00)
#   - side.a4 radial bore-pin + Winkler grip pad + Lanczos buckling (lambda >= 1)
#   - 3-level Roache Grid Convergence Index (GCI) + strict 0.0625 mm^2 plate FEM
#   - Watertight 3D STEP + STL export + 18/18 CAD battery + Master Scorecard
#
# Usage:
#   ./evolve.sh                                  # Default: 2 rounds, 12 candidates/elite/round -> out/auto_evolve
#   ./evolve.sh 4 24 out/my_wave                 # Positional: <rounds> <candidates_per_round> <out_dir>
#   ./evolve.sh --rounds 5 --out-dir out/wave_x  # Named flags forwarded to `jarambit auto-evolve`
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export JARAMBIT_P1_SFMAP="${JARAMBIT_P1_SFMAP:-$ROOT_DIR/evidence/d1_p1/w249_sfmap.txt}"
export JARAMBIT_FEM="${JARAMBIT_FEM:-1}"

echo "[evolve.sh] Building release binary (target/release/jarambit)..."
cargo build --release --bin jarambit --quiet

if [[ $# -gt 0 && "${1:-}" != -* ]]; then
    ROUNDS="${1:-2}"
    CANDS="${2:-12}"
    OUT_DIR="${3:-$ROOT_DIR/out/auto_evolve}"
    shift $(( $# >= 3 ? 3 : $# ))
    exec "$ROOT_DIR/target/release/jarambit" auto-evolve \
        --rounds "$ROUNDS" \
        --candidates-per-round "$CANDS" \
        --out-dir "$OUT_DIR" \
        "$@"
else
    exec "$ROOT_DIR/target/release/jarambit" auto-evolve "$@"
fi
