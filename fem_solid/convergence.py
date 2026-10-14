"""Pure/mocked convergence contracts. Resolution counts alone do not authorize a ratio."""
import json
from dataclasses import asdict
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from assurance.testing.contracts import ContractError, finite, require, scientific_hash
from fem_solid.gci import compute_gci, validate_sequence
from fem_solid.gci_report import sf_band
from fem_solid.run_tip import Identity, bound_identity, execute_level, parameters, reuse

LEVELS = [(0, 2), (1, 4), (2, 8)]  # unchanged coarse-to-fine resolution requests, not a definition of r


def level(d1, out, nsub, nl, *, identity=None, execute=None, reuse_from=None):
    require(isinstance(identity, Identity), 'explicit_identity_required')
    config = parameters('30', str(nl), str(nsub), '2.0')
    expected = bound_identity(d1, config, identity.image_digest, identity.mesh, identity.material, identity.observable)
    require(identity == expected, 'input_code_config_identity_mismatch')
    if reuse_from is not None: return reuse(reuse_from, identity)
    return execute_level(d1, Path(out)/f'L{nsub}{nl}.attempts', '30', str(nl), str(nsub), '2.0',
                         identity=identity, execute=execute)


def main(d1, out, *, identities=None, sequence=None, execute=None):
    require(type(identities) in (list, tuple) and len(identities) == 3, 'explicit_level_identities_required')
    require(type(sequence) in (list, tuple) and len(sequence) == 3, 'explicit_mesh_sequence_required')
    try: ratio = finite(sequence[1].h)/finite(sequence[0].h)
    except (AttributeError, ZeroDivisionError): raise ContractError('invalid_mesh_sequence')
    require(validate_sequence(sequence, ratio) is None, 'invalid_mesh_sequence')
    observable = sequence[0].observable
    require(observable.id == 'vm_nodal_max' and observable.units == 'MPa' and
            observable.projection == 'nodal' and observable.metric == 'max', 'governing_observable_required')
    for identity, mesh_level in zip(identities, reversed(sequence)):
        require(isinstance(identity, Identity) and identity.mesh == mesh_level.mesh.sha256 and
                identity.observable == scientific_hash(asdict(mesh_level.observable)), 'mesh_or_observable_identity_mismatch')
    runs = [level(d1, out, *resolution, identity=identity, execute=execute)
            for resolution, identity in zip(LEVELS, identities)]
    data = [r['data'] for r in runs]
    coarse, middle, fine = [finite(row['vm_nodal_max_MPa']) for row in data]
    estimate = compute_gci(fine, middle, coarse, ratio, levels=tuple(sequence))
    findings = {'vm_nodal_max_MPa': estimate.to_dict(),
                'vm_nodal_avg_MPa': {'status': 'unsupported_observable_binding',
                                     'raw_values': [finite(row['vm_nodal_avg_MPa']) for row in data],
                                     'reason': 'A separate observable identity/sequence is required; no max-to-average transfer'}}
    maximum = findings['vm_nodal_max_MPa']
    sf = None
    if maximum['admitted']:
        fine = finite(data[-1]['vm_nodal_max_MPa']); allowable = finite(data[-1]['sallow_MPa'])
        require(fine > 0 and allowable > 0, 'invalid_sf_base_quantity')
        sf = sf_band(allowable/fine, maximum['gci_fine'])
    return {'schema': 2, 'design': Path(d1).name.removesuffix('_D1.json'),
            'runs': runs, 'findings': findings, 'SF_nodal_max': sf, 'execution_kind': 'mock',
            'numerical_verification': 'not_run', 'physical_validation': 'not_performed',
            'asymptotic_validation': 'not_established'}


def cli(argv):
    if len(argv) != 2: return 2
    print(json.dumps({'status': 'not_run', 'reason': 'No solver/image/capability lease; use explicit mocked software API only'}))
    return 3


if __name__ == '__main__':
    raise SystemExit(cli(sys.argv[1:]))
