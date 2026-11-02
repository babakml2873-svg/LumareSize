import sys, re, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
from features import watts, length_ft, inches, trade_size, poles, amps, lights, gang
from classify import classify
from estimate import est
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.model_selection import GroupKFold
import lightgbm as lgb
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
R=pd.read_pickle(SP+'recs.pkl'); v=pd.read_pickle(SP+'var.pkl'); o=pd.read_pickle(SP+'est.pkl')
df=v.join(o[['kg_each','pack','cls']]).join(R[['Net Weight (kg)','Weight Status']])
df['Type']=df['Type'].fillna('')
df['text']=(df.Title.fillna('')+' '+df[['Option1 Value','Option2 Value','Option3 Value']].fillna('').astype(str).agg(' '.join,axis=1)).str.replace('Default Title','')
df['price']=pd.to_numeric(df['Variant Price'],errors='coerce')/df.pack
df['src']='ours'
lib=pd.read_pickle(SP+'lib_clean.pkl')
lib=lib[(lib.weight_kg>0.002)&(lib.weight_kg<500)].copy()
cat=lib.category_path.fillna('').astype(str)
lib['Type']=cat.str.split('/').str[-1].str.strip()
cls=[]; kg=[]
for t,ty,c in zip(lib.title.astype(str),lib.Type,cat):
    try: k,_=classify(ty,t,c.replace('/',' '))
    except Exception: k='misc'
    cls.append(k)
    try: kg.append(est(k,t)[0])
    except Exception: kg.append(np.nan)
lib['cls']=cls; lib['kg_each']=kg
L=pd.DataFrame({'Vendor':lib.brand.astype(str),'Type':lib.Type,'text':lib.title.astype(str)+' '+cat,'kg_each':lib.kg_each,'pack':1,'cls':lib.cls,'price':np.nan,'src':'lib','y':np.log(lib.weight_kg.values),'grp':'L'+lib.index.astype(str)})
ver=df['Weight Status'].fillna('').str.startswith('Verified')
O=df[['Vendor','Type','text','kg_each','pack','cls','price','src']].copy()
O['y']=np.where(ver,np.log((df['Net Weight (kg)']/df.pack).clip(lower=1e-4)),np.nan); O['grp']=df.Handle
A=pd.concat([O,L],ignore_index=True); A['text']=A.text.fillna('').astype(str)
F=pd.DataFrame(index=A.index)
for n,fn in [('w',watts),('L',length_ft),('inch',inches),('ts',trade_size),('poles',poles),('amps',amps),('lights',lights),('gang',gang)]:
    F[n]=A.text.map(fn).astype(float)
F['pack']=A.pack.astype(float); F['logprice']=np.log1p(A.price); F['log_model']=np.log(A.kg_each.astype(float).clip(lower=1e-4)); F['is_lib']=(A.src=='lib').astype(int)
for c in ['cls','Vendor','Type']: F[c]=A[c].astype(str).astype('category')
tf=TfidfVectorizer(min_df=3,ngram_range=(1,2),max_features=80000,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9]+\b',sublinear_tf=True)
Z=TruncatedSVD(96,random_state=0).fit_transform(tf.fit_transform(A.text))
for k in range(Z.shape[1]): F[f's{k}']=Z[:,k]
params=dict(objective='regression_l1',learning_rate=0.05,num_leaves=127,min_data_in_leaf=20,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,lambda_l2=1.0,verbose=-1,cat_smooth=10,max_cat_to_onehot=8)
iv=np.where((A.src=='ours')&A.y.notna())[0]; il=np.where(A.src=='lib')[0]
oof=np.zeros(len(iv)); g=A.grp.values[iv]
for tr,te in GroupKFold(3).split(iv,groups=g):
    tri=np.concatenate([iv[tr],il])
    m=lgb.train(params,lgb.Dataset(F.iloc[tri],A.y.iloc[tri]),num_boost_round=1000)
    oof[te]=m.predict(F.iloc[iv[te]])
e=np.exp(np.abs(oof-A.y.values[iv]))
old=pd.read_pickle(SP+'ml_oof.pkl'); yo=np.log((df['Net Weight (kg)']/df.pack).clip(lower=1e-4))
eo=np.exp(np.abs(old.values-yo.loc[old.index].values))
print(f'OLD ML: median {np.median(eo):.2f}x  ±50% {(eo<=1.5).mean():.1%}  2x {(eo<=2).mean():.1%}')
print(f'NEW ML (+library {len(il)}): median {np.median(e):.2f}x  ±50% {(e<=1.5).mean():.1%}  2x {(e<=2).mean():.1%}')
vend=A.Vendor.values[iv]
r=pd.DataFrame({'v':vend,'new':e}).groupby('v').new.median().round(2)
print(r.loc[[x for x in ['ELCO Lighting','Nora Lighting','Orbit','Westgate','Leviton','Lutron','Dottie','Morris','EnVision'] if x in r.index]].to_dict())
# brand holdout
for hold in ['Nora Lighting','Westgate']:
    te=iv[vend==hold]; tr=np.concatenate([iv[vend!=hold],il])
    m=lgb.train(params,lgb.Dataset(F.iloc[tr],A.y.iloc[tr]),num_boost_round=1000)
    ee=np.exp(np.abs(m.predict(F.iloc[te])-A.y.values[te]))
    print(f'holdout {hold:16s} median {np.median(ee):.2f}x ±50% {(ee<=1.5).mean():.0%}')
final=lgb.train(params,lgb.Dataset(F.iloc[np.concatenate([iv,il])],A.y.iloc[np.concatenate([iv,il])]),num_boost_round=1000)
qs={a:lgb.train(dict(params,objective='quantile',alpha=a),lgb.Dataset(F.iloc[np.concatenate([iv,il])],A.y.iloc[np.concatenate([iv,il])]),num_boost_round=600) for a in (0.1,0.9)}
iu=np.where((A.src=='ours')&A.y.isna())[0]
P=pd.DataFrame({'ml_kg_piece':np.exp(final.predict(F.iloc[iu])),'lo':np.exp(qs[0.1].predict(F.iloc[iu])),'hi':np.exp(qs[0.9].predict(F.iloc[iu]))},index=df.index[iu])
P.to_pickle(SP+'ml_pred_v2.pkl'); pd.Series(oof,index=df.index[iv]).to_pickle(SP+'ml_oof_v2.pkl')
print('pred rows',len(P))
