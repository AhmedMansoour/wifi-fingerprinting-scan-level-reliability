"""Animate additional native scan examples and centroid-relative candidate neighborhoods.

Source is the public, fixed example export. UJIIndoorLoc U02 supplies
three query scans; U03 supplies two candidate neighborhoods. No HK examples,
floor plans, absolute coordinates, reconstructed building outlines, predicted
errors, thresholds, or warning labels are drawn. The x-y neighborhoods are
independently translated to their own centroids and rotated, preserving local
distances but not original map orientation or global placement.
"""
from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/assets/figures"
DATA = ROOT / "docs/assets/interactive/sample_scans.json"
NAVY=(17,45,69); TEAL=(8,131,121); BLUE=(49,116,166)
INK=(26,55,77); MUTED=(83,113,132); LINE=(217,230,237)
BG=(242,247,249); WHITE=(255,255,255); FAINT=(232,241,245)
GOLD=(199,124,62)
WIDTH, HEIGHT = 1100, 540
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def txt(draw, pos, words, size=14, color=INK, bold=False):
    draw.text(pos, str(words), font=font(size,bold), fill=color)


def rect(draw, box, fill, radius=11, outline=None):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=1 if outline else 0)


def scaffold(title, kicker, description):
    im=Image.new("RGB",(WIDTH,HEIGHT),BG); d=ImageDraw.Draw(im)
    rect(d,(0,0,1100,113),NAVY,16)
    d.rectangle((0,99,1100,113),fill=NAVY)
    txt(d,(32,18),kicker,12,(146,229,219),True)
    txt(d,(32,48),title,28,WHITE,True)
    txt(d,(32,121),description,13,MUTED)
    return im,d


def qimage(frames, name, durations):
    assert len(frames)==len(durations) and len(frames)>=10
    # Quantization keeps repository assets lightweight while retaining readable labels.
    base=frames[0].quantize(colors=160, method=Image.Quantize.MEDIANCUT)
    series=[im.quantize(palette=base,dither=Image.Dither.NONE) for im in frames]
    out=DIR/name
    series[0].save(out,save_all=True,append_images=series[1:],duration=durations,
                   optimize=True,loop=0,disposal=2)
    chk=Image.open(out)
    assert chk.size==(WIDTH,HEIGHT) and chk.n_frames>=10
    assert out.stat().st_size<2_000_000, (out, out.stat().st_size)
    print(out.relative_to(ROOT), out.stat().st_size,"bytes",chk.n_frames,"frames")
    return out


def scan_cases(data):
    """Three selected U02 cases, fixed deterministic extrema and mid-record."""
    examples=sorted(data["units"]["U02"]["examples"],key=lambda v:v["sqs"])
    assert len(examples)==22
    scans=[examples[0],examples[11],examples[-1]]
    assert len({v["row_id"] for v in scans})==3
    components=[
        ("signal_match","Signal match"),
        ("candidate_geometry","Candidate geometry"),
        ("ap_count","AP-count support"),
        ("ap_overlap","AP overlap"),
        ("local_density","Reference-point density")]
    frames=[];durations=[]
    def render(active,fade):
        im,d=scaffold("A single scan can tell a different story",
                      "04  /  ADDITIONAL MEASURED SCAN CASES",
                      "Three UJIIndoorLoc U02 observations, sorted within the same evaluation unit by SQS")
        for n,(scan,tag) in enumerate(zip(scans,("LOWER","MIDDLE","HIGHER"))):
            x=29+n*350;on=n==active;tone=TEAL if on else (78,105,127)
            rect(d,(x,164,x+336,262),WHITE,11,tone if on else LINE)
            d.rectangle((x+15,183,x+19,238),fill=tone)
            txt(d,(x+33,179),tag+" SQS",12,MUTED,True)
            txt(d,(x+33,201),scan["row_id"],14,INK,True)
            txt(d,(x+33,229),str(scan["ap_observations"])+" observed APs",12,MUTED)
            txt(d,(x+237,184),f'{scan["sqs"]:.3f}',23,tone,True)
        current=scans[active]
        rect(d,(29,278,1071,470),WHITE,12,LINE)
        txt(d,(49,297),"SQS SUPPORT COMPONENTS — "+current["row_id"],14,INK,True)
        for i,(key,label) in enumerate(components):
            v=float(current["components"][key])
            assert 0<=v<=1
            y=333+26*i
            txt(d,(51,y-4),label,13,INK)
            rect(d,(268,y-1,926,y+13),FAINT,7)
            w=658*v*fade
            if w>1:rect(d,(268,y-1,268+w,y+13),TEAL,7)
            txt(d,(950,y-6),f"{v:.3f}",13,INK,True)
        txt(d,(29,494),"Recorded values, not warning states. SQS is not a probability of positioning correctness.",12,MUTED)
        rect(d,(895,483,1071,523),(224,243,239),15)
        txt(d,(918,494),"OPEN EXPLORER  >",12,TEAL,True)
        return im
    for k in range(3):
        for step in range(12):
            t=min(1,step/9)
            factor=t*t*(3-2*t)
            frames.append(render(k,factor))
            durations.append(95 if step<11 else 800)
    return qimage(frames,"preview_additional_scan_cases.gif",durations),scans


def rotate_relative(scan,angle):
    cx,cy=scan["diagnostic_centroid"]
    rad=math.radians(angle);co,si=math.cos(rad),math.sin(rad)
    points=[]
    for cand in scan["candidates"]:
        dx,dy=cand["x"]-cx,cand["y"]-cy
        points.append((dx*co-dy*si,dx*si+dy*co))
    assert len(points)==10
    return points


def xy_cases(data):
    """Two U03 neighborhoods, independently centered and rotated (not aligned maps)."""
    examples=sorted(data["units"]["U03"]["examples"],key=lambda v:v["indicators"]["sigma_fps"])
    assert len(examples)==22
    compact=examples[0];dispersed=examples[-1]
    cases=[compact,dispersed]
    transformed=[rotate_relative(compact,31),rotate_relative(dispersed,-41)]
    assert compact["indicators"]["sigma_fps"]<dispersed["indicators"]["sigma_fps"]
    extent=max(abs(z) for points in transformed for p in points for z in p)
    bound=max(40,math.ceil(extent/10)*10)
    frames=[];durations=[]
    def render(count):
        im,d=scaffold("Local x-y candidate support: compact vs. dispersed",
                      "05  /  CANDIDATE GEOMETRY & NEIGHBORHOOD STABILITY",
                      "Ten ranked reference candidates per recorded UJIIndoorLoc U03 query; progressively reveal retrieval order")
        for n,scan in enumerate(cases):
            x=29+n*535
            rect(d,(x,166,x+505,471),WHITE,13,LINE)
            title="COMPACT EXAMPLE" if n==0 else "DISPERSED EXAMPLE"
            txt(d,(x+19,179),title,14,TEAL if n==0 else BLUE,True)
            txt(d,(x+19,202),scan["row_id"],13,MUTED)
            txt(d,(x+19,224),f'Spread: {scan["indicators"]["sigma_fps"]:.1f} m   Diameter: {scan["indicators"]["D_cand"]:.1f} m',13,INK)
            cx=x+255;cy=357
            d.line((cx-190,cy,cx+190,cy),fill=LINE,width=2)
            d.line((cx,cy-105,cx,cy+101),fill=LINE,width=2)
            d.line((cx-190,cy-105,cx+190,cy-105),fill=FAINT)
            d.line((cx-190,cy+101,cx+190,cy+101),fill=FAINT)
            sx=186/bound;sy=100/bound
            pts=[(cx+px*sx,cy-py*sy) for px,py in transformed[n]]
            for j,(xx,yy) in enumerate(pts[:count]):
                c=GOLD if j==0 else (TEAL if n==0 else BLUE)
                d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=c,outline=WHITE,width=1)
                if j==0:txt(d,(xx+9,yy-14),"1",11,GOLD,True)
            # The centered centroid cross is a reference marker, not ground truth.
            d.line((cx-9,cy,cx+9,cy),fill=NAVY,width=3)
            d.line((cx,cy-9,cx,cy+9),fill=NAVY,width=3)
            txt(d,(x+19,443),f"Retrieved: {count}/10  |  Origin: candidate centroid",12,MUTED)
        txt(d,(29,494),"Independent centroid-relative rotated frames (m); no absolute coordinates, floor plans, or floor labels.",12,MUTED)
        rect(d,(895,483,1071,523),(224,243,239),15)
        txt(d,(918,494),"OPEN EXPLORER  >",12,TEAL,True)
        return im
    for count in list(range(1,11))+[10]*10:
        frames.append(render(count));durations.append(200 if count<10 else 250)
    return qimage(frames,"preview_xy_candidate_cases.gif",durations),cases


def main():
    import json
    data=json.loads(DATA.read_text(encoding="utf8"))
    assert data["schema_version"]=="1.0" and data["no_calibrated_warning_labels"] is True
    assert set(("U02","U03")).issubset(data["units"])
    a,scans=scan_cases(data); b,cases=xy_cases(data)
    assert all(s["row_id"].startswith("U02-test-") for s in scans)
    assert all(s["row_id"].startswith("U03-test-") for s in cases)
    return (a,b)


if __name__=="__main__":
    main()
