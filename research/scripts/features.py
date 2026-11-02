import re
from fractions import Fraction
def _num(s):
    s=s.strip().replace('"','')
    try:
        if '-' in s and '/' in s:
            a,b=s.split('-',1); return float(a)+float(Fraction(b))
        if ' ' in s and '/' in s:
            a,b=s.split(' ',1); return float(a)+float(Fraction(b))
        if '/' in s: return float(Fraction(s))
        return float(s)
    except Exception: return None
FR=r'(\d+(?:[- ]\d+/\d+)|\d+/\d+|\d+(?:\.\d+)?)'
def watts(t):
    v=[float(x) for x in re.findall(r'(?<![\w.\-])(\d{1,4}(?:\.\d+)?)\s?(?:W|watts?)\b(?!/)',t,re.I)]
    v=[x for x in v if 0<x<=2000]
    return max(v) if v else None
def length_ft(t):
    m=re.search(r'(?<![\d.])(\d{1,3}(?:\.\d+)?)\s?(?:ft\.?|feet|foot|\')(?!\w)',t,re.I)
    if m: return float(m.group(1))
    m=re.search(r'(?<![\d.])(\d{1,3}(?:\.\d+)?)\s?(?:m|meters?|metre)\b',t,re.I)
    if m and float(m.group(1))<=100: return float(m.group(1))*3.281
    m=re.search(r'(?<![\d./-])(\d{2,3}(?:\.\d+)?)\s?(?:"|in\b|inch|-inch)',t,re.I)
    if m and 12<=float(m.group(1))<=240: return float(m.group(1))/12
    return None
def inches(t):
    m=re.search(r'(?<![\d./-])(\d{1,2}(?:\.\d+)?)\s?(?:"|in\b|inch|-inch|”)',t,re.I)
    return float(m.group(1)) if m else None
def trade_size(t):
    m=re.search(FR+r'\s?(?:"|in\b|inch|”|-in\b)',t,re.I)
    if m:
        v=_num(m.group(1))
        if v and 0.3<=v<=6: return v
    m=re.search(r'\b(\d{3})\b',t)  # catalog style e.g. LT90125 -> skip
    return None
def poles(t):
    m=re.search(r'(\d)\s?-?\s?(?:p\b|pole)',t,re.I)
    if m: return int(m.group(1))
    if re.search(r'single[- ]pole',t,re.I): return 1
    if re.search(r'double[- ]pole|two[- ]pole',t,re.I): return 2
    if re.search(r'three[- ]pole|triple[- ]pole',t,re.I): return 3
    return None
def amps(t):
    v=[int(x) for x in re.findall(r'(?<![\d.])(\d{1,4})\s?(?:A|amps?)\b',t,re.I)]
    return max(v) if v else None
def lights(t):
    m=re.search(r'(\d{1,2})[- ]?(?:light|lt|lite)s?\b',t,re.I)
    return int(m.group(1)) if m else None
def gang(t):
    m=re.search(r'(\d)[- ]?(?:gang|g)\b',t,re.I)
    if m: return int(m.group(1))
    for w,n in (('single',1),('two',2),('three',3),('four',4)):
        if re.search(w+r'[- ]gang',t,re.I): return n
    return None
def pack(t):
    t=re.sub(r'(\d),(\d{3})',r'\1\2',t)
    for pat in [r'\((\d+)\s?(?:pc|pcs|pieces)\b', r'(?:case|pack|box|bag|carton|pkg|package|set) of (\d+)', r'\((\d+)\s*-?\s*(?:pack|pk|pcs|pieces|pc)\)', r'\b(\d+)\s*-?\s*(?:pack|pk)\b', r'\b(\d+)\s?/\s?(?:box|bag|pack|carton)\b', r'\((\d+)-pack\)']:
        m=re.search(pat,t,re.I)
        if m:
            n=int(m.group(1))
            if 1<n<=5000: return n
    return 1
def dims(t):
    m=re.search(r'(\d{1,2})\s?(?:in)?\s?x\s?(\d{1,2})\s?(?:in)?\s?x\s?(\d{1,2})',t,re.I)
    if m: return tuple(int(x) for x in m.groups())
    m=re.search(r'\b(\d{2})(\d{2})(\d{1,2})(?:SC|R|\b)',t)
    return None
