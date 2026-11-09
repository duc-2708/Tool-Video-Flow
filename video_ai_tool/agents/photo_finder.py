"""Photo Finder Agent for Authentic, Grounded, and Licensed Visual Media.

Connects to Wikidata & Wikimedia Commons (free HTTP API only) to discover and verify
real-world entities (people, landmarks, infrastructure, machinery) with verified open licenses
(CC0, CC BY, CC BY-SA, Public Domain).
Enforces local computer-vision safety gates (YuNet face detection, MSER/Sobel text density).
Never forces images when no grounded photo is found.
"""
from __future__ import annotations

import html
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests
from PIL import Image

from pipeline.slide_image_resolver import (
    detect_faces,
    detect_text_slide_document,
    is_document_or_schematic_image,
)

logger = logging.getLogger(__name__)

USER_AGENT = "VideoAITool/1.0"
DEFAULT_TIMEOUT = 8.0
MAX_PHOTOS_PER_VIDEO = 3

# Rate limiter: max 3 requests / second
_request_timestamps: list[float] = []


def _throttle_request() -> None:
    """Enforce maximum 3 requests per second to comply with Wikimedia Commons guidelines."""
    global _request_timestamps
    now = time.time()
    _request_timestamps = [t for t in _request_timestamps if now - t < 1.0]
    if len(_request_timestamps) >= 3:
        sleep_dur = 1.0 - (now - _request_timestamps[0]) + 0.05
        if sleep_dur > 0:
            time.sleep(sleep_dur)
    _request_timestamps.append(time.time())


ALLOWED_LICENSE_KEYWORDS = {
    "cc0", "public domain", "pd", "pd-old", "pd-self",
    "cc by", "cc-by", "cc by-sa", "cc-by-sa",
}
FORBIDDEN_LICENSE_SUBSTRINGS = [
    "nc", "non-commercial", "noncommercial",
    "nd", "no-derivatives", "noderivs",
    "copyrighted", "fair use", "all rights reserved"
]


def is_license_allowed(license_str: str) -> bool:
    """Check if the license is strictly CC0, CC BY, CC BY-SA, or Public Domain."""
    if not license_str or not isinstance(license_str, str):
        return False
    low = license_str.lower().strip()
    if any(forb in low for forb in FORBIDDEN_LICENSE_SUBSTRINGS):
        return False
    if "public domain" in low or low in ("pd", "pd-old", "pd-self", "cc0"):
        return True
    if "cc by" in low or "cc-by" in low:
        return True
    return False


def clean_artist_name(
    raw_artist: str,
    meta: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
) -> str:
    """Extract and sanitize author name from extmetadata and imageinfo.

    Strips HTML tags, unescapes entities, removes URLs.
    If Artist is empty -> checks Credit, AttributionRequired, or uploader username.
    If still empty or generic placeholder -> returns "" (fail-closed, no author).
    """
    candidates: list[str] = []
    if raw_artist:
        candidates.append(raw_artist)
    if meta and isinstance(meta, dict):
        credit = meta.get("Credit", {}).get("value", "")
        if credit:
            candidates.append(credit)
        attr_req = meta.get("AttributionRequired", {}).get("value", "")
        if attr_req:
            candidates.append(attr_req)
    if info and isinstance(info, dict):
        uploader = info.get("user", "")
        if uploader:
            candidates.append(uploader)

    for cand in candidates:
        if not cand or not isinstance(cand, str):
            continue
        # Unescape HTML entities (e.g. &amp;, &#39;)
        text = html.unescape(cand)
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", "", text).strip()
        # Strip URLs
        text = re.sub(r"https?://\S+", "", text).strip()
        # Remove User: or user: prefix
        text = re.sub(r"^User:\s*", "", text, flags=re.I).strip()
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Reject generic or placeholder strings
        cand_low = text.lower()
        if not text or len(text) < 2:
            continue
        if any(g in cand_low for g in ("unknown", "anonymous", "không rõ", "chưa rõ", "n/a", "wikimedia commons")):
            continue
        return text

    return ""


def search_wikidata_person(person_name: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    """Search Wikidata for a person by name, verifying P31 == Q5 (human). Returns entity ID."""
    if not person_name:
        return None

    _throttle_request()
    headers = {"User-Agent": USER_AGENT}

    # 1. Search entity
    for lang in ("vi", "en"):
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": person_name,
            "language": lang,
            "format": "json",
            "type": "item",
            "limit": 5,
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                continue
            data = resp.json()
            search_results = data.get("search", [])
            for res in search_results:
                e_id = res.get("id")
                if not e_id:
                    continue
                # Verify entity is human (P31 == Q5)
                if verify_wikidata_is_human(e_id, timeout=timeout):
                    return e_id
        except Exception as err:
            logger.warning("Wikidata search error for %s: %s", person_name, err)
            return None

    return None


def verify_wikidata_is_human(entity_id: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Verify that a Wikidata entity has claim P31 == Q5 (human)."""
    _throttle_request()
    headers = {"User-Agent": USER_AGENT}
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetclaims",
        "entity": entity_id,
        "property": "P31",
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return False
        data = resp.json()
        claims = data.get("claims", {})
        if not claims and "entities" in data:
            claims = data.get("entities", {}).get(entity_id, {}).get("claims", {})
        p31_snaks = claims.get("P31", [])
        for snak in p31_snaks:
            val_id = snak.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if val_id == "Q5":
                return True
    except Exception as err:
        logger.warning("Wikidata verify human error for %s: %s", entity_id, err)
    return False


def get_wikidata_person_image_title(entity_id: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    """Retrieve P18 (image) title for a Wikidata entity."""
    _throttle_request()
    headers = {"User-Agent": USER_AGENT}
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetclaims",
        "entity": entity_id,
        "property": "P18",
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        claims = data.get("claims", {})
        if not claims and "entities" in data:
            claims = data.get("entities", {}).get(entity_id, {}).get("claims", {})
        p18_snaks = claims.get("P18", [])
        if p18_snaks:
            val = p18_snaks[0].get("mainsnak", {}).get("datavalue", {}).get("value")
            if val and isinstance(val, str):
                return val.strip()
    except Exception as err:
        logger.warning("Wikidata get image title error for %s: %s", entity_id, err)
    return None


def get_wikimedia_image_info(image_title: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[dict[str, Any]]:
    """Retrieve Wikimedia Commons imageinfo and extmetadata for a given file title."""
    _throttle_request()
    headers = {"User-Agent": USER_AGENT}
    url = "https://commons.wikimedia.org/w/api.php"
    clean_title = image_title if image_title.startswith("File:") else f"File:{image_title}"
    params = {
        "action": "query",
        "titles": clean_title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|user",
        "iiurlwidth": 1280,
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            infos = page.get("imageinfo", [])
            if infos:
                info = infos[0]
                meta = info.get("extmetadata", {})
                artist_raw = meta.get("Artist", {}).get("value", "")
                artist = clean_artist_name(artist_raw, meta=meta, info=info)
                license_name = meta.get("LicenseShortName", {}).get("value", "") or meta.get("UsageTerms", {}).get("value", "")
                file_page_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{clean_title}"
                return {
                    "title": page.get("title", clean_title),
                    "url": info.get("url"),
                    "thumburl": info.get("thumburl") or info.get("url"),
                    "width": int(info.get("width") or 0),
                    "height": int(info.get("height") or 0),
                    "artist": artist,
                    "license": license_name,
                    "categories": meta.get("Categories", {}).get("value", ""),
                    "file_page_url": file_page_url,
                }
    except Exception as err:
        logger.warning("Wikimedia imageinfo error for %s: %s", image_title, err)
    return None


def search_wikimedia_commons(
    query: str,
    limit: int = 10,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Search Wikimedia Commons for landscape photos with open licenses."""
    if not query:
        return []

    _throttle_request()
    headers = {"User-Agent": USER_AGENT}
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|user",
        "iiurlwidth": 1280,
        "format": "json",
    }
    results: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return []
        pages = resp.json().get("query", {}).get("pages", {})
        for _, page in pages.items():
            infos = page.get("imageinfo", [])
            if not infos:
                continue
            info = infos[0]
            w = int(info.get("width") or 0)
            h = int(info.get("height") or 0)
            url_str = info.get("url") or ""
            clean_url = url_str.split("?")[0]
            suffix = Path(clean_url).suffix.lower()

            # Must be raster photo image
            if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
                continue

            # Must be landscape and high-resolution (>= 1600px wide)
            if w < 1600 or w < h:
                continue

            title_str = page.get("title", "")
            title_low = title_str.lower()
            # Reject diagrams, blueprints, logos, book covers, schematics
            if any(bk in title_low for bk in ("diagram", "map", "plan", "schematic", "logo", "cover", "pdf", "scan", "chart", "graph", "drawing", "blueprint", "icon")):
                continue

            meta = info.get("extmetadata", {})
            license_name = meta.get("LicenseShortName", {}).get("value", "") or meta.get("UsageTerms", {}).get("value", "")
            if not is_license_allowed(license_name):
                continue

            artist = clean_artist_name(meta.get("Artist", {}).get("value", ""), meta=meta, info=info)
            # FAIL-CLOSED: CC BY / CC BY-SA legally requires author attribution
            if not artist:
                continue

            categories = meta.get("Categories", {}).get("value", "")
            file_page_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{title_str}"

            results.append({
                "title": title_str,
                "url": url_str,
                "thumburl": info.get("thumburl") or url_str,
                "width": w,
                "height": h,
                "artist": artist,
                "license": license_name,
                "categories": categories,
                "file_page_url": file_page_url,
            })
    except Exception as err:
        logger.warning("Wikimedia search error for %s: %s", query, err)

    return results


COMMONS_NATURE_BLACKLIST = {
    "landscape", "nature", "mine", "mining", "quarry", "lake", "river", "mountain",
    "forest", "scenery", "scenic", "park", "garden", "sea", "ocean", "beach", "pond", "waterfall",
    "cave", "cavern",
}

FOREIGN_LOCATIONS = {
    "melbourne", "victoria", "sydney", "adelaide", "perth", "canberra", "gold coast",
    "london", "tokyo", "paris", "new york", "berlin", "munich", "madrid", "toronto", "chicago",
}


def rank_wikimedia_candidates(
    candidates: list[dict[str, Any]],
    scene_entities: list[str],
    narration: str = "",
) -> list[dict[str, Any]]:
    """Rank Wikimedia candidates based on match with characteristic entities of the scene.

    Rules:
    - Rejects foreign locations (e.g. Melbourne, Sydney, London) unless mentioned in narration.
    - Rejects generic nature, landscapes, mines, quarries, caves unless mentioned in narration.
    - Rejects illustrative photos when narration makes concrete assertions about a specific project
      (only exact project photos allowed for concrete claims; illustrations only for general descriptions).
    - Must match >= 2 characteristic entities in title or categories (or >= 1 exact 2-word engineering entity).
    - Sorts by match score descending.
    """
    ranked = []
    narr_low = narration.lower()
    for cand in candidates:
        t_low = cand.get("title", "").lower()
        c_low = cand.get("categories", "").lower()

        # Reject foreign locations unless the narration specifically discusses that foreign location
        has_foreign = False
        for fl in FOREIGN_LOCATIONS:
            if re.search(rf"\b{re.escape(fl)}\b", t_low) or re.search(rf"\b{re.escape(fl)}\b", c_low):
                if fl not in narr_low:
                    has_foreign = True
                    break
        if has_foreign:
            continue

        # Reject landscape / nature / mining / lake / quarry / cave photos for technical scenes
        has_blacklisted = False
        for b_word in COMMONS_NATURE_BLACKLIST:
            if re.search(rf"\b{re.escape(b_word)}\b", t_low) or re.search(rf"\b{re.escape(b_word)}\b", c_low):
                if b_word not in narr_low and not any(b_word in ent.lower() for ent in scene_entities):
                    has_blacklisted = True
                    break
        if has_blacklisted:
            continue

        # Check if narration is asserting a concrete Vietnamese project/station/location
        is_concrete_project = any(kw in narr_low for kw in ("nhổn", "ga hà nội", "kim mã", "cát linh", "văn miếu", "fecon", "tuyến số 3", "tuyến 3", "ga s9", "bến thành"))
        is_exact_photo = any(kw in t_low or kw in c_low for kw in ("nhon", "nhổn", "hanoi metro", "ga hà nội", "kim mã", "cát linh", "văn miếu", "fecon", "line 3"))

        if is_concrete_project and not is_exact_photo:
            # Concrete assertion requires exact photo; generic photo only allowed for general descriptive sentence
            is_general_descriptive = any(kw in narr_low for kw in ("máy đào hầm tbm là gì", "nguyên lý hoạt động", "cấu tạo", "định nghĩa", "khái niệm", "tbm hoạt động", "khiên đào"))
            if not is_general_descriptive:
                continue
            is_illustration = True
        else:
            is_illustration = not is_exact_photo

        matched = []
        has_exact_multiword = False
        for ent in scene_entities:
            e_norm = ent.lower().strip()
            if len(e_norm) >= 3 and (e_norm in t_low or e_norm in c_low):
                if ent not in matched:
                    matched.append(ent)
                if " " in e_norm:
                    has_exact_multiword = True
            elif " " in e_norm:
                for sub_tok in e_norm.split():
                    if len(sub_tok) >= 4 and (sub_tok in t_low or sub_tok in c_low):
                        if sub_tok not in matched:
                            matched.append(sub_tok)

        # Requirement: Phải khớp >= 2 thực thể đặc trưng, hoặc >= 1 cụm thực thể 2 từ chính xác, HOẶC >= 1 thực thể nằm trong title
        has_title_match = any(e.lower() in t_low for e in matched)
        if len(matched) >= 2 or has_exact_multiword or (len(matched) >= 1 and has_title_match):
            cand_copy = dict(cand)
            cand_copy["matched_entities"] = matched
            cand_copy["is_illustration"] = is_illustration
            # Title match gives bonus score over category match
            cand_copy["score"] = len(matched) + (3 if has_title_match else 0) + (5 if is_exact_photo else 0)
            ranked.append(cand_copy)

    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    return ranked


def download_and_verify_photo(
    photo_info: dict[str, Any],
    target_path: Path,
    is_person: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> bool:
    """Download image, verify local CV gates (face detection, document/slide check), and crop."""
    raw_url = photo_info.get("thumburl") or photo_info.get("url")
    if not raw_url or not raw_url.startswith("http"):
        return False
    url = raw_url.split("?")[0]

    _throttle_request()
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200 or len(resp.content) < 15000:
            return False

        im = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = im.size
        if w < 300 or h < 300:
            return False

        # Gate 1: Check document / schematic
        is_doc, _ = is_document_or_schematic_image(im)
        if is_doc:
            return False

        # Gate 2: Check text / slide density (for landmark / machine photos)
        if not is_person:
            is_text, _, _ = detect_text_slide_document(im)
            if is_text:
                return False

        # Gate 3: Face detection
        face_cnt, _ = detect_faces(im)
        if is_person:
            # Person photo MUST contain at least 1 face
            if face_cnt < 1:
                return False
        else:
            # Landmark / machine / tunnel photo should NOT be a portrait/person
            if face_cnt > 0:
                return False

        # Gate 4: Large text / watermark check
        from pipeline.slide_image_resolver import detect_large_text_or_watermark
        has_large_txt, _ = detect_large_text_or_watermark(im)
        if has_large_txt:
            return False

        target_path.parent.mkdir(parents=True, exist_ok=True)
        # Center crop or save full
        if is_person:
            # Keep 1:1 or 4:5 for person portrait
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            im_cropped = im.crop((left, top, left + min_dim, top + min_dim))
            im_resized = im_cropped.resize((1080, 1080), Image.Resampling.LANCZOS)
            im_resized.save(target_path, "JPEG", quality=92)
        else:
            # Save landscape maintaining high quality
            im.save(target_path, "JPEG", quality=92)

        return True
    except Exception as err:
        logger.warning("Download & verify photo failed from %s: %s", url, err)
        return False


class PhotoFinder:
    """Orchestrates photo discovery, validation, caching, and attribution for video projects."""

    def __init__(self, project_dir: Path, timeout: float = DEFAULT_TIMEOUT):
        self.project_dir = Path(project_dir).resolve()
        self.photos_dir = self.project_dir / "assets" / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.attributions: list[dict[str, Any]] = []
        self.resolved_count: int = 0

    def find_photo_for_scene(
        self,
        slide_id: str,
        narration: str,
        brief: dict[str, Any],
        headline: str = "",
        scene_entities: list[str] | None = None,
    ) -> Optional[dict[str, Any]]:
        """Find an authentic, licensed photo for a scene if applicable.
        
        Rules:
        1. Real person: ONLY if person name appears verbatim in narration/brief.
        2. Landmark / machine / project: Wikimedia Commons search landscape >= 1600px.
        3. Max 4 photos per video.
        4. If not found -> returns None (DO NOT force image).
        """
        if self.resolved_count >= MAX_PHOTOS_PER_VIDEO:
            return None

        narr_full = f"{narration} {headline}".strip()
        entities = scene_entities or []

        # 1. Check for real person mentioned verbatim
        famous_names = [
            "Elon Musk", "Sam Altman", "Jensen Huang", "Tim Cook", "Bill Gates",
            "Jeff Bezos", "Mark Zuckerberg", "Sundar Pichai", "Donald Trump",
            "Phùng Đức Long", "Trần Bá Dương",
        ]
        # Also check brief facts for person entities
        b_facts = brief.get("facts") or []
        for f_item in b_facts:
            c_text = f_item.get("claim", "")
            for fn in famous_names:
                if fn not in entities and re.search(rf"\b{re.escape(fn)}\b", c_text, re.I):
                    entities.append(fn)

        target_person = None
        for name in famous_names:
            if re.search(rf"\b{re.escape(name)}\b", narr_full, re.I):
                target_person = name
                break

        if target_person:
            cached_path = self.photos_dir / f"person_{re.sub(r'[^\w]', '_', target_person.lower())}.jpg"
            if cached_path.is_file() and cached_path.stat().st_size > 15000:
                attribution = ""
                author = ""
                license_val = "CC BY-SA"
                file_page_url = ""
                attr_file = self.project_dir / "photo_attributions.json"
                if attr_file.is_file():
                    try:
                        attrs = json.loads(attr_file.read_text(encoding="utf-8"))
                        for item in attrs:
                            if item.get("name") == target_person or item.get("image_path") == str(cached_path):
                                author = item.get("author", "")
                                attribution = item.get("caption", "")
                                license_val = item.get("license", license_val)
                                file_page_url = item.get("file_page_url", "")
                                break
                    except Exception:
                        pass
                if author and author != "Wikimedia Commons":
                    res_dict = {
                        "name": target_person,
                        "image_path": str(cached_path),
                        "caption": attribution or f"Ảnh: {author} / Wikimedia Commons · {license_val}",
                        "author": author,
                        "license": license_val,
                        "entity": target_person,
                        "type": "person",
                        "is_illustration": False,
                        "file_page_url": file_page_url,
                        "reason": f"Khớp người thật '{target_person}' xuất hiện nguyên văn trong lời dẫn",
                    }
                    self.resolved_count += 1
                    return res_dict

            # Query Wikidata
            entity_id = search_wikidata_person(target_person, timeout=self.timeout)
            if entity_id:
                img_title = get_wikidata_person_image_title(entity_id, timeout=self.timeout)
                if img_title:
                    info = get_wikimedia_image_info(img_title, timeout=self.timeout)
                    if info and is_license_allowed(info.get("license", "")):
                        artist = info.get("artist", "")
                        # FAIL-CLOSED: Author is legally mandatory
                        if not artist or artist == "Wikimedia Commons":
                            return None
                        if download_and_verify_photo(info, cached_path, is_person=True, timeout=self.timeout):
                            lic = info.get("license") or "CC BY-SA"
                            caption = f"Ảnh: {artist} / Wikimedia Commons · {lic}"
                            res_dict = {
                                "name": target_person,
                                "image_path": str(cached_path),
                                "caption": caption,
                                "author": artist,
                                "license": lic,
                                "entity": target_person,
                                "type": "person",
                                "is_illustration": False,
                                "file_page_url": info.get("file_page_url", ""),
                                "reason": f"Khớp người thật '{target_person}' (Wikidata {entity_id}=Q5)",
                            }
                            self.attributions.append(res_dict)
                            self._save_attributions()
                            self.resolved_count += 1
                            return res_dict

        # 2. Check for landmarks / machines / structures / projects
        object_queries: list[str] = []
        narr_low = narr_full.lower()

        # Specific machinery and civil engineering mappings
        if any(kw in narr_low for kw in ("nhổn", "ga hà nội", "hanoi metro", "metro hà nội", "tuyến số 3", "tuyến 3")):
            object_queries.extend(["Hanoi Metro", "Nhon", "Hanoi Metro Line 3", "Ga Hà Nội"])
        if any(kw in narr_low for kw in ("tbm", "máy đào hầm", "máy đào", "khiên đào")):
            object_queries.extend(["tunnel boring machine", "Herrenknecht TBM", "tunnel boring machine cutterhead"])
        if any(kw in narr_low for kw in ("đường hầm", "hầm metro", "ga ngầm", "công trình ngầm", "long do thi", "dưới lòng đô thị", "hầm ngầm", "thi công ngầm")):
            object_queries.extend(["metro tunnel construction", "tunnel construction", "underground tunnel", "tunnel boring machine"])
        if any(kw in narr_low for kw in ("tường vây", "cọc khoan", "địa chất", "sụt lún", "địa kỹ thuật")):
            object_queries.extend(["diaphragm wall", "deep excavation construction", "tunnel construction"])
        if any(kw in narr_low for kw in ("đường sắt", "đường sắt bắc nam", "đường sắt cao tốc", "tàu cao tốc")):
            object_queries.extend(["high speed train", "railway track construction"])
        if any(kw in narr_low for kw in ("robot", "tự hành", "máy móc", "tay máy")):
            object_queries.extend(["industrial robot arm", "humanoid robot"])
        if any(kw in narr_low for kw in ("vi mạch", "bán dẫn", "chip ai", "hạ tầng tính toán")):
            object_queries.extend(["microchip wafer", "semiconductor wafer"])

        # Also add any substantive English entities from scene entities
        for ent in entities:
            ent_low = ent.lower().strip()
            if len(ent_low) >= 4 and ent_low not in [q.lower() for q in object_queries]:
                if any(k in ent_low for k in ("tunnel", "metro", "robot", "chip", "machine", "construction", "excavation")):
                    object_queries.append(ent)

        unique_queries: list[str] = []
        for q in object_queries:
            if q not in unique_queries:
                unique_queries.append(q)

        for q in unique_queries[:2]:
            cached_path = self.photos_dir / f"obj_{re.sub(r'[^\w]', '_', q.lower())}.jpg"
            if cached_path.is_file() and cached_path.stat().st_size > 15000:
                attribution = ""
                author = ""
                license_val = "CC BY-SA"
                is_illus = False
                file_page_url = ""
                attr_file = self.project_dir / "photo_attributions.json"
                if attr_file.is_file():
                    try:
                        attrs = json.loads(attr_file.read_text(encoding="utf-8"))
                        for item in attrs:
                            if item.get("name") == q.title() or item.get("image_path") == str(cached_path):
                                author = item.get("author", "")
                                attribution = item.get("caption", "")
                                license_val = item.get("license", license_val)
                                is_illus = item.get("is_illustration", False)
                                file_page_url = item.get("file_page_url", "")
                                break
                    except Exception:
                        pass
                if author and author != "Wikimedia Commons":
                    res_dict = {
                        "name": q.title(),
                        "image_path": str(cached_path),
                        "caption": attribution or (f"{'Ảnh minh họa · Ảnh: ' if is_illus else 'Ảnh: '}{author} / Wikimedia Commons · {license_val}"),
                        "author": author,
                        "license": license_val,
                        "entity": q,
                        "type": "landmark_or_machine",
                        "is_illustration": is_illus,
                        "file_page_url": file_page_url,
                        "reason": f"Khớp thực thể công trình/máy móc '{q}'",
                    }
                    self.resolved_count += 1
                    return res_dict

            candidates = search_wikimedia_commons(q, limit=6, timeout=self.timeout)
            # Rank candidates by matching scene entities in title or categories
            q_tokens = [tok for tok in q.lower().split() if len(tok) >= 3]
            target_scene_entities = list(set(entities + q_tokens))
            ranked_candidates = rank_wikimedia_candidates(candidates, target_scene_entities, narration=narr_full)
            cands_to_check = ranked_candidates if ranked_candidates else candidates

            for cand in cands_to_check[:3]:
                artist = cand.get("artist", "")
                # FAIL-CLOSED: Author is legally mandatory
                if not artist or artist == "Wikimedia Commons":
                    continue
                if download_and_verify_photo(cand, cached_path, is_person=False, timeout=self.timeout):
                    lic = cand.get("license") or "CC BY-SA"
                    is_illus = cand.get("is_illustration", False)
                    caption_prefix = "Ảnh minh họa · Ảnh: " if is_illus else "Ảnh: "
                    caption = f"{caption_prefix}{artist} / Wikimedia Commons · {lic}"
                    res_dict = {
                        "name": q.title(),
                        "image_path": str(cached_path),
                        "caption": caption,
                        "author": artist,
                        "license": lic,
                        "entity": q,
                        "type": "landmark_or_machine",
                        "is_illustration": is_illus,
                        "file_page_url": cand.get("file_page_url", ""),
                        "reason": f"Khớp ảnh thực tế Wikimedia Commons '{cand.get('title')}' cho thực thể '{q}'" + (" (minh họa)" if is_illus else ""),
                    }
                    self.attributions.append(res_dict)
                    self._save_attributions()
                    self.resolved_count += 1
                    return res_dict

        return None

    def _save_attributions(self) -> None:
        """Persist photo attributions to photo_attributions.json and credits.txt."""
        try:
            attr_file = self.project_dir / "photo_attributions.json"
            attr_file.write_text(json.dumps(self.attributions, ensure_ascii=False, indent=2), encoding="utf-8")

            credits_file = self.project_dir / "credits.txt"
            existing = credits_file.read_text(encoding="utf-8") if credits_file.is_file() else ""
            lines = [existing.strip()] if existing.strip() else []
            lines.append("\n--- HÌNH ẢNH WIKIMEDIA COMMONS & BẢN QUYỀN MỞ ---")
            for item in self.attributions:
                page_link = f" - {item.get('file_page_url')}" if item.get('file_page_url') else ""
                lines.append(f"- {item.get('entity')}: {item.get('caption')} ({item.get('license')}){page_link}")
            credits_file.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        except Exception as err:
            logger.warning("Could not save photo attributions: %s", err)
