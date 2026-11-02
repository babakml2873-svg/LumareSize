import sys, numpy as np, pandas as pd
sys.path.insert(0,'.')
from match import build_lib, run
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
lib=build_lib()
pn=lib.pack_note.fillna('').str.lower()
bad=pn.str.contains(r'pack|box|case|bundle|carton|per f|/ft|foot|feet|reel|spool|\bctn\b') | ((lib.source.str.contains('lightingsupply'))&(lib.brand.astype(str).str.contains('Metallics')))
lib=lib[~bad].reset_index(drop=True)
print('library usable',len(lib))
lib.to_pickle(SP+'lib_clean.pkl')
R=pd.read_pickle(SP+'recs.pkl'); v=pd.read_pickle(SP+'var.pkl'); o=pd.read_pickle(SP+'est.pkl')
df=v.join(o[['pack','cls']]).join(R[['Net Weight (kg)','Weight Status']])
df['title']=(df.Title.fillna('')+' '+df['Option1 Value'].fillna('').astype(str).str.replace('Default Title',''))
df=df.rename(columns={'Vendor':'vendor','Variant SKU':'sku'})
ver=df['Weight Status'].str.startswith('Verified')
# validation: exclude library rows of the same brand+part (handled in run) – also exclude same brand entirely to mimic "other brand" situation
V=df[ver].copy()
V['true']=V['Net Weight (kg)']/V.pack
m=run(V,lib)
oof=pd.read_pickle(SP+'ml_oof.pkl')
J=V.join(m,how='inner').join(oof.rename('ml_log'))
J['err_match']=np.exp(np.abs(np.log(J.match_kg/J.true)))
J['err_ml']=np.exp(np.abs(J.ml_log-np.log(J.true)))
J['bin']=pd.cut(J.score,[-9,0.2,0.3,0.4,0.5,0.6,0.7,0.8,1.01])
print(J.groupby('bin').agg(n=('true','size'),match_med=('err_match','median'),ml_med=('err_ml','median'),match_in50=('err_match',lambda e:(e<=1.5).mean()),ml_in50=('err_ml',lambda e:(e<=1.5).mean())).round(2).to_string())
J[['score','sim','match_kg','true','err_match','err_ml','cls']].to_pickle(SP+'match_val.pkl')
