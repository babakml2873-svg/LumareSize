import sys, pandas as pd, traceback, re
sys.path.insert(0,'/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/work')
from estimate import est, REF
from features import pack
SP='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/'
p=pd.read_pickle(SP+'prod.pkl').set_index('Handle')
v=pd.read_pickle(SP+'var.pkl')
out=[]; errs=0
for i,r in v.iterrows():
    pr=p.loc[r.Handle]
    title=str(pr.Title)
    opts=' '.join(str(r[c]) for c in ['Option1 Value','Option2 Value','Option3 Value'] if isinstance(r[c],str) and r[c]!='Default Title')
    t=title+' | '+opts
    try:
        kg,keys,basis,conf=est(pr.cls,t)
    except Exception as e:
        errs+=1; kg,keys,basis,conf=None,[],'ERR '+repr(e),'Low'
    q=pack(title)
    out.append(dict(idx=i,cls=pr.cls,kg_each=kg,pack=q,keys=keys,basis=basis,conf=conf))
o=pd.DataFrame(out).set_index('idx'); o.to_pickle(SP+'est.pkl')
print('errors',errs); print(o[o.basis.str.startswith('ERR')].basis.value_counts().head(20))
