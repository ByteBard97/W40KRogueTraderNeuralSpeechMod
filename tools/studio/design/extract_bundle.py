"""Unpack the Claude Design bundle (a single big .html) into reviewable pieces.

    python3 -I tools/studio/design/extract_bundle.py "<bundle>.html" docs/design/voice-studio-redesign

Writes shared.css (tokens + components, identical on every page), fonts.css + fonts/*.woff2 (urls rewritten to
fonts/<name>), and one pages/<slug>.html per board (page style, markup and its small state script). Needs only the stdlib.
"""
import base64, gzip, hashlib, json, pathlib, re, sys

def block(s: str, kind: str) -> str:
    st = re.search(r'<script type="__bundler/%s">' % kind, s).end()
    return s[st:s.index("</script>", st)]

def unpack(s: str) -> tuple[str, dict[str, bytes], list[str]]:
    man, tpl = json.loads(block(s, "manifest")), json.loads(block(s, "template"))
    assets = {}
    for uid, e in man.items():
        b = base64.b64decode(e["data"])
        assets[uid] = gzip.decompress(b) if e.get("compressed") else b
    return tpl, assets, json.loads(block(s, "page_order"))

def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

def main(src: str, out: str) -> None:
    out_d = pathlib.Path(out)
    (out_d / "pages").mkdir(parents=True, exist_ok=True)
    (out_d / "fonts").mkdir(exist_ok=True)
    root_tpl, root_assets, order = unpack(open(src, encoding="utf-8").read())
    shared_hashes, fonts_css, font_files = set(), "", {}
    for uid in order:
        tpl, assets, _ = unpack(root_assets[uid].decode("utf-8"))
        title = re.search(r"<title>([^<]*)", tpl).group(1)
        if "420" in title:
            continue                       # same component as the desktop board, narrower frame
        styles = re.findall(r"<style>(.*?)</style>", tpl, re.S)
        shared, fonts, page_style = styles[0], styles[1], "\n".join(styles[2:])
        shared_hashes.add(hashlib.md5(shared.encode()).hexdigest())
        if not fonts_css:
            fonts_css = fonts
            for fu in set(re.findall(r'url\("?([0-9a-f-]{36})"?\)', fonts)):
                font_files[fu] = assets[fu]
        body = tpl[tpl.index("<body>") + 6:]
        body = re.sub(r"<script[^>]*src=[^>]*></script>", "", body)
        body = re.sub(r"<helmet>.*?</helmet>\s*", "", body, flags=re.S)       # per-page copy of fonts.css
        (out_d / "pages" / f"{slug(title)}.html").write_text(
            f"<!-- {title} -->\n<style>\n{page_style}\n</style>\n{body}", encoding="utf-8")
        if not (out_d / "shared.css").exists():
            (out_d / "shared.css").write_text(shared, encoding="utf-8")
    assert len(shared_hashes) == 1, f"shared css differs between pages: {len(shared_hashes)} variants"
    for i, (fu, data) in enumerate(sorted(font_files.items())):
        name = f"font-{i:02d}.woff2"
        (out_d / "fonts" / name).write_bytes(data)
        fonts_css = re.sub(rf'url\("?{fu}"?\)', f"url(fonts/{name})", fonts_css)
    (out_d / "fonts.css").write_text(fonts_css, encoding="utf-8")
    print("pages:", sorted(p.name for p in (out_d / "pages").iterdir()), "fonts:", len(font_files))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
