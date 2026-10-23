import json, sys, re
data=json.load(open(sys.argv[1])); out=sys.argv[2]; width_mm=float(sys.argv[3])
total=sum(s['adv'] for s in data['segs']); k=width_mm/total; xh=data['xHeight']
px=1000/22.0
COL={'ink':'#2b1f19','accent':'#e7a54d','berry':'#f2557f'}
def spark(cx,cy,s):
    q=.16*s
    return f"M{cx} {cy-s} Q{cx+q} {cy-q} {cx+s} {cy} Q{cx+q} {cy+q} {cx} {cy+s} Q{cx-q} {cy+q} {cx-s} {cy} Q{cx-q} {cy-q} {cx} {cy-s} Z"
paths=[]; x=0; dots=[]
for seg in data['segs']:
    for g in seg['glyphs']:
        gx=x+g['x']
        paths.append((seg['role'],f'<path transform="translate({gx} 0)" d="{g["svg"]}"/>'))
        if g['char']=='ı': dots.append(gx+g['adv']/2)
    x+=seg['adv']
s_c=(dots[0], xh+7*px); b_c=(dots[1], xh+6.5*px)
extra=[('accent',f'<path d="{spark(s_c[0],s_c[1],4.6*px)}"/>'),('berry',f'<circle cx="{b_c[0]}" cy="{b_c[1]}" r="{3.6*px}"/>')]
by={}
for r,p in paths+extra: by.setdefault(r,[]).append(p)
H=1150; D=260
body=''.join(f'<g id="{r}" fill="{COL[r]}">{"".join(v)}</g>' for r,v in by.items())
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:.2f}mm" height="{(H+D)*k:.2f}mm" viewBox="0 {-H} {total} {H+D}">
<!-- ChAIpi wordmark (logo No. 8). Font: Unbounded SemiBold, SIL Open Font License 1.1. Font units are y-up, so the group flips y. -->
<g transform="scale(1,-1)">{body}</g></svg>'''
open(out,'w').write(svg)
json.dump({'k':k,'spark':s_c,'spark_r':4.6*px,'berry':b_c,'berry_r':3.6*px,'total':total},open(sys.argv[4],'w'))
print('svg written; mm per unit',round(k,5),'x-height mm',round(xh*k,2))
