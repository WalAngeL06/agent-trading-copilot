"""Offline candlestick review of production SwingEngine output (HTML + PNG).

    python -m agent_trading.research.swing.chart
    python -m agent_trading.research.swing.chart --out runs/swing_review --no-png

Reads the saved candle fixtures in tests/data, runs the real
`agent_trading.swing.SwingEngine`, and writes one self-contained chart per
timeframe, a multiplier comparison, and a summary CSV. No network.

Layout is computed once into backend-neutral drawing primitives, then emitted
as SVG (stdlib, always available) or PNG (needs Pillow). One geometry, two
renderers -- the two formats cannot drift apart.

PNG needs an optional dependency:  pip install -e '.[research-charts]'

For human inspection only. It changes no algorithm and proves nothing about
trading quality; it exists so a person can judge whether the confirmed swings
look like meaningful turning points.

Reading the chart:

* the triangle sits on the candle where the extreme actually printed (swing_time)
* the dashed run forward to a hollow circle ends at confirmed_at, which is when
  a live agent would first have known
* the length of that dashed run IS the confirmation delay

The zigzag connects confirmed swings at their swing_time, never at confirmed_at.
"""

import argparse
import csv
from decimal import Decimal
from html import escape
from pathlib import Path

from ...swing import SwingConfig, SwingEngine, SwingSide
from .review import DEFAULT_TIMEFRAMES, load_series

STEP = 6.0             # horizontal pixels per candle
BODY = 3.0
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 74.0, 30.0, 80.0, 44.0

COLOR = {
    "bg": "#ffffff", "up": "#1a9a6c", "down": "#d2444a", "wick": "#5b6470",
    "grid": "#e6e8ec", "axis": "#8a929c", "ink": "#1d2430",
    "high": "#b5179e", "low": "#0466c8", "zig": "#7b8494",
}

FONT_CANDIDATES = ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/arial.ttf",
                   "/System/Library/Fonts/Menlo.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


def _f(value):
    """Decimal -> float for pixel geometry only. Prices stay Decimal in logic."""
    return float(value)


def detect(candles, config):
    """Run the production engine and return its confirmed swings."""
    engine = SwingEngine(candles[0].symbol, candles[0].timeframe, config)
    engine.bootstrap(candles)
    return engine.confirmed


def _nice_ticks(low, high, count=6):
    span = high - low
    if span <= 0:
        return [low]
    raw = span / count
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    step = max(1.0, round(raw / magnitude) * magnitude)
    ticks, value = [], (int(low / step)) * step
    while value <= high + step:
        if low - step <= value <= high + step:
            ticks.append(value)
        value += step
    return ticks


# ----------------------------------------------------------------- geometry

def panel_ops(candles, swings, *, height=420.0, title="", subtitle="", legend=True):
    """Backend-neutral drawing primitives for one candlestick panel."""
    count = len(candles)
    plot_w = count * STEP
    width = PAD_LEFT + plot_w + PAD_RIGHT
    total_h = PAD_TOP + height + PAD_BOTTOM
    low = min(_f(c.low) for c in candles)
    high = max(_f(c.high) for c in candles)
    span = (high - low) or 1.0
    low, high = low - span * 0.06, high + span * 0.06
    span = high - low

    def x(index):
        return PAD_LEFT + index * STEP + STEP / 2

    def y(price):
        return PAD_TOP + height - ((_f(price) - low) / span) * height

    ops = []
    if title:
        ops.append({"k": "text", "x": PAD_LEFT, "y": 24, "s": title, "size": 14,
                    "fill": COLOR["ink"], "weight": "700", "anchor": "start"})
    if subtitle:
        ops.append({"k": "text", "x": PAD_LEFT, "y": 42, "s": subtitle, "size": 11,
                    "fill": COLOR["axis"], "weight": "400", "anchor": "start"})
    if legend:
        ops.extend(_legend_ops(PAD_LEFT, 62))

    for tick in _nice_ticks(low, high):
        ty = y(tick)
        if not (PAD_TOP - 1 <= ty <= PAD_TOP + height + 1):
            continue
        ops.append({"k": "line", "x1": PAD_LEFT, "y1": ty, "x2": PAD_LEFT + plot_w,
                    "y2": ty, "stroke": COLOR["grid"], "width": 1})
        ops.append({"k": "text", "x": PAD_LEFT - 8, "y": ty + 3,
                    "s": format(tick, ",.0f"), "size": 10, "fill": COLOR["axis"],
                    "anchor": "end"})

    every = max(1, count // 10)
    for index in range(0, count, every):
        ops.append({"k": "text", "x": x(index), "y": PAD_TOP + height + 16,
                    "s": candles[index].close_time.strftime("%m-%d %H:%M"),
                    "size": 9, "fill": COLOR["axis"], "anchor": "middle"})

    for index, candle in enumerate(candles):
        cx = x(index)
        color = COLOR["up"] if candle.close >= candle.open else COLOR["down"]
        tip = ("%s  O %s  H %s  L %s  C %s"
               % (candle.close_time.strftime("%Y-%m-%d %H:%M"), candle.open,
                  candle.high, candle.low, candle.close))
        ops.append({"k": "line", "x1": cx, "y1": y(candle.high), "x2": cx,
                    "y2": y(candle.low), "stroke": COLOR["wick"], "width": 1})
        top, bottom = y(max(candle.open, candle.close)), y(min(candle.open, candle.close))
        ops.append({"k": "rect", "x": cx - BODY / 2, "y": top, "w": BODY,
                    "h": max(1.0, bottom - top), "fill": color, "title": tip})

    index_of = {candle.close_time: index for index, candle in enumerate(candles)}
    points = [(x(index_of[s.swing_time]), y(s.price))
              for s in swings if s.swing_time in index_of]
    if len(points) > 1:
        ops.append({"k": "polyline", "pts": points, "stroke": COLOR["zig"],
                    "width": 1.4, "opacity": 0.85})

    for swing in swings:
        si = index_of.get(swing.swing_time)
        ci = index_of.get(swing.confirmed_at)
        if si is None:
            continue
        is_high = swing.side is SwingSide.HIGH
        color = COLOR["high"] if is_high else COLOR["low"]
        sx, sy = x(si), y(swing.price)
        if ci is not None:
            # The delay drawn to scale: extreme -> when it became knowable.
            # This horizontal run is the point of the chart, so it carries the
            # emphasis; the vertical tick only anchors the confirming column.
            ops.append({"k": "line", "x1": sx, "y1": sy, "x2": x(ci), "y2": sy,
                        "stroke": color, "width": 1.6, "dash": (3, 2)})
            edge = PAD_TOP if is_high else PAD_TOP + height
            ops.append({"k": "line", "x1": x(ci), "y1": sy, "x2": x(ci), "y2": edge,
                        "stroke": color, "width": 1, "dash": (1, 4), "opacity": 0.3})
            ops.append({"k": "circle", "cx": x(ci), "cy": sy, "r": 3.4,
                        "stroke": color, "fill": COLOR["bg"], "width": 1.6,
                        "title": "confirmed_at %s (delay %d bars)"
                                 % (swing.confirmed_at.strftime("%Y-%m-%d %H:%M"),
                                    swing.confirmation_delay_bars)})
        offset = -11 if is_high else 11
        ops.append({"k": "poly",
                    "pts": [(sx, sy + offset * 0.35), (sx - 4.6, sy + offset),
                            (sx + 4.6, sy + offset)],
                    "fill": color,
                    "title": ("%s swing %s | swing_time %s | confirmed_at %s | "
                              "delay %d bars | ATR %s threshold %s"
                              % (swing.side.value, swing.price,
                                 swing.swing_time.strftime("%Y-%m-%d %H:%M"),
                                 swing.confirmed_at.strftime("%Y-%m-%d %H:%M"),
                                 swing.confirmation_delay_bars,
                                 swing.atr.quantize(Decimal("0.01")),
                                 swing.threshold.quantize(Decimal("0.01"))))})
    return ops, width, total_h


def _legend_ops(x0, y0):
    """Drawn into the image so a bare PNG still explains itself."""
    ops, cursor = [], x0
    for color, label, up in ((COLOR["high"], "swing high at swing_time", False),
                             (COLOR["low"], "swing low at swing_time", True)):
        tip = ((cursor + 4, y0 - 7), (cursor, y0 - 1), (cursor + 8, y0 - 1)) if up else \
              ((cursor + 4, y0 - 1), (cursor, y0 - 7), (cursor + 8, y0 - 7))
        ops.append({"k": "poly", "pts": list(tip), "fill": color})
        ops.append({"k": "text", "x": cursor + 13, "y": y0 - 1, "s": label,
                    "size": 10, "fill": COLOR["axis"], "anchor": "start"})
        cursor += 13 + len(label) * 6.2 + 22
    ops.append({"k": "line", "x1": cursor, "y1": y0 - 4, "x2": cursor + 18, "y2": y0 - 4,
                "stroke": COLOR["ink"], "width": 1.4, "dash": (3, 2)})
    ops.append({"k": "circle", "cx": cursor + 22, "cy": y0 - 4, "r": 3.4,
                "stroke": COLOR["ink"], "fill": COLOR["bg"], "width": 1.4})
    label = "dashed run to circle = confirmed_at (length = confirmation delay)"
    ops.append({"k": "text", "x": cursor + 30, "y": y0 - 1, "s": label,
                "size": 10, "fill": COLOR["axis"], "anchor": "start"})
    cursor += 30 + len(label) * 6.2 + 22
    ops.append({"k": "line", "x1": cursor, "y1": y0 - 4, "x2": cursor + 18, "y2": y0 - 4,
                "stroke": COLOR["zig"], "width": 1.6})
    ops.append({"k": "text", "x": cursor + 24, "y": y0 - 1,
                "s": "zigzag joins swings at swing_time", "size": 10,
                "fill": COLOR["axis"], "anchor": "start"})
    return ops


# -------------------------------------------------------------- SVG backend

_ANCHOR_SVG = {"start": "start", "middle": "middle", "end": "end"}


def ops_to_svg(ops, width, height):
    out = ['<svg width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f" '
           'xmlns="http://www.w3.org/2000/svg" font-family="ui-monospace,'
           'SFMono-Regular,Menlo,Consolas,monospace">' % (width, height, width, height),
           '<rect width="100%%" height="100%%" fill="%s"/>' % COLOR["bg"]]
    for op in ops:
        title = op.get("title")
        inner = "<title>%s</title>" % escape(title) if title else ""
        kind = op["k"]
        if kind == "line":
            dash = (' stroke-dasharray="%g,%g"' % op["dash"]) if op.get("dash") else ""
            opacity = (' stroke-opacity="%g"' % op["opacity"]) if op.get("opacity") else ""
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                       'stroke-width="%g"%s%s/>'
                       % (op["x1"], op["y1"], op["x2"], op["y2"], op["stroke"],
                          op["width"], dash, opacity))
        elif kind == "rect":
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s">%s</rect>'
                       % (op["x"], op["y"], op["w"], op["h"], op["fill"], inner))
        elif kind == "poly":
            pts = " ".join("%.1f,%.1f" % p for p in op["pts"])
            out.append('<polygon points="%s" fill="%s">%s</polygon>' % (pts, op["fill"], inner))
        elif kind == "polyline":
            pts = " ".join("%.1f,%.1f" % p for p in op["pts"])
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%g" '
                       'stroke-opacity="%g"/>'
                       % (pts, op["stroke"], op["width"], op.get("opacity", 1)))
        elif kind == "circle":
            out.append('<circle cx="%.1f" cy="%.1f" r="%g" fill="%s" stroke="%s" '
                       'stroke-width="%g">%s</circle>'
                       % (op["cx"], op["cy"], op["r"], op["fill"], op["stroke"],
                          op["width"], inner))
        elif kind == "text":
            out.append('<text x="%.1f" y="%.1f" font-size="%g" text-anchor="%s" '
                       'fill="%s" font-weight="%s">%s</text>'
                       % (op["x"], op["y"], op["size"], _ANCHOR_SVG[op.get("anchor", "start")],
                          op["fill"], op.get("weight", "400"), escape(op["s"])))
    out.append("</svg>")
    return "".join(out)


# -------------------------------------------------------------- PNG backend

_ANCHOR_PIL = {"start": "ls", "middle": "ms", "end": "rs"}


def _require_pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise SystemExit(
            "PNG output needs Pillow. Install the optional research extra:\n"
            "    pip install -e '.[research-charts]'\n"
            "or re-run with --no-png for HTML only.") from exc
    return Image, ImageDraw, ImageFont


def _font(ImageFont, size):
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _dashed(draw, xy, fill, width, dash):
    """Pillow has no dash support, so walk the segment."""
    (x1, y1), (x2, y2) = xy
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length == 0:
        return
    on, off = dash
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    position = 0.0
    while position < length:
        end = min(position + on, length)
        draw.line([(x1 + ux * position, y1 + uy * position),
                   (x1 + ux * end, y1 + uy * end)], fill=fill, width=width)
        position = end + off


def _blend(color, opacity, background=(255, 255, 255)):
    """Flatten opacity against the panel background; PIL draws opaque."""
    value = color.lstrip("#")
    rgb = tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(round(c * opacity + b * (1 - opacity)))
                 for c, b in zip(rgb, background))


def ops_to_image(ops, width, height, scale=2):
    """Render primitives at `scale` then downsample for clean edges."""
    Image, ImageDraw, ImageFont = _require_pillow()
    image = Image.new("RGB", (int(width * scale), int(height * scale)), COLOR["bg"])
    draw = ImageDraw.Draw(image)
    fonts = {}

    def s(value):
        return value * scale

    for op in ops:
        kind = op["k"]
        if kind == "line":
            color = _blend(op["stroke"], op.get("opacity", 1))
            width_px = max(1, int(round(op["width"] * scale)))
            xy = [(s(op["x1"]), s(op["y1"])), (s(op["x2"]), s(op["y2"]))]
            if op.get("dash"):
                _dashed(draw, xy, color, width_px,
                        (op["dash"][0] * scale, op["dash"][1] * scale))
            else:
                draw.line(xy, fill=color, width=width_px)
        elif kind == "rect":
            draw.rectangle([s(op["x"]), s(op["y"]), s(op["x"] + op["w"]),
                            s(op["y"] + op["h"])], fill=op["fill"])
        elif kind == "poly":
            draw.polygon([(s(px), s(py)) for px, py in op["pts"]], fill=op["fill"])
        elif kind == "polyline":
            draw.line([(s(px), s(py)) for px, py in op["pts"]],
                      fill=_blend(op["stroke"], op.get("opacity", 1)),
                      width=max(1, int(round(op["width"] * scale))))
        elif kind == "circle":
            r = s(op["r"])
            draw.ellipse([s(op["cx"]) - r, s(op["cy"]) - r, s(op["cx"]) + r,
                          s(op["cy"]) + r], fill=op["fill"], outline=op["stroke"],
                         width=max(1, int(round(op["width"] * scale))))
        elif kind == "text":
            size = int(op["size"] * scale)
            if size not in fonts:
                fonts[size] = _font(ImageFont, size)
            draw.text((s(op["x"]), s(op["y"])), op["s"], font=fonts[size],
                      fill=op["fill"], anchor=_ANCHOR_PIL[op.get("anchor", "start")])
    return image.resize((int(width), int(height)), Image.LANCZOS)


def stack_images(images, path, gap=14):
    """Compose comparison panels into one tall PNG."""
    Image, _, _ = _require_pillow()
    width = max(image.width for image in images)
    height = sum(image.height for image in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (width, height), COLOR["bg"])
    offset = 0
    for image in images:
        canvas.paste(image, (0, offset))
        offset += image.height + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return path


# ------------------------------------------------------------------- output

CSS = """
:root{color-scheme:light}
body{margin:0;background:#f6f7f9;color:#1d2430;
 font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
header{padding:18px 22px 10px}
h1{margin:0 0 4px;font-size:17px}
.meta{color:#697080;font-size:12px}
.note{margin:10px 22px;padding:10px 12px;background:#fff6e5;border-left:3px solid #e0a33a;
 font-size:12px;color:#5c4813}
.panel{margin:0 22px 22px;background:#fff;border:1px solid #e6e8ec;border-radius:8px;
 overflow-x:auto}
table{border-collapse:collapse;margin:6px 22px 24px;font-size:12px;background:#fff}
th,td{border:1px solid #e6e8ec;padding:5px 12px;text-align:right}
th:first-child,td:first-child{text-align:left}
th{background:#f0f2f5}
footer{padding:4px 22px 28px;color:#8a929c;font-size:11px}
"""


def _document(title, meta, body):
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title><style>%s</style></head><body>"
            "<header><h1>%s</h1><div class=\"meta\">%s</div></header>"
            "<div class=\"note\">Markers sit on the candle where the extreme printed "
            "(<b>swing_time</b>). The dashed run ends at <b>confirmed_at</b> — its length "
            "is the confirmation delay. A swing is never drawn at confirmed_at.</div>"
            "%s<footer>Research artifact. Hypothesis [H] detection; not a validated "
            "trading rule and not wired to any decision.</footer></body></html>"
            % (escape(title), CSS, escape(title), escape(meta), body))


def stats(candles, swings):
    delays = [s.confirmation_delay_bars for s in swings]
    return {
        "candles": len(candles),
        "confirmed": len(swings),
        "highs": sum(1 for s in swings if s.side is SwingSide.HIGH),
        "lows": sum(1 for s in swings if s.side is SwingSide.LOW),
        "per_100": round(len(swings) * 100 / len(candles), 1),
        "avg_delay": round(sum(delays) / len(delays), 2) if delays else "",
        "max_delay": max(delays) if delays else "",
        "min_delay": min(delays) if delays else "",
    }


def base_name(symbol, timeframe):
    return "%s_%s_swings" % (symbol.replace("-", ""), timeframe)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render SwingEngine review charts (offline)")
    parser.add_argument("--data", default="tests/data")
    parser.add_argument("--out", default="runs/swing_review")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--multiplier", default="1.25")
    parser.add_argument("--compare-timeframe", default="15m")
    parser.add_argument("--compare-multipliers", default="0.75,1.0,1.25,1.5,2.0")
    parser.add_argument("--no-png", action="store_true", help="skip PNG (no Pillow needed)")
    parser.add_argument("--no-html", action="store_true")
    args = parser.parse_args(argv)

    series = load_series(args.data, args.symbol, DEFAULT_TIMEFRAMES)
    if not series:
        print("No saved candles in %s. Run agent_trading.swing_smoke first." % args.data)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    config = SwingConfig(atr_length=args.atr_length, atr_multiplier=Decimal(args.multiplier))
    multipliers = tuple(m.strip() for m in args.compare_multipliers.split(",") if m.strip())
    written, summary, rows = [], [], []

    for timeframe, candles in series.items():
        swings = detect(candles, config)
        info = stats(candles, swings)
        subtitle = ("ATR length %d x multiplier %s   |   %s to %s   |   mean delay %s bars, "
                    "max %s" % (args.atr_length, args.multiplier,
                                candles[0].close_time.strftime("%Y-%m-%d %H:%M"),
                                candles[-1].close_time.strftime("%Y-%m-%d %H:%M"),
                                info["avg_delay"], info["max_delay"]))
        ops, width, height = panel_ops(
            candles, swings, height=430,
            title="%s %s — %d candles, %d confirmed swings"
                  % (args.symbol, timeframe, len(candles), len(swings)),
            subtitle=subtitle)
        stem = base_name(args.symbol, timeframe)
        if not args.no_html:
            path = out / (stem + ".html")
            path.write_text(_document(
                "%s %s swings" % (args.symbol, timeframe),
                "SwingEngine v0.1 · ATR(%d) x %s · %d confirmed · mean delay %s · max %s"
                % (args.atr_length, args.multiplier, len(swings),
                   info["avg_delay"], info["max_delay"]),
                '<div class="panel">%s</div>' % ops_to_svg(ops, width, height)),
                encoding="utf-8")
            written.append(path)
        if not args.no_png:
            path = out / (stem + ".png")
            ops_to_image(ops, width, height).save(path)
            written.append(path)
        summary.append((timeframe, info))

    for timeframe, candles in series.items():
        for multiplier in multipliers:
            swept = detect(candles, SwingConfig(atr_length=args.atr_length,
                                                atr_multiplier=Decimal(multiplier)))
            info = stats(candles, swept)
            rows.append({
                "symbol": args.symbol, "timeframe": timeframe,
                "atr_length": args.atr_length, "atr_multiplier": multiplier,
                "candles": info["candles"],
                "first_close": candles[0].close_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_close": candles[-1].close_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "confirmed_swings": info["confirmed"], "swing_highs": info["highs"],
                "swing_lows": info["lows"], "swings_per_100_bars": info["per_100"],
                "avg_confirmation_delay_bars": info["avg_delay"],
                "min_confirmation_delay_bars": info["min_delay"],
                "max_confirmation_delay_bars": info["max_delay"],
                "is_default_config": multiplier == args.multiplier,
            })

    csv_path = out / "swing_review_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    written.append(csv_path)

    compare = args.compare_timeframe
    if compare in series:
        candles = series[compare]
        images, panels, table = [], [], []
        for multiplier in multipliers:
            swept = detect(candles, SwingConfig(atr_length=args.atr_length,
                                                atr_multiplier=Decimal(multiplier)))
            info = stats(candles, swept)
            ops, width, height = panel_ops(
                candles, swept, height=215, legend=(multiplier == multipliers[0]),
                title="%s %s — ATR(%d) x %s — %d confirmed swings"
                      % (args.symbol, compare, args.atr_length, multiplier, len(swept)),
                subtitle="mean delay %s bars, max %s bars, %s per 100 bars"
                         % (info["avg_delay"], info["max_delay"], info["per_100"]))
            panels.append('<div class="panel">%s</div>' % ops_to_svg(ops, width, height))
            table.append((multiplier, info))
            if not args.no_png:
                images.append(ops_to_image(ops, width, height))
        if not args.no_html:
            head = ["<table><tr><th>multiplier</th><th>confirmed</th><th>per 100 bars</th>"
                    "<th>mean delay</th><th>max delay</th></tr>"]
            for multiplier, info in table:
                head.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                            % (multiplier, info["confirmed"], info["per_100"],
                               info["avg_delay"], info["max_delay"]))
            head.append("</table>")
            path = out / ("compare_%s_multipliers.html" % compare)
            path.write_text(_document(
                "%s %s multiplier comparison" % (args.symbol, compare),
                "Same %d candles in every panel; only the ATR multiplier changes."
                % len(candles), "".join(head) + "".join(panels)), encoding="utf-8")
            written.append(path)
        if not args.no_png:
            written.append(stack_images(images, out / ("compare_%s_multipliers.png" % compare)))

    header = "%-10s %8s %10s %7s %7s %12s %11s" % (
        "timeframe", "candles", "confirmed", "highs", "lows", "avg_delay", "max_delay")
    print("# SwingEngine v0.1  ATR(%d) x %s   [H] hypothesis detection"
          % (args.atr_length, args.multiplier))
    print(header)
    print("-" * len(header))
    for timeframe, info in summary:
        print("%-10s %8d %10d %7d %7d %12s %11s"
              % (timeframe, info["candles"], info["confirmed"], info["highs"],
                 info["lows"], info["avg_delay"], info["max_delay"]))
    print("\n# generated (gitignored)")
    for path in written:
        print("  %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
