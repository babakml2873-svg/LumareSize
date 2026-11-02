import sys, re, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/work')
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
t=df.text
F=pd.DataFrame(index=df.index)
for name,fn in [('w',watts),('L',length_ft),('inch',inches),('ts',trade_size),('poles',poles),('amps',amps),('lights',lights),('gang',gang)]:
    F[name]=t.map(fn).astype(float)
F['pack']=df.pack.astype(float)
price=pd.to_numeric(df['Variant Price'],errors='coerce')
F['logprice_piece']=np.log1p(price/df.pack).where(price>0)
F['log_model']=np.log(df.kg_each.clip(lower=1e-4))
for c in ['cls','Vendor','Type']:
    F[c]=df[c].astype('category')
tf=TfidfVectorizer(min_df=3,ngram_range=(1,2),max_features=60000,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z0-9]+\b')
X=tf.fit_transform(t)
svd=TruncatedSVD(64,random_state=0); Z=svd.fit_transform(X)
for k in range(Z.shape[1]): F[f'svd{k}']=Z[:,k]
ver=df['Weight Status'].fillna('').str.startswith('Verified')
y=np.log((df['Net Weight (kg)']/df.pack).clip(lower=1e-4))
Xv,yv,gv=F[ver],y[ver],df.Handle[ver]
params=dict(objective='regression_l1',learning_rate=0.05,num_leaves=63,min_data_in_leaf=20,feature_fraction=0.8,bagging_fraction=0.8,bagging_freq=1,lambda_l2=1.0,verbose=-1,cat_smooth=10)
oof=np.zeros(len(Xv)); 
for tr,te in GroupKFold(5).split(Xv,yv,gv):
    m=lgb.train(params,lgb.Dataset(Xv.iloc[tr],yv.iloc[tr]),num_boost_round=1500)
    oof[te]=m.predict(Xv.iloc[te])
err_ml=np.abs(oof-yv.values); err_mod=np.abs(Xv.log_model.values-yv.values)
def rep(e,name):
    r=np.exp(e)
    print(f'{name}: median factor-off {np.median(r):.2f}x | within ±25%: {(r<=1.25).mean():.1%} | within ±50%: {(r<=1.5).mean():.1%} | within 2x: {(r<=2).mean():.1%}')
rep(err_mod,'current rule model (held-out)'); rep(err_ml,'ML model (5-fold, grouped by product)')
res=pd.DataFrame({'vendor':df.Vendor[ver].values,'cls':df.cls[ver].values,'ml':np.exp(err_ml),'rule':np.exp(err_mod)})
print(res.groupby('vendor')[['ml','rule']].median().round(2).sort_values('ml').to_string())
# brand-holdout test: how well does it do on a vendor it never saw (like ELCO/Nora situation)
vb=df.Vendor[ver].values
for hold in ['Nora Lighting','Westgate','Leviton','Kuzco','Focus Industries']:
    tr=vb!=hold; te=vb==hold
    if te.sum()<50: continue
    m=lgb.train(params,lgb.Dataset(Xv[tr],yv[tr]),num_boost_round=1500)
    e=np.abs(m.predict(Xv[te])-yv[te].values); r=np.exp(e); r2=np.exp(np.abs(Xv.log_model.values[te]-yv[te].values))
    print(f'brand-holdout {hold:18s} n={te.sum():5d} ML median {np.median(r):.2f}x within±50% {(r<=1.5).mean():.0%} | rule median {np.median(r2):.2f}x within±50% {(r2<=1.5).mean():.0%}')
# quantile models for intervals, final fit on all verified
final=lgb.train(params,lgb.Dataset(Xv,yv),num_boost_round=1500)
q={}
for a in (0.1,0.9):
    q[a]=lgb.train(dict(params,objective='quantile',alpha=a),lgb.Dataset(Xv,yv),num_boost_round=800)
U=F[~ver]
pred=pd.DataFrame({'ml_kg_piece':np.exp(final.predict(U)),'lo':np.exp(q[0.1].predict(U)),'hi':np.exp(q[0.9].predict(U))},index=U.index)
pred.to_pickle(SP+'ml_pred.pkl')
pd.Series(oof,index=Xv.index).to_pickle(SP+'ml_oof.pkl')
print('predicted rows',len(pred)); print(pred.describe().round(3))
