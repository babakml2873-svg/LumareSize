import pandas as pd, re, sys
sys.path.insert(0, sys.argv[1])
from classify import classify
d=pd.read_pickle(sys.argv[2])
p=d[d.Title.notna()].copy()
p['desc']=p['Body (HTML)'].fillna('').str.replace('<[^>]+>',' ',regex=True).str.extract(r'(?:is an? |—)(.{0,160})',flags=0)[0].fillna('')
p['ptype']=p['Body (HTML)'].fillna('').str.extract(r'Product Type</th>\s*<td>([^<]+)',flags=re.I)[0]
p[['cls','how']]=p.apply(lambda r: pd.Series(classify(r.Type if isinstance(r.Type,str) else "", r.Title, r.ptype if isinstance(r.ptype,str) else "", r.Vendor if isinstance(r.Vendor,str) else "", r.desc)),axis=1)
p[['Handle','Vendor','Type','Title','ptype','desc','cls','how','Body (HTML)']].to_pickle(sys.argv[3])
print(p.cls.value_counts().to_string())
