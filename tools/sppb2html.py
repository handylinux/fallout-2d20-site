#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sppb2html — convert SP Page Builder 5 JSON into clean, self-contained HTML.

The input can be:

  * a page object       {"template": "[...]", "css": "...", "title": "..."}
  * a raw template      "[{...}, {...}]"
  * a phpMyAdmin dump    (the export of the `jos_sppagebuilder` table)
  * the site database     `jos_sppagebuilder.zip` (read directly)

The output is a standalone HTML file: the JSON grid (rows -> columns -> addons)
is recreated with the same column widths, paddings, margins, backgrounds,
borders, shadows and typography, plus small vanilla-JS behaviours for tabs and
accordions.  No framework, no build step.

Usage
-----
    python3 tools/sppb2html.py data/supermutant.sppb.json -o pages/supermutant.html
    python3 tools/sppb2html.py data/*.sppb.json -o pages/
    python3 tools/sppb2html.py jos_sppagebuilder.zip --all -o build/site --limit 20

Every generated file ends with an HTML comment containing the counter of
sections / columns / addons / tables, e.g.

    <!-- sppb2html: sections=5 columns=9 addons=14 tables=7 -->
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import re
import uuid
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SITE = "https://www.fallout-2d20.ru/"

# SP Page Builder follows the Bootstrap 5 breakpoints.  `xl` is the desktop
# value and therefore the base rule; the rest are narrower ranges.
BPS = ("xl", "lg", "md", "sm", "xs")
MEDIA = {
    "lg": "(min-width: 992px) and (max-width: 1199.98px)",
    "md": "(min-width: 768px) and (max-width: 991.98px)",
    "sm": "(min-width: 576px) and (max-width: 767.98px)",
    "xs": "(max-width: 575.98px)",
}
MIN_WIDTH = {
    "xs": None,
    "sm": "(min-width: 576px)",
    "md": "(min-width: 768px)",
    "lg": "(min-width: 992px)",
    "xl": "(min-width: 1200px)",
}

# --------------------------------------------------------------------------- #
# tiny helpers
# --------------------------------------------------------------------------- #


def truthy(value: Any) -> bool:
    return value not in (None, False, 0, "", "0", "false", "False", "[]")


def as_responsive(value: Any) -> dict[str, Any]:
    """Normalise a SPPB responsive value into {xl, lg, md, sm, xs}."""
    if value is None:
        return {}
    if isinstance(value, dict):
        if any(bp in value for bp in BPS):
            return {bp: value[bp] for bp in BPS if bp in value and value[bp] not in (None, "")}
        return {}
    if isinstance(value, (int, float)):
        return {"xl": value}
    if isinstance(value, str) and value.strip():
        return {"xl": value}
    return {}


def norm_len(value: Any) -> str:
    """Clean up a length value (SPPB data often contains '5px 0px 5px px')."""
    if isinstance(value, (int, float)):
        return f"{value}px" if value else "0"
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return ""
    tokens: list[str] = []
    for token in text.split(" "):
        if token in ("px", "%", "em", "rem", "vw", "vh", "pt"):
            tokens.append("0" + token)
            continue
        if re.fullmatch(r"[-+]?\d*\.?\d+", token):
            tokens.append(token + "px")
            continue
        tokens.append(token)
    return " ".join(tokens)


def norm_raw(value: Any) -> str:
    """Clean up a value that already carries its unit (colors, auto, ...)."""
    if isinstance(value, (int, float)):
        return str(value)
    return re.sub(r"\s+", " ", str(value)).strip()


def responsive_decls(prop: str, value: Any, *, length: bool = True) -> list[tuple[str | None, str]]:
    """[(media, 'prop: value'), ...] — desktop value is the base rule."""
    data = as_responsive(value)
    out: list[tuple[str | None, str]] = []
    clean = norm_len if length else norm_raw
    if data.get("xl") is not None and str(data["xl"]).strip():
        out.append((None, f"{prop}: {clean(data['xl'])}"))
    for bp in ("lg", "md", "sm", "xs"):
        if data.get(bp) is not None and str(data[bp]).strip():
            out.append((bp, f"{prop}: {clean(data[bp])}"))
    return out


def to_percent(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith("%"):
        try:
            return float(text[:-1])
        except ValueError:
            return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        number = float(text)
        return number if 0 < number <= 100 else None
    return None


def heading_tag(value: Any, default: str = "h3") -> str:
    text = str(value or "").strip().lower()
    return text if re.fullmatch(r"h[1-6]", text) else default


def text_align(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if text in ("left", "center", "right", "justify") else None


def box_shadow(value: Any) -> str | None:
    """Return a CSS box-shadow or None when the shadow is disabled."""
    if isinstance(value, dict):
        if not truthy(value.get("enabled")):
            return None
        parts = []
        for key in ("ho", "vo", "blur", "spread"):
            raw = value.get(key)
            if raw in (None, ""):
                parts.append("0")
            else:
                number = re.sub(r"[^\d.\-]", "", str(raw)) or "0"
                parts.append(f"{number}px")
        color = value.get("color") or "rgba(0,0,0,.15)"
        inset = " inset" if truthy(value.get("inset")) else ""
        return f"{' '.join(parts)} {color}{inset}"
    if isinstance(value, str) and value.strip():
        text = re.sub(r"\s+", " ", value).strip()
        if re.fullmatch(r"0(px)? 0(px)? 0(px)? 0(px)? (#\w+|rgba?\([^)]*\))?", text):
            return None
        parts = text.split(" ")
        if len(parts) >= 4:
            nums = []
            for part in parts[:4]:
                if part.endswith("px"):
                    nums.append(part)
                else:
                    number = re.sub(r"[^0-9.\-]", "", part) or "0"
                    nums.append(number + "px")
            color = " ".join(parts[4:]) or "rgba(0,0,0,.15)"
            return f"{' '.join(nums)} {color}"
        return text
    return None


def typography_decls(typo: Any) -> list[tuple[str | None, str]]:
    if not isinstance(typo, dict):
        return []
    out: list[tuple[str | None, str]] = []
    font = (typo.get("font") or "").strip()
    if font:
        out.append((None, f"font-family: {font}"))
    weight = (str(typo.get("weight") or "")).strip()
    if weight:
        out.append((None, f"font-weight: {weight}"))
    if truthy(typo.get("italic")):
        out.append((None, "font-style: italic"))
    if truthy(typo.get("underline")):
        out.append((None, "text-decoration: underline"))
    if truthy(typo.get("uppercase")):
        out.append((None, "text-transform: uppercase"))
    for key, prop in (("size", "font-size"), ("line_height", "line-height"), ("letter_spacing", "letter-spacing")):
        block = typo.get(key)
        if not isinstance(block, dict):
            continue
        for bp, value in block.items():
            if bp not in BPS or not isinstance(value, dict):
                continue
            raw = value.get("value")
            if raw in (None, ""):
                continue
            unit = value.get("unit") or "px"
            text = f"{raw}{unit}" if str(raw).replace(".", "", 1).replace("-", "", 1).isdigit() else str(raw)
            out.append((None if bp == "xl" else bp, f"{prop}: {text}"))
    return out


def slug(value: Any, prefix: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]", "", str(value or ""))[:10]
    if not base:
        base = "x"
    candidate = f"{prefix}-{base}"
    index = 2
    while candidate in used:
        candidate = f"{prefix}-{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


# --------------------------------------------------------------------------- #
# CSS collection
# --------------------------------------------------------------------------- #


class StyleSheet:
    def __init__(self) -> None:
        self._rules: dict[tuple[str | None, str], list[str]] = {}

    def add(self, selector: str, declarations: Iterable[str | tuple[str | None, str]] | str, media: str | None = None) -> None:
        if not declarations:
            return
        if isinstance(declarations, str):
            declarations = [declarations]
        bucket = self._rules.setdefault((media, selector), [])
        for declaration in declarations:
            if isinstance(declaration, tuple):
                decl_media, decl = declaration
                if decl_media != media:
                    self.add(selector, [decl], decl_media)
                else:
                    bucket.append(decl)
            elif declaration:
                bucket.append(declaration)

    def add_responsive(self, selector: str, declarations: list[tuple[str | None, str]]) -> None:
        for media, declaration in declarations:
            self.add(selector, [declaration], media)

    def render(self) -> str:
        chunks: list[str] = []
        # base rules first, then the media queries in desktop -> mobile order
        for (media, selector), declarations in self._rules.items():
            if media is None:
                chunks.append(f"{selector} {{ {'; '.join(dict.fromkeys(declarations))}; }}")
        for media in MEDIA.values():
            lines = []
            for (rule_media, selector), declarations in self._rules.items():
                if rule_media == media:
                    lines.append(f"  {selector} {{ {'; '.join(dict.fromkeys(declarations))}; }}")
            if lines:
                chunks.append("@media " + media + " {\n" + "\n".join(lines) + "\n}")
        return "\n".join(chunks)


# --------------------------------------------------------------------------- #
# Base CSS — a small Bootstrap-compatible subset used by SP Page Builder
# --------------------------------------------------------------------------- #

BASE_CSS = r"""
:root{
  --sppb-container: 1140px;
  --sppb-gutter: 15px;
  --sppb-text: #212529;
  --sppb-muted: #6c757d;
  --sppb-link: #0b5cad;
  --sppb-border: #dee2e6;
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;font-size:16px;line-height:1.5;color:var(--sppb-text);background:#fff}
img{max-width:100%;height:auto;vertical-align:middle}
figure{margin:0}
p{margin:0 0 1rem}
ul,ol{margin:0 0 1rem;padding-left:1.5rem}
dl{margin:0 0 1rem}
a{color:var(--sppb-link);text-decoration:none}
a:hover{text-decoration:underline}
h1,h2,h3,h4,h5,h6{margin:0 0 .5rem;font-weight:600;line-height:1.2}
h1{font-size:2.5rem}
h2{font-size:2rem}
h3{font-size:1.75rem}
h4{font-size:1.5rem}
h5{font-size:1.25rem}
h6{font-size:1rem}
table{border-collapse:collapse}
th{text-align:inherit}
hr{margin:1rem 0;border:0;border-top:1px solid rgba(0,0,0,.15)}
.sppb-text-left{text-align:left}
.sppb-text-center{text-align:center}
.sppb-text-right{text-align:right}

/* ---------- grid ---------- */
.sppb-section{position:relative;z-index:1}
.sppb-section--nested{position:relative}
.sppb-row-container{width:100%;max-width:var(--sppb-container);margin:0 auto;padding-right:15px;padding-left:15px}
.sppb-section-fullwidth > .sppb-row-container{max-width:100%}
.sppb-row{display:flex;flex-wrap:wrap;margin-right:calc(var(--sppb-gutter) / -2);margin-left:calc(var(--sppb-gutter) / -2)}
.sppb-no-gutter > .sppb-row{--sppb-gutter:0px}
.sppb-row--align-center{align-items:center}
.sppb-column{position:relative;width:100%;min-height:1px;padding-right:calc(var(--sppb-gutter) / 2);padding-left:calc(var(--sppb-gutter) / 2)}
.sppb-column--vcenter{display:flex;flex-direction:column;justify-content:center}
""" + "\n".join(
    # .sppb-col-N (mobile base) and .sppb-col-BP-N
    [f".sppb-col-{n}{{flex:0 0 {n / 12 * 100:.6f}%;max-width:{n / 12 * 100:.6f}%}}" for n in range(1, 13)]
    + [
        f"@media {MIN_WIDTH[bp]}{{\n"
        + "\n".join(f"  .sppb-col-{bp}-{n}{{flex:0 0 {n / 12 * 100:.6f}%;max-width:{n / 12 * 100:.6f}%}}" for n in range(1, 13))
        + "\n}"
        for bp in ("sm", "md", "lg", "xl")
    ]
) + r"""

/* ---------- addons ---------- */
.sppb-addon{position:relative}
.sppb-addon > :first-child{margin-top:0}
.sppb-addon > :last-child{margin-bottom:0}
.sppb-addon-content > :last-child{margin-bottom:0}
.sppb-addon-nested-row{position:relative}
.sppb-addon-image{line-height:0}
.sppb-addon-image .sppb-image-title{line-height:1.4;margin:.5rem 0}
.sppb-image-link{display:inline-block;line-height:0}
.sppb-table-wrap{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}

/* ---------- content tables (text blocks) ---------- */
.sppb-addon-content table{border-collapse:collapse;max-width:100%}
.sppb-addon-content th,.sppb-addon-content td{vertical-align:middle}
.sppb-addon-content img{max-width:100%;height:auto}
.sppb-addon-content img.cd-icon,.sppb-addon-content .cd-icon,.cd-icon{height:calc(1em + 2px);width:auto;max-width:none;display:inline-block;vertical-align:-.15em}
.sppb-term{font-weight:700;text-transform:uppercase}

/* ---------- tabs ---------- */
.sppb-tabs-nav{display:flex;flex-wrap:wrap;margin:0;padding:0;list-style:none;gap:2px}
.sppb-tabs-nav > li{display:flex}
.sppb-tabs-nav a{display:flex;align-items:center;justify-content:center;gap:.4em;padding:.5rem 1rem;border:1px solid transparent;text-decoration:none;cursor:pointer;transition:background-color .2s,color .2s,border-color .2s}
.sppb-tabs-nav a:hover{text-decoration:none}
.sppb-tabs-nav a.is-active{cursor:default}
.sppb-tabs--justified .sppb-tabs-nav > li{flex:1 1 0}
.sppb-tabs--justified .sppb-tabs-nav a{width:100%;text-align:center}
.sppb-tab-pane{display:none}
.sppb-tab-pane.is-active{display:block}

/* ---------- accordion ---------- */
.sppb-accordion-item{overflow:hidden;margin-bottom:5px}
.sppb-accordion-title{margin:0;font-size:1rem;line-height:1.3}
.sppb-accordion-toggle{display:flex;width:100%;align-items:center;justify-content:space-between;gap:.75rem;padding:.75rem 1rem;border:0;background:none;font:inherit;font-weight:600;color:inherit;text-align:left;cursor:pointer}
.sppb-accordion-toggle::-webkit-details-marker{display:none}
.sppb-accordion-toggle::after{content:"+";flex:none;font-size:1.15em;line-height:1}
.sppb-accordion-item.is-open > .sppb-accordion-title .sppb-accordion-toggle::after{content:"\2212"}
.sppb-accordion-content{display:none;padding:1rem}
.sppb-accordion-item.is-open > .sppb-accordion-content{display:block}

/* ---------- advanced table ---------- */
.sppb-table{width:100%;border-collapse:collapse;margin:0}
.sppb-table th,.sppb-table td{padding:.5rem .6rem;border:1px solid var(--sppb-border);vertical-align:top}
.sppb-table thead th{font-weight:600}

/* ---------- misc addons ---------- */
.sppb-divider{border:0;border-top:1px solid rgba(0,0,0,.15);margin:1rem 0}
.sppb-button{display:inline-block;padding:.5rem 1rem;border:1px solid transparent;border-radius:.25rem;text-decoration:none}
.sppb-placeholder{margin:0;padding:.75rem 1rem;border:1px dashed #adb5bd;background:#f8f9fa;color:#6c757d;font-size:.875rem}
.sppb-feature-icon{display:inline-block;line-height:1}

/* ---------- responsive visibility ---------- */
@media (min-width: 1200px){.sppb-hidden-xl{display:none !important}}
@media (min-width: 992px) and (max-width: 1199.98px){.sppb-hidden-lg{display:none !important}}
@media (min-width: 768px) and (max-width: 991.98px){.sppb-hidden-md{display:none !important}}
@media (min-width: 576px) and (max-width: 767.98px){.sppb-hidden-sm{display:none !important}}
@media (max-width: 575.98px){.sppb-hidden-xs{display:none !important}}

/* ---------- container widths ---------- */
@media (min-width: 576px){.sppb-row-container{max-width:540px}}
@media (min-width: 768px){.sppb-row-container{max-width:720px}}
@media (min-width: 992px){.sppb-row-container{max-width:960px}}
@media (min-width: 1200px){.sppb-row-container{max-width:1140px}}
.sppb-section-fullwidth > .sppb-row-container{max-width:100%}

:focus-visible{outline:2px solid #0b5cad;outline-offset:2px}
"""

SCRIPT = r"""
(function () {
  "use strict";

  function activate(tabs, paneId) {
    tabs.querySelectorAll("[data-sppb-tab]").forEach(function (link) {
      var on = link.getAttribute("href") === "#" + paneId;
      link.classList.toggle("is-active", on);
      link.setAttribute("aria-selected", on ? "true" : "false");
      link.tabIndex = on ? 0 : -1;
    });
    tabs.querySelectorAll(".sppb-tab-pane").forEach(function (pane) {
      var on = pane.id === paneId;
      pane.classList.toggle("is-active", on);
      if (on) { pane.removeAttribute("hidden"); } else { pane.setAttribute("hidden", ""); }
    });
  }

  document.addEventListener("click", function (event) {
    var link = event.target.closest("[data-sppb-tab]");
    if (!link) { return; }
    event.preventDefault();
    var tabs = link.closest("[data-sppb-tabs]");
    var paneId = link.getAttribute("href").slice(1);
    activate(tabs, paneId);
    if (history.replaceState) { history.replaceState(null, "", "#" + paneId); }
  });

  document.addEventListener("keydown", function (event) {
    var link = event.target.closest("[data-sppb-tab]");
    if (!link || (event.key !== "ArrowRight" && event.key !== "ArrowLeft")) { return; }
    var tabs = link.closest("[data-sppb-tabs]");
    var links = Array.prototype.slice.call(tabs.querySelectorAll("[data-sppb-tab]"));
    var index = links.indexOf(link) + (event.key === "ArrowRight" ? 1 : -1);
    if (index < 0) { index = links.length - 1; }
    if (index >= links.length) { index = 0; }
    links[index].focus();
    links[index].click();
  });

  document.querySelectorAll("[data-sppb-tabs]").forEach(function (tabs) {
    var hash = window.location.hash.slice(1);
    if (hash && document.getElementById(hash) && tabs.contains(document.getElementById(hash))) {
      activate(tabs, hash);
    }
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".sppb-accordion-toggle");
    if (!button) { return; }
    var item = button.closest(".sppb-accordion-item");
    var open = item.classList.toggle("is-open");
    button.setAttribute("aria-expanded", open ? "true" : "false");
    var content = item.querySelector(".sppb-accordion-content");
    if (!content) { return; }
    if (open) { content.removeAttribute("hidden"); } else { content.setAttribute("hidden", ""); }
  });
})();
"""


# --------------------------------------------------------------------------- #
# Input loading
# --------------------------------------------------------------------------- #


class Page:
    def __init__(self, title: str, rows: list[dict], css: str = "", language: str = "ru", source: str = "") -> None:
        self.title = title or "Без названия"
        self.rows = rows
        self.css = css or ""
        lang = (language or "ru").strip()
        self.language = lang if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", lang) else "ru"
        self.source = source


def _apply_mobile_clone(rows: list[dict], config: dict) -> list[dict]:
    """Скопировать аддон в другую колонку для мобильной версии.

    Конфиг страницы::

        "mobile_clone": {
            "from": "<id аддона-описания>",
            "into": "<id колонки, куда вставить>",
            "after": "<id аддона, после которого вставить>",
            "class": "supermutant-desc-mobile",
            "hide_class": "supermutant-desc-original"
        }

    Клон получает новый id и указанный класс; секция-источник — hide_class,
    чтобы её можно было скрыть на мобильном через CSS.
    """
    source_id = config.get("from")
    target_column_id = config.get("into")
    after_id = config.get("after")
    clone_class = config.get("class") or "mobile-clone"
    hide_class = config.get("hide_class") or "mobile-hide-source"

    source_section = None
    source_addon = None
    for section in rows:
        for column in section.get("columns", []):
            for addon in column.get("addons", []):
                if addon.get("id") == source_id:
                    source_section, source_addon = section, addon
                    break
    if source_addon is None:
        raise ValueError(f"mobile_clone: addon {source_id!r} not found")

    if hide_class and source_section is not None:
        settings = source_section.setdefault("settings", {})
        classes = [c for c in str(settings.get("class") or "").split() if c]
        if hide_class not in classes:
            classes.append(hide_class)
        settings["class"] = " ".join(classes)

    target_column = None
    for section in rows:
        for column in section.get("columns", []):
            if column.get("id") == target_column_id:
                target_column = column
                break
    if target_column is None:
        raise ValueError(f"mobile_clone: column {target_column_id!r} not found")

    clone = copy.deepcopy(source_addon)
    clone["id"] = str(uuid.uuid4())
    settings = clone.setdefault("settings", {})
    classes = [c for c in str(settings.get("class") or "").split() if c]
    if clone_class not in classes:
        classes.append(clone_class)
    settings["class"] = " ".join(classes)

    addons = target_column.setdefault("addons", [])
    insert_at = len(addons)
    if after_id:
        for index, addon in enumerate(addons):
            if addon.get("id") == after_id:
                insert_at = index + 1
                break
    addons.insert(insert_at, clone)
    return rows


def _page_from_object(obj: dict, source: str = "") -> Page:
    template = obj.get("template")
    if template is None:
        raise ValueError("page object has no 'template' key")
    rows = json.loads(template) if isinstance(template, str) else template
    if isinstance(rows, list) and isinstance(obj.get("mobile_clone"), dict):
        rows = _apply_mobile_clone(rows, obj["mobile_clone"])
    return Page(
        title=obj.get("title") or "",
        rows=rows if isinstance(rows, list) else [],
        css=obj.get("css") or "",
        language=obj.get("language") or "ru",
        source=source,
    )


def load_pages(path: str | Path) -> list[Page]:
    """Load pages from a wrapper JSON, a raw template, a DB dump or the zip."""
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.endswith(".json")]
            if not names:
                raise ValueError(f"{path}: no JSON inside the archive")
            data = json.loads(archive.read(names[0]))
    else:
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not valid JSON ({exc})") from exc

    # 1) wrapper object {"template": "...", ...}
    if isinstance(data, dict) and "template" in data:
        return [_page_from_object(data, str(path))]

    # 2) phpMyAdmin dump -> list of {type, name, data}
    if isinstance(data, list) and data and isinstance(data[0], dict) and "type" in data[0]:
        if str(data[0].get("type")).lower() == "header":
            table = next((item for item in data if item.get("type") == "table"), None)
            if table is None:
                raise ValueError(f"{path}: dump contains no table")
            pages = []
            for row in table.get("data", []):
                raw = row.get("content") or row.get("text") or ""
                if not raw:
                    continue
                try:
                    rows = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rows, list):
                    continue
                pages.append(
                    Page(
                        title=row.get("title") or f"page-{row.get('id', len(pages) + 1)}",
                        rows=rows,
                        css=row.get("css") or "",
                        language=row.get("language") or "ru",
                        source=f"{path}#{row.get('id', '')}",
                    )
                )
            return pages

    # 3) raw template array
    if isinstance(data, list) and data and isinstance(data[0], dict) and "settings" in data[0]:
        return [Page(title=path.stem, rows=data, source=str(path))]

    # 4) list of wrapper objects
    if isinstance(data, list) and data and isinstance(data[0], dict) and "template" in data[0]:
        return [_page_from_object(obj, str(path)) for obj in data]

    raise ValueError(f"{path}: unsupported JSON shape")


# --------------------------------------------------------------------------- #
# Renderer
# --------------------------------------------------------------------------- #


class Renderer:
    def __init__(self, page: Page, *, asset_base: str = DEFAULT_SITE, link_base: str = DEFAULT_SITE) -> None:
        self.page = page
        self.asset_base = (asset_base or "").rstrip("/") + "/" if asset_base else ""
        self.link_base = (link_base or "").rstrip("/") + "/" if link_base else ""
        self.css = StyleSheet()
        self.used_ids: set[str] = set()
        self.warnings: list[str] = []
        self.stats: Counter[str] = Counter()
        self.rows: dict[str, dict] = {row.get("id"): row for row in page.rows if row.get("id")}
        self._render_stack: set[str] = set()
        self._tab_counter = 0

    # ------------------------------------------------------------------ utils

    def asset_url(self, url: str | None) -> str:
        return self._fix_url(url, self.asset_base)

    def link_url(self, url: str | None) -> str:
        return self._fix_url(url, self.link_base)

    @staticmethod
    def _fix_url(url: str | None, base: str) -> str:
        if url is None:
            return ""
        value = str(url).strip()
        if not value:
            return ""
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", value, re.I):
            return value
        if not base:
            return value
        if value.startswith("/"):
            return base.rstrip("/") + value
        return base + value

    def _rewrite_urls(self, text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            attr, quote, url = match.group(1), match.group(2), match.group(3)
            if url.startswith(("data:", "javascript:")):
                return match.group(0)
            base = self.link_base if attr.lower() == "href" else self.asset_base
            return f'{attr}={quote}{self._fix_url(url, base)}{quote}'

        return re.sub(r'\b(href|src)=(["\'])(.*?)\2', repl, text, flags=re.I | re.S)

    def _process_html(self, text: str | None) -> str:
        if not text:
            return ""
        value = str(text)
        # WordPress/TinyMCE leftovers that break HTML parsing
        value = re.sub(r"</?mce:root[^>]*>", "", value)
        value = value.replace("data-mce-root=\"1\"", "")
        # combat dice icon (Joomla content plugin shortcode used by the site)
        cd_icon = f'<img class="cd-icon" src="{html.escape(self.asset_url("images/CD.png"), quote=True)}" alt="Боевой кубик">'
        value = value.replace("{/CD}", cd_icon).replace("{\\/CD}", cd_icon)
        # glossary/trait shortcodes: {Иммунитет к радиации}
        def term(match: re.Match[str]) -> str:
            label = match.group(1).strip()
            if not label or label.startswith("/"):
                return match.group(0)
            return f'<strong class="sppb-term">{html.escape(label)}</strong>'

        value = re.sub(r"\{([^{}<>]{2,80})\}", term, value)
        # responsive wrappers for author tables
        def table(match: re.Match[str]) -> str:
            self.stats["tables"] += 1
            return '<div class="sppb-table-wrap">' + match.group(0) + "</div>"

        value = re.sub(r"<table\b.*?</table>", table, value, flags=re.I | re.S)
        return self._rewrite_urls(value)

    def _link_attrs(self, link: dict | None) -> tuple[str, str]:
        if not isinstance(link, dict):
            return "", ""
        url = ""
        if link.get("type") == "menu":
            url = link.get("menu") or link.get("url") or ""
        else:
            url = link.get("url") or link.get("menu") or ""
        if not url:
            return "", ""
        attrs = f' href="{html.escape(self.link_url(url), quote=True)}"'
        rel: list[str] = []
        if truthy(link.get("new_tab")):
            attrs += ' target="_blank"'
            rel.append("noopener")
        if truthy(link.get("nofollow")):
            rel.append("nofollow")
        if truthy(link.get("noreferrer")):
            rel.append("noreferrer")
        if truthy(link.get("noopener")) and "noopener" not in rel:
            rel.append("noopener")
        if rel:
            attrs += f' rel="{" ".join(rel)}"'
        return attrs, url

    def _hidden_classes(self, settings: dict) -> list[str]:
        return [f"sppb-hidden-{bp}" for bp in BPS if truthy(settings.get(f"hidden_{bp}"))]

    def _background_decls(self, settings: dict, prefix: str) -> list[str]:
        out: list[str] = []
        color = settings.get(f"{prefix}background_color")
        if not color and prefix:
            color = settings.get(f"{prefix}global_background_color")
        if color:
            out.append(f"background-color: {color}")
        kind = str(settings.get(f"{prefix}background_type") or "none").lower()
        if kind == "gradient":
            gradient = settings.get(f"{prefix}background_gradient") or {}
            if isinstance(gradient, dict) and gradient.get("color"):
                color2 = gradient.get("color2") or gradient.get("color")
                deg = gradient.get("deg") or 0
                name = "radial-gradient(circle" if gradient.get("type") == "radial" else f"linear-gradient({deg}deg"
                out.append(f"background-image: {name}, {gradient['color']}, {color2})")
        elif kind == "image":
            image = settings.get(f"{prefix}background_image") or {}
            src = image.get("src") if isinstance(image, dict) else image
            if src:
                out.append(f"background-image: url('{self.asset_url(src)}')")
                repeat = settings.get(f"{prefix}background_repeat")
                size = settings.get(f"{prefix}background_size")
                attachment = settings.get(f"{prefix}background_attachment")
                position = settings.get(f"{prefix}background_position")
                if repeat and repeat != "inherit":
                    out.append(f"background-repeat: {repeat}")
                if size and size != "inherit":
                    out.append(f"background-size: {size}")
                if attachment and attachment != "inherit":
                    out.append(f"background-attachment: {attachment}")
                if position and position != "inherit":
                    out.append(f"background-position: {position}")
        return out

    def _border_decls(self, settings: dict, prefix: str) -> list[str]:
        out: list[str] = []
        flag = settings.get(f"{prefix}user_border")
        if prefix == "":
            flag = settings.get("row_border")
        if not truthy(flag):
            return out
        width = settings.get(f"{prefix}border_width")
        out.append("border-style: solid")
        out.extend(decl for _, decl in responsive_decls("border-width", width))
        color = settings.get(f"{prefix}border_color") or settings.get("border_color")
        if color:
            out.append(f"border-color: {color}")
        return out

    def _radius_decls(self, settings: dict, prefix: str) -> list[str]:
        value = settings.get(f"{prefix}border_radius")
        return [decl for _, decl in responsive_decls("border-radius", value)] if value else []

    def _box_css(self, selector: str, settings: dict, kind: str, text_color: bool = True) -> None:
        """Emit the common box model for a section / column / addon."""
        if kind == "section":
            padding = settings.get("padding")
            margin = settings.get("margin")
            self.css.add_responsive(selector, responsive_decls("padding", padding))
            self.css.add_responsive(selector, responsive_decls("margin", margin))
            self.css.add(selector, self._background_decls(settings, ""))
            self.css.add(selector, self._border_decls(settings, "row_"))
            self.css.add(selector, self._radius_decls(settings, "row_"))
            shadow = box_shadow(settings.get("row_boxshadow"))
            if shadow:
                self.css.add(selector, [f"box-shadow: {shadow}"])
            overflow_x = settings.get("section_overflow_x")
            if overflow_x in ("hidden", "auto", "scroll"):
                # SPPB stores "scroll" as a default on many pages; only hidden
                # is reproduced faithfully (scroll would add nested scrollbars).
                if overflow_x == "hidden":
                    self.css.add(selector, ["overflow-x: hidden"])
            return

        if kind == "column":
            self.css.add_responsive(selector, responsive_decls("padding", settings.get("padding")))
            self.css.add_responsive(selector, responsive_decls("margin", settings.get("margin")))
            self.css.add(selector, self._background_decls(settings, ""))
            if truthy(settings.get("use_border")):
                self.css.add(selector, ["border-style: solid"])
                self.css.add_responsive(selector, responsive_decls("border-width", settings.get("border_width")))
                if settings.get("border_color"):
                    self.css.add(selector, [f"border-color: {settings['border_color']}"])
            self.css.add(selector, self._radius_decls(settings, ""))
            shadow = box_shadow(settings.get("boxshadow"))
            if shadow:
                self.css.add(selector, [f"box-shadow: {shadow}"])
            return

        # addon
        self.css.add_responsive(selector, responsive_decls("padding", settings.get("global_padding")))
        self.css.add_responsive(selector, responsive_decls("margin", settings.get("global_margin")))
        self.css.add(selector, self._background_decls(settings, "global_"))
        if truthy(settings.get("global_user_border")):
            self.css.add(selector, ["border-style: solid"])
            self.css.add_responsive(selector, responsive_decls("border-width", settings.get("global_border_width")))
            if settings.get("global_border_color"):
                self.css.add(selector, [f"border-color: {settings['global_border_color']}"])
        self.css.add(selector, self._radius_decls(settings, "global_"))
        shadow = box_shadow(settings.get("global_boxshadow"))
        if shadow:
            self.css.add(selector, [f"box-shadow: {shadow}"])
        if text_color and settings.get("global_text_color"):
            self.css.add(selector, [f"color: {settings['global_text_color']}"])
        if settings.get("global_link_color"):
            self.css.add(f"{selector} a", [f"color: {settings['global_link_color']}"])
        if truthy(settings.get("global_custom_position")):
            self.css.add(selector, ["position: absolute"])
            left = settings.get("global_addon_position_left")
            top = settings.get("global_addon_position_top")
            if isinstance(left, dict) and left.get("value") not in (None, ""):
                self.css.add(selector, [f"left: {norm_len(left['value'])}"])
            if isinstance(top, dict) and top.get("value") not in (None, ""):
                self.css.add(selector, [f"top: {norm_len(top['value'])}"])

    # --------------------------------------------------------------- sections

    def render(self) -> str:
        body: list[str] = []
        for row in self.page.rows:
            if row.get("parent"):
                continue  # stored out of tree, rendered where it is referenced
            if not truthy(row.get("visibility", True)):
                continue
            body.append(self.render_section(row))

        custom_css: list[str] = []
        if self.page.css.strip():
            custom_css.append(self.page.css.strip())
        for row in self.page.rows:
            for settings in self._walk_row_settings(row):
                value = settings.get("global_custom_css")
                if value and value.strip() and value.strip() not in custom_css:
                    custom_css.append(value.strip())
        generated = self.css.render()

        stats = (
            f"sections={self.stats['sections']} columns={self.stats['columns']} "
            f"addons={self.stats['addons']} tables={self.stats['tables']}"
        )
        return f"""<!DOCTYPE html>
<html lang="{html.escape(self.page.language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(self.page.title)}</title>
<meta name="generator" content="sppb2html">
<style>
{BASE_CSS}
{generated}
{chr(10).join(custom_css)}
</style>
</head>
<body>
<div id="sp-page-builder">
<div class="sppb-page-content">
{chr(10).join(body)}
</div>
</div>
<script>
{SCRIPT}
</script>
<!-- sppb2html: {stats} -->
</body>
</html>
"""

    def _walk_row_settings(self, row: dict) -> Iterable[dict]:
        yield row.get("settings") or {}
        for column in row.get("columns") or []:
            yield column.get("settings") or {}
            for addon in column.get("addons") or []:
                yield from self._walk_addon_settings(addon)

    def _walk_addon_settings(self, addon: dict) -> Iterable[dict]:
        settings = addon.get("settings") or {}
        yield settings
        for key in ("sp_tab_item", "sp_accordion_item", "sp_table_advanced_item", "table_advanced_item"):
            for item in settings.get(key) or []:
                if not isinstance(item, dict):
                    continue
                for sub in item.get("content") or []:
                    if isinstance(sub, dict) and sub.get("settings"):
                        yield from self._walk_addon_settings(sub)
                for cell_row in item.get("table_advanced_item") or []:
                    for cell in cell_row.get("table_advanced_item") or []:
                        for sub in cell.get("content") or []:
                            if isinstance(sub, dict) and sub.get("settings"):
                                yield from self._walk_addon_settings(sub)

    def render_section(self, row: dict) -> str:
        self.stats["sections"] += 1
        settings = row.get("settings") or {}
        section_id = slug(row.get("id"), "section", self.used_ids)
        classes = ["sppb-section"]
        if truthy(settings.get("fullscreen")):
            classes.append("sppb-section-fullwidth")
        if truthy(settings.get("no_gutter")):
            classes.append("sppb-no-gutter")
        if settings.get("class"):
            classes.append(str(settings["class"]))
        classes.extend(self._hidden_classes(settings))
        if settings.get("id"):
            classes.append(str(settings["id"]))

        self._box_css(f"#{section_id}", settings, "section")
        gutter = as_responsive(settings.get("columns_gap"))
        if gutter:
            for bp, value in gutter.items():
                self.css.add(f"#{section_id} .sppb-row", [f"--sppb-gutter: {norm_len(value)}"], None if bp == "xl" else bp)

        title_html = ""
        if settings.get("title"):
            tag = heading_tag(settings.get("heading_selector") or "h2")
            title_html = (
                f'<div class="sppb-section-title sppb-text-{text_align(settings.get("title_position")) or "left"}">'
                f'<{tag} class="sppb-title-heading">{html.escape(str(settings["title"]))}</{tag}>'
                "</div>"
            )
            declarations = []
            if settings.get("title_fontsize"):
                declarations.append(f"font-size: {norm_len(settings['title_fontsize'])}")
            if settings.get("title_fontweight"):
                declarations.append(f"font-weight: {settings['title_fontweight']}")
            self.css.add(f"#{section_id} .sppb-title-heading", declarations)

        row_classes = ["sppb-row"]
        if truthy(settings.get("columns_align_center")):
            row_classes.append("sppb-row--align-center")

        columns = [self.render_column(column) for column in row.get("columns") or [] if truthy(column.get("visibility", True))]
        inner = (
            f'<div class="sppb-row-container">'
            f'<div class="{" ".join(row_classes)}">{"".join(columns)}</div>'
            f"</div>"
        )
        return f'<section id="{section_id}" class="{" ".join(classes)}">\n{title_html}\n{inner}\n</section>'

    def render_nested_row(self, row: dict) -> str:
        self.stats["sections"] += 1
        settings = row.get("settings") or {}
        section_id = slug(row.get("id"), "section", self.used_ids)
        classes = ["sppb-section", "sppb-section--nested"]
        if truthy(settings.get("fullscreen")):
            classes.append("sppb-section-fullwidth")
        if truthy(settings.get("no_gutter")):
            classes.append("sppb-no-gutter")
        classes.extend(self._hidden_classes(settings))
        self._box_css(f"#{section_id}", settings, "section")

        gutter = as_responsive(settings.get("columns_gap"))
        if gutter:
            for bp, value in gutter.items():
                self.css.add(f"#{section_id} .sppb-row", [f"--sppb-gutter: {norm_len(value)}"], None if bp == "xl" else bp)

        row_classes = ["sppb-row"]
        if truthy(settings.get("columns_align_center")):
            row_classes.append("sppb-row--align-center")
        columns = [self.render_column(column) for column in row.get("columns") or [] if truthy(column.get("visibility", True))]
        return f'<div id="{section_id}" class="{" ".join(classes)}"><div class="{" ".join(row_classes)}">{"".join(columns)}</div></div>'

    def render_column(self, column: dict) -> str:
        self.stats["columns"] += 1
        settings = column.get("settings") or {}
        column_id = slug(column.get("id"), "column", self.used_ids)
        classes = ["sppb-column"]
        classes.extend(self._width_classes(settings.get("width"), column_id))
        if truthy(settings.get("items_align_center")):
            classes.append("sppb-column--vcenter")
        if column.get("class_name"):
            classes.append(str(column["class_name"]))
        if settings.get("class"):
            classes.append(str(settings["class"]))
        classes.extend(self._hidden_classes(settings))

        self._box_css(f"#{column_id}", settings, "column")
        addon_classes = ["sppb-addon-wrapper"]
        addons = "".join(
            self.render_addon(addon) for addon in column.get("addons") or [] if truthy(addon.get("visibility", True))
        )
        return f'<div id="{column_id}" class="{" ".join(classes)}"><div class="{" ".join(addon_classes)}">{addons}</div></div>'

    def _width_classes(self, width: Any, column_id: str) -> list[str]:
        data = as_responsive(width)
        percents: dict[str, float | None] = {bp: to_percent(data.get(bp)) for bp in BPS}
        # empty device values inherit the desktop value (SPPB behaviour)
        last = percents.get("xl") or 100.0
        for bp in ("lg", "md", "sm", "xs"):
            if percents.get(bp) is None:
                percents[bp] = last
            else:
                last = percents[bp]

        classes: list[str] = []
        custom: dict[str, float] = {}
        for bp in BPS:
            percent = percents[bp] or 100.0
            span = round(percent / 100 * 12)
            if span < 1:
                span = 12
            if abs(percent - span / 12 * 100) < 0.05:
                classes.append(f"sppb-col-{span}" if bp == "xs" else f"sppb-col-{bp}-{span}")
            else:
                custom[bp] = percent
        if custom:
            # no bootstrap-equivalent class: keep the exact percentage on this column
            for bp, percent in custom.items():
                self.css.add(
                    f"#{column_id}",
                    [f"flex: 0 0 {percent:.4f}%", f"max-width: {percent:.4f}%"],
                    MIN_WIDTH[bp],
                )
        return classes

    # ----------------------------------------------------------------- addons

    def render_addon(self, addon: dict) -> str:
        name = str(addon.get("name") or addon.get("type") or "unknown")
        self.stats["addons"] += 1
        settings = addon.get("settings") or {}
        addon_id = slug(addon.get("id"), "sppb-addon", self.used_ids)
        selector = f"#{addon_id}"
        classes = ["sppb-addon", f"sppb-addon-{name}"]
        if settings.get("class"):
            classes.append(str(settings["class"]))
        if name == "text_block" and truthy(settings.get("dropcap")):
            classes.append("sppb-dropcap")
        classes.extend(self._hidden_classes(settings))

        self._box_css(selector, settings, "addon")

        builder = getattr(self, f"addon_{name}", None)
        if builder is None:
            self.warnings.append(f"unsupported addon: {name}")
            inner = f'<div class="sppb-placeholder">Addon «{html.escape(name)}» не поддержан конвертером</div>'
        else:
            inner = builder(addon, selector, settings)

        anim = ""
        if truthy(settings.get("global_use_animation")):
            anim = ' data-sppb-animate="1"'
        return f'<div id="{addon_id}" class="{" ".join(classes)}"{anim}>{inner}</div>'

    # -- heading -------------------------------------------------------------

    def addon_heading(self, addon: dict, selector: str, settings: dict) -> str:
        tag = heading_tag(settings.get("heading_selector"))
        title = html.escape(str(settings.get("title") or ""))
        icon = settings.get("title_icon")
        if isinstance(icon, dict):
            icon = icon.get("src") or icon.get("value")
        if icon:
            icon_html = str(icon) if str(icon).lstrip().startswith("<") else f'<i class="{html.escape(str(icon))}"></i>'
            title = f"{icon_html} {title}" if settings.get("title_icon_position") != "after" else f"{title} {icon_html}"
        attrs, _ = self._link_attrs(settings.get("title_link"))
        if attrs:
            title = f"<a{attrs}>{title}</a>"

        declarations = typography_decls(settings.get("title_typography") or settings.get("heading_typography"))
        if settings.get("title_text_color"):
            declarations.append((None, f"color: {settings['title_text_color']}"))
        alignment = settings.get("alignment")
        for bp, value in as_responsive(alignment).items():
            direction = text_align(value)
            if direction:
                declarations.append((None if bp == "xl" else bp, f"text-align: {direction}"))
        self.css.add(f"{selector} .sppb-addon-title", declarations)
        self.css.add_responsive(f"{selector} .sppb-addon-title", responsive_decls("margin", settings.get("title_margin")))
        self.css.add_responsive(f"{selector} .sppb-addon-title", responsive_decls("padding", settings.get("title_padding")))

        shadow = settings.get("title_text_shadow")
        if isinstance(shadow, dict):
            if truthy(shadow.get("enabled")):
                value = box_shadow({"enabled": True, **shadow})
                if value:
                    self.css.add(f"{selector} .sppb-addon-title", [f"text-shadow: {value}"])
        elif isinstance(shadow, str) and shadow.strip():
            if not re.fullmatch(r"0(px)? 0(px)? 0(px)? (#\w+)?", shadow.strip()):
                self.css.add(f"{selector} .sppb-addon-title", [f"text-shadow: {shadow}"])

        return f'<{tag} class="sppb-addon-title">{title}</{tag}>'

    # -- text block ----------------------------------------------------------

    def addon_text_block(self, addon: dict, selector: str, settings: dict) -> str:
        inner: list[str] = []
        if settings.get("title"):
            tag = heading_tag(settings.get("heading_selector"))
            inner.append(f'<{tag} class="sppb-addon-title">{html.escape(str(settings["title"]))}</{tag}>')
            self.css.add(f"{selector} .sppb-addon-title", typography_decls(settings.get("title_typography")))
        content = self._process_html(settings.get("text"))
        inner.append(f'<div class="sppb-addon-content">{content}</div>')
        self.css.add(f"{selector} .sppb-addon-content", typography_decls(settings.get("text_typography")))
        if settings.get("global_text_color"):
            self.css.add(f"{selector} .sppb-addon-content", [f"color: {settings['global_text_color']}"])
        if settings.get("title_text_color"):
            self.css.add(f"{selector} .sppb-addon-title", [f"color: {settings['title_text_color']}"])
        if truthy(settings.get("dropcap")):
            self.css.add(
                f"{selector}.sppb-dropcap .sppb-addon-content > p:first-of-type::first-letter",
                ["float: left", "font-size: 3.2em", "line-height: .9", "padding: 0 .12em 0 0", "font-weight: 700"],
            )
        return "".join(inner)

    # -- image ---------------------------------------------------------------

    def addon_image(self, addon: dict, selector: str, settings: dict) -> str:
        image = settings.get("image") or {}
        if not isinstance(image, dict):
            image = {}
        src = image.get("src") or ""
        alt = settings.get("alt_text") or image.get("alt") or ""
        if not src:
            return ""
        declarations: list[str] = []
        width = as_responsive(settings.get("image_width"))
        if width.get("xl") not in (None, ""):
            declarations.append(f"width: {norm_len(width['xl'])}")
        height = as_responsive(settings.get("image_height"))
        if height.get("xl") not in (None, ""):
            declarations.append(f"height: {norm_len(height['xl'])}")
        if settings.get("image_fit") in ("cover", "contain", "fill", "none", "scale-down"):
            declarations.append(f"object-fit: {settings['image_fit']}")
        radius = settings.get("border_radius")
        if radius not in (None, "", 0, "0"):
            declarations.append(f"border-radius: {norm_len(radius)}")
        img_style = f' style="{"; ".join(declarations)}"' if declarations else ""

        attrs = (
            f' src="{html.escape(self.asset_url(src), quote=True)}"'
            f' alt="{html.escape(str(alt), quote=True)}"'
            ' loading="lazy" decoding="async"'
        )
        attrs += img_style
        img = f"<img{attrs}>"

        link_attrs, link_url = self._link_attrs(settings.get("link"))
        if link_url and not truthy(settings.get("open_lightbox")):
            img = f'<a class="sppb-image-link"{link_attrs}>{img}</a>'
        elif truthy(settings.get("open_lightbox")):
            full = self.asset_url(settings.get("lightbox_image") or src)
            img = f'<a class="sppb-image-link sppb-lightbox" href="{html.escape(full, quote=True)}">{img}</a>'

        position = as_responsive(settings.get("position"))
        for bp, value in position.items():
            direction = text_align(value)
            if direction:
                self.css.add(selector, [f"text-align: {direction}"], None if bp == "xl" else bp)

        title = settings.get("image_title") or settings.get("title") or ""
        title_html = f'<div class="sppb-image-title">{html.escape(str(title))}</div>' if title else ""
        body = title_html + img if str(settings.get("title_position") or "top") != "bottom" else img + title_html
        return f'<figure class="sppb-image-figure">{body}</figure>'

    # -- nested row ----------------------------------------------------------

    def addon_row(self, addon: dict, selector: str, settings: dict) -> str:
        row = self.rows.get(addon.get("id"))
        if not row:
            self.warnings.append(f"nested row {addon.get('id')} not found")
            return ""
        if row.get("id") in self._render_stack:
            self.warnings.append(f"cycle detected at row {row.get('id')}")
            return ""
        self._render_stack.add(row["id"])
        try:
            return self.render_nested_row(row)
        finally:
            self._render_stack.discard(row["id"])

    # -- tabs ----------------------------------------------------------------

    def _render_row_refs(self, refs: list[dict]) -> str:
        parts = []
        for ref in refs or []:
            row = self.rows.get(ref.get("id"))
            if not row:
                self.warnings.append(f"row reference {ref.get('id')} not found")
                continue
            if row["id"] in self._render_stack:
                self.warnings.append(f"cycle detected at row {row['id']}")
                continue
            self._render_stack.add(row["id"])
            try:
                parts.append(self.render_nested_row(row))
            finally:
                self._render_stack.discard(row["id"])
        return "".join(parts)

    def addon_tab(self, addon: dict, selector: str, settings: dict) -> str:
        items = settings.get("sp_tab_item") or []
        self._tab_counter += 1
        base = f"sppb-tab{self._tab_counter}"
        nav = []
        panes = []
        for index, item in enumerate(items):
            pane_id = f"{base}-{index + 1}"
            active = index == 0
            title = html.escape(str(item.get("title") or f"Tab {index + 1}"))
            nav.append(
                f'<li role="presentation"><a role="tab" href="#{pane_id}" data-sppb-tab aria-controls="{pane_id}" '
                f'aria-selected="{"true" if active else "false"}" tabindex="{0 if active else -1}" '
                f'class="{"is-active" if active else ""}">{title}</a></li>'
            )
            content = self._render_row_refs(item.get("content") or [])
            panes.append(
                f'<div class="sppb-tab-pane{" is-active" if active else ""}" id="{pane_id}" role="tabpanel"'
                f'{" hidden" if not active else ""}>{content}</div>'
            )

        justified = truthy(as_responsive(settings.get("nav_justified")).get("xl"))
        classes = 'sppb-tabs' + (' sppb-tabs--justified' if justified else '')
        content_bg = settings.get("content_backround")
        if content_bg:
            self.css.add(f"{selector} .sppb-tabs-content", [f"background-color: {content_bg}"])
        self.css.add_responsive(f"{selector} .sppb-tabs-content", responsive_decls("padding", settings.get("content_padding")))
        self.css.add_responsive(f"{selector} .sppb-tabs-content", responsive_decls("margin", settings.get("content_margin")))
        if str(settings.get("content_border") or "0") not in ("0", ""):
            self.css.add(f"{selector} .sppb-tabs-content", [f"border: {settings['content_border']}"])
        if truthy(settings.get("show_boxshadow")):
            shadow_color = settings.get("shadow_color") or "rgba(0,0,0,.15)"
            self.css.add(f"{selector} .sppb-tabs-content", [f"box-shadow: 0 0 12px {shadow_color}"])

        nav_decls = [
            f"background-color: {settings['nav_bg_color']}" if settings.get("nav_bg_color") else "",
            f"color: {settings['nav_color']}" if settings.get("nav_color") else "",
        ]
        if settings.get("nav_border") and settings.get("nav_border") != "0":
            nav_decls.append(f"border-width: {settings['nav_border']}")
            nav_decls.append("border-style: solid")
        if settings.get("nav_border_color"):
            nav_decls.append(f"border-color: {settings['nav_border_color']}")
        self.css.add(f"{selector} .sppb-tabs-nav a", [d for d in nav_decls if d])
        self.css.add_responsive(f"{selector} .sppb-tabs-nav a", responsive_decls("padding", settings.get("nav_padding")))
        radius = settings.get("nav_border_radius")
        if radius:
            self.css.add(f"{selector} .sppb-tabs-nav a", [f"border-radius: {norm_len(as_responsive(radius).get('xl', radius))}"])
        self.css.add(f"{selector} .sppb-tabs-nav a", typography_decls(settings.get("nav_typography")))
        self.css.add(f"{selector} .sppb-tabs-nav a.is-active", [
            f"background-color: {settings['active_tab_bg']}" if settings.get("active_tab_bg") else "",
            f"color: {settings['active_tab_color']}" if settings.get("active_tab_color") else "",
        ])
        self.css.add(f"{selector} .sppb-tabs-nav a:hover", [
            f"background-color: {settings['hover_tab_bg']}" if settings.get("hover_tab_bg") else "",
            f"color: {settings['hover_tab_color']}" if settings.get("hover_tab_color") else "",
        ])
        self.css.add(f"{selector} .sppb-tabs-content", typography_decls(settings.get("content_typography")))
        if not settings.get("content_padding"):
            self.css.add(f"{selector} .sppb-tabs-content", ["padding: 1rem"])

        return f'<div class="{classes}" data-sppb-tabs><ul class="sppb-tabs-nav" role="tablist">{"".join(nav)}</ul><div class="sppb-tabs-content">{"".join(panes)}</div></div>'

    # -- accordion -----------------------------------------------------------

    def addon_accordion(self, addon: dict, selector: str, settings: dict) -> str:
        items = settings.get("sp_accordion_item") or []
        open_mode = str(settings.get("openitem") or "hide")
        items_html = []
        for index, item in enumerate(items):
            is_open = index == 0 and open_mode in ("show", "first", "1", "open")
            title = html.escape(str(item.get("title") or f"Item {index + 1}"))
            content = self._render_row_refs(item.get("content") or [])
            item_id = "acc-" + re.sub(r"[^A-Za-z0-9]", "", str(addon.get("id") or ""))[:8] + f"-{index + 1}"
            while item_id in self.used_ids:
                item_id += "x"
            self.used_ids.add(item_id)
            items_html.append(
                f'<div class="sppb-accordion-item{" is-open" if is_open else ""}">'
                f'<h3 class="sppb-accordion-title"><button type="button" class="sppb-accordion-toggle" '
                f'aria-expanded="{"true" if is_open else "false"}" aria-controls="{item_id}">{title}</button></h3>'
                f'<div class="sppb-accordion-content" id="{item_id}"{" hidden" if not is_open else ""}>{content}</div>'
                "</div>"
            )

        if settings.get("item_bg"):
            self.css.add(f"{selector} .sppb-accordion-item", [f"background-color: {settings['item_bg']}"])
        if settings.get("item_border_width") not in (None, "", "0", 0, "0px"):
            self.css.add(f"{selector} .sppb-accordion-item", ["border-style: solid", f"border-width: {norm_len(settings['item_border_width'])}"])
            color = settings.get("item_border_color") or "rgba(0,0,0,.15)"
            self.css.add(f"{selector} .sppb-accordion-item", [f"border-color: {color}"])
        radius = settings.get("item_border_radius")
        if radius:
            self.css.add(f"{selector} .sppb-accordion-item", [f"border-radius: {norm_len(as_responsive(radius).get('xl', radius))}"])
        spacing = settings.get("item_spacing")
        if spacing:
            self.css.add(f"{selector} .sppb-accordion-item", [f"margin-bottom: {norm_len(as_responsive(spacing).get('xl', spacing))}"])
        self.css.add(f"{selector} .sppb-accordion-toggle", typography_decls(settings.get("item_title_typography")))
        self.css.add_responsive(f"{selector} .sppb-accordion-toggle", responsive_decls("padding", settings.get("item_title_padding")))
        self.css.add_responsive(f"{selector} .sppb-accordion-content", responsive_decls("padding", settings.get("item_content_padding")))
        if settings.get("title_text_color"):
            self.css.add(f"{selector} .sppb-accordion-toggle", [f"color: {settings['title_text_color']}"])
        if settings.get("item_title_bg_color"):
            self.css.add(f"{selector} .sppb-accordion-title", [f"background-color: {settings['item_title_bg_color']}"])
        return f'<div class="sppb-accordion" data-sppb-accordion>{"".join(items_html)}</div>'

    # -- advanced table ------------------------------------------------------

    def addon_table_advanced(self, addon: dict, selector: str, settings: dict) -> str:
        self.stats["tables"] += 1
        head_cells: list[str] = []
        if not truthy(settings.get("turn_off_heading")):
            for item in settings.get("sp_table_advanced_item") or []:
                head_cells.append("".join(self.render_addon(sub) for sub in item.get("content") or [] if truthy(sub.get("visibility", True))))

        body_rows: list[str] = []
        for index, row in enumerate(settings.get("table_advanced_item") or []):
            cells = []
            for cell in row.get("table_advanced_item") or []:
                content = "".join(
                    self.render_addon(sub) for sub in cell.get("content") or [] if truthy(sub.get("visibility", True))
                )
                cells.append(f"<td>{content}</td>")
            body_rows.append(f"<tr>{''.join(cells)}</tr>")

        head = ""
        if head_cells:
            head = "<thead><tr>" + "".join(
                '<th scope="col">' + cell + "</th>" for cell in head_cells
            ) + "</tr></thead>"
        body = f'<tbody>{"".join(body_rows)}</tbody>' if body_rows else ""

        if settings.get("header_color"):
            self.css.add(f"{selector} .sppb-table thead th", [f"color: {settings['header_color']}"])
        if settings.get("header_bg_options") == "gradient_bg":
            gradient = settings.get("header_gradient_bg") or {}
            if gradient.get("color"):
                self.css.add(f"{selector} .sppb-table thead th", [
                    f"background-image: linear-gradient({gradient.get('deg', 0)}deg, {gradient['color']}, {gradient.get('color2', gradient['color'])})"
                ])
        elif settings.get("header_bg_color"):
            self.css.add(f"{selector} .sppb-table thead th", [f"background-color: {settings['header_bg_color']}"])
        if settings.get("tr_bg_color"):
            self.css.add(f"{selector} .sppb-table tbody tr", [f"background-color: {settings['tr_bg_color']}"])
        if settings.get("td_second_bg_color"):
            self.css.add(f"{selector} .sppb-table tbody tr:nth-child(even)", [f"background-color: {settings['td_second_bg_color']}"])
        alignment = text_align(settings.get("table_text_alignment"))
        if alignment:
            self.css.add(f"{selector} .sppb-table th, {selector} .sppb-table td", [f"text-align: {alignment}"])
        self.css.add_responsive(f"{selector} .sppb-table th", responsive_decls("padding", settings.get("header_padding")))
        self.css.add_responsive(f"{selector} .sppb-table td", responsive_decls("padding", settings.get("td_padding")))
        if settings.get("header_border"):
            self.css.add(f"{selector} .sppb-table thead th", [f"border: {settings['header_border']}"])
        if settings.get("td_border"):
            self.css.add(f"{selector} .sppb-table td", [f"border: {settings['td_border']}"])
        if settings.get("global_text_color"):
            self.css.add(f"{selector} .sppb-table", [f"color: {settings['global_text_color']}"])

        return (
            f'<div class="sppb-addon-table-main"><div class="sppb-table-wrap">'
            f'<table class="sppb-table">{head}{body}</table></div></div>'
        )

    # -- simple addons -------------------------------------------------------

    def addon_raw_html(self, addon: dict, selector: str, settings: dict) -> str:
        value = settings.get("html") or settings.get("text") or ""
        return f'<div class="sppb-addon-content">{self._process_html(value)}</div>'

    def addon_empty_space(self, addon: dict, selector: str, settings: dict) -> str:
        gap = as_responsive(settings.get("gap")).get("xl", 40)
        return f'<div class="sppb-empty-space" style="height:{norm_len(gap)}"></div>'

    def addon_divider(self, addon: dict, selector: str, settings: dict) -> str:
        declarations = []
        for key, prop in (("divider_color", "border-top-color"), ("divider_height", "border-top-width"), ("divider_width", "width"), ("divider_margin", "margin")):
            if settings.get(key):
                declarations.append(f"{prop}: {norm_len(settings[key])}")
        style = f' style="{"; ".join(declarations)}"' if declarations else ""
        return f'<hr class="sppb-divider"{style}>'

    def addon_button(self, addon: dict, selector: str, settings: dict) -> str:
        text = html.escape(str(settings.get("text") or "Button"))
        attrs, _ = self._link_attrs(settings.get("link") or {"type": settings.get("type"), "url": settings.get("url")})
        declarations = []
        for key, prop in (("btn_color", "color"), ("background_color", "background-color"), ("border_radius", "border-radius"), ("padding", "padding")):
            if settings.get(key):
                declarations.append(f"{prop}: {norm_len(settings[key])}")
        style = f' style="{"; ".join(declarations)}"' if declarations else ""
        return f'<a class="sppb-button"{attrs}{style}>{text}</a>'

    def addon_feature(self, addon: dict, selector: str, settings: dict) -> str:
        parts = []
        if settings.get("feature_type") == "image" and (settings.get("feature_image") or {}).get("src"):
            src = settings["feature_image"]["src"]
            parts.append(f'<img class="sppb-feature-image" src="{html.escape(self.asset_url(src), quote=True)}" alt="">')
        elif settings.get("icon_name"):
            declarations = []
            if settings.get("icon_color"):
                declarations.append(f"color: {settings['icon_color']}")
            size = as_responsive(settings.get("icon_size")).get("xl")
            if size:
                declarations.append(f"font-size: {norm_len(size)}")
            style = f' style="{"; ".join(declarations)}"' if declarations else ""
            parts.append(f'<i class="sppb-feature-icon {html.escape(str(settings["icon_name"]))}"{style}></i>')
        if settings.get("title"):
            tag = heading_tag(settings.get("heading_selector"))
            parts.append(f'<{tag} class="sppb-feature-title">{html.escape(str(settings["title"]))}</{tag}>')
        if settings.get("text"):
            parts.append(f'<div class="sppb-feature-text">{self._process_html(settings["text"])}</div>')
        return f'<div class="sppb-feature">{"".join(parts)}</div>'

    def addon_navigation(self, addon: dict, selector: str, settings: dict) -> str:
        items = settings.get("sp_link_list_item") or []
        links = []
        for item in items:
            title = html.escape(str(item.get("title") or ""))
            url = item.get("url")
            if url:
                links.append(f'<li><a href="{html.escape(self.link_url(url), quote=True)}">{title}</a></li>')
            else:
                links.append(f'<li><span>{title}</span></li>')
        return f'<ul class="sppb-nav-links">{"".join(links)}</ul>'

    def addon_module(self, addon: dict, selector: str, settings: dict) -> str:
        position = settings.get("position") or "module"
        return f'<div class="sppb-placeholder">Joomla-модуль: {html.escape(str(position))}</div>'

    def addon_articles(self, addon: dict, selector: str, settings: dict) -> str:
        return '<div class="sppb-placeholder">Динамический список статей Joomla (нужны данные из jos_content)</div>'

    def addon_gallery(self, addon: dict, selector: str, settings: dict) -> str:
        return '<div class="sppb-placeholder">Галерея Joomla (нужны изображения)</div>'


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #


def render_page(page: Page, *, asset_base: str, link_base: str) -> tuple[str, Renderer]:
    renderer = Renderer(page, asset_base=asset_base, link_base=link_base)
    return renderer.render(), renderer


def make_index(pages: list[tuple[str, str]], title: str = "Прототипы страниц") -> str:
    links = "\n".join(f'<li><a href="{html.escape(href, quote=True)}">{html.escape(name)}</a></li>' for href, name in pages)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;margin:0;padding:3rem 1.25rem;background:#f6f4ee;color:#212529}}
main{{max-width:760px;margin:0 auto;background:#fff;padding:2.5rem;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.07)}}
h1{{margin-top:0;font-size:1.75rem}}
ul{{padding-left:1.25rem;line-height:1.9}}
code{{background:#f1f3f5;padding:.1em .3em;border-radius:4px}}
p{{color:#495057}}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p>Статические HTML-прототипы, собранные из экспорта SP Page Builder.</p>
<ul>
{links}
</ul>
<p>Исходники: <code>data/*.sppb.json</code>. Генератор: <code>tools/sppb2html.py</code>.</p>
</main>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def slugify_title(title: str) -> str:
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
        "я": "ya",
    }
    transliterated = "".join(table.get(char, char) for char in title.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    return slug or "page"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert SP Page Builder JSON to standalone HTML.")
    parser.add_argument("inputs", nargs="+", help="JSON files / zip archives with SPPB pages")
    parser.add_argument("-o", "--out", required=True, help="output HTML file or directory")
    parser.add_argument("--asset-base", default=DEFAULT_SITE, help="base URL for images (default: %(default)s)")
    parser.add_argument("--link-base", default=DEFAULT_SITE, help="base URL for links (default: %(default)s)")
    parser.add_argument("--all", action="store_true", help="render all pages from a database dump")
    parser.add_argument("--only", help="render only pages whose title contains this text")
    parser.add_argument("--limit", type=int, help="limit the number of pages")
    parser.add_argument("--index", action="store_true", help="write an index.html into the output directory")
    args = parser.parse_args(argv)

    pages: list[Page] = []
    for item in args.inputs:
        try:
            pages.extend(load_pages(item))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.only:
        needle = args.only.lower()
        pages = [page for page in pages if needle in page.title.lower()]
    if args.limit:
        pages = pages[: args.limit]
    if not pages:
        print("error: no pages to render", file=sys.stderr)
        return 2

    out = Path(args.out)
    single = len(pages) == 1 and not args.all and out.suffix.lower() in (".html", ".htm")
    if single:
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        out.mkdir(parents=True, exist_ok=True)

    index_entries: list[tuple[str, str]] = []
    used_slugs: set[str] = set()
    failures = 0
    for page in pages:
        markup, renderer = render_page(page, asset_base=args.asset_base, link_base=args.link_base)
        if single:
            target = out
        else:
            base = slugify_title(page.title)
            candidate = base
            counter = 2
            while candidate in used_slugs:
                candidate = f"{base}-{counter}"
                counter += 1
            used_slugs.add(candidate)
            target = out / f"{candidate}.html"
            index_entries.append((target.name, page.title))
        target.write_text(markup, encoding="utf-8")
        status = "ok"
        if renderer.warnings:
            status = "warnings: " + "; ".join(sorted(set(renderer.warnings)))
            failures += 1
        print(
            f"{target}: {renderer.stats['sections']} sections, "
            f"{renderer.stats['columns']} columns, {renderer.stats['addons']} addons, "
            f"{renderer.stats['tables']} tables — {status}"
        )

    if args.index and not single:
        (out / "index.html").write_text(make_index(index_entries), encoding="utf-8")
        print(f"{out / 'index.html'}: index")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
