#!/usr/bin/env python3
"""
리포트 HTML → 웹 배포용 폴더 (index.html + og.png)
==================================================
Usage:
    python make_share_page.py <report.html> <out_dir> [--base-url https://도메인/경로/]

- 리포트 표지에서 학원명·학교·제목·시험명을 읽어 링크 섬네일(og.png, 1200x630)을 만든다.
- 리포트 HTML 에 Open Graph 메타 태그(카카오톡·문자 링크 미리보기용)를 넣어 index.html 로 저장한다.
- --base-url 을 주면 og:image / og:url 을 절대 주소로 쓴다 (카카오톡 미리보기는 절대 주소가 필요).
"""
import base64
import html as htmllib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from convert_to_pdf import find_browser  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def text_of(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def read_cover(report):
    cover = re.search(r'<div class="cover">(.*?)<div class="page">', report, flags=re.DOTALL).group(1)
    logo = re.search(r'<img src="(data:[^"]+)"[^>]*class="cover-logo[^"]*"', cover)
    brand = re.search(r'<div class="brand">(.*?)</div>', cover, flags=re.DOTALL)
    h1 = re.search(r"<h1>(.*?)<br>\s*<span class=\"highlight\">(.*?)</span></h1>", cover, flags=re.DOTALL)
    sub = re.search(r'<div class="subtitle">(.*?)</div>', cover, flags=re.DOTALL)
    return {
        "logo": logo.group(1) if logo else "",
        "brand": text_of(brand.group(1)) if brand else "",
        "school": text_of(h1.group(1)) if h1 else "",
        "headline": text_of(h1.group(2)) if h1 else "",
        "subtitle": text_of(sub.group(1)) if sub else "",
    }


CARD = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1200px;height:630px;overflow:hidden}}
body{{font-family:'Pretendard','Malgun Gothic',sans-serif;background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);color:#fff;
  display:flex;align-items:center;gap:64px;padding:0 84px}}
.logo{{flex:0 0 auto;display:flex;align-items:center;justify-content:center;width:250px}}
.logo img{{max-width:250px;max-height:300px;display:block}}
.text{{flex:1;min-width:0;border-left:3px solid rgba(251,191,36,.55);padding-left:60px}}
.brand{{display:inline-block;padding:8px 22px;border:2px solid #fbbf24;color:#fbbf24;font-size:22px;font-weight:700;border-radius:30px;letter-spacing:2px;margin-bottom:30px}}
h1{{font-size:{size}px;font-weight:800;line-height:1.22;letter-spacing:-1.5px}}
h1 .hl{{color:#fbbf24;display:block}}
.sub{{font-size:30px;color:#cbd5e1;margin-top:26px;font-weight:500}}
</style></head><body>
<div class="logo">{logo}</div>
<div class="text">
  <div class="brand">{brand}</div>
  <h1>{school}<span class="hl">{headline}</span></h1>
  <div class="sub">{subtitle}</div>
</div>
</body></html>"""


def make_og(info, out_png):
    browser = find_browser()
    if not browser:
        raise RuntimeError("Chrome/Edge 를 찾지 못했습니다.")
    longest = max(len(info["school"]), len(info["headline"]))
    size = 84 if longest <= 8 else 72 if longest <= 11 else 60
    logo = f'<img src="{info["logo"]}" alt="">' if info["logo"] else ""
    card = CARD.format(size=size, logo=logo, **{k: htmllib.escape(v) for k, v in info.items() if k != "logo"})
    tmp = Path(tempfile.mkdtemp(prefix="og-card-"))
    try:
        (tmp / "card.html").write_text(card, encoding="utf-8")
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--no-first-run",
             f"--user-data-dir={tmp / 'profile'}", "--force-device-scale-factor=1", "--window-size=1200,630",
             "--virtual-time-budget=10000", f"--screenshot={out_png}", (tmp / "card.html").as_uri()],
            capture_output=True, timeout=120,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not os.path.exists(out_png):
        raise RuntimeError("섬네일 생성 실패")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = ""
    if "--base-url" in sys.argv:
        base = sys.argv[sys.argv.index("--base-url") + 1].rstrip("/") + "/"
        args.remove(sys.argv[sys.argv.index("--base-url") + 1])
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    report = Path(args[0]).read_text(encoding="utf-8")
    out = Path(args[1])
    out.mkdir(parents=True, exist_ok=True)

    info = read_cover(report)
    og_png = out / "og.png"
    make_og(info, str(og_png.resolve()))

    title = re.search(r"<title>(.*?)</title>", report, flags=re.DOTALL)
    title = text_of(title.group(1)) if title else f'{info["school"]} {info["headline"]}'
    desc = f'{info["subtitle"]} · {info["brand"]} 내신분석 리포트'.strip(" ·")
    meta = "\n".join(
        [
            f'<meta property="og:type" content="article">',
            f'<meta property="og:title" content="{htmllib.escape(title, quote=True)}">',
            f'<meta property="og:description" content="{htmllib.escape(desc, quote=True)}">',
            f'<meta property="og:image" content="{base}og.png">',
            f'<meta property="og:image:width" content="1200">',
            f'<meta property="og:image:height" content="630">',
            f'<meta property="og:site_name" content="{htmllib.escape(info["brand"], quote=True)}">',
            f'<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="description" content="{htmllib.escape(desc, quote=True)}">',
        ]
        + ([f'<meta property="og:url" content="{base}">'] if base else [])
    )
    report = re.sub(r'<meta property="og:[^>]*>\s*|<meta name="twitter:card"[^>]*>\s*|<meta name="description"[^>]*>\s*', "", report)
    report = report.replace("<title>", meta + "\n<title>", 1)
    (out / "index.html").write_text(report, encoding="utf-8")
    print(f"✅ {out / 'index.html'} + og.png ({og_png.stat().st_size // 1024} KB)")
    print(f"   제목: {title}\n   설명: {desc}")


if __name__ == "__main__":
    main()
