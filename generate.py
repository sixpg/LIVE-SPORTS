import os
import urllib.request

SOURCE = os.environ["SOURCE_URL"]

with urllib.request.urlopen(SOURCE) as response:
    playlist = response.read().decode("utf-8")

with open("playlist.m3u8", "w", encoding="utf-8") as f:
    f.write(playlist)
