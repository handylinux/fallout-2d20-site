#!/usr/bin/env python3
"""Strict Publisher-artwork resolution for the full Russian weapon catalogue.

The normal manifest selector in :mod:`weapon2pdf` also supports an explicit
page override for one-off card work.  A multi-page catalogue must be stricter:
it may only replay a layer when the manifest itself identifies the same weapon
ID.  It must never use the final catalogue page number as an accidental
fallback, because that page number changes when the printed TOC is inserted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import weapon2pdf as w


class CatalogArtworkError(w.ArtworkManifestError):
    """The catalogue cannot safely use its requested Publisher artwork."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtworkResolver:
    """Cache and audit exact manifest layers keyed by ``weapon_id``.

    A resolver is intentionally optional so the structural PDF tests can run
    from source data alone.  The published Russian catalogue supplies one,
    which makes all usable source artwork mandatory and records every omission
    that is inherent to the Publisher export (for example a page with only
    vector art and therefore no exported PNG placement).
    """

    def __init__(self, manifest_path: str | Path | None = None,
                 asset_root: str | Path | None = None,
                 source_pdf: str | Path | None = None):
        self.manifest_path = (Path(manifest_path).resolve()
                              if manifest_path is not None else None)
        self.asset_root = (Path(asset_root).resolve()
                           if asset_root is not None else None)
        self.manifest: dict[str, Any] | None = None
        self._pages_by_weapon: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, w.ArtworkLayer | None] = {}
        self._records: dict[str, dict[str, Any]] = {}

        if self.manifest_path is None:
            return
        self.manifest = w.load_artwork_manifest(str(self.manifest_path))
        if source_pdf is not None:
            self._validate_source(Path(source_pdf))
        for page in self.manifest["pages"]:
            if not isinstance(page, dict):
                continue
            weapon_id = page.get("weapon_id")
            if not isinstance(weapon_id, str) or not weapon_id:
                continue
            if weapon_id in self._pages_by_weapon:
                first = self._pages_by_weapon[weapon_id].get("number")
                raise CatalogArtworkError(
                    f"artwork manifest сопоставляет {weapon_id!r} нескольким страницам "
                    f"({first} и {page.get('number')})")
            self._pages_by_weapon[weapon_id] = page

    @property
    def enabled(self) -> bool:
        return self.manifest is not None

    def _validate_source(self, source_pdf: Path) -> None:
        if not source_pdf.is_file():
            raise CatalogArtworkError(f"не найден исходный PDF для artwork: {source_pdf}")
        assert self.manifest is not None
        source = self.manifest.get("source") or {}
        expected = source.get("sha256") if isinstance(source, dict) else None
        if not expected:
            raise CatalogArtworkError("artwork manifest не содержит SHA-256 исходного PDF")
        actual = _sha256(source_pdf)
        if actual != expected:
            raise CatalogArtworkError(
                "artwork manifest относится к другому исходному PDF: "
                f"ожидался SHA-256 {expected}, получен {actual}")

    def layer_for(self, weapon_id: str) -> w.ArtworkLayer | None:
        """Return the exact source layer for one weapon, or an audited absence.

        There is deliberately no ``card.page`` fallback here.  An unmatched ID
        remains blank rather than borrowing artwork from a different weapon.
        """
        if not self.enabled:
            return None
        if weapon_id in self._cache:
            return self._cache[weapon_id]
        page = self._pages_by_weapon.get(weapon_id)
        if page is None:
            self._records[weapon_id] = {"status": "no-manifest-page"}
            self._cache[weapon_id] = None
            return None
        placements = w.artwork_placements(page)
        if not placements:
            self._records[weapon_id] = {
                "status": "manifest-page-without-exported-artwork",
                "source_page": page.get("number"),
            }
            self._cache[weapon_id] = None
            return None

        layer = w.ArtworkLayer(
            manifest_path=str(self.manifest_path),
            asset_root=str(self.asset_root or self.manifest_path.parent),
            page=page,
        )
        # Resolve every asset before any page is emitted.  A stale extraction
        # fails loudly instead of producing a partially illustrated book.
        for placement in placements:
            w._manifest_asset_path(layer, placement)
        self._records[weapon_id] = {
            "status": "replayed",
            "source_page": page.get("number"),
            "placements": [
                {"xref": item.get("xref"), "asset": item.get("asset"),
                 "draw_order": item.get("draw_order")}
                for item in placements
            ],
        }
        self._cache[weapon_id] = layer
        return layer

    def assert_all_available_layers_requested(self) -> None:
        """Ensure every usable identified Publisher layer reached a card.

        This catches a missed argument while threading the resolver through a
        new section builder.  It says nothing about source pages that lack an
        exported artwork placement: those are explicitly reported instead.
        """
        if not self.enabled:
            return
        available = {
            weapon_id for weapon_id, page in self._pages_by_weapon.items()
            if w.artwork_placements(page)
        }
        replayed = {
            weapon_id for weapon_id, record in self._records.items()
            if record["status"] == "replayed"
        }
        missing = sorted(available - replayed)
        if missing:
            raise CatalogArtworkError(
                "не все доступные artwork layers были переданы в каталог: "
                + ", ".join(missing))

    def coverage(self) -> dict[str, Any]:
        """Return a portable, reviewable record suitable for JSON output."""
        if not self.enabled:
            return {"schema": "fallout-2d20.weapon-catalog-artwork-coverage/v1",
                    "enabled": False, "weapons": {}}
        assert self.manifest is not None and self.manifest_path is not None
        source = self.manifest.get("source") or {}
        counts: dict[str, int] = {}
        for record in self._records.values():
            status = str(record["status"])
            counts[status] = counts.get(status, 0) + 1
        return {
            "schema": "fallout-2d20.weapon-catalog-artwork-coverage/v1",
            "enabled": True,
            "manifest": {
                "file": self.manifest_path.name,
                "sha256": _sha256(self.manifest_path),
                "source": source,
            },
            "counts": dict(sorted(counts.items())),
            "weapons": dict(sorted(self._records.items())),
            "policy": (
                "Artwork is replayed only for an exact manifest weapon_id match; "
                "there is no final-page fallback or substitute illustration."
            ),
        }

    def write_coverage(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.coverage(), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
