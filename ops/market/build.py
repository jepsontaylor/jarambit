#!/usr/bin/env python3
"""Build an evidence-scoped market census and offline publication figures."""
import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import statistics
from collections import Counter, defaultdict
from urllib.parse import urlparse
from normalize import DATA, ROOT, material, number, slug

OZ = 28.349523125
MINIMUM_IN = 3.375
PALETTE = {
    'Stainless steel': '#527F91',
    'Carbon / tool steel': '#BA7058',
    'PM tool steel': '#89739C',
    'Damascus / pattern steel': '#BBA071',
    'Titanium / Ti composite': '#4D9B93',
    'Steel, grade unspecified': '#8A919B',
    'Polymer / nonmetal': '#AC6288',
}
GOLD = '#E8B849'
INK = '#152A38'
BG = '#FAF7F0'
MANUFACTURERS = ('bokerusa.com','boker.de','crkt.com','kaiusa.com','civivi.com','coldsteel.com',
                 'topsknives.com','halfbreedblades.com','microtechknives.com','emersonknives.com','armisknifeandtool.com')


def save_figure(fig, path):
    for ext in ('png','svg','pdf'):
        metadata={'Creator':'jarambit market census','CreationDate':None,'ModDate':None} if ext=='pdf' else {'Date':None,'Creator':'jarambit market census'} if ext=='svg' else None
        target=path.with_suffix('.'+ext)
        fig.savefig(target,dpi=220,metadata=metadata)
        if ext=='svg':target.write_text('\n'.join(line.rstrip() for line in target.read_text().splitlines())+'\n')


def family(grade):
    if grade=='Glass-reinforced polymer':return 'Polymer / nonmetal'
    if grade.startswith('Ti'):
        return 'Titanium / Ti composite'
    if grade.startswith('Damascus'):
        return 'Damascus / pattern steel'
    if grade in ('CPM 3V','Z-Wear','K340'):
        return 'PM tool steel'
    if grade in ('1095','1075','5160','SK-5','D2','A2','OU-31'):
        return 'Carbon / tool steel'
    if grade=='Steel, grade unspecified':
        return grade
    return 'Stainless steel'


def dimension(value):
    """Read explicit inches or metric units, including mixed fractions."""
    value=value.replace('−','-')
    if re.search(r'\d\s*(?:\"|in\.?)\s*[-–]\s*\d',value,re.I):return None
    m=re.search(r'(\d+(?:\.\d+)?)(?:[- ](\d+)/(\d+))?\s*(?:\"|″|in\b|inch)',value,re.I)
    if m:
        return float(m[1])+(int(m[2])/int(m[3]) if m[2] else 0)
    m=re.search(r'(\d+(?:\.\d+)?)\s*(?:\"|″|in\b|inch)',value,re.I)
    if m: return float(m[1])
    m=re.search(r'(\d+(?:\.\d+)?)\s*(mm|cm)\b',value,re.I)
    if m: return float(m[1])/(25.4 if m[2].lower()=='mm' else 2.54)
    return None


def weight(value):
    m=re.search(r'(\d+(?:\.\d+)?)\s*(?:g\b|grams?\b|gr\b)',value,re.I)
    if m: return float(m[1])
    m=re.search(r'(\d+(?:\.\d+)?)\s*(?:oz\b|ounces?\b)',value,re.I)
    return round(float(m[1])*OZ,2) if m else None


def parse_facts(text):
    result={}
    patterns={
        'blade_length_in':r'Blade\s*Length\s*(?:\([^)]*\))?\s*[:|]?\s*([^\n]{1,65})',
        'cutting_edge_in':r'(?:Cutting Edge(?: Length)?|Edge Length|Sharpened Length)\s*[:|]?\s*([^\n]{1,55})',
        'weight_g':r'(?<!Sheath )(?<!Total )(?<!Shipping )\b(?:Knife |Karambit |Blade )?Weight\s*[:|]\s*([^\n]{1,65})',
        'weight_with_sheath_g':r'(?:Weight\s*(?:with|w/)\s*Sheath|Blade w/ Kydex Sheath Weight)\s*[:|]?\s*([^\n]{1,65})',
        'blade_grade':r'Blade\s*(?:Material|Steel)\b\s*[:|]?\s*([^\n]{1,65})',
    }
    for field,pattern in patterns.items():
        for m in re.finditer(pattern,text,re.I):
            val=m[1]
            if field.endswith('_in'): parsed=dimension(val)
            elif field.endswith('_g'): parsed=weight(val)
            else: parsed=material(val.split('Blade')[0].split('Handle')[0].split('Hardness')[0])
            if parsed is not None:
                result[field]=parsed
                if parsed!='Steel, grade unspecified': break
    m=re.search(r'Blade [Ll]ength \(mm\)\s*(\d+(?:\.\d+)?)',text)
    if m:result['blade_length_in']=float(m[1])/25.4
    m=re.search(r'Blade Length \((inches|in|mm|cm)\)\s*[:|]?\s*(\d+(?:\.\d+)?)',text,re.I)
    if m:result['blade_length_in']=float(m[2])/(25.4 if m[1].lower()=='mm' else 2.54 if m[1].lower()=='cm' else 1)
    # Manufacturer tables sometimes omit colon separators.
    if 'weight_g' not in result:
        m=re.search(r'\b(?:Knife Weight|Weight)\s+(\d+(?:\.\d+)?\s*(?:g\b|oz\b)[^\n]{0,12})',text,re.I)
        if m: result['weight_g']=weight(m[1])
    if 'including sheath' in text.lower() or 'including the sheath' in text.lower():
        result['weight_basis']='ambiguous_or_sheathed'
    else:
        result['weight_basis']='explicit_knife_only' if re.search(r'(?:Knife |Karambit |Blade )Weight|Weight (?:with|w/) Sheath',text,re.I) else 'published_knife_spec'
    return result


def sources():
    src={}
    for r in json.loads((DATA/'retrieval_ledger.json').read_text()):
        if r['status']=='retrieval_failed': continue
        path=ROOT/'.study/market/pages'/(r['cache_key']+'.txt')
        # During rebuilding, committed facts replace scratch, which is never required.
        facts=parse_facts(path.read_text()) if path.exists() else {}
        if 'arizonacustomknives.com/products/' in r['url'] and path.exists():
            text=path.read_text()
            detail=text.split('Product Details',1)[-1]
            m=re.search(r'Blade Length\s+(\d+(?:\.\d+)?)',detail)
            if m:facts['blade_length_in']=float(m[1])
            m=re.search(r'Weight \(oz\)\s+(\d+(?:\.\d+)?)',detail)
            if m:facts['weight_g']=round(float(m[1])*OZ,2)
            facts['weight_basis']='seller_weight_scope_unspecified'
        src[r['url']]={'url':r['url'],'title':r.get('page_title',''),'method':'direct_public_page',
                       'content_sha256':r.get('content_sha256'),'facts':facts}
    for r in json.loads((DATA/'web_evidence.json').read_text()):
        facts=parse_facts('\n'.join(re.sub(r'^L\d+:\s*','',s) for s in r['facts']))
        if facts.get('blade_length_in') is None: continue
        src[r['url']]={'url':r['url'],'title':r['title'],'method':'web_reader_catalog_facts','facts':facts}
    return src


def row_priority(r):
    f=r['input_file']
    return (10 if f.startswith('karambit_catalog') else 8 if f=='karambit_knives_min_3_375_in.csv' else 7 if f.startswith('karambit_reference') else 3)


def canonical_key(r):
    key=slug(r['model_family'])
    if r['model_family'] in ('CIVIVI Midwatch','Artisan Cobra','Hoback TALIM'):
        key+='__'+slug(r['blade_grade'])
    if r['model_family']=='United Cutlery Honshu':
        key+='__'+('d2' if r['blade_grade']=='D2' else '7cr13')
    if 'black-legion' in key or r['sku']=='BV448': key='black-legion-set-karambit'
    return key


def assemble():
    observations=json.loads((DATA/'observations.json').read_text())
    observations.extend(json.loads((DATA/'discovered_models.json').read_text()))
    source_facts=sources()
    overrides=json.loads((DATA/'curation.json').read_text())
    groups=defaultdict(list)
    for r in observations: groups[canonical_key(r)].append(r)
    # Same exact product URL can reconcile spelling/catalog-line aliases. Preserve
    # material-specific Midwatch and Cobra identities even if a bad input reused a URL.
    urlkeys=defaultdict(set)
    for key,rs in groups.items():
        for r in rs:
            # A shared category/home/search URL is not product identity.
            if r['url'] and re.search(r'/(?:item|products?|store/product|online-store)/[^/?]+',urlparse(r['url']).path) and '/department/' not in r['url']:
                urlkeys[r['url']].add(key)
    for keys in urlkeys.values():
        if len(keys)<2 or any('__' in k for k in keys): continue
        dest=sorted(keys,key=lambda k:(-max(row_priority(r) for r in groups.get(k,[])) if groups.get(k) else 0,k))[0]
        for key in keys-{dest}:
            groups[dest].extend(groups.pop(key,[]))
    records=[]
    for key,rs in sorted(groups.items()):
        if not rs: continue
        rs.sort(key=lambda r:(-row_priority(r),r['input_file'],r['input_row']))
        chosen=rs[0]
        urls=sorted({u for r in rs for u in r.get('all_urls',[r['url']]) if u and urlparse(u).path.strip('/')})
        urls=sorted(set(urls+overrides.get(key,{}).get('additional_verified_urls',[])))
        candidates=[source_facts[u] for u in urls if u in source_facts and source_facts[u]['facts'].get('blade_length_in')]
        candidates=[s for s in candidates if s['url'] not in overrides.get(key,{}).get('ignored_source_urls',[])]
        candidates.sort(key=lambda s:(-int(any(h in urlparse(s['url']).hostname for h in MANUFACTURERS)),
                                      -int('knifecenter.com' in s['url']),-int(s['method']=='web_reader_catalog_facts'),s['url']))
        current=candidates[0] if candidates else None
        facts=current['facts'] if current else {}
        lens=sorted({r['blade_length_in'] for r in rs if r['blade_length_in'] is not None})
        weights=sorted({r['weight_g'] for r in rs if r['weight_g'] is not None})
        row={'id':key,'model':chosen['model_family'],'blade_grade':facts.get('blade_grade',chosen['blade_grade']),
             'blade_length_in':facts.get('blade_length_in',chosen['blade_length_in']),
             'cutting_edge_in':facts.get('cutting_edge_in',chosen['cutting_edge_in']),
             'knife_type':'folder' if any(x in chosen['knife_type'].lower() for x in ('fold','manual','auto')) else 'fixed' if chosen['knife_type']=='fixed' else 'unspecified',
             'style_scope':'broader_style' if any(x in chosen['style'].lower() for x in ('hybrid','ringless','straight','kukri','p-kal','hawkbill_no_ring','non_ring')) else 'curved_karambit',
             'qualification':'source_confirmed_as_listed' if current else 'candidate_unverified',
             'weight_g':facts.get('weight_g',chosen['weight_g']),
             'weight_basis':facts.get('weight_basis',chosen['weight_scope'] or 'unverified_input_estimate'),
             'weight_verification':'current_source' if facts.get('weight_g') is not None else 'input_only',
             'weight_with_sheath_g':facts.get('weight_with_sheath_g',chosen['weight_with_sheath_g']),
             'source_url':current['url'] if current else chosen['url'],'all_source_urls':urls,
             'length_source_url':current['url'] if current else chosen['url'],
             'weight_source_url':current['url'] if facts.get('weight_g') is not None else chosen['url'],
             'source_method':current['method'] if current else 'supplied_csv_only',
             'availability_as_reported':chosen['availability_as_reported'],'market_segment':'historical_or_custom' if any(x in chosen['availability_as_reported'].lower() for x in ('discontinued','archiv','histor','preowned')) or any(x in chosen['url'] for x in ('arizonacustomknives','knife-market')) else 'retail_catalog',
             'availability_verified':False,'observation_count':len(rs),
             'input_lengths_in':lens,'input_weights_g':weights,
             'input_refs':[f'{r["input_file"]}:{r["input_row"]}' for r in rs],
             'notes':chosen['notes'],'conflicts':[],'research_date':'2026-10-13'}
        if len(lens)>1 and lens[-1]-lens[0]>0.08: row['conflicts'].append('input_blade_length_disagreement')
        if len(weights)>1 and weights[-1]-weights[0]>max(5,weights[0]*0.05): row['conflicts'].append('input_weight_disagreement')
        current_lengths=[s['facts']['blade_length_in'] for s in candidates]
        if len(current_lengths)>1 and max(current_lengths)-min(current_lengths)>0.08:
            row['conflicts'].append('published_length_disagreement')
        if current_lengths and min(current_lengths)<MINIMUM_IN<=max(current_lengths):
            row['qualification']='conditional_length_conflict'
        current_weights=[s['facts']['weight_g'] for s in candidates if s['facts'].get('weight_g')]
        if len(current_weights)>1 and max(current_weights)-min(current_weights)>max(5,min(current_weights)*0.05):
            row['conflicts'].append('published_weight_disagreement')
        if current and 'knifecountryusa.com' in current['url']:
            row['weight_g']=None;row['weight_basis']='package_or_shipping_not_knife'
            row['weight_verification']='no_knife_weight'
        row.update(overrides.get(key,{}))
        row['material_family']=family(row['blade_grade'])
        if row['blade_length_in'] is not None and row['blade_length_in']<MINIMUM_IN and row['qualification']!='conditional_length_conflict':
            row['qualification']='excluded_below_minimum'
        row['qualified']=row['qualification']=='source_confirmed_as_listed' and row['blade_length_in'] is not None and row['blade_length_in']>=MINIMUM_IN
        row['plot_eligible']=row['qualified'] and row['weight_g'] is not None and row['weight_verification']=='current_source' and row['weight_basis'] in ('published_knife_spec','explicit_knife_only')
        row['strict_weight_eligible']=row['plot_eligible'] and row['weight_basis']=='explicit_knife_only'
        records.append(row)
    return records,source_facts


def write_csv(path,rows,fields=None):
    fields=fields or list(rows[0])
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader()
        for r in rows: w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else '' if v is None else v for k,v in r.items() if k in fields})


def stats(records,benchmark):
    qualified=[r for r in records if r['qualified']]
    weighted=[r for r in records if r['plot_eligible']]
    masses=[r['weight_g'] for r in weighted]
    bm=benchmark['primary']['mass_g']
    out={'research_date':'2026-10-13','minimum_blade_length_in':MINIMUM_IN,
         'input_rows':sum(1 for r in records for ref in r['input_refs'] if not ref.startswith('discovered_models.json:')),
         'discovered_observations':sum(1 for r in records for ref in r['input_refs'] if ref.startswith('discovered_models.json:')),
         'canonical_entries':len(records),
         'qualification_counts':dict(Counter(r['qualification'] for r in records)),
         'qualified_entries':len(qualified),'plotted_entries':len(weighted),
         'qualified_missing_comparable_weight':len(qualified)-len(weighted),
         'strict_weight_entries':sum(r['strict_weight_eligible'] for r in records),
         'market_median_g':statistics.median(masses) if masses else None,
         'market_min_g':min(masses) if masses else None,'market_max_g':max(masses) if masses else None,
         'benchmark_g':bm,'benchmark_lighter_than_count':sum(m>bm for m in masses),
         'benchmark_lighter_than_fraction':sum(m>bm for m in masses)/len(masses) if masses else None,
         'benchmark_below_median_fraction':1-bm/statistics.median(masses) if masses else None,
         'lighter_models':[{'model':r['model'],'weight_g':r['weight_g'],'style_scope':r['style_scope'],'source_url':r['source_url']} for r in sorted(weighted,key=lambda r:r['weight_g']) if r['weight_g']<bm],
         'material_counts':dict(Counter(r['material_family'] for r in qualified)),
         'material_weight_counts':dict(Counter(r['material_family'] for r in weighted)),
         'claim_scope':'Unweighted catalog entries, not sales share or a proof of total global coverage. CAD mass vs published commercial knife specifications. No performance equivalence inferred.'}
    out['missing_weight_bounds']={'minimum_fraction_lighter_than_benchmark':sum(m>bm for m in masses)/len(qualified),
                                  'maximum_fraction_lighter_than_benchmark':(sum(m>bm for m in masses)+len(qualified)-len(weighted))/len(qualified),
                                  'meaning':'Extreme bookkeeping bounds if every missing comparable weight were below or above the CAD benchmark. Not confidence intervals.'}
    out['sensitivity']={}
    for name,subset in [('explicit_knife_only',[r for r in weighted if r['strict_weight_eligible']]),
                        ('curved_karambit_only',[r for r in weighted if r['style_scope']=='curved_karambit']),
                        ('metal_blades_only',[r for r in weighted if r['material_family']!='Polymer / nonmetal'])]:
        vals=[r['weight_g'] for r in subset]
        out['sensitivity'][name]={'n':len(vals),'median_g':statistics.median(vals) if vals else None,'nominally_heavier_than_benchmark':sum(v>bm for v in vals)}
    return out


def plot(records,benchmark,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':INK,
                         'axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,
                         'axes.edgecolor':'#CFD1CD','axes.spines.top':False,'axes.spines.right':False,
                         'figure.facecolor':BG,'axes.facecolor':BG,'svg.fonttype':'none',
                         'savefig.facecolor':BG,'pdf.fonttype':42,'svg.hashsalt':'jarambit-market-census-v1'})
    rows=[r for r in records if r['plot_eligible']]
    bm=benchmark['primary']['mass_g']; bl=benchmark['primary']['blade_length_in']
    out=DATA/'figures';out.mkdir(exist_ok=True)
    x_max=max(450,math.ceil(max(r['weight_g'] for r in rows)/50)*50)
    bins=np.arange(0,x_max+25,25)
    families=[f for f in PALETTE if any(r['material_family']==f for r in rows)]
    fig=plt.figure(figsize=(16.5,11.5))
    gs=fig.add_gridspec(2,2,height_ratios=[1,3.1],width_ratios=[4.8,1.8],
                        left=.075,right=.95,bottom=.17,top=.78,wspace=.24,hspace=.07)
    top=fig.add_subplot(gs[0,0]);ax=fig.add_subplot(gs[1,0],sharex=top);side=fig.add_subplot(gs[:,1])
    fig.text(.075,.94,'THE WEIGHT OF THE MARKET',fontsize=12,fontweight='bold',color='#5A6B72')
    fig.text(.075,.885,'SWITCHBACK sits near the lightweight edge',fontsize=27,fontweight='bold')
    fig.text(.075,.84,f'Karambit-style knives with published blade length ≥ {MINIMUM_IN:g} in  •  Research: October 13, 2026',fontsize=12,color='#5A6B72')
    for f in families:
        group=[r for r in rows if r['material_family']==f]
        top.hist([r['weight_g'] for r in group],bins=bins,color=PALETTE[f],alpha=.42,edgecolor=PALETTE[f],linewidth=.8)
        for style,marker in [('curved_karambit','o'),('broader_style','D')]:
            points=[r for r in group if r['style_scope']==style]
            ax.scatter([r['weight_g'] for r in points],[r['blade_length_in'] for r in points],
                       c=PALETTE[f],s=66 if marker=='o' else 48,marker=marker,alpha=.80,
                       edgecolor=BG,linewidth=.7,zorder=3)
    for a in (top,ax):
        a.axvline(bm,color=GOLD,lw=2,zorder=2)
        a.set_xlim(0,x_max)
        a.grid(axis='y',color='#DEDCD6',lw=.65,zorder=0)
    top.tick_params(axis='x',labelbottom=False,bottom=False)
    top.set_ylabel('Catalog entries',fontsize=10)
    top.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    top.text(.98,.85,'Shared 25 g bins · overlapping fills, α = 0.42',transform=top.transAxes,ha='right',fontsize=9,color='#5A6B72')
    ax.axhline(MINIMUM_IN,color='#AEB6B7',linestyle=(0,(3,3)),lw=1)
    ax.set_ylim(3.25,max(7.6,max(r['blade_length_in'] for r in rows)+.3))
    ax.set_xlabel('Knife weight (g)  →  heavier',fontsize=12,labelpad=13)
    ax.set_ylabel('Published blade length (in)  →  longer',fontsize=12,labelpad=12)
    ax.scatter([bm],[bl],marker='*',s=560,c=GOLD,edgecolor=INK,lw=1.3,zorder=7)
    ax.annotate(f'SWITCHBACK C.10a RC4\n{bm:.3f} g · {bl:.2f} in\nCAD prediction; unmeasured',xy=(bm,bl),xytext=(bm+40,bl+.8),
                fontsize=11,fontweight='bold',color=INK,arrowprops={'arrowstyle':'-','color':INK,'lw':1.1},
                bbox={'boxstyle':'round,pad=.5','fc':BG,'ec':'#D5D2C7','alpha':.97},zorder=8)
    labels=[('hoback-talim__titanium-alloy-unspecified',(-25,75),'TALIM titanium\n51.03 g · broader style'),
            ('bastinelli-creations-chopper',(16,38),'Bastinelli Chopper\n70.87 g'),
            ('crkt-du-hoc-fixed',(12,15),'CRKT Du Hoc Fixed'),
            ('tops-tac-tops',(10,-15),'TOPS TAC-TOPS')]
    for key,offset,label in labels:
        r=next((r for r in rows if r['id']==key),None)
        if r: ax.annotate(label,(r['weight_g'],r['blade_length_in']),xytext=offset,textcoords='offset points',fontsize=9,
                          color=INK,arrowprops={'arrowstyle':'-','lw':.7,'color':'#89959A'},zorder=6)
    side.axis('off')
    side.text(0,.98,f'{bm:.3f}',fontsize=38,fontweight='bold',color=INK)
    side.text(0,.915,'grams · C.10a CAD mass',fontsize=12,color='#5A6B72')
    side.text(0,.82,f'{summary["benchmark_lighter_than_fraction"]:.1%}',fontsize=34,fontweight='bold',color='#4D9B93')
    side.text(0,.75,f'lighter than {summary["benchmark_lighter_than_count"]} of {len(rows)}\nplotted catalog entries',fontsize=12,linespacing=1.6)
    side.text(0,.64,f'{summary["benchmark_below_median_fraction"]:.0%}',fontsize=32,fontweight='bold',color='#89739C')
    side.text(0,.57,f'below catalog median\n{summary["market_median_g"]:.1f} g',fontsize=12,linespacing=1.6)
    side.text(0,.43,'HOW TO READ',fontsize=10,fontweight='bold',color='#5A6B72')
    side.text(0,.37,'Left = lighter. Up = longer.\nOne point = one model/material\nentry or distinct custom example.\n\nColor = blade material family.\nCircle = curved karambit.\nDiamond = broader style.',fontsize=10,linespacing=1.65,va='top')
    side.text(0,.02,f'{summary["qualified_entries"]} qualifying entries\n{summary["qualified_missing_comparable_weight"]} without comparable verified weight',fontsize=10,linespacing=1.6)
    handles=[Patch(facecolor=PALETTE[f],edgecolor=PALETTE[f],alpha=.65,label=f) for f in families]
    fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.075,.073),ncol=4,frameon=False,fontsize=10,columnspacing=2.2)
    fig.text(.075,.035,'Catalog specifications, not physical measurements. Retail, archived and custom examples included; sales share is unknown.\nC.10a length is CAD tip-to-heel. Commercial measurement conventions differ. Conflicted lengths, sets, sheaths and shipping weights excluded.',fontsize=9,color='#5A6B72',linespacing=1.5)
    save_figure(fig,out/'market_landscape')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(15,8));fig.subplots_adjust(left=.075,right=.95,bottom=.23,top=.77)
    fig.text(.075,.925,'WHERE KNIFE WEIGHTS CLUSTER',fontsize=13,color='#5A6B72',fontweight='bold')
    fig.text(.075,.87,'Knife weights by blade material',fontsize=27,fontweight='bold')
    fig.text(.075,.81,f'{len(rows)} comparable catalog weights · blade length ≥ 3.375 in · shared 25 g bins · transparency α = 0.42',fontsize=11,color='#5A6B72')
    for f in families:
        vals=[r['weight_g'] for r in rows if r['material_family']==f]
        ax.hist(vals,bins=bins,color=PALETTE[f],edgecolor=PALETTE[f],alpha=.42,lw=1,label=f'{f} (n={len(vals)})')
    ax.axvline(bm,color=GOLD,lw=3,label=f'SWITCHBACK C.10a RC4: {bm:.3f} g (CAD)')
    ax.text(.02,.965,f'SWITCHBACK C.10a\n{bm:.3f} g · CAD prediction',transform=ax.transAxes,fontsize=12,fontweight='bold',va='top',bbox={'fc':BG,'ec':'none','alpha':.9})
    ax.set(xlabel='Knife weight (g)',ylabel='Catalog entries in each 25 g bin',xlim=(0,x_max))
    ax.grid(axis='y',color='#DEDCD6',lw=.65)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(frameon=False,ncol=3,loc='upper left',bbox_to_anchor=(0,-.16),fontsize=10)
    fig.text(.075,.03,'Counts represent catalog entries, not market share. Missing weights, conflicting blade lengths, packaged weights and set weights are excluded.',fontsize=9,color='#5A6B72')
    save_figure(fig,out/'weight_histogram')
    plt.close(fig)
    grades=sorted({r['blade_grade'] for r in rows},key=lambda g:(list(PALETTE).index(family(g)),statistics.median([r['weight_g'] for r in rows if r['blade_grade']==g])))
    fig,ax=plt.subplots(figsize=(15,max(7,len(grades)*.38+2.6)))
    fig.subplots_adjust(left=.24,right=.95,bottom=.13,top=.88)
    for y,g in enumerate(grades):
        vals=sorted([r['weight_g'] for r in rows if r['blade_grade']==g])
        offsets=[((i%5)-2)*.09 for i in range(len(vals))]
        ax.scatter(vals,[y+o for o in offsets],c=PALETTE[family(g)],s=46,alpha=.8,edgecolor=BG,lw=.6)
        ax.plot([min(vals),max(vals)],[y,y],color=PALETTE[family(g)],alpha=.25,lw=2,zorder=0)
    ax.axvline(bm,color=GOLD,lw=2.5)
    ax.set_yticks(range(len(grades)),[f'{g}  (n={sum(r["blade_grade"]==g for r in rows)})' for g in grades])
    ax.invert_yaxis();ax.set_xlabel('Knife weight (g)');ax.grid(axis='x',color='#DEDCD6',lw=.65)
    fig.text(.24,.95,'Exact blade grades, with every comparable weight',fontsize=22,fontweight='bold')
    fig.text(.24,.91,'Gold line: SWITCHBACK C.10a CAD mass · small vertical offsets separate equal weights',fontsize=10,color='#5A6B72')
    save_figure(fig,out/'weight_by_grade')
    plt.close(fig)


def main():
    global sources
    args=argparse.ArgumentParser();args.add_argument('--prepare-facts',action='store_true');args.add_argument('--no-plots',action='store_true');opts=args.parse_args()
    facts_path=DATA/'source_facts.json'
    if opts.prepare_facts:
        facts_path.write_text(json.dumps(sources(),indent=2,ensure_ascii=False)+'\n')
        print('Prepared frozen source facts');return
    # Rebuild reads frozen facts only. Never make current network or scratch a hidden input.
    frozen=json.loads(facts_path.read_text())
    sources=lambda:frozen
    records,_=assemble();benchmark=json.loads((DATA/'benchmark.json').read_text())
    summary=stats(records,benchmark)
    bm=benchmark['primary']['mass_g']
    for r in records:
        r['market_weight_minus_c10a_g']=round(r['weight_g']-bm,3) if r['plot_eligible'] else None
        r['c10a_nominal_weight_saving_fraction']=1-bm/r['weight_g'] if r['plot_eligible'] else None
    (DATA/'census.json').write_text(json.dumps(records,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    (DATA/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    write_csv(DATA/'census.csv',records)
    write_csv(DATA/'qualified_by_material.csv',sorted([r for r in records if r['qualified']],key=lambda r:(r['material_family'],r['blade_grade'],r['model'])))
    write_csv(DATA/'review_queue.csv',[r for r in records if not r['qualified']])
    grades=[]
    for grade in sorted({r['blade_grade'] for r in records if r['qualified']},key=lambda g:(family(g),g)):
        group=[r for r in records if r['qualified'] and r['blade_grade']==grade]
        vals=[r['weight_g'] for r in group if r['plot_eligible']]
        grades.append({'material_family':family(grade),'blade_grade':grade,'qualifying_entries':len(group),'comparable_weights':len(vals),
                       'minimum_weight_g':min(vals) if vals else None,'median_weight_g':statistics.median(vals) if vals else None,'maximum_weight_g':max(vals) if vals else None})
    write_csv(DATA/'material_summary.csv',grades)
    nearby=sorted([r for r in records if r['weight_g'] is not None and r['weight_g']<=80],key=lambda r:r['weight_g'])
    write_csv(DATA/'nearby_weight_links.csv',nearby,['model','blade_grade','weight_g','blade_length_in','qualification','weight_basis','source_url','notes'])
    if not opts.no_plots:plot(records,benchmark,summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
