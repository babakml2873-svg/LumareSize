"""Match our products to the most similar library product (any brand) and take its weight.
Validates on our verified rows (excluding same part number) and compares against the ML model."""
import sys, re, numpy as np, pandas as pd
sys.path.insert(0,'/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/work')
from features import watts, length_ft, inches, trade_size, poles, amps, lights, gang
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
LIB=sys.argv[1] if len(sys.argv)>1 else SP+'library/comparables.csv'

STOP=r'\b(lighting|electric(al)?|industries|inc|llc|co|corp|the|and|with|for|in|of|by|w/|finish|series|new|pack|case|per|each|ea|pk|pc|pcs)\b'
def clean(t, brand=''):
    t=str(t)
    if brand: t=re.sub(re.escape(str(brand)),' ',t,flags=re.I)
    t=re.sub(r'\b[A-Z0-9]*\d[A-Z0-9\-/\.]{4,}\b',' ',t)   # drop model/part codes
    t=t.lower()
    t=re.sub(STOP,' ',t)
    t=re.sub(r'(\d+(?:\.\d+)?)\s?(w|watt)s?\b',r'\1w',t)
    t=re.sub(r'(\d+)\s?(in|inch|")\b',r'\1in',t)
    t=re.sub(r'[^a-z0-9\. ]',' ',t)
    return re.sub(r'\s+',' ',t).strip()
FE=[('w',watts),('L',length_ft),('inch',inches),('ts',trade_size),('poles',poles),('amps',amps),('lights',lights),('gang',gang)]
def feats(titles):
    return pd.DataFrame({n:[f(str(t)) for t in titles] for n,f in FE})
def compat(a,b):
    """penalty for attribute mismatch (0 good, larger worse); also returns scale factor for length"""
    pen=0.0; scale=1.0
    for n in ['inch','ts','poles','lights','gang']:
        x,y=a[n],b[n]
        if pd.notna(x) and pd.notna(y) and x!=y: pen+=0.35
        elif pd.notna(x)!=pd.notna(y): pen+=0.05
    for n,tol in [('w',0.35),('amps',0.3)]:
        x,y=a[n],b[n]
        if pd.notna(x) and pd.notna(y) and x>0 and y>0:
            r=max(x,y)/min(x,y)
            if r>1+tol: pen+=min(0.5,0.15*np.log(r)/np.log(1+tol))
    x,y=a['L'],b['L']
    if pd.notna(x) and pd.notna(y) and x>0 and y>0: scale=x/y
    return pen,scale

def build_lib():
    lib=pd.read_csv(LIB)
    lib=lib[pd.to_numeric(lib.weight_kg,errors='coerce')>0].copy()
    lib['weight_kg']=lib.weight_kg.astype(float)
    lib['ctext']=[clean(f"{t} {c}",b) for t,c,b in zip(lib.title,lib.category_path.fillna(''),lib.brand.fillna(''))]
    lib=lib[lib.ctext.str.len()>3].reset_index(drop=True)
    lib['mpn_n']=lib.mpn.astype(str).str.upper().str.replace(r'[^A-Z0-9]','',regex=True)
    return lib

def run(targets, lib, k=8):
    """targets: DataFrame with title, vendor, sku; returns best match per target"""
    vec=TfidfVectorizer(ngram_range=(1,2),min_df=2,sublinear_tf=True)
    Xl=vec.fit_transform(lib.ctext)
    tt=[clean(t,v) for t,v in zip(targets.title,targets.vendor)]
    Xt=vec.transform(tt)
    nn=NearestNeighbors(n_neighbors=min(k,len(lib)),metric='cosine').fit(Xl)
    dist,idx=nn.kneighbors(Xt)
    lf=feats(lib.title); tf=feats(targets.title)
    skun=targets.sku.astype(str).str.upper().str.replace(r'[^A-Z0-9]','',regex=True).values
    out=[]
    for r in range(len(targets)):
        best=None
        for d,j in zip(dist[r],idx[r]):
            if lib.mpn_n.iat[j]==skun[r]: continue      # never use the same part (that would be a verified match, handled elsewhere)
            sim=1-d
            pen,scale=compat(tf.iloc[r],lf.iloc[j])
            if scale<0.33 or scale>3: scale=1.0; pen+=0.2
            score=sim-pen
            if best is None or score>best[0]: best=(score,j,sim,scale)
        if best: out.append((targets.index[r],best[0],best[2],int(best[1]),lib.weight_kg.iat[best[1]]*best[3],best[3]))
    return pd.DataFrame(out,columns=['idx','score','sim','lib_row','match_kg','scale']).set_index('idx')
