import json
import sys
import re
from typing import Optional, List, Tuple
from urllib import request, parse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, unquote
import uuid
import time
import subprocess
from datetime import datetime

# =========================
# TERMUX COLOR CODES
# =========================

BLACK   = "\033[30m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

DARK_RED     = "\033[31m"
DARK_GREEN   = "\033[32m"
DARK_YELLOW  = "\033[33m"
DARK_BLUE    = "\033[34m"
DARK_MAGENTA = "\033[35m"
DARK_CYAN    = "\033[36m"
GRAY         = "\033[90m"

BOLD_RED     = "\033[1;91m"
BOLD_GREEN   = "\033[1;92m"
BOLD_YELLOW  = "\033[1;93m"
BOLD_BLUE    = "\033[1;94m"
BOLD_MAGENTA = "\033[1;95m"
BOLD_CYAN    = "\033[1;96m"
BOLD_WHITE   = "\033[1;97m"

UNDERLINE = "\033[4m"
RESET = "\033[0m"

API_TEMPLATE = "https://www.hotstar.com/api/internal/bff/v2/slugs/in/{slug_path}/watch"
TOKEN = os.getenv("HOTSTAR_TOKEN", "")
HOTSTAR_URL = os.getenv("HOTSTAR_URL", "")

LANGUAGES={
"eng":"ENGLISH",
"en":"ENGLISH",
"hin":"HINDI",
"hi":"HINDI",
"hd":"HINDI HD",
"mar":"MARATHI",
"mr":"MARATHI",
"ma":"MARATHI",
"guj":"GUJARATI",
"gu":"GUJARATI",
"bho":"BHOJPURI",
"bh":"BHOJPURI",
"bih":"BHOJPURI",
"pan":"PUNJABI",
"pun":"PUNJABI",
"pa":"PUNJABI",
"pu":"PUNJABI",
"har":"HARYANVI",
"hv":"HARYANVI",
"ha":"HARYANVI",
"tam":"TAMIL",
"ta":"TAMIL",
"tel":"TELUGU",
"te":"TELUGU",
"kan":"KANNADA",
"kn":"KANNADA",
"mal":"MALAYALAM",
"ml":"MALAYALAM",
"ben":"BENGALI",
"bn":"BENGALI",
"ori":"ORIYA",
"or":"ORIYA",
}

HEADERS_BASE = {
    "User-Agent": "Hotstar;in.startv.hotstar.dplus.tv/26.05.10.2 (Android/14; tv)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "x-hs-retry-count": "0",
    "X-HS-Platform": "androidtv",
    "X-Country-Code": "in",
    "X-HS-Accept-language": "eng",
    "x-hs-is-retry": "false",
    "X-HS-Client": "platform:androidtv;app_id:in.startv.hotstar.dplus.tv;app_version:26.05.10.2;os:Android;os_version:14;schema_version:0.0.1690",
    "x-hs-app": "260510002",
    "Alt-Used": "www.hotstar.com",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

def build_jhs_headers():
    headers = HEADERS_BASE.copy()
    headers["x-hs-usertoken"] = load_user_token()
    headers["X-HS-Platform"] = "androidtv"
    headers["x-hs-app"] = "260510002"
    return headers

def build_jhs_headers_android():
    headers = HEADERS_BASE.copy()
    headers.update({
        "User-Agent": "Hotstar;in.startv.hotstar/26.03.30.2.11580 (Android/12)",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "eng",
        "Referer": "https://www.hotstar.com/in/explore?search_query=live",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
        "x-hs-retry-count": "0",
        "X-HS-Platform": "android",
        "X-Country-Code": "in",
        "X-HS-Accept-language": "eng",
        "X-Request-Id": "2e9242-6af387-32c79a-96accb",
        "x-hs-device-id": "6812b7-62b085-769fe2-7eccc0",
        "x-hs-is-retry": "false",
        "x-hs-request-id": "2e9242-6af387-32c79a-96accb",
        "X-HS-Client": (
            "platform:android;"
            "app_id:in.startv.hotstar;"
            "app_version:26.03.06.0;"
            "os:Android;"
            "os_version:12;"
            "schema_version:0.0.1690"
        ),
        "x-hs-app": "260306000",
        "Alt-Used": "www.hotstar.com",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Priority": "u=4",
    })
    headers["x-hs-usertoken"] = load_user_token()
    return headers

def build_ott_url(stream_url, hdntl):
    clean_url = stream_url.split("?")[0]
    final = (
        f"{clean_url}?|"
        f"Cookie=hdntl={hdntl}"
        f"&User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)"
        f"&Referer=https://www.hotstar.com/"
        f"&Origin=https://www.hotstar.com"
    )
    return final

def build_ott_drm_url(mpd_url: str, key_str: str) -> str:
    """Build OTT Navigator / pipe-format DRM URL for clearkey MPD streams."""
    # Decode percent-encoded chars (%2f→/ %3d→= %2a→* etc.) so OTT Navigator
    # can correctly pass the hdnea token to the CDN (movie URLs come pre-encoded)
    base, _, query = mpd_url.partition("?")
    decoded_url = f"{base}?{unquote(query)}" if query else base
    final = (
        f"{decoded_url}"
        f"|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)"
        f"&Referer=https://www.hotstar.com/"
        f"&Origin=https://www.hotstar.com"
        f"&drmScheme=clearkey"
        f"&drmLicense={key_str}"
    )
    return final

def build_ott_drm_url_direct(mpd_url: str, key_str: str = "", hdntl_cookie: str = "") -> str:
    """Build OTT Navigator / NS Player pipe-URL from a raw MPD URL with optional cookie + clearkey.
    Strips hdnea query entirely — auth is provided by the hdntl cookie instead."""
    base = mpd_url.partition("?")[0]  # strip all query params (hdnea etc.)
    parts = [
        f"{base}?",  # NS Player expects base?| format
        "|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)",
        "&Referer=https://www.hotstar.com/",
        "&Origin=https://www.hotstar.com",
    ]
    if hdntl_cookie:
        parts.append(f"&Cookie=hdntl={hdntl_cookie}")
    if key_str:
        parts.append("&drmScheme=clearkey")
        parts.append(f"&drmLicense={key_str}")
    return "".join(parts)

def load_user_token():
    return TOKEN

def build_headers() -> dict:
    headers = HEADERS_BASE.copy()
    headers["x-hs-usertoken"] = load_user_token()
    return headers

def extract_hdntl(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    token = ""
    if "hdntl" in query:
        token = query["hdntl"][0]
    elif "hdnea" in query:
        token = query["hdnea"][0]
    if not token:
        return ""
    token = re.sub(r"st=\d+~", "", token)
    return token

def extract_slug_path(url: str) -> Optional[str]:
    value = url.strip()
    parsed = parse.urlparse(value)
    path = parsed.path if parsed.scheme else value
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    if segments[0] == "in":
        segments = segments[1:]
    if segments and segments[-1] == "watch":
        segments = segments[:-1]
    return "/".join(segments)

def build_jhs_api_url(slug_path: str, lang: str, is_live: bool = False):
    if is_live:
        capabilities = {
            "ads": ["ssai"],
            "audio_channel": ["stereo"],
            "container": ["ts"],
            "dvr": ["short"],
            "dynamic_range": ["sdr"],
            "encryption": ["plain"],
            "ladder": ["phone"],
            "package": ["hls"],
            "resolution": ["hd", "fhd"],
            "video_codec": ["h264"]
        }
        drm = {"widevine_security_level": ["SW_SECURE_DECODE"]}
    else:
        capabilities = {
            "ads": ["non_ssai"],
            "audio_channel": ["stereo"],
            "container": ["fmp4", "fmp4br", "ts"],
            "dvr": ["short"],
            "dynamic_range": ["sdr"],
            "encryption": ["plain"],
            "ladder": ["web", "tv", "full", "phone"],
            "package": ["hls"],
            "resolution": ["sd", "hd", "fhd"],
            "video_codec": ["h264", "h265"],
            "video_codec_non_secure": ["h264", "h265"]
        }
        drm = {
            "hdcp_version": ["HDCP_V2_2"],
            "widevine_security_level": ["SW_SECURE_DECODE", "SW_SECURE_CRYPTO"]
        }
    return (
        API_TEMPLATE.format(slug_path=slug_path)
        + "?search_query=live"
        + "&client_capabilities=" + parse.quote(json.dumps(capabilities, separators=(",", ":")))
        + "&drm_parameters=" + parse.quote(json.dumps(drm, separators=(",", ":")))
        + "&request_features=consent_supported"
        + "&lang=" + parse.quote(lang)
    )

def build_jhs_4k_api_url(slug_path: str, lang: str, is_live: bool = False):
    if is_live:
        capabilities = {
            "ads": ["ssai"],
            "audio_channel": ["stereo", "dolby51", "atmos"],
            "container": ["ts", "fmp4"],
            "dvr": ["short"],
            "dynamic_range": ["sdr", "hdr"],
            "encryption": ["plain"],
            "ladder": ["tv", "full"],
            "package": ["hls", "dash"],
            "resolution": ["hd", "fhd", "4k"],
            "true_resolution": ["hd", "4k"],
            "video_codec": ["h265", "h264"]
        }
        drm = {"widevine_security_level": ["SW_SECURE_DECODE"]}
    else:
        capabilities = {
            "ads": ["non_ssai"],
            "audio_channel": ["stereo", "dolby51", "atmos"],
            "container": ["fmp4", "fmp4br", "ts"],
            "dvr": ["short", "long"],
            "dynamic_range": ["sdr", "hdr"],
            "encryption": ["plain"],
            "ladder": ["tv", "full"],
            "package": ["hls", "dash"],
            "resolution": ["sd", "hd", "fhd", "4k"],
            "true_resolution": ["hd", "4k"],
            "video_codec": ["h265", "h264"],
            "video_codec_non_secure": ["h265", "h264", "vp9"]
        }
        drm = {
            "hdcp_version": ["HDCP_V2_2"],
            "widevine_security_level": ["SW_SECURE_DECODE", "SW_SECURE_CRYPTO"]
        }
    return (
        API_TEMPLATE.format(slug_path=slug_path)
        + "?search_query=live"
        + "&client_capabilities=" + parse.quote(json.dumps(capabilities, separators=(",", ":")))
        + "&drm_parameters=" + parse.quote(json.dumps(drm, separators=(",", ":")))
        + "&request_features=consent_supported"
        + "&lang=" + parse.quote(lang)
    )

def build_api_url(slug_path: str, lang: str, quality_choice: str) -> str:
    if quality_choice == "1":
        capabilities = {
            "ads": ["non_ssai"],
            "audio_channel": ["stereo", "dolby51", "atmos"],
            "container": ["fmp4", "fmp4br", "ts"],
            "dvr": ["short", "long"],
            "dynamic_range": ["sdr", "hdr"],
            "encryption": ["widevine", "plain"],
            "ladder": ["tv", "full"],
            "package": ["dash", "hls"],
            "resolution": ["sd", "hd", "fhd", "4k"],
            "true_resolution": ["hd", "4k"],
            "video_codec": ["h265", "h264"],
            "video_codec_non_secure": ["h265", "h264", "vp9"]
        }
    else:
        capabilities = {
            "ads": ["non_ssai", "ssai"],
            "audio_channel": ["stereo"],
            "container": ["fmp4", "fmp4br", "ts"],
            "dvr": ["short"],
            "dynamic_range": ["sdr"],
            "encryption": ["widevine", "plain"],
            "ladder": ["web", "tv", "phone"],
            "package": ["dash", "hls"],
            "resolution": ["sd", "hd", "fhd"],
            "video_codec": ["h264", "h265"],
            "video_codec_non_secure": ["h264", "h265"]
        }
    drm = {
        "hdcp_version": ["HDCP_V2_2"],
        "widevine_security_level": ["SW_SECURE_DECODE", "SW_SECURE_CRYPTO"]
    }
    return (
        API_TEMPLATE.format(slug_path=slug_path)
        + "?search_query=live"
        + "&client_capabilities=" + parse.quote(json.dumps(capabilities, separators=(",", ":")))
        + "&drm_parameters=" + parse.quote(json.dumps(drm, separators=(",", ":")))
        + "&request_features=consent_supported"
        + "&lang=" + parse.quote(lang)
    )

def extract_match_title(url: str) -> tuple[str, str]:
    slug = extract_slug_path(url)
    if not slug: return "HOTSTAR CONTENT", ""
    parts = slug.split('/')
    match_no = ""
    match_search = re.search(r'(match[-_]?\d+|\bm\d+\b)', slug.lower())
    if match_search:
        match_no = match_search.group(1).replace('match', 'MATCH-').replace('m', 'MATCH-').upper()
        match_no = re.sub(r'-+', '-', match_no)
    for p in parts:
        if any(x in p for x in ["tata-ipl", "-vs-", "highlights", "replay"]):
            clean_name = p.replace('-highlights', '').replace('-replay', '').replace('-video', '')
            clean_name = re.sub(r'match[-_]?\d+|m\d+', '', clean_name)
            return clean_name.strip('-').replace('-', ' ').upper(), match_no
    name = parts[1] if len(parts) > 1 else parts[0]
    return name.replace('-', ' ').upper(), match_no

def extract_stream_type(url: str) -> str:
    u = url.lower()
    if "replay" in u: return "REPLAY"
    if "highlights" in u: return "HIGHLIGHTS"
    if "clips" in u: return "CLIP"
    if "/movies/" in u: return "MOVIE"
    if "/sports/" in u and "/video/live/" in u: return "LIVE TV"
    if "/tv/" in u and "live" in u: return "LIVE TV"
    if "/shows/" in u: return "TV SHOW"
    return "STREAM"

def extract_best_stream(player_config: dict, input_url: str) -> Optional[str]:
    media_assets = []
    stype = extract_stream_type(input_url)
    for key in ["media_asset", "media_asset_v2"]:
        asset = player_config.get(key)
        if isinstance(asset, dict):
            media_assets.append(asset)
        elif isinstance(asset, list):
            media_assets.extend(asset)
    for asset in media_assets:
        for key in ["fallback", "primary"]:
            try:
                url = asset[key]["content_url"]
                if not url:
                    continue
                if ".m3u8" not in url and ".mpd" not in url:
                    continue
                base_url = url.split("?")[0]
                if ".mpd" in base_url:
                    return url
                candidates = [
                    base_url.replace("_fhd", "_fhd").replace("/fhd/", "/fhd/"),
                    base_url.replace("_fhd", "_hd").replace("/fhd/", "/hd/").replace("_hd", "_hd"),
                    base_url.replace("_fhd", "_sd").replace("/fhd/", "/sd/").replace("/hd/", "/sd/").replace("_hd", "_sd"),
                ]
                seen = set()
                candidates = [c for c in candidates if not (c in seen or seen.add(c))]
                final_url = candidates[0]
                if stype in ["LIVE TV", "MOVIE", "TV SHOW"]:
                    return url
                elif stype == "REPLAY":
                    clean = url.split("?")[0]
                    path = clean.rsplit("/", 1)[0]
                    return path + "/index_7.m3u8"
                elif stype in ["HIGHLIGHTS", "CLIP"]:
                    return final_url.split("?")[0]
                return final_url
            except:
                pass
    return None

def extract_4k_streams(player_config: dict):
    streams = []
    for key in ["media_asset", "media_asset_v2"]:
        assets = player_config.get(key)
        if not assets: continue
        if isinstance(assets, dict):
            assets = [assets]
        for asset in assets:
            for variant in ["fallback", "primary"]:
                item = asset.get(variant)
                if not isinstance(item, dict): continue
                url = item.get("content_url")
                if not url: continue
                tags = str(item.get("playback_tags", "")).lower()
                height = int(item.get("height") or 0)
                video_quality = str(item.get("video_quality", "")).lower()
                resolution = str(item.get("resolution", "")).lower()
                url_lower = url.lower()
                is_4k = (
                    "4k" in tags or height >= 2160 or "4k" in video_quality or
                    "4k" in resolution or "_4k" in url_lower or "/4k/" in url_lower
                )
                if is_4k:
                    streams.append({"url": url, "height": height, "type": variant.upper()})
    return streams

def extract_jhs_fallback_only(player_config):
    streams = []
    for key in ["media_asset", "media_asset_v2"]:
        assets = player_config.get(key)
        if not assets:
            continue
        if isinstance(assets, dict):
            assets = [assets]
        for asset in assets:
            for variant in ["fallback", "primary"]:
                item = asset.get(variant)
                if not isinstance(item, dict):
                    continue
                url = item.get("content_url")
                if url and (".m3u8" in url or ".mpd" in url):
                    streams.append({"content_url": url, "type": variant, "playback_tags": item.get("playback_tags", "")})
    return streams

def build_drm_api_url(slug_path: str, lang: str = "eng") -> str:
    capabilities = {
        "ads": ["non_ssai"],
        "audio_channel": ["stereo", "dolby51", "atmos"],
        "container": ["fmp4", "fmp4br"],
        "dvr": ["short", "long"],
        "dynamic_range": ["sdr", "hdr"],
        "encryption": ["widevine"],
        "ladder": ["tv", "full"],
        "package": ["dash"],
        "resolution": ["sd", "hd", "fhd", "4k"],
        "true_resolution": ["hd", "4k"],
        "video_codec": ["h265", "h264"],
        "video_codec_non_secure": ["h265", "h264", "vp9"]
    }
    drm = {
        "hdcp_version": ["HDCP_V2_2"],
        "widevine_security_level": ["SW_SECURE_DECODE", "SW_SECURE_CRYPTO"]
    }
    return (
        API_TEMPLATE.format(slug_path=slug_path)
        + "?search_query=live"
        + "&client_capabilities=" + parse.quote(json.dumps(capabilities, separators=(",", ":")))
        + "&drm_parameters=" + parse.quote(json.dumps(drm, separators=(",", ":")))
        + "&request_features=consent_supported"
        + "&lang=" + parse.quote(lang)
    )

def extract_drm_info(player_config: dict) -> list:
    results = []
    seen = set()
    def find_license(obj, depth=0):
        if depth > 6 or not isinstance(obj, (dict, list)):
            return None
        if isinstance(obj, list):
            for item in obj:
                r = find_license(item, depth+1)
                if r: return r
        elif isinstance(obj, dict):
            for k in ["license_url", "licenseUrl", "widevine_license_url", "keyServerUrl", "key_server_url"]:
                if k in obj and obj[k]:
                    return str(obj[k])
            for v in obj.values():
                r = find_license(v, depth+1)
                if r: return r
        return None
    license_url = find_license(player_config)
    for key in ["media_asset", "media_asset_v2"]:
        assets = player_config.get(key)
        if not assets:
            continue
        if isinstance(assets, dict):
            assets = [assets]
        for asset in assets:
            for variant in ["primary", "fallback"]:
                item = asset.get(variant)
                if not isinstance(item, dict):
                    continue
                url = item.get("content_url", "")
                if not url or ".mpd" not in url:
                    continue
                base = url.split("?")[0]
                if base in seen:
                    continue
                seen.add(base)
                item_license = item.get("license_url") or item.get("licenseUrl") or license_url
                results.append({"mpd_url": url, "license_url": item_license, "variant": variant.upper()})
    return results

def fetch_mpd_pssh(mpd_url: str) -> dict:
    try:
        req = request.Request(mpd_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.hotstar.com/",
            "Origin": "https://www.hotstar.com",
            "Accept": "*/*",
        })
        with request.urlopen(req, timeout=15) as resp:
            mpd_text = resp.read().decode("utf-8", errors="replace")
        pssh = ""
        wv_block = re.search(r'(?:edef8ba9|EDEF8BA9).{0,200}?<cenc:pssh[^>]*>(.*?)</cenc:pssh>', mpd_text, re.DOTALL)
        if not wv_block:
            wv_block = re.search(r'<cenc:pssh[^>]*>(.*?)</cenc:pssh>', mpd_text, re.DOTALL)
        if wv_block:
            pssh = wv_block.group(1).strip()
        kid_patterns = [
            r'default_KID="([0-9a-fA-F\-]{32,36})"',
            r'cenc:default_KID="([0-9a-fA-F\-]{32,36})"',
            r'<ContentProtection[^>]+value="([0-9a-fA-F]{32})"'
        ]
        key_ids = []
        for pat in kid_patterns:
            for m in re.finditer(pat, mpd_text):
                kid = m.group(1).replace("-", "").lower()
                if len(kid) == 32 and kid not in key_ids:
                    key_ids.append(kid)
        has_clearkey = "1077efec" in mpd_text.lower() or "clearkey" in mpd_text.lower()
        return {"pssh": pssh, "key_ids": key_ids, "has_clearkey": has_clearkey, "raw_mpd": mpd_text, "error": None}
    except Exception as e:
        return {"pssh": "", "key_ids": [], "has_clearkey": False, "raw_mpd": "", "error": str(e)}

def extract_mpd_languages(mpd_url: str) -> list:
    """Parse MPD XML and return list of (lang_code, lang_name) from audio AdaptationSets.
    Falls back to URL path detection if MPD parsing fails."""
    LANG_MAP = {
        "eng": "ENGLISH", "en": "ENGLISH",
        "hin": "HINDI",   "hi": "HINDI",
        "mar": "MARATHI", "mr": "MARATHI",
        "tam": "TAMIL",   "ta": "TAMIL",
        "tel": "TELUGU",  "te": "TELUGU",
        "kan": "KANNADA", "kn": "KANNADA",
        "mal": "MALAYALAM","ml": "MALAYALAM",
        "ben": "BENGALI", "bn": "BENGALI",
        "guj": "GUJARATI","gu": "GUJARATI",
        "pan": "PUNJABI", "pa": "PUNJABI",
        "bho": "BHOJPURI","bih": "BHOJPURI","bh": "BHOJPURI",
        "har": "HARYANVI","hv": "HARYANVI","ha": "HARYANVI",
        "ori": "ORIYA",   "or": "ORIYA",
    }

    def langs_from_url(url: str) -> list:
        """Extract language from MPD URL path segments like /eng/ /hin/ etc."""
        path = url.split("?")[0].lower()
        segments = path.replace("//", "/").split("/")
        found = []
        seen = set()
        for seg in segments:
            seg = seg.strip()
            if seg in LANG_MAP and seg not in seen:
                seen.add(seg)
                found.append((seg, LANG_MAP[seg]))
        return found

    try:
        req = request.Request(mpd_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.hotstar.com/",
            "Origin": "https://www.hotstar.com",
            "Accept": "*/*",
        })
        with request.urlopen(req, timeout=15) as resp:
            mpd_text = resp.read().decode("utf-8", errors="replace")

        seen = set()
        langs = []

        # Strategy 1: Find audio AdaptationSet blocks and extract lang= from them
        # Split on AdaptationSet boundaries to isolate each block
        adapt_blocks = re.split(r'(?=<AdaptationSet)', mpd_text, flags=re.IGNORECASE)
        for block in adapt_blocks:
            if not block.strip().startswith("<AdaptationSet"):
                continue
            # Get just the opening tag
            tag_match = re.match(r'<AdaptationSet([^>]*)>', block, re.IGNORECASE | re.DOTALL)
            if not tag_match:
                continue
            tag_attrs = tag_match.group(1)
            # Check if this is an audio AdaptationSet
            is_audio = (
                'audio' in tag_attrs.lower() or
                'audio' in block[:200].lower()
            )
            if not is_audio:
                continue
            # Extract lang attribute (handles lang="eng", lang='hin', lang=tel etc.)
            lang_m = re.search(r'''lang\s*=\s*["']?([a-zA-Z]{2,3})["']?''', tag_attrs)
            if lang_m:
                lc = lang_m.group(1).lower()
                if lc not in seen and lc in LANG_MAP:
                    seen.add(lc)
                    langs.append((lc, LANG_MAP[lc]))

        # Strategy 2: Scan ALL lang= in the full MPD (some MPDs don't label mimeType in tag)
        if not langs:
            for m in re.finditer(r'''lang\s*=\s*["']?([a-zA-Z]{2,3})["']?''', mpd_text):
                lc = m.group(1).lower()
                if lc not in seen and lc in LANG_MAP:
                    seen.add(lc)
                    langs.append((lc, LANG_MAP[lc]))

        # Strategy 3: URL path fallback if MPD gave nothing
        if not langs:
            langs = langs_from_url(mpd_url)

        return langs

    except Exception:
        # Network/parse error — fall back to URL detection
        return langs_from_url(mpd_url)

def try_clearkey_json(kid_list: list, license_url: str) -> list:
    import base64 as _b64
    if not kid_list or not license_url:
        return []
    try:
        b64_kids = [_b64.urlsafe_b64encode(bytes.fromhex(kid.replace("-", ""))).rstrip(b"=").decode() for kid in kid_list]
        body = json.dumps({"kids": b64_kids, "type": "temporary"}).encode()
        ck_req = request.Request(license_url, data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.hotstar.com/",
            "Origin": "https://www.hotstar.com",
        }, method="POST")
        with request.urlopen(ck_req, timeout=12) as resp:
            resp_json = json.loads(resp.read())
        keys = []
        for entry in resp_json.get("keys", []):
            k_b64 = entry.get("k", "")
            kd_b64 = entry.get("kid", "")
            if not k_b64:
                continue
            k_hex = _b64.urlsafe_b64decode(k_b64 + "==").hex()
            kd_hex = _b64.urlsafe_b64decode(kd_b64 + "==").hex() if kd_b64 else kid_list[0]
            keys.append(f"{kd_hex}:{k_hex}")
        return keys
    except Exception:
        return []

def fetch_widevine_keys(pssh_b64: str, license_url: str) -> list:
    try:
        from pywidevine.cdm import Cdm
        from pywidevine.device import Device
        from pywidevine.pssh import PSSH as WvPSSH
    except ImportError:
        return ["❌ pywidevine not installed → pip install pywidevine"]
    if not pssh_b64:
        return ["❌ No PSSH available"]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    wvd_names = ["device.wvd", "wv.wvd", "chrome.wvd", "cdm.wvd"]
    device_path = None
    for name in wvd_names:
        for base in [script_dir, os.getcwd()]:
            p = os.path.join(base, name)
            if os.path.exists(p):
                device_path = p
                break
        if device_path:
            break
    if not device_path:
        return ["❌ No .wvd file found. Place device.wvd in script folder."]
    try:
        device = Device.load(device_path)
        cdm = Cdm.from_device(device)
        session_id = cdm.open()
        pssh_obj = WvPSSH(pssh_b64)
        challenge = cdm.get_license_challenge(session_id, pssh_obj)
        lic_req = request.Request(license_url, data=challenge, headers={
            "Content-Type": "application/octet-stream",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.hotstar.com/",
            "Origin": "https://www.hotstar.com",
        }, method="POST")
        with request.urlopen(lic_req, timeout=15) as resp:
            license_bytes = resp.read()
        cdm.parse_license(session_id, license_bytes)
        keys = [f"{k.kid.hex}:{k.key.hex()}" for k in cdm.get_keys(session_id) if k.type == "CONTENT"]
        cdm.close(session_id)
        return keys if keys else ["⚠ License OK but no CONTENT keys returned"]
    except Exception as e:
        return [f"❌ {str(e)}"]

def fetch_lang_stream(lang_code: str, lang_name: str, slug_path: str, input_url: str, quality_choice: str):
    try:
        api_url = build_api_url(slug_path, lang_code, quality_choice)
        req = request.Request(api_url, headers=build_headers())
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        player_config = None
        page_spaces = data.get("success", {}).get("page", {}).get("spaces", {})
        for s in page_spaces:
            for w in page_spaces[s].get("widget_wrappers", []):
                if "player_config" in w.get("widget", {}).get("data", {}):
                    player_config = w["widget"]["data"]["player_config"]
                    break
            if player_config:
                break
        if not player_config:
            return None
        clean_stream = extract_best_stream(player_config, input_url)
        if not clean_stream:
            return None
        audio_lang = ""
        try:
            # Primary: URL path segment match (most reliable) e.g. /eng/ /hin/ /tam/
            _url_segs = set(clean_stream.lower().split("?")[0].replace("https://","").split("/"))
            for code, name in LANGUAGES.items():
                if code.lower() in _url_segs:
                    audio_lang = name
                    break
            # Fallback: playback_tags "language:eng" style
            if not audio_lang:
                _ptags = str(player_config.get("playback_tags", "")).lower()
                for _tag in _ptags.split(";"):
                    if _tag.strip().startswith("language:"):
                        _detected = _tag.split(":")[1].strip()
                        audio_lang = LANGUAGES.get(_detected, "")
                        break
        except:
            pass
        is_hdr = False
        dynamic_range = player_config.get("dynamic_range", "").lower()
        if dynamic_range == "hdr":
            is_hdr = True
        elif "hdr" in str(player_config.get("playback_tags", "")).lower():
            is_hdr = True
        elif "hdr" in clean_stream.lower():
            is_hdr = True
        return {"lang_name": audio_lang or lang_name, "stream": clean_stream, "player_config": player_config, "is_hdr": is_hdr}
    except:
        return None

# ===================== OPTION 5 (PRIMARY ADSFREE) =====================
LANG_MAP_1 = {
    "eng": "ENGLISH", "hin": "HINDI", "mar": "MARATHI", "guj": "GUJARATI",
    "bih": "BHOJPURI", "pan": "PUNJABI", "har": "HARYANVI", "tam": "TAMIL",
    "tel": "TELUGU", "kan": "KANNADA", "mal": "MALAYALAM", "ben": "BENGALI"
}
LANG_DISPLAY_1 = {
    "eng": "ENGLISH", "hin": "HINDI", "mar": "MARATHI", "guj": "GUJARATI",
    "bih": "BHOJPURI", "pan": "PUNJABI", "har": "HARYANVI", "tam": "TAMIL",
    "tel": "TELUGU", "kan": "KANNADA", "mal": "MALAYALAM", "ben": "BENGALI",
    "hi": "HINDI", "hd": "HINDI", "mr": "MARATHI", "ma": "MARATHI",
    "gu": "GUJARATI", "bho": "BHOJPURI", "bh": "BHOJPURI",
    "pun": "PUNJABI", "pa": "PUNJABI", "pu": "PUNJABI",
    "hv": "HARYANVI", "ha": "HARYANVI", "ta": "TAMIL",
    "te": "TELUGU", "kn": "KANNADA", "ml": "MALAYALAM", "bn": "BENGALI"
}
CDN_HOSTS_1 = [
    "live11p.hotstar.com", "live12p.hotstar.com", "live13p.hotstar.com",
    "live14p.hotstar.com", "live15p.hotstar.com", "live16p.hotstar.com",
    "live17p.hotstar.com", "live18p.hotstar.com", "live19p.hotstar.com",
    "live20p.hotstar.com"
]
HEADERS_BASE_1 = {
    "User-Agent": "Hotstar;in.startv.hotstar/26.03.30.2.11580 (Android/12)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "eng",
    "Referer": "https://www.hotstar.com/in/explore?search_query=live",
    "Connection": "keep-alive",
    "X-HS-Platform": "androidtv",
    "X-Country-Code": "in",
    "X-HS-Accept-language": "eng",
    "x-hs-is-retry": "false",
    "x-hs-retry-count": "0",
    "X-HS-Client": "platform:androidtv;app_id:in.startv.hotstar;app_version:26.03.06.0;os:Android;os_version:12;schema_version:0.0.1690",
    "x-hs-app": "260306000",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}
def build_headers_1():
    h = HEADERS_BASE_1.copy()
    h["x-hs-usertoken"] = load_user_token()
    h["X-Request-Id"] = str(uuid.uuid4())
    h["x-hs-request-id"] = str(uuid.uuid4())
    h["x-hs-device-id"] = str(uuid.uuid4())
    return h
def build_api_url_1(asset_id: str, lang: str, slug_path: str = "") -> str:
    # Use slug_path for correct URL, fallback to asset_id guess
    if slug_path:
        base = f"https://www.hotstar.com/api/internal/bff/v2/slugs/in/{slug_path}/watch"
    else:
        base = f"https://www.hotstar.com/api/internal/bff/v2/slugs/in/sports/cricket/{asset_id}/video/live/watch"
    caps = {
        "ads": ["ssai", "non_ssai"],
        "audio_channel": ["stereo", "dolby51", "atmos"],
        "container": ["fmp4", "fmp4br", "ts"],
        "dvr": ["short", "long"],
        "dynamic_range": ["hdr", "sdr"],
        "encryption": ["plain", "widevine"],
        "ladder": ["tv", "full", "web", "phone"],
        "package": ["hls", "dash"],
        "resolution": ["4k", "fhd", "hd", "sd"],
        "true_resolution": ["4k", "hd"],
        "video_codec": ["h265", "h264"],
        "video_codec_non_secure": ["h265", "h264", "vp9"]
    }
    drm = {
        "hdcp_version": ["HDCP_V2_2"],
        "widevine_security_level": ["SW_SECURE_DECODE", "SW_SECURE_CRYPTO"]
    }
    return (base + "?search_query=live" +
            "&client_capabilities=" + parse.quote(json.dumps(caps, separators=(",", ":"))) +
            "&drm_parameters=" + parse.quote(json.dumps(drm, separators=(",", ":"))) +
            "&request_features=consent_supported" +
            "&lang=" + parse.quote(lang))
def fetch_player_config_1(api_url: str, retries=5):
    for attempt in range(retries):
        try:
            req = request.Request(api_url, headers=build_headers_1())
            with request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Search all spaces for player_config (not just "player" space)
            page_spaces = data.get("success", {}).get("page", {}).get("spaces", {})
            for space_name, space_val in page_spaces.items():
                for w in space_val.get("widget_wrappers", []):
                    d = w.get("widget", {}).get("data", {})
                    if "player_config" in d:
                        return d["player_config"]
            raise ValueError("player_config not found in any space")
        except Exception:
            time.sleep(1)
    raise ValueError("Failed to fetch player_config")
def extract_primary_streams_1(player_config: dict) -> list:
    streams = []
    for key in ["media_asset", "media_asset_v2", "media_assets"]:
        asset = player_config.get(key)
        if not asset:
            continue
        if isinstance(asset, dict):
            assets = [asset]
        else:
            assets = asset
        for a in assets:
            for stype in ["primary", "preview", "dash", "hls", "playback_url"]:
                item = a.get(stype)
                if not isinstance(item, dict):
                    continue
                url = item.get("content_url") or item.get("url") or item.get("playback_url")
                if url:
                    streams.append({
                        "type": stype,
                        "content_url": url,
                        "playback_tags": str(item.get("playback_tags", "")).lower()
                    })
    seen = set()
    uniq = []
    for s in streams:
        base = s["content_url"].split("?")[0]
        if base not in seen:
            seen.add(base)
            uniq.append(s)
    return uniq
def get_hdntl_token_1(url: str, retries=5) -> str:
    for attempt in range(retries):
        try:
            req = request.Request(url, headers={
                "User-Agent": HEADERS_BASE_1["User-Agent"],
                "Referer": "https://www.hotstar.com/",
                "Origin": "https://www.hotstar.com",
                "Accept": "*/*"
            })
            with request.urlopen(req, timeout=15) as resp:
                set_cookie = resp.headers.get("Set-Cookie", "")
                if "hdntl=" in set_cookie:
                    for part in set_cookie.split(","):
                        if "hdntl=" in part:
                            return part.split("hdntl=")[1].split(";")[0].strip()
        except:
            pass
        time.sleep(0.5)
    # Do NOT fallback to URL params — hdnea is URL-specific, not a valid wildcard cookie
    return ""
def append_hdntl_to_url_1(base_url: str, token: str) -> str:
    if not token:
        return base_url
    if '?' in base_url:
        base_part, query_part = base_url.split('?', 1)
        params = query_part.split('&')
        new_params = [p for p in params if not p.startswith('hdnea=') and not p.startswith('hdntl=')]
        base_url = base_part + ('?' + '&'.join(new_params) if new_params else base_part)
    if '?' in base_url:
        return base_url + '&hdnea=' + token
    else:
        return base_url + '?hdnea=' + token
def is_working_url_1(url: str) -> bool:
    try:
        req = request.Request(url, headers={
            "User-Agent": HEADERS_BASE_1["User-Agent"],
            "Referer": "https://www.hotstar.com/",
            "Origin": "https://www.hotstar.com",
        })
        with request.urlopen(req, timeout=15) as resp:
            data = resp.read(300).decode("utf-8", errors="ignore")
            if "#EXTM3U" in data or "mpegurl" in str(resp.headers.get("Content-Type", "")).lower():
                return True
    except:
        return False
    return False
def modify_bitrate_url_1(url: str) -> list:
    variants = []
    for old, new in [("master", "master_2160"), ("master", "master_1080"),
                     ("master", "master_720"), ("master", "master_high"), ("master", "master_hd")]:
        if old in url:
            variants.append(url.replace(old, new))
    variants.append(url)
    return list(dict.fromkeys(variants))
def generate_cdn_variants_1(url: str) -> list:
    """Only swap CDN host, keep path and query exactly same (no resolution suffix changes)."""
    urls = []
    parsed = urlparse(url)
    if not parsed.netloc:
        return urls
    # If current host is already in allowed list, keep it as first candidate
    if parsed.netloc in CDN_HOSTS_1:
        urls.append(url)
    # Generate variants for each allowed CDN host (same path + query)
    for host in CDN_HOSTS_1:
        new_url = parsed._replace(netloc=host).geturl()
        urls.append(new_url)   # ← NO modify_bitrate_url_1 call
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique
def detect_language_from_url_1(url: str) -> str:
    lower = url.lower()
    for code, name in LANG_DISPLAY_1.items():
        if f"/{code}/" in lower:
            return name
    return "OTHER"

def get_option5_entries(input_url: str):
    """Reusable version of option5_main that returns (lang, url, is_hdr) entries."""
    def parse_asset_id(url: str):
        parsed = urlparse(url)
        path = parsed.path if parsed.scheme else url
        segs = [s for s in path.split("/") if s]
        if len(segs) >= 4 and segs[-1] == "watch" and segs[-3] == "video":
            return segs[-4]
        if len(segs) >= 3 and segs[-1] == "watch":
            return segs[-3]
        if len(segs) >= 2 and segs[-1] in ["live", "highlights", "replay", "clips"]:
            return segs[-2]
        return segs[-1]

    asset_id = parse_asset_id(input_url)
    if not asset_id:
        return []

    slug_path_5 = extract_slug_path(input_url) or ""
    lang_codes_list_raw = [
        ("eng","ENGLISH"), ("en","ENGLISH"),
        ("hin","HINDI"), ("hi","HINDI"), ("hd","HINDI HD"),
        ("mar","MARATHI"), ("mr","MARATHI"), ("ma","MARATHI"),
        ("guj","GUJARATI"), ("gu","GUJARATI"),
        ("bih","BHOJPURI"), ("bho","BHOJPURI"), ("bh","BHOJPURI"),
        ("pan","PUNJABI"), ("pun","PUNJABI"), ("pa","PUNJABI"), ("pu","PUNJABI"),
        ("har","HARYANVI"), ("hv","HARYANVI"), ("ha","HARYANVI"),
        ("tam","TAMIL"), ("ta","TAMIL"),
        ("tel","TELUGU"), ("te","TELUGU"),
        ("kan","KANNADA"), ("kn","KANNADA"),
        ("mal","MALAYALAM"), ("ml","MALAYALAM"),
        ("ben","BENGALI"), ("bn","BENGALI"),
        ("ori","ORIYA"), ("or","ORIYA"),
    ]
    _s = set()
    lang_codes_list = [(_c,_n) for _c,_n in lang_codes_list_raw if not (_n in _s or _s.add(_n))]

    collected = []
    lock = __import__('threading').Lock()

    def fetch_one(lang_code, lang_name):
        for attempt in range(2):
            try:
                api = build_api_url_1(asset_id, lang_code, slug_path=slug_path_5)
                pc = fetch_player_config_1(api)
                streams = extract_primary_streams_1(pc)
                if not streams:
                    # Fallback: try jhs_4k_api which works better for live
                    try:
                        is_live = extract_stream_type(input_url) == "LIVE TV"
                        jhs_api = build_jhs_4k_api_url(slug_path_5, lang_code, is_live=is_live)
                        jhs_req = request.Request(jhs_api, headers=build_jhs_headers())
                        with request.urlopen(jhs_req, timeout=10) as r:
                            jhs_data = json.loads(r.read().decode("utf-8"))
                        jhs_pc = None
                        for sec in jhs_data.get("success",{}).get("page",{}).get("spaces",{}).values():
                            for w in sec.get("widget_wrappers",[]):
                                d = w.get("widget",{}).get("data",{})
                                if "player_config" in d:
                                    jhs_pc = d["player_config"]
                                    break
                            if jhs_pc: break
                        if jhs_pc:
                            streams = extract_primary_streams_1(jhs_pc) or []
                            if not streams:
                                streams = [{"type":"primary","content_url":s.get("content_url"),"playback_tags":s.get("playback_tags","")} for s in extract_jhs_fallback_only(jhs_pc) if s.get("content_url")]
                            pc = jhs_pc
                    except Exception:
                        pass
                if streams:
                    candidate_urls = []
                    for s in streams:
                        original = s.get("content_url")
                        if not original:
                            continue
                        for v in generate_cdn_variants_1(original):
                            candidate_urls.append((v, s))
                    # Remove dupes
                    seen_c = set()
                    candidate_urls = [(u,s) for u,s in candidate_urls if not (u in seen_c or seen_c.add(u))]
                    working = []
                    with ThreadPoolExecutor(max_workers=4) as ex:
                        futures = {ex.submit(is_working_url_1, u): (u, s) for u, s in candidate_urls}
                        for fut in as_completed(futures):
                            try:
                                if fut.result(timeout=15):
                                    working.append(futures[fut])
                            except:
                                continue
                    if not working:
                        working = candidate_urls
                    for u, s in working:
                        detected = detect_language_from_url_1(u)
                        if detected.upper() == lang_name.upper() or detected == "OTHER":
                            token = get_hdntl_token_1(u)
                            final = append_hdntl_to_url_1(u, token)
                            is_hdr = "hdr" in final.lower() or "hdr" in str(s.get("playback_tags", "")).lower()
                            with lock:
                                if lang_name not in [c[0] for c in collected]:
                                    collected.append((lang_name, final, is_hdr))
                            return
            except Exception:
                time.sleep(1)
                continue

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_one, code, name) for code, name in lang_codes_list]
        for f in as_completed(futures):
            try:
                f.result(timeout=50)
            except:
                pass

    return collected
    print(f"{RED}No working primary streams found for any language.{RESET}")
    return
    title, match_no = extract_match_title(input_url)
    stream_type = extract_stream_type(input_url)
    logo_url = ""
    try:
        api = build_api_url_1(asset_id, "eng", slug_path=slug_path_5)
        pc = fetch_player_config_1(api)
        img = pc.get("expanded_content_poster", {}).get("image", {}).get("src") or pc.get("cast_image", {}).get("src")
        if img:
            logo_url = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
    except:
        pass
    print(f"\n{BOLD_RED}LOGO{RESET}")
    if logo_url:
        print(logo_url)
    if match_no:
        print(f"{GREEN}{match_no}{RESET}")
    print(f"{BOLD_GREEN}{title}{RESET}")
    print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
    for lang, url, is_hdr in collected:
        hdr_tag = " HDR" if is_hdr else ""
        print(f"{BOLD_CYAN}{lang}{hdr_tag}{RESET}")
        print(f"{GREEN}{url}{RESET}")
    if create_m3u:
        offer_m3u_creation(collected, title, match_no, stream_type, logo_url)
    if os.name == "nt":
        pass

# ===================== OPTION 7 (DRM OTT NAVIGATOR FORMAT) =====================
def fetch_drm_info_for_slug(slug_path: str) -> tuple:
    """Fetch DRM MPD streams + keys. Returns (drm_entries, global_license, global_keys, player_config)."""
    player_config = None
    # Primary: widevine-only DRM API
    try:
        api_url = build_drm_api_url(slug_path, "eng")
        req = request.Request(api_url, headers=build_headers())
        with request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for sec in data.get("success", {}).get("page", {}).get("spaces", {}).values():
            for w in sec.get("widget_wrappers", []):
                d = w.get("widget", {}).get("data", {})
                if "player_config" in d:
                    player_config = d["player_config"]
                    break
            if player_config:
                break
    except Exception:
        pass
    # Fallback: 4K API which also returns widevine MPD for most content
    if not player_config:
        try:
            api_url2 = build_api_url(slug_path, "eng", "1")
            req2 = request.Request(api_url2, headers=build_headers())
            with request.urlopen(req2, timeout=12) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
            for sec in data2.get("success", {}).get("page", {}).get("spaces", {}).values():
                for w in sec.get("widget_wrappers", []):
                    d = w.get("widget", {}).get("data", {})
                    if "player_config" in d:
                        player_config = d["player_config"]
                        break
                if player_config:
                    break
        except Exception:
            pass
    if not player_config:
        return [], "", [], None
    drm_streams = extract_drm_info(player_config)
    if not drm_streams:
        return [], "", [], player_config
    global_license = ""
    for s in drm_streams:
        if s.get("license_url"):
            global_license = s["license_url"]
            break
    global_keys = []
    first_mpd = drm_streams[0]["mpd_url"] if drm_streams else ""
    if first_mpd and global_license:
        try:
            mpd_info0 = fetch_mpd_pssh(first_mpd)
            if mpd_info0 and mpd_info0.get("key_ids"):
                ck = try_clearkey_json(mpd_info0["key_ids"], global_license)
                if ck:
                    global_keys = ck
                elif mpd_info0.get("pssh"):
                    wv = fetch_widevine_keys(mpd_info0["pssh"], global_license)
                    if wv and not any(l.startswith("❌") for l in wv):
                        global_keys = wv
        except Exception:
            pass
    return drm_streams, global_license, global_keys, player_config

def option7_main(slug_path: str, title: str, match_no: str, stream_type: str):
    """Option 7: DRM MPD plain links — display and save raw MPD URLs with detected language labels."""
    print(f"\n{BOLD_RED}LOGO{RESET}")
    logo_url_7 = ""
    try:
        api_url_logo = build_drm_api_url(slug_path, "eng")
        req_logo = request.Request(api_url_logo, headers=build_headers())
        with request.urlopen(req_logo, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
        for sec in d.get("success", {}).get("page", {}).get("spaces", {}).values():
            for w in sec.get("widget_wrappers", []):
                pc = w.get("widget", {}).get("data", {}).get("player_config")
                if pc:
                    img = pc.get("expanded_content_poster", {}).get("image", {}).get("src") or pc.get("cast_image", {}).get("src")
                    if img:
                        logo_url_7 = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                        print(logo_url_7)
                    break
    except Exception:
        pass
    if match_no:
        print(f"{GREEN}{match_no}{RESET}")
    print(f"{BOLD_GREEN}{title}{RESET}")
    print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
    print(f"{DARK_MAGENTA}Fetching DRM streams..{RESET}")
    drm_streams, global_license, global_keys, _ = fetch_drm_info_for_slug(slug_path)
    if not drm_streams:
        print(f"{RED}NO DRM STREAM FOUND ❌{RESET}")
        return
    key_str_global7 = ",".join(global_keys) if global_keys else global_license
    seen_mpds = set()
    ordered_streams = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
    m3u_lines = ["#EXTM3U", f"# Title: {title}", f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for stream in ordered_streams:
        mpd_url = stream["mpd_url"]
        mpd_base = mpd_url.split("?")[0]
        if mpd_base in seen_mpds:
            continue
        seen_mpds.add(mpd_base)
        license_url = stream.get("license_url") or global_license
        variant = stream.get("variant", "")
        # Try per-MPD keys
        key_str = key_str_global7
        try:
            mpd_info = fetch_mpd_pssh(mpd_url)
            if mpd_info and mpd_info.get("key_ids") and license_url:
                ck = try_clearkey_json(mpd_info["key_ids"], license_url)
                if ck:
                    key_str = ",".join(ck)
                elif mpd_info.get("pssh"):
                    wv = fetch_widevine_keys(mpd_info["pssh"], license_url)
                    if wv and not any(l.startswith("❌") for l in wv):
                        key_str = ",".join(wv)
        except Exception:
            pass
        avail_langs = extract_mpd_languages(mpd_url)
        if not avail_langs:
            avail_langs = [("unk", "STREAM")]
        lang_label = ", ".join(n for _, n in avail_langs)
        ott_url = build_ott_drm_url(mpd_url, key_str)
        print(f"\n{BOLD_GREEN}{lang_label} {variant}{RESET}")
        print(f"{GREEN}{ott_url}{RESET}")
        for _, lang_name in avail_langs:
            entry_title = f"{lang_name} {variant}"
            m3u_lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_url_7}" group-title="{title}", {entry_title}')
            m3u_lines.append(ott_url)
            m3u_lines.append("")
    # Ask to save
    if len(m3u_lines) > 4:
        m3u_fname = f"hotstar_ott_{title.replace(' ','_')}.m3u"
        ans = input(f"\n{BOLD_CYAN}Save M3U? (y/n): {RESET}").strip().lower()
        if ans == "y":
            print(f"{YELLOW}Paste hdntl cookie (TamperDev/browser extension) or press Enter to skip:{RESET}")
            print(f"{GRAY}Format: hdntl=exp=...~hmac=...{RESET}")
            _raw_ck = input(f"{BOLD_CYAN}Cookie : {RESET}").strip()
            _hdntl_ck = ""
            if _raw_ck:
                if _raw_ck.startswith("hdntl="):
                    _hdntl_ck = _raw_ck[len("hdntl="):]
                else:
                    import re as _rck
                    _m2 = _rck.search(r'hdntl=([^\s;&|]+)', _raw_ck)
                    _hdntl_ck = _m2.group(1) if _m2 else _raw_ck
            if _hdntl_ck:
                _new_lines = []
                for _ln in m3u_lines:
                    if _ln.startswith('#EXTHTTP:'):
                        _ln = '#EXTHTTP:{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","Cookie":"hdntl=' + _hdntl_ck + '"}' 
                    _new_lines.append(_ln)
                m3u_lines = _new_lines
            try:
                with open(m3u_fname, "w", encoding="utf-8") as fw:
                    fw.write("\n".join(m3u_lines))
                total = len([l for l in m3u_lines if l.startswith("#EXTINF")])
                print(f"{GREEN}✓ M3U saved: {m3u_fname} ({total} entries){RESET}")
            except Exception as e:
                print(f"{RED}Failed to write M3U: {e}{RESET}")
    print()

# ===================== M3U FUNCTIONS =====================
def extract_logo_from_url(url: str) -> str:
    slug_path = extract_slug_path(url)
    if not slug_path:
        return ""
    try:
        api_url = build_api_url(slug_path, "eng", "2")
        req = request.Request(api_url, headers=build_headers())
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        player_config = None
        page_spaces = data.get("success", {}).get("page", {}).get("spaces", {})
        for s in page_spaces:
            for w in page_spaces[s].get("widget_wrappers", []):
                if "player_config" in w.get("widget", {}).get("data", {}):
                    player_config = w["widget"]["data"]["player_config"]
                    break
            if player_config:
                break
        if player_config:
            img = player_config.get("expanded_content_poster", {}).get("image", {}).get("src") or player_config.get("cast_image", {}).get("src")
            if img:
                return f"https://img10.hotstar.com/image/upload/f_auto/{img}"
    except:
        pass
    return ""

def create_m3u_file(entries: List[Tuple[str, str, bool]], title: str, match_no: str,
                    stream_type: str, filename: str = "hotstar_live.m3u", logo_url: str = "", hdntl_cookie: str = "") -> bool:
    if not entries:
        print(f"{RED}No stream entries to save.{RESET}")
        return False
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# Playlist generated by Hotstar Extractor\n")
            f.write(f"# Title: {title}\n")
            if match_no:
                f.write(f"# Match: {match_no}\n")
            f.write(f"# Type: {stream_type}\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            import hashlib
            for entry in entries:
                try:
                    if len(entry) == 3:
                        lang, url, is_hdr = entry
                    else:
                        lang, url = entry[0], entry[1]
                        is_hdr = False
                except Exception:
                    continue
                tvg_id = str(int(hashlib.md5(url.encode()).hexdigest(), 16) % 9999999999)
                # Build smart label:
                # Label: LANG SDR / LANG HDR / LANG
                lang_upper = lang.upper()
                if "SDR" in lang_upper:
                    base_lang = lang.replace(" SDR", "").replace(" sdr", "").strip()
                    channel_label = f"{base_lang} SDR"
                elif is_hdr:
                    channel_label = f"{lang} HDR"
                else:
                    channel_label = f"{lang}"
                if logo_url:
                    f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{lang}" tvg-logo="{logo_url}" group-title="{title}", {channel_label}\n')
                else:
                    f.write(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{lang}" group-title="{title}", {channel_label}\n')
                _exthttp = '{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/"' + (f',"Cookie":"hdntl={hdntl_cookie}"' if hdntl_cookie else "") + '}'
                f.write(f'#EXTHTTP:{_exthttp}\n')
                f.write('#EXTVLCOPT:http-extra-headers=Origin: https://www.hotstar.com\n')
                f.write('#EXTVLCOPT:http-referrer=https://www.hotstar.com/\n')
                f.write(f"{url}\n")
        print(f"{GREEN}✓ M3U playlist saved as: {filename}{RESET}")
        return True
    except Exception as e:
        print(f"{RED}Failed to create M3U: {e}{RESET}")
        return False

def offer_m3u_creation(entries: List[Tuple[str, str, bool]], title: str,
                       match_no: str, stream_type: str, logo_url: str = "", auto_hdntl: str = ""):
    if not entries:
        return
    ans = input(f"\n{BOLD_CYAN}Save M3U? (y/n): {RESET}").strip().lower()
    if ans == 'y':
        default_name = f"hotstar_{title.replace(' ', '_')}.m3u"
        hdntl_cookie = auto_hdntl  # pre-filled from auto-extract
        if auto_hdntl:
            print(f"{GREEN}✓ Cookie auto-extracted, press Enter to use it or paste a new one:{RESET}")
            print(f"{GRAY}hdntl={auto_hdntl[:60]}...{RESET}")
        else:
            print(f"{YELLOW}Paste hdntl cookie (TamperDev/browser extension) or press Enter to skip:{RESET}")
            print(f"{GRAY}Format: hdntl=exp=...~hmac=...{RESET}")
        raw_cookie = input(f"{BOLD_CYAN}Cookie : {RESET}").strip()
        if raw_cookie:
            if raw_cookie.startswith("hdntl="):
                hdntl_cookie = raw_cookie[len("hdntl="):]
            else:
                import re as _rc
                _m = _rc.search(r'hdntl=([^\s;&|]+)', raw_cookie)
                hdntl_cookie = _m.group(1) if _m else raw_cookie
        create_m3u_file(entries, title, match_no, stream_type, default_name, logo_url, hdntl_cookie=hdntl_cookie)

def git_push_m3u(filename: str, message: str = "Auto update M3U playlist") -> bool:
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        print(f"{YELLOW}⚠ Git not installed. Skipping push.{RESET}")
        return False
    if not os.path.isdir(".git"):
        print(f"{YELLOW}⚠ Not a git repository (no .git folder). Skipping push.{RESET}")
        print(f"{YELLOW}   To enable auto-push, run: git init && git remote add origin <your-repo-url>{RESET}")
        return False
    try:
        subprocess.run(["git", "add", filename], check=True, capture_output=True)
        has_changes = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], capture_output=True
        ).returncode != 0
        if not has_changes:
            print(f"{YELLOW}⚠ No changes to commit for {filename}. Skipping push.{RESET}")
            return True
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
        print(f"{GREEN}✓ Committed changes for {filename}{RESET}")
        pull_result = subprocess.run(
            ["git", "pull", "origin", "main", "--no-rebase"],
            capture_output=True, text=True
        )
        if pull_result.returncode != 0:
            subprocess.run(["git", "merge", "--abort"], capture_output=True)
            subprocess.run(["git", "rebase", "--abort"], capture_output=True)
            print(f"{YELLOW}⚠ Git pull failed, but attempting force push? No, will retry later.{RESET}")
            return False
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print(f"{GREEN}✓ Pushed to GitHub successfully{RESET}")
        return True
    except subprocess.CalledProcessError as e:
        if "push" in str(e.cmd) and e.returncode != 0:
            try:
                subprocess.run(["git", "push", "--force-with-lease"], check=True, capture_output=True)
                print(f"{GREEN}✓ Force-pushed to GitHub successfully (resolved divergence){RESET}")
                return True
            except:
                print(f"{RED}Git push failed even after force-with-lease: {e}{RESET}")
        else:
            print(f"{RED}Git operation failed: {e}{RESET}")
        return False

# ===================== CLOUDFLARE WORKERS PUSH =====================
CF_CONFIG_FILE = "cf_config.json"
def load_cf_config():
    try:
        with open(CF_CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return None
def save_cf_config(worker_url, api_token):
    with open(CF_CONFIG_FILE, "w") as f:
        json.dump({"worker_url": worker_url, "api_token": api_token}, f)
def push_to_cloudflare(filename: str, worker_url: str, api_token: str, retries: int = 3) -> bool:
    import urllib.error
    try:
        with open(filename, "rb") as f:
            file_content = f.read()
    except Exception as e:
        print(f"{RED}Failed to read M3U file: {e}{RESET}")
        return False
    for attempt in range(1, retries + 1):
        try:
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "text/plain",
                "X-File-Name": os.path.basename(filename),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Length": str(len(file_content)),
            }
            req = request.Request(worker_url, data=file_content, headers=headers, method="PUT")
            try:
                with request.urlopen(req, timeout=30) as resp:
                    status = resp.status
                    body = resp.read().decode("utf-8", errors="replace").strip()
                    if status == 200:
                        print(f"{GREEN}✓ Uploaded to Cloudflare Workers (attempt {attempt}){RESET}")
                        if body:
                            print(f"{CYAN}  CF Response: {body[:200]}{RESET}")
                        return True
                    else:
                        print(f"{RED}✗ Cloudflare returned HTTP {status} (attempt {attempt}){RESET}")
                        if body:
                            print(f"{YELLOW}  CF Response: {body[:300]}{RESET}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace").strip()
                print(f"{RED}✗ Cloudflare HTTP {e.code} error (attempt {attempt}): {e.reason}{RESET}")
                if body:
                    print(f"{YELLOW}  CF Error body: {body[:300]}{RESET}")
                if e.code in [401, 403]:
                    print(f"{RED}  → Check your API Bearer Token in cf_config.json{RESET}")
                    return False  # Don't retry auth errors
            except urllib.error.URLError as e:
                print(f"{RED}✗ Network error (attempt {attempt}): {e.reason}{RESET}")
        except Exception as e:
            print(f"{RED}✗ Cloudflare push attempt {attempt}/{retries} failed: {e}{RESET}")
        if attempt < retries:
            print(f"{YELLOW}  Retrying in 3 seconds...{RESET}")
            time.sleep(3)
    print(f"{RED}✗ All {retries} Cloudflare push attempts failed.{RESET}")
    print(f"{YELLOW}  Tip: Check Worker URL and Bearer Token in cf_config.json{RESET}")
    return False

# ===================== OPTION 8 (LIVE TV CHANNELS — NS PLAYER FORMAT) =====================
def option8_direct_mpd(slug_path: str, title: str, match_no: str, stream_type: str, input_url: str = ""):
    """Option 8: Fetch live TV MPD + hdntl cookie + DRM keys → NS Player pipe-URL."""
    print(f"\n{BOLD_GREEN}=== AUTO MPD + COOKIE FINDER (NS PLAYER FORMAT) ==={RESET}")

    # ── fetch logo ────────────────────────────────────────────────────
    logo_url = ""
    if input_url:
        try:
            logo_url = extract_logo_from_url(input_url)
        except Exception:
            pass
    if not logo_url:
        try:
            api_url_logo = build_drm_api_url(slug_path, "eng")
            req_logo = request.Request(api_url_logo, headers=build_headers())
            with request.urlopen(req_logo, timeout=10) as r:
                d = json.loads(r.read().decode("utf-8"))
            for sec in d.get("success", {}).get("page", {}).get("spaces", {}).values():
                for w in sec.get("widget_wrappers", []):
                    pc = w.get("widget", {}).get("data", {}).get("player_config")
                    if pc:
                        img = (pc.get("expanded_content_poster", {}).get("image", {}).get("src")
                               or pc.get("cast_image", {}).get("src"))
                        if img:
                            logo_url = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                        break
        except Exception:
            pass

    print(f"\n{BOLD_RED}LOGO{RESET}")
    if logo_url:
        print(f"{GREEN}{logo_url}{RESET}")
    if match_no:
        print(f"{GREEN}{match_no}{RESET}")
    print(f"{BOLD_GREEN}{title}{RESET}")
    print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
    print(f"{DARK_MAGENTA}Fetching DRM streams...{RESET}")

    drm_streams, global_license, global_keys, _ = fetch_drm_info_for_slug(slug_path)
    if not drm_streams:
        print(f"{RED}No DRM streams found ❌{RESET}")
        return

    key_str_global = ",".join(global_keys) if global_keys else (global_license or "")
    seen_mpds = set()
    ordered = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
    results = []  # list of (variant, mpd_base, hdntl_val, key_str)

    for stream in ordered:
        mpd_url = stream["mpd_url"]
        mpd_base = mpd_url.split("?")[0]
        if mpd_base in seen_mpds:
            continue
        seen_mpds.add(mpd_base)
        variant     = stream.get("variant", "PRIMARY")
        license_url = stream.get("license_url") or global_license

        # ── auto-detect DRM keys ──────────────────────────────────────
        key_str = key_str_global
        try:
            mpd_info = fetch_mpd_pssh(mpd_url)
            if mpd_info and mpd_info.get("key_ids") and license_url:
                ck = try_clearkey_json(mpd_info["key_ids"], license_url)
                if ck:
                    key_str = ",".join(ck)
                elif mpd_info.get("pssh"):
                    wv = fetch_widevine_keys(mpd_info["pssh"], license_url)
                    if wv and not any(l.startswith("❌") for l in wv):
                        key_str = ",".join(wv)
        except Exception:
            pass

        # ── auto-fetch hdntl cookie ───────────────────────────────────
        hdntl_val = ""
        try:
            hdntl_val = get_hdntl_token_1(mpd_url)
        except Exception:
            pass
        if not hdntl_val:
            hdntl_val = extract_hdntl(mpd_url)

        results.append((variant, mpd_base, hdntl_val, key_str))

    if not results:
        print(f"{RED}Could not retrieve any stream.{RESET}")
        return

    # ── print NS Player URLs (clean, no extra sections) ──────────────
    for variant, mpd_base, hdntl_val, key_str in results:
        ott_url = build_ott_drm_url_direct(mpd_base, key_str, hdntl_val)
        print(f"\n{GREEN}{ott_url}{RESET}")

    # ── save M3U ──────────────────────────────────────────────────────
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', title.lower())[:40]
    ans = input(f"\n{BOLD_CYAN}Save M3U? (y/n): {RESET}").strip().lower()
    if ans != "y":
        return
    print(f"{YELLOW}Paste hdntl cookie (TamperDev/browser extension) or press Enter to skip:{RESET}")
    print(f"{GRAY}Format: hdntl=exp=...~hmac=...{RESET}")
    _raw_ck8 = input(f"{BOLD_CYAN}Cookie : {RESET}").strip()
    _hdntl_ck8 = ""
    if _raw_ck8:
        if _raw_ck8.startswith("hdntl="):
            _hdntl_ck8 = _raw_ck8[len("hdntl="):]
        else:
            import re as _rck8
            _m8 = _rck8.search(r'hdntl=([^\s;&|]+)', _raw_ck8)
            _hdntl_ck8 = _m8.group(1) if _m8 else _raw_ck8

    filename = input(f"Filename (default: {safe_name}.m3u): ").strip()
    if not filename:
        filename = f"{safe_name}.m3u"

    m3u_lines = [
        "#EXTM3U",
        f"# Title: {title}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for variant, mpd_base, hdntl_val, key_str in results:
        entry_title = f"{title} [{variant}]"
        ott_url = build_ott_drm_url_direct(mpd_base, key_str, hdntl_val)
        m3u_lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_url}" group-title="{title}", {entry_title}')
        _ck8_hdr = ('#EXTHTTP:{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","Cookie":"hdntl=' + _hdntl_ck8 + '"}'
                    if _hdntl_ck8 else '#EXTHTTP:{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/"}')
        m3u_lines.append(_ck8_hdr)
        m3u_lines.append(ott_url)
        m3u_lines.append("")

    try:
        with open(filename, "w", encoding="utf-8") as fw:
            fw.write("\n".join(m3u_lines))
        total = len([l for l in m3u_lines if l.startswith("#EXTINF")])
        print(f"{GREEN}✓ M3U saved: {filename} ({total} entries){RESET}")
    except Exception as e:
        print(f"{RED}Failed to save M3U: {e}{RESET}")


def fetch_existing_m3u(filename: str, cf_worker_url: str = None) -> list:
    """Read existing M3U from local file or fetch from Cloudflare.
    Returns list of (extinf_line, url, tvg_name) tuples.
    Skips #EXTHTTP/#EXTVLCOPT lines to find real URL."""
    import re as _re
    lines_src = None
    if os.path.isfile(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines_src = f.readlines()
        except Exception:
            pass
    if lines_src is None and cf_worker_url:
        try:
            _base = cf_worker_url.rstrip("/")
            if _base.endswith("/upload"):
                _base = _base[:-7]
            _get_url = f"{_base}/{os.path.basename(filename)}"
            _req = request.Request(_get_url, headers={"User-Agent": "Mozilla/5.0"})
            with request.urlopen(_req, timeout=10) as _r:
                lines_src = _r.read().decode("utf-8").splitlines(keepends=True)
            print(f"{GREEN}  ✓ Fetched existing file from Cloudflare{RESET}")
        except Exception as _e:
            print(f"{YELLOW}  ⚠ Could not fetch from CF ({_e}), starting fresh{RESET}")
    if not lines_src:
        return []
    entries = []
    seen_urls = set()
    seen_names = set()
    i = 0
    while i < len(lines_src):
        ln = lines_src[i].strip()
        if ln.startswith("#EXTINF"):
            extinf = ln
            nm = _re.search(r'tvg-name="([^"]+)"', extinf)
            tvg_name = nm.group(1).strip() if nm else ""
            # Fallback: use display name (after last comma) if tvg-name missing
            if not tvg_name:
                dn = _re.search(r',\s*(.+)$', extinf)
                tvg_name = dn.group(1).strip() if dn else ""
            j = i + 1
            found_url = ""
            while j < len(lines_src):
                nxt = lines_src[j].strip()
                if nxt and not nxt.startswith("#"):
                    found_url = nxt
                    break
                j += 1
            base = found_url.split("?")[0]
            # Deduplicate by both URL base AND tvg_name to prevent same-name duplicates
            if found_url and base not in seen_urls and tvg_name not in seen_names:
                entries.append((extinf, found_url, tvg_name))
                seen_urls.add(base)
                if tvg_name:
                    seen_names.add(tvg_name)
            i = j + 1
            continue
        i += 1
    return entries

# ===================== AUTO-UPDATE MODE =====================
def auto_update_mode(input_url: str):
    print(f"{BOLD_GREEN}=== AUTO-UPDATE MODE ==={RESET}")
    url = input_url
    print(f"{CYAN}Fetching logo image...{RESET}")
    logo_url = extract_logo_from_url(url)
    if logo_url:
        print(f"{GREEN}✓ Logo found: {logo_url}{RESET}")
    else:
        print(f"{YELLOW}⚠ No logo found, will create M3U without tvg-logo.{RESET}")
    print(f"{BOLD_YELLOW}Available qualities:{RESET}")
    print(f"{BOLD_GREEN}{{1}} NORMAL 4K{RESET}")
    print(f"{BOLD_BLUE}{{2}} NORMAL FHD{RESET}")
    print(f"{BOLD_YELLOW}{{3}} ADS-FREE JHS FHD{RESET}")
    print(f"{BOLD_MAGENTA}{{4}} JHS 4K{RESET}")
    print(f"{BOLD_CYAN}{{5}} ADS-FREE 4K PRIMARY{RESET}")
    print(f"{BOLD_RED}{{6}} DRM MPD + CLEARKEY / PSSH{RESET}")
    print(f"{BOLD_WHITE}{{7}} DRM NS PLAYER FORMAT{RESET}")
    print(f"{BOLD_GREEN}{{8}} DRM-TV{RESET}")
    print(f"{BOLD_YELLOW}{{9}} JHS ALL CHANNELS{RESET}")
    quality_raw = input(f"{BOLD_CYAN}Choose quality (1-9 or multiple like 1,2 or 1.2): {RESET}").strip()
    # Support comma or dot separated multiple choices e.g. "1,2" or "1.2"
    quality_list = [q.strip() for q in quality_raw.replace(".", ",").split(",") if q.strip() in ["1","2","3","4","5","6","7","8","9"]]
    if not quality_list:
        print(f"{RED}Invalid choice. Defaulting to 2.{RESET}")
        quality_list = ["2"]
    quality = quality_list[0]  # primary quality (used for single-quality paths)
    if len(quality_list) > 1:
        print(f"{GREEN}✓ Multi-quality mode: {', '.join(quality_list)}{RESET}")
    interval = input(f"Update interval in minutes (default 25): ").strip()
    interval = int(interval) if interval.isdigit() else 25
    filename = input(f"M3U filename (default: hotstar_auto.m3u): ").strip()
    if not filename:
        filename = "hotstar_auto.m3u"
    print(f"\n{BOLD_CYAN}Auto-push destination:{RESET}")
    print(f"  {BOLD_GREEN}1{RESET}) GitHub only")
    print(f"  {BOLD_YELLOW}2{RESET}) Cloudflare Workers only")
    print(f"  {BOLD_MAGENTA}3{RESET}) Both GitHub + Cloudflare")
    print(f"  {BOLD_WHITE}n{RESET}) No push (local only)")
    push_choice = input(f"{BOLD_CYAN}Choose (1/2/3/n): {RESET}").strip().lower()
    git_push_enabled = push_choice in ["1", "3"]
    use_cf = push_choice in ["2", "3"]
    cf_worker_url = None
    cf_api_token = None
    replace_m3u = True  # default: replace
    if use_cf:
        config = load_cf_config()
        # Validate saved config - worker_url must start with http and token must exist
        config_valid = (
            config and
            config.get("worker_url", "").startswith("http") and
            config.get("api_token", "")
        )
        if config_valid:
            print(f"{GREEN}✓ Loaded Cloudflare config from {CF_CONFIG_FILE}{RESET}")
            print(f"{CYAN}  Worker URL: {config['worker_url']}{RESET}")
            use_existing = input(f"Use existing config? (y/n): ").strip().lower()
            if use_existing == 'y':
                cf_worker_url = config['worker_url']
                cf_api_token = config['api_token']
                print(f"{GREEN}✓ Using saved Worker URL and token{RESET}")
                _rep = input(f"{BOLD_CYAN}Replace Your M3U File? (y/n): {RESET}").strip().lower()
                replace_m3u = (_rep == 'y')
                if replace_m3u:
                    print(f"{YELLOW}  → Replace mode: full rewrite each cycle{RESET}")
                else:
                    print(f"{GREEN}  → Append mode: existing channels kept, tokens refreshed{RESET}")
            else:
                cf_worker_url = input("Enter Cloudflare Worker URL (https://...): ").strip()
                cf_api_token = input("Enter API Bearer Token: ").strip()
                save_cf_config(cf_worker_url, cf_api_token)
        else:
            if config and not config_valid:
                print(f"{YELLOW}⚠ Saved config is invalid (bad URL or missing token). Re-entering.{RESET}")
            cf_worker_url = input("Enter Cloudflare Worker URL (https://...): ").strip()
            cf_api_token = input("Enter API Bearer Token: ").strip()
            save_cf_config(cf_worker_url, cf_api_token)
        # Final validation
        if not cf_worker_url or not cf_worker_url.startswith("http"):
            print(f"{RED}✗ Invalid Worker URL! Must start with https://. Disabling CF push.{RESET}")
            use_cf = False
        elif not cf_api_token:
            print(f"{RED}✗ API token is empty! Disabling CF push.{RESET}")
            use_cf = False
        else:
            print(f"{GREEN}✓ Cloudflare Workers configured{RESET}")
            print(f"{CYAN}  URL: {cf_worker_url}{RESET}")
    if git_push_enabled:
        if not use_cf:
            _rep = input(f"{BOLD_CYAN}Replace Your M3U File? (y/n): {RESET}").strip().lower()
            replace_m3u = (_rep == 'y')
            if replace_m3u:
                print(f"{YELLOW}  → Replace mode: full rewrite each cycle{RESET}")
            else:
                print(f"{GREEN}  → Append mode: existing channels kept, tokens refreshed{RESET}")
        print(f"{GREEN}✓ GitHub auto-push enabled{RESET}")
    if not git_push_enabled and not use_cf:
        print(f"{YELLOW}No push destination. M3U will be saved locally only.{RESET}")
    slug_path = extract_slug_path(url)
    if not slug_path:
        print(f"{RED}Invalid URL!{RESET}")
        return

    def add_hdr_sdr_variants(entries):
        """For ALL languages: if HDR stream found, also add SDR variant."""
        final = []
        seen_urls = set()
        for lang, url, is_hdr in entries:
            if url not in seen_urls:
                seen_urls.add(url)
                final.append((lang, url, is_hdr))
            # Add SDR variant for ALL languages that have HDR
            if is_hdr:
                sdr_url = url.replace("hdr", "sdr").replace("HDR", "sdr").replace("Hdr", "sdr")
                if sdr_url != url and sdr_url not in seen_urls:
                    seen_urls.add(sdr_url)
                    final.append((f"{lang} SDR", sdr_url, False))
        return final

    def get_entries(quality, url, slug_path):
        def collect_option9_entries(url):
            _asset_id = parse_asset_id_4kads(url)
            _slug_path = extract_slug_path(url) or ""
            if not _asset_id:
                return []
            _lang_groups = [
                ("eng", ["eng"], "ENGLISH"),
                ("hin", ["hin", "hi", "hd"], "HINDI"),
                ("mar", ["mar", "mr", "ma"], "MARATHI"),
                ("guj", ["guj", "gu"], "GUJARATI"),
                ("bih", ["bih", "bho", "bh"], "BHOJPURI"),
                ("pan", ["pan", "pun", "pa", "pu"], "PUNJABI"),
                ("har", ["har", "hv", "ha"], "HARYANVI"),
                ("tam", ["tam", "ta"], "TAMIL"),
                ("tel", ["tel", "te"], "TELUGU"),
                ("kan", ["kan", "kn"], "KANNADA"),
                ("mal", ["mal", "ml"], "MALAYALAM"),
                ("ben", ["ben", "bn"], "BENGALI"),
            ]
            _collected = []
            _seen_langs = set()
            _lock = __import__("threading").Lock()

            def _fetch_one(primary, codes, lang_name):
                for lang_code in codes:
                    for attempt in range(3):
                        try:
                            api_url = build_api_url_4kads(_asset_id, lang_code, slug_path=_slug_path)
                            pc = fetch_player_config_4kads(api_url)
                            streams = extract_all_streams_4kads(pc)
                            if not streams:
                                continue
                            candidates = []
                            for s in streams:
                                orig = str(s.get("content_url", ""))
                                if not orig or str(s.get("type", "")).lower() != "primary":
                                    continue
                                for v in generate_cdn_variants_1(orig):
                                    candidates.append((v, s))
                            if not candidates:
                                continue
                            lang_candidates = []
                            for raw_url, s in candidates:
                                path_parts = set(raw_url.split("?")[0].replace("https://","").replace("http://","").split("/"))
                                if lang_code in path_parts:
                                    lang_candidates.append((raw_url, s))
                            if not lang_candidates:
                                lang_candidates = candidates
                            for raw_url, s in lang_candidates:
                                try:
                                    if not is_working_url_1(raw_url):
                                        continue
                                    token = get_hdntl_token_1(raw_url)
                                    final_url = append_hdntl_to_url_1(raw_url, token)
                                    is_hdr = "hdr" in raw_url.lower()
                                    label = f"{lang_name} 4K ADSFREE"
                                    with _lock:
                                        if lang_name not in _seen_langs:
                                            _seen_langs.add(lang_name)
                                            _collected.append((label, final_url, is_hdr))
                                    return
                                except Exception:
                                    continue
                        except Exception:
                            if attempt < 2:
                                time.sleep(1)
                            continue

            _LANG_ORDER = [
                "HINDI","ENGLISH","TELUGU","TAMIL","KANNADA","MALAYALAM",
                "BENGALI","MARATHI","GUJARATI","PUNJABI","BHOJPURI","HARYANVI",
            ]

            with ThreadPoolExecutor(max_workers=5) as pool:
                futs = [pool.submit(_fetch_one, p, codes, name) for p, codes, name in _lang_groups]
                for f in as_completed(futs, timeout=300):
                    try:
                        f.result()
                    except Exception:
                        pass
            _collected.sort(key=lambda x: _LANG_ORDER.index(x[0].split()[0]) if x[0].split()[0] in _LANG_ORDER else 99)
            return _collected

        if quality == "1":
            entries = []
            seen_bases_q1 = set()
            for lang_code, lang_name in LANGUAGES.items():
                try:
                    res = fetch_lang_stream(lang_code, lang_name, slug_path, url, quality)
                    if not res:
                        continue
                    player_config = res["player_config"]
                    is_hdr = res.get("is_hdr", False)
                    streams_4k = extract_4k_streams(player_config)
                    if streams_4k:
                        url_4k = streams_4k[0]["url"]
                        base_4k = url_4k.split("?")[0]
                        if base_4k in seen_bases_q1:
                            continue
                        seen_bases_q1.add(base_4k)
                        if not is_hdr and ("hdr" in url_4k.lower() or "hdr" in str(streams_4k[0].get("playback_tags", "")).lower()):
                            is_hdr = True
                        entries.append((res["lang_name"], url_4k, is_hdr))
                    else:
                        base_s = res["stream"].split("?")[0]
                        if base_s in seen_bases_q1:
                            continue
                        seen_bases_q1.add(base_s)
                        entries.append((res["lang_name"], res["stream"], is_hdr))
                except Exception:
                    continue
            return add_hdr_sdr_variants(entries)
        elif quality == "2":
            entries = []
            seen_bases_q2 = set()
            for lang_code, lang_name in LANGUAGES.items():
                try:
                    res = fetch_lang_stream(lang_code, lang_name, slug_path, url, quality)
                    if res:
                        base_s = res["stream"].split("?")[0]
                        if base_s in seen_bases_q2:
                            continue
                        seen_bases_q2.add(base_s)
                        entries.append((res["lang_name"], res["stream"], res.get("is_hdr", False)))
                except:
                    continue
            return add_hdr_sdr_variants(entries)
        elif quality == "3":
            def collect_jhs_entries(url, slug_path):
                LANG_CODES = [
                    ("eng","ENGLISH"), ("en","ENGLISH"),
                    ("hin","HINDI"), ("hi","HINDI"), ("hd","HINDI HD"),
                    ("mar","MARATHI"), ("mr","MARATHI"), ("ma","MARATHI"),
                    ("guj","GUJARATI"), ("gu","GUJARATI"),
                    ("bih","BHOJPURI"), ("bho","BHOJPURI"), ("bh","BHOJPURI"),
                    ("pan","PUNJABI"), ("pun","PUNJABI"), ("pa","PUNJABI"), ("pu","PUNJABI"),
                    ("har","HARYANVI"), ("hv","HARYANVI"), ("ha","HARYANVI"),
                    ("tam","TAMIL"), ("ta","TAMIL"),
                    ("tel","TELUGU"), ("te","TELUGU"),
                    ("kan","KANNADA"), ("kn","KANNADA"),
                    ("mal","MALAYALAM"), ("ml","MALAYALAM"),
                    ("ben","BENGALI"), ("bn","BENGALI"),
                    ("ori","ORIYA"), ("or","ORIYA"),
                ]
                _seen_names = set()
                _unique_codes = []
                for _code, _name in LANG_CODES:
                    if _name not in _seen_names:
                        _seen_names.add(_name)
                        _unique_codes.append((_code, _name))
                LANG_CODES = _unique_codes
                FALLBACKS = {
                    "eng":["en"], "hin":["hi","hd"], "mar":["mr","ma"],
                    "guj":["gu"], "bih":["bho","bh"], "pan":["pun","pa","pu"],
                    "har":["hv","ha"], "tam":["ta"], "tel":["te"],
                    "kan":["kn"], "mal":["ml"], "ben":["bn"], "ori":["or"],
                }
                is_live = extract_stream_type(url) == "LIVE TV"
                seen_lang = set()
                seen_url = set()
                res_list = []
                lock = __import__("threading").Lock()

                def fetch_jhs_lang(lang_code, lang_name):
                    all_codes = [lang_code] + FALLBACKS.get(lang_code, [])
                    for code in all_codes:
                        try:
                            api_url = build_jhs_api_url(slug_path, code, is_live=is_live)
                            req = request.Request(api_url, headers=build_jhs_headers_android())
                            with request.urlopen(req, timeout=10) as resp:
                                data = json.loads(resp.read().decode("utf-8"))
                            player_config = None
                            for sec in data.get("success",{}).get("page",{}).get("spaces",{}).values():
                                for w in sec.get("widget_wrappers",[]):
                                    d = w.get("widget",{}).get("data",{})
                                    if "player_config" in d:
                                        player_config = d["player_config"]; break
                                if player_config: break
                            if not player_config: continue
                            streams = extract_jhs_fallback_only(player_config)
                            for s in streams:
                                u = s.get("content_url")
                                if not u: continue
                                base_url = u.split("?")[0]
                                if is_live:
                                    tags = s.get("playback_tags","") or ""
                                    detected = ""
                                    for tag in tags.split(";"):
                                        if tag.startswith("language:"):
                                            detected = tag.split(":")[1].strip().lower(); break
                                    if detected and detected != code.lower(): continue
                                    display = LANGUAGES.get(detected, lang_name) if detected else lang_name
                                else:
                                    display = lang_name
                                    if extract_stream_type(url) not in ["MOVIE","TV SHOW"]:
                                        path_set = set(base_url.replace("https://","").split("/"))
                                        if not any(c in path_set for c in [lang_code]+FALLBACKS.get(lang_code,[])):
                                            continue
                                clean = u.split("?")[0] if extract_stream_type(url) in ["HIGHLIGHTS","CLIP"] else u
                                is_hdr = "hdr" in u.lower() or "hdr" in str(s.get("playback_tags","")).lower()
                                with lock:
                                    if display not in seen_lang and clean not in seen_url:
                                        seen_lang.add(display)
                                        seen_url.add(clean)
                                        res_list.append((display, clean, is_hdr))
                                return
                        except: continue

                with ThreadPoolExecutor(max_workers=2) as ex:
                    futs = [ex.submit(fetch_jhs_lang, code, name) for code,name in LANG_CODES]
                    for f in as_completed(futs, timeout=90):
                        try: f.result()
                        except: pass
                order = [name for _,name in LANG_CODES]
                res_list.sort(key=lambda x: order.index(x[0]) if x[0] in order else 99)
                return res_list
            return add_hdr_sdr_variants(collect_jhs_entries(url, slug_path))
        elif quality == "4":
            def collect_jhs4k_entries(url, slug_path):
                LANG_CODES = [
                    ("eng","ENGLISH"), ("en","ENGLISH"),
                    ("hin","HINDI"), ("hi","HINDI"), ("hd","HINDI HD"),
                    ("mar","MARATHI"), ("mr","MARATHI"), ("ma","MARATHI"),
                    ("guj","GUJARATI"), ("gu","GUJARATI"),
                    ("bih","BHOJPURI"), ("bho","BHOJPURI"), ("bh","BHOJPURI"),
                    ("pan","PUNJABI"), ("pun","PUNJABI"), ("pa","PUNJABI"), ("pu","PUNJABI"),
                    ("har","HARYANVI"), ("hv","HARYANVI"), ("ha","HARYANVI"),
                    ("tam","TAMIL"), ("ta","TAMIL"),
                    ("tel","TELUGU"), ("te","TELUGU"),
                    ("kan","KANNADA"), ("kn","KANNADA"),
                    ("mal","MALAYALAM"), ("ml","MALAYALAM"),
                    ("ben","BENGALI"), ("bn","BENGALI"),
                    ("ori","ORIYA"), ("or","ORIYA"),
                ]
                _seen_names = set()
                _unique_codes = []
                for _code, _name in LANG_CODES:
                    if _name not in _seen_names:
                        _seen_names.add(_name)
                        _unique_codes.append((_code, _name))
                LANG_CODES = _unique_codes
                FALLBACKS = {
                    "eng":["en"], "hin":["hi","hd"], "mar":["mr","ma"],
                    "guj":["gu"], "bih":["bho","bh"], "pan":["pun","pa","pu"],
                    "har":["hv","ha"], "tam":["ta"], "tel":["te"],
                    "kan":["kn"], "mal":["ml"], "ben":["bn"], "ori":["or"],
                }
                is_live = extract_stream_type(url) == "LIVE TV"
                seen_lang = set()
                seen_url = set()
                results = {}
                lock = __import__("threading").Lock()

                def fetch_jhs4k_single(lang_code, lang_name):
                    all_codes = [lang_code] + FALLBACKS.get(lang_code, [])
                    for code in all_codes:
                        try:
                            api_url = build_jhs_4k_api_url(slug_path, code, is_live=is_live)
                            req = request.Request(api_url, headers=build_jhs_headers())
                            with request.urlopen(req, timeout=5) as resp:
                                data = json.loads(resp.read().decode("utf-8"))
                            player_config = None
                            for sec in data.get("success",{}).get("page",{}).get("spaces",{}).values():
                                for w in sec.get("widget_wrappers",[]):
                                    d = w.get("widget",{}).get("data",{})
                                    if "player_config" in d:
                                        player_config = d["player_config"]; break
                                if player_config: break
                            if not player_config: continue
                            streams_4k = extract_4k_streams(player_config)
                            if streams_4k:
                                u = streams_4k[0]["url"]
                                clean = u if extract_stream_type(url) not in ["HIGHLIGHTS","CLIP"] else u.split("?")[0]
                                is_hdr = "hdr" in u.lower() or "hdr" in str(streams_4k[0].get("playback_tags","")).lower()
                                with lock:
                                    if lang_name not in seen_lang and clean not in seen_url:
                                        seen_lang.add(lang_name)
                                        seen_url.add(clean)
                                        results[lang_name] = (clean, is_hdr)
                                return
                            for s in extract_jhs_fallback_only(player_config):
                                u = s.get("content_url")
                                if not u: continue
                                base = u.split("?")[0]
                                if is_live:
                                    tags = s.get("playback_tags","") or ""
                                    detected = ""
                                    for tag in tags.split(";"):
                                        if tag.startswith("language:"):
                                            detected = tag.split(":")[1].strip().lower(); break
                                    if detected and detected != code.lower(): continue
                                    display = LANGUAGES.get(detected, lang_name) if detected else lang_name
                                else:
                                    display = lang_name
                                    if extract_stream_type(url) not in ["MOVIE","TV SHOW"]:
                                        path_set = set(base.replace("https://","").split("/"))
                                        if not any(c in path_set for c in [lang_code]+FALLBACKS.get(lang_code,[])):
                                            continue
                                clean = u.split("?")[0] if extract_stream_type(url) in ["HIGHLIGHTS","CLIP"] else u
                                is_hdr = "hdr" in u.lower() or "hdr" in str(s.get("playback_tags","")).lower()
                                with lock:
                                    if display not in seen_lang and clean not in seen_url:
                                        seen_lang.add(display)
                                        seen_url.add(clean)
                                        results[display] = (clean, is_hdr)
                                return
                        except: continue

                with ThreadPoolExecutor(max_workers=2) as ex:
                    futs = [ex.submit(fetch_jhs4k_single, code, name) for code,name in LANG_CODES]
                    for f in as_completed(futs, timeout=90):
                        try: f.result()
                        except: pass
                order = [name for _,name in LANG_CODES]
                entries = [(name, results[name][0], results[name][1]) for name in order if name in results]
                return entries
            return add_hdr_sdr_variants(collect_jhs4k_entries(url, slug_path))
        elif quality == "5":
            return get_option5_entries(url)
        elif quality == "6":
            def collect_option6_drm(url, slug_path):
                try:
                    drm_streams, global_license, global_keys, _ = fetch_drm_info_for_slug(slug_path)
                    if not drm_streams:
                        print(f"{YELLOW}  [DRM] No MPD streams found from API.{RESET}")
                        return []
                    key_str_global = ",".join(global_keys) if global_keys else global_license
                    result = []
                    seen_mpds = set()
                    ordered = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
                    for stream in ordered:
                        mpd_url = stream["mpd_url"]
                        mpd_base = mpd_url.split("?")[0]
                        if mpd_base in seen_mpds:
                            continue
                        seen_mpds.add(mpd_base)
                        license_url = stream.get("license_url") or global_license
                        variant = stream["variant"]
                        avail_langs = extract_mpd_languages(mpd_url)
                        if not avail_langs:
                            avail_langs = [("unk", "STREAM")]
                        key_str = key_str_global
                        try:
                            mpd_info = fetch_mpd_pssh(mpd_url)
                            if mpd_info and mpd_info.get("key_ids") and license_url:
                                ck = try_clearkey_json(mpd_info["key_ids"], license_url)
                                if ck:
                                    key_str = ",".join(ck)
                                elif mpd_info.get("pssh"):
                                    wv = fetch_widevine_keys(mpd_info["pssh"], license_url)
                                    if wv and not any(l.startswith("❌") for l in wv):
                                        key_str = ",".join(wv)
                        except Exception:
                            pass
                        for _, lang_name in avail_langs:
                            result.append((lang_name, variant, mpd_url, license_url, key_str))
                    return result
                except Exception as e:
                    print(f"{YELLOW}  [DRM] collect error: {e}{RESET}")
                    return []
            drm_entries = collect_option6_drm(url, slug_path)
            if not drm_entries:
                print(f"{RED}No DRM streams found.{RESET}")
                return []
            title_m3u, _ = extract_match_title(url)
            group = title_m3u or "Cricket"
            logo = logo_url or ""
            lines = ["#EXTM3U", f"# Title: {group}", f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            for lang_name, variant, mpd_url, license_url, key_str in drm_entries:
                entry_title = f"{lang_name} [{variant}]"
                ott_url = build_ott_drm_url(mpd_url, key_str) if key_str else mpd_url
                lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo}" group-title="{group}", {entry_title}')
                lines.append(ott_url)
                lines.append("")
            m3u_text = "\n".join(lines)
            total_entries = len([l for l in lines if l.startswith("#EXTINF")])
            try:
                with open(filename, "w", encoding="utf-8") as fw:
                    fw.write(m3u_text)
                print(f"{GREEN}✓ DRM M3U saved: {filename} ({total_entries} entries — PRIMARY + FALLBACK){RESET}")
            except Exception as e:
                print(f"{RED}Failed to write M3U: {e}{RESET}")
            if os.path.isfile(filename):
                if git_push_enabled:
                    git_push_m3u(filename, f"Auto update DRM {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                if use_cf and cf_worker_url and cf_api_token:
                    push_to_cloudflare(filename, cf_worker_url, cf_api_token)
            return None
        elif quality == "7":
            def collect_option7_plain_entries(slug_path):
                try:
                    drm_streams, _, _, _ = fetch_drm_info_for_slug(slug_path)
                    if not drm_streams:
                        return []
                    result = []
                    seen_mpds = set()
                    ordered = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
                    for stream in ordered:
                        mpd_url = stream["mpd_url"]
                        mpd_base = mpd_url.split("?")[0]
                        if mpd_base in seen_mpds:
                            continue
                        seen_mpds.add(mpd_base)
                        variant = stream["variant"]
                        avail_langs = extract_mpd_languages(mpd_url)
                        if not avail_langs:
                            avail_langs = [("unk", "STREAM")]
                        for _, lang_name in avail_langs:
                            result.append((f"{lang_name} {variant}", mpd_url, False))
                    return result
                except Exception as e:
                    print(f"{RED}Option 7 plain error: {e}{RESET}")
                    return []
            plain_entries = collect_option7_plain_entries(slug_path)
            if not plain_entries:
                print(f"{RED}No DRM streams found.{RESET}")
                return []
            title_p, _ = extract_match_title(url)
            group_p = title_p or "Cricket"
            logo_p = logo_url or ""
            lines_p = ["#EXTM3U", f"# Title: {group_p}", f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            for lang_name, mpd_url, _ in plain_entries:
                lines_p.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_p}" group-title="{group_p}", {lang_name}')
                lines_p.append(mpd_url)
                lines_p.append("")
            total_p = len([l for l in lines_p if l.startswith("#EXTINF")])
            try:
                with open(filename, "w", encoding="utf-8") as fw:
                    fw.write("\n".join(lines_p))
                print(f"{GREEN}✓ DRM plain M3U saved: {filename} ({total_p} entries){RESET}")
            except Exception as e:
                print(f"{RED}Failed to write M3U: {e}{RESET}")
            if os.path.isfile(filename):
                if git_push_enabled:
                    git_push_m3u(filename, f"Auto update DRM plain {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                if use_cf and cf_worker_url and cf_api_token:
                    push_to_cloudflare(filename, cf_worker_url, cf_api_token)
            return None
        elif quality == "8":
            def collect_live_tv_entries(url, slug_path):
                drm_streams, global_license, global_keys, _ = fetch_drm_info_for_slug(slug_path)
                if not drm_streams:
                    return []
                result = []
                seen_mpds = set()
                for stream in drm_streams:
                    mpd_url = stream["mpd_url"]
                    mpd_base = mpd_url.split("?")[0]
                    if mpd_base in seen_mpds:
                        continue
                    seen_mpds.add(mpd_base)
                    variant = stream.get("variant", "PRIMARY")
                    hdntl_val = get_hdntl_token_1(mpd_url) or extract_hdntl(mpd_url)
                    key_str = ""
                    license_url = stream.get("license_url") or global_license
                    if license_url:
                        try:
                            mpd_info = fetch_mpd_pssh(mpd_url)
                            if mpd_info and mpd_info.get("key_ids"):
                                ck = try_clearkey_json(mpd_info["key_ids"], license_url)
                                if ck:
                                    key_str = ",".join(ck)
                        except:
                            pass
                    ott_url = build_ott_drm_url_direct(mpd_base, key_str, hdntl_val)
                    result.append((f"LIVE TV [{variant}]", ott_url, False))
                return result
            entries = collect_live_tv_entries(url, slug_path)
            return entries
        elif quality == "9":
            print(f"{CYAN}  → Fetching fresh JHS cookie...{RESET}")
            try:
                _slug = extract_slug_path(url)
                _hdntl = ""
                # Try DRM fetch first
                try:
                    _drm_streams, _, _, _ = fetch_drm_info_for_slug(_slug)
                    for _s in _drm_streams:
                        _mpd = _s.get("mpd_url", "")
                        if _mpd:
                            _hdntl = get_hdntl_token_1(_mpd) or extract_hdntl(_mpd)
                            if _hdntl:
                                break
                except Exception:
                    pass
                # Fallback: JHS API
                if not _hdntl:
                    try:
                        _jhs_api = build_jhs_api_url(_slug, "hin", is_live=True)
                        _jhs_req = request.Request(_jhs_api, headers=build_jhs_headers_android())
                        with request.urlopen(_jhs_req, timeout=10) as _r:
                            _jhs_data = json.loads(_r.read().decode("utf-8"))
                        for _sec in _jhs_data.get("success", {}).get("page", {}).get("spaces", {}).values():
                            for _ww in _sec.get("widget_wrappers", []):
                                _pc = _ww.get("widget", {}).get("data", {}).get("player_config")
                                if _pc:
                                    for _st in extract_jhs_fallback_only(_pc):
                                        _u = _st.get("content_url", "")
                                        if _u:
                                            _hdntl = get_hdntl_token_1(_u) or extract_hdntl(_u)
                                            if _hdntl:
                                                break
                                if _hdntl:
                                    break
                            if _hdntl:
                                break
                    except Exception:
                        pass
                if not _hdntl:
                    print(f"{RED}  Could not fetch hdntl cookie for JHS.{RESET}")
                    return []
                import re as _re
                _exp = _re.search(r"exp=(\d+)", _hdntl)
                if _exp:
                    import datetime as _dt
                    _exp_str = _dt.datetime.fromtimestamp(int(_exp.group(1))).strftime("%H:%M:%S")
                    print(f"{GREEN}  ✓ JHS cookie fetched (expires {_exp_str}){RESET}")
                else:
                    print(f"{GREEN}  ✓ JHS cookie fetched{RESET}")
                # Build fresh JHS entries with new token
                _jhs_by_name = {}
                for _ch in JHS_CHANNELS:
                    _final_url = _ch["url_template"].replace("{HDNTL}", _hdntl)
                    _ch_logo = _ch.get("logo", "")
                    _extinf = f'#EXTINF:-1 tvg-name="{_ch["name"]}" tvg-logo="{_ch_logo}" group-title="JHS CHANNELS", {_ch["name"]}'
                    _jhs_by_name[_ch["name"]] = (_extinf, _final_url)

                if not replace_m3u:
                    # Append mode: refresh JHS tokens, keep non-JHS entries
                    _cf_get = cf_worker_url if use_cf else None
                    _existing = fetch_existing_m3u(filename, _cf_get)
                    _m3u_lines = [
                        "#EXTM3U",
                        f"# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        ""
                    ]
                    _refreshed = 0; _kept = 0; _added = 0
                    _written = set()
                    for _ex_inf, _ex_url, _ex_name in _existing:
                        if _ex_name in _jhs_by_name:
                            _new_inf, _new_url = _jhs_by_name[_ex_name]
                            _m3u_lines += [_new_inf, _new_url, ""]
                            _refreshed += 1
                        else:
                            _m3u_lines += [_ex_inf, _ex_url, ""]
                            _kept += 1
                        _written.add(_ex_name)
                    for _ch_name, (_ni, _nu) in _jhs_by_name.items():
                        if _ch_name not in _written:
                            _m3u_lines += [_ni, _nu, ""]
                            _added += 1
                    _total = _refreshed + _kept + _added
                    _msg = f"Append: {_refreshed} JHS refreshed + {_kept} kept + {_added} new = {_total} total"
                else:
                    # Replace mode: only JHS channels
                    _m3u_lines = [
                        "#EXTM3U",
                        f"# JHS Channels — auto-updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        ""
                    ]
                    for _ni, _nu in _jhs_by_name.values():
                        _m3u_lines += [_ni, _nu, ""]
                    _msg = f"Replace: {len(_jhs_by_name)} JHS channels"

                try:
                    with open(filename, "w", encoding="utf-8") as _fw:
                        _fw.write("\n".join(_m3u_lines))
                    _total = len([_l for _l in _m3u_lines if _l.startswith("#EXTINF")])
                    print(f"{GREEN}  ✓ JHS M3U saved: {filename} ({_total} channels) [{_msg}]{RESET}")
                except Exception as _e:
                    print(f"{RED}  Failed to write JHS M3U: {_e}{RESET}")
                if os.path.isfile(filename):
                    if git_push_enabled:
                        git_push_m3u(filename, f"JHS auto update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    if use_cf and cf_worker_url and cf_api_token:
                        push_to_cloudflare(filename, cf_worker_url, cf_api_token)
                return None
            except Exception as e:
                print(f"{RED}  JHS update failed: {e}{RESET}")
                return []
        else:
            return []

    while True:
        try:
            print(f"\n{BOLD_YELLOW}[{datetime.now().strftime('%H:%M:%S')}] Updating M3U...{RESET}")
            # Multi-quality: collect entries from all selected qualities and merge
            if len(quality_list) > 1:
                merged_entries = []
                seen_merge_urls = set()
                seen_merge_labels = set()
                for q_idx, q in enumerate(quality_list):
                    q_label_map = {"1":"4K","2":"FHD","3":"JHS-FHD","4":"JHS-4K","5":"ADS-FREE 4K","6":"DRM-OTT","7":"DRM-NS","8":"DRM-TV","9":"JHS-CHANNELS"}
                    q_tag = q_label_map.get(q, f"Q{q}")
                    print(f"{CYAN}  → Fetching quality {q} ({q_tag})...{RESET}")
                    q_entries = get_entries(q, url, slug_path)
                    if q_entries is None or not q_entries:
                        continue
                    for entry in q_entries:
                        if len(entry) == 2:
                            lang_n, entry_url = entry; is_hdr = False
                        else:
                            lang_n, entry_url, is_hdr = entry
                        entry_url_base = entry_url.split("?")[0]
                        # Tag label with quality if multiple qualities
                        tagged_label = f"{lang_n} [{q_tag}]"
                        if entry_url_base not in seen_merge_urls and tagged_label not in seen_merge_labels:
                            seen_merge_urls.add(entry_url_base)
                            seen_merge_labels.add(tagged_label)
                            merged_entries.append((tagged_label, entry_url, is_hdr))
                entries = merged_entries if merged_entries else []
            else:
                entries = get_entries(quality, url, slug_path)
            if entries is None:
                pass  # option 6 DRM: already handled inside get_entries
            elif entries:
                title, match_no = extract_match_title(url)
                stype = extract_stream_type(url)
                # Normalize entries - handle both (lang, url) and (lang, url, is_hdr) tuples
                normalized = []
                for entry in entries:
                    if len(entry) == 2:
                        normalized.append((entry[0], entry[1], False))
                    else:
                        normalized.append(entry)
                # ── Auto-extract hdntl cookie from fresh stream URLs ──────
                _au_hdntl = ""
                for _en, _eu, _eh in normalized:
                    try:
                        _tok = get_hdntl_token_1(_eu)
                        if _tok:
                            _au_hdntl = _tok
                            break
                    except Exception:
                        pass

                if not replace_m3u:
                    # ── APPEND MODE ─────────────────────────────────────────
                    # Recently refreshed/new channels TOP pe, kept (old) channels BOTTOM pe
                    import re as _re
                    _new_by_name = {}
                    for _n, _u, _h in normalized:
                        _new_by_name[_n.strip()] = (_n, _u, _h)
                    # Fetch existing entries (local file or CF)
                    _cf_get = cf_worker_url if use_cf else None
                    _existing = fetch_existing_m3u(filename, _cf_get)

                    _refreshed = 0
                    _kept = 0
                    _added = 0
                    _written_names = set()

                    # --- Separate refreshed vs kept from existing ---
                    _refreshed_lines = []   # existing entries that got new token (top)
                    _kept_lines = []        # existing entries with no new match (bottom)

                    def _exthttp_line(ck):
                        if ck:
                            return f'#EXTHTTP:{{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/","Cookie":"hdntl={ck}"}}' 
                        return '#EXTHTTP:{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/"}'

                    for _extinf, _old_url, _tvg in _existing:
                        if _tvg in _new_by_name:
                            # Refresh URL with new token, keep EXTINF header
                            _, _new_url, _new_h = _new_by_name[_tvg]
                            _refreshed_lines.append(_extinf)
                            _refreshed_lines.append(_exthttp_line(_au_hdntl))
                            _refreshed_lines.append('#EXTVLCOPT:http-extra-headers=Origin: https://www.hotstar.com')
                            _refreshed_lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
                            _refreshed_lines.append(_new_url)
                            _refreshed_lines.append("")
                            _refreshed += 1
                        else:
                            # Keep as-is (JHS channel or other source)
                            _kept_lines.append(_extinf)
                            _kept_lines.append(_old_url)
                            _kept_lines.append("")
                            _kept += 1
                        _written_names.add(_tvg)

                    # --- Truly new entries not seen before ---
                    _new_lines = []
                    for _n, _u, _h in normalized:
                        if _n.strip() not in _written_names:
                            _tag = " [HDR]" if _h else ""
                            _new_lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_url}" group-title="{title}", {_n}{_tag}')
                            _new_lines.append(_exthttp_line(_au_hdntl))
                            _new_lines.append('#EXTVLCOPT:http-extra-headers=Origin: https://www.hotstar.com')
                            _new_lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
                            _new_lines.append(_u)
                            _new_lines.append("")
                            _added += 1

                    # --- Build final M3U: header → refreshed → new → kept ---
                    _merged = [
                        "#EXTM3U",
                        f"# Title: {title}",
                        f"# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        ""
                    ]
                    _merged += _refreshed_lines   # recently refreshed → TOP
                    _merged += _new_lines          # brand new channels → after refreshed
                    _merged += _kept_lines         # old/JHS channels → BOTTOM

                    try:
                        with open(filename, "w", encoding="utf-8") as _fw:
                            _fw.write("\n".join(_merged))
                        print(f"{GREEN}✓ Append: {_refreshed} refreshed + {_added} new [TOP] + {_kept} kept [BOTTOM] = {_refreshed+_kept+_added} total → {filename}{RESET}")
                    except Exception as _we:
                        print(f"{YELLOW}⚠ Write failed ({_we}), falling back to replace{RESET}")
                        create_m3u_file(normalized, title, match_no, stype, filename, logo_url)
                else:
                    # ── REPLACE MODE (default) ───────────────────────────────
                    create_m3u_file(normalized, title, match_no, stype, filename, logo_url, hdntl_cookie=_au_hdntl)
                # ── Push ─────────────────────────────────────────────────────
                file_exists = os.path.isfile(filename)
                if git_push_enabled and file_exists:
                    git_push_m3u(filename, f"Auto update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                if use_cf and cf_worker_url and cf_api_token and file_exists:
                    push_to_cloudflare(filename, cf_worker_url, cf_api_token)
                elif use_cf and cf_worker_url and cf_api_token and not file_exists:
                    print(f"{RED}✗ M3U file not found on disk, cannot push to Cloudflare.{RESET}")
            else:
                print(f"{RED}No streams found this cycle.{RESET}")
            print(f"Waiting {interval} minutes...")
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Auto-update stopped by user.{RESET}")
            break
        except Exception as e:
            print(f"{RED}ERROR in update loop: {type(e).__name__}: {e}{RESET}")
            import traceback
            traceback.print_exc()
            print(f"{YELLOW}Retrying in {interval} minutes...{RESET}")
            time.sleep(interval * 60)

        # ===================== OPTION 9 (4K ADS-FREE PRIMARY CDN - SINGLE LANGUAGE) =====================
        API_TEMPLATE_4KADS = "https://www.hotstar.com/api/internal/bff/v2/slugs/in/{slug_path}/watch"

        LANG_MAP_4KADS = {
            "1": ["eng"],
            "2": ["hin", "hi", "hd"],
            "3": ["mar", "mr", "ma"],
            "4": ["guj", "gu"],
            "5": ["bih", "bho", "bh"],
            "6": ["pan", "pun", "pa", "pu"],
            "7": ["har", "hv", "ha"],
            "8": ["tam", "ta"],
            "9": ["tel", "te"],
            "10": ["kan", "kn"],
            "11": ["mal", "ml"],
            "12": ["ben", "bn"],
        }

def build_api_url_4kads(asset_id: str, lang: str, slug_path: str = "") -> str:
    if slug_path:
        base_url = API_TEMPLATE_4KADS.format(slug_path=slug_path)
    else:
        # Fallback to news slug if no slug_path provided (old behavior)
        base_url = "https://www.hotstar.com/api/internal/bff/v2/slugs/in/news/news18-india/{id}/live/watch".format(id=asset_id)

    client_capabilities = {
        "ads": ["non_ssai", "ssai"],
        "audio_channel": ["stereo", "dolby51", "atmos"],
        "container": ["fmp4", "fmp4br", "ts"],
        "dvr": ["short", "long"],
        "dynamic_range": ["hdr10", "hdr", "sdr"],
        "encryption": ["widevine", "plain"],
        "ladder": ["tv", "web", "phone", "4k"],
        "package": ["dash", "hls"],
        "resolution": ["4k", "fhd", "hd", "sd"],
        "video_codec": ["h265", "h264"],
        "video_codec_non_secure": ["h265", "h264", "vp9"]
    }
    drm_parameters = {
        "hdcp_version": ["HDCP_V2_2"],
        "widevine_security_level": ["HW_SECURE_ALL", "HW_SECURE_DECODE", "SW_SECURE_DECODE"]
    }
    return (
        base_url
        + '?'
        + '&client_capabilities=' + parse.quote(json.dumps(client_capabilities, separators=(',', ':')))
        + '&drm_parameters=' + parse.quote(json.dumps(drm_parameters, separators=(',', ':')))
        + '&request_features=consent_supported'
        + '&lang=' + parse.quote(lang, safe="")
    )

def fetch_player_config_4kads(api_url: str) -> dict:
    req = request.Request(api_url, method="GET", headers=build_headers_1())
    with request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["success"]["page"]["spaces"]["player"]["widget_wrappers"][0]["widget"]["data"]["player_config"]
    except:
        raise ValueError("Could not find player_config")

def extract_all_streams_4kads(player_config: dict) -> list:
    streams = []
    media_assets = []
    for key in ["media_asset", "media_asset_v2", "media_assets"]:
        asset = player_config.get(key)
        if not asset:
            continue
        if isinstance(asset, dict):
            media_assets.append(asset)
        elif isinstance(asset, list):
            media_assets.extend(asset)
    for asset in media_assets:
        for stream_type in ["primary", "preview", "dash", "hls", "playback_url"]:
            item = asset.get(stream_type)
            if not isinstance(item, dict):
                continue
            content_url = (
                item.get("content_url")
                or item.get("url")
                or item.get("playback_url")
            )
            if not content_url:
                continue
            streams.append({
                "type": stream_type,
                "content_url": content_url,
                "playback_tags": str(item.get("playback_tags", "")).lower(),
                "width": item.get("width") or 0,
                "height": item.get("height") or 0,
            })
    unique_streams = []
    seen = set()
    for s in streams:
        url = s.get("content_url")
        if not url:
            continue
        clean = url.split("?")[0]
        if clean in seen:
            continue
        seen.add(clean)
        unique_streams.append(s)
    return unique_streams

def print_streams_4kads(streams: list, expected_lang: str):
    if not streams:
        return None
    candidate_urls = []
    for s in streams:
        original_url = str(s.get("content_url", ""))
        if not original_url:
            continue
        if str(s.get("type", "")).lower() != "primary":
            continue
        variants = generate_cdn_variants_1(original_url)
        for v in variants:
            candidate_urls.append((v, s))
    working = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(is_working_url_1, item[0]): item for item in candidate_urls}
        for future in as_completed(futures):
            result = future.result()
            if result:
                working.append(futures[future])
    shown = set()
    for raw_url, s in working:
        clean = raw_url.split("?")[0]
        if clean in shown:
            continue
        shown.add(clean)
        detected_lang = detect_language_from_url_1(raw_url)
        if detected_lang.upper() != expected_lang.upper():
            continue
        token = get_hdntl_token_1(raw_url)
        final_url = append_hdntl_to_url_1(raw_url, token)
        lower = raw_url.lower()
        stype = str(s.get("type", "")).upper()
        extra = f" {GREEN}ADSFREE{RESET}" if ("non_ssai" in lower or "ssai" not in lower) else ""
        if "2160" in lower or "4k" in lower:
            extra += f" {MAGENTA}4K{RESET}"
        elif "1080" in lower:
            extra += f" {CYAN}1080P{RESET}"
        elif "720" in lower:
            extra += f" {BLUE}720P{RESET}"
        print(f"{YELLOW}WORKING PRIMARY CDN | {detected_lang} | {stype}{extra}{RESET}")
        print(f"{final_url}\n")
        return final_url
    return None

def parse_asset_id_4kads(url: str):
    value = url.strip()
    if not value:
        return None
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) >= 4 and segments[-1] == "watch" and segments[-3] == "video":
        return segments[-4]
    if len(segments) >= 3 and segments[-1] == "watch":
        return segments[-3]
    if len(segments) >= 2 and segments[-1] in ["live", "highlights", "replay", "clips"]:
        return segments[-2]
    return segments[-1]

def get_option5_entries(input_url: str):
    """Reusable version of option5_main that returns (lang, url, is_hdr) entries."""
    def parse_asset_id(url: str):
        parsed = urlparse(url)
        path = parsed.path if parsed.scheme else url
        segs = [s for s in path.split("/") if s]
        if len(segs) >= 4 and segs[-1] == "watch" and segs[-3] == "video":
            return segs[-4]
        if len(segs) >= 3 and segs[-1] == "watch":
            return segs[-3]
        if len(segs) >= 2 and segs[-1] in ["live", "highlights", "replay", "clips"]:
            return segs[-2]
        return segs[-1]

    asset_id = parse_asset_id(input_url)
    if not asset_id:
        return []

    slug_path_5 = extract_slug_path(input_url) or ""
    lang_codes_list_raw = [
        ("eng","ENGLISH"), ("en","ENGLISH"),
        ("hin","HINDI"), ("hi","HINDI"), ("hd","HINDI HD"),
        ("mar","MARATHI"), ("mr","MARATHI"), ("ma","MARATHI"),
        ("guj","GUJARATI"), ("gu","GUJARATI"),
        ("bih","BHOJPURI"), ("bho","BHOJPURI"), ("bh","BHOJPURI"),
        ("pan","PUNJABI"), ("pun","PUNJABI"), ("pa","PUNJABI"), ("pu","PUNJABI"),
        ("har","HARYANVI"), ("hv","HARYANVI"), ("ha","HARYANVI"),
        ("tam","TAMIL"), ("ta","TAMIL"),
        ("tel","TELUGU"), ("te","TELUGU"),
        ("kan","KANNADA"), ("kn","KANNADA"),
        ("mal","MALAYALAM"), ("ml","MALAYALAM"),
        ("ben","BENGALI"), ("bn","BENGALI"),
        ("ori","ORIYA"), ("or","ORIYA"),
    ]
    _s = set()
    lang_codes_list = [(_c,_n) for _c,_n in lang_codes_list_raw if not (_n in _s or _s.add(_n))]

    collected = []
    lock = __import__('threading').Lock()

    def fetch_one(lang_code, lang_name):
        for attempt in range(2):
            try:
                api = build_api_url_1(asset_id, lang_code, slug_path=slug_path_5)
                pc = fetch_player_config_1(api)
                streams = extract_primary_streams_1(pc)
                if not streams:
                    # Fallback: try jhs_4k_api which works better for live
                    try:
                        is_live = extract_stream_type(input_url) == "LIVE TV"
                        jhs_api = build_jhs_4k_api_url(slug_path_5, lang_code, is_live=is_live)
                        jhs_req = request.Request(jhs_api, headers=build_jhs_headers())
                        with request.urlopen(jhs_req, timeout=10) as r:
                            jhs_data = json.loads(r.read().decode("utf-8"))
                        jhs_pc = None
                        for sec in jhs_data.get("success",{}).get("page",{}).get("spaces",{}).values():
                            for w in sec.get("widget_wrappers",[]):
                                d = w.get("widget",{}).get("data",{})
                                if "player_config" in d:
                                    jhs_pc = d["player_config"]
                                    break
                            if jhs_pc: break
                        if jhs_pc:
                            streams = extract_primary_streams_1(jhs_pc) or []
                            if not streams:
                                streams = [{"type":"primary","content_url":s.get("content_url"),"playback_tags":s.get("playback_tags","")} for s in extract_jhs_fallback_only(jhs_pc) if s.get("content_url")]
                            pc = jhs_pc
                    except Exception:
                        pass
                if streams:
                    candidate_urls = []
                    for s in streams:
                        original = s.get("content_url")
                        if not original:
                            continue
                        for v in generate_cdn_variants_1(original):
                            candidate_urls.append((v, s))
                    # Remove dupes
                    seen_c = set()
                    candidate_urls = [(u,s) for u,s in candidate_urls if not (u in seen_c or seen_c.add(u))]
                    working = []
                    with ThreadPoolExecutor(max_workers=4) as ex:
                        futures = {ex.submit(is_working_url_1, u): (u, s) for u, s in candidate_urls}
                        for fut in as_completed(futures):
                            try:
                                if fut.result(timeout=15):
                                    working.append(futures[fut])
                            except:
                                continue
                    if not working:
                        working = candidate_urls
                    for u, s in working:
                        detected = detect_language_from_url_1(u)
                        if detected.upper() == lang_name.upper() or detected == "OTHER":
                            token = get_hdntl_token_1(u)
                            final = append_hdntl_to_url_1(u, token)
                            is_hdr = "hdr" in final.lower() or "hdr" in str(s.get("playback_tags", "")).lower()
                            with lock:
                                if lang_name not in [c[0] for c in collected]:
                                    collected.append((lang_name, final, is_hdr))
                            return
            except Exception:
                time.sleep(1)
                continue

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fetch_one, code, name) for code, name in lang_codes_list]
        for f in as_completed(futures):
            try:
                f.result(timeout=50)
            except:
                pass

    return collected

def option9_main(input_url: str):
    import threading
    asset_id = parse_asset_id_4kads(input_url)
    slug_path = extract_slug_path(input_url) or ""
    if not asset_id:
        print(f"{RED}Error: could not parse asset id from URL{RESET}")
        return

    print(f"\n{GREEN}=== PRIMARY ADSFREE STREAM FINDER (ALL LANGUAGES) ==={RESET}\n")
    print(f"{YELLOW}Checking all languages in parallel...{RESET}\n")

    # All unique language groups to try (primary code + fallbacks)
    lang_groups = [
        ("eng", ["eng"], "ENGLISH"),
        ("hin", ["hin", "hi", "hd"], "HINDI"),
        ("mar", ["mar", "mr", "ma"], "MARATHI"),
        ("guj", ["guj", "gu"], "GUJARATI"),
        ("bih", ["bih", "bho", "bh"], "BHOJPURI"),
        ("pan", ["pan", "pun", "pa", "pu"], "PUNJABI"),
        ("har", ["har", "hv", "ha"], "HARYANVI"),
        ("tam", ["tam", "ta"], "TAMIL"),
        ("tel", ["tel", "te"], "TELUGU"),
        ("kan", ["kan", "kn"], "KANNADA"),
        ("mal", ["mal", "ml"], "MALAYALAM"),
        ("ben", ["ben", "bn"], "BENGALI"),
    ]

    collected = []
    lock = threading.Lock()

    def fetch_one_lang(primary, codes, lang_name):
        for lang_code in codes:
            for attempt in range(2):
                try:
                    api_url = build_api_url_4kads(asset_id, lang_code, slug_path=slug_path)
                    player_config = fetch_player_config_4kads(api_url)
                    streams = extract_all_streams_4kads(player_config)
                    if not streams:
                        continue
                    # Build CDN candidate list
                    candidate_urls = []
                    for s in streams:
                        orig = str(s.get("content_url", ""))
                        if not orig:
                            continue
                        if str(s.get("type", "")).lower() != "primary":
                            continue
                        for v in generate_cdn_variants_1(orig):
                            candidate_urls.append((v, s))
                    if not candidate_urls:
                        continue
                    # Check working URLs in parallel
                    working = []
                    with ThreadPoolExecutor(max_workers=12) as ex:
                        futs = {ex.submit(is_working_url_1, item[0]): item for item in candidate_urls}
                        for fut in as_completed(futs):
                            if fut.result():
                                working.append(futs[fut])
                    shown = set()
                    for raw_url, s in working:
                        clean = raw_url.split("?")[0]
                        if clean in shown:
                            continue
                        shown.add(clean)
                        detected = detect_language_from_url_1(raw_url)
                        if detected.upper() != lang_name.upper():
                            continue
                        token = get_hdntl_token_1(raw_url)
                        final_url = append_hdntl_to_url_1(raw_url, token)
                        lower = raw_url.lower()
                        extra = " ADSFREE" if ("non_ssai" in lower or "ssai" not in lower) else ""
                        if "2160" in lower or "4k" in lower:
                            extra += " 4K"
                        elif "1080" in lower:
                            extra += " 1080P"
                        elif "720" in lower:
                            extra += " 720P"
                        with lock:
                            if lang_name not in [c[0] for c in collected]:
                                collected.append((lang_name, final_url, extra.strip()))
                        return
                except Exception:
                    if attempt == 0:
                        time.sleep(0.5)
                    continue

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(fetch_one_lang, p, codes, name) for p, codes, name in lang_groups]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception:
                pass

    if not collected:
        print(f"{RED}No working primary streams found for any language.{RESET}")
        print(f"{YELLOW}Check token/network.{RESET}")
        return

    print(f"{BOLD_GREEN}=== FOUND {len(collected)} LANGUAGE(S) ==={RESET}\n")
    for lang_name, final_url, tags in collected:
        lower_url = final_url.lower()
        label = f"{lang_name} 4K ADSFREE"
        print(f"{BOLD_CYAN}{label}{RESET}")
        print(f"{GREEN}{final_url}{RESET}\n")

    if os.name == "nt":
        pass
    else:
        input(f"\nPress Enter to exit and copy URLs...")

# ===================== OPTION 10 (REFRESH TOKENS IN M3U) =====================
def option9_refresh_tokens():
    print(f"\n{BOLD_GREEN}=== AUTO REFRESH TOKENS IN M3U ==={RESET}")
    filename = input(f"Enter M3U filename to refresh (e.g. hotstar_auto.m3u): ").strip()
    if not filename:
        print(f"{RED}No filename entered.{RESET}")
        return
    if not os.path.isfile(filename):
        print(f"{RED}File not found: {filename}{RESET}")
        return

    interval_raw = input(f"Refresh interval in minutes (default 20): ").strip()
    interval = int(interval_raw) if interval_raw.isdigit() else 20

    print(f"\n{BOLD_CYAN}Auto-push destination:{RESET}")
    print(f"  {BOLD_GREEN}1{RESET}) GitHub only")
    print(f"  {BOLD_YELLOW}2{RESET}) Cloudflare Workers only")
    print(f"  {BOLD_MAGENTA}3{RESET}) Both GitHub + Cloudflare")
    print(f"  {BOLD_WHITE}n{RESET}) No push (local only)")
    push_choice = input(f"{BOLD_CYAN}Choose (1/2/3/n): {RESET}").strip().lower()
    git_push_enabled = push_choice in ["1", "3"]
    use_cf = push_choice in ["2", "3"]
    cf_worker_url = None
    cf_api_token = None
    if use_cf:
        config = load_cf_config()
        config_valid = (
            config and
            config.get("worker_url", "").startswith("http") and
            config.get("api_token", "")
        )
        if config_valid:
            print(f"{GREEN}✓ Loaded Cloudflare config from {CF_CONFIG_FILE}{RESET}")
            use_existing = input(f"Use existing config? (y/n): ").strip().lower()
            if use_existing == 'y':
                cf_worker_url = config['worker_url']
                cf_api_token = config['api_token']
            else:
                cf_worker_url = input("Enter Cloudflare Worker URL (https://...): ").strip()
                cf_api_token = input("Enter API Bearer Token: ").strip()
                save_cf_config(cf_worker_url, cf_api_token)
        else:
            cf_worker_url = input("Enter Cloudflare Worker URL (https://...): ").strip()
            cf_api_token = input("Enter API Bearer Token: ").strip()
            save_cf_config(cf_worker_url, cf_api_token)
        if not cf_worker_url or not cf_worker_url.startswith("http"):
            print(f"{RED}✗ Invalid Worker URL! Disabling CF push.{RESET}")
            use_cf = False
        elif not cf_api_token:
            print(f"{RED}✗ API token empty! Disabling CF push.{RESET}")
            use_cf = False
    if git_push_enabled:
        print(f"{GREEN}✓ GitHub auto-push enabled{RESET}")
    if not git_push_enabled and not use_cf:
        print(f"{YELLOW}No push destination. File will be saved locally only.{RESET}")

    def do_refresh():
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        url_indices = [
            i for i, line in enumerate(lines)
            if line.strip().startswith("http") and "hotstar.com" in line and "hdnea=" in line
        ]
        if not url_indices:
            print(f"{YELLOW}No hdnea URLs found in file.{RESET}")
            return 0, 0

        lock = __import__("threading").Lock()
        refreshed = [0]
        failed = [0]

        def refresh_one(idx):
            old_url = lines[idx].strip()
            try:
                token = get_hdntl_token_1(old_url)
                if token:
                    new_url = append_hdntl_to_url_1(old_url, token)
                    with lock:
                        lines[idx] = new_url + "\n"
                        refreshed[0] += 1
                else:
                    with lock:
                        failed[0] += 1
            except Exception:
                with lock:
                    failed[0] += 1

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(refresh_one, i) for i in url_indices]
            for fut in as_completed(futs, timeout=120):
                try:
                    fut.result()
                except Exception:
                    pass

        for i, line in enumerate(lines):
            if line.startswith("# Generated:"):
                lines[i] = f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                break

        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return refreshed[0], failed[0]

    print(f"{GREEN}✓ Starting auto-refresh every {interval} minute(s) — Ctrl+C to stop{RESET}")
    while True:
        try:
            print(f"\n{BOLD_YELLOW}[{datetime.now().strftime('%H:%M:%S')}] Refreshing tokens...{RESET}")
            ok, fail = do_refresh()
            print(f"{GREEN}✓ {ok} token(s) refreshed, {fail} failed → {filename}{RESET}")
            if git_push_enabled:
                git_push_m3u(filename, f"Token refresh {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if use_cf and cf_worker_url and cf_api_token:
                push_to_cloudflare(filename, cf_worker_url, cf_api_token)
            print(f"{CYAN}Waiting {interval} minutes...{RESET}")
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Stopped.{RESET}")
            break


# ===================== OPTION 11 (UPDATE JHS.TXT COOKIES) =====================

# ── Embedded JHS channel list (from jhs.txt) ──────────────────────────────────
JHS_CHANNELS = [
    {
        "logo": "https://img10.hotstar.com/image/upload/f_auto/sources/r1/cms/prod/8763/1739203338763-a.jpg",
        "name": "TATA IPL TV",
        "url_template": "https://jcevents.hotstar.com/bpk-tv/e03bbf7688f4b14faa3782e78851c3d9_CTV/Fallback/index2.m3u8?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}",
        "type": "m3u8_lcookie",
        "stream_id": "e03bbf7688f4b14faa3782e78851c3d9_CTV",
    },
    {
        "logo": "https://img.media.jio.com/tvpimages/5/6/301982_1749665314605_l_medium.jpg",
        "name": "STAR SPORTS 1 Hindi HD",
        "url_template": "https://livetv.hotstar.com/mp1/gec-india-1540065788/fa6a4f0005ef4f90ab24484d165b0aaf/index.mpd?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}&drmScheme=clearkey&drmLicense=81872faa1d6b45fa9045cdeb2e310000:9b88168e61274587a471962c46b94675",
        "type": "mpd_cookie",
    },
    {
        "logo": "https://i.ibb.co/pmVQWFZ/SS1HD.jpg",
        "name": "STAR SPORTS 1 HD",
        "url_template": "https://livetv.hotstar.com/mp1/gec-india-1540065782/fce958099ca84fc3b980e651a4a668a8/index.mpd?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}&drmScheme=clearkey&drmLicense=b7cdde012ce04e90a08b90622e020000:13603245acab444faef6cab5198de55f",
        "type": "mpd_cookie",
    },
    {
        "logo": "https://i.ibb.co/x8739M8d/SS2HD.jpg",
        "name": "STAR SPORTS 2 HD",
        "url_template": "https://livetv.hotstar.com/mp2/gec-india-1540065785/a00717b1324f45eb814eec9e48a12db8/index.mpd?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}&drmScheme=clearkey&drmLicense=9dacc80134404c34ba184022c28d0000:982183fb4d9449c995859b7cff512092",
        "type": "mpd_cookie",
    },
    {
        "logo": "https://i.ibb.co/YBMBDWtd/SS2HD-HINDI.jpg",
        "name": "STAR SPORTS 2 Hindi HD",
        "url_template": "https://jcevents.hotstar.com/bpk-tv/f0e3e64ae415771d8e460317ce97aa5e/Fallback/f0e3e64ae415771d8e460317ce97aa5e.m3u8?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}",
        "type": "m3u8_lcookie",
    },
    {
        "logo": "https://i.ibb.co/B5Mnd89k/SS2-HINDI.jpg",
        "name": "STAR SPORTS 2 Hindi",
        "url_template": "https://jcevents.hotstar.com/bpk-tv/2c7182c8e6a22cfa6ebc02bbc9ed6dd0/Fallback/2c7182c8e6a22cfa6ebc02bbc9ed6dd0.m3u8?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}",
        "type": "m3u8_cookie",
    },
    {
        "logo": "https://i.ibb.co/cXNb5Y9t/SS2-TAMIL.jpg",
        "name": "STAR SPORTS 2 Tamil",
        "url_template": "https://jcevents.hotstar.com/bpk-tv/4db6f833701e78ae4443cb268020f03b/Fallback/4db6f833701e78ae4443cb268020f03b.m3u8?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}",
        "type": "m3u8_cookie",
    },
    {
        "logo": "https://i.ibb.co/bM7qT3NC/SS2-TELUGU.jpg",
        "name": "STAR SPORTS 2 Telugu",
        "url_template": "https://jcevents.hotstar.com/bpk-tv/034d1fb94cae87294a06f4dc266084b9/Fallback/034d1fb94cae87294a06f4dc266084b9.m3u8?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}",
        "type": "m3u8_cookie",
    },
    {
        "logo": "https://img1.hotstarext.com/image/upload/f_auto/sources/r1/cms/prod/7226/597226-h.jpg",
        "name": "STAR SPORTS 1 SELECT HD",
        "url_template": "https://livetv.hotstar.com/mp2/gec-india-1540065791/8bb5cd7a8e274186977473a6771d9352/index.mpd?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}&drmScheme=clearkey&drmLicense=1f64a24b3950468497390155c4880000:68f788aced6c4ecb89108f22fe9ee087",
        "type": "mpd_cookie",
    },
    {
        "logo": "https://img1.hotstarext.com/image/upload/f_auto/sources/r1/cms/prod/7227/597227-h.jpg",
        "name": "STAR SPORTS 2 SELECT HD",
        "url_template": "https://livetv.hotstar.com/mp1/gec-india-1540065794/e2408fbafb9d4a5ab23775b69e5737d7/index.mpd?|User-Agent=Hotstar;in.startv.hotstar/25.02.24.8.11169 (Android/15)&Referer=https://www.hotstar.com/&Origin=https://www.hotstar.com&Cookie=hdntl={HDNTL}&drmScheme=clearkey&drmLicense=2effd2e98f95492cb7418857bf610000:f0e42f1c91fb4b59bf6684cb4478d82e",
        "type": "mpd_cookie",
    },
]


def option11_update_jhs(input_url: str = ""):
    """Option 11: Fetch fresh hdntl cookie from any Hotstar Live URL and
    regenerate all JHS channels with the updated cookie, then print and save."""
    # ── Step 1: Get URL if not provided ──────────────────────────────
    if not input_url:
        input_url = input(f"{BOLD_CYAN}Enter any Hotstar Live TV URL (to fetch fresh cookie): {RESET}").strip()
    if not input_url:
        print(f"{RED}No URL provided. Aborting.{RESET}")
        return

    slug_path = extract_slug_path(input_url)
    if not slug_path:
        print(f"{RED}Invalid Hotstar URL!{RESET}")
        return

    # ── Step 2: Fetch fresh hdntl via DRM stream fetch ───────────────
    hdntl_new = ""

    try:
        drm_streams, _, _, _ = fetch_drm_info_for_slug(slug_path)
        for stream in drm_streams:
            mpd_url = stream.get("mpd_url", "")
            if mpd_url:
                hdntl_new = get_hdntl_token_1(mpd_url)
                if hdntl_new:
                    break
                hdntl_new = extract_hdntl(mpd_url)
                if hdntl_new:
                    break
    except Exception as e:
        print(f"{YELLOW}Warning: DRM fetch failed ({e}), trying direct token fetch...{RESET}")

    # Fallback: try JHS API
    if not hdntl_new:
        try:
            jhs_api = build_jhs_api_url(slug_path, "hin", is_live=True)
            jhs_req = request.Request(jhs_api, headers=build_jhs_headers_android())
            with request.urlopen(jhs_req, timeout=10) as r:
                jhs_data = json.loads(r.read().decode("utf-8"))
            for sec in jhs_data.get("success", {}).get("page", {}).get("spaces", {}).values():
                for ww in sec.get("widget_wrappers", []):
                    pc = ww.get("widget", {}).get("data", {}).get("player_config")
                    if pc:
                        streams = extract_jhs_fallback_only(pc)
                        for s in streams:
                            url = s.get("content_url", "")
                            if url:
                                hdntl_new = get_hdntl_token_1(url) or extract_hdntl(url)
                                if hdntl_new:
                                    break
                    if hdntl_new:
                        break
                if hdntl_new:
                    break
        except Exception as e:
            print(f"{YELLOW}JHS API fallback also failed: {e}{RESET}")

    if not hdntl_new:
        print(f"{RED}Could not fetch fresh hdntl cookie. Aborting.{RESET}")
        return

    # Show expiry from token
    exp_match = re.search(r"exp=(\d+)", hdntl_new)
    if exp_match:
        import datetime as _dt
        exp_ts = int(exp_match.group(1))
        exp_str = _dt.datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{GREEN}✓ Fresh cookie fetched! Expires: {exp_str}{RESET}")
    else:
        print(f"{GREEN}✓ Fresh cookie fetched!{RESET}")

    # ── Step 3: Build updated channel list lines ──────────────────────
    lines = []
    for ch in JHS_CHANNELS:
        final_url = ch["url_template"].replace("{HDNTL}", hdntl_new)
        lines.append("LOGO")
        lines.append(ch["logo"])
        lines.append(ch["name"])
        lines.append(final_url)
        lines.append("")

    output = "\n".join(lines).rstrip() + "\n"

    # ── Print all channels directly ───────────────────────────────────
    print(f"{BOLD_CYAN}ALL JHS CHANNELS{RESET}\n")
    for ch in JHS_CHANNELS:
        final_url = ch["url_template"].replace("{HDNTL}", hdntl_new)
        print(f"{BOLD_RED}LOGO{RESET}\n{ch['logo']}")
        print(f"{BOLD_GREEN}{ch['name']}{RESET}")
        print(f"{WHITE}{final_url}{RESET}")

    # ── Step 4: Ask to save jhs.txt at the end ────────────────────────
    save_ans = input(f"\n{BOLD_YELLOW}Save jhs.txt? (y/n): {RESET}").strip().lower()
    if save_ans == "y":
        out_file = input(f"Filename (default: jhs.txt): ").strip()
        if not out_file:
            out_file = "jhs.txt"
        try:
            with open(out_file, "w", encoding="utf-8") as fw:
                fw.write(output)
            print(f"{GREEN}✓ Saved {len(JHS_CHANNELS)} channels to: {out_file}{RESET}")
        except Exception as e:
            print(f"{RED}Failed to save: {e}{RESET}")


# ===================== MAIN =====================
def main():
    if len(sys.argv) > 1:
        input_url = sys.argv[1]
        print(f"{CYAN}CLI Mode: Using provided URL{RESET}")
        quality_choice = input(f"{BOLD_CYAN}Enter number ➤ {RESET}").strip()
    else:
        input_url = input("Enter Hotstar URL: ").strip()
        print(f"{BOLD_GREEN}{{1}} NORMAL 4K{RESET}")
        print(f"{BOLD_BLUE}{{2}} NORMAL FHD{RESET}")
        print(f"{BOLD_YELLOW}{{3}} ADS-FREE JHS HD{RESET}")
        print(f"{BOLD_MAGENTA}{{4}} JHS 4K{RESET}")
        print(f"{BOLD_CYAN}{{5}} ADS-FREE 4K PRIMARY{RESET}")
        print(f"{BOLD_RED}{{6}} DRM MPD + CLEARKEY / PSSH{RESET}")
        print(f"{BOLD_WHITE}{{7}} DRM NS PLAYER FORMAT{RESET}")
        print(f"{BOLD_GREEN}{{8}} DRM-TV {RESET}")
        print(f"{BOLD_YELLOW}{{9}} JHS ALL CHANNELS {RESET}")
        print(f"{BOLD_BLUE}{{10}} REFRESH TOKENS IN EXISTING M3U{RESET}")
        print(f"{BOLD_MAGENTA}{{11}} AUTO-UPDATE M3U (EVERY MINUTES){RESET}")
        quality_choice = input(f"{BOLD_CYAN}Enter number ➤ {RESET}").strip()
    if quality_choice == "8":
        slug_path = extract_slug_path(input_url)
        if not slug_path:
            print(f"{RED}Invalid Hotstar URL!{RESET}")
            return
        title, match_no = extract_match_title(input_url)
        stream_type = extract_stream_type(input_url)
        option8_direct_mpd(slug_path, title, match_no, stream_type, input_url=input_url)
        return
    if quality_choice == "9":
        option11_update_jhs(input_url=input_url)
        return
    if quality_choice == "10":
        option9_refresh_tokens()
        return
    if quality_choice == "11":
        auto_update_mode(input_url)
        return
    if quality_choice not in ["1","2","3","4","5","6","7"]:
        quality_choice = "2"
    slug_path = extract_slug_path(input_url)
    if not slug_path:
        print(f"{RED}Invalid URL!{RESET}")
        return
    title, match_no = extract_match_title(input_url)
    stream_type = extract_stream_type(input_url)
    print(f"{DARK_MAGENTA}FETCHING STREAMS... PLEASE WAIT{RESET}")
    playlist_entries = []
    logo_url = ""
    if quality_choice == "5":
        option5_main(input_url)
        return
    if quality_choice == "7":
        option7_main(slug_path, title, match_no, stream_type)
        return
    if quality_choice == "6":
        print(f"\n{BOLD_RED}LOGO{RESET}")
        logo_url_drm = ""
        try:
            api_url_drm = build_drm_api_url(slug_path, "eng")
            req0 = request.Request(api_url_drm, headers=build_headers())
            with request.urlopen(req0) as r0:
                d0 = json.loads(r0.read().decode("utf-8"))
            for sec in d0.get("success",{}).get("page",{}).get("spaces",{}).values():
                for w in sec.get("widget_wrappers",[]):
                    pc = w.get("widget",{}).get("data",{}).get("player_config")
                    if pc:
                        img = pc.get("expanded_content_poster",{}).get("image",{}).get("src") or pc.get("cast_image",{}).get("src")
                        if img:
                            logo_url_drm = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                            print(logo_url_drm)
                        break
        except: pass
        if match_no: print(f"{GREEN}{match_no}{RESET}")
        print(f"{BOLD_GREEN}{title}{RESET}")
        print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
        try:
            api_url_eng = build_drm_api_url(slug_path, "eng")
            req_eng = request.Request(api_url_eng, headers=build_headers())
            with request.urlopen(req_eng, timeout=10) as resp_eng:
                data_eng = json.loads(resp_eng.read().decode("utf-8"))
            player_config = None
            for sec in data_eng.get("success",{}).get("page",{}).get("spaces",{}).values():
                for w in sec.get("widget_wrappers",[]):
                    d = w.get("widget",{}).get("data",{})
                    if "player_config" in d:
                        player_config = d["player_config"]
                        break
                if player_config: break
            if not player_config:
                print(f"{RED}NO DRM STREAM FOUND ❌{RESET}")
                return
            drm_streams = extract_drm_info(player_config)
            if not drm_streams:
                print(f"{RED}NO DRM STREAM FOUND ❌{RESET}")
                return
            # ── Collect keys once (shared across PRIMARY/FALLBACK) ──────────────
            global_keys = []
            global_license = ""
            seen_mpds = set()
            for stream in drm_streams:
                lic = stream.get("license_url") or ""
                if lic:
                    global_license = lic
                    break
            # Try keys from first MPD
            first_mpd = drm_streams[0]["mpd_url"] if drm_streams else ""
            if first_mpd and global_license:
                try:
                    mpd_info0 = fetch_mpd_pssh(first_mpd)
                    if mpd_info0 and mpd_info0.get("key_ids"):
                        ck = try_clearkey_json(mpd_info0["key_ids"], global_license)
                        if ck:
                            global_keys = ck
                        elif mpd_info0.get("pssh"):
                            wv = fetch_widevine_keys(mpd_info0["pssh"], global_license)
                            if wv and not any(l.startswith("❌") for l in wv):
                                global_keys = wv
                except Exception:
                    pass
            key_str_global = ",".join(global_keys) if global_keys else global_license
            # ── Print PRIMARY then FALLBACK ─────────────────────────────────────
            m3u_lines = ["#EXTM3U", f"# Title: {title}", f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            # Order: PRIMARY first, FALLBACK second
            ordered_streams = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
            for stream in ordered_streams:
                mpd_url = stream["mpd_url"]
                mpd_base = mpd_url.split("?")[0]
                if mpd_base in seen_mpds:
                    continue
                seen_mpds.add(mpd_base)
                license_url = stream.get("license_url") or global_license
                variant = stream.get("variant", "")
                print(f"\n{BOLD_CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
                print(f"{BOLD_CYAN}[{variant}]{RESET}")
                print(f"{BOLD_YELLOW}MPD URL:{RESET}\n{GREEN}{mpd_url}{RESET}")
                if license_url:
                    print(f"{BOLD_YELLOW}LICENSE URL:{RESET}\n{CYAN}{license_url}{RESET}")
                else:
                    print(f"{BOLD_YELLOW}LICENSE URL:{RESET} {GRAY}not found{RESET}")
                # Detect available languages from this MPD
                print(f"{BOLD_YELLOW}Detecting languages...{RESET}", end=" ", flush=True)
                avail_langs = extract_mpd_languages(mpd_url)
                if avail_langs:
                    lang_names = ", ".join(n for _, n in avail_langs)
                    print(f"{GREEN}{lang_names}{RESET}")
                else:
                    # URL-based detection already tried inside extract_mpd_languages
                    avail_langs = [("unk", "STREAM")]
                    print(f"{YELLOW}Could not detect languages{RESET}")
                # Fetch PSSH/keys for this specific MPD
                print(f"{BOLD_YELLOW}Fetching MPD...{RESET}", end=" ", flush=True)
                mpd_info = fetch_mpd_pssh(mpd_url)
                if mpd_info["error"]:
                    print(f"{RED}Failed: {mpd_info['error']}{RESET}")
                    key_str = key_str_global
                else:
                    print(f"{GREEN}OK{RESET}")
                    if mpd_info["has_clearkey"]:
                        print(f"{BOLD_GREEN}⚡ ClearKey scheme detected!{RESET}")
                    if mpd_info["key_ids"]:
                        print(f"{BOLD_YELLOW}KEY IDs:{RESET}")
                        for kid in mpd_info["key_ids"]:
                            print(f"  {CYAN}{kid}{RESET}")
                    if mpd_info["pssh"]:
                        print(f"{BOLD_YELLOW}PSSH (Widevine):{RESET}\n  {CYAN}{mpd_info['pssh']}{RESET}")
                    # Try to get keys for this MPD
                    variant_keys = []
                    if license_url and mpd_info["key_ids"]:
                        print(f"{BOLD_YELLOW}Trying ClearKey...{RESET}", end=" ", flush=True)
                        ck_keys = try_clearkey_json(mpd_info["key_ids"], license_url)
                        if ck_keys:
                            variant_keys = ck_keys
                            print(f"{BOLD_GREEN}SUCCESS{RESET}")
                            print(f"{BOLD_GREEN}🔑 KEYS (kid:key):{RESET}")
                            for k in ck_keys:
                                print(f"  {BOLD_GREEN}{k}{RESET}")
                        else:
                            print(f"{YELLOW}No ClearKey response{RESET}")
                            if mpd_info["pssh"]:
                                print(f"{BOLD_YELLOW}Trying Widevine (pywidevine)...{RESET}", end=" ", flush=True)
                                wv_keys = fetch_widevine_keys(mpd_info["pssh"], license_url)
                                if any(l.startswith("❌") or l.startswith("⚠") for l in wv_keys):
                                    print(f"{RED}Failed{RESET}")
                                    for l in wv_keys:
                                        print(f"  {RED}{l}{RESET}")
                                else:
                                    variant_keys = wv_keys
                                    print(f"{BOLD_GREEN}SUCCESS{RESET}")
                                    print(f"{BOLD_GREEN}🔑 KEYS (kid:key):{RESET}")
                                    for k in wv_keys:
                                        print(f"  {BOLD_GREEN}{k}{RESET}")
                            else:
                                print(f"{YELLOW}⚠ No PSSH — cannot generate Widevine challenge{RESET}")
                    elif not license_url:
                        print(f"{YELLOW}⚠ No license URL{RESET}")
                    key_str = ",".join(variant_keys) if variant_keys else (key_str_global or license_url)
                    save_name = title.replace(" ", "_")
                    lic_part = " --key-text-file keys.txt --decryption-binary-path mp4decrypt" if license_url else ""
                    cmd = f'N_m3u8DL-RE "{mpd_url}" --auto-select --save-name "{save_name}"{lic_part}'
                    print(f"{BOLD_YELLOW}N_m3u8DL-RE Command:{RESET}\n  {DARK_CYAN}{cmd}{RESET}")
                # Build M3U entries — one per available language for this variant
                for _, lang_name in avail_langs:
                    entry_title = f"{lang_name} [{variant}] DRM"
                    m3u_lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_url_drm}" group-title="{title}", {entry_title}')
                    m3u_lines.append('#EXTHTTP:{"Origin":"https://www.hotstar.com","Referer":"https://www.hotstar.com/"}')
                    m3u_lines.append('#EXTVLCOPT:http-extra-headers=Origin: https://www.hotstar.com')
                    m3u_lines.append('#EXTVLCOPT:http-referrer=https://www.hotstar.com/')
                    m3u_lines.append('#KODIPROP:inputstream=inputstream.adaptive')
                    m3u_lines.append('#KODIPROP:inputstream.adaptive.manifest_type=mpd')
                    m3u_lines.append('#KODIPROP:inputstream.adaptive.license_type=com.widevine.alpha')
                    if key_str:
                        m3u_lines.append(f'#KODIPROP:inputstream.adaptive.license_key={key_str}')
                    m3u_lines.append(mpd_url)
                    m3u_lines.append("")
            # ── Build and offer OTT Navigator M3U ────────────────────────────────
            # Re-iterate drm_streams to build OTT lines (keys already fetched above; re-use key_str_global).
            ott_lines = ["#EXTM3U", f"# Title: {title}", f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            seen_ott = set()
            ordered_ott = sorted(drm_streams, key=lambda s: 0 if s["variant"] == "PRIMARY" else 1)
            for stream_ott in ordered_ott:
                mpd_url_ott = stream_ott["mpd_url"]
                mpd_base_ott = mpd_url_ott.split("?")[0]
                if mpd_base_ott in seen_ott:
                    continue
                seen_ott.add(mpd_base_ott)
                variant_ott = stream_ott.get("variant", "")
                license_url_ott = stream_ott.get("license_url") or global_license
                # Try to fetch keys for this MPD
                ks_ott = key_str_global
                try:
                    mi_ott = fetch_mpd_pssh(mpd_url_ott)
                    if mi_ott and mi_ott.get("key_ids") and license_url_ott:
                        ck_ott = try_clearkey_json(mi_ott["key_ids"], license_url_ott)
                        if ck_ott:
                            ks_ott = ",".join(ck_ott)
                        elif mi_ott.get("pssh"):
                            wv_ott = fetch_widevine_keys(mi_ott["pssh"], license_url_ott)
                            if wv_ott and not any(l.startswith("❌") for l in wv_ott):
                                ks_ott = ",".join(wv_ott)
                except Exception:
                    pass
                langs_ott = extract_mpd_languages(mpd_url_ott)
                if not langs_ott:
                    langs_ott = [("unk", "STREAM")]
                ott_url = build_ott_drm_url(mpd_url_ott, ks_ott)
                for _, lname_ott in langs_ott:
                    ott_entry = f"{lname_ott} [{variant_ott}] DRM"
                    ott_lines.append(f'#EXTINF:-1 tvg-id="" tvg-logo="{logo_url_drm}" group-title="{title}", {ott_entry}')
                    ott_lines.append(ott_url)
                    ott_lines.append("")
            if len(ott_lines) > 4:
                ott_fname = f"hotstar_ott_{title.replace(' ','_')}.m3u"
                ans_ott = input(f"\n{BOLD_CYAN}Save M3U? (y/n): {RESET}").strip().lower()
                if ans_ott == "y":
                    try:
                        with open(ott_fname, "w", encoding="utf-8") as fw:
                            fw.write("\n".join(ott_lines))
                        total_ott = len([l for l in ott_lines if l.startswith("#EXTINF")])
                        print(f"{GREEN}✓ M3U saved: {ott_fname} ({total_ott} entries){RESET}")
                    except Exception as e:
                        print(f"{RED}Failed to write M3U: {e}{RESET}")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
        return
    if quality_choice == "3":
        print(f"\n{BOLD_RED}LOGO{RESET}")
        try:
            first_api = build_jhs_api_url(slug_path, "eng")
            req0 = request.Request(first_api, headers=build_jhs_headers_android())
            with request.urlopen(req0) as r0:
                d0 = json.loads(r0.read().decode("utf-8"))
            for sec in d0.get("success", {}).get("page", {}).get("spaces", {}).values():
                for w in sec.get("widget_wrappers", []):
                    pc = w.get("widget", {}).get("data", {}).get("player_config")
                    if pc:
                        img = pc.get("expanded_content_poster", {}).get("image", {}).get("src") or pc.get("cast_image", {}).get("src")
                        if img:
                            logo_url = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                            print(f"https://img10.hotstar.com/image/upload/f_auto/{img}")
                        break
        except:
            pass
        if match_no:
            print(f"{GREEN}{match_no}{RESET}")
        print(f"{BOLD_GREEN}{title}{RESET}")
        print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
        seen_urls = set()
        seen_lang_names = set()
        results_lock = __import__('threading').Lock()
        PRIMARY_CODES = [
            ("eng","ENGLISH"),("en","ENGLISH"),("hin","HINDI"),("hi","HINDI"),("hd","HINDI HD"),
            ("mar","MARATHI"),("mr","MARATHI"),("ma","MARATHI"),("guj","GUJARATI"),("gu","GUJARATI"),
            ("bho","BHOJPURI"),("bh","BHOJPURI"),("bih","BHOJPURI"),("pan","PUNJABI"),("pun","PUNJABI"),
            ("pa","PUNJABI"),("pu","PUNJABI"),("har","HARYANVI"),("hv","HARYANVI"),("ha","HARYANVI"),
            ("tam","TAMIL"),("ta","TAMIL"),("tel","TELUGU"),("te","TELUGU"),("kan","KANNADA"),("kn","KANNADA"),
            ("mal","MALAYALAM"),("ml","MALAYALAM"),("ben","BENGALI"),("bn","BENGALI"),("ori","ORIYA"),("or","ORIYA")
        ]
        FALLBACK_CODES = {
            "ENGLISH":["en","eng"],"HINDI":["hi","hd","hin"],"MARATHI":["mr","ma","mar"],"GUJARATI":["gu","guj"],
            "BHOJPURI":["bho","bh","bih"],"PUNJABI":["pan","pun","pa","pu"],"HARYANVI":["hv","ha","har"],
            "TAMIL":["ta","tam"],"TELUGU":["te","tel"],"KANNADA":["kn","kan"],"MALAYALAM":["ml","mal"],
            "BENGALI":["bn","ben"],"ORIYA":["or","ori"]
        }
        # Dedup PRIMARY_CODES by lang_name - keeps all variant codes in fallback map
        _seen_pc = set()
        PRIMARY_CODES_UNIQUE = [(_c,_n) for _c,_n in PRIMARY_CODES if not (_n in _seen_pc or _seen_pc.add(_n))]
        lang_codes_map = {name: [code] + FALLBACK_CODES.get(name, []) for code, name in PRIMARY_CODES_UNIQUE}
        def fetch_jhs_lang(lang_name, codes):
            is_live = stream_type == "LIVE TV"
            for lang_code in codes:
                try:
                    api_url = build_jhs_api_url(slug_path, lang_code, is_live=is_live)
                    req = request.Request(api_url, headers=build_jhs_headers_android())
                    with request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    player_config = None
                    page_spaces = data.get("success", {}).get("page", {}).get("spaces", {})
                    for sec in page_spaces.values():
                        for w in sec.get("widget_wrappers", []):
                            d = w.get("widget", {}).get("data", {})
                            if "player_config" in d:
                                player_config = d["player_config"]
                                break
                        if player_config:
                            break
                    if not player_config:
                        continue
                    streams = extract_jhs_fallback_only(player_config)
                    for s in streams:
                        url = s.get("content_url")
                        if not url:
                            continue
                        base_url = url.split("?")[0]
                        if is_live:
                            tags = s.get("playback_tags", "") or ""
                            detected_lang = ""
                            for tag in tags.split(";"):
                                if tag.startswith("language:"):
                                    detected_lang = tag.split(":")[1].strip().lower()
                                    break
                            if detected_lang and detected_lang != lang_code.lower():
                                continue
                            display_lang = LANGUAGES.get(detected_lang, lang_name) if detected_lang else lang_name
                        else:
                            display_lang = lang_name
                            if stream_type not in ["MOVIE","TV SHOW"]:
                                path_set = set(base_url.replace("https://","").split("/"))
                                lang_in_url = any(c.lower() in path_set for c in codes)
                                if not lang_in_url:
                                    continue
                        clean_url = url.split("?")[0] if stream_type in ["HIGHLIGHTS","CLIP"] else url
                        is_hdr = "hdr" in url.lower() or "hdr" in str(s.get("playback_tags", "")).lower()
                        return (display_lang, clean_url, is_hdr)
                except:
                    continue
            return None
        with ThreadPoolExecutor(max_workers=4) as jhs_executor:
            jhs_futures = {jhs_executor.submit(fetch_jhs_lang, name, codes): name for name, codes in lang_codes_map.items()}
            for future in as_completed(jhs_futures):
                result = future.result()
                if not result:
                    continue
                lang_name, clean_url, is_hdr = result
                with results_lock:
                    if clean_url not in seen_urls and lang_name not in seen_lang_names:
                        seen_urls.add(clean_url)
                        seen_lang_names.add(lang_name)
                        hdr_tag = " HDR" if is_hdr else ""
                        print(f"{BOLD_CYAN}{lang_name}{hdr_tag} FHD ✓{RESET}")
                        print(f"{GREEN}{clean_url}{RESET}")
                        playlist_entries.append((lang_name, clean_url, is_hdr))
        if not seen_lang_names:
            print(f"{RED}NO ADSFREE STREAM FOUND ❌{RESET}")
        offer_m3u_creation(playlist_entries, title, match_no, stream_type, logo_url)
        print()
        return
    if quality_choice == "4":
        print(f"\n{BOLD_RED}LOGO{RESET}")
        try:
            first_api = build_jhs_4k_api_url(slug_path, "eng")
            req0 = request.Request(first_api, headers=build_jhs_headers())
            with request.urlopen(req0) as r0:
                d0 = json.loads(r0.read().decode("utf-8"))
            for sec in d0.get("success", {}).get("page", {}).get("spaces", {}).values():
                for w in sec.get("widget_wrappers", []):
                    pc = w.get("widget", {}).get("data", {}).get("player_config")
                    if pc:
                        img = pc.get("expanded_content_poster", {}).get("image", {}).get("src") or pc.get("cast_image", {}).get("src")
                        if img:
                            logo_url = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                            print(f"https://img10.hotstar.com/image/upload/f_auto/{img}")
                        break
        except:
            pass
        if match_no:
            print(f"{GREEN}{match_no}{RESET}")
        print(f"{BOLD_GREEN}{title}{RESET}")
        print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
        seen_urls = set()
        seen_lang_names = set()
        results_lock = __import__('threading').Lock()
        ordered_results = {}
        PRIMARY_CODES = [
            ("eng","ENGLISH"),("en","ENGLISH"),("hin","HINDI"),("hi","HINDI"),("hd","HINDI HD"),
            ("mar","MARATHI"),("mr","MARATHI"),("ma","MARATHI"),("guj","GUJARATI"),("gu","GUJARATI"),
            ("bho","BHOJPURI"),("bh","BHOJPURI"),("bih","BHOJPURI"),("pan","PUNJABI"),("pun","PUNJABI"),
            ("pa","PUNJABI"),("pu","PUNJABI"),("har","HARYANVI"),("hv","HARYANVI"),("ha","HARYANVI"),
            ("tam","TAMIL"),("ta","TAMIL"),("tel","TELUGU"),("te","TELUGU"),("kan","KANNADA"),("kn","KANNADA"),
            ("mal","MALAYALAM"),("ml","MALAYALAM"),("ben","BENGALI"),("bn","BENGALI"),("ori","ORIYA"),("or","ORIYA")
        ]
        # Dedup by lang_name
        _seen_4k = set()
        PRIMARY_CODES = [(_c,_n) for _c,_n in PRIMARY_CODES if not (_n in _seen_4k or _seen_4k.add(_n))]
        def fetch_jhs4k_single(lang_code, lang_name):
            is_live = stream_type == "LIVE TV"
            try:
                api_url = build_jhs_4k_api_url(slug_path, lang_code, is_live=is_live)
                req = request.Request(api_url, headers=build_jhs_headers())
                with request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                player_config = None
                page_spaces = data.get("success", {}).get("page", {}).get("spaces", {})
                for sec in page_spaces.values():
                    for w in sec.get("widget_wrappers", []):
                        d = w.get("widget", {}).get("data", {})
                        if "player_config" in d:
                            player_config = d["player_config"]
                            break
                    if player_config:
                        break
                if not player_config:
                    return None
                streams_4k = extract_4k_streams(player_config)
                if streams_4k:
                    url = streams_4k[0]["url"]
                    base_url = url.split("?")[0]
                    clean_url = url if stream_type not in ["HIGHLIGHTS","CLIP"] else base_url
                    is_hdr = "hdr" in url.lower() or "hdr" in str(streams_4k[0].get("playback_tags", "")).lower()
                    return (lang_name, clean_url, is_hdr, True)
                streams = extract_jhs_fallback_only(player_config)
                for s in streams:
                    url = s.get("content_url")
                    if not url:
                        continue
                    base_url = url.split("?")[0]
                    if is_live:
                        tags = s.get("playback_tags", "") or ""
                        detected_lang = ""
                        for tag in tags.split(";"):
                            if tag.startswith("language:"):
                                detected_lang = tag.split(":")[1].strip().lower()
                                break
                        if detected_lang and detected_lang != lang_code.lower():
                            continue
                        display_lang = LANGUAGES.get(detected_lang, lang_name) if detected_lang else lang_name
                    else:
                        display_lang = lang_name
                        if stream_type not in ["MOVIE","TV SHOW"]:
                            path_set = set(base_url.replace("https://","").split("/"))
                            if lang_code.lower() not in path_set:
                                continue
                    clean_url = url.split("?")[0] if stream_type in ["HIGHLIGHTS","CLIP"] else url
                    is_hdr = "hdr" in url.lower() or "hdr" in str(s.get("playback_tags", "")).lower()
                    return (display_lang, clean_url, is_hdr, False)
            except:
                return None
        with ThreadPoolExecutor(max_workers=4) as jhs4k_executor:
            jhs4k_futures = {jhs4k_executor.submit(fetch_jhs4k_single, code, name): (code,name) for code,name in PRIMARY_CODES}
            for future in as_completed(jhs4k_futures):
                result = future.result()
                if not result:
                    continue
                lang_name, clean_url, is_hdr, is_4k = result
                with results_lock:
                    if clean_url not in seen_urls and lang_name not in seen_lang_names:
                        seen_urls.add(clean_url)
                        seen_lang_names.add(lang_name)
                        ordered_results[lang_name] = (clean_url, is_hdr)
        printed_names = set()
        for code,name in LANGUAGES.items():
            if name in ordered_results and name not in printed_names:
                clean_url, is_hdr = ordered_results[name]
                hdr_tag = " HDR" if is_hdr else ""
                label = f"{BOLD_CYAN}{name}{hdr_tag}{RESET}" + f" {DARK_BLUE}4K{RESET}"
                print(label)
                print(f"{GREEN}{clean_url}{RESET}")
                printed_names.add(name)
                playlist_entries.append((name, clean_url, is_hdr))
        if not seen_lang_names:
            print(f"{RED}NO JHS 4K STREAM FOUND ❌{RESET}")
        offer_m3u_creation(playlist_entries, title, match_no, stream_type, logo_url)
        print()
        return
    # Options 1 & 2
    lang_streams = {}
    seen_stream_bases = set()
    logo_printed = False
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(fetch_lang_stream, lang_code, lang_name, slug_path, input_url, quality_choice): lang_name
            for lang_code, lang_name in LANGUAGES.items()
        }
        for future in as_completed(futures):
            result = future.result()
            if not result:
                continue
            lang_name = result["lang_name"]
            stream_base = result["stream"].split("?")[0]
            if lang_name in lang_streams or stream_base in seen_stream_bases:
                continue
            lang_streams[lang_name] = result
            seen_stream_bases.add(stream_base)
            if not logo_printed:
                first_config = result["player_config"]
                img = first_config.get("expanded_content_poster", {}).get("image", {}).get("src") or first_config.get("cast_image", {}).get("src")
                if img:
                    logo_url = f"https://img10.hotstar.com/image/upload/f_auto/{img}"
                print(f"\n{BOLD_RED}LOGO{RESET}")
                if img:
                    print(f"https://img10.hotstar.com/image/upload/f_auto/{img}")
                if match_no:
                    print(f"{GREEN}{match_no}{RESET}")
                print(f"{BOLD_GREEN}{title}{RESET}")
                print(f"{BOLD_MAGENTA}{stream_type}{RESET}")
                logo_printed = True
    for lang_name, res in lang_streams.items():
        clean_stream = res["stream"]
        is_hdr = res.get("is_hdr", False)
        hdr_tag = " HDR" if is_hdr else ""
        print(f"{BOLD_CYAN}{lang_name}{hdr_tag}{RESET}")
        playlist_entries.append((lang_name, clean_stream, is_hdr))
        if quality_choice == "1":
            streams_4k = extract_4k_streams(res["player_config"])
            if streams_4k:
                printed = set()
                for s in streams_4k:
                    clean_url = s["url"].split("?")[0]
                    if clean_url in printed:
                        continue
                    printed.add(clean_url)
                    url_to_print = s["url"]
                    if stream_type in ["HIGHLIGHTS","CLIP"]:
                        print(url_to_print.split("?")[0])
                    else:
                        if "star-sports-hindi-1" in input_url:
                            hdntl_token = extract_hdntl(url_to_print)
                            print(build_ott_url(url_to_print, hdntl_token))
                        else:
                            print(url_to_print)
            else:
                print(f"{BOLD_RED}FHD ✓{RESET}")
                if "star-sports-hindi-1" in input_url:
                    hdntl_token = extract_hdntl(clean_stream)
                    print(build_ott_url(clean_stream, hdntl_token))
                else:
                    print(clean_stream)
        else:
            if "star-sports-hindi-1" in input_url:
                hdntl_token = extract_hdntl(clean_stream)
                print(build_ott_url(clean_stream, hdntl_token))
            else:
                print(clean_stream)
    # Add SDR variants for English/Hindi if HDR exists
    sdr_entries = []
    for lang_name, url, is_hdr in playlist_entries:
        if lang_name in ["ENGLISH", "HINDI"] and is_hdr:
            sdr_url = url.replace("hdr", "sdr").replace("HDR", "sdr")
            if sdr_url != url:
                sdr_entries.append((f"{lang_name} (SDR)", sdr_url, False))
    playlist_entries.extend(sdr_entries)
    # ── Auto-extract hdntl cookie from stream URL (like Option 8) ──────
    _auto_hdntl = ""
    for _ln, _lu, _lh in playlist_entries:
        try:
            _tok = get_hdntl_token_1(_lu)
            if _tok:
                _auto_hdntl = _tok
                break
        except Exception:
            pass
    if _auto_hdntl:
        print(f"\n{BOLD_GREEN}Cookie  : {RESET}{CYAN}hdntl={_auto_hdntl}{RESET}")
    offer_m3u_creation(playlist_entries, title, match_no, stream_type, logo_url, auto_hdntl=_auto_hdntl)
    print()

if __name__ == "__main__":
    main()

# ===================== GITHUB ACTIONS CRON MODE =====================

def github_cron_main():
    if not HOTSTAR_URL:
        raise Exception("HOTSTAR_URL missing")

    title, match_no = extract_match_title(HOTSTAR_URL)
    stream_type = extract_stream_type(HOTSTAR_URL)

    print(f"Fetching streams for: {title}")

    entries = get_option5_entries(HOTSTAR_URL)

    if not entries:
        raise Exception("No streams extracted")

    logo_url = extract_logo_from_url(HOTSTAR_URL)

    output_file = "playlist.m3u"

    create_m3u_file(
        entries,
        title,
        match_no,
        stream_type,
        filename=output_file,
        logo_url=logo_url
    )

    print("Playlist updated successfully")


if __name__ == "__main__":
    github_cron_main()
