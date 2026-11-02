import json, glob, math, re, os
from features import *
from features import _num, FR
from fractions import Fraction
REFDIR='/tmp/claude-0/-home-user-LumareSize/4bdae89e-be9f-5b88-bcfd-cb08e1ba615f/scratchpad/refs'
REF={}
for f in sorted(glob.glob(REFDIR+'/*.json')):
    g=os.path.basename(f)[:-5]
    for i,r in enumerate(json.load(open(f))):
        if r.get('weight_kg') and 'ebay.' not in (r.get('url') or '').lower() and 'lumera' not in json.dumps(r).lower(): REF[f'{g}:{i}']=r
def W(*keys):
    """per-piece kg average of refs (handles pack_qty)"""
    v=[REF[k]['weight_kg']/(REF[k].get('pack_qty') or 1) for k in keys]
    return sum(v)/len(v)
def curve(x, pts):
    """log-log interpolation; pts: list of (x, keys or kg)"""
    P=sorted((px, W(*k) if isinstance(k,tuple) else k, k) for px,k in pts)
    xs=[p[0] for p in P]
    if x is None: return None,[]
    def keys(k): return list(k) if isinstance(k,tuple) else []
    if x<=xs[0]:
        if len(P)>1:
            b=math.log(P[1][1]/P[0][1])/math.log(P[1][0]/P[0][0])
            b=max(0.3,min(b,2.5))
        else: b=1
        return P[0][1]*(x/P[0][0])**b, keys(P[0][2])
    if x>=xs[-1]:
        if len(P)>1:
            b=math.log(P[-1][1]/P[-2][1])/math.log(P[-1][0]/P[-2][0]); b=max(0.3,min(b,1.2))
        else: b=1
        return P[-1][1]*(min(x,3*P[-1][0])/P[-1][0])**b, keys(P[-1][2])
    for (x0,y0,k0),(x1,y1,k1) in zip(P,P[1:]):
        if x0<=x<=x1:
            t=math.log(x/x0)/math.log(x1/x0) if x1!=x0 else 0
            return math.exp(math.log(y0)+t*(math.log(y1)-math.log(y0))), (keys(k0)+keys(k1)) if t not in (0,1) else keys(k0 if t==0 else k1)
def has(t,pat): return re.search(pat,t,re.I) is not None

def est(cls, t):
    """t = text (title + options). returns kg_each, refs, basis, confidence"""
    M='Medium'; Lo='Low'
    w=watts(t); L=length_ft(t); s=inches(t); ts=trade_size(t)
    if cls!='floor_box_cover' and has(t,r'arlington.*\bFLBC?\d') and has(t,r'cover'): return est('floor_box_cover',t)
    if cls!='lamp_bulb' and has(t,r'incandescent lamp|wedge ?base|halogen lamp|led lamp\b') and not has(t,r'fixture|socket'): return est('lamp_bulb',t)
    if cls!='floor_box' and has(t,r'electrical pedestal'): return W('F2:1'),['F2:1'],'electrical pedestal est. vs 3-gang cast floor box',Lo
    if has(t,r'pigtail'): return W('H:10'),['H:10'],'ground pigtail with screw est. at #6 copper lug weight',Lo
    if has(t,r'\bchain\b'): return W('D2:6','D2:7')/10,['D2:6','D2:7'],'chain per foot est. from 10ft LED extension cable weight per foot (pack = feet)',Lo
    if has(t,r'heat lamp'): return W('D:32','D:33')*1.4,['D:32','D:33'],'R40 heat lamp est. 1.4x BR30 lamp refs',Lo
    if has(t,r'lamp ?socket|lampholder|lamp holder'): return W('E:6'),['E:6'],'lampholder/socket est. at wall switch weight',Lo
    if has(t,r'box support|bracket') and has(t,r'non-?metallic|plastic|low voltage'): return W('F:13'),['F:13'],'plastic bracket est. at Carlon 1-gang plastic box weight',Lo
    if has(t,r'downlight bracket|recessed.*bracket|box support'): return W('F:24'),['F:24'],'steel bracket/support est. at RACO 768 device ring weight',Lo
    if has(t,r'arlington.*\bRW\d') : return W('G2:20'),['G2:20'],'reducing washer vs Bridgeport 1061',M
    if cls!='misc' and has(t,r'cable tie|zip tie|cable staple|\bstaples?\b') and not has(t,r'mount'): return est('misc',t)
    M='Medium'; Lo='Low'
    def fixed(keys,basis,conf=M): return W(*keys),list(keys),basis,conf
    def cv(x,pts,basis,default_x,conf=M):
        if x is None: x=default_x; conf=Lo; basis+=f' (size not stated; assumed {default_x})'
        kg,k=curve(x,pts); return kg,k,basis+f' scaled to {x:g}',conf
    # ---------------- lighting
    if cls=='downlight':
        if has(t,r'cylinder|\bcyl'):
            return cv(s,[(4.9,('A:3','A:4'))],'LED cylinder; ref 4-5in cylinders, scaled by aperture^1.5',4)
        if has(t,r'monopoint'): return fixed(('A:22',),'LED monopoint fixture vs WAC Paloma monopoint')
        if has(t,r'disk|disc'): return fixed(('D2:12','D2:13'),'LED surface disk light vs 6in disk refs')
        if has(t,r'commercial|ip-dr|high output|\blm\b.*\b[2-9]\d{3}'):
            return cv(s,[(6,('A:5',))],'commercial LED downlight; ref Lithonia LDN6',6)
        return cv(s,[(2,('D2:10','D2:11')),(4,('A:1',)),(6,('A:2',))],'LED canless/recessed downlight; aperture curve 2in Koto / 4in & 6in Lithonia WF',4)
    if cls=='trim':
        if has(t,r'baffle') and not has(t,r'led|engine|module'): return cv(s,[(6,('A:13',))],'non-LED baffle trim vs Halo 6100WB',6)
        return cv(s,[(2,('A:11','A:12')),(4,('A:7','A:8')),(6,('A:9','A:10'))],'LED trim/engine/reflector; aperture curve WAC 2in / Halo RL4 / Halo RL6',4)
    if cls=='housing':
        if has(t,r'remodel|retrofit'): return cv(s,[(6,('A:17',))],'remodel recessed housing vs Halo H7RICAT',6)
        return cv(s,[(2,('A:18',)),(4,('A:14',)),(6,('A:15','A:16'))],'recessed housing / frame-in; aperture curve WAC 2in / Halo H995ICAT / H750ICAT',4)
    if cls=='track_head':
        if has(t,r'monopoint'): return fixed(('A:22',),'LED monopoint vs WAC Paloma')
        if has(t,r'\brail\b|track section|\d ?ft'): 
            return cv(L,[(4,('A:25',))],'track rail section vs Halo L651P 4ft per length',4)
        if w and w>60: w=None
        return cv(w,[(10,('A:19',)),(20,('A:20',))],'LED track head; wattage curve WAC H-8010 / H-3020',15)
    if cls=='track_kit': return fixed(('B2:14','B2:15'),'4ft track kit vs Nicor/Nuvo kits')
    if cls=='track_accessory':
        if has(t,r'canopy|limiter|barn door|projector'): return fixed(('B2:15',),'heavier track accessory approx 15% of a 3-light track kit',Lo) if False else (W('A:25')*0.4,['A:25'],'track canopy/limiter accessory estimated at 40% of Halo 4ft rail',Lo)
        return fixed(('A:24',),'track connector/end/feed vs Juno T23')
    if cls=='pendant':
        if has(t,r'linear') or (L and L>=2): return cv(L,[(4,('B:10',))],'linear pendant per length vs WAC Cabot 48in',4)
        n=lights(t)
        if n and n>=3: return cv(n,[(3,('B:5','B:6')),(5,('B:7','B:8')),(9,('B:9',))],'multi-light pendant; light-count curve',3)
        if has(t,r'mini') or (s and s<=8): return fixed(('B:0',),'mini pendant vs Kuzco 41311W')
        if s and s>=10: return cv(s,[(6.5,('B:0',)),(16,('B:1','B:2')),(24,('B:3',))],'pendant; diameter curve Kuzco mini / Hinkley 16in / Visual Comfort 24in',16)
        if has(t,r'\bled\b') : return fixed(('B:4','B:0'),'small LED/1-light pendant vs Kuzco pendants',Lo)
        return fixed(('B:1','B:2'),'decorative pendant (size not stated) vs Hinkley medium pendants',Lo)
    if cls=='chandelier':
        if has(t,r'linear') : return cv(L,[(4,('B:10',))],'linear chandelier per length vs WAC Cabot 48in',4)
        n=lights(t)
        return cv(n,[(3,('B:5','B:6')),(5,('B:7','B:8')),(9,('B:9',))],'chandelier; light-count curve Progress 3-lt / Kichler 5-lt / Fredrick Ramond 9-lt',5)
    if cls=='sconce':
        if has(t,r'outdoor|exterior|lantern'):
            if has(t,r'lantern') and not has(t,r'\bled\b'): return fixed(('B:14','B:15'),'outdoor wall lantern vs Kichler 49893 / Hinkley 2324')
            return fixed(('B:16','B:17'),'outdoor LED wall light vs Kichler LED up/down cylinders')
        if has(t,r'\bled\b'): return fixed(('B:13',),'indoor LED sconce vs Kuzco WS83218')
        return fixed(('B:11','B:12'),'indoor wall sconce vs Hinkley sconces')
    if cls=='vanity':
        n=lights(t)
        if not n and (has(t,r'\bled\b') or L):
            if L: return cv(L*12,[(24,('B:24','B:25'))],'LED vanity bar per length vs WAC 24in bars',24)
            return fixed(('B:24','B:25'),'LED vanity bar vs WAC 24in bars',Lo)
        return cv(n,[(1,('B:18','B:19')),(3,('B:20','B:21')),(4,('B:22','B:23'))],'bath vanity; light-count curve Progress/Kichler/Hinkley',3)
    if cls=='flush_mount':
        if has(t,r'\bled\b') and not has(t,r'semi'): return cv(s,[(13,('B:26',))],'LED flush mount vs Progress P3632 13in (area scaling)',13)
        return cv(s,[(13,('B:27',)),(18,('B:0x',)) if False else (18,('B2:0',))],'decorative flush/semi-flush; diameter curve Progress Bezel 13in / Hinkley 18in',14)
    if cls=='floor_lamp': return fixed(('B2:1','B2:2'),'floor lamp vs Possini arc floor lamps',Lo)
    if cls=='table_lamp': return fixed(('B2:3',),'table lamp vs Possini Mia 25in',Lo)
    if cls=='ceiling_fan':
        if has(t,r'light kit|blade|arm|control|switch|remote'): return fixed(('B2:8','B2:9'),'fan accessory vs Minka downrod',Lo)
        return cv(s if s and s>=30 else None,[(44,('B2:6','B2:7')),(52,('B2:4','B2:5'))],'ceiling fan; blade-span curve Hunter 44in / Minka 52in',52)
    if cls=='fan_accessory': return fixed(('B2:8','B2:9'),'fan downrod/accessory vs Minka DR518')
    if cls=='lamp_shade':
        if has(t,r'fabric|linen|drum|burlap'): return fixed(('B2:11',),'fabric shade vs 16in drum shade',Lo)
        if has(t,r'lens|louver|filter|snoot|optic'): return fixed(('A:24',),'small optic/lens accessory (estimated at track connector weight x3)',Lo) if False else (W('A:24')*3,['A:24'],'small optic/lens accessory estimated at 3x Juno T23 connector weight',Lo)
        return fixed(('B2:10',),'glass shade vs Westinghouse 8131400',Lo)
    if cls=='high_bay':
        if has(t,r'linear'): return cv(w,[(220,('C:4',))],'linear high bay vs EnVision 220W (wattage scaling)',220)
        return cv(w,[(100,('C:0',)),(150,('C:1','C:2')),(240,('C:3',))],'UFO high bay; wattage curve',150)
    if cls=='flood':
        if has(t,r'shroud|visor|lens|bracket|mount'): return W('C:5')*0.25,['C:5'],'flood accessory est. 25% of 30W RAB flood',Lo
        return cv(w,[(30,('C:5','C:6')),(100,('C:7','C:8')),(300,('C:9','C:10'))],'LED flood; wattage curve RAB 30W / MaxLite+NaturaLED 100W / Halco+West 300W',50)
    if cls=='area_light':
        if has(t,r'path|landscape|mini pole|flag'): return est('landscape_path',t)
        if has(t,r'mount|arm|bracket|pole adapter'): return W('C:11')*0.15,['C:11'],'area light mount est. 15% of 100W area light',Lo
        return cv(w,[(100,('C:11',)),(200,('C:12','C:13')),(300,('C:14',))],'LED area/shoebox; wattage curve',150)
    if cls=='wall_pack':
        if has(t,r'canopy|garage'): return cv(w,[(60,('C:21',))],'LED canopy light vs NaturaLED 60W (wattage scaling)',60)
        if has(t,r'shroud|visor|bracket'): return W('C:15')*0.2,['C:15'],'wall pack accessory est. 20% of 30W wall pack',Lo
        return cv(w,[(30,('C:15','C:16')),(80,('C:17','C:18')),(120,('C:19','C:20'))],'LED wall pack; wattage curve',60)
    if cls=='panel_troffer':
        k=('C:28','C:29') if has(t,r'troffer|lay-in') else None
        if has(t,r'2 ?x ?4|2x4|24 ?x ?48|2\'? ?x ?4'): return fixed(k or ('C:24','C:25'),'2x4 LED panel/troffer refs')
        if has(t,r'1 ?x ?4|1x4|12 ?x ?48'): return fixed(('C:26','C:27'),'1x4 LED panel refs')
        if has(t,r'2 ?x ?2|2x2|24 ?x ?24'): return (W(*k)/2,list(k),'2x2 troffer est. as half of 2x4 Lithonia 2GTL4',Lo) if k else fixed(('C:22','C:23'),'2x2 LED panel refs')
        if has(t,r'1 ?x ?2|1x2|12 ?x ?24'): return W('C:26','C:27')/2,['C:26','C:27'],'1x2 panel est. as half of 1x4 panel refs',Lo
        if s: return cv(s,[(6,('D2:12','D2:13'))],'round/square slim panel scaled from 6in disk refs (area)',6)
        return fixed(('C:22','C:23'),'LED panel, size not stated, vs 2x2 panel refs',Lo)
    if cls=='vapor_strip':
        if has(t,r'vapor'): return cv(L,[(4,('C:30','C:31')),(8,('C:32',))],'LED vapor tight; length curve',4)
        if has(t,r'wrap'): return cv(L,[(4,('C:35',))],'LED wraparound vs 4ft ref',4)
        return cv(L,[(4,('C:33','C:34'))],'LED strip/linear fixture vs Lithonia CSS 4ft',4)
    if cls=='exit_emerg':
        if has(t,r'nema ?4x|wet location|vandal'): return fixed(('C2:2',),'NEMA 4X exit/emergency vs Dialight ECN combo')
        if has(t,r'combo|exit.*emerg|emerg.*exit'): return fixed(('C2:0','C2:1'),'exit/emergency combo vs Lithonia LHQM')
        if has(t,r'exit'): return fixed(('C:36','C:37'),'LED exit sign vs Lithonia LQM')
        if has(t,r'remote|head'): return W('C:38')*0.3,['C:38'],'remote emergency head est. 30% of Lithonia ELM2L',Lo
        return fixed(('C:38',),'emergency light vs Lithonia ELM2L')
    if cls in ('linear_arch','under_cabinet','landscape_well','landscape_path','landscape_spot','light_fixture_generic'):
        return est_c2(cls,t,w,L,s)
    if cls=='driver':
        if has(t,r'landscape|stainless|transformer') and (w is None or w>=100) and not has(t,r'magnetic.*(driver)|electronic'):
            return cv(w,[(300,('D:22','D:23')),(600,('D:24',)),(900,('D:25','D:27')),(1200,('D:26',))],'landscape transformer; wattage curve Kichler/FX',300)
        if has(t,r'emergency|battery|backup|inverter'): return fixed(('D:28','D:29'),'emergency LED driver/battery vs Bodine BSL310')
        if has(t,r'magnetic'): return cv(w,[(60,('D:21',))],'magnetic LV transformer/driver vs EnVision 60W (linear wattage scaling)',60)
        if has(t,r'ballast retrofit'): return cv(40,[(20,('D:12','D:13')),(60,('D:14','D:15'))],'Lutron LED ballast retrofit kit treated as ~40W LED driver',40,Lo)
        if has(t,r'junction box|j-box|enclosure'): return cv(w,[(96,('D:16',))],'driver in junction box vs Magnitude M96L24DC-AR',96)
        return cv(w,[(20,('D:12','D:13')),(60,('D:14','D:15')),(96,('D:16','D:17')),(150,('D:18',)),(320,('D:19','D:20'))],'LED driver/power supply; wattage curve Mean Well/Magnitude',60)
    if cls=='tape_light':
        if has(t,r'jumper|connector|clip|end cap'): return est('tape_connector',t)
        per = W('D:0')/16.4; basis='LED tape per foot from 16.4ft 24V reel (Inspired LED)'
        if has(t,r'neon'): per=W('D:3','D:4')/32.8; basis='LED neon flex per foot from Aspect LED 32.8ft reels'; keys=['D:3','D:4']
        elif has(t,r'120v|rope'): per=W('D:2')/150; basis='120V LED strip per foot from Wiedamark 150ft spool'; keys=['D:2']
        else: keys=['D:0']
        if has(t,r'strip light fixture|ip66 led strip|ULS-|led strip light,') and not has(t,r'tape'): return est('vapor_strip',t)
        conf=M
        if L is None: L=16.4; conf=Lo; basis+=' (length not stated; assumed 16.4ft reel)'
        return per*L, keys, basis+f' x {L:g} ft', conf
    if cls=='channel':
        if has(t,r'end ?cap|clip|bracket|connector'): return est('channel_acc',t)
        if has(t,r'lens|diffuser') and not has(t,r'bundle'): k=0.35
        else: k=1.0
        per=W('D:6')/(2*3.281)
        conf=M
        if L is None: L=6.56 if not has(t,r'1 ?m\b') else 3.28; conf=Lo
        return per*L*k,['D:6'],f'aluminum LED channel per foot from Klus 2m profile x {L:g} ft'+(' (lens only ~35%)' if k<1 else ''),conf
    if cls=='channel_acc':
        if has(t,r'end ?cap|clip|clevis'): return fixed(('D2:1',),'channel clips/end caps vs aspectLED 5-pack clips',Lo)
        if has(t,r'chain|cord|wire|cable'): return fixed(('D2:6','D2:7'),'cord/cable accessory vs 10ft LED extension cables',Lo)
        if has(t,r'pole|arm|bracket|mount|kit|plate|stake|spike'): return W('F:22'),['F:22'],'metal mounting bracket/kit vs Arlington 8081 mounting kit (comparable size steel/plastic accessory)',Lo
        return fixed(('D2:1',),'small lighting accessory vs aspectLED clip pack',Lo)
    if cls=='tape_connector':
        if has(t,r'extension|power cord|appliance cord|suspension') or (L and L>=8): return cv(L,[(10,('D2:6','D2:7'))],'extension/suspension cable per length vs 10ft LED extension cables',10)
        return fixed(('D2:4','D2:5'),'tape connector/jumper vs Diode LED / WAC jumpers')
    if cls=='lamp_bulb':
        if has(t,r'incandescent|halogen|xenon|quartz|mini.?can') : w=None
        if has(t,r'incandescent|halogen|xenon') and not has(t,r'par|mr16|br\d|t8|t5'): return fixed(('D:46','D:47'),'incandescent/halogen lamp vs Satco decorative lamps (similar glass envelope mass)',Lo)
        if has(t,r'corn|hid replacement|post top'): return cv(w,[(100,('D:41','D:42'))],'LED corn lamp; wattage scaling vs Satco/GB 100W',100)
        if has(t,r'\bt8\b|\bt5\b|tube'): return cv(L,[(4,('D:40',))],'LED tube per length vs 4ft T8',4)
        if has(t,r'par ?38'): return fixed(('D:34','D:35'),'PAR38 LED lamp refs')
        if has(t,r'par ?30'): return W('D:34','D:35','D:36','D:37')*0.9,['D:34','D:35','D:36','D:37'],'PAR30 est. between PAR20 and PAR38 refs',Lo
        if has(t,r'par ?20|par ?16'): return fixed(('D:36','D:37'),'PAR20 LED lamp refs')
        if has(t,r'br ?40'): return W('D:32','D:33')*1.4,['D:32','D:33'],'BR40 est. 1.4x BR30 refs',Lo
        if has(t,r'br ?30|br ?20|r ?20|r ?30'): return fixed(('D:32','D:33'),'BR30 LED lamp refs')
        if has(t,r'mr ?16|mr ?11|gu10|ar111'): return fixed(('D:38','D:39'),'MR16 LED lamp refs')
        if has(t,r'\bc7\b|\bc9\b|ledc7|ledc9|s11|s14|g40'): return fixed(('D2:8','D2:9'),'C7/C9 replacement bulb refs (per bulb)')
        if has(t,r'\bg9\b|\bg4\b|bi-pin|g8'): return fixed(('D:44','D:45'),'G9/G4 bi-pin LED refs')
        if has(t,r'filament|st19|g25|edison|candelabra|\bb11\b|ca10'): return fixed(('D:46','D:47'),'LED filament/decorative lamp refs')
        if has(t,r'\bpl\b|4-pin|2-pin|cfl'): return W('D:40')*0.5,['D:40'],'PL/CFL-replacement LED est. 50% of 4ft T8 tube',Lo
        if w and w>30: return cv(w,[(100,('D:41','D:42'))],'high-wattage LED lamp scaled from 100W corn lamp',100)
        return fixed(('D:30','D:31'),'A-line/general LED lamp vs Satco A19')
    # ---------------- wiring devices & controls
    if cls=='receptacle':
        a=amps(t)
        if a and a>=30: return fixed(('E:3',),'30-50A single receptacle vs Leviton 279')
        if has(t,r'20 ?a|commercial|industrial|hospital|spec'): return fixed(('E:1','E:2'),'20A commercial duplex vs Hubbell HBL5362')
        return fixed(('E:0',),'15A duplex receptacle vs Leviton 5320')
    if cls=='gfci': return fixed(('E:4',),'GFCI receptacle vs Leviton GFNT2')
    if cls=='usb_recept': return fixed(('E:5',),'USB receptacle vs Leviton T5633')
    if cls=='switch':
        if has(t,r'weatherproof|cover'): return fixed(('F2:13',),'weatherproof device/cover vs TayMac MX3200 die-cast cover',Lo)
        if has(t,r'20 ?a|commercial|industrial'): return fixed(('E:7','E:8'),'20A commercial switch vs Hubbell HBL1221')
        return fixed(('E:6',),'15A wall switch vs Leviton 5601')
    if cls=='dimmer':
        if has(t,r'fan'): return fixed(('E:10','E:11'),'fan speed control vs Lutron DVFSQ-F')
        if has(t,r'heater'): return fixed(('E2:12',),'heater control panel vs Infratech 30-4053',Lo)
        return fixed(('E:9',),'wall dimmer/control vs Lutron Diva DVCL-153P')
    if cls=='keypad_remote':
        if has(t,r'pico|remote|handheld|fob'): return fixed(('E:12',),'wireless remote vs Lutron Pico',Lo)
        if has(t,r'keypad|seetouch|wall|switch|dimmer|aux'): return fixed(('E:13',),'wall keypad/control vs Lutron RRD-W6BRL')
        if has(t,r'flood|fixture|downlight'): return est('flood' if has(t,'flood') else 'downlight',t)
        return fixed(('E:14','E:15'),'hub/controller/interface vs Lutron Caseta bridge',Lo)
    if cls=='occ_sensor':
        if has(t,r'ceiling|fixture mount|high bay|line voltage.*power pack|power pack|corner'): return fixed(('E:17',),'ceiling/fixture sensor vs Leviton OSC10')
        if has(t,r'fan'): return est('vent_fan',t)
        if has(t,r'disk|downlight'): return est('downlight',t)
        return fixed(('E2:13',),'wall-switch occupancy sensor vs Lutron MS-OPS2')
    if cls=='timer':
        if has(t,r'photo'): return fixed(('E:21',),'photocontrol vs Intermatic K4121C')
        if has(t,r'mechanical time switch|t10\d|t17\d|enclosure|panel mount|din rail|module|motor|mechanism|outdoor'): return fixed(('E:20',),'time switch in enclosure/module vs Intermatic T104',Lo if has(t,'module|motor|mechanism') else M)
        if has(t,r'spring|countdown|ff\d'): return fixed(('E:19',),'spring-wound/countdown timer vs Intermatic FF60MC')
        return fixed(('E:18',),'in-wall electronic timer vs Intermatic EI400')
    if cls=='surge':
        if has(t,r'strip|point-of-use|plug-in'): return fixed(('E:24',),'surge strip vs Tripp Lite TLP606')
        if has(t,r'module'): return W('E:22','E:23')*0.4,['E:22','E:23'],'SPD replacement module est. 40% of panel SPD',Lo
        return fixed(('E:22','E:23'),'panel SPD vs Eaton CHSPT2 / Intermatic IG1240')
    if cls=='wallplate':
        g=gang(t) or 1
        if has(t,r'stainless|metal|brass|bronze|nickel|chrome|aluminum|steel'):
            return (W('E:27') if g==1 else W('E:29')/3*g), (['E:27'] if g==1 else ['E:29']), f'metal wallplate {g}-gang vs Pass & Seymour SS plates', M
        return W('E:28')/3*g,['E:28'],f'thermoplastic wallplate {g}-gang scaled from P&S TP263 3-gang',M
    if cls=='network_jack': return fixed(('E:30',),'keystone jack vs Leviton 61110')
    if cls=='pin_sleeve':
        a=amps(t) or 30
        return cv(a,[(30,('E:31',)),(60,('E:32',)),(100,('E:33',))],'pin & sleeve device; amperage curve Hubbell HBL4xx',30)
    if cls=='locking_plug':
        a=amps(t)
        return cv(a,[(20,('E2:0',)),(30,('E2:1',)),(50,('E2:3',))],'locking/industrial plug or connector; amperage curve Hubbell',20)
    if cls=='hour_meter': return fixed(('E2:4',),'AC hour meter vs Intermatic FWZ72')
    if cls=='vent_fan':
        if has(t,r'grille|cover'): return fixed(('E2:6',),'fan grille vs Broan FGR101')
        if has(t,r'light kit|light$'): return W('E2:6')*2.5,['E2:6'],'vent fan light kit est. 2.5x fan grille',Lo
        return fixed(('E2:5',),'bath ventilation fan vs Panasonic FV-0511VQ1')
    if cls=='heater':
        if has(t,r'control|relay|switch|dimmer'): return fixed(('E2:12',),'heater control vs Infratech 30-4053',Lo)
        return cv(w if w and w>=500 else None,[(2000,('E2:7',)),(4000,('E2:8','E2:9')),(6000,('E2:10','E2:11'))],'infrared heater; wattage curve Infratech W/WD series',4000)
    # ---------------- power distribution & boxes
    if cls in ('breaker','breaker_mccb'):
        a=amps(t); p=poles(t) or 1
        if has(t,r'hub|handle|lock|tie|cover|lug kit|accessory|shunt'): return fixed(('F:24',),'breaker accessory (hub/handle) vs small steel accessory RACO 768',Lo)
        if (a and a>=125) or has(t,r'molded case|\b[EFHJKL][DGJAL]?[A-Z]?\d{4,6}'):
            a=a or 100
            if a>=125 or p>=3 and has(t,r'480|600'):
                return cv(a,[(100,('F:8',)),(225,('F:7',))],'molded case breaker; amperage curve Square D HDL / Siemens FXD',100)
        if has(t,r'afci|gfci|gfp|cafi|dual function|df\b'): return W('F:5','F:6')*p,['F:5','F:6'],f'AFCI/GFCI breaker x {p} pole vs QO120CAFI',M
        if p>=3: return fixed(('F:4',),'3-pole breaker vs Square D QOB320',Lo)
        return W('F:0','F:1')*p,['F:0','F:1'],f'miniature breaker {p}-pole (per-pole) vs Siemens Q120',M
    if cls=='load_center':
        if has(t,r'bracket|cover|trim|door|hub'): return fixed(('F:23',),'load center accessory vs steel cover',Lo)
        if has(t,r'meter'): return fixed(('F:11','F:12'),'meter socket/main vs Milbank',Lo)
        a=amps(t)
        return cv(a,[(100,('F:9',)),(200,('F2:14','F2:15'))],'load center; amperage curve',100)
    if cls=='disconnect': return fixed(('E:20',),'relay panel/kit est. vs Intermatic T104 enclosure',Lo)
    if cls=='fuse': return fixed(('E:21',),'',Lo)
    if cls=='elec_box':
        g=gang(t) or 1
        if has(t,r'siding|mounting block|mounting kit'): return fixed(('F:22',),'siding mounting kit vs Arlington 8081')
        if has(t,r'fan'): return fixed(('F:18','F:19'),'fan-rated box/brace vs Arlington FBRS415')
        if has(t,r'cast|\bfs\b|\bfd\b'): return W('F:20','F:21')*g,['F:20','F:21'],f'cast device box {g}-gang vs Crouse-Hinds FS1',M
        if has(t,r'5s|4-11/16|4 11/16'): return W('F:15','F:16')*1.45,['F:15','F:16'],'5S (4-11/16) steel box est. 1.45x 4S deep box',M
        if has(t,r'4s|4 in square|4" square|square'):
            return (W('F:15','F:16'),['F:15','F:16'],'4in square deep steel box vs RACO 232','Medium') if has(t,r'2-1/8|2 1/8|deep|3-1/2') else fixed(('F:14',),'4in square steel box vs RACO 189')
        if has(t,r'octagon|4o\b|round'): return fixed(('F:17',),'octagon/round steel box vs RACO 125')
        if has(t,r'steel|metal|handy|gangable|switch box|utility'): return W('F:14')*0.75*g,['F:14'],f'steel device box {g}-gang est. 75% of 4S box per gang',Lo
        return W('F:13')*g,['F:13'],f'plastic/nonmetallic box {g}-gang vs Carlon B114R',M if has(t,r'plastic|pvc|nonmetal|non-metal|uv') else Lo
    if cls=='box_cover':
        k=1.45 if has(t,r'5s|4-11/16') else 1.0
        if has(t,r'industrial'): return W('F:25')*k,['F:25'],'industrial raised cover vs RACO 811C',M
        if has(t,r'ring|raised|mud|plaster'): return W('F:24')*k,['F:24'],'device/mud ring vs RACO 768',M
        if has(t,r'countdown|timer'): return est('timer',t)
        return W('F:23')*k,['F:23'],'steel box cover vs RACO 752',M if has(t,r'4s|square|octagon|4o|cover') else Lo
    if cls=='wp_box':
        g=gang(t) or 1
        return W('F:26')*g,['F:26'],f'weatherproof die-cast box {g}-gang vs Bell 5321-0',M
    if cls=='wp_cover':
        if has(t,r'die-?cast|metal|extra.duty|alumin'): return fixed(('F2:13',),'die-cast in-use cover vs TayMac MX3200')
        return fixed(('F:27',),'plastic in-use cover vs TayMac MM410C')
    if cls=='enclosure':
        if has(t,r'exit|emergency'): return est('exit_emerg',t+' nema 4x')
        d=dims(t)
        if d is None:
            m=re.findall(r'(\d{1,2})\s?in\s?[WHD]',t)
            if len(m)==3: d=tuple(int(x) for x in m)
        def sa(a,b,c): return 2*(a*b+a*c+b*c)
        if has(t,r'4x|fiberglass|polycarbonate'): base=('F2:11','F2:12'); bd=(8,6,4); lab='NEMA 4X fiberglass 8x6x4 Hoffman'
        else: base=('F2:8','F2:9'); bd=(6,6,4); lab='NEMA 1 6x6x4 screw cover (Hoffman/Hammond)'
        if d: return W(*base)*sa(*d)/sa(*bd),list(base),f'enclosure scaled by surface area {d} vs {lab}',M
        return W(*base),list(base),f'enclosure (size not parsed) vs {lab}',Lo
    if cls=='floor_box':
        if has(t,r'countertop|pop-?up'): return fixed(('F2:2','F2:3'),'countertop pop-up vs Hubbell RCT')
        if has(t,r'plastic|nonmetal|non-metal|pvc|recessed'): return fixed(('F2:4',),'nonmetallic floor box vs Arlington FLBR101')
        g=gang(t)
        if g and g>=2: return W('F2:1')/3*g,['F2:1'],f'{g}-gang cast floor box scaled from Steel City 643 3-gang',M
        return fixed(('F2:0',),'cast iron/steel floor box vs Steel City 600',Lo)
    if cls=='floor_box_cover':
        if has(t,r'plastic|nonmetal|non-metal|black|gray|brown|ivory') and not has(t,r'brass|nickel|aluminum'): return fixed(('F2:7',),'nonmetallic floor cover vs Arlington FLBC4520')
        if has(t,r'flange') and has(t,r'malleable|rigid'): return est('emt_fitting',t)
        return fixed(('F2:5','F2:6'),'brass floor box cover vs Arlington FLBC8501/FLB5320')
    # ---------------- conduit fittings (per piece, by trade size)
    SS=[(0.75,('G:0',)),(1,('G:1',)),(1.25,('G:2',)),(1.5,('G:3',)),(2,('G:4',)),(2.5,('G:5',)),(3,('G:6',)),(4,('G:7',))]
    CMP=[(0.75,('G:10',)),(1,('G:11',)),(1.5,('G:12',)),(2,('G:13',))]
    if cls=='emt_fitting':
        if has(t,r'hub'): return cv(ts,[(1,('G:37',)),(2,('G:39',))],'conduit hub est. vs aluminum LB body curve',1,Lo)
        if has(t,r'coupling'):
            if has(t,r'compression|rain|steel|malleable|rigid'): return cv(ts,[(1,('G:18',)),(1.5,('G:19',)),(2,('G:20',))],'compression/steel coupling; trade-size curve Bridgeport 26x',1)
            return cv(ts,[(0.5,('G:16',)),(1,('G:17',))],'set-screw coupling; trade-size curve Bridgeport 24x-DC',0.75)
        if has(t,r'compression|rain|steel|malleable|rigid|threadless'): return cv(ts,CMP,'compression/steel connector; trade-size curve Bridgeport 25x',0.75)
        if has(t,r'plastic|nylon|non-?metallic|pvc'):
            kg,k,b,c=cv(ts,SS,'plastic fitting est. 30% of zinc set-screw connector curve',0.75); return kg*0.3,k,b,Lo
        return cv(ts,SS,'EMT set-screw connector/fitting; trade-size curve Bridgeport 23x-DC2',0.75)
    if cls=='liquidtight':
        if has(t,r'cable connector|nm|romex|snap|squeeze|duplex|ac/mc|mc cable') and not has(t,r'liquid'):
            if has(t,r'plastic|snap|push'): return fixed(('G:35',),'plastic NM snap-in connector vs Arlington NM94X')
            return cv(ts,[(0.375,('G:34',))],'cable (NM/MC) connector vs Bridgeport 651 (trade-size scaling)',0.5)
        if has(t,r'90|45|angle'): return cv(ts,[(0.5,('G:28','G:29','G:30')),(0.75,('G:31',)),(2,('G:33',))],'liquidtight angle connector; trade-size curve',0.75)
        return cv(ts,[(0.5,('G2:21',)),(0.75,('G2:22',)),(1,('G:22',)),(1.25,('G:23',)),(1.5,('G:24',))],'liquidtight straight connector; trade-size curve',0.75)
    if cls=='conduit_body':
        if has(t,r'service entrance|entrance cap|entrance head'): return cv(ts,[(1.25,('G:43',))],'service entrance cap vs Crouse-Hinds EHC4 (trade-size scaling)',1.25)
        if has(t,r'cover') and not has(t,r'body'): return cv(ts,[(1,('G:37',))],'conduit body cover est. 25% of LB body',1,Lo) if False else (curve(ts or 1,[(0.5,('G2:23','G2:24')),(1,('G:37',)),(2,('G:39',))])[0]*0.25,['G:37'],'conduit body cover est. 25% of aluminum LB body of same trade size',Lo)
        k=2.4 if has(t,r'malleable|iron|steel|form 8') else 1
        kg,keys,b,c=cv(ts,[(0.5,('G2:23','G2:24')),(0.75,('G:36',)),(1,('G:37',)),(1.25,('G:38',)),(2,('G:39',))],'conduit body; trade-size curve Crouse-Hinds aluminum LB',1)
        return kg*k,keys,b+(' x2.4 for malleable iron (ratio LB37/LB37SA)' if k>1 else ''),c
    if cls=='conduit_elbow':
        if has(t,r'chase'): return cv(ts,[(0.5,('G:59',)),(1,('G:60',)),(1.25,('G:61',)),(1.5,('G:62',)),(2.5,('G:63',)),(3,('G:64',))],'chase nipple; trade-size curve Bridgeport 110x',1)
        if has(t,r'nipple|sleeve'): return cv(ts,[(0.5,('G:53',)),(1.5,('G:54',)),(2.5,('G:56',))],'rigid close nipple; trade-size curve Topaz/Robroy',1)
        if has(t,r'pull elbow|conduit bod'): return est('conduit_body',t)
        return cv(ts,[(1,('G:46',)),(1.5,('G:47',)),(2,('G:48',)),(2.5,('G:49',)),(4,('G:50',))],'EMT 90 elbow; trade-size curve Robroy',1)
    if cls=='bushing_locknut':
        if has(t,r'ground'): return cv(ts,[(1,('G2:15',)),(1.5,('G2:16','G2:17')),(2,('G2:18','G2:19'))],'insulated grounding bushing; trade-size curve',1)
        if has(t,r'reducing washer'): return fixed(('G2:20',),'reducing washer vs Bridgeport 1061 (per washer)')
        if has(t,r'plastic|insulat|nylon|non-?metallic') and not has(t,r'zinc|malleable|steel'): return cv(ts,[(1,('G:71','G:72'))],'plastic bushing vs T&B 224 (trade-size^2 scaling)',1)
        if has(t,r'knockout seal|ko seal|plug'): return cv(ts,[(1,('G:67',))],'knockout seal est. vs 1in locknut (trade-size scaling)',1,Lo)
        if has(t,r'bushing'): return cv(ts,[(0.75,('G:66',)),(1,('G:67',)),(3,('G:68',))],'metal bushing est. ~2x locknut curve',1,Lo) if False else (curve(ts or 1,[(0.75,('G:66',)),(1,('G:67',)),(3,('G:68',))])[0]*2,['G:66','G:67','G:68'],'zinc/malleable bushing est. 2x steel locknut of same trade size',Lo)
        return cv(ts,[(0.75,('G:66',)),(1,('G:67',)),(3,('G:68',))],'steel locknut; trade-size curve Bridgeport 10x-S',1)
    if cls=='strap_hanger':
        if has(t,r'beam'): return fixed(('G2:11','G2:12'),'beam clamp vs Bridgeport 951/952')
        if has(t,r'strut|unistrut'): return fixed(('G2:14',),'strut clamp vs B-Line B1520',Lo)
        if has(t,r'hanger'): return cv(ts,[(1,('G2:7',)),(2,('G2:8',)),(2.5,('G2:9',)),(3.5,('G2:10',))],'conduit hanger; trade-size curve Bridgeport 21x0',1)
        if has(t,r'garden|post|support'): return W('F:22'),['F:22'],'light post support/stake est. vs mounting kit',Lo
        return cv(ts,[(0.5,('G2:0',)),(1,('G2:1',)),(2.5,('G2:2',)),(3,('G2:3',)),(4,('G2:5',))],'conduit strap/clip; trade-size curve Bridgeport 90xS',0.75)
    # ---------------- hardware
    if cls=='screw_small':
        if has(t,r'coupling|connector|conduit bod'): return est('emt_fitting',t)
        if has(t,r'threaded rod|all ?thread') and not has(t,r'spike|hanger|coupl|clamp'):
            m=re.search(r'(\d/\d{1,2})\s?-\s?\d{1,2}',t); d=float(Fraction(m.group(1))) if m else 0.375
            kg,k=curve(L or 10,[(10,('H:9',))]); return kg*(d/0.375)**2,k,f'threaded rod scaled by length and dia^2 vs 3/8x10ft ({d:g}in)',M
        if has(t,r'anchor'): return fixed(('H:5',),'concrete/wall anchor (each) vs CDE 11941')
        if has(t,r'toggle'): return fixed(('H:6',),'toggle bolt (each) vs Hillman 53720')
        if has(t,r'\bnut\b|locknut'): return fixed(('H:7','H:8'),'hex nut (each) vs PECO/Hillman 100-pk')
        if has(t,r'washer') and not has(t,r'screw'): return W('H:7','H:8')*0.5,['H:7','H:8'],'washer est. 50% of hex nut',Lo
        m=re.search(r'(\d/\d{1,2})\s?-\s?\d{1,2}|(\d/\d{1,2})\s?(?:inch|in)\s?-',t)
        if m or has(t,r'bolt|cap screw|lag'):
            try: d=float(Fraction(m.group(1) or m.group(2))) if m else 0.375
            except ZeroDivisionError: d=0.375
            ln=re.search(r'x\s?'+FR,t)
            l=(_num(ln.group(1)) if ln else 2) or 2
            return W('H:4')*(d/0.5)**2*(max(l,0.5)/2),['H:4'],f'bolt/cap screw scaled by dia^2 x length vs CDE 1/2-13x2 ({d:g}in x {l:g}in)',M
        if has(t,r'self.?drill|tek|metal piercing|sheet metal|wood screw'): return fixed(('H:2',),'self-drilling/sheet-metal screw (each) vs Kimball Midwest 446006 per-100')
        if has(t,r'kit|assort'): return W('H:0')*1.5,['H:0'],'assorted fastener kit est. as ~150 machine screws',Lo
        return fixed(('H:0',),'machine screw (each) vs Tanner 10-32 box of 100')
    if cls=='lug':
        if has(t,r'crimp sleeve|sleeve|butt|splice'): return fixed(('H:15',),'compression splice/sleeve vs Burndy YS28',Lo) if has(t,r'mcm|kcmil|/0') else (W('H:10')*0.3,['H:10'],'small crimp sleeve est. 30% of #6 lug',Lo)
        if has(t,r'crimp|tool|cutter'): return fixed(('H2:3',),'crimp tool vs Accuglass HCT-1',Lo)
        if has(t,r'hub'): return est('emt_fitting',t+' hub')
        if has(t,r'mechanical|panelboard|offset|tap'): return fixed(('H:13','H:14'),'aluminum mechanical lug vs Ilsco TA-250')
        if has(t,r'splice|sleeve|butt'): return fixed(('H:15',),'compression splice vs Burndy YS28')
        m=re.search(r'(\d{3,4})\s?(?:mcm|kcmil)',t,re.I); a=re.search(r'(\d)/0',t); g=re.search(r'#?\b(\d{1,2})\s?(?:awg|ga\b)?',t)
        if m: x=int(m.group(1))
        elif a: x=[0,105.6,133.1,167.8,211.6][int(a.group(1))]
        else:
            n=re.search(r'#(\d{1,2})',t); 
            x={14:4.1,12:6.5,10:10.4,8:16.5,6:26.2,4:41.7,2:66.4,1:83.7}.get(int(n.group(1)),26.2) if n else None
        return cv(x,[(26.2,('H:10',)),(211.6,('H:11',)),(500,('H:12',))],'copper compression lug; conductor-size curve Burndy YA (kcmil)',26.2)
    if cls=='cable_gland': return cv(ts,[(0.5,('H:16',)),(1,('H2:13',))],'cable gland/cord grip; trade-size curve T&B nylon / Appleton metal',0.5)
    if cls=='wire_connector':
        big=has(t,r'(\d/0|\d{3}\s?(mcm|kcmil))')
        return fixed(('H:20','H:21') if big else ('H:18','H:19'),'insulated multi-tap connector vs NSI Polaris '+('large' if big else 'small'))
    if cls=='ground_clamp':
        if has(t,r'ground rod\b|rod,|copper.?bonded') and not has(t,r'clamp'): return cv(L,[(8,('H:23',))],'ground rod per length vs Erico 8ft',8)
        if has(t,r'bar'): return fixed(('H:24',),'ground/neutral bar vs Eaton GBK14')
        return fixed(('H:22',),'ground clamp/connector vs Dottie 29BRZ')
    if cls=='drill_bit':
        if has(t,r'glove'): return fixed(('H2:1','H2:2'),'work gloves vs Milwaukee pairs')
        if has(t,r'crimp|cutter|tool|fish|piston'): return fixed(('H2:3',),'hand tool vs hex crimp tool',Lo)
        if has(t,r'knockout|punch|die'): return W('H2:0')/4,['H2:0'],'single knockout punch/die est. 1/4 of Greenlee 7235BB kit',Lo
        if has(t,r'hole saw|hole cutter'): return fixed(('H:27',),'hole saw vs Milwaukee 2-1/8in')
        if has(t,r'sds|rotary|masonry|bell hanger|flex|\d{2} in'): return fixed(('H:28','H:29'),'long/SDS bit vs Bosch HC2081')
        if has(t,r'measuring tape|pull line'): return fixed(('H2:4',),'pull line/measuring tape vs 1000ft tape roll',Lo)
        return fixed(('H:25','H:26'),'drill/driver bit vs Milwaukee carded bit')
    if cls=='warning_tape': return fixed(('H2:4','H2:5'),'warning/marking tape roll vs 3in x 1000ft rolls',Lo if not has(t,'1000') else M)
    if cls=='wire_lowvolt':
        if has(t,r'clamp'): return est('ground_clamp',t)
        return cv(L,[(250,('H2:6',)),(500,('H2:7','H2:8'))],'12/2 landscape wire per length',250)
    if cls=='misc':
        if has(t,r'staple'): return W('H2:9')*0.5,['H2:9'],'cable staple (each) est. 50% of 7in cable tie',Lo
        if has(t,r'cable tie|zip tie'): return fixed(('H2:9',),'cable tie (each) vs Panduit PLT2S carton',Lo)
        if has(t,r'roof|flashing|jack'): return fixed(('H2:10',),'roof flashing/jack vs Oatey 12920')
        if has(t,r'expansion'): return fixed(('H2:11','H2:12'),'PVC expansion coupling vs Carlon E945')
        if has(t,r'glove'): return fixed(('H2:1','H2:2'),'gloves vs Milwaukee')
        if has(t,r'medallion'): return fixed(('B2:12','B2:13'),'ceiling medallion vs Ekena 16in')
        if has(t,r'cutter|tool|blade|saw'): return fixed(('H2:3',),'hand tool/blade vs hex crimp tool',Lo)
        if has(t,r'pedestal'): return fixed(('F2:1',),'electrical pedestal est. vs 3-gang cast floor box',Lo)
        return fixed(('F:24',),'misc small electrical accessory vs RACO 768 steel ring',Lo)
    raise KeyError(cls)

def est_c2(cls,t,w,L,s):
    M='Medium'; Lo='Low'
    def fx(keys,basis,conf=M): return W(*keys),list(keys),basis,conf
    C2=C2MAP
    if cls=='linear_arch':
        x=L if L else 4; conf=M if L else Lo
        if has(t,r'connector|end cap|joiner|accessor|cable|kit|bracket|lens|option') and not has(t,r'luminaire|light\b'): return est('channel_acc',t)
        kg,k=curve(x,C2['linear']); return kg,k,f'architectural linear LED per length (curve 4ft/8ft) x {x:g} ft'+('' if L else ' (length not stated; assumed 4ft)'),conf
    if cls=='under_cabinet':
        if has(t,r'puck'): return fx(C2['puck'],'LED puck light ref')
        if has(t,r'power supply|driver|transformer'): return est('driver',t)
        x=L*12 if L else (s if s and s>=8 else None)
        conf=M
        if x is None: x=24; conf=Lo
        kg,k=curve(x,C2['uc']); return kg,k,f'LED under cabinet; length curve x {x:g} in',conf
    if cls=='landscape_well':
        if has(t,r'underwater|pond|fountain'): return fx(C2['underwater'],'underwater light ref')
        if has(t,r'sleeve|trim|cover|lens'): return W(*C2['well'])*0.3,list(C2['well']),'well light accessory est. 30% of well light',Lo
        return fx(C2['well'],'in-grade well light ref')
    if cls=='landscape_path':
        if has(t,r'bollard'): 
            if has(t,r'head'): return W(*C2['bollard'])*0.35,list(C2['bollard']),'bollard head est. 35% of complete bollard',Lo
            return fx(C2['bollard'],'LED bollard ref')
        return fx(C2['path'],'landscape path light ref')
    if cls=='landscape_spot':
        if has(t,r'transformer|power'): return est('driver',t+' landscape')
        if has(t,r'step|brick|paver|deck|hardscape|bbq|mini'): return fx(C2['step'],'step/hardscape/accent light ref')
        if has(t,r'brass|bronze|copper|stainless'): return fx(C2['brass'],'brass/bronze directional spot ref')
        return fx(C2['alu'],'aluminum directional/spot ref')
    if cls=='light_fixture_generic':
        if has(t,r'solar'): return fx(C2['solar'],'LED solar light ref',Lo)
        if has(t,r'sign'): return est('flood',t)
        if has(t,r'crossbar|mounting pan|bracket|canopy'): return est('channel_acc',t+' bracket')
        if w and w>=30: return est('flood',t)
        if has(t,r'putting|landscape|outdoor|path|garden'): return fx(C2['alu'],'outdoor accent light ref',Lo)
        return est('downlight',t)
C2MAP={'linear':[(4,('C2:3',)),(8,('C2:4',))],'puck':('C2:25','C2:26'),'uc':[(12,('C2:20','C2:21')),(24,('C2:22','C2:23')),(36,('C2:24',))],
'well':('C2:5','C2:6'),'underwater':('C2:7','C2:8'),'path':('C2:9','C2:10'),'bollard':('C2:11','C2:12'),'step':('C2:16','C2:17','C2:18','C2:19'),
'brass':('C2:13',),'alu':('C2:14','C2:15'),'solar':('C2:27',),'sign':None}
