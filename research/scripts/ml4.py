import sys, re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
from fractions import Fraction
from features import watts, length_ft, inches, trade_size, poles, amps, lights, gang
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.model_selection import GroupKFold
import lightgbm as lgb
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
R=pd.read_pickle(SP+'recs.pkl'); v=pd.read_pickle(SP+'var.pkl'); o=pd.read_pickle(SP+'est.pkl')
p=pd.read_pickle(SP+'prod.pkl').set_index('Handle')
df=v.join(o[['kg_each','pack','cls']]).join(R[['Net Weight (kg)','Weight Status']])
df['Type']=df['Type'].fillna('')
df['text']=(df.Title.fillna('')+' '+df[['Option1 Value','Option2 Value','Option3 Value']].fillna('').astype(str).agg(' '.join,axis=1)).str.replace('Default Title','')
# ---------- dimensions from description (specifications) ----------
body=df.Handle.map(p['Body (HTML)']).fillna('').str.replace('<[^>]+>',' ',regex=True).str.replace(r'\s+',' ',regex=True)
def num(s):
    s=s.replace('”','').replace('"','').strip()
    try:
        if '-' in s and '/' in s: a,b=s.split('-',1); return float(a)+float(Fraction(b))
        if '/' in s: return float(Fraction(s))
        return float(s)
    except Exception: return np.nan
NUM=r'(\d+(?:\.\d+)?(?:-\d+/\d+)?|\d+/\d+)'
def dims(t):
    d={'dL':np.nan,'dW':np.nan,'dH':np.nan,'dD':np.nan,'dExt':np.nan,'nbulb':np.nan}
    m=re.search(r'(?<!Canopy )Dimensions:?\s*((?:[LWHD]\s?'+NUM+r'["”]?\s*(?:x\s*)?){1,3})',t)
    if m:
        for k,val in re.findall(r'([LWHD])\s?'+NUM,m.group(1)): d['d'+k]=num(val)
    for k,lab in [('dL','Length'),('dW','Width'),('dH','Height'),('dD','Diameter'),('dExt','Extension')]:
        if np.isnan(d[k]):
            mm=re.search(r'(?:Product |Fixture )?'+lab+r':?\s*'+NUM+r'\s*(?:"|”|in\b)?',t)
            if mm and not re.search(r'(Hang|Minimum|Max)',t[max(0,mm.start()-12):mm.start()]): d[k]=num(mm.group(1))
    mm=re.search(r'Number of Bulbs:?\s*(\d+)',t)
    if mm: d['nbulb']=float(mm.group(1))
    return d
D=pd.DataFrame([dims(t) for t in body],index=df.index)
for c in D: D.loc[(D[c]<=0)|(D[c]>300),c]=np.nan
try:
    G=pd.read_csv(SP+'results/dims_g10.csv').drop_duplicates('row_id').set_index('row_id')
    for src,dst in [('length_in','dL'),('width_in','dW'),('height_in','dH'),('diameter_in','dD')]:
        val=pd.to_numeric(G[src],errors='coerce').reindex(D.index)
        D[dst]=D[dst].fillna(val.where((val>0)&(val<300)))
    print('dims after spec-sheet merge',D[['dL','dW','dH','dD']].notna().any(axis=1).sum())
except Exception as ex: print('dims_g10 not used',ex)
print('rows with any dimension',D[['dL','dW','dH','dD']].notna().any(axis=1).sum())
a=D[['dL','dW','dD']].max(axis=1); h=D.dH
D['dmax']=D[['dL','dW','dH','dD']].max(axis=1)
D['vol']=np.where(D.dD.notna(),D.dD**2*h.fillna(D.dD*0.5),D.dL*D.dW.fillna(D.dL*0.3)*h.fillna(2))
D['lvol']=np.log1p(D.vol)
# ---------- base features ----------
t=df.text
F=pd.DataFrame(index=df.index)
for n,fn in [('w',watts),('L',length_ft),('inch',inches),('ts',trade_size),('poles',poles),('amps',amps),('lights',lights),('gang',gang)]:
    F[n]=t.map(fn).astype(float)
F=F.join(D[['dL','dW','dH','dD','dExt','nbulb','dmax','lvol']])
F['pack']=df.pack.astype(float)
price=pd.to_numeric(df['Variant Price'],errors='coerce')
F['logprice']=np.log1p(price/df.pack).where(price>0)
F['log_model']=np.log(df.kg_each.clip(lower=1e-4))
for c in ['cls','Vendor','Type']: F[c]=df[c].astype(str).astype('category')
tf=TfidfVectorizer(min_df=3,ngram_range=(1,2),max_features=60000,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9]+\b',sublinear_tf=True)
Z=TruncatedSVD(64,random_state=0).fit_transform(tf.fit_transform(t))
for k in range(Z.shape[1]): F[f's{k}']=Z[:,k]
ver=df['Weight Status'].fillna('').str.startswith('Verified').values
y=np.log((df['Net Weight (kg)']/df.pack).clip(lower=1e-4)).values
# ---------- family keys ----------
skun=df['Variant SKU'].astype(str).str.upper().str.replace(r'[^A-Z0-9]','',regex=True)
K={'k_sku5':df.Vendor.astype(str)+'|'+skun.str[:5],'k_sku7':df.Vendor.astype(str)+'|'+skun.str[:7],'k_vcls':df.Vendor.astype(str)+'|'+df.cls.astype(str),'k_vtype':df.Vendor.astype(str)+'|'+df.Type.astype(str),'k_handle':df.Handle.astype(str)}
def fam_feats(train_mask):
    out=pd.DataFrame(index=df.index)
    for k,key in K.items():
        s=pd.Series(np.where(train_mask,y,np.nan),index=df.index)
        g=s.groupby(key)
        med=g.transform('median'); cnt=g.transform('count')
        # leave-one-out for training rows: approximate by excluding self when count>1
        out[k+'_med']=med; out[k+'_n']=cnt
        out[k+'_rel']=med-F.log_model
    return out
params=dict(objective='regression_l1',learning_rate=0.05,num_leaves=63,min_data_in_leaf=20,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,lambda_l2=1.0,verbose=-1,cat_smooth=10)
iv=np.where(ver)[0]; groups=df.Handle.values[iv]
oof=np.zeros(len(iv)); oof_nofam=np.zeros(len(iv))
for tr,te in GroupKFold(5).split(iv,groups=groups):
    trmask=np.zeros(len(df),bool); trmask[iv[tr]]=True
    # inner LOO-ish: for training rows compute family stats from OTHER training folds (2-way split) to avoid self-leak
    half=np.zeros(len(df),bool); rng=np.random.RandomState(0)
    trA=iv[tr][rng.rand(len(tr))<0.5]; half[trA]=True
    FA=fam_feats(half); FB=fam_feats(trmask & ~half)
    Ftr=F.copy(); fam_tr=FA.copy(); fam_tr.loc[df.index[trA]]=FB.loc[df.index[trA]].values
    Xtr=pd.concat([F.iloc[iv[tr]],fam_tr.iloc[iv[tr]]],axis=1)
    Xte=pd.concat([F.iloc[iv[te]],fam_feats(trmask).iloc[iv[te]]],axis=1)
    m=lgb.train(params,lgb.Dataset(Xtr,y[iv[tr]]),num_boost_round=1200); oof[te]=m.predict(Xte)
e=np.exp(np.abs(oof-y[iv]))
old=pd.read_pickle(SP+'ml_oof.pkl').reindex(df.index[iv]).values
eo=np.exp(np.abs(old-y[iv]))
print(f'OLD: median {np.nanmedian(eo):.3f}x ±25% {(eo<=1.25).mean():.1%} ±50% {(eo<=1.5).mean():.1%} 2x {(eo<=2).mean():.1%}')
print(f'NEW (dims+family): median {np.median(e):.3f}x ±25% {(e<=1.25).mean():.1%} ±50% {(e<=1.5).mean():.1%} 2x {(e<=2).mean():.1%}')
r=pd.DataFrame({'v':df.Vendor.values[iv],'new':e,'old':eo}).groupby('v')[['old','new']].median().round(2)
print(r.loc[[x for x in ['ELCO Lighting','Nora Lighting','Orbit','Westgate','Leviton','Lutron','Dottie','Morris','EnVision','Focus Industries'] if x in r.index]].to_string())
# ---------- final fit & predict ----------
allmask=np.zeros(len(df),bool); allmask[iv]=True
half=np.zeros(len(df),bool); rng=np.random.RandomState(1); hA=iv[rng.rand(len(iv))<0.5]; half[hA]=True
FA=fam_feats(half); FB=fam_feats(allmask&~half); fam_tr=FA.copy(); fam_tr.loc[df.index[hA]]=FB.loc[df.index[hA]].values
Xtr=pd.concat([F.iloc[iv],fam_tr.iloc[iv]],axis=1)
iu=np.where(~ver)[0]; Xu=pd.concat([F.iloc[iu],fam_feats(allmask).iloc[iu]],axis=1)
final=lgb.train(params,lgb.Dataset(Xtr,y[iv]),num_boost_round=1200)
q={a:lgb.train(dict(params,objective='quantile',alpha=a),lgb.Dataset(Xtr,y[iv]),num_boost_round=700) for a in (0.1,0.9)}
P=pd.DataFrame({'ml_kg_piece':np.exp(final.predict(Xu)),'lo':np.exp(q[0.1].predict(Xu)),'hi':np.exp(q[0.9].predict(Xu))},index=df.index[iu])
# calibrate interval width -> confidence using OOF residual by interval? keep simple
P.to_pickle(SP+'ml_pred_v4.pkl'); pd.Series(oof,index=df.index[iv]).to_pickle(SP+'ml_oof_v4.pkl'); D.to_pickle(SP+'dims.pkl')
print('pred',len(P))
