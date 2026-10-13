#!/usr/bin/env python3
"""Fill the generated parts of the bookshelf pages (/books/ and /books/en/) from books/books.json.

The Korean page books/index.html is the original, at https://hughqlee.com/books/, and
books/en/index.html is its English translation. Both are written by hand except the blocks between
<!-- generated:NAME --> and <!-- /generated:NAME -->, which this script fills from books/books.json:
the robots tag, the structured data, the draft notice, the shelf counts, the filters, and the shelf.
The shelf is then in the HTML itself, so the pages read the same without JavaScript, and search
engines and AI answer engines see every book and review.

books/books.json is the only file to edit for books and reviews. A book needs an id (the year it
joined the shelf and its order, for links such as /books/#book-2026-001), title, author, publisher,
genres, listPrice, and status. Optional: subtitle, original (the original title of a translated
book), translator, series and volume, isbn, language ("ko" unless the book is in another language,
such as "en" for an English original), note, knowledge, waitlist, loans, readers, and hugh.

Ratings are out of three stars: 3 = recommended, 2 = pretty good but not quite satisfying,
1 = not really recommended.
  - hugh: {"stars": 1-3 or null while unrated, "review": "", "reviewEn": ""}. The review is optional;
    the English page shows the Korean review unless reviewEn is given.
  - readers: [{"nick", "read": "YYYY-MM", "stars": 1-3, "line" (optional), "for" (optional)}].

Only books Hugh has rated appear on the pages: Hugh lends a book only after reading it, so a book whose
hugh.stars is still null stays in books.json, unlisted, until it gets stars. The shelf shows the most stars
first, and within the same stars the newest id first, so a newly added book (the next id, at the end of the
file) comes first among its peers.
Visitors can narrow it with a switch for available books only and with genre chips: all genres are on
at first, any number can be switched on or off, and a book shows when any of its genres is on.

The file holds public data only: names, contacts, refund accounts, and addresses stay in the
private loan ledger, never in this repository, which is public. The script stops on a book that
breaks the shelf's rules:
  - a deposit above the price of a new copy (90% of the list price, rounded down to 1,000 won);
  - more reviews than loans (only people who borrowed a book review it);
  - a review line over 100 characters, or a "for" over 30;
  - a key that looks like personal data (name, phone, email, account, address, ...).

While books/books.json has "draft": true, both pages show a draft notice and carry
<meta name="robots" content="noindex, follow">, so a draft that gets pushed stays out of search.

Run from the repository root (folders starting with "_" are not published by GitHub Pages):
    python3 _scripts/build_books.py           write books/index.html and books/en/index.html
    python3 _scripts/build_books.py --check   only report; write nothing
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "books" / "books.json"
PAGE_FILE = {"ko": ROOT / "books" / "index.html", "en": ROOT / "books" / "en" / "index.html"}
KNOWLEDGE_FILE = {"ko": ROOT / "knowledge" / "index.html", "en": ROOT / "knowledge" / "en" / "index.html"}
KNOWLEDGE_PATH = {"ko": "/knowledge/", "en": "/knowledge/en/"}
SITE = "https://hughqlee.com/"
PAGE = {"ko": SITE + "books/", "en": SITE + "books/en/"}
HOME = {"ko": SITE, "en": SITE + "en/"}
SAME_AS = ["https://github.com/hughqlee", "https://www.linkedin.com/in/hughqlee/", "https://x.com/hughqlee/"]
ROBOTS = '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">'
ROBOTS_DRAFT = '<meta name="robots" content="noindex, follow">'

STATUSES = ("available", "reserved", "on-loan", "not-lent")
STARS = (3, 2, 1)  # best first, the order the tallies show them in
OPTIONAL_TEXT = ("subtitle", "original", "translator", "series", "isbn")
PRIVATE = {"name", "realname", "phone", "tel", "mobile", "email", "account", "bank", "address", "contact"}
LINE_MAX, FOR_MAX = 100, 30


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


UI = {
    "ko": {
        "status": {"available": "대여 가능", "reserved": "예약 있음", "on-loan": "대여 중", "not-lent": "대여하지 않음"},
        "mood": {3: "추천도서", 2: "꽤 좋았지만 만족까진 아니야", 1: "별로 권하지 않아"},
        "stars": lambda n: f"별 3개 중 {n}개",
        "star_count": lambda n: f"별 {n}개",
        "available_only": "대여 가능한 책만",
        "no_match": "조건에 맞는 책이 없다. 장르를 하나 이상 켜거나 '대여 가능한 책만'을 끄면 된다.",
        "genre_group": "장르",
        "count": "{shown}권 / 전체 {total}권",
        "deposit": lambda won: f"보증금 {won:,}원",
        "loans": lambda n: f"대여 {n}회",
        "waitlist": lambda n: f"대기 {n}명",
        "tally": lambda n, average: f"빌려 읽은 독자 {n}명 · 평균 {average:.1f}점",
        "stats": lambda s: (f"책 <b>{s['books']}</b>권 · 대여 가능 <b>{s['available']}</b>권 · "
                            f"누적 대여 <b>{s['loans']}</b>회 · 감상 <b>{s['reviews']}</b>개"),
        "consensus": "독자 모두 추천",
        "split": "의견이 갈림",
        "for": "이런 사람에게: ",
        "related": "관련 지식: ",
        "empty": "아직 책장이 비어 있다.",
        "draft": "초안 · 책장 사진에서 옮긴 목록이라 서지와 보증금을 아직 확인하는 중이다. 확인이 끝나기 전까지 이 페이지는 검색엔진에 노출하지 않는다.",
    },
    "en": {
        "status": {"available": "Available", "reserved": "Reserved", "on-loan": "On loan", "not-lent": "Not lent"},
        "mood": {3: "Recommended", 2: "Pretty good, not quite satisfying", 1: "Not really recommended"},
        "stars": lambda n: f"{n} of 3 stars",
        "star_count": lambda n: plural(n, "star"),
        "available_only": "Available only",
        "no_match": "No books match. Switch on at least one genre, or turn off \"Available only\".",
        "genre_group": "Genre",
        "count": "{shown} of {total} books",
        "deposit": lambda won: f"Deposit ₩{won:,}",
        "loans": lambda n: plural(n, "loan"),
        "waitlist": lambda n: f"{n} waiting",
        "tally": lambda n, average: f"{plural(n, 'borrower')} · average {average:.1f} of 3",
        "stats": lambda s: " · ".join([
            f"<b>{s['books']}</b> book" + ("" if s["books"] == 1 else "s"),
            f"<b>{s['available']}</b> available",
            f"<b>{s['loans']}</b> loan" + ("" if s["loans"] == 1 else "s"),
            f"<b>{s['reviews']}</b> review" + ("" if s["reviews"] == 1 else "s")]),
        "consensus": "Every reader recommends",
        "split": "Split verdicts",
        "for": "For: ",
        "related": "Related: ",
        "empty": "The shelf is empty for now.",
        "draft": "Draft · This list was copied from a photo of the bookshelf, and its details and deposits are still being checked. Until then, this page stays out of search engines.",
    },
}


def text(value):
    return html.escape(value, quote=False)


def attr(value):
    return html.escape(value, quote=True)


def names(value):
    """Split "A, B" into ["A", "B"]."""
    return [part.strip() for part in value.split(",") if part.strip()]


def is_stars(value):
    return type(value) is int and value in STARS  # not bool, which Python counts as an int


def knowledge_titles():
    """Knowledge page titles by slug, read from the knowledge index in each language."""
    titles = {}
    for lang, path in KNOWLEDGE_FILE.items():
        pattern = r'<h2><a href="' + re.escape(KNOWLEDGE_PATH[lang]) + r'([a-z0-9-]+)/">([^<]+)</a></h2>'
        titles[lang] = {slug: html.unescape(title) for slug, title in re.findall(pattern, path.read_text(encoding="utf-8"))}
    return titles


def load():
    """books/books.json, checked against the shelf's rules; most stars first, then newest id."""
    try:
        data = json.loads(DATA.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        sys.exit(f"books/books.json is not valid JSON: {error}")
    genres, books = data.get("genres", {}), data.get("books", [])
    titles = knowledge_titles()
    problems, seen = [], set()
    if not isinstance(data.get("draft", False), bool):
        problems.append('"draft" must be true or false')
    for book in books:
        where = book.get("id", "(no id)")

        def check(ok, message):
            if not ok:
                problems.append(f"{where}: {message}")

        check(re.fullmatch(r"\d{4}-\d{3}", str(book.get("id", ""))), 'id should look like "2026-001" (year it joined the shelf, then its order)')
        check(book.get("id") not in seen, "id is used twice")
        seen.add(book.get("id"))
        for key in ("title", "author", "publisher"):
            check(isinstance(book.get(key), str) and book[key].strip(), f"{key} is missing")
        for key in OPTIONAL_TEXT:
            check(key not in book or (isinstance(book[key], str) and book[key].strip()), f"{key} must be text when present")
        check(isinstance(book.get("volume", 1), int) and book.get("volume", 1) >= 1, "volume must be a number from 1")
        check(book.get("language", "ko") in ("ko", "en"), 'language must be "ko" or "en"')
        check(book.get("genres") and all(g in genres for g in book["genres"]),
              "genres must be keys of the genres table: " + ", ".join(genres))
        price = book.get("listPrice")
        check(isinstance(price, int) and price > 0, "listPrice (the list price in won) is missing")
        cap = price * 9 // 10 // 1000 * 1000 if isinstance(price, int) else 0
        deposit = book.setdefault("deposit", cap)
        check(isinstance(deposit, int) and 0 < deposit <= cap,
              f"deposit must be at most the price of a new copy, {cap:,} won (90% of the list price, rounded down to 1,000 won)")
        check(book.get("status") in STATUSES, "status must be one of " + ", ".join(STATUSES))
        hugh = book.setdefault("hugh", {})
        check(isinstance(hugh, dict), 'hugh must look like { "stars": 3, "review": "" }')
        if isinstance(hugh, dict):
            check(hugh.get("stars") is None or is_stars(hugh["stars"]), "hugh.stars must be 1, 2, 3, or null while unrated")
            for key in ("review", "reviewEn"):
                check(isinstance(hugh.get(key, ""), str), f"hugh.{key} must be text")
        readers = book.setdefault("readers", [])
        loans = book.setdefault("loans", 0)
        check(isinstance(loans, int) and loans >= len(readers),
              "loans must be at least the number of reviews: only people who borrowed the book review it")
        waitlist = book.get("waitlist", 0)
        check(isinstance(waitlist, int) and waitlist >= 0, "waitlist must be a count")
        for reader in readers:
            who = f"review by {reader.get('nick', '?')}"
            check(isinstance(reader.get("nick"), str) and reader["nick"].strip(), f"{who}: nick is missing")
            check(re.fullmatch(r"\d{4}-\d{2}", str(reader.get("read", ""))), f'{who}: read should look like "2026-06"')
            check(is_stars(reader.get("stars")), f"{who}: stars must be 1, 2, or 3")
            check(isinstance(reader.get("line", ""), str) and len(reader.get("line", "")) <= LINE_MAX,
                  f"{who}: line must be at most {LINE_MAX} characters")
            check(isinstance(reader.get("for", ""), str) and len(reader.get("for", "")) <= FOR_MAX,
                  f"{who}: for must be at most {FOR_MAX} characters")
        for slug in book.get("knowledge", []):
            check(slug in titles["ko"] and slug in titles["en"], f"knowledge page {slug!r} is not on the knowledge index")
        note = book.get("note")
        check(note is None or all(note.get(lang) for lang in ("ko", "en")), "note needs both ko and en")
        for item in [book] + readers:
            found = PRIVATE & {key.lower() for key in item}
            check(not found, f"remove {', '.join(sorted(found))}: personal data belongs in the private loan ledger, not in this public file")
    if problems:
        sys.exit("books/books.json:\n  " + "\n  ".join(problems))
    books.sort(key=lambda b: b["id"], reverse=True)  # newest first within each star level (sorts are stable)
    books.sort(key=lambda b: b["hugh"].get("stars") or 0, reverse=True)
    for book in books:
        book["readers"].sort(key=lambda r: r["read"])
    return data.get("draft", False), genres, books, titles


def views_of(book):
    """The filter views a book belongs to besides "all"."""
    ratings = [r["stars"] for r in book["readers"]]
    views = []
    if book["status"] == "available":
        views.append("available")
    if book["hugh"].get("stars") == 3:
        views.append("pick")
    if len(ratings) >= 2 and all(s == 3 for s in ratings):
        views.append("consensus")
    if 3 in ratings and 1 in ratings:
        views.append("split")
    return views


def stars(lang, n):
    """n of three stars, read out as text by screen readers."""
    off = f'<span class="off">{"★" * (3 - n)}</span>' if n < 3 else ""
    return f'<span class="stars" role="img" aria-label="{attr(UI[lang]["stars"](n))}"><span class="on">{"★" * n}</span>{off}</span>'


def card(lang, book, genres, titles):
    ui = UI[lang]
    ko = ' lang="ko"' if lang == "en" else ""  # Korean text on the English page
    own = book.get("language", "ko")
    mark = f' lang="{own}"' if own != lang else ""  # the book's title and byline, in the book's language

    def korean(value):
        return f'<span lang="ko">{text(value)}</span>' if lang == "en" else text(value)

    readers, views, hugh = book["readers"], views_of(book), book["hugh"]
    meta = [genres[g][lang] for g in book["genres"]]
    if book["status"] != "not-lent":
        meta.append(ui["deposit"](book["deposit"]))
    if book["loans"]:
        meta.append(ui["loans"](book["loans"]))
    status = ui["status"][book["status"]]
    if book.get("waitlist"):
        status += " · " + ui["waitlist"](book["waitlist"])
    badges = [f'<span class="badge flag">{text(ui[view])}</span>' for view in ("consensus", "split") if view in views]
    badges.append(f'<span class="badge st-{book["status"]}">{text(status)}</span>')
    byline = book["author"]
    if book.get("translator"):
        byline += f" · {book['translator']} 옮김"
    byline += f" · {book['publisher']}"

    lines = [
        f'<li id="book-{book["id"]}" data-genres="{attr(" ".join(book["genres"]))}" data-views="{" ".join(views)}">',
        '    <article class="book">',
        '        <div class="book-top">',
        f'            <p class="meta">{text(" · ".join(meta))}</p>',
        f'            <p class="badges">{" ".join(badges)}</p>',
        '        </div>',
        f'        <h3{mark}>{text(book["title"])}</h3>',
    ]
    if book.get("subtitle"):
        lines.append(f'        <p class="subtitle"{mark}>{text(book["subtitle"])}</p>')
    if book.get("original"):
        original = text(book["original"])
        lines.append(f'        <p class="original">원제 <span lang="en">{original}</span></p>' if lang == "ko"
                     else f'        <p class="original">{original}</p>')
    lines.append(f'        <p class="byline"{mark}>{text(byline)}</p>')
    review = hugh.get("reviewEn") if lang == "en" and hugh.get("reviewEn") else hugh.get("review")
    if hugh.get("stars") or review:
        pick = '        <p class="pick"><span class="who">Hugh</span>'
        if hugh.get("stars"):
            pick += f' {stars(lang, hugh["stars"])} <span class="mood">{text(ui["mood"][hugh["stars"]])}</span>'
        lines.append(pick + '</p>')
        if review:
            review_lang = "" if lang == "en" and hugh.get("reviewEn") else ko
            lines.append(f'        <p class="pick-review"{review_lang}>{text(review)}</p>')
    if readers:
        tally = {s: sum(1 for r in readers if r["stars"] == s) for s in STARS}
        average = sum(r["stars"] for r in readers) / len(readers)
        counts = " · ".join(  # only the star levels someone gave, so the line stays short in a narrow card
            f'<span class="count"><span class="on" aria-hidden="true">{"★" * s}</span>'
            f'<span class="sr">{text(ui["star_count"](s))}</span> {tally[s]}</span>' for s in STARS if tally[s])
        segments = "".join(f'<span class="s{s}" style="--n: {tally[s]}"></span>' for s in STARS if tally[s])
        # The tally is the summary of a disclosure: stars at a glance, the reviews one click away.
        lines += [
            '        <details class="tally">',
            '            <summary>',
            f'                <span class="tally-line">{text(ui["tally"](len(readers), average))} · {counts}</span>',
            f'                <span class="bar" aria-hidden="true">{segments}</span>',
            '            </summary>',
            '            <ul class="reviews">',
        ]
        for reader in readers:
            lines += [
                '                <li>',
                f'                    <p class="review-meta">{korean(reader["nick"])} · '
                f'<time datetime="{reader["read"]}">{reader["read"]}</time> · {stars(lang, reader["stars"])}</p>',
            ]
            if reader.get("line"):
                lines.append(f'                    <p class="review-line"{ko}>{text(reader["line"])}</p>')
            if reader.get("for"):
                lines.append(f'                    <p class="review-for">{text(ui["for"])}{korean(reader["for"])}</p>')
            lines.append('                </li>')
        lines += ['            </ul>', '        </details>']
    if book.get("knowledge"):
        links = ", ".join(f'<a href="{KNOWLEDGE_PATH[lang]}{slug}/">{text(titles[lang][slug])}</a>' for slug in book["knowledge"])
        lines.append(f'        <p class="related">{text(ui["related"])}{links}</p>')
    if book.get("note"):
        lines.append(f'        <p class="note">{text(book["note"][lang])}</p>')
    lines += ['    </article>', '</li>']
    return lines


def shelf(lang, books, genres, titles):
    if not books:
        return [f'<p class="empty">{text(UI[lang]["empty"])}</p>']
    lines = ['<ol id="shelf" class="shelf" aria-labelledby="shelf-title">']
    for book in books:
        lines += ["    " + line for line in card(lang, book, genres, titles)]
    return lines + ['</ol>']


def filters(lang, books, genres):
    """The available-only switch and the genre chips (all on at first), hidden until the page script runs.
    The page script keeps the counts in step with the switch."""
    if not books:
        return []
    ui = UI[lang]
    available = sum(1 for b in books if "available" in views_of(b))
    lines = ['<div id="filters" class="filters" hidden>',
             '    <div class="filter-head">',
             '        <button type="button" id="available-only" class="switch" role="switch" aria-checked="false">'
             '<span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>'
             f'{text(ui["available_only"])} <span class="n">{available}</span></button>',
             f'        <p id="filter-count" class="filter-count" aria-live="polite" data-format="{attr(ui["count"])}"></p>',
             '    </div>',
             f'    <div class="filter-row" role="group" aria-label="{attr(ui["genre_group"])}">']
    for key, labels in genres.items():
        n = sum(1 for b in books if key in b["genres"])
        if n:
            lines.append(f'        <button type="button" data-genre="{attr(key)}" aria-pressed="true">{text(labels[lang])} <span class="n">{n}</span></button>')
    lines += ['    </div>',
              f'    <p id="filter-empty" class="filter-empty" hidden>{text(ui["no_match"])}</p>',
              '</div>']
    return lines


def stats(lang, books):
    counts = {"books": len(books),
              "available": sum(1 for b in books if b["status"] == "available"),
              "loans": sum(b["loans"] for b in books),
              "reviews": sum(len(b["readers"]) for b in books)}
    return ['<div class="shell">',
            '    <p aria-hidden="true"><span class="prompt">$</span> ls ~/books</p>',
            f'    <p class="out">{UI[lang]["stats"](counts)}</p>',
            '</div>']


def rating(n):
    return {"@type": "Rating", "ratingValue": n, "bestRating": 3, "worstRating": 1}


def structured_data(lang, doc, books, genres):
    name = html.unescape(re.search(r'<h1 id="page-title">([^<]*)</h1>', doc).group(1))
    description = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', doc).group(1))
    page = PAGE[lang]
    items = []
    for position, book in enumerate(books, 1):
        item = {"@type": "Book", "@id": f"{page}#book-{book['id']}", "url": f"{page}#book-{book['id']}",
                "name": book["title"], "inLanguage": book.get("language", "ko"),
                "author": [{"@type": "Person", "name": n} for n in names(book["author"])],
                "genre": [genres[g][lang] for g in book["genres"]]}
        if book.get("subtitle"):
            item["alternativeHeadline"] = book["subtitle"]
        if book.get("original"):
            item["alternateName"] = book["original"]
        if book.get("translator"):
            item["translator"] = [{"@type": "Person", "name": n} for n in names(book["translator"])]
        if book.get("isbn"):
            item["isbn"] = book["isbn"]
        item["publisher"] = {"@type": "Organization", "name": book["publisher"]}
        reviews = []
        hugh = book["hugh"]
        body = hugh.get("reviewEn") if lang == "en" and hugh.get("reviewEn") else hugh.get("review")
        if hugh.get("stars") or body:
            review = {"@type": "Review", "author": {"@id": SITE + "#person"}}
            if hugh.get("stars"):
                review["reviewRating"] = rating(hugh["stars"])
            if body:
                review["reviewBody"] = body
                review["inLanguage"] = "en" if lang == "en" and hugh.get("reviewEn") else "ko"
            reviews.append(review)
        for reader in book["readers"]:
            review = {"@type": "Review", "author": {"@type": "Person", "name": reader["nick"]},
                      "datePublished": reader["read"], "reviewRating": rating(reader["stars"])}
            if reader.get("line"):
                review["reviewBody"] = reader["line"]
                review["inLanguage"] = "ko"
            reviews.append(review)
        if reviews:
            item["review"] = reviews
        items.append({"@type": "ListItem", "position": position, "item": item})
    collection = {"@type": "CollectionPage", "@id": page + "#collection", "url": page, "name": name,
                  "description": description, "inLanguage": lang, "author": {"@id": SITE + "#person"}}
    if lang == "ko":
        collection["workTranslation"] = {"@id": PAGE["en"] + "#collection"}
    else:
        collection["translationOfWork"] = {"@id": PAGE["ko"] + "#collection"}
    collection["mainEntity"] = {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items}
    graph = [
        collection,
        {"@type": "Person", "@id": SITE + "#person", "name": "Hugh Q Lee", "url": SITE,
         "jobTitle": "Vision AI Product Engineer", "sameAs": SAME_AS},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Hugh Q Lee", "item": HOME[lang]},
            {"@type": "ListItem", "position": 2, "name": "Books", "item": page}]},
    ]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return ['<script type="application/ld+json">', *body.splitlines(), '</script>']


def replace_block(doc, name, lines, indent):
    start, end = f"{indent}<!-- generated:{name} -->\n", f"{indent}<!-- /generated:{name} -->"
    if doc.count(start) != 1 or doc.count(end) != 1:
        sys.exit(f"<!-- generated:{name} --> markers not found once at their expected indent")
    i, j = doc.index(start) + len(start), doc.index(end)
    return doc[:i] + "".join(indent + line + "\n" for line in lines) + doc[j:]


def build():
    draft, genres, books, titles = load()
    unread = [b for b in books if not b["hugh"].get("stars")]
    books = [b for b in books if b["hugh"].get("stars")]  # not read yet: kept in the file, not listed or lent
    outputs = {}
    for lang, path in PAGE_FILE.items():
        doc = path.read_text(encoding="utf-8")
        doc = replace_block(doc, "robots", [ROBOTS_DRAFT if draft else ROBOTS], "    ")
        doc = replace_block(doc, "jsonld", structured_data(lang, doc, books, genres), "    ")
        doc = replace_block(doc, "draft", [f'<p class="draft" role="note">{text(UI[lang]["draft"])}</p>'] if draft else [], "        ")
        doc = replace_block(doc, "stats", stats(lang, books), "            ")
        doc = replace_block(doc, "filters", filters(lang, books, genres), "            ")
        doc = replace_block(doc, "shelf", shelf(lang, books, genres, titles), "            ")
        outputs[path] = doc
    return outputs, draft, unread


def main():
    check = "--check" in sys.argv[1:]
    outputs, draft, unread = build()
    changed = [path for path, doc in outputs.items() if path.read_text(encoding="utf-8") != doc]
    names_changed = ", ".join(str(path.relative_to(ROOT)) for path in changed)
    if draft:
        print('note: books/books.json has "draft": true: both pages show a draft notice and stay noindex until it is false')
    if unread:
        print(f"note: {len(unread)} unrated book(s) are kept in books/books.json but not listed until they get stars")
    if check:
        print("up to date" if not changed else f"out of date: {names_changed} (run without --check)")
        sys.exit(1 if changed else 0)
    for path in changed:
        path.write_text(outputs[path], encoding="utf-8")
    print("wrote " + names_changed if changed else "already up to date")


if __name__ == "__main__":
    main()
