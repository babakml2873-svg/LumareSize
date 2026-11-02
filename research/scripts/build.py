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
    recs[i]={
     'Net Weight (kg)':rnd(net),'Shipping Weight (kg)':rnd(gross),
     'Weight Status':status,'Source Type':stype,
     'Reference Brand':'; '.join(dict.fromkeys(str(x.get('brand')) for x in refs)),
     'Reference Model':'; '.join(dict.fromkeys(str(x.get('model')) for x in refs)),
     'Reference Weight (kg)':'; '.join(str(rnd(x['weight_kg'])) for x in refs)+('' if all(not x.get('pack_qty') or x.get('pack_qty')==1 for x in refs) else ' (pack totals: '+', '.join(f"{x.get('pack_qty')}" for x in refs)+')'),
     'Source URL':' | '.join(dict.fromkeys(str(x.get('url')) for x in refs)),
     'Confidence':conf,'Research Notes':'; '.join(notes),
     '_cls':r.cls}
R=pd.DataFrame.from_dict(recs,orient='index')
cols=['Net Weight (kg)','Shipping Weight (kg)','Weight Status','Source Type','Reference Brand','Reference Model','Reference Weight (kg)','Source URL','Confidence','Research Notes']
full=d.join(R)
img=full['Net Weight (kg)'].isna()
full.loc[img,'Weight Status']='N/A'
full.loc[img,'Research Notes']='Image-only row of the Shopify export (no variant/SKU) – weight is given on the product\'s variant row(s)'
full.to_pickle(SP+'final.pkl')
R.to_pickle(SP+'recs.pkl')
print(R['Weight Status'].value_counts(), R['Source Type'].value_counts(), R.Confidence.value_counts())
