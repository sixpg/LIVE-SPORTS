import os
import requests

SOURCE = os.environ["SOURCE_URL"]

r = requests.get(SOURCE, timeout=20)
r.raise_for_status()

playlist = r.text

# If desired, rewrite URLs here for streams you are authorized to proxy.

with open("playlist.m3u8", "w", encoding="utf-8", newline="\n") as f:
    f.write(playlist)
