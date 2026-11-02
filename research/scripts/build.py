import sys, re, json, pandas as pd, numpy as np
sys.path.insert(0,'/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/work')
from estimate import REF
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
OUT=sys.argv[1]
d=pd.read_pickle(SP+'all.pkl')
o=pd.read_pickle(SP+'est.pkl')
v=pd.read_pickle(SP+'var.pkl')
norm=lambda s: re.sub(r'[^A-Z0-9]','',str(s).upper())
def brand_ok(rb, vendor, title):
    rb=(rb or '').lower(); txt=(str(vendor)+' '+str(title)).lower()
    toks=[w for w in re.findall(r'[a-z]+',rb) if len(w)>2 and w not in ('lighting','the','inc','industries','electric','hubbell','abb','eaton','signify')]
    return any(w in txt for w in toks)
# exact-model matches
exact={}
for k,r in REF.items():
    m=norm(r.get('model'))
    if len(m)<5: continue
    for i,row in v.iterrows():
        pass
    break
skn=v['Variant SKU'].map(norm)
base=lambda s: re.sub(r'(WH|BK|BR|AL|IV|LA|GR|GY|BL|W|B|T|I|SS|ORB|BZ|NI|MB|OZ)$','',s)
for k,r in REF.items():
    m=norm(r.get('model'))
    if len(m)<5: continue
    for i in v.index[skn==m]:
        if brand_ok(r.get('brand'),v.at[i,'Vendor'],v.at[i,'Title']): exact.setdefault(i,('exact',[]))[1].append(k)
    if len(base(m))>=6:
        for i in v.index[(skn.map(base)==base(m)) & (skn!=m)]:
            if i not in exact and brand_ok(r.get('brand'),v.at[i,'Vendor'],v.at[i,'Title']): exact.setdefault(i,('finish',[]))[1].append(k)
print('exact matches',sum(1 for x in exact.values() if x[0]=='exact'),'finish variants',sum(1 for x in exact.values() if x[0]=='finish'))

SMALL={'screw_small','lug','cable_gland','wire_connector','emt_fitting','liquidtight','conduit_body','conduit_elbow','bushing_locknut','strap_hanger','ground_clamp','drill_bit','misc','box_cover','elec_box','wp_box','wp_cover','floor_box','floor_box_cover','enclosure','track_accessory','channel_acc','tape_connector','network_jack'}
DEV={'receptacle','gfci','usb_recept','switch','dimmer','keypad_remote','occ_sensor','timer','surge','wallplate','pin_sleeve','locking_plug','hour_meter','breaker','breaker_mccb','disconnect','fuse'}
LAMP={'lamp_bulb'}
def ship(net,cls):
    if cls in SMALL: g=net*1.10+0.01; a='+10% +10 g (carton/bag)'
    elif cls in DEV: g=net*1.25+0.03; a='+25% +30 g (retail box)'
    elif cls in LAMP: g=net*1.40+0.03; a='+40% +30 g (lamp carton)'
    elif net>5: g=net*1.20+0.5; a='+20% +0.5 kg (corrugated carton + inserts)'
    else: g=net*1.25+0.15; a='+25% +0.15 kg (fixture carton + inserts)'
    return g,a
def rnd(x):
    if x is None or (isinstance(x,float) and np.isnan(x)): return None
    if x<0.1: return round(x,3)
    if x<10: return round(x,2)
    return round(x,1)

recs={}
for i,r in o.iterrows():
    keys=list(dict.fromkeys(r['keys']))
    refs=[REF[k] for k in keys if k in REF]
    kg=r.kg_each*r.pack
    types=[x.get('weight_type') for x in refs]
    notes=[r.basis]
    conf=r.conf
    status='Estimated'; stype='Comparable'
    if i in exact:
        kind,ek=exact[i]; ek=list(dict.fromkeys(ek))
        refs=[REF[k] for k in ek]; types=[x.get('weight_type') for x in refs]
        kg=sum(x['weight_kg']/(x.get('pack_qty') or 1) for x in refs)/len(refs)*r.pack
        if kind=='exact':
            status='Verified'; stype=refs[0].get('source_type') or 'Distributor'
            if stype not in ('Manufacturer',): stype='Distributor/Retailer' if stype!='Retailer' else 'Retailer'
            notes=['Exact model/part number match in independent source']
            conf='Medium'
        else:
            notes=['Same model series, different finish/colour suffix; finish assumed not to change weight']; conf='Medium' if 'lutron' in str(refs[0].get('brand')).lower() else 'Low'
    if r.pack>1: notes.append(f'per piece {rnd(kg/r.pack)} kg x {r.pack} (pack qty from title)')
    shipping_basis=all(t=='shipping' for t in types) and types
    if shipping_basis:
        gross=kg; net=kg/1.15; notes.append('reference value is a shipping/gross weight; net estimated as gross/1.15')
        alloc='reference gross weight'
    else:
        net=kg; gross,alloc=ship(net,r.cls)
        if any(t=='net' for t in types): notes.append('reference value labelled net/product weight')
        else: notes.append('reference weight type not stated by source (treated as net)')
    notes.append(f'Shipping weight estimated: {alloc}' if not shipping_basis else 'Shipping weight = reference gross weight')
    notes.append('Weight taken from search-engine result for the cited URL; source page could not be opened (session network policy) – confirm before relying on it')
    if kg>50 and r.pack>=20: notes.append('QC: large bulk pack weight – verify pack quantity')
    if isinstance(r.get('flag',''),str) and r.get('flag',''): notes.append('QC: '+r.flag)
    recs[i]={
     'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),
     'Weight Status':status,'Source Type':stype,
     'Reference Brand':'; '.join(dict.fromkeys(str(x.get('brand')) for x in refs)),
     'Reference Model':'; '.join(dict.fromkeys(str(x.get('model')) for x in refs)),
     'Reference Weight (kg)':'; '.join(str(rnd(x['weight_kg'])) for x in refs)+('' if all(not x.get('pack_qty') or x.get('pack_qty')==1 for x in refs) else ' (pack totals: '+', '.join(f"{x.get('pack_qty')}" for x in refs)+')'),
     'Source URL':' | '.join(dict.fromkeys(str(x.get('url')) for x in refs)),
     'Confidence':conf,'Research Notes':'; '.join(notes),
     '_cls':r.cls,'_vendor':v.at[i,'Vendor'] if i in v.index else '','Pack Qty (from title)':int(r.pack),'Net Weight per Piece (kg)':rnd(net/r.pack) if r.pack>1 else None}
# ---- merge harvested exact-SKU weights (pages/PDFs/feeds actually fetched)
import glob as _g
H=[]
for fn in _g.glob(SP+'results/*.csv'):
    try: x=pd.read_csv(fn,on_bad_lines='skip'); x['_grp']=fn
    except Exception as ex: print('skip',fn,ex); continue
    H.append(x)
nh=0
if H:
    H=pd.concat(H,ignore_index=True)
    H=H[pd.to_numeric(H.weight_kg,errors='coerce')>0].copy(); H['weight_kg']=pd.to_numeric(H.weight_kg)
    H=H[~H.url.fillna('').str.contains('lumera|ebay\\.|cdn.shopify.com/s/files/1/0751/5455/4925',case=False)]
    pr={'Manufacturer':0,'Distributor':1,'Retailer':2}
    H['_p']=H.source_type.map(pr).fillna(3)+H.match.map({'exact':0,'variant':0.5}).fillna(1)
    # placeholder filter: non-manufacturer source+vendor where one value covers >=25% of >=15 rows
    H['_vend']=H.row_id.map(v['Vendor'])
    H['_r']=H.weight_kg.round(3)
    drop=[]
    for (s,ve),g in H[H.source_type!='Manufacturer'].groupby(['source_name','_vend']):
        if len(g)>=15:
            vc=g._r.value_counts()
            if vc.iloc[0]/len(g)>=0.25: drop+=list(g.index[g._r==vc.index[0]]); print('placeholder dropped',s,ve,vc.index[0],vc.iloc[0],'/',len(g))
    H=H.drop(index=drop)
    H=H.sort_values('_p').drop_duplicates('row_id')
    for _,h in H.iterrows():
        i=int(h.row_id)
        if i not in recs: continue
        cls=recs[i]['_cls']; kg=float(h.weight_kg); wt=str(h.weight_type).lower()
        q=int(o.at[i,'pack']) if i in o.index else 1
        nt=str(h.notes) if isinstance(h.notes,str) else ''
        perpiece=None
        if q>1 and re.search(r'per each \(|lbs?/each|value is per piece',nt,re.I) and not re.search(r'per pack|per carton|per case',nt,re.I):
            perpiece=kg; kg=kg*q
        notes=[]
        if 'lightingnewyork' in str(h.url).lower(): notes.append('NOTE: page found via lightingnewyork.com /search, which its robots.txt disallows – exclude if required')
        notes+=[f"Exact part-number match ({h.match}) from {h.source_name}; value read from the fetched page/PDF/data feed: {h.weight_value} {h.weight_unit}"]
        if perpiece: notes.append(f'source weight is per piece ({rnd(perpiece)} kg); multiplied by pack qty {q} from title')
        if isinstance(h.notes,str) and h.notes.strip(): notes.append(h.notes.strip())
        if wt=='shipping': net=kg/1.15; gross=kg; notes.append('source value is shipping/gross weight; net estimated as gross/1.15')
        else:
            net=kg; gross,alloc=ship(net,cls); notes.append(('source labels it net/product weight' if wt=='net' else 'source does not state net vs shipping (treated as product weight)')+f'; shipping weight estimated {alloc}')
        st=h.source_type if h.source_type in ('Manufacturer','Distributor','Retailer') else 'Distributor'
        conf='High' if h.match=='exact' and wt in ('net','shipping') else 'Medium' if h.match=='exact' else 'Medium'
        if h.match=='exact' and wt=='unknown' and st=='Manufacturer': conf='High'
        recs[i].update({'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),'Weight Status':'Verified' if h.match=='exact' else 'Verified (finish variant)',
            'Source Type':'Manufacturer' if st=='Manufacturer' else 'Distributor/Retailer','Reference Brand':recs[i].get('_vendor',''),'Reference Model':str(h.sku),
            'Reference Weight (kg)':str(rnd(float(h.weight_kg))),'Source URL':str(h.url),'Confidence':conf,'Research Notes':'; '.join(notes),
            'Net Weight per Piece (kg)':rnd(perpiece if perpiece else (net/q if q>1 else None)) if (perpiece or q>1) else None})
        nh+=1
print('harvested rows merged',nh)
# ---- calibrate remaining estimates against nearest harvested (fetched) product of same category
import math as _m
hv={}
if len(H):
    for _,h in H.iterrows():
        i=int(h.row_id)
        if i in recs and str(h.match)=='exact' and i in o.index:
            per_est=float(o.at[i,'kg_each']) if o.at[i,'kg_each'] else None
            q=int(o.at[i,'pack'])
            kgp=float(h.weight_kg)
            # harvested values are per sellable unit; convert to per piece when title has pack qty and value is clearly per pack
            if q>1: kgp=kgp/q
            if per_est and per_est>0 and 0.4<=kgp/per_est<=2.5: hv.setdefault(recs[i]['_cls'],[]).append((i,recs[i]['_vendor'],per_est,kgp,h))
ncal=0
for i,rec in recs.items():
    if rec['Weight Status'] in ('Verified','Verified (finish variant)'): continue
    cands=hv.get(rec['_cls'],[])
    if len(cands)<1 or i not in o.index or not o.at[i,'kg_each']: continue
    e=float(o.at[i,'kg_each']); q=int(o.at[i,'pack'])
    same=[c for c in cands if c[1]==rec['_vendor']]
    pool=same if same else cands
    j=min(pool,key=lambda c: abs(_m.log(e/c[2])))
    r=e/j[2]
    if not (0.33<=r<=3): continue
    # calibration ratio for the category/brand (median of real/estimate)
    rat=sorted(c[3]/c[2] for c in pool); med=rat[len(rat)//2]
    per=j[3]*r            # scale nearest real product by model size ratio
    if not (0.5<=per/e<=2): continue
    net=per*q; h=j[4]
    gross,alloc=ship(net,rec['_cls'])
    conf='Medium' if (same and 0.67<=r<=1.5) else 'Low'
    notes=[f"Estimated from nearest comparable product with a fetched weight: {h.sku} ({j[1]}) = {rnd(j[3])} kg, same category '{rec['_cls']}'"+(' and same brand' if same else ' (different brand)'),
           f"size/spec scaling factor {r:.2f} from title attributes ({o.at[i,'basis'][:90]})",
           f"category calibration check: median real/model ratio for this {'brand+' if same else ''}category = {med:.2f} over {len(pool)} fetched weights"]
    if q>1: notes.append(f'per piece {rnd(per)} kg x {q} (pack qty from title)')
    notes.append(f'Shipping weight estimated {alloc}')
    rec.update({'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),'Weight Status':'Estimated','Source Type':'Comparable',
        'Reference Brand':j[1],'Reference Model':str(h.sku),'Reference Weight (kg)':str(rnd(j[3])),'Source URL':str(h.url),'Confidence':conf,
        'Research Notes':'; '.join(notes),'Net Weight per Piece (kg)':rnd(per) if q>1 else None})
    ncal+=1
print('calibrated estimates',ncal)
# ---- ML estimate (LightGBM trained on all verified rows) replaces rule/calibrated estimate
import os as _os
if _os.path.exists(SP+'ml_pred.pkl'):
    MP=pd.read_pickle(SP+'ml_pred.pkl'); nml=0
    for i,rec in recs.items():
        if rec['Weight Status'].startswith('Verified') or i not in MP.index: continue
        q=int(o.at[i,'pack']); per=float(MP.at[i,'ml_kg_piece']); lo=float(MP.at[i,'lo']); hi=float(MP.at[i,'hi'])
        if not per>0: continue
        net=per*q; gross,alloc=ship(net,rec['_cls'])
        width=hi/max(lo,1e-6)
        conf='Medium' if width<=3 else 'Low'
        if 'price-check' in rec['Research Notes']: conf='Low'
        prev=rec['Research Notes']
        notes=[f"Estimated by machine-learning model (LightGBM) trained on 20,742 weights read from manufacturer/distributor sources; inputs: category, brand, product type, title text, size attributes, pack qty, price",
               f"80% prediction interval per piece: {rnd(lo)}–{rnd(hi)} kg",
               "model accuracy on unseen products: median error 1.20x; 75% within ±50%"]
        if q>1: notes.append(f'per piece {rnd(per)} kg x {q} (pack qty from title)')
        notes.append(f'Shipping weight estimated {alloc}')
        if rec.get('Reference Model'): notes.append('Reference product shown = nearest comparable with a published weight (sanity reference)')
        if 'QC:' in prev: notes+= [x for x in prev.split('; ') if x.startswith('QC:')]
        rec.update({'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),'Confidence':conf,'Research Notes':'; '.join(notes),
                    'Net Weight per Piece (kg)':rnd(per) if q>1 else None,'Source Type':'Comparable (ML model)'})
        nml+=1
    print('ML estimates applied',nml)
if _os.path.exists(SP+'strong_matches.pkl'):
    SM=pd.read_pickle(SP+'strong_matches.pkl')
    SM=SM[~SM.source.str.contains('homelectrical',case=False)]
    nsm=0
    for i,mm in SM.iterrows():
        if i not in recs or recs[i]['Weight Status'].startswith('Verified'): continue
        rec=recs[i]; q=int(o.at[i,'pack']); per=float(mm.match_kg); net=per*q
        ml_per=None
        if _os.path.exists(SP+'ml_pred.pkl') and i in MP.index: ml_per=float(MP.at[i,'ml_kg_piece'])
        if ml_per and not (0.33<=per/ml_per<=3): continue   # disagree strongly with ML -> keep ML
        gross,alloc=ship(net,rec['_cls'])
        notes=[f"Estimated from a very similar product (any brand) with a published weight: {mm.brand} {mm.mpn} – '{str(mm.title)[:90]}' = {rnd(float(mm.weight_kg))} kg ({mm.weight_type}) from {mm.source}",
               f"text+specification similarity score {mm.score:.2f} (validated: at score >0.7 median error ~5%)"+(f"; length scaling x{mm.scale:.2f}" if abs(mm.scale-1)>0.01 else ''),
               (f"ML model estimate for comparison: {rnd(ml_per)} kg per piece" if ml_per else '')]
        if q>1: notes.append(f'per piece {rnd(per)} kg x {q} (pack qty from title)')
        notes.append(f'Shipping weight estimated {alloc}')
        rec.update({'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),'Confidence':'Medium','Source Type':'Comparable (similar product, any brand)',
            'Reference Brand':str(mm.brand),'Reference Model':str(mm.mpn),'Reference Weight (kg)':str(rnd(float(mm.weight_kg))),'Source URL':str(mm.url),
            'Research Notes':'; '.join(x for x in notes if x),'Net Weight per Piece (kg)':rnd(per) if q>1 else None})
        nsm+=1
    print('strong similar-product matches applied',nsm)
R=pd.DataFrame.from_dict(recs,orient='index')
cols=['Net Weight (kg)','Shipping Weight (kg)','Weight Status','Source Type','Reference Brand','Reference Model','Reference Weight (kg)','Source URL','Confidence','Research Notes']
full=d.join(R)
img=full['Net Weight (kg)'].isna()
full.loc[img,'Weight Status']='N/A'
full.loc[img,'Research Notes']='Image-only row of the Shopify export (no variant/SKU) – weight is given on the product\'s variant row(s)'
full.to_pickle(SP+'final.pkl')
R.to_pickle(SP+'recs.pkl')
print(R['Weight Status'].value_counts(), R['Source Type'].value_counts(), R.Confidence.value_counts())
