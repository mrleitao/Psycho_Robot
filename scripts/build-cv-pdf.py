#!/usr/bin/env python3
"""Builds public/Matthew_Leitao_Resume.pdf (2 pages) and public/Matthew_Leitao_CV.pdf from src/data/cv/*.json.
Run after editing the CV data: python3 scripts/build-cv-pdf.py"""
import json, html, re, sys, pathlib
from playwright.sync_api import sync_playwright

root = pathlib.Path(__file__).resolve().parent.parent
cv = json.load(open(root / 'src/data/cv/cv.json'))
pubs = json.load(open(root / 'src/data/cv/publications.json'))
rs = json.load(open(root / 'src/data/cv/resume.json'))
S = {s['id']: s for s in cv['sections']}
e = html.escape
import datetime
updated = datetime.date.fromisoformat(cv['updated']).strftime('%B %-d, %Y')

CSS = """

* { box-sizing: border-box; }
body { font-family: Carlito, 'Liberation Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.28; color: #111; margin: 0; }
h1 { font-size: 21pt; margin: 0 0 2pt; letter-spacing: .2pt; }
.title { font-size: 11.5pt; color: #305f72; margin: 0 0 3pt; font-weight: 700; }
.contact { font-size: 10pt; margin: 0 0 7pt; }
.contact span + span::before { content: ' | '; color: #777; }
h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: .8pt; border-bottom: 1.2pt solid #305f72; color: #17313c; margin: 10pt 0 4pt; padding-bottom: 1.5pt; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 6pt 0 1pt; break-after: avoid; }
.row { display: flex; justify-content: space-between; gap: 12pt; break-inside: avoid; }
.row .when { white-space: nowrap; font-weight: 400; }
.org { font-weight: 700; }
.role { font-style: italic; margin: 0 0 1pt; }
ul { margin: 1pt 0 3pt; padding-left: 14pt; } li { margin: 0 0 1.2pt; } li, p { orphans: 2; widows: 2; }
p { margin: 0 0 3pt; }
.entry { break-inside: avoid; margin-bottom: 4pt; }
.cite { break-inside: avoid; margin: 0 0 3pt; padding-left: 14pt; text-indent: -14pt; }
a { color: inherit; text-decoration: none; }
.group h3 { font-size: 10.5pt; margin: 5pt 0 2pt; color: #305f72; }
.note { color: #555; font-size: 9.5pt; }
"""

def page(body):
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"

contact = ''.join(f'<span>{e(c)}</span>' for c in rs['contact'])
head = f"<h1>{e(rs['name'])}</h1><p class='contact'>{contact}</p>"

def resume():
    h = f"<h1>{e(rs['name'])}</h1><p class='title'>{e(rs['title'])}</p><p class='contact'>{contact}</p>"
    h += f"<h2>Summary</h2><p>{e(rs['summary'])}</p>"
    h += "<h2>Research Experience</h2>"
    for x in rs['experience']:
        h += f"<div class='entry'><div class='row'><span class='org'>{e(x['org'])}</span><span class='when'>{e(x['when'])}</span></div><p class='role'>{e(x['role'])}</p><ul>" + ''.join(f'<li>{e(b)}</li>' for b in x['bullets']) + '</ul></div>'
    h += "<h2>Selected Publications</h2>" + ''.join(f"<p class='cite'>{c}</p>" for c in rs['publications'])
    h += "<h2>Education</h2>" + ''.join(f"<div class='row'><span><strong>{e(d['degree'])}</strong>, {e(d['org'])}</span><span class='when'>{e(d['when'])}</span></div>" for d in rs['education'])
    h += "<h2>Technical Skills</h2>" + ''.join(f"<p><strong>{e(a)}:</strong> {e(b)}</p>" for a, b in rs['skills'])
    h += "<h2>Honors and Service</h2><ul>" + ''.join(f'<li>{e(x)}</li>' for x in rs['honors']) + '</ul>'
    return page(h)

def strip(t):
    return re.sub(r'<a [^>]*>(.*?)</a>', lambda m: m.group(1), t)

def entries(sec):
    out = ''
    for i in sec['items']:
        when = e(i.get('when', ''))
        out += f"<div class='entry'><div class='row'><span><strong>{e(i['title'])}</strong>{', ' + e(i['org']) if i.get('org') else ''}</span><span class='when'>{when}</span></div>"
        if i.get('lines'): out += '<ul>' + ''.join(f'<li>{e(l)}</li>' for l in i['lines']) + '</ul>'
        out += '</div>'
    return out

def cvdoc():
    h = f"<h1>{e(rs['name'])}</h1><p class='contact'>{contact}</p>"
    for sid in ['positions', 'education', 'publications', 'grants', 'honors', 'research-experience', 'professional-experience', 'teaching', 'mentorship', 'invited', 'talks', 'posters', 'intramural', 'skills', 'workshops-attended', 'workshops-led', 'service', 'memberships']:
        if sid == 'publications':
            h += '<h2>Publications</h2>'
            for g in pubs['groups']:
                h += f"<div class='group'><h3>{e(g['heading'])}</h3>" + ''.join(f"<p class='cite'>{strip(i['html'])}</p>" for i in g['items']) + '</div>'
            continue
        s = S[sid]
        h += f"<h2>{e(s['title'])}</h2>"
        if s['kind'] == 'entries': h += entries(s)
        elif s['kind'] == 'html': h += ''.join(f"<p class='cite'>{strip(i['html'])}</p>" for i in s['items'])
        elif s['kind'] == 'groups':
            for g in s['groups']:
                h += f"<div class='group'><h3>{e(g['heading'])}</h3>"
                if g.get('text'): h += f"<p>{e(g['text'])}</p>"
                if g.get('items'): h += '<ul>' + ''.join(f"<li>{e(i['when'])}: {e(i['text'])}</li>" for i in g['items']) + '</ul>'
                h += '</div>'
    return page(h)

def render(pw, htmltext, out, footer):
    b = pw.chromium.launch(); pg = b.new_page()
    pg.set_content(htmltext); pg.wait_for_timeout(300)
    pg.pdf(path=str(root / 'public' / out), format='Letter', print_background=True,
           margin={'top': '0.6in', 'bottom': '0.65in', 'left': '0.7in', 'right': '0.7in'},
           display_header_footer=True, header_template='<span></span>',
           footer_template=f"<div style=\"width:100%;font:8pt Carlito,Arial,sans-serif;color:#555;text-align:center\">{footer} | Page <span class='pageNumber'></span> of <span class='totalPages'></span></div>")
    b.close()

with sync_playwright() as pw:
    render(pw, resume(), 'Matthew_Leitao_Resume.pdf', 'Matthew Leitao, Resume')
    render(pw, cvdoc(), 'Matthew_Leitao_CV.pdf', f'Matthew Leitao, CV, updated {updated}')
