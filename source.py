import json
import requests
from urllib.parse import urlparse

# ============================================================
# CONFIG
# ============================================================

INPUT_JSON = "events.json"
OUTPUT_M3U = "events.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/149.0.0.0 Safari/537.36"
}

TIMEOUT = 20


# ============================================================
# HELPERS
# ============================================================

def fetch_json(url):
    """Fetch JSON from URL."""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"[ERROR] Failed to fetch: {url}")
        print(f"        {e}")
        return None


def escape_m3u(value):
    """Make text safe for M3U attributes."""

    if value is None:
        return ""

    return str(value).replace('"', "'").strip()


def parse_stream_link(link):
    """
    Converts:

    URL|Referer=https://example.com&Origin=https://example.com

    into:

    URL
    headers = {
        "Referer": "...",
        "Origin": "..."
    }
    """

    if not link:
        return "", {}

    parts = link.split("|", 1)

    stream_url = parts[0].strip()

    if len(parts) == 1:
        return stream_url, {}

    header_string = parts[1]

    headers = {}

    # Supports both & and multiple header separators
    for item in header_string.split("&"):

        if "=" not in item:
            continue

        key, value = item.split("=", 1)

        key = key.strip()
        value = value.strip()

        if key:
            headers[key] = value

    return stream_url, headers


def headers_to_m3u(headers):
    """
    Convert headers into Kodi inputstream header format.

    Example:

    User-Agent=...
    Referer=https://...
    Origin=https://...

    becomes:

    User-Agent=...&Referer=https://...&Origin=https://...
    """

    if not headers:
        return ""

    return "&".join(
        f"{key}={value}"
        for key, value in headers.items()
    )


def detect_stream_type(stream_url, stream_type):
    """
    Returns HLS or DASH.
    """

    url_lower = stream_url.lower()

    if ".mpd" in url_lower:
        return "DASH"

    if ".m3u8" in url_lower:
        return "HLS"

    if str(stream_type) == "7":
        return "DASH"

    return "HLS"


# ============================================================
# M3U GENERATION
# ============================================================

def create_m3u(events):
    output = []

    output.append("#EXTM3U")

    total_events = 0
    total_streams = 0

    for event in events:

        if not isinstance(event, dict):
            continue

        event_id = event.get("id", "")
        event_title = event.get("title", "Unknown Event")
        event_image = event.get("image", "")
        category = event.get("cat", "Live Events")

        event_info = event.get("eventInfo") or {}

        event_logo = event_info.get("eventLogo", "")

        # Prefer eventLogo
        logo = event_logo or event_image

        # Ignore literal null strings
        if logo in ("null", "nulln", "None"):
            logo = ""

        channel_url = event.get("channelUrl")

        if not channel_url:
            print(
                f"[SKIP] {event_title} "
                f"(no channelUrl)"
            )
            continue

        # ----------------------------------------------------
        # Fetch stream JSON
        # ----------------------------------------------------

        channel_data = fetch_json(channel_url)

        if not channel_data:
            continue

        stream_urls = channel_data.get("streamUrls", [])

        if not isinstance(stream_urls, list):
            print(
                f"[SKIP] {event_title}: "
                f"streamUrls is not a list"
            )
            continue

        total_events += 1

        # ----------------------------------------------------
        # Process streams
        # ----------------------------------------------------

        for stream in stream_urls:

            if not isinstance(stream, dict):
                continue

            stream_title = stream.get(
                "title",
                "Stream"
            ).strip()

            link = stream.get("link", "").strip()

            api = stream.get("api", "").strip()

            stream_type = stream.get("type", "0")

            if not link:
                print(
                    f"[SKIP] {event_title} / "
                    f"{stream_title}: no link"
                )
                continue

            stream_url, headers = parse_stream_link(link)

            if not stream_url:
                continue

            detected_type = detect_stream_type(
                stream_url,
                stream_type
            )

            # ------------------------------------------------
            # M3U attributes
            # ------------------------------------------------

            group = escape_m3u(category)
            name = escape_m3u(
                f"{event_title} | {stream_title}"
            )
            logo_safe = escape_m3u(logo)

            output.append(
                f'#EXTINF:-1 tvg-id="{escape_m3u(event_id)}" '
                f'tvg-name="{name}" '
                f'tvg-logo="{logo_safe}" '
                f'group-title="{group}",'
                f'{name}'
            )

            # ------------------------------------------------
            # DASH / ClearKey
            # ------------------------------------------------

            if detected_type == "DASH":

                output.append(
                    '#KODIPROP:inputstream.adaptive.manifest_type=mpd'
                )

                # api is already:
                # KID:KEY

                if api:

                    output.append(
                        '#KODIPROP:inputstream.adaptive.license_type=clearkey'
                    )

                    output.append(
                        f'#KODIPROP:inputstream.adaptive.license_key={api}'
                    )

            # ------------------------------------------------
            # Headers
            # ------------------------------------------------

            if headers:

                header_string = headers_to_m3u(headers)

                output.append(
                    f'#KODIPROP:inputstream.adaptive.stream_headers={header_string}'
                )

            # ------------------------------------------------
            # Stream URL
            # ------------------------------------------------

            output.append(stream_url)

            output.append("")

            total_streams += 1

    print()
    print("=" * 60)
    print(f"Events processed : {total_events}")
    print(f"Streams created  : {total_streams}")
    print("=" * 60)

    return "\n".join(output)


# ============================================================
# MAIN
# ============================================================

def main():

    print("[INFO] Loading events JSON...")

    try:
        with open(
            INPUT_JSON,
            "r",
            encoding="utf-8"
        ) as f:

            events = json.load(f)

    except Exception as e:

        print(
            f"[ERROR] Could not read {INPUT_JSON}: {e}"
        )

        return

    # Some APIs return {"events": [...]}
    if isinstance(events, dict):

        if "events" in events:
            events = events["events"]

        elif "data" in events:
            events = events["data"]

    if not isinstance(events, list):

        print(
            "[ERROR] Expected a JSON array of events."
        )

        return

    print(
        f"[INFO] Found {len(events)} events"
    )

    m3u = create_m3u(events)

    with open(
        OUTPUT_M3U,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(m3u)

    print(
        f"[SUCCESS] Created {OUTPUT_M3U}"
    )


if __name__ == "__main__":
    main()
