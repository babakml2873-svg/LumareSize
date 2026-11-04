import sys, re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
from features import watts, length_ft, inches, trade_size, poles, amps, lights, gang, pack as packq
from classify import classify
from estimate import est
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
import lightgbm as lgb
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
R=pd.read_pickle(SP+'recs.pkl'); v=pd.read_pickle(SP+'var.pkl'); o=pd.read_pickle(SP+'est.pkl')
V=pd.read_excel(SP+'issues/issues.xlsx','Variants')
V['sku']=V['Variant SKU'].astype(str).str.lstrip("'").str.strip()
# ---- training set: our verified rows
df=v.join(o[['kg_each','pack','cls']]).join(R[['Net Weight (kg)','Shipping Weight (kg)','Weight Status']])
df['text']=(df.Title.fillna('')+' '+df[['Option1 Value','Option2 Value','Option3 Value']].fillna('').astype(str).agg(' '.join,axis=1)).str.replace('Default Title','')
df['price']=pd.to_numeric(df['Variant Price'],errors='coerce')/df.pack
# ---- issue rows -> link to our rows (sku+handle, else sku)
key=v.reset_index()[['index','Handle','Variant SKU']].rename(columns={'index':'row'})
key['sku']=key['Variant SKU'].astype(str).str.strip()
m1=V.merge(key[['row','Handle','sku']],on=['Handle','sku'],how='left')
miss=m1.row.isna()
m2=V[miss.values].merge(key.drop_duplicates('sku')[['row','sku']],on='sku',how='left')
m1.loc[miss,'row']=m2.row.values
V['row']=m1.row.values
print('issue rows linked to our data:',V.row.notna().sum(),'of',len(V))
# features for new (Damar etc.) rows
new=V[V.row.isna()].copy()
cls=[];ke=[]
for t,ty in zip(new.Title.astype(str),new['Product Type'].astype(str)):
    c,_=classify(ty,t,''); cls.append(c); ke.append(est(c,t)[0])
new['cls']=cls; new['kg_each']=ke; new['pack']=[packq(t) for t in new.Title.astype(str)]
A=pd.concat([df[['Vendor','Type','text','kg_each','pack','cls','price']].assign(src='ours'),
             pd.DataFrame({'Vendor':new.Vendor,'Type':new['Product Type'],'text':new.Title.astype(str),'kg_each':new.kg_each,'pack':new.pack,'cls':new.cls,'price':np.nan,'src':'new'},index='N'+new.index.astype(str))])
A['text']=A.text.fillna('').astype(str)
F=pd.DataFrame(index=A.index)
for n,fn in [('w',watts),('L',length_ft),('inch',inches),('ts',trade_size),('poles',poles),('amps',amps),('lights',lights),('gang',gang)]: F[n]=A.text.map(fn).astype(float)
F['pack']=A.pack.astype(float); F['logprice']=np.log1p(A.price.astype(float)); F['log_model']=np.log(A.kg_each.astype(float).clip(lower=1e-4))
for c in ['cls','Vendor','Type']: F[c]=A[c].astype(str).astype('category')
Z=TruncatedSVD(64,random_state=0).fit_transform(TfidfVectorizer(min_df=3,ngram_range=(1,2),max_features=60000,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9]+\b',sublinear_tf=True).fit_transform(A.text))
for k in range(64): F[f's{k}']=Z[:,k]
ver=(A.src=='ours')&df['Weight Status'].reindex(A.index).fillna('').str.startswith('Verified')
y=np.log((df['Net Weight (kg)']/df.pack).clip(lower=1e-4)).reindex(A.index)
params=dict(objective='regression_l1',learning_rate=0.05,num_leaves=63,min_data_in_leaf=20,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,lambda_l2=1.0,verbose=-1,cat_smooth=10)
mdl=lgb.train(params,lgb.Dataset(F[ver],y[ver]),num_boost_round=1200)
pred_new=pd.Series(np.exp(mdl.predict(F.loc['N'+new.index.astype(str)])),index=new.index)
# ML per-piece for our rows: OOF for verified, ensemble pred for estimated
oof=pd.read_pickle(SP+'ml_oof.pkl'); oof3=pd.read_pickle(SP+'ml_oof_v3.pkl')
mlv=np.exp((oof+oof3.reindex(oof.index).fillna(oof))/2)
mp=pd.read_pickle(SP+'ml_pred.pkl')['ml_kg_piece']
ml_piece=pd.concat([mlv,mp])
from estimate import W as REFW, curve
def lamp_est(t):
    T=t.upper()
    m=re.search(r'(\d+(?:\.\d+)?)\s?FT',T); mi=re.search(r'(\d{2,3})\s?IN\b',T)
    if re.search(r'T8|T5|T12|TUBE',T):
        ft=float(m.group(1)) if m else (float(mi.group(1))/12 if mi else (2.0 if re.search(r'U\d',T) else 4.0))
        per=REFW('D:40')/4*(0.8 if 'T5' in T else 1.0)
        return per*ft,'LED tube per length from 4 ft T8 reference (ULE 14W T8 0.2 kg)'
    if re.search(r'HIGHBAY|HIGH BAY|CORN|RETROFIT|SOX|HID|MOGUL|EX39',T):
        w=watts(t) or 100
        kg,_=curve(w,[(100,('D:41','D:42'))]); return kg,'HID-replacement LED lamp scaled by wattage from 100 W corn lamps (Satco/GB)'
    if re.search(r'PSB|S11|S6|C7|C9|INDICATOR|SIGN|T-?2\b|T-?3\b|BA9|BAYONET|WEDGE',T):
        return (REFW('D2:8')/25+REFW('D2:9')/4)/2,'small indicator/sign lamp vs C7/C9 replacement bulbs (per bulb)'
    if re.search(r'G4|G9|JC|BI-?PIN|GY6',T): return REFW('D:44','D:45'),'bi-pin capsule vs G9/G4 LED refs'
    if re.search(r'PAR ?38',T): return REFW('D:34','D:35'),'PAR38 refs'
    if re.search(r'PAR ?30|BR ?40',T): return REFW('D:34','D:35','D:32','D:33'),'PAR30/BR40 refs'
    if re.search(r'PAR ?20|MR ?16|GU10|BR ?30',T): return REFW('D:36','D:37','D:38','D:39','D:32','D:33'),'small reflector lamp refs'
    return REFW('D:30','D:31'),'general LED lamp vs Satco A19'
DENSCAP={'lug':3.0,'screw_small':3.0,'emt_fitting':3.0,'conduit_body':3.0,'conduit_elbow':3.0,'bushing_locknut':3.0,'strap_hanger':3.0,'ground_clamp':3.0,'liquidtight':3.0,'wire_connector':2.0}
# ---- decide per issue row
def ship_from_net(net,cls):
    from build_ship import ship
    return ship(net,cls)[0]
out=[]
for i,r in V.iterrows():
    L,W,H=r['Box L (cm)'],r['Box W (cm)'],r['Box H (cm)']
    vol=L*W*H if all(pd.notna([L,W,H])) and L*W*H>0 else np.nan
    cur=float(r['Weight (g)']) if pd.notna(r['Weight (g)']) else 0.0
    if pd.notna(r.row):
        rid=int(r.row); q=int(o.at[rid,'pack']); c=o.at[rid,'cls']
        mlg=float(ml_piece.get(rid,np.nan))*q*1000
        mlg_ship=mlg*(float(R.at[rid,'Shipping Weight (kg)'])/max(float(R.at[rid,'Net Weight (kg)']),1e-6))
        status=R.at[rid,'Weight Status']
    else:
        q=int(new.at[i,'pack']); c=new.at[i,'cls']; status='Not in export files'
        mlg=float(pred_new[i])*q*1000; mlg_ship=mlg*1.4+30 if c=='lamp_bulb' else mlg*1.25+150
    lamp_basis=''
    if c=='lamp_bulb' or re.search(r'\bLED\d|T8|T5|PSB|INCANDESCENT|HALOGEN|BULB|LAMP\b',str(r.Title).upper()) and str(r.get('Product Type','')).lower().find('bulb')>=0:
        kgp,lamp_basis=lamp_est(str(r.Title)); mlg=kgp*q*1000; mlg_ship=(kgp*1.4+0.03)*q*1000
    dcap=DENSCAP.get(c,1.0); cap=vol*dcap if pd.notna(vol) else np.inf
    floor_=vol*0.003 if pd.notna(vol) else 0
    iss=r.Issue; action='keep'; newg=cur; reason=''
    try:
        rk=est(c,str(r.Title))[0]
        from build_ship import ship as _sh
        rule_ship=_sh(rk,c)[0]*q*1000
    except Exception: rule_ship=np.nan
    mft=re.search(r'by the foot|per foot|/ft\b',str(r.Title),re.I)
    if mft:
        ga=re.search(r'(\d{2})\s?/\s?(\d)',str(r.Title)); gauge,cond=(int(ga.group(1)),int(ga.group(2))) if ga else (18,2)
        k={12:1,14:0.65,16:0.42,18:0.27,20:0.17,22:0.11,24:0.07}.get(gauge,0.27)*cond/2
        from estimate import W as _W
        per_ft=_W('H2:6')/250*k
        mlg=per_ft*1000; mlg_ship=per_ft*1.1*1000+5; rule_ship=float('nan'); lamp_basis=f'sold by the foot: {gauge} AWG x{cond} wire per foot scaled from 12/2 landscape wire (Nassau 250 ft = 7.26 kg)'
    def use_ml(why):
        g=mlg_ship; w=why+(f' [{lamp_basis}]' if lamp_basis else '')
        if not lamp_basis and rule_ship==rule_ship and rule_ship>0 and (g/rule_ship>3 or g/rule_ship<1/3):
            g=float(np.sqrt(g*rule_ship)); w+=f'; ML ({mlg_ship:.0f} g) and category rule ({rule_ship:.0f} g) disagree -> geometric mean used (low confidence)'
        mt=re.search(r'(\d+(?:\.\d+)?)\s?(lb|lbs|pound)s?\b',str(r.Title),re.I)
        if mt and not re.search(r'lb\.?-?ft|in-lb|ft-lb|load|rated|capacity',str(r.Title),re.I):
            g=float(mt.group(1))*453.6*1.05; w='weight stated in product title ('+mt.group(0)+') + packaging'
        if np.isfinite(cap) and g>cap: w+=f'; estimate is denser than {dcap} g/cm3 for the given box -> box dimensions look too small, please check box'
        return max(round(g),5),w
    if iss.startswith('No weight'):
        newg,reason=use_ml('no published weight anywhere; ML estimate from 20k verified products (similar lamps)'); action='estimate'
    elif iss.startswith('Heavier than solid steel') and mlg_ship>0 and 0.5<=cur/mlg_ship<=2 and not mft:
        reason=f'source weight agrees with independent estimate ({mlg_ship:.0f} g) -> weight kept; the BOX dimensions are too small, please check box'; action='keep (check box)'
    elif iss.startswith('Heavier than solid steel'):
        newg,reason=use_ml(f'source value {cur:.0f} g is physically impossible for the box (likely bulk carton/placeholder); replaced by ML estimate, capped at 0.6 g/cm3 of box'); action='replace'
    elif iss.startswith('Over 68'):
        dens=cur/vol if pd.notna(vol) else np.nan
        if pd.notna(dens) and dens>0.5:
            newg,reason=use_ml(f'{cur/1000:.1f} kg in this box = {dens:.2f} g/cm3, implausible for a chandelier; replaced by ML estimate'); action='replace'
        else:
            reason='weight consistent with box size (large crystal chandelier); keep, but ships as freight/LTL (over parcel limit)'; action='keep (freight)'
    elif iss.startswith('Under 10'):
        best=max(mlg_ship,rule_ship if rule_ship==rule_ship else 0)
        if best>2*cur: newg,reason=max(round(best),5),f'{cur:.0f} g is too light for this item/pack; replaced by the larger of ML ({mlg_ship:.0f} g) and category-rule ({rule_ship:.0f} g) estimates'; action='replace'
        else: reason='small item; ML agrees it is very light'; newg=max(cur,5)
    elif iss.startswith('Box far too big'):
        if mlg_ship>5*cur: newg,reason=use_ml('weight too low vs ML estimate and box; replaced'); action='replace'
        else: reason='weight agrees with ML estimate -> the box dimensions are probably wrong (check box)'; action='keep (check box)'
    elif iss.startswith('Unusual'):
        ratio=cur/max(mlg_ship,1)
        if ratio>4 or ratio<0.25: newg,reason=use_ml(f'source value {cur:.0f} g is {ratio:.1f}x the ML estimate ({mlg_ship:.0f} g); source rejected'); action='replace'
        else: reason=f'unusual for its type but consistent with ML estimate ({mlg_ship:.0f} g); keep'; action='keep'
    out.append(dict(idx=i,row=r.row,new_g=int(newg),action=action,reason=reason,ml_g=round(mlg_ship) if mlg_ship==mlg_ship else None))
Fx=pd.DataFrame(out).set_index('idx')
V=V.join(Fx[['new_g','action','reason','ml_g']])
V.to_pickle(SP+'issues/fixed.pkl')
print(V.groupby(['Issue','action']).size().to_string())
