#!/usr/bin/env python3
"""Build the RigCost website into ./site for Cloudflare (drag-and-drop upload of the zip).

Pages: home calculator, one page per graphics card (/gpu/<card>/), one per processor (/cpu/<cpu>/),
console pages (/console/<console>/) with a hub (/consoles/), a money-saving guide (/guides/...),
plus 404, favicon, share image, sitemap.xml and robots.txt.   Run:  python3 build.py
"""
import datetime
import html
import json
import pathlib
import re
import shutil

SITE = 'https://rigcost.co.uk'
ROOT = pathlib.Path(__file__).parent
OUT = ROOT / 'site'
SRC = (ROOT / 'rigcost.html').read_text()
TODAY = datetime.date.today().isoformat()
E = html.escape

# Calculator defaults: Ryzen 5 7600 / RTX 4060, typical load, 27" monitor, 3h a day, 26.32p/kWh.
RATE, DEF_CPU_W, DEF_GPU_W, MON_W, REST, PSU = 26.32, 65, 115, 35, 50, 0.9
WEEKS = 52.18
HOURS_TABLE = [1, 2, 3, 4, 6]

gpus = json.loads('[' + re.search(r'var GPUS = \[(.*?)\];', SRC, re.S).group(1).replace("'", '"') + ']')
cpus = json.loads('[' + re.search(r'var CPUS = \[(.*?)\];', SRC, re.S).group(1).replace("'", '"') + ']')

# Console gaming draw at the wall, console only (no TV). Sources listed on each page.
SRC_SONY = ('Sony: PlayStation and the environment', 'https://www.playstation.com/en-id/corporate/playstation-and-the-environment/our-products/')
SRC_DF = ('Notebookcheck, reporting Digital Foundry\'s PS5 Pro power tests', 'https://www.notebookcheck.net/PS5-Pro-vs-PS5-power-consumption-Pro-console-shows-impressive-efficiency-with-30-FPS-uplift-for-modest-energy-increase.920303.0.html')
SRC_XBOX = ('Microsoft Xbox: lab platform power baselines', 'https://devdocs.xbox.com/build/game-principles/sustainability/lab-platform-baselines')
SRC_NSW = ('GamePro: Nintendo Switch 2 power measurements', 'https://www.gamepro.de/artikel/nintendo-switch-2-akkulaufzeit-energieverbrauch-effizienzmonster,3434318.html')
CONSOLES = [
    dict(slug='ps5', name='PS5', full='PlayStation 5 (original and Slim)', w=210,
         basis='Sony says PS5 gaming draws from under 100 W to around 200 W, with new games at the top of that range. Digital Foundry measured 200–218 W in demanding games, so we use 210 W.',
         src=[SRC_SONY, SRC_DF]),
    dict(slug='ps5-pro', name='PS5 Pro', full='PlayStation 5 Pro', w=230,
         basis='Digital Foundry measured the PS5 Pro at about 228–240 W in demanding games such as Elden Ring, Spider-Man 2 and F1 24, so we use 230 W.',
         src=[SRC_DF]),
    dict(slug='xbox-series-x', name='Xbox Series X', full='Xbox Series X', w=154,
         basis="Microsoft's own lab measured an average of about 154 W during gameplay across more than 200 games.",
         src=[SRC_XBOX]),
    dict(slug='xbox-series-s', name='Xbox Series S', full='Xbox Series S', w=74,
         basis="Microsoft's own lab measured an average of about 74 W during gameplay across more than 200 games.",
         src=[SRC_XBOX]),
    dict(slug='nintendo-switch-2', name='Nintendo Switch 2', full='Nintendo Switch 2 (docked)', w=20,
         basis='GamePro measured about 20 W docked in Cyberpunk 2077, and up to about 25 W while also charging the Joy-Cons. Handheld play uses roughly 10 W.',
         src=[SRC_NSW]),
]


def slug(name):
    name = re.sub(r' /.*$', '', name)
    name = re.sub(r'^(NVIDIA|AMD|Intel) ', '', name)
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def short(name):
    return re.sub(r'^(NVIDIA|AMD|Intel) ', '', re.sub(r' /.*$', '', name))


def article(word):
    # "an RTX", "an RX", "an Arc", "an Xbox"; "a Ryzen", "a Core", "a GTX", "a PS5"
    return 'an' if word.startswith(('RTX', 'RX', 'Arc', 'Xbox', 'A', 'E', 'I', 'O', 'U', '8')) else 'a'


def pc_wall(gpu_w=DEF_GPU_W, cpu_w=DEF_CPU_W, gl=0.85, cl=0.7, mon=MON_W):
    return (gpu_w * gl + cpu_w * cl + REST) / PSU + mon


def per_hour(watts):
    return watts / 1000 * RATE  # pence


def money(p):
    return f'{p:.1f}p' if p < 100 else f'£{p / 100:.2f}'


def pounds(p, dp=0):
    return f'£{p / 100:,.{dp}f}'


def cost_table(watts, caption):
    rows = ''.join(
        f'<tr><td>{h} hour{"s" if h > 1 else ""} a day</td><td class="num">{pounds(per_hour(watts) * h * 7, 2)}</td>'
        f'<td class="num">{pounds(per_hour(watts) * h * WEEKS * 7 / 12, 2)}</td><td class="num">{pounds(per_hour(watts) * h * 7 * WEEKS)}</td></tr>'
        for h in HOURS_TABLE)
    return (f'<div class="table-wrap" role="region" aria-label="{E(caption)}" tabindex="0"><table>'
            f'<thead><tr><th>Playing</th><th class="num">Per week</th>'
            f'<th class="num">Per month</th><th class="num">Per year</th></tr></thead><tbody>{rows}</tbody></table></div>')


def jsonld(*objs):
    return ''.join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>\n' for o in objs)


def crumbs(*pairs):
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': SITE + p} for i, (n, p) in enumerate(pairs)]}


def faq(pairs):
    return {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in pairs]}


def browse():
    g = ''.join(f'<li><a href="/gpu/{slug(n)}/">{E(short(n))}</a></li>' for n, _ in sorted(gpus, key=lambda x: x[1]))
    c = ''.join(f'<li><a href="/cpu/{slug(n)}/">{E(short(n))}</a></li>' for n, _ in cpus)
    k = ''.join(f'<li><a href="/console/{x["slug"]}/">{E(x["name"])}</a></li>' for x in CONSOLES)
    return f'''<section aria-labelledby="browse" class="browse">
      <h2 id="browse">Running costs by part</h2>
      <div class="browse-grid">
        <div><h3>Graphics cards</h3><ul>{g}</ul></div>
        <div><h3>Processors</h3><ul>{c}</ul></div>
        <div><h3>Consoles</h3><ul>{k}<li><a href="/consoles/">PC vs console compared</a></li></ul>
        <h3>Guides</h3><ul><li><a href="/guides/cut-gaming-pc-electricity-cost/">Cut your gaming PC's electricity cost</a></li></ul></div>
      </div>
    </section>'''


BROWSE_CSS = '''<style>
.browse-grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin-top: 14px; }
.browse h3 { font-size: 16px; margin: 0 0 6px; }
.browse ul { list-style: none; padding: 0; margin: 0 0 16px; columns: 2; column-gap: 16px; font-size: 15px; }
.browse li { margin: 3px 0; break-inside: avoid; }
.crumb { font: 13px var(--readout); color: var(--muted); padding-top: 18px; }
.crumb a { color: var(--muted); }
.prose { max-width: 70ch; }
.prose h2 { font-size: clamp(22px, 3vw, 28px); margin: 34px 0 8px; }
.prose p, .prose li { color: var(--ink); }
.prose li { margin: 6px 0; }
.stat { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 18px 0 8px; }
.stat div { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
.stat dt { font: 12px var(--readout); text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.stat dd { margin: 4px 0 0; font: 26px var(--readout); font-variant-numeric: tabular-nums; }
.btn-link { display: inline-block; margin-top: 10px; padding: 12px 18px; border-radius: 10px; background: var(--accent); color: var(--accent-ink); font-weight: 700; text-decoration: none; }
</style>'''

STYLE = re.search(r'<style>.*?</style>', SRC, re.S).group(0)
FOOTER = re.search(r'<footer>.*?</footer>', SRC, re.S).group(0)
FONTS = '\n'.join(re.findall(r'<link rel="(?:preconnect|stylesheet)"[^>]*>', SRC))
MAST = '''<header class="mast">
    <a class="brand" href="/">Rig<span>Cost</span></a>
    <span class="rate-chip">UK price cap · 26.32p/kWh</span>
  </header>'''


def page(body_html, title, description, path, head_extra='', script_vars=''):
    url = SITE + path
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title>
<meta name="description" content="{E(description)}">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(description)}">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="RigCost">
<meta property="og:image" content="{SITE}/og.png">
<meta property="og:locale" content="en_GB">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/og.png">
<meta name="theme-color" content="#0d6b5b">
<meta name="google-site-verification" content="3PvC1MIsjz__GuhE1ktbg3zEu9GB-7bujPmxtdtwkj4">
<style>:root{{color-scheme:light}}body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
{head_extra}
<script>window.RIGCOST_LINKS = true;{script_vars}</script>
</head>
<body>
{body_html}
</body>
</html>
'''


# The calculator body (styles, markup, script) from rigcost.html, minus the artifact-only head lines.
CALC = re.sub(r'^<title>.*?</title>\n<meta name="claude:viewport-fit-sides"[^>]*>\n<meta name="description"[^>]*>\n', '', SRC)
CALC = CALC.replace('class="brand" href="#top"', 'class="brand" href="/"').replace('</style>', '</style>\n' + BROWSE_CSS, 1)


def calc_page(h1, intro, extra_sections='', crumb=''):
    b = CALC.replace('<h1>How much does your gaming PC cost to run?</h1>', f'<h1>{E(h1)}</h1>', 1)
    b = re.sub(r'(<div class="intro">\s*)(<h1>.*?</h1>\s*)<p>.*?</p>',
               lambda m: m.group(1) + crumb + m.group(2) + f'<p>{intro}</p>', b, count=1, flags=re.S)
    return b.replace('</main>', extra_sections + browse() + '\n  </main>', 1)


def content_page(main_html):
    return f'''{FONTS}
{STYLE}
{BROWSE_CSS}
<div class="page">
  {MAST}
  <main>
{main_html}
{browse()}
  </main>
  {FOOTER}
</div>'''


def crumb_html(*pairs):
    parts = [f'<a href="{p}">{E(n)}</a>' if p else E(n) for n, p in pairs]
    return '<p class="crumb">' + ' / '.join(parts) + '</p>'


if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
urls = []


def write(path, content):
    d = OUT / path.strip('/')
    d.mkdir(parents=True, exist_ok=True)
    (d / 'index.html').write_text(content)
    urls.append(SITE + path)


# ---- Home ----
home_faq = [
    ('How much does a gaming PC cost to run in the UK?',
     f'A typical mid-range gaming PC (RTX 4060, Ryzen 5 7600, 27-inch monitor) draws about {round(pc_wall())} W while gaming. '
     f'At the UK price cap of {RATE}p per kWh that is about {money(per_hour(pc_wall()))} an hour, or around {pounds(per_hour(pc_wall()) * 3 * 7 * WEEKS)} a year at 3 hours a day.'),
    ('Which part of a gaming PC uses the most electricity?', 'The graphics card, by a wide margin. In most gaming PCs it uses more power than the processor and the rest of the system combined.'),
    ('Where does the electricity price come from?', f"Ofgem's price cap unit rate for 1 October to 31 December 2026: {RATE}p per kWh for a standard variable tariff paid by Direct Debit, with VAT on electricity at 0%."),
]
home_ld = jsonld(
    {'@context': 'https://schema.org', '@type': 'WebApplication', 'name': 'RigCost', 'url': SITE + '/',
     'applicationCategory': 'UtilitiesApplication', 'operatingSystem': 'Any', 'inLanguage': 'en-GB',
     'description': 'Free calculator for the electricity cost of running a gaming PC in the UK.',
     'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'GBP'}},
    faq(home_faq))
write('/', page(calc_page('How much does your gaming PC cost to run?',
                          'Pick your graphics card and processor, then how long you play. We work out the cost at the current UK electricity price, per hour, per month and per year.'),
                'RigCost: how much does your gaming PC cost to run? (UK)',
                'Work out what your gaming PC costs to run in the UK. Pick your graphics card, processor and hours to see the cost per hour, month and year at the current electricity price cap.',
                '/', home_ld))

# ---- Graphics card pages ----
by_w = sorted(gpus, key=lambda x: x[1])
for name, watts in gpus:
    s, sh = slug(name), short(name)
    wall = pc_wall(gpu_w=watts)
    hour = per_hour(wall)
    year = hour * 3 * 7 * WEEKS
    gpu_share = watts * 0.85 / PSU / wall * 100
    i = [n for n, _ in by_w].index(name)
    near = [g for g in by_w[max(0, i - 2):i + 3] if g[0] != name][:4]
    near_html = ''.join(
        f'<li><a href="/gpu/{slug(n)}/">{E(short(n))}</a>: about {money(per_hour(pc_wall(gpu_w=w)))} an hour '
        f'({"+" if w >= watts else "−"}£{abs(round(per_hour(pc_wall(gpu_w=w)) * 3 * 7 * WEEKS / 100 - year / 100))} a year)</li>'
        for n, w in near)
    h1 = f'How much does {article(sh)} {sh} cost to run?'
    intro = (f'A gaming PC with the {E(name)} (rated {watts} W) draws about {round(wall)} W at the wall in a typical game, '
             f'with a Ryzen 5 7600 and a 27-inch monitor. At the UK price cap of {RATE}p per kWh, that is about '
             f'{money(hour)} an hour, or around {pounds(year)} a year if you play 3 hours a day. '
             'Change any setting below to match your own PC.')
    extra = f'''
    <section aria-labelledby="glance">
      <h2 id="glance">{E(sh)} running costs at a glance</h2>
      <p class="lede">Whole PC, typical gaming load, with a Ryzen 5 7600, 27-inch monitor and {RATE}p per kWh. The graphics card is about {round(gpu_share)}% of the total.</p>
      {cost_table(wall, sh + ' running cost by hours played')}
    </section>
    <section aria-labelledby="near">
      <h2 id="near">Cards with similar power use</h2>
      <p class="lede">Same PC and 3 hours a day. The figure in brackets is the difference per year compared with the {E(sh)}.</p>
      <ul class="sources">{near_html}</ul>
    </section>'''
    ld = jsonld(crumbs(('RigCost', '/'), ('Graphics cards', '/'), (sh, f'/gpu/{s}/')),
                faq([(f'How much does {article(sh)} {sh} cost to run in the UK?',
                      f'About {money(hour)} an hour for a whole gaming PC with the {name} in a typical game, at {RATE}p per kWh. That is around {pounds(year)} a year at 3 hours a day.')]))
    write(f'/gpu/{s}/', page(calc_page(h1, intro, extra, crumb_html(('RigCost', '/'), ('Graphics cards', None), (sh, None))),
                             f'{sh} running cost UK: about {money(hour)} an hour | RigCost',
                             f'How much electricity does the {name} use, and what does it cost to run in the UK? About {money(hour)} an hour for a typical gaming PC at {RATE}p/kWh.',
                             f'/gpu/{s}/', ld, f' window.RIGCOST_GPU = {json.dumps(name)};'))

# ---- Processor pages ----
for name, watts in cpus:
    s, sh = slug(name), short(name)
    gaming_w = watts * 0.7
    wall = pc_wall(cpu_w=watts)
    hour = per_hour(wall)
    year = hour * 3 * 7 * WEEKS
    cpu_hour = per_hour(gaming_w / PSU)
    h1 = f'How much power does {article(sh)} {sh} use?'
    intro = (f'The {E(name)} has a rated power of {watts} W. In a typical game it draws around {round(gaming_w)} W, which costs about '
             f'{money(cpu_hour)} an hour on its own at {RATE}p per kWh. A whole gaming PC with this processor and an RTX 4060 costs about '
             f'{money(hour)} an hour, or {pounds(year)} a year at 3 hours a day. Change the settings below to match your PC.')
    extra = f'''
    <section aria-labelledby="glance">
      <h2 id="glance">Running costs with the {E(sh)}</h2>
      <p class="lede">Whole PC with an RTX 4060, typical gaming load, 27-inch monitor and {RATE}p per kWh. Games rarely push a processor to its full rated power, so typical draw is lower than the rating.</p>
      {cost_table(wall, sh + ' PC running cost by hours played')}
    </section>'''
    ld = jsonld(crumbs(('RigCost', '/'), ('Processors', '/'), (sh, f'/cpu/{s}/')),
                faq([(f'How much electricity does {article(sh)} {sh} use when gaming?',
                      f'The {name} is rated at {watts} W and typically draws around {round(gaming_w)} W in games. That costs about {money(cpu_hour)} an hour on its own at {RATE}p per kWh.')]))
    write(f'/cpu/{s}/', page(calc_page(h1, intro, extra, crumb_html(('RigCost', '/'), ('Processors', None), (sh, None))),
                             f'{sh} power consumption and running cost UK | RigCost',
                             f'How much power does the {name} use when gaming, and what does it cost to run in the UK? Rated {watts} W, typically around {round(gaming_w)} W in games.',
                             f'/cpu/{s}/', ld, f' window.RIGCOST_CPU = {json.dumps(name)};'))

# ---- Console pages ----
pc_mid = pc_wall(gpu_w=200)  # RTX 4070 PC, for comparison
for c in CONSOLES:
    hour = per_hour(c['w'])
    year = hour * 3 * 7 * WEEKS
    srcs = ''.join(f'<li><a href="{u}" target="_blank" rel="noopener">{E(t)}</a></li>' for t, u in c['src'])
    main = f'''
    <div class="intro">
      {crumb_html(('RigCost', '/'), ('Consoles', '/consoles/'), (c['name'], None))}
      <h1>How much does {article(c["name"])} {E(c["name"])} cost to run?</h1>
      <p>The {E(c["full"])} uses about {c["w"]} W while gaming. At the UK price cap of {RATE}p per kWh, that is about {money(hour)} an hour, or around {pounds(year)} a year if you play 3 hours a day. These figures are for the console only; your TV adds to it.</p>
      <dl class="stat"><div><dt>Per hour</dt><dd>{money(hour)}</dd></div><div><dt>3 hours a day, per month</dt><dd>{pounds(year / 12, 2)}</dd></div><div><dt>3 hours a day, per year</dt><dd>{pounds(year)}</dd></div></dl>
    </div>
    <section aria-labelledby="glance">
      <h2 id="glance">{E(c["name"])} running costs by hours played</h2>
      <p class="lede">Console only, while gaming, at {RATE}p per kWh.</p>
      {cost_table(c["w"], c["name"] + " running cost by hours played")}
    </section>
    <section aria-labelledby="where" class="prose">
      <h2 id="where">Where the figure comes from</h2>
      <p>{E(c["basis"])} Real use changes with each game, and menus, streaming apps and downloads use less.</p>
      <h2>What about the TV?</h2>
      <p>A TV adds its own power use on top, which varies a lot with size and type. Check the energy label on your TV for its on-mode power in watts and add it to the console's figure.</p>
      <h2>Compared with a gaming PC</h2>
      <p>A mid-range gaming PC with an RTX 4070 and a 27-inch monitor uses about {round(pc_mid)} W while gaming, about {money(per_hour(pc_mid))} an hour. <a href="/consoles/">See every console next to a gaming PC</a> or <a href="/">work out your own PC's cost</a>.</p>
      <h2>Sources</h2>
      <ul class="sources">{srcs}</ul>
    </section>'''
    ld = jsonld(crumbs(('RigCost', '/'), ('Consoles', '/consoles/'), (c['name'], f'/console/{c["slug"]}/')),
                faq([(f'How much does {article(c["name"])} {c["name"]} cost to run in the UK?',
                      f'About {money(hour)} an hour while gaming at {RATE}p per kWh, console only. That is around {pounds(year)} a year at 3 hours a day.')]))
    write(f'/console/{c["slug"]}/', page(content_page(main),
                                         f'{c["name"]} running cost UK: about {money(hour)} an hour | RigCost',
                                         f'How much electricity does the {c["full"]} use, and what does it cost to run in the UK? About {money(hour)} an hour while gaming at {RATE}p/kWh.',
                                         f'/console/{c["slug"]}/', ld))

# ---- Consoles hub: console vs PC ----
rows = [(c['name'], f'/console/{c["slug"]}/', c['w']) for c in CONSOLES]
rows += [('Gaming PC: RTX 4060 + Ryzen 5 7600 + monitor', '/gpu/rtx-4060/', pc_wall(gpu_w=115)),
         ('Gaming PC: RTX 4070 + Ryzen 5 7600 + monitor', '/gpu/rtx-4070/', pc_wall(gpu_w=200)),
         ('Gaming PC: RTX 5080 + Ryzen 7 9800X3D + monitor', '/gpu/rtx-5080/', pc_wall(gpu_w=360, cpu_w=120)),
         ('Gaming PC: RTX 5090 + Ryzen 7 9800X3D + monitor', '/gpu/rtx-5090/', pc_wall(gpu_w=575, cpu_w=120))]
rows.sort(key=lambda r: r[2])
mx = rows[-1][2]
trs = ''.join(f'<tr><td><a href="{p}">{E(n)}</a></td><td class="num">{round(w)} W<span class="tbar" style="width:{round(w / mx * 60)}px"></span></td>'
              f'<td class="num">{money(per_hour(w))}</td><td class="num">{pounds(per_hour(w) * 3 * 7 * WEEKS)}</td></tr>' for n, p, w in rows)
main = f'''
    <div class="intro">
      {crumb_html(('RigCost', '/'), ('Consoles', None))}
      <h1>Console vs gaming PC: which costs more to run?</h1>
      <p>A console uses far less electricity than most gaming PCs. An Xbox Series S costs about {money(per_hour(74))} an hour to run, while a high-end PC with an RTX 5090 costs about {money(per_hour(pc_wall(gpu_w=575, cpu_w=120)))}. Here's every console next to typical gaming PCs, at the UK price cap of {RATE}p per kWh.</p>
    </div>
    <section aria-labelledby="cmp">
      <h2 id="cmp">Running cost while gaming</h2>
      <p class="lede">Consoles are the console only, without a TV. PCs include a 27-inch monitor. Per year means 3 hours a day.</p>
      <div class="table-wrap" role="region" aria-label="Console and PC running costs" tabindex="0"><table>
        <thead><tr><th>Device</th><th class="num">Power while gaming</th><th class="num">Per hour</th><th class="num">Per year</th></tr></thead>
        <tbody>{trs}</tbody></table></div>
    </section>
    <section class="prose" aria-labelledby="sense">
      <h2 id="sense">Does running cost matter when choosing?</h2>
      <p>For most people, no. Even the gap between a Series S and a high-end PC is a few pounds a month at 3 hours a day, much smaller than the difference in what the hardware costs to buy. It matters more if you play for many hours every day.</p>
      <p><a class="btn-link" href="/">Work out your own PC's cost</a></p>
      <h2>Sources</h2>
      <ul class="sources">{''.join(f'<li><a href="{u}" target="_blank" rel="noopener">{E(t)}</a></li>' for t, u in [SRC_SONY, SRC_DF, SRC_XBOX, SRC_NSW])}</ul>
    </section>'''
write('/consoles/', page(content_page(main), 'Console vs gaming PC running cost UK: PS5, Xbox, Switch 2 | RigCost',
                         'How much does a PS5, Xbox Series X or S, or Switch 2 cost to run in the UK, compared with a gaming PC? Running costs per hour and per year at the price cap.',
                         '/consoles/', jsonld(crumbs(('RigCost', '/'), ('Consoles', '/consoles/')))))

# ---- Guide: cut your gaming PC's electricity cost ----
mid = pc_wall(gpu_w=200)
light = pc_wall(gpu_w=200, gl=0.6, cl=0.5)
save_year = (per_hour(mid) - per_hour(light)) * 3 * 7 * WEEKS
mon_save = per_hour(35 - 0) * 3 * 7 * WEEKS  # turning a second 27" screen off
tips = [
    ('Cap your frame rate', f'If your graphics card is producing more frames than your monitor can show, it is using power for nothing. Set a frame cap at or just below your monitor\'s refresh rate, in the game or in your graphics driver. Going from a typical load to a light one on an RTX 4070 PC saves about {pounds(save_year)} a year at 3 hours a day.'),
    ('Use upscaling', 'DLSS, FSR and XeSS render at a lower resolution and upscale the image, so the graphics card does less work for each frame. With a frame cap on, that usually means lower power use for a similar picture.'),
    ('Use V-Sync or adaptive sync', 'V-Sync, G-Sync and FreeSync stop the card running far beyond your refresh rate in lighter games, which has the same effect as a frame cap.'),
    ('Turn off screens you aren\'t using', f'A second 27-inch monitor left on while you play adds about 35 W, around {pounds(mon_save)} a year at 3 hours a day.'),
    ('Use sleep, not idle', 'Leaving the PC on overnight on the desktop still draws power all night. Set Windows to sleep after 15–30 minutes and turn off the PC at the wall if you are away for long.'),
    ('Pick efficient parts when you upgrade', 'When two cards perform similarly, the one with the lower rated power costs less every hour you play. Compare running costs on any card\'s page before you buy.'),
    ('Check your tariff', f'The calculator uses the price cap of {RATE}p per kWh. A cheaper fixed tariff, or cheaper off-peak hours if you have a smart tariff, lowers the cost of every hour you play.'),
]
tips_html = ''.join(f'<h2>{i + 1}. {E(t)}</h2><p>{E(b)}</p>' for i, (t, b) in enumerate(tips))
main = f'''
    <div class="intro">
      {crumb_html(('RigCost', '/'), ('Guides', None))}
      <h1>How to cut your gaming PC's electricity cost</h1>
      <p>Most of a gaming PC's power goes on the graphics card, so the biggest savings come from making it work less hard. These seven changes cost nothing and keep games looking good.</p>
    </div>
    <section class="prose" aria-label="Tips">
      {tips_html}
      <p><a class="btn-link" href="/">See what your PC costs now</a></p>
    </section>'''
write('/guides/cut-gaming-pc-electricity-cost/', page(
    content_page(main), "How to cut your gaming PC's electricity cost (UK) | RigCost",
    'Seven free ways to lower what your gaming PC costs to run in the UK, from frame caps and upscaling to sleep settings and efficient upgrades.',
    '/guides/cut-gaming-pc-electricity-cost/',
    jsonld(crumbs(('RigCost', '/'), ('Guides', '/guides/cut-gaming-pc-electricity-cost/')),
           {'@context': 'https://schema.org', '@type': 'Article', 'headline': "How to cut your gaming PC's electricity cost",
            'inLanguage': 'en-GB', 'dateModified': TODAY, 'author': {'@type': 'Organization', 'name': 'RigCost'}})))

# ---- 404, icon, sitemap, robots ----
(OUT / '404.html').write_text(page(content_page(
    '<div class="intro"><h1>Page not found</h1><p>That page doesn\'t exist. <a href="/">Go to the RigCost calculator</a>, or pick a part below.</p></div>'),
    'Page not found | RigCost', 'This page does not exist.', '/404'))
(OUT / 'favicon.svg').write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1c1913"/>'
    '<path d="M36 8 18 36h12l-4 20 20-30H34z" fill="#ffb547"/></svg>\n')
if (ROOT / 'og.png').exists():
    shutil.copy(ROOT / 'og.png', OUT / 'og.png')
(OUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                 + ''.join(f'<url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>\n' for u in urls) + '</urlset>\n')
(OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
print(f'Built {len(urls)} pages into {OUT}')
