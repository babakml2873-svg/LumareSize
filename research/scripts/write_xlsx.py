import sys, pandas as pd, json, re
sys.path.insert(0,'/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/work')
from estimate import REF
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
OUT=sys.argv[1]
f=pd.read_pickle(SP+'final.pkl'); R=pd.read_pickle(SP+'recs.pkl')
prod=pd.read_pickle(SP+'prod.pkl')
cols=['Net Weight (kg)','Pack Qty (from title)','Net Weight per Piece (kg)','Shipping Weight (kg)','Weight Status','Source Type','Reference Brand','Reference Model','Reference Weight (kg)','Source URL','Confidence','Research Notes']
orig=[c for c in f.columns if c not in cols+['_f','_cls','_vendor']]
W=pd.ExcelWriter(OUT,engine='xlsxwriter',engine_kwargs={'options':{'strings_to_urls':False,'strings_to_formulas':False,'nan_inf_to_errors':True}})
wb=W.book
hdr=wb.add_format({'bold':True,'bg_color':'#1F4E78','font_color':'white','text_wrap':True,'valign':'top'})
hdr2=wb.add_format({'bold':True,'bg_color':'#C65911','font_color':'white','text_wrap':True,'valign':'top'})
bold=wb.add_format({'bold':True}); title=wb.add_format({'bold':True,'font_size':14})
wrap=wb.add_format({'text_wrap':True,'valign':'top'})
# ---- Summary
var=R
n_prod=prod.shape[0]
s=wb.add_worksheet('Summary'); W.sheets['Summary']=s
rows=[('Product Weight Research – Summary',None),
('Input files','products_export_1..4 (Shopify product export, 4 CSVs)'),
('Total input rows',len(f)),
('Product handles (unique products)',n_prod),
('Variant rows (each SKU/variant = one sellable item)',len(var)),
('Image-only rows (no variant; weight N/A)',int((f['Weight Status']=='N/A').sum())),
('Variant rows with a weight',int(var['Net Weight (kg)'].notna().sum())),
('Coverage of variant rows', f"{var['Net Weight (kg)'].notna().mean():.1%}"),
('',None),
('Weight evidence breakdown (variant rows)',None),
('Verified – Manufacturer (exact part no.)',int(((var['Weight Status']=='Verified')&(var['Source Type']=='Manufacturer')).sum())),
('Verified – Manufacturer (same model, other finish/CCT)',int(((var['Weight Status']=='Verified (finish variant)')&(var['Source Type']=='Manufacturer')).sum())),
('Verified – Distributor/Retailer (exact part no.)',int(((var['Weight Status']=='Verified')&(var['Source Type']!='Manufacturer')).sum())),
('Verified – Distributor/Retailer (same model, other finish/CCT)',int(((var['Weight Status']=='Verified (finish variant)')&(var['Source Type']!='Manufacturer')).sum())),
('Estimated – ML model / comparable product',int((var['Weight Status']=='Estimated').sum())),
('',None),
('Confidence (variant rows)',None),
('High',int((var.Confidence=='High').sum())),('Medium',int((var.Confidence=='Medium').sum())),('Low',int((var.Confidence=='Low').sum())),
('',None),
('Reference library size',f'{len(REF)} published weights for named comparable models (see "Reference Library" sheet)'),
('',None),
('METHOD & LIMITATIONS',None),
('1','Priority 1/2 – exact part number: weights were read directly from manufacturer sites, manufacturer data feeds and spec-sheet PDFs, or from distributor/retailer product pages and catalog APIs, matched on the exact part number (Weight Status = Verified). "Verified (finish variant)" = same model, different finish/colour/CCT suffix.'),
('2b','Estimated rows: weight predicted by a LightGBM model trained on all verified weights (median error 1.20x on unseen products, 75% within ±50%); the 80% prediction interval is in Research Notes. Reference columns show the nearest comparable product with a published weight.'),
('2','Priority 3 – comparable product: rows without a published weight are linked to the nearest product of the same category (same brand preferred) whose weight WAS read from a source, scaled by size attributes parsed from the title (aperture, wattage, length, trade size, poles, amps, light count, gang, pack qty). The comparable product, its weight and URL are given per row.'),
('3','Sites protected by bot checks (403/Cloudflare/CAPTCHA) were not accessed or circumvented; robots.txt crawl-delays were respected. Distributor values that are obvious placeholders (one value repeated across many different items) were discarded.'),
('4','Never used: Lumera Electric (site, CDN, PDFs), eBay/marketplaces, and the weights already present in the export (Variant Grams).'),
('5','Pack items: "Net Weight (kg)" is the sellable unit (whole pack). "Net Weight per Piece (kg)" is shown when the title states a pack quantity.'),
('6','Shipping weight: taken from the source when it is a gross/shipping weight; otherwise net + documented packaging allowance by category.'),
('7','Known caveat: about 900 Satco/Nuvo/Arabela weights came from lightingnewyork.com pages located through its /search path, which that site\'s robots.txt disallows; they are kept but flagged in Research Notes so you can exclude them.'),
]
s.set_column(0,0,48); s.set_column(1,1,120)
for i,(a,b_) in enumerate(rows):
    s.write(i,0,a,title if i==0 else (bold if b_ is None else None))
    if b_ is not None: s.write(i,1,b_,wrap)
# ---- category summary
cat=var.groupby('_cls').agg(rows=('Net Weight (kg)','size'),median_net_kg=('Net Weight (kg)','median'),min_kg=('Net Weight (kg)','min'),max_kg=('Net Weight (kg)','max'),low_conf=('Confidence',lambda x:(x=='Low').sum())).reset_index().rename(columns={'_cls':'category'})
cat.to_excel(W,sheet_name='Category Summary',index=False)
W.sheets['Category Summary'].set_column(0,0,24); W.sheets['Category Summary'].set_column(1,5,14)
# ---- QC sheet: low confidence + flags
q=f[f['Confidence'].eq('Low') | f['Research Notes'].fillna('').str.contains('QC:')].copy()
q['QC Reason']=q['Research Notes'].str.extract(r'(QC:[^;]+)')[0].fillna('Low confidence: generic size/subtype not stated or category-level comparable only')
q['Category']=q['_cls']
qq=q[['Handle','Title','Vendor','Variant SKU','Category','Net Weight (kg)','Shipping Weight (kg)','Confidence','QC Reason','Research Notes']]
qq.to_excel(W,sheet_name='QC - Low Confidence',index=False)
ws=W.sheets['QC - Low Confidence']; ws.set_column(0,3,22); ws.set_column(4,7,12); ws.set_column(8,9,60); ws.freeze_panes(1,0); ws.autofilter(0,0,len(qq),len(qq.columns)-1)
# ---- reference library
lib=pd.DataFrame([{'Ref ID':k,'Category':r.get('category'),'Size point':r.get('size_point'),'Brand':r.get('brand'),'Model':r.get('model'),'Description':r.get('product_desc'),
   'Published weight':r.get('weight_value'),'Unit':r.get('weight_unit'),'Weight (kg)':round(r['weight_kg'],4),'Pack qty':r.get('pack_qty') or 1,'Weight type':r.get('weight_type'),
   'Source type':r.get('source_type'),'URL':r.get('url'),'Evidence (search result)':r.get('evidence'),'Notes':r.get('note')} for k,r in REF.items()])
lib.to_excel(W,sheet_name='Reference Library',index=False)
ws=W.sheets['Reference Library']; ws.set_column(0,4,16); ws.set_column(5,5,45); ws.set_column(12,14,50); ws.freeze_panes(1,0)
# ---- data sheets
for fn,g in sorted(f.groupby('_f'),key=lambda x: re.search(r'export_(\d)',x[0]).group(1)):
    name=re.search(r'products_export_\d',fn).group(0)
    g=g[orig+cols]
    g.to_excel(W,sheet_name=name,index=False)
    ws=W.sheets[name]
    for j,c in enumerate(g.columns):
        ws.write(0,j,c,hdr2 if c in cols else hdr)
    ws.freeze_panes(1,2)
    ws.set_column(0,len(orig)-1,14)
    ws.set_column(len(orig),len(orig)+1,12); ws.set_column(len(orig)+2,len(orig)+8,18); ws.set_column(len(orig)+9,len(orig)+9,80)
    ws.autofilter(0,0,len(g),len(g.columns)-1)
    print(name,len(g))
W.close()
