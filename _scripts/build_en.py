#!/usr/bin/env python3
"""Generate the English projects page (projects/en/index.html) from the Korean one (projects/index.html).

The projects page follows the rule of the knowledge pages: the Korean page is the original, at
https://hughqlee.com/projects/, and its English version at https://hughqlee.com/projects/en/ is
generated from it. Search engines and AI answer engines then find each language at its own address,
linked with hreflang, and read it without running the page's JavaScript. (The home page, / and /en/,
is a short profile written by hand in both languages: index.html and en/index.html.)

projects/index.html is the only page to edit:
  - Korean: `copy.ko` and `projectData[].i18n.ko` in its script, and its head (description,
    keywords, og:description, og:image:alt).
  - English: `copy.en` and `projectData[].i18n.en` in the same script, and EN_HEAD below. It
    follows the Korean; keep it in step.
This script reads `copy` and `projectData` with Node, then
  - writes into projects/index.html the text its script sets on load (so the page reads the same
    without JavaScript), the titles, twitter:description (a copy of og:description), and the
    generated blocks: the structured data and the project list for readers and crawlers without
    JavaScript;
  - writes projects/en/index.html: the same page with lang="en", the English head, text, and blocks,
    the breadcrumb pointing to /en/, and the EN / KO link pointing back to /projects/;
  - records in _scripts/en-sync.json the text it built from. When a Korean string has changed since
    then and its English has not, it stops and names them: update the English, or run with
    --accept when the English still fits.

Run from the repository root (folders starting with "_" are not published by GitHub Pages):
    python3 _scripts/build_en.py           write projects/index.html, projects/en/index.html, _scripts/en-sync.json
    python3 _scripts/build_en.py --check   only report; write nothing
    python3 _scripts/build_en.py --accept  build although a changed Korean string kept its English
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "projects" / "index.html"
TARGET = ROOT / "projects" / "en" / "index.html"
SYNC = ROOT / "_scripts" / "en-sync.json"
SITE = "https://hughqlee.com/"
PAGE = {"ko": SITE + "projects/", "en": SITE + "projects/en/"}
HOME = {"ko": SITE, "en": SITE + "en/"}
SAME_AS = ["https://github.com/hughqlee", "https://www.linkedin.com/in/hughqlee/", "https://x.com/hughqlee/"]

# The English head of projects/en/index.html, in step with the Korean head of projects/index.html.
EN_HEAD = {
    "description": "Computer vision and robotics systems that Hugh Q Lee, a Vision AI Product Engineer, built for zebrafish lab automation: toxicity evaluation automation, microinjection, behavior and feeding analytics, and robotic 3D imaging.",
    "keywords": "Hugh Q Lee, Projects, Vision AI, Product Engineer, Lab Automation, Computer Vision, Robotics, Zebrafish, Assay Automation, Microscopy",
    "og:description": "Selected work in vision AI, robotics, microscopy automation, and zebrafish assay systems.",
    "og:image:alt": "Terminal-style home page of Hugh Q Lee: hughqlee in ASCII art, “To see is something extraordinary.”, and links to projects, knowledge, and books.",
}
HEAD_TAG = {
    "description": '<meta name="description" ',
    "keywords": '<meta name="keywords" ',
    "og:description": '<meta property="og:description" ',
    "og:image:alt": '<meta property="og:image:alt" ',
}


def page_data(doc):
    """`copy` and `projectData` from the page script, evaluated by Node."""
    start, end = doc.index("const copy = {"), doc.index("const galleryGrid")
    js = doc[start:end] + "\nprocess.stdout.write(JSON.stringify({ copy, projectData }));"
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    if out.returncode:
        sys.exit("node could not read copy/projectData:\n" + out.stderr)
    data = json.loads(out.stdout)
    return data["copy"], data["projectData"]


def text(value):
    return html.escape(value, quote=False)


def attr(value):
    return html.escape(value, quote=True)


def set_inner(doc, el_id, inner):
    pat = re.compile(r'(<(\w+)\b[^<>]*\bid="' + re.escape(el_id) + r'"[^<>]*>)(.*?)(</\2>)', re.S)
    doc, n = pat.subn(lambda m: m.group(1) + inner + m.group(4), doc, count=1)
    if n != 1:
        sys.exit(f"#{el_id} not found in projects/index.html")
    return doc


def set_attr(doc, el_id, name, value):
    m = re.search(r'<[^<>]*\bid="' + re.escape(el_id) + r'"[^<>]*>', doc)
    if not m:
        sys.exit(f"#{el_id} not found in projects/index.html")
    tag, n = re.subn(r'\b' + name + r'="[^"]*"', f'{name}="{attr(value)}"', m.group(0), count=1)
    if n != 1:
        sys.exit(f"#{el_id} has no {name}")
    return doc[:m.start()] + tag + doc[m.end():]


def get_head(doc, opening):
    """The content="..." of the one head tag that starts with `opening`."""
    m = re.search(re.escape(opening) + r'content="([^"]*)"', doc)
    if not m:
        sys.exit(f"head tag not found: {opening}")
    return html.unescape(m.group(1))


def set_head(doc, opening, value):
    """Replace the content="..." (or href="...") of the one head tag that starts with `opening`."""
    pat = re.compile(re.escape(opening) + r'(content|href)="[^"]*"')
    doc, n = pat.subn(lambda m: f'{opening}{m.group(1)}="{attr(value)}"', doc, count=1)
    if n != 1:
        sys.exit(f"head tag not found: {opening}")
    return doc


def replace_block(doc, name, body, indent):
    start, end = f"{indent}<!-- generated:{name} -->\n", f"{indent}<!-- /generated:{name} -->"
    i, j = doc.index(start) + len(start), doc.index(end)
    return doc[:i] + body + doc[j:]


def static_copy(doc, ui, projects):
    """The text renderStaticCopy() sets, written into the HTML (mirror that function when it changes)."""
    # A project with a link (href) is one with a published paper.
    meta = (ui["introMeta"].replace("{count}", str(len(projects)))
            .replace("{papers}", str(sum(1 for p in projects if p.get("href")))))
    for el_id, value in [
        ("skipLink", ui["skipLink"]), ("introLead", ui["introLead"]), ("introMeta", meta),
        ("introNote", ui["introNote"]), ("selected-work-title", ui["selectedWorkTitle"]),
    ]:
        doc = set_inner(doc, el_id, text(value))
    doc = set_inner(doc, "introByline", "Hugh Q Lee<br>" + text(ui["profileRole"]))
    for el_id, name in [("crumbs", "crumbsAria"), ("promptLine", "promptAria"),
                        ("modalClose", "modalCloseAria"), ("languageToggle", "languageToggleAria"),
                        ("modalLanguageToggle", "languageToggleAria")]:
        doc = set_attr(doc, el_id, "aria-label", ui[name])
    for el_id in ("themeToggle", "modalThemeToggle"):
        doc = set_attr(doc, el_id, "aria-label", ui["themeToggleAria"]["toLight"])
    for theme in ("dark", "light"):
        doc = re.sub(r'(data-theme-option="' + theme + r'">)[^<]*(<)', lambda m: m.group(1) + text(ui["themeLabels"][theme]) + m.group(2), doc)
    doc = re.sub(r"<title>[^<]*</title>", f"<title>{text(ui['documentTitle'])}</title>", doc, count=1)
    doc = set_head(doc, '<meta property="og:title" ', ui["documentTitle"])
    return set_head(doc, '<meta name="twitter:title" ', ui["documentTitle"])


def structured_data(lang, ui, projects, description):
    """The projects as an ItemList of CreativeWorks; the full Person is on the home page (#person)."""
    page = PAGE[lang]
    items = []
    for position, p in enumerate(projects, 1):
        t = p["i18n"][lang]
        work = {"@type": "CreativeWork", "@id": page + "#" + p["id"], "url": page + "#" + p["id"],
                "name": t["fullTitle"], "alternateName": t["title"], "genre": t["category"],
                "description": t["summary"], "abstract": t["outcome"], "keywords": t["tags"],
                "inLanguage": lang, "creator": {"@id": SITE + "#person"}}
        if p.get("artifactImage"):
            work["image"] = SITE + p["artifactImage"].lstrip("/")
        if p.get("href"):
            work["subjectOf"] = {"@type": "ScholarlyArticle", "url": p["href"]}
        items.append({"@type": "ListItem", "position": position, "item": work})
    collection = {"@type": "CollectionPage", "@id": page + "#collection", "url": page, "name": "Projects",
                  "description": description, "inLanguage": lang, "isPartOf": {"@id": SITE + "#website"},
                  "author": {"@id": SITE + "#person"}}
    if lang == "ko":
        collection["workTranslation"] = {"@id": PAGE["en"] + "#collection"}
    else:
        collection["translationOfWork"] = {"@id": PAGE["ko"] + "#collection"}
    collection["mainEntity"] = {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items}
    graph = [
        collection,
        {"@type": "Person", "@id": SITE + "#person", "name": "Hugh Q Lee", "url": SITE,
         "jobTitle": ui["profileRole"], "sameAs": SAME_AS},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Hugh Q Lee", "item": HOME[lang]},
            {"@type": "ListItem", "position": 2, "name": "Projects", "item": page}]},
    ]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return '    <script type="application/ld+json">\n' + "\n".join("    " + line for line in body.splitlines()) + "\n    </script>\n"


def runs_without_js(lang, projects):
    """The run reports for readers and crawlers that do not run JavaScript."""
    items = []
    for p in projects:
        t = p["i18n"][lang]
        items.append(
            "                    <li>\n"
            f"                        <h3>{text(t['fullTitle'])}</h3>\n"
            f"                        <p>{text(t['category'])} · {text(t['statusLabel'])}</p>\n"
            f"                        <p>{text(t['summary'])}</p>\n"
            f"                        <p>{text(t['outcome'])}</p>\n"
            "                    </li>\n")
    return ("            <noscript>\n                <ol class=\"noscript-runs\">\n" + "".join(items) +
            "                </ol>\n            </noscript>\n")


def texts(lang, copy, projects, head):
    """Every string of one language, keyed the same in both languages (a list counts as one string)."""
    out = {}

    def walk(key, node):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{key}.{k}", v)
        elif isinstance(node, list):
            out[key] = json.dumps(node, ensure_ascii=False)
        elif isinstance(node, str):
            out[key] = node

    walk("copy", copy[lang])
    for p in projects:
        walk("projectData." + p["id"], p["i18n"][lang])
    walk("head", head)
    return out


def english_problems(ko, en):
    """Korean strings with no English, and Korean strings changed since the last build whose English did not."""
    synced = json.loads(SYNC.read_text(encoding="utf-8"))["text"] if SYNC.exists() else {}
    missing = [k for k in ko if ko[k] and not en.get(k)]
    stale = [(k, synced[k][0], ko[k]) for k in ko
             if k in synced and synced[k][0] != ko[k] and synced[k][1] == en.get(k)]
    return missing, stale


def localize_english(doc, ui):
    def once(old, new, count=1):
        nonlocal doc
        if doc.count(old) != count:
            sys.exit(f"expected {count} of {old!r} in projects/index.html, found {doc.count(old)}")
        doc = doc.replace(old, new)

    start, end = doc.index("<!--\n  Korean projects page"), doc.index('-->\n<html lang="ko">')
    doc = (doc[:start] + "<!--\n  English projects page (https://hughqlee.com/projects/en/), generated from projects/index.html\n"
           "  by _scripts/build_en.py. Do not edit this file: edit projects/index.html and run the script.\n" + doc[end:])
    once('<html lang="ko">', '<html lang="en">')
    for key, tag in HEAD_TAG.items():
        doc = set_head(doc, tag, EN_HEAD[key])
    doc = set_head(doc, '<meta name="twitter:description" ', EN_HEAD["og:description"])
    doc = set_head(doc, '<meta property="og:url" ', PAGE["en"])
    # The share card in English (the Korean page uses images/og-cover-ko.jpg; both from _scripts/build_og.py).
    doc = set_head(doc, '<meta property="og:image" ', SITE + "images/og-cover.jpg")
    doc = set_head(doc, '<meta name="twitter:image" ', SITE + "images/og-cover.jpg")
    doc = set_head(doc, '<link rel="canonical" ', PAGE["en"])
    once('<meta property="og:locale" content="ko_KR">', '<meta property="og:locale" content="en_US">')
    once('<meta property="og:locale:alternate" content="en_US">', '<meta property="og:locale:alternate" content="ko_KR">')
    once('href="/projects/en/" hreflang="en"', 'href="/projects/" hreflang="ko"', count=2)
    # The footer, as on the English knowledge pages: home in English and a link to the Korean original.
    once('<a href="/" id="footerHome">Hugh Q Lee</a>',
         '<a href="/en/" id="footerHome">Hugh Q Lee</a> · Translated from the '
         '<a href="/projects/" hreflang="ko">Korean original</a>')
    return set_attr(doc, "homeCrumb", "href", "/en/")


def build():
    ko_doc = SOURCE.read_text(encoding="utf-8")
    copy, projects = page_data(ko_doc)
    ko_head = {key: get_head(ko_doc, tag) for key, tag in HEAD_TAG.items()}
    ko_text, en_text = texts("ko", copy, projects, ko_head), texts("en", copy, projects, EN_HEAD)

    ko = static_copy(ko_doc, copy["ko"], projects)
    ko = set_head(ko, '<meta name="twitter:description" ', ko_head["og:description"])
    ko = replace_block(ko, "jsonld", structured_data("ko", copy["ko"], projects, ko_head["description"]), "    ")
    ko = replace_block(ko, "runs", runs_without_js("ko", projects), "            ")

    en = static_copy(ko, copy["en"], projects)
    en = replace_block(en, "jsonld", structured_data("en", copy["en"], projects, EN_HEAD["description"]), "    ")
    en = replace_block(en, "runs", runs_without_js("en", projects), "            ")
    en = localize_english(en, copy["en"])

    sync = {"note": "Written by _scripts/build_en.py: the Korean and English text of the last build. Do not edit.",
            "text": {k: [ko_text[k], en_text.get(k)] for k in sorted(ko_text)}}
    outputs = {SOURCE: ko, TARGET: en,
               SYNC: json.dumps(sync, ensure_ascii=False, indent=1) + "\n"}
    return outputs, *english_problems(ko_text, en_text)


def main():
    check, accept = "--check" in sys.argv[1:], "--accept" in sys.argv[1:]
    outputs, missing, stale = build()
    if missing:
        sys.exit("no English for: " + ", ".join(missing))
    if stale and not accept:
        print("The Korean changed but its English did not. Update copy.en, projectData[].i18n.en, or EN_HEAD,"
              " or run with --accept if the English still fits:")
        for key, old, new in stale:
            print(f"  {key}: {old!r} -> {new!r}")
        sys.exit(1)
    changed = [path for path, doc in outputs.items()
               if not path.exists() or path.read_text(encoding="utf-8") != doc]
    names = ", ".join(str(path.relative_to(ROOT)) for path in changed)
    if check:
        print("up to date" if not changed else f"out of date: {names} (run without --check)")
        sys.exit(1 if changed else 0)
    for path in changed:
        path.parent.mkdir(exist_ok=True)
        path.write_text(outputs[path], encoding="utf-8")
    print("wrote " + names if changed else "already up to date")


if __name__ == "__main__":
    main()
