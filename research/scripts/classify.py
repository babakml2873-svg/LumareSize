import re
from classes import C
D={c:(re.compile(r,re.I),desc) for c,r,desc in C}
ORDER="""drill_bit warning_tape wire_lowvolt enclosure bushing_locknut screw_small lug ground_clamp cable_gland wire_connector hour_meter
conduit_body conduit_elbow tape_connector locking_plug pin_sleeve liquidtight emt_fitting strap_hanger floor_box_cover floor_box wp_cover box_cover wp_box elec_box
wallplate gfci usb_recept network_jack surge timer load_center breaker_mccb breaker disconnect fuse
trim housing
exit_emerg ceiling_fan vent_fan heater high_bay flood area_light wall_pack panel_troffer vapor_strip under_cabinet landscape_well landscape_path landscape_spot track_kit linear_arch chandelier pendant floor_lamp table_lamp vanity downlight track_head sconce flush_mount
occ_sensor keypad_remote dimmer
driver tape_light channel lamp_bulb fan_accessory lamp_shade track_accessory channel_acc receptacle switch light_fixture_generic misc""".split()
assert set(ORDER)==set(D), set(D)^set(ORDER)
FIXT=set("exit_emerg ceiling_fan vent_fan heater high_bay flood area_light wall_pack panel_troffer vapor_strip under_cabinet landscape_well landscape_path landscape_spot track_kit linear_arch chandelier pendant floor_lamp table_lamp vanity downlight track_head sconce flush_mount".split())
GUARD=re.compile(r"accessor|component|\blens|shroud|visor|louver|bracket|mounting kit|mount kit|replacement|\barms?\b|adapter|end cap|\bclips?\b|stake|spike|\bglass\b|\bshades?\b|canopy kit|\bplate\b|\bcover\b|grille|trim ring|extension|sleeve|\bstem\b|downrod|blades?\b|medallion|crossbar|mounting pan|\bpole\b(?! light)|wire guard|\bguard\b|junction box|\brail\b|connector|\bcable\b|limiter|transformer|power supply|driver|\bcontrols?\b|remote|switch\b|\bhub\b|ballast",re.I)
GENERIC=re.compile(r'^(lighting accessory|lighting component|lighting fixture|wiring device|electrical supplies|electrical accessory|lighting|accessory|accessories|controls|spektrum|led lighting component|led lighting accessory|electrical products?|outdoor lighting accessory|led fixture|fastener and support|misc.*|other|component|parts?|products?|general|hardware|)$',re.I)
def first(text, skipgen=False):
    g=bool(GUARD.search(text))
    for c in ORDER:
        if skipgen and c in('misc','light_fixture_generic'): continue
        if g and c in FIXT: continue
        if D[c][0].search(text): return c
    return None
def classify(typ, title, ptype, vendor='', desc=''):
    typ=(typ or '').strip(); ptype=(ptype or '').strip()
    if vendor=='Leviton' and typ in ('Wiring Device','Meter','Plug & Connector'):
        dd=re.sub(r'^.*?—|Genuine Leviton.*$','',desc)
        r=first(dd, True)
        if r: return r,'desc'
        typ=''
    if typ=='LED Retrofit Kit': typ='LED driver retrofit kit'
    title=(title or '')
    if vendor: title=re.sub(re.escape(vendor),' ',title,flags=re.I)
    if typ and not GENERIC.match(typ):
        c=first(typ, True)
        if c: return c,'type'
    if ptype and not GENERIC.match(ptype):
        c=first(ptype, True)
        if c: return c,'ptype'
    r=first(typ+' | '+title, True)
    if r: return r,'title'
    if desc:
        r=first(desc, True)
        if r: return r,'desc'
    return first(typ+' | '+title),'title-generic'
