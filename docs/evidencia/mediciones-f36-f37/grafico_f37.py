"""Genera un SVG de memory.current, memory.max y sub-tareas en curso desde un JSON de medir_f37.py."""
import json
import sys

datos = json.load(open(sys.argv[1], encoding="utf-8"))
ms = datos["muestras"]
w, h, m = 720, 320, 50
tmax = max(x["instante"] for x in ms)
ymax = datos["memory_max"] * 1.1
px = lambda t: m + t / tmax * (w - 2 * m)
py = lambda b: h - m - b / ymax * (h - 2 * m)
mem = " ".join(f"{px(x['instante']):.1f},{py(x['memory_current']):.1f}" for x in ms)
cur = " ".join(f"{px(x['instante']):.1f},{h - m - x['en_curso'] / (datos['plan']['cupo'] + 1) * (h - 2 * m) * 0.5:.1f}" for x in ms)
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" font-family="sans-serif" font-size="12">
<rect width="{w}" height="{h}" fill="white"/>
<line x1="{m}" y1="{h-m}" x2="{w-m}" y2="{h-m}" stroke="black"/><line x1="{m}" y1="{m}" x2="{m}" y2="{h-m}" stroke="black"/>
<line x1="{m}" y1="{py(datos['memory_max']):.1f}" x2="{w-m}" y2="{py(datos['memory_max']):.1f}" stroke="red" stroke-dasharray="6"/>
<text x="{m+4}" y="{py(datos['memory_max'])-4:.1f}" fill="red">memory.max = {datos['memory_max']//2**20} MiB</text>
<polyline points="{mem}" fill="none" stroke="steelblue" stroke-width="2"/>
<polyline points="{cur}" fill="none" stroke="darkgreen" stroke-width="2" stroke-dasharray="3"/>
<text x="{m}" y="20" fill="steelblue">azul: memory.current</text><text x="{m+170}" y="20" fill="darkgreen">verde: sub-tareas en curso (máx {datos['pico_en_curso']}, cupo {datos['plan']['cupo']}; escala propia)</text>
<text x="{w//2}" y="{h-12}">tiempo (s), 0 a {tmax}</text>
</svg>'''
open(sys.argv[2], "w", encoding="utf-8").write(svg)
