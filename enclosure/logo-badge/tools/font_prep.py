import sys, json
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont, OverlapMode
from fontTools.pens.svgPathPen import SVGPathPen
src, out_ttf, out_json = sys.argv[1], sys.argv[2], sys.argv[3]
f = TTFont(src)
inst = instantiateVariableFont(f, {"wght": 600}, overlap=OverlapMode.REMOVE)
inst.save(out_ttf)
f = TTFont(out_ttf)
upm = f['head'].unitsPerEm
cmap = f.getBestCmap(); gs = f.getGlyphSet(); hmtx = f['hmtx']
segs = [('ch','ink'),('a','accent'),('ı','accent'),('p','ink'),('ı','ink')]
res = {'upm': upm, 'xHeight': getattr(f['OS/2'],'sxHeight',0), 'segs': []}
for text, role in segs:
    glyphs = []
    x = 0
    for ch in text:
        gn = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[gn].draw(pen)
        glyphs.append({'char': ch, 'glyph': gn, 'x': x, 'adv': hmtx[gn][0], 'svg': pen.getCommands()})
        x += hmtx[gn][0]
    # kerning inside a segment is ignored (no kern between c and h in this font is fine)
    res['segs'].append({'text': text, 'role': role, 'adv': x, 'glyphs': glyphs})
json.dump(res, open(out_json, 'w'))
print('upm', upm, 'xHeight', res['xHeight'], 'advances', [s['adv'] for s in res['segs']])
