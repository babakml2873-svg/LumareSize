"""Final deliverable: shipping weights in grams.
 - Shipping_Weights_grams.csv / .xlsx : one row per variant (SKU) with shipping + net grams and status
 - shopify_import/products_export_N_with_weights.csv : original exports with 'Variant Grams' = shipping grams
"""
import sys, re, os, glob, numpy as np, pandas as pd
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
OUT=sys.argv[1]; os.makedirs(OUT+'/shopify_import',exist_ok=True)
f=pd.read_pickle(SP+'final.pkl'); R=pd.read_pickle(SP+'recs.pkl')
def g(x):
    if x is None or pd.isna(x): return None
    return int(max(1,round(float(x)*1000)))
R['Shipping Weight (g)']=R['Shipping Weight (kg)'].map(g)
R['Net Weight (g)']=R['Net Weight (kg)'].map(g)
cols=['Handle','Title','Vendor','Variant SKU','Option1 Value','Option2 Value','Option3 Value']
base=f.loc[R.index,cols+['_f']].copy()
for c in ['Title','Vendor']: base[c]=f.groupby('Handle')[c].transform('first').loc[R.index]
T=base.join(R[['Shipping Weight (g)','Net Weight (g)','Pack Qty (from title)','Weight Status','Source Type','Confidence','Source URL']])
T['File']=T._f.str.extract(r'(products_export_\d)')[0]; T=T.drop(columns='_f')
T=T.rename(columns={'Source Type':'Basis','Source URL':'Source / reference URL'})
T.to_csv(OUT+'/Shipping_Weights_grams.csv',index=False)
with pd.ExcelWriter(OUT+'/Shipping_Weights_grams.xlsx',engine='xlsxwriter',engine_kwargs={'options':{'strings_to_urls':False}}) as W:
    T.to_excel(W,sheet_name='Shipping weights (g)',index=False)
    ws=W.sheets['Shipping weights (g)']; ws.freeze_panes(1,4); ws.autofilter(0,0,len(T),len(T.columns)-1)
    ws.set_column(0,0,30); ws.set_column(1,1,45); ws.set_column(2,6,16); ws.set_column(7,8,14); ws.set_column(9,12,18)
# Shopify re-import copies: only Variant Grams changed
src=sorted(glob.glob(SP+'in/*/*.csv'),key=lambda s:s[-5])
for fn in src:
    name=re.search(r'(products_export_\d)',fn).group(1)
    d=pd.read_csv(fn,dtype=str,keep_default_na=False)
    sub=f[f._f.str.contains(name)]
    assert len(sub)==len(d)
    grams=R['Shipping Weight (g)'].reindex(sub.index).values
    newg=[str(int(x)) if x is not None and not pd.isna(x) else old for x,old in zip(grams,d['Variant Grams'])]
    d['Variant Grams']=newg
    d.to_csv(OUT+f'/shopify_import/{name}_with_shipping_grams.csv',index=False)
    print(name,len(d),'updated',sum(1 for x in grams if x is not None and not pd.isna(x)))
print(T['Weight Status'].value_counts().to_dict()); print(T['Shipping Weight (g)'].describe().round(0).to_dict())
