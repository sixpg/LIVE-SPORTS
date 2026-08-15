import json
import os
import requests

OUTPUT_M3U = "events.m3u"

SOURCE_URL = os.environ["SOURCE_URL"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*"
}

TIMEOUT = 30


def fetch_json(url):
    try:
        print(f"[FETCH] {url}")

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        r.raise_for_status()

        return r.json()

    except Exception as e:
        print(f"[ERROR] {url}")
        print(f"        {e}")
        return None


def parse_link(link):
    """
    Example:

    https://example.com/live.m3u8|Referer=https://example.com&Origin=https://example.com

    Returns:

    URL
    headers
    """

    parts = link.split("|", 1)

    url = parts[0].strip()

    headers = {}

    if len(parts) > 1:

        for item in parts[1].split("&"):

            if "=" in item:

                key, value = item.split("=", 1)

                headers[key.strip()] = value.strip()

    return url, headers


def make_header_string(headers):

    return "&".join(
        f"{k}={v}"
        for k, v in headers.items()
    )


def stream_type(url, typ):

    url_lower = url.lower()

    if ".mpd" in url_lower:
        return "DASH"

    if ".m3u8" in url_lower:
        return "HLS"

    if str(typ) == "7":
        return "DASH"

    return "HLS"


def main():

    print("========================================")
    print(" JSON → M3U CONVERTER")
    print("========================================")

    # ------------------------------------
    # FETCH MAIN JSON
    # ------------------------------------

    data = fetch_json(SOURCE_URL)

    if data is None:
        raise SystemExit("Failed to fetch source JSON")

    # ------------------------------------
    # SUPPORT COMMON JSON STRUCTURES
    # ------------------------------------

    if isinstance(data, list):

        events = data

    elif isinstance(data, dict):

        if isinstance(data.get("events"), list):
            events = data["events"]

        elif isinstance(data.get("data"), list):
            events = data["data"]

        else:
            raise SystemExit(
                "Could not find event list in JSON"
            )

    else:

        raise SystemExit(
            "Invalid JSON structure"
        )

    print(f"[INFO] Events found: {len(events)}")

    m3u = [
        "#EXTM3U"
    ]

    total_events = 0
    total_streams = 0

    # ------------------------------------
    # PROCESS EVENTS
    # ------------------------------------

    for event in events:

        event_id = str(
            event.get("id", "")
        )

        event_title = event.get(
            "title",
            "Unknown Event"
        )

        category = event.get(
            "cat",
            "Live Events"
        )

        event_info = event.get(
            "eventInfo"
        ) or {}

        logo = event_info.get(
            "eventLogo",
            ""
        )

        if logo in [
            "null",
            "nulln",
            "None",
            None
        ]:
            logo = ""

        channel_url = event.get(
            "channelUrl"
        )

        if not channel_url:

            print(
                f"[SKIP] {event_title}: "
                "no channelUrl"
            )

            continue

        # --------------------------------
        # FETCH CHANNEL JSON
        # --------------------------------

        channel_data = fetch_json(
            channel_url
        )

        if not channel_data:
            continue

        streams = channel_data.get(
            "streamUrls",
            []
        )

        if not isinstance(streams, list):

            print(
                f"[SKIP] {event_title}: "
                "invalid streamUrls"
            )

            continue

        total_events += 1

        print(
            f"[EVENT] {event_title} "
            f"({len(streams)} streams)"
        )

        # --------------------------------
        # PROCESS STREAMS
        # --------------------------------

        for stream in streams:

            title = stream.get(
                "title",
                "Stream"
            ).strip()

            link = stream.get(
                "link",
                ""
            ).strip()

            api = stream.get(
                "api",
                ""
            ).strip()

            typ = stream.get(
                "type",
                "0"
            )

            if not link:

                print(
                    f"  [SKIP] {title}: "
                    "no link"
                )

                continue

            url, headers = parse_link(
                link
            )

            if not url:
                continue

            detected = stream_type(
                url,
                typ
            )

            name = (
                f"{event_title} | {title}"
            )

            # --------------------------------
            # EXTINF
            # --------------------------------

            m3u.append(
                f'#EXTINF:-1 '
                f'tvg-id="{event_id}" '
                f'tvg-name="{name}" '
                f'tvg-logo="{logo}" '
                f'group-title="{category}",'
                f'{name}'
            )

            # --------------------------------
            # DASH
            # --------------------------------

            if detected == "DASH":

                m3u.append(
                    "#KODIPROP:"
                    "inputstream.adaptive."
                    "manifest_type=mpd"
                )

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

            # --------------------------------
            # HEADERS
            # --------------------------------

            if headers:

                header_string = (
                    make_header_string(headers)
                )

                m3u.append(
                    "#KODIPROP:"
                    "inputstream.adaptive."
                    f"stream_headers={header_string}"
                )

            # --------------------------------
            # URL
            # --------------------------------

            m3u.append(url)

            m3u.append("")

            total_streams += 1

    # ------------------------------------
    # WRITE M3U
    # ------------------------------------

    with open(
        OUTPUT_M3U,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n".join(m3u)
        )

    print()
    print("========================================")
    print(" CONVERSION COMPLETE")
    print("========================================")
    print(f"Events  : {total_events}")
    print(f"Streams : {total_streams}")
    print(f"Output  : {OUTPUT_M3U}")
    print("========================================")


if __name__ == "__main__":
    main()
