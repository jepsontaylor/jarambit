"""Blender adapter for the retained paper scene library; no CAD is regenerated.

The host wrapper validates the context. Typography is applied by Pillow later;
the adapter replaces the library's fixed #84 status with this assessment's status.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_scenes as atlas

context = json.loads(Path(os.environ['JARAMBIT_RENDER_CONTEXT']).read_text())
atlas.SUBJECT = context['label']
atlas.STL = Path(context['artifacts']['stl'])
atlas.D1 = Path(context['artifacts']['d1'])
atlas.SCORE = json.loads(Path(context['artifacts']['scorecard']).read_text())
for name in ('hero_oblique', 'hero_reverse', 'hero_section'):
    title, subtitle, mode = atlas.SCENES[name]
    atlas.SCENES[name] = (title, 'Exact assessed export · ' + context['status'], mode)
atlas.main()
output = Path(sys.argv[sys.argv.index('--output')+1]).with_suffix('.labels.json')
captions = json.loads(output.read_text())
# The final two entries are the subject/verdict and qualification annotations in
# the retained scene library; the geometry pass contains no rasterized labels.
assert captions[-2]['text'].startswith(atlas.SUBJECT + '   /   ')
assert captions[-1]['text'] == 'ASSESSED EXAMPLE · NOT QUALIFIED · CHAMPION = NULL'
if 'RS-karambit-v2: FAIL' in captions[-2]['text']:
    captions[-2]['text'] = captions[-2]['text'].replace('RS-karambit-v2: FAIL',
        'RS-karambit-v2: ' + ('PASS' if context['rs_v2_all_hard'] else 'FAIL'))
captions[-1]['text'] = context['status']
output.write_text(json.dumps(captions, indent=1)+'\n')
