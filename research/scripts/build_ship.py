
SMALL={'screw_small','lug','cable_gland','wire_connector','emt_fitting','liquidtight','conduit_body','conduit_elbow','bushing_locknut','strap_hanger','ground_clamp','drill_bit','misc','box_cover','elec_box','wp_box','wp_cover','floor_box','floor_box_cover','enclosure','track_accessory','channel_acc','tape_connector','network_jack'}
DEV={'receptacle','gfci','usb_recept','switch','dimmer','keypad_remote','occ_sensor','timer','surge','wallplate','pin_sleeve','locking_plug','hour_meter','breaker','breaker_mccb','disconnect','fuse'}
def ship(net,cls):
    if cls in SMALL: return net*1.10+0.01,''
    if cls in DEV: return net*1.25+0.03,''
    if cls=='lamp_bulb': return net*1.40+0.03,''
    if net>5: return net*1.20+0.5,''
    return net*1.25+0.15,''
