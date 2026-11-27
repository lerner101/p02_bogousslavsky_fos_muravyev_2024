"""Apply the project's presentation to the generated ChartBook Pages site."""

import os
import re
import shutil
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs"
SHORT_DATA_LABELS = {
    "iti_agreement_by_year": "ITI agreement",
    "replication_scorecard": "Scorecard",
}
NAV_GROUPS = {
    "Pipeline Charts": "Charts",
    "Pipeline Dataframes": "Data",
    "Pipeline Models": "Models",
    "Pipeline Files": "Files",
}
EMOJI = re.compile(
    r"(?:[0-9#*]\ufe0f?\u20e3|[\U0001F000-\U0001FAFF\u2600-\u27BF]\ufe0f?)"
    r"(?:\u200d[\U0001F000-\U0001FAFF\u2600-\u27BF]\ufe0f?)*"
)
RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def relative_url(target, page):
    return Path(os.path.relpath(target, page.parent)).as_posix()


def style_navigation(soup):
    for brand in soup.select("a.navbar-brand.logo"):
        brand["class"].append("iti-brand")
        brand.string = "ITI Replication"
    for caption in soup.select(".caption-text"):
        label = caption.get_text(strip=True)
        caption.string = NAV_GROUPS.get(label, label)
    for label in soup.select(".bd-sidebar-primary nav a, article .toctree-wrapper a, .prev-next-title"):
        if label.get_text(strip=True) == "Chart List":
            label.string = "Chart gallery"
            continue
        identifier = label.find("code")
        if identifier is None or not label.get_text().startswith("Dataframe:"):
            continue
        name = label.get_text(" ", strip=True).partition(" - ")[2]
        dataset = identifier.get_text().rsplit(":", 1)[-1]
        label["title"] = name
        label.string = SHORT_DATA_LABELS.get(dataset, name.split(":", 1)[0] or dataset)
    # Chart source tags belong to the chart archive rather than every page's navigation.
    tag_cloud = soup.select_one(".bd-sidebar-primary .ablog__tagcloud")
    if tag_cloud is not None:
        tag_cloud.decompose()


def style_tables(soup):
    for table in soup.select("article table"):
        wrapper = table.parent
        if "pst-scrollable-table-container" not in wrapper.get("class", []):
            wrapper = table.wrap(soup.new_tag("div"))
        wrapper["class"] = [*wrapper.get("class", []), "iti-table"]
        if len(table.select("tr")) > 12:
            wrapper["class"].append("iti-table-long")
        wrapper["tabindex"] = "0"
        wrapper["role"] = "region"
        heading = table.find("caption") or table.find_previous(["h2", "h3", "h4"])
        if heading:
            wrapper["aria-label"] = heading.get_text(" ", strip=True).removesuffix(" #")
        else:
            wrapper["aria-label"] = "Table"


def chart_image(soup, src, alt, lazy=False):
    image = soup.new_tag("img", src=src, alt=alt, decoding="async")
    if lazy:
        image["loading"] = "lazy"
    return image


def style_chart(soup, page, asset, name):
    url = relative_url(asset, page)
    section = soup.select_one("article section#chart")
    if section is None or (embed := section.find("iframe")) is None:
        raise ValueError(f"Chart embed not found in {page}")
    frame = soup.new_tag("figure", attrs={"class": "iti-chart"})
    frame.append(chart_image(soup, url, name))
    embed.replace_with(frame)
    download = section.select_one("a.download")
    if download is not None:
        download.parent.decompose()
    link = soup.new_tag("a", href=url, attrs={"class": "iti-image-link"})
    link.string = "View full-size image"
    frame.insert_after(link)


def style_gallery(soup, page, charts):
    gallery = soup.select_one("article ul.postlist")
    if gallery is None:
        raise ValueError(f"Chart list not found in {page}")
    for heading in soup.find_all("h1"):
        if heading.contents and heading.contents[0] == "Chart List":
            heading.contents[0].replace_with("Chart gallery")
    gallery["class"].append("iti-gallery")
    for link in gallery.select(".ablog-post-title > a"):
        chart_id = Path(urlsplit(link["href"]).path).stem.rsplit(".", 1)[-1]
        if chart_id not in charts:
            continue
        asset, name = charts[chart_id]
        link.string = name
        preview = soup.new_tag("span", attrs={"class": "iti-chart-preview"})
        preview.append(chart_image(soup, relative_url(asset, page), "", lazy=True))
        link.insert(0, preview)
    if len(gallery.select(".iti-chart-preview")) != len(charts):
        raise ValueError("The Chart List does not contain every registered image")


def style_home(soup, project):
    title = soup.select_one("article h1")
    hero = title.wrap(soup.new_tag("header", attrs={"class": "iti-hero"}))
    intro = soup.new_tag("p")
    intro.string = project["description"]
    hero.append(intro)
    links = soup.new_tag("nav", attrs={"class": "iti-hero-links", "aria-label": "Explore the project"})
    old_charts = soup.select_one("article ul.postlist a")
    for label, href in [
        ("Browse charts", "cb/charts.html"),
        ("Project notes", "project_overview.html"),
    ]:
        link = soup.new_tag("a", href=href)
        link.string = label
        links.append(link)
    hero.append(links)
    if old_charts is not None:
        old_charts.find_parent("ul", class_="postlist").decompose()


def main():
    manifest = tomllib.loads((ROOT / "chartbook.toml").read_text(encoding="utf-8"))
    assets = SITE / "_static" / "iti-charts"
    assets.mkdir(exist_ok=True)
    charts = {}
    for chart_id, entry in manifest["charts"].items():
        source = ROOT / entry["path"]
        if source.suffix.lower() in RASTER_EXTENSIONS:
            destination = assets / f"{chart_id}{source.suffix.lower()}"
            shutil.copyfile(source, destination)
            charts[chart_id] = (destination, entry["name"])

    stylesheet = SITE / "_static" / "iti.css"
    if not stylesheet.is_file():
        raise FileNotFoundError(stylesheet)
    rendered = set()
    for path in SITE.rglob("*.html"):
        if path.relative_to(SITE).parts[0] in {"_static", "_downloads", "_sources"}:
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        if soup.head is None:
            continue
        for node in soup.find_all(string=EMOJI):
            if node.parent.name not in {"script", "style"}:
                node.replace_with(EMOJI.sub("", node))
        soup.head.append(soup.new_tag("link", rel="stylesheet", href=relative_url(stylesheet, path)))
        style_navigation(soup)
        style_tables(soup)
        if path == SITE / "index.html":
            style_home(soup, manifest["project"])
        elif path == SITE / "cb" / "charts.html":
            style_gallery(soup, path, charts)
        elif path.parent == SITE / "cb" / "charts":
            chart_id = path.stem.rsplit(".", 1)[-1]
            if chart_id in charts:
                style_chart(soup, path, *charts[chart_id])
                rendered.add(chart_id)
        path.write_text(str(soup), encoding="utf-8")
    if missing := charts.keys() - rendered:
        raise ValueError(f"Chart pages not found: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
