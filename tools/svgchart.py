#!/usr/bin/env python3
"""svgchart.py — dependency-free SVG plotting primitives (stdlib only).

Why this exists: THE_PATH_TO_NUMBER_ONE.md names **Geometry Blindness** as a top-3 cause of our
plateau — 71 lens runs, all numeric, and nobody ever looked at a picture of the data. matplotlib is
not installable in the shipping container (zero pip deps, see Dockerfile), and a chart that only
renders on the author's laptop is not a system feature. So: plain text SVG, stdlib only.

Charts emit CSS CLASSES, not hardcoded colors, so the embedding page owns the theme (light/dark):
    .ax axis lines/ticks · .gr gridlines · .lb labels · .ti title
    .sa series A (train/reference) · .sb series B (test/candidate) · .pt scatter points
Usage as a library:
    from svgchart import overlay_hist, scatter, bars, PAGE_CSS
Self-test:  python3 svgchart.py > /tmp/t.html
"""
import math

PAGE_CSS = """
.chart{max-width:100%;height:auto;overflow:visible}
.chart .ax{stroke:currentColor;stroke-width:1;opacity:.55;fill:none}
.chart .gr{stroke:currentColor;stroke-width:1;opacity:.12;fill:none}
.chart .lb{fill:currentColor;opacity:.72;font:10px ui-monospace,SFMono-Regular,Menlo,monospace}
.chart .ti{fill:currentColor;opacity:.95;font:600 12px ui-sans-serif,system-ui,sans-serif}
.chart .sa{fill:#3b82f6;fill-opacity:.42;stroke:#3b82f6;stroke-width:1.2}
.chart .sb{fill:#f97316;fill-opacity:.42;stroke:#f97316;stroke-width:1.2}
.chart .pt{fill:#3b82f6;fill-opacity:.45;stroke:none}
.chart .zl{stroke:#ef4444;stroke-width:1;stroke-dasharray:3 3;opacity:.8;fill:none}
.legend{font:11px ui-monospace,monospace;opacity:.8}
.legend i{display:inline-block;width:10px;height:10px;margin:0 4px -1px 10px;border-radius:2px}
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _fmt(v):
    if v is None:
        return "—"
    a = abs(v)
    if v == int(v) and a < 1e6:
        return str(int(v))
    if a >= 1e6 or (a < 1e-3 and a > 0):
        return "%.2e" % v
    return "%.4g" % v


def histogram(vals, bins, lo, hi):
    """counts per bin over [lo,hi]; values outside are clamped into the edge bins."""
    if hi <= lo:
        hi = lo + 1.0
    w = (hi - lo) / bins
    out = [0] * bins
    for v in vals:
        i = int((v - lo) / w)
        if i < 0:
            i = 0
        elif i >= bins:
            i = bins - 1
        out[i] += 1
    return out, lo, w


def _axes(x0, y0, x1, y1, xlo, xhi, ymax, xticks=5, yticks=3):
    """returns svg fragment for frame + gridlines + tick labels"""
    p = ['<path class="ax" d="M%.1f %.1f L%.1f %.1f L%.1f %.1f"/>' % (x0, y0, x0, y1, x1, y1)]
    for i in range(yticks + 1):
        y = y1 - (y1 - y0) * i / yticks
        p.append('<path class="gr" d="M%.1f %.1f H%.1f"/>' % (x0, y, x1))
        p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="end">%s</text>'
                 % (x0 - 4, y + 3, esc(_fmt(ymax * i / yticks))))
    for i in range(xticks + 1):
        x = x0 + (x1 - x0) * i / xticks
        p.append('<path class="ax" d="M%.1f %.1f V%.1f"/>' % (x, y1, y1 + 3))
        p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                 % (x, y1 + 14, esc(_fmt(xlo + (xhi - xlo) * i / xticks))))
    return "".join(p)


def overlay_hist(a, b, title="", label_a="A", label_b="B", bins=32, w=460, h=190, note=""):
    """Two distributions on one axis, area-normalised so different Ns stay comparable.
    This is the picture that answers 'is test shaped like train?' — the question our all-numeric
    gap probes kept answering with a single scalar."""
    a = [v for v in a if v is not None and not math.isnan(v)]
    b = [v for v in b if v is not None and not math.isnan(v)] if b else []
    if not a and not b:
        return '<div class="lb">no numeric values</div>'
    allv = a + b
    lo, hi = min(allv), max(allv)
    if hi <= lo:
        hi = lo + 1.0
    # trim to 0.5–99.5 pct so one outlier cannot flatten the whole picture (it is reported instead)
    s = sorted(allv)
    q_lo, q_hi = s[int(0.005 * (len(s) - 1))], s[int(0.995 * (len(s) - 1))]
    if q_hi > q_lo:
        lo, hi = q_lo, q_hi
    ca, _, _ = histogram(a, bins, lo, hi)
    cb, _, _ = histogram(b, bins, lo, hi) if b else ([0] * bins, lo, 0)
    na, nb = max(1, len(a)), max(1, len(b))
    fa = [c / na for c in ca]
    fb = [c / nb for c in cb]
    ymax = max(max(fa), max(fb) if b else 0) or 1.0
    x0, y0, x1, y1 = 46.0, 26.0, float(w - 10), float(h - 22)
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, esc(title))]
    if title:
        out.append('<text class="ti" x="%.1f" y="16">%s</text>' % (x0 - 40, esc(title)))
    if note:
        out.append('<text class="lb" x="%.1f" y="16" text-anchor="end">%s</text>' % (x1, esc(note)))
    out.append(_axes(x0, y0, x1, y1, lo, hi, ymax))

    def step(fr, cls):
        bw = (x1 - x0) / bins
        d = ["M%.2f %.2f" % (x0, y1)]
        for i, f in enumerate(fr):
            yy = y1 - (y1 - y0) * (f / ymax)
            d.append("L%.2f %.2f L%.2f %.2f" % (x0 + i * bw, yy, x0 + (i + 1) * bw, yy))
        d.append("L%.2f %.2f Z" % (x1, y1))
        return '<path class="%s" d="%s"/>' % (cls, " ".join(d))

    out.append(step(fa, "sa"))
    if b:
        out.append(step(fb, "sb"))
    out.append("</svg>")
    leg = '<div class="legend"><i style="background:#3b82f6"></i>%s (n=%d)' % (esc(label_a), len(a))
    if b:
        leg += '<i style="background:#f97316"></i>%s (n=%d)' % (esc(label_b), len(b))
    leg += "</div>"
    return "".join(out) + leg


def scatter(xs, ys, title="", w=460, h=210, xlab="", ylab="", zero_line=False, maxpts=4000):
    pts = [(x, y) for x, y in zip(xs, ys)
           if x is not None and y is not None and not math.isnan(x) and not math.isnan(y)]
    if not pts:
        return '<div class="lb">no points</div>'
    if len(pts) > maxpts:                      # deterministic thinning (no RNG: resumable/reproducible)
        stride = len(pts) // maxpts + 1
        pts = pts[::stride]
    xlo, xhi = min(p[0] for p in pts), max(p[0] for p in pts)
    ylo, yhi = min(p[1] for p in pts), max(p[1] for p in pts)
    if xhi <= xlo:
        xhi = xlo + 1
    if yhi <= ylo:
        yhi = ylo + 1
    x0, y0, x1, y1 = 52.0, 26.0, float(w - 10), float(h - 22)
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, esc(title))]
    if title:
        out.append('<text class="ti" x="12" y="16">%s</text>' % esc(title))
    p = ['<path class="ax" d="M%.1f %.1f L%.1f %.1f L%.1f %.1f"/>' % (x0, y0, x0, y1, x1, y1)]
    for i in range(4):
        y = y1 - (y1 - y0) * i / 3
        p.append('<path class="gr" d="M%.1f %.1f H%.1f"/>' % (x0, y, x1))
        p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="end">%s</text>'
                 % (x0 - 4, y + 3, esc(_fmt(ylo + (yhi - ylo) * i / 3))))
    for i in range(5):
        x = x0 + (x1 - x0) * i / 4
        p.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                 % (x, y1 + 14, esc(_fmt(xlo + (xhi - xlo) * i / 4))))
    out.append("".join(p))
    if zero_line and ylo < 0 < yhi:
        yz = y1 - (y1 - y0) * (0 - ylo) / (yhi - ylo)
        out.append('<path class="zl" d="M%.1f %.1f H%.1f"/>' % (x0, yz, x1))
    r = 1.6 if len(pts) > 800 else 2.4
    dots = ['<circle class="pt" cx="%.1f" cy="%.1f" r="%.1f"/>'
            % (x0 + (x1 - x0) * (x - xlo) / (xhi - xlo),
               y1 - (y1 - y0) * (y - ylo) / (yhi - ylo), r) for x, y in pts]
    out.append("".join(dots))
    if xlab:
        out.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="end">%s</text>' % (x1, y0 - 12, esc(xlab)))
    if ylab:
        out.append('<text class="lb" x="12" y="%.1f">%s</text>' % (y0 - 12, esc(ylab)))
    out.append("</svg>")
    return "".join(out) + '<div class="legend">%d pts shown%s</div>' % (
        len(pts), " (thinned)" if len(pts) < len(xs) else "")


def bars(labels, values, title="", w=460, h=200, hi_first=True):
    if not values:
        return '<div class="lb">no values</div>'
    vmax = max(values) or 1.0
    x0, y0, x1, y1 = 46.0, 26.0, float(w - 10), float(h - 34)
    n = len(values)
    bw = (x1 - x0) / max(1, n)
    out = ['<svg class="chart" viewBox="0 0 %d %d" role="img" aria-label="%s">' % (w, h, esc(title))]
    if title:
        out.append('<text class="ti" x="12" y="16">%s</text>' % esc(title))
    out.append('<path class="ax" d="M%.1f %.1f L%.1f %.1f L%.1f %.1f"/>' % (x0, y0, x0, y1, x1, y1))
    for i in range(3):
        y = y1 - (y1 - y0) * i / 2
        out.append('<path class="gr" d="M%.1f %.1f H%.1f"/>' % (x0, y, x1))
        out.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="end">%s</text>'
                   % (x0 - 4, y + 3, esc(_fmt(vmax * i / 2))))
    for i, (lb, v) in enumerate(zip(labels, values)):
        hh = (y1 - y0) * (v / vmax)
        cls = "sb" if (hi_first and i == 0) else "sa"
        out.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"><title>%s: %s</title></rect>'
                   % (cls, x0 + i * bw + 1, y1 - hh, max(1.0, bw - 2), hh, esc(lb), esc(_fmt(v))))
        if n <= 16:
            out.append('<text class="lb" x="%.1f" y="%.1f" text-anchor="end" transform="rotate(-35 %.1f %.1f)">%s</text>'
                       % (x0 + i * bw + bw / 2, y1 + 12, x0 + i * bw + bw / 2, y1 + 12, esc(str(lb)[:16])))
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import random
    random.seed(7)
    a = [random.gauss(0, 1) for _ in range(4000)]
    b = [random.gauss(0.6, 1.4) for _ in range(1500)]
    print("<style>body{font-family:system-ui;margin:24px;color:#111;background:#fff}"
          "@media(prefers-color-scheme:dark){body{color:#eee;background:#111}}" + PAGE_CSS + "</style>")
    print(overlay_hist(a, b, "self-test: shifted test distribution", "train", "test", note="KS=0.23"))
    print(scatter([x for x in a[:900]], [x * 0.4 + random.gauss(0, .5) for x in a[:900]],
                  "self-test: residual vs prediction", zero_line=True))
    print(bars(["c1", "c2", "c3", "c4"], [0.31, 0.22, 0.09, 0.04], "self-test: drift by column"))
