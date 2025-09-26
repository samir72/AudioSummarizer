#!/usr/bin/env python3
import yt_dlp, traceback, sys, os
from http.cookiejar import MozillaCookieJar

class YDLLogger:
    def debug(self, msg): print("[DEBUG]", msg)
    def warning(self, msg): print("[WARN]", msg)
    def error(self, msg): print("[ERROR]", msg)

def probe(url, cookies=None):
    ydl_opts = {
        "format": "bestaudio/best",
        "cachedir": False,
        "logger": YDLLogger(),
        "no_warnings": False,
        "quiet": False,
        # don't try postprocessing during probe
        "postprocessors": [],
        # helpful to mimic a browser if site is picky:
        "http_headers": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"},
    }
    if cookies:
        ydl_opts["cookiefile"] = cookies

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Probing (no download)...")
            info = ydl.extract_info(url, download=False)
            print("Top-level keys in info:", list(info.keys()))
            formats = info.get("formats")
            if formats:
                print("Found formats (count):", len(formats))
                for f in formats[:10]:
                    print(f" - id={f.get('format_id')}, ext={f.get('ext')}, abr={f.get('abr')}, vbr={f.get('vbr')}, note={f.get('format_note')}")
            else:
                print("No formats found. Inspecting other info fields:")
                for k in ("webpage_url", "extractor", "requested_formats", "is_live", "entries"):
                    print(f"  {k}: {info.get(k)}")
            return info
    except Exception as e:
        print("EXCEPTION during probe:")
        traceback.print_exc()
        # also dump any HTML/diagnostic text if available in exception text
        print("Exception message:", str(e))

if __name__ == "__main__":
    cookies = None
    if len(sys.argv) > 1:
        cookies = sys.argv[1]
        if not os.path.isfile(cookies):
            print(f"Cookie file '{cookies}' not found.")
            sys.exit(1)
    url = "https://www.youtube.com/watch?v=wDchsz8nmbo"
    probe(url, cookies)
