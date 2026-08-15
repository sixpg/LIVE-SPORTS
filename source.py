import json
import os
import requests


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_M3U = "events.m3u"

# Main JSON URL is stored in GitHub Actions Secrets
SOURCE_URL = os.environ.get("SOURCE_URL")

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*"
}


# ============================================================
# FETCH JSON
# ============================================================

def fetch_json(url):
    """
    Fetch JSON from a URL.
    """

    try:
        print(f"[FETCH] {url}")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:

        print(f"[ERROR] Request failed:")
        print(f"        {url}")
        print(f"        {e}")

        return None

    except ValueError as e:

        print(f"[ERROR] Invalid JSON:")
        print(f"        {url}")
        print(f"        {e}")

        return None

    except Exception as e:

        print(f"[ERROR] Unexpected error:")
        print(f"        {url}")
        print(f"        {e}")

        return None


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):
    """
    Clean text for M3U.
    """

    if value is None:
        return ""

    value = str(value)

    # Remove unwanted surrounding whitespace
    value = value.strip()

    # Collapse multiple spaces
    value = " ".join(value.split())

    # Avoid breaking M3U attributes
    value = value.replace('"', "'")

    return value


# ============================================================
# PARSE STREAM LINK
# ============================================================

def parse_stream_link(link):
    """
    Converts:

    https://example.com/live.m3u8

    OR:

    https://example.com/live.m3u8|Referer=https://example.com&Origin=https://example.com

    into:

    stream_url
    headers
    """

    if not link:
        return "", {}

    parts = link.split("|", 1)

    stream_url = parts[0].strip()

    headers = {}

    if len(parts) == 1:
        return stream_url, headers

    header_string = parts[1].strip()

    if not header_string:
        return stream_url, headers

    # Headers are separated by &
    for item in header_string.split("&"):

        item = item.strip()

        if not item:
            continue

        if "=" not in item:
            continue

        key, value = item.split("=", 1)

        key = key.strip()
        value = value.strip()

        if key:
            headers[key] = value

    return stream_url, headers


# ============================================================
# CONVERT HEADERS TO M3U FORMAT
# ============================================================

def headers_to_string(headers):
    """
    Example:

    {
        "Referer": "https://example.com",
        "Origin": "https://example.com"
    }

    becomes:

    Referer=https://example.com&Origin=https://example.com
    """

    if not headers:
        return ""

    return "&".join(
        f"{key}={value}"
        for key, value in headers.items()
    )


# ============================================================
# DETECT STREAM TYPE
# ============================================================

def detect_stream_type(url, stream_type):
    """
    Detect HLS or DASH.
    """

    url_lower = url.lower()

    # URL takes priority
    if ".mpd" in url_lower:
        return "DASH"

    if ".m3u8" in url_lower:
        return "HLS"

    # type 7 in your API = DASH
    if str(stream_type) == "7":
        return "DASH"

    return "HLS"


# ============================================================
# EVENT STATUS PRIORITY
# ============================================================

def event_priority(event):
    """
    Sorting:

    0 = LIVE
    1 = UPCOMING
    2 = everything else
    """

    status = str(
        event.get("status", "")
    ).lower().strip()

    if status == "live":
        return 0

    if status == "upcoming":
        return 1

    return 2


# ============================================================
# GET EVENT GROUP
# ============================================================

def get_event_group(event):
    """
    Every event gets its own group.

    Example:

    Formula 1 -> Formula 1
    Premier League -> Premier League
    Wimbledon -> Wimbledon
    """

    title = event.get(
        "title",
        "Unknown Event"
    )

    return clean_text(title)


# ============================================================
# GET EVENT LOGO
# ============================================================

def get_event_logo(event):

    event_info = event.get(
        "eventInfo"
    )

    if not isinstance(event_info, dict):
        event_info = {}

    # Prefer eventLogo
    logo = event_info.get(
        "eventLogo",
        ""
    )

    # Fall back to image
    if not logo:
        logo = event.get(
            "image",
            ""
        )

    # Remove fake/null values
    if str(logo).lower() in [
        "null",
        "nulln",
        "none",
        ""
    ]:
        return ""

    return str(logo).strip()


# ============================================================
# PROCESS EVENTS
# ============================================================

def convert_events(events):

    # --------------------------------------------------------
    # SORT
    # LIVE FIRST
    # UPCOMING SECOND
    # OTHER LAST
    # --------------------------------------------------------

    events = sorted(
        events,
        key=event_priority
    )

    print()
    print("========================================")
    print("EVENT ORDER")
    print("========================================")

    for index, event in enumerate(events, start=1):

        title = clean_text(
            event.get(
                "title",
                "Unknown Event"
            )
        )

        status = str(
            event.get(
                "status",
                "unknown"
            )
        ).upper()

        print(
            f"{index:03d}. [{status}] {title}"
        )

    print("========================================")
    print()

    # --------------------------------------------------------
    # M3U HEADER
    # --------------------------------------------------------

    m3u = []

    m3u.append(
        "#EXTM3U"
    )

    total_events = 0
    total_streams = 0
    live_events = 0
    upcoming_events = 0

    # --------------------------------------------------------
    # PROCESS EACH EVENT
    # --------------------------------------------------------

    for event in events:

        if not isinstance(event, dict):
            continue

        # ----------------------------------------------------
        # EVENT INFORMATION
        # ----------------------------------------------------

        event_id = clean_text(
            event.get(
                "id",
                ""
            )
        )

        event_title = clean_text(
            event.get(
                "title",
                "Unknown Event"
            )
        )

        status = str(
            event.get(
                "status",
                ""
            )
        ).lower().strip()

        group = get_event_group(
            event
        )

        logo = get_event_logo(
            event
        )

        channel_url = event.get(
            "channelUrl"
        )

        # ----------------------------------------------------
        # COUNT STATUS
        # ----------------------------------------------------

        if status == "live":
            live_events += 1

        elif status == "upcoming":
            upcoming_events += 1

        # ----------------------------------------------------
        # CHANNEL URL CHECK
        # ----------------------------------------------------

        if not channel_url:

            print(
                f"[SKIP] {event_title}"
            )

            print(
                "       No channelUrl"
            )

            continue

        # ----------------------------------------------------
        # FETCH CHANNEL JSON
        # ----------------------------------------------------

        channel_data = fetch_json(
            channel_url
        )

        if not channel_data:

            print(
                f"[SKIP] {event_title}"
            )

            print(
                "       Could not fetch channel JSON"
            )

            continue

        # ----------------------------------------------------
        # GET STREAM URLS
        # ----------------------------------------------------

        stream_urls = channel_data.get(
            "streamUrls",
            []
        )

        if not isinstance(
            stream_urls,
            list
        ):

            print(
                f"[SKIP] {event_title}"
            )

            print(
                "       streamUrls is not a list"
            )

            continue

        if not stream_urls:

            print(
                f"[SKIP] {event_title}"
            )

            print(
                "       No streams found"
            )

            continue

        total_events += 1

        print(
            f"[EVENT] {event_title}"
        )

        print(
            f"        Status  : {status.upper()}"
        )

        print(
            f"        Group   : {group}"
        )

        print(
            f"        Streams : {len(stream_urls)}"
        )

        # ----------------------------------------------------
        # PROCESS EVERY STREAM
        # ----------------------------------------------------

        for stream in stream_urls:

            if not isinstance(
                stream,
                dict
            ):
                continue

            stream_title = clean_text(
                stream.get(
                    "title",
                    "Stream"
                )
            )

            link = str(
                stream.get(
                    "link",
                    ""
                )
            ).strip()

            api = str(
                stream.get(
                    "api",
                    ""
                )
            ).strip()

            stream_type = stream.get(
                "type",
                "0"
            )

            # ------------------------------------------------
            # NO LINK
            # ------------------------------------------------

            if not link:

                print(
                    f"        [SKIP] "
                    f"{stream_title}: no link"
                )

                continue

            # ------------------------------------------------
            # PARSE LINK + HEADERS
            # ------------------------------------------------

            stream_url, headers = (
                parse_stream_link(
                    link
                )
            )

            if not stream_url:

                continue

            # ------------------------------------------------
            # DETECT TYPE
            # ------------------------------------------------

            detected_type = (
                detect_stream_type(
                    stream_url,
                    stream_type
                )
            )

            # ------------------------------------------------
            # STREAM NAME
            # ------------------------------------------------

            stream_name = clean_text(
                f"{event_title} | {stream_title}"
            )

            # ------------------------------------------------
            # EXTINF
            # ------------------------------------------------

            extinf = (
                f'#EXTINF:-1 '
                f'tvg-id="{event_id}" '
                f'tvg-name="{stream_name}" '
                f'tvg-logo="{logo}" '
                f'group-title="{group}",'
                f'{stream_name}'
            )

            m3u.append(
                extinf
            )

            # ------------------------------------------------
            # DASH
            # ------------------------------------------------

            if detected_type == "DASH":

                m3u.append(
                    "#KODIPROP:"
                    "inputstream.adaptive."
                    "manifest_type=mpd"
                )

                # ------------------------------------------------
                # CLEARKEY
                # ------------------------------------------------

                if api:

                    m3u.append(
                        "#KODIPROP:"
                        "inputstream.adaptive."
                        "license_type=clearkey"
                    )

                    m3u.append(
                        "#KODIPROP:"
                        "inputstream.adaptive."
                        f"license_key={api}"
                    )

            # ------------------------------------------------
            # STREAM HEADERS
            # ------------------------------------------------

            if headers:

                header_string = (
                    headers_to_string(
                        headers
                    )
                )

                m3u.append(
                    "#KODIPROP:"
                    "inputstream.adaptive."
                    f"stream_headers={header_string}"
                )

            # ------------------------------------------------
            # STREAM URL
            # ------------------------------------------------

            m3u.append(
                stream_url
            )

            m3u.append("")

            total_streams += 1

            print(
                f"        [+] "
                f"{stream_title} "
                f"({detected_type})"
            )

    # --------------------------------------------------------
    # RETURN M3U
    # --------------------------------------------------------

    return (
        "\n".join(m3u),
        total_events,
        total_streams,
        live_events,
        upcoming_events
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("========================================")
    print("       JSON → M3U CONVERTER")
    print("========================================")

    # --------------------------------------------------------
    # CHECK SOURCE URL
    # --------------------------------------------------------

    if not SOURCE_URL:

        raise SystemExit(
            "ERROR: SOURCE_URL environment variable "
            "is not set."
        )

    print(
        f"[SOURCE] {SOURCE_URL}"
    )

    print()

    # --------------------------------------------------------
    # FETCH MAIN JSON
    # --------------------------------------------------------

    data = fetch_json(
        SOURCE_URL
    )

    if data is None:

        raise SystemExit(
            "ERROR: Could not fetch main JSON."
        )

    # --------------------------------------------------------
    # FIND EVENTS
    # --------------------------------------------------------

    if isinstance(
        data,
        list
    ):

        events = data

    elif isinstance(
        data,
        dict
    ):

        # Common structures

        if isinstance(
            data.get("events"),
            list
        ):

            events = data["events"]

        elif isinstance(
            data.get("data"),
            list
        ):

            events = data["data"]

        elif isinstance(
            data.get("results"),
            list
        ):

            events = data["results"]

        else:

            raise SystemExit(
                "ERROR: Could not find event list "
                "in the JSON."
            )

    else:

        raise SystemExit(
            "ERROR: Invalid JSON structure."
        )

    print(
        f"[INFO] Events found: {len(events)}"
    )

    print()

    # --------------------------------------------------------
    # CONVERT
    # --------------------------------------------------------

    (
        m3u,
        total_events,
        total_streams,
        live_events,
        upcoming_events
    ) = convert_events(
        events
    )

    # --------------------------------------------------------
    # WRITE FILE
    # --------------------------------------------------------

    with open(
        OUTPUT_M3U,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            m3u
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("========================================")
    print("          CONVERSION COMPLETE")
    print("========================================")
    print(
        f"Live events     : {live_events}"
    )
    print(
        f"Upcoming events : {upcoming_events}"
    )
    print(
        f"Events processed: {total_events}"
    )
    print(
        f"Streams created : {total_streams}"
    )
    print(
        f"Output file     : {OUTPUT_M3U}"
    )
    print("========================================")
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
