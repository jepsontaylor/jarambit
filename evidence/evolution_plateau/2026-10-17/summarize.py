"""Verify retained snapshot bytes and summarize provisional search failures (no certificates)."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def summarize():
    result = {}
    for host, waves in [('xbabe2', ['w298', 'w300']), ('xbabe3', ['w401c3', 'w402c3'])]:
        manifest = json.loads((ROOT / host / 'snapshot_manifest.json').read_text())
        for entry in manifest['files']:
            raw = (ROOT / host / entry['path']).read_bytes()
            assert len(raw) == entry['bytes']
            assert hashlib.sha256(raw).hexdigest() == entry['sha256'], entry['path']
        for wave in waves:
            folder = ROOT / host / 'out' / wave
            rounds = []
            for file in sorted(folder.glob('round_*_screen.json')):
                screen = json.loads(file.read_text())
                births = json.loads(file.with_name(file.name.replace('_screen', '_births')).read_text())
                rounds.append({
                    'round': births['round'], 'seed': births['seed'],
                    'births': len(births['genomes']),
                    'unique_births': len({x['row'] for x in births['genomes']}),
                    'birth_families': dict(collections.Counter(x['family'] for x in births['genomes'])),
                    'survivors': len(screen),
                    'survivor_families': dict(collections.Counter(x['family'] for x in screen)),
                    'first_four_families': [x['family'] for x in screen[:4]],
                    'best_screen_deficit': screen[0]['screen_deficit'] if screen else None,
                })
            assessments = []
            for file in sorted(folder.glob('by-content/*/*/*_master_scorecard.json')):
                score = json.loads(file.read_text())
                rs = json.loads(file.with_name(file.name.replace('_master_scorecard.json', '_rs.json')).read_text())
                assessments.append({
                    'scorecard': str(file.relative_to(ROOT)), 'label': rs['label'],
                    'source_commit': score['cad_battery']['source_commit'],
                    'mass_g': rs['mass_g'], 'solid_tip_sf': rs['solid_tip_sf'],
                    'strict_hunter_sf': score['engineering_metrics']['sf_hunter_strict'],
                    'hm_twist_sf': rs['hm_twist_sf'], 'hm_spine_sf': rs['hm_spine_sf'],
                    'fat_sf': rs['fat_sf'], 'strict_tip_twist_sf': rs['twist_tipzone_sf_strict'],
                    'bore_radius_mm': rs['export_measurements']['bore_edge_radius_mm'],
                    'sharpness': rs['export_measurements']['sharpness'],
                    'point_monotonic': rs['export_measurements']['point']['monotonic'],
                    'all_16': score['weighted_cad_score']['all_engineering_gates_pass'],
                    'rs_all_hard': rs['all_hard'], 'unverified': rs['unverified'],
                    'battery_pass': score['cad_battery']['pass_count'],
                    'engineering_failures': [k for k, v in score['weighted_cad_score']['gates'].items() if not v],
                    'rs_failures': [k for k, v in rs['gates'].items() if v != 'pass'],
                })
            result[wave] = {
                'host': host, 'captured_utc': manifest['captured_utc'],
                'leaderboard_present': (folder / 'leaderboard.json').exists(),
                'rounds': rounds, 'completed_assessments_in_snapshot': assessments,
            }
    return result


if __name__ == '__main__':
    print(json.dumps(summarize(), indent=2, sort_keys=True))
