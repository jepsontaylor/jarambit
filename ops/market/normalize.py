#!/usr/bin/env python3
"""Normalize supplied catalog rows; preserve every observation and merge identity."""
import csv
import hashlib
import json
import pathlib
import re
import unicodedata
from collections import defaultdict
from harvest import normalize_url

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT/'docs/market/2026-10-13'


def slug(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')


def get(r, *keys):
    return next((r[k] for k in keys if r.get(k)), '')


def number(s):
    if not s or str(s).lower() in ('nan','unknown','n/a'):
        return None
    m=re.search(r'-?\d+(?:\.\d+)?',str(s).replace(',',''))
    return float(m[0]) if m else None


def material(s):
    t=s.lower().replace('-','').replace(' ','')
    if any(x in t for x in ('polymer','grivory','grivex')) and 'steel' not in t:
        return 'Glass-reinforced polymer'
    if ('titanium' in t or '6al4v' in t or 'ti6al4v' in t) and not any(k in t for k in ('coating','coated','finish','aus','8cr','m390','magnacut','stainless','steel')):
        return 'Ti / carbon fiber' if 'carbon' in t else ('Ti-6Al-4V' if any(x in t for x in ('6al4v','ti6al4v')) else 'Titanium, alloy unspecified')
    if 'damascus' in t:
        return 'Damascus, composition unspecified'
    if t.startswith('3v'): return 'CPM 3V'
    for grade in ('MagnaCut','M390MK','M390','CPM154','CPM3V','154CM','S35VN','S30V','VG10','NitroV','AEBL','14C28N','12C27','9Cr18MoV','8Cr13MoV','7Cr17MoV','7Cr17','7Cr13','5Cr15MoV','3Cr13','2Cr13','AUS10A','AUS10','AUS8A','AUS8','440C','440A','440','420','1095','1075','5160','K340','N690','SK5','D2','A2','ZWear','OU31'):
        if grade.lower() in t:
            return {'CPM3V':'CPM 3V','VG10':'VG-10','CPM154':'CPM 154','NitroV':'Nitro-V','AEBL':'AEB-L','AUS10A':'AUS-10A','AUS10':'AUS-10','AUS8A':'AUS-8A','AUS8':'AUS-8','SK5':'SK-5','ZWear':'Z-Wear','OU31':'OU-31'}.get(grade,grade)
    return 'Steel, grade unspecified'


# Aliases are identity decisions, never numeric substitutions. Color-only finishes
# collapse for analysis. Different materials and named generations remain separate.
ALIASES=[
 ('steel-tiger','Cold Steel Steel Tiger'),('black-talon','Cold Steel Black Talon II'),
 ('du-hoc','CRKT Du Hoc'),('dawnstar','Kershaw Dawnstar'),('super-karambit','Emerson Super Karambit'),
 ('spartan','Schwartz Spartan'),('cyroclaw','HIGHTRON Cyroclaw'),('straight-karambit','Boker Straight Karambit'),
 ('spike-karambit','Boker Spike Karambit'),('raptor','Boker Raptor\'s Claw'),('wildcat','Boker Wildcat XL'),
 ('boker-plus-bat','Boker Bat Karambit'),('monky','Fox Monky Tumber'),
 ('parong','Fox Parong'),('boneyard','Schrade Boneyard'),('shasta','Schrade Shasta McNasty'),('mcnasty','Schrade Shasta McNasty'),
 ('deep-6','Skallywag Deep 6'),('gambit-xl','SOG Gambit XL'),('cia-stinger','United Cutlery CIA Stinger III'),
 ('liberator-falcon','United Cutlery M48 Liberator Falcon'),('falcon','United Cutlery M48 Falcon'),
 ('steel-titan','United Cutlery M48 Steel Titan'),('tanker','United Cutlery M48 Tanker'),('magnum-karambit','United Cutlery M48 Magnum'),
 ('m48-magnum','United Cutlery M48 Magnum'),('anti-zombie','United Cutlery M48 Anti-Zombie'),
 ('warbird','United Cutlery Warbird'),('high-polish','Gil Hibben High Polish'),('gil-hibben-karambit','Gil Hibben High Polish'),
 ('honshu','United Cutlery Honshu'),('garra','BLACKHAWK Garra'),('ghost-ii','Bark River Ghost II'),
 ('arctic-fox','Stroup Arctic Fox'),('trailhead','TOPS Trailhead Kukri'),('tac-tops','TOPS TAC-TOPS'),
 ('c-u-t','TOPS C.U.T. 4.0'),('bushcraft-karambit','TOPS C.U.T. 4.0'),('10-27','TOPS 10/27'),
 ('fenris','McDaniel Fenris'),('lycan','McDaniel Lycan'),('gti','Gingrich Custom'),('gingrich','Gingrich Custom'),
 ('talim','Hoback TALIM'),('kharma','LOTAR KHARMA'),('hela','Maxace Hela'),('hawk-auto','Microtech Hawk Auto'),
 ('hawk-karambit','Microtech Hawk'),('microtech-hawk','Microtech Hawk'),('civilian','Spyderco Civilian'),
 ('ps-small','Strider PS Small'),('strider-ps','Strider PS Small'),('msc-ps','Strider MSC PS'),
 ('strider-custom','Mick Strider Custom'),('mick-strider','Mick Strider Custom'),('warren-thomas','Warren Thomas Prototype'),
 ('olamic','Olamic Karambit'),('ontario','Ontario Ranger EOD'),('mtech','MTech'),('midwatch','CIVIVI Midwatch'),
 ('cqb-02','Halfbreed CQB-02'),('master-usa','Master USA'),('cobra','Artisan Cobra'),('reapr','REAPR Versa'),
 ('silverfang','Elite Tactical Silverfang'),('derespina','Rich Derespina'),('rogue','Rogue Custom Titanium'),('kong','Steve Ryan Kong'),
]


def identity(row):
    name=slug(row['brand']+' '+row['model'])
    key=next((b for a,b in ALIASES if a in name),row['brand']+' '+row['model'])
    if 'airborne' in name: key='Airborne Reaper'
    if 'death-before-dishonor' in name: key='Death Before Dishonor'
    if 'phantom-edge' in name: key='SOG Phantom Edge'
    if 'medford' in name and 'burung' in name: key='Medford Burung'
    if 'jungle-ranger' in name: key='Jungle Ranger'
    if 'tac-force' in name: key='Tac-Force TF-957'
    if 'extreme-ops' in name or 'chokehold' in name: key='Smith & Wesson Chokehold'
    if 'damascus' in name and ('1177' in row['url'] or '1177' in name): key='Damascus 1177'
    if 'strider' in name and 'ps-karambit-tiger' in name: key='Strider PS Small'
    if key=='CRKT Du Hoc':
        key+=' Folding' if ('fold' in name or '2635' in row['url']) else ' Fixed'
    if key=='Fox Parong':
        key+=' Hunting' if 'hunting' in name else ' Standard'
    if key=='LOTAR KHARMA':
        key+=' Gen.2' if 'gen-2' in name else ' Gen.3X'
    if key=='Halfbreed CQB-02' and ('02s' in name or '02s' in row['sku'].lower()):
        key+='S'
    if key=='Rich Derespina':
        m=re.search(r'model-(\d+)',name)
        key+=' Model '+m[1] if m else (' Pikarambit' if 'pikarambit' in name else ' Custom')
    if key=='Warren Thomas Prototype':
        key+=' 415135' if '415135' in row['url'] else ' 1099471'
    if key=='MTech':
        sku=slug(row['sku'])
        for a,b in [('20-78','MT-20-78'),('2078','MT-20-78'),('20-76','MT-20-76'),('2076','MT-20-76'),('8140','MX-8140'),('665','MT-665'),('panther','Panther')]:
            if a in name+sku+row['url']:
                key+=' '+b; break
        else:
            key+=' '+(row['sku'] or slug(row['model']))
    if key=='Master USA':
        key+=' '+ ('4-inch' if row['blade_length_in'] and row['blade_length_in']>=3.95 else '3.5-inch')
    return key.strip()


def main():
    rows=[]
    for path in sorted((DATA/'raw').glob('*.csv')):
        for index,r in enumerate(csv.DictReader(path.open(encoding='utf-8-sig',newline='')),2):
            row={'input_file':path.name,'input_row':index,'input_record_id':get(r,'record_id','id'),
                 'brand':get(r,'brand','Brand'), 'model':get(r,'model','Model','Name/Model'),
                 'variant':get(r,'variant'), 'sku':get(r,'sku','manufacturer_sku','model_number'),
                 'knife_type':get(r,'knife_type'),
                 'style':get(r,'style_classification','style_scope','karambit_classification'),
                 'blade_length_in':number(get(r,'blade_length_in','Blade_Length_inches','Blade_Length_Inches')),
                 'cutting_edge_in':number(get(r,'cutting_edge_length_in')),
                 'material_as_reported':get(r,'blade_material','Blade_Material','Material'),
                 'weight_g':number(get(r,'weight_g','Weight_grams','Weight_Grams')),
                 'weight_as_reported':get(r,'weight_as_listed'),
                 'weight_scope':get(r,'weight_scope','weight_basis'),
                 'weight_with_sheath_g':number(get(r,'weight_with_sheath_g','package_or_sheathed_weight_g')),
                 'availability_as_reported':get(r,'availability'),
                 'qualification_as_reported':get(r,'qualification_status','inclusion_status','data_confidence'),
                 'url':normalize_url(get(r,'spec_source_url','seller_url','product_url','Seller_URL','Seller_URL_or_Location','Seller_Location_URL')),
                 'notes':get(r,'notes','Notes')}
            row['blade_grade']=material(row['material_as_reported'])
            row['all_urls']=sorted({normalize_url(u.rstrip(';,.)')) for k,v in r.items() if k is not None and ('url' in k.lower() or k in ('Seller_URL_or_Location','Seller_Location_URL')) for u in re.findall(r'https?://[^\s|<>]+',v or '')})
            row['model_family']=identity(row)
            # Unknown grades in old thin schemas are observations of the same model;
            # reconcile them explicitly later, without guessing metallurgy.
            row['group_key']=slug(row['model_family'])+'__'+slug(row['blade_grade'])
            rows.append(row)
    groups=defaultdict(list)
    for row in rows:
        groups[row['group_key']].append(row)
    (DATA/'observations.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    preview=[]
    for key,group in sorted(groups.items()):
        lens=sorted({r['blade_length_in'] for r in group if r['blade_length_in']})
        weights=sorted({r['weight_g'] for r in group if r['weight_g']})
        urls=sorted({r['url'] for r in group if r['url']})
        preview.append({'key':key,'model':group[0]['model_family'],'grade':group[0]['blade_grade'],'rows':len(group),'lengths':lens,'weights':weights,'urls':urls})
    (ROOT/'.study/market/groups.json').write_text(json.dumps(preview,indent=2,ensure_ascii=False)+'\n')
    print(f'{len(rows)} observations -> {len(preview)} preliminary groups')
    for p in preview:
        print(p['key'],len(p['urls']),p['lengths'],p['weights'])


if __name__=='__main__':
    main()
