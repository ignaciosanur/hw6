"""Problem 5: render each practice document the way a person would see it.

HTML -> headless Chrome screenshot (of a copy with <script> tags removed, so nothing runs), PDF -> page image (what a PDF viewer shows),
.eml -> the HTML part a mail app displays (or the plain text if there is no HTML part), with the headers on top.
Writes output/attack_screens/<document>.png.   Run: .venv/bin/python scripts/render_docs.py [folder under data/]
"""
import email
import html
import re
import subprocess
import sys
import tempfile
from email import policy
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parent.parent
FOLDER = sys.argv[1] if len(sys.argv) > 1 else "practice_docs"
DOCS = sorted(p for p in (ROOT / "data" / FOLDER).iterdir() if p.suffix in (".html", ".pdf", ".eml"))
OUT = ROOT / "output" / "attack_screens"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def chrome_shot(html_file: Path, png: Path, height: int = 700) -> None:
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size=900,{height}", f"--screenshot={png}", html_file.as_uri()],
                   check=True, capture_output=True, timeout=60)


def email_view(path: Path) -> str:
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    head = "".join(f"<div><b>{h}:</b> {html.escape(str(msg[h]))}</div>" for h in ("From", "To", "Subject", "Date") if msg[h])
    part = msg.get_body(preferencelist=("html", "plain"))  # what a mail app picks to display
    body = part.get_content()
    if part.get_content_subtype() == "plain":
        body = f"<pre style='font-family:inherit;white-space:pre-wrap'>{html.escape(body)}</pre>"
    return (f"<html><body style='font-family:-apple-system,Helvetica,Arial;margin:0;background:#fff'>"
            f"<div style='background:#f2f2f2;padding:14px 24px;border-bottom:1px solid #ddd;font-size:14px'>"
            f"<div style='color:#888;font-size:12px;margin-bottom:6px'>Mail app view ({part.get_content_type()} part)</div>{head}</div>"
            f"<div style='padding:18px 24px;font-size:15px'>{body}</div></body></html>")


OUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    for doc in DOCS:
        png = OUT / f"{doc.stem}.png"
        if doc.suffix == ".html":
            copy = Path(tmp) / doc.name  # scripts stripped; they don't change what's on screen here
            copy.write_text(re.sub(r"(?is)<script.*?</script>", "", doc.read_text()))
            chrome_shot(copy, png)
        elif doc.suffix == ".pdf":
            pdf = pdfium.PdfDocument(doc)
            pdf[0].render(scale=1.3).to_pil().save(png)  # the full visible page
            pdf.close()
        elif doc.suffix == ".eml":
            view = Path(tmp) / f"{doc.stem}.html"
            view.write_text(email_view(doc))
            chrome_shot(view, png, height=520)
        if not png.exists():
            raise SystemExit(f"Chrome did not write {png}")
        print("rendered", png.relative_to(ROOT))
