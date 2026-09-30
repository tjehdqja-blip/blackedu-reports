#!/usr/bin/env python3
"""
HTML → PDF 변환 (시험지 분석 리포트용)
======================================
Usage:
    python convert_to_pdf.py <input.html> <output.pdf>

동작:
    1. Playwright 가 설치돼 있으면 Playwright 로 변환한다.
    2. 없으면 PC 에 설치된 Chrome / Edge / Chromium 을 headless 로 직접 실행해 변환한다.
       (Windows · macOS · Linux 공통. 브라우저 경로는 CHROME_PATH 환경변수로 지정 가능)
    3. 변환 뒤 두 가지를 확인해 알려 준다.
       - KaTeX 수식이 실제로 렌더링됐는지 (KaTeX elements rendered: N)
       - PDF 쪽수가 HTML 의 페이지 블록 수와 같은지 (다르면 어느 쪽이 넘쳤는지)

종료 코드:
    0 = 정상 / 1 = 변환 실패 / 2 = PDF 는 만들었지만 수식 미렌더링 또는 쪽 넘침
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 윈도 콘솔(cp949)에서 이모지·한글 출력 시 UnicodeEncodeError 방지
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

VIRTUAL_TIME_MS = 20000  # 폰트·KaTeX 로딩과 번호 매김 스크립트가 끝날 시간


def find_browser():
    """Chrome 계열 브라우저 실행 파일을 찾는다. 없으면 None."""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env

    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    patterns = [
        # Windows
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(local, "ms-playwright", "chromium-*", "chrome-win*", "chrome.exe"),
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.path.join(home, "Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium"),
        # Linux / 클라우드 컨테이너
        "/opt/pw-browsers/chromium-*/chrome-linux*/chrome",
        os.path.join(home, ".cache/ms-playwright/chromium-*/chrome-linux*/chrome"),
        "/root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
        os.path.join(home, ".cache/puppeteer/chrome/linux-*/chrome-linux*/chrome"),
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for pattern in patterns:
        if not pattern:
            continue
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def strip_comments(html):
    return re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)


def expected_page_count(html):
    """표지 1쪽 + .page 블록 수."""
    body = strip_comments(html)
    pages = len(re.findall(r'<div\s+class="page(?:\s[^"]*)?"', body))
    return pages + 1


def has_math(html):
    body = strip_comments(html)
    body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.DOTALL)
    return "$" in body


def convert_with_playwright(html_path, pdf_path, browser_path):
    """Playwright 경로. 설치돼 있지 않으면 ImportError."""
    import asyncio
    from playwright.async_api import async_playwright

    async def run():
        launch_args = {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        if browser_path:
            launch_args["executable_path"] = browser_path
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_args)
            page = await browser.new_page()
            await page.goto(Path(html_path).as_uri(), wait_until="networkidle")
            await page.evaluate(
                """
                async () => {
                    for (let i = 0; i < 100 && typeof renderMathInElement === 'undefined'; i++) {
                        await new Promise(r => setTimeout(r, 50));
                    }
                    if (typeof renderMathInElement !== 'undefined' && !document.querySelector('.katex')) {
                        renderMathInElement(document.body, {
                            delimiters: [
                                {left: '$$', right: '$$', display: true},
                                {left: '$', right: '$', display: false}
                            ],
                            ignoredClasses: ['no-math'],
                            throwOnError: false
                        });
                    }
                    if (document.fonts && document.fonts.ready) { await document.fonts.ready; }
                    await new Promise(r => setTimeout(r, 1000));
                }
                """
            )
            await page.emulate_media(media="print")
            katex_count = await page.evaluate("document.querySelectorAll('.katex').length")
            await page.pdf(path=pdf_path, print_background=True, prefer_css_page_size=True)
            await browser.close()
            return katex_count

    return asyncio.run(run())


def convert_with_cli(html_path, pdf_path, browser_path, check_math):
    """설치된 Chrome/Edge 를 headless 로 직접 실행."""
    uri = Path(html_path).as_uri()
    profile = tempfile.mkdtemp(prefix="exam-report-chrome-")
    base = [
        browser_path,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile}",
        f"--virtual-time-budget={VIRTUAL_TIME_MS}",
    ]
    katex_count = None
    try:
        if check_math:
            dom = subprocess.run(base + ["--dump-dom", uri], capture_output=True, timeout=180)
            rendered = dom.stdout.decode("utf-8", errors="replace")
            katex_count = len(re.findall(r'class="katex"', rendered))
        result = subprocess.run(
            base + ["--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", uri],
            capture_output=True,
            timeout=180,
        )
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            err = result.stderr.decode("utf-8", errors="replace")[-800:]
            raise RuntimeError(f"브라우저가 PDF 를 만들지 못했습니다.\n{err}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return katex_count


def inspect_pdf(pdf_path):
    """(쪽수, 넘친 쪽 목록 또는 None). pypdf 가 없으면 쪽수만 센다."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        overflow = []
        marker = re.compile(r"\d+\s*/\s*\d+\s*페이지")
        for i, page in enumerate(reader.pages):
            if i == 0:
                continue  # 표지
            text = page.extract_text() or ""
            if not marker.search(text):
                overflow.append(i + 1)
        return len(reader.pages), overflow
    except ImportError:
        data = Path(pdf_path).read_bytes()
        return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data)), None


def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_to_pdf.py <input.html> <output.pdf>")
        sys.exit(1)

    html_path = os.path.abspath(sys.argv[1])
    pdf_path = os.path.abspath(sys.argv[2])
    if not os.path.exists(html_path):
        print(f"❌ HTML 파일이 없습니다: {html_path}", file=sys.stderr)
        sys.exit(1)

    html = Path(html_path).read_text(encoding="utf-8")
    expected = expected_page_count(html)
    math = has_math(html)
    browser_path = find_browser()
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    katex_count = None
    try:
        try:
            katex_count = convert_with_playwright(html_path, pdf_path, browser_path)
            print("변환 방식: Playwright" + (f" ({browser_path})" if browser_path else " (번들 Chromium)"))
        except ImportError:
            if not browser_path:
                raise RuntimeError(
                    "Chrome/Edge/Chromium 을 찾지 못했습니다. CHROME_PATH 환경변수로 경로를 지정하거나 "
                    "`pip install playwright && python -m playwright install chromium` 을 실행하세요."
                )
            print(f"변환 방식: headless 브라우저 직접 실행 ({browser_path})")
            katex_count = convert_with_cli(html_path, pdf_path, browser_path, math)
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ 변환 실패: {e}", file=sys.stderr)
        print("   대안: HTML 을 Chrome 에서 열고 Ctrl+P → 'PDF로 저장' (배경 그래픽 체크)", file=sys.stderr)
        sys.exit(1)

    problems = False
    size = os.path.getsize(pdf_path)
    print(f"\n✅ PDF 생성: {pdf_path} ({size/1024:.0f} KB)")

    if math:
        print(f"KaTeX elements rendered: {katex_count}")
        if not katex_count:
            problems = True
            print("⚠️ 수식이 렌더링되지 않았습니다 (KaTeX CDN 차단 가능성).")
            print("   → python scripts/setup_katex_local.py <input.html> 실행 후 다시 변환하세요.")

    pages, overflow = inspect_pdf(pdf_path)
    if pages == expected:
        print(f"쪽수 확인: {pages}쪽 (표지 1 + 본문 {expected - 1}) — 일치")
    else:
        problems = True
        print(f"⚠️ 쪽수 불일치: PDF {pages}쪽, HTML 기준 {expected}쪽.")
        if pages > expected:
            if overflow:
                print(f"   넘친 내용이 실린 PDF 쪽: {overflow} → 바로 앞 섹션의 분량을 줄이거나 둘로 나누세요.")
            else:
                print("   어떤 섹션이 한 쪽을 넘쳤습니다. 표 행 수·핵심 문항 설명 분량을 줄이거나 페이지를 나누세요.")

    sys.exit(2 if problems else 0)


if __name__ == "__main__":
    main()
