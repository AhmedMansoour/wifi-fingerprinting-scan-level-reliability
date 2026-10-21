"""Render faithful, looping GitHub README GIFs from approved static SVG previews.

This build-only script does not generate, infer, or change scientific values.
It animates the bar widths already present in three manually reviewed SVGs.
Dependencies: Pillow, CairoSVG. Run with --publish in GitHub Actions.
"""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
from copy import deepcopy
from xml.etree import ElementTree as ET
import hashlib
import re
import subprocess
import sys
import cairosvg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/assets/figures"
COLORS = {"#3279a9", "#08877e", "#cb7e43"}
KEYS = ("scan_comparison", "sqs_ablation", "evidence_matrix")


def bar_for(key, x, y, w, h, color):
    if color not in COLORS or y < 180 or w <= 0 or h > 21:
        return False
    if key == "scan_comparison":
        return x in (250, 766) and 250 <= y <= 421 and h == 13
    if key == "sqs_ablation":
        return x == 280 and 196 <= y <= 402 and h == 15
    if key == "evidence_matrix":
        return x in (486, 685, 884) and 184 <= y <= 409 and h == 20
    raise ValueError(key)


def source(key):
    p = ASSETS / ("preview_" + key + ".svg")
    original = ET.parse(p)
    raw_svg = p.read_text(encoding="utf8")
    cleared_svg = raw_svg
    bars = []
    for el in original.getroot():
        if not el.tag.endswith("rect"):
            continue
        x, y, w, h = (float(el.get(k, "0")) for k in ("x", "y", "width", "height"))
        color = el.get("fill")
        if bar_for(key, x, y, w, h, color):
            bars.append((x, y, w, h, color, float(el.get("rx", "0"))))
            old = ('<rect x="' + el.get("x") + '" y="' + el.get("y") +
                   '" width="' + el.get("width") + '" height="' + el.get("height") +
                   '" rx="' + el.get("rx") + '" fill="' + color + '"/>')
            assert cleared_svg.count(old) == 1, (key, old)
            cleared_svg = cleared_svg.replace(old, old.replace(
                ' width="' + el.get("width") + '"', ' width="0"', 1), 1)
    expected = {"scan_comparison": 7, "sqs_ablation": 6, "evidence_matrix": 24}
    assert len(bars) == expected[key], (key, len(bars))
    empty = cairosvg.svg2png(bytestring=cleared_svg.encode("utf8"),
                             output_width=1100, output_height=540)
    rendered = cairosvg.svg2png(url=str(p), output_width=1100, output_height=540)
    poster = Image.open(BytesIO(rendered)).convert("RGB")
    background = Image.open(BytesIO(empty)).convert("RGB")
    assert poster.size == background.size == (1100, 540)
    return poster, background, bars


def smooth(value):
    t = max(0.0, min(1.0, value))
    return t * t * (3 - 2 * t)


def progress(key, i, t):
    if t <= 0.05:
        return 1
    if t < 0.17:
        return 1 - smooth((t - 0.05) / 0.12)
    reveal = max(0.0, min(1.0, (t - 0.20) / 0.62))
    if key == "scan_comparison":
        return smooth((reveal - (i % 5) * 0.105) / 0.46)
    if key == "sqs_ablation":
        return smooth((reveal - i * 0.10) / 0.47)
    col, row = i % 3, i // 3
    return smooth((reveal - col * 0.16 - row * 0.037) / 0.32)


def render(key):
    poster, blank, bars = source(key)
    times = [0.0] + [i / 26 for i in range(1, 27)]
    frames = [poster]
    for t in times[1:-1]:
        img = blank.copy()
        painter = ImageDraw.Draw(img)
        for i, (x, y, width, h, color, radius) in enumerate(bars):
            w = width * progress(key, i, t)
            if w >= 0.7:
                painter.rounded_rectangle(
                    (round(x), round(y), round(x + w), round(y + h)),
                    radius=min(radius, w / 2), fill=color)
        frames.append(img)
    frames.append(poster)
    palette = poster.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
    quantized = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in frames]
    output = ASSETS / ("preview_" + key + ".gif")
    durations = [1100] + [92] * (len(quantized) - 2) + [1600]
    quantized[0].save(output, save_all=True, append_images=quantized[1:],
                      duration=durations, loop=0, optimize=True, disposal=2)
    gif = Image.open(output)
    assert gif.n_frames >= 20 and gif.size == (1100, 540)
    assert output.stat().st_size < 2_000_000
    print(output.relative_to(ROOT), output.stat().st_size, "bytes", gif.n_frames, "frames")
    return output


def publish(paths):
    pins = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf8")
    for path in pins:
        old = path.replace(".gif", ".svg")
        if text.count(old) == 1:
            text = text.replace(old, path, 1)
        elif text.count(path) != 1:
            raise ValueError("Expected exactly one approved preview: " + path)
    text = text.replace(
        "Three compact previews of the public research tools.",
        "Three animated previews of the public research tools. "
        "Bars reveal recorded values; the underlying measurements do not change.")
    readme.write_text(text, encoding="utf8")

    checker_path = ROOT / "scripts/check_public_release.py"
    checker = checker_path.read_text(encoding="utf8")
    definition = ("README_ANIMATED_PREVIEWS = {\n" +
                  "".join(f"    {key!r}: {value!r},\n" for key, value in sorted(pins.items())) +
                  "}\n")
    anchor = "README_PREVIEW_FIGURES = {"
    if "README_ANIMATED_PREVIEWS = {" not in checker:
        assert checker.count(anchor) == 1
        checker = checker.replace(anchor, definition + anchor)
    else:
        checker = re.sub(r"README_ANIMATED_PREVIEWS = \{.*?\}\n",
                         lambda _: definition, checker, count=1, flags=re.S)
    condition = "        if rel in README_PREVIEW_FIGURES:\n"
    if "        if rel in README_ANIMATED_PREVIEWS:\n" not in checker:
        assert checker.count(condition) == 1
        safety = (
            "        # Approved GIF previews: exact paths and SHA-256; all others forbidden.\n"
            "        if rel in README_ANIMATED_PREVIEWS:\n"
            "            if path.suffix.lower() != '.gif' or data[:6] not in (b'GIF87a', b'GIF89a'):\n"
            "                fail.append(rel+': malformed animated scientific preview')\n"
            "            if hashlib.sha256(data).hexdigest() != README_ANIMATED_PREVIEWS[rel]:\n"
            "                fail.append(rel+': animated scientific preview has an unapproved digest')\n"
            "            continue\n"
        )
        checker = checker.replace(condition, safety + condition)
    checker_path.write_text(checker, encoding="utf8")

    test_path = ROOT / "tests/unit/test_readme_visual_previews.py"
    tests = test_path.read_text(encoding="utf8")
    original = 'assert readme.count("docs/assets/figures/" + filename) == 1'
    revised = ('assert readme.count("docs/assets/figures/" + filename.replace(".svg", ".gif")) == 1\n'
               '        gif = FIGURES / filename.replace(".svg", ".gif")\n'
               '        assert gif.read_bytes()[:6] == b"GIF89a"\n'
               '        assert 0 < gif.stat().st_size < 2_000_000')
    if tests.count(original) == 1:
        tests = tests.replace(original, revised)
    elif revised not in tests:
        raise ValueError("Preview regression test does not match expected structure")
    test_path.write_text(tests, encoding="utf8")

    files = [readme, checker_path, test_path] + paths
    subprocess.run(["git", "add", *[p.relative_to(ROOT).as_posix() for p in files]],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/refresh_release_manifest.py", "--write"],
                   cwd=ROOT, check=True)
    subprocess.run(["git", "add", "metadata/public_release_manifest.json"],
                   cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/refresh_release_manifest.py", "--check"],
                   cwd=ROOT, check=True)


if __name__ == "__main__":
    results = [render(key) for key in KEYS]
    if "--publish" in sys.argv:
        publish(results)
