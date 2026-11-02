import sys, numpy as np, pandas as pd
sys.path.insert(0,'.')
from match import run
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
lib=pd.read_pickle(SP+'lib_clean.pkl')
R=pd.read_pickle(SP+'recs.pkl'); v=pd.read_pickle(SP+'var.pkl'); o=pd.read_pickle(SP+'est.pkl')
df=v.join(o[['pack']]).join(R[['Weight Status']])
df['title']=(df.Title.fillna('')+' '+df['Option1 Value'].fillna('').astype(str).str.replace('Default Title',''))
df=df.rename(columns={'Vendor':'vendor','Variant SKU':'sku'})
U=df[~df['Weight Status'].str.startswith('Verified')]
m=run(U,lib)
m=m[m.score>0.7]
m=m.join(lib[['source','brand','mpn','title','url','weight_kg','weight_type']],on='lib_row')
m.to_pickle(SP+'strong_matches.pkl')
print('strong matches',len(m)); print(m.source.value_counts().head(8).to_dict())
