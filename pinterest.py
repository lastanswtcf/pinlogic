import sys
import json
import time
import re
import os
import threading
from urllib.parse import urlparse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

def installdeps():
    import subprocess
    for pkg, imp in [("requests", "requests"), ("beautifulsoup4", "bs4")]:
        try:
            __import__(imp)
        except ImportError:
            print(f"  installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

installdeps()

class c:
    r  = "\033[91m"
    g  = "\033[92m"
    y  = "\033[93m"
    b  = "\033[94m"
    m  = "\033[95m"
    cy = "\033[96m"
    w  = "\033[97m"
    bo = "\033[1m"
    d  = "\033[2m"
    rs = "\033[0m"

def cl(text, *codes):
    return "".join(codes) + str(text) + c.rs

class loader:
    def __init__(self, msg="loading"):
        self.msg = msg
        self.running = False
        self.thread = None
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
    def _spin(self):
        dots = 0
        while self.running:
            d = "." * dots + "   "
            print(f"\r  {cl(self.msg, c.d)}  {cl(d[:3], c.cy)}", end="", flush=True)
            dots = (dots % 3) + 1
            time.sleep(0.4)
    def stop(self, donemsg=None):
        self.running = False
        if self.thread:
            self.thread.join()
        if donemsg:
            print(f"\r  {cl(donemsg, c.g)}              ")
        else:
            print(f"\r  {cl(self.msg, c.d)}  {cl('done', c.g)}           ")

def showbanner():
    os.system("cls" if os.name == "nt" else "clear")
    banner = r"""
        _       _             _      
       (_)     | |           (_)     
  _ __  _ _ __ | | ___   __ _ _  ___ 
 | '_ \| | '_ \| |/ _ \ / _` | |/ __|
 | |_) | | | | | | (_) | (_| | | (__ 
 | .__/|_|_| |_|_|\___/ \__, |_|\___|
 | |                     __/ |       
 |_|                    |___/        
"""
    print(cl(banner, c.m, c.bo))
    print(cl("  pinterest board scraper", c.d))
    print(cl("  grab every image url from any board", c.d))
    print(cl("  github.com/lastanswtcf/pinlogic\n", c.d))
    print(cl("  " + "─" * 52 + "\n", c.d))

def validateurl(url):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    p = urlparse(url)
    if "pinterest" not in p.netloc:
        return False, url
    parts = [x for x in p.path.strip("/").split("/") if x]
    if len(parts) < 2:
        return False, url
    return True, url

def getboardname(url):
    p = urlparse(url)
    parts = [x for x in p.path.strip("/").split("/") if x]
    return parts[-1] if parts else "board"

def getuserboardparts(url):
    p = urlparse(url)
    parts = [x for x in p.path.strip("/").split("/") if x]
    return (parts[0], parts[1]) if len(parts) >= 2 else ("", "")

HDRS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetchpage(url, sess):
    try:
        r = sess.get(url, headers=HDRS, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extractimgs(html):
    imgs = set()
    patterns = [
        r'"orig":\s*\{"url":\s*"([^"]+)"',
        r'"736x":\s*\{"url":\s*"([^"]+)"',
        r'"564x":\s*\{"url":\s*"([^"]+)"',
        r'"474x":\s*\{"url":\s*"([^"]+)"',
    ]
    for pat in patterns:
        for u in re.findall(pat, html):
            u = u.replace("\\u002F", "/").replace("\\/", "/")
            if "pinimg.com" in u:
                imgs.add(u)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src") or ""
        if "pinimg.com" in src:
            imgs.add(src)
    for u in re.findall(r'https://[^"\'>\s]+pinimg\.com[^"\'>\s]+\.(?:jpg|png|webp|gif)', html):
        imgs.add(u)
    return list(imgs)

def toorig(url):
    return re.sub(r'/\d+x(?:/)', '/originals/', url)

def getboardid(html):
    for pat in [r'"board_id":\s*"?(\d+)"?', r'"id":\s*"(\d+)"[^}]*"type":\s*"board"']:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None

def scrapeboard(url, sess):
    images = []
    seen = set()
    username, boardname = getuserboardparts(url)
    print(cl(f"  user: {username}", c.d))
    print(cl(f"  board: {boardname}\n", c.d))
    ld = loader("fetching board page")
    ld.start()
    html = fetchpage(url, sess)
    ld.stop("page fetched" if html else "could not fetch page")

    if not html:
        return None, "could not reach that url, check the link and try again"
    if "pinterestapp:notfound" in html.lower() or '"error": 404' in html:
        return None, "board not found, it might be private or the url is wrong"
    for imgurl in extractimgs(html):
        if imgurl not in seen:
            seen.add(imgurl)
            images.append({"url": imgurl, "url_orig": toorig(imgurl), "source": "html"})
    boardid = getboardid(html)

    if boardid:
        print(cl(f"  board id: {boardid}", c.d))
        apiurl = "https://www.pinterest.com/resource/BoardFeedResource/get/"
        bookmark = None
        page = 1
        maxpages = 60
        ld2 = loader("collecting pins")
        ld2.start()

        while page <= maxpages:
            params = {
                "source_url": f"/{username}/{boardname}/",
                "data": json.dumps({
                    "options": {
                        "board_id": boardid,
                        "board_url": f"/{username}/{boardname}/",
                        "currentFilter": -1,
                        "field_set_key": "react_grid_pin",
                        "filter_section_pins": True,
                        "layout": "default",
                        "page_size": 25,
                        "redux_normalize_feed": True,
                        **({"bookmarks": [bookmark]} if bookmark else {})
                    },
                    "context": {}
                }),
                "_": str(int(time.time() * 1000))
            }
            try:
                r = sess.get(apiurl, params=params, headers={
                    **HDRS,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*, q=0.01",
                    "Referer": url,
                }, timeout=15)
                data = r.json()
                resp = data.get("resource_response", {})
                pins = resp.get("data", [])

                if not pins:
                    break

                for pin in pins:
                    pinimgs = pin.get("images", {})
                    for sizekey in ["orig", "736x", "564x", "474x", "236x"]:
                        info = pinimgs.get(sizekey, {})
                        imgurl = info.get("url")
                        if imgurl and imgurl not in seen:
                            seen.add(imgurl)
                            images.append({
                                "url": imgurl,
                                "url_orig": toorig(imgurl),
                                "pin_id": pin.get("id", ""),
                                "description": pin.get("description", ""),
                                "width": info.get("width", 0),
                                "height": info.get("height", 0),
                                "size": sizekey
                            })
                            break

                bookmark = resp.get("bookmark")
                if not bookmark or bookmark == "-end-":
                    break
                page += 1
                time.sleep(0.35)
            except Exception:
                break

        ld2.stop(f"collected: {len(images)} images")

    else:
        print(cl("  no board id found: using html results only", c.y))
    if len(images) == 0:
        return None, "no images found: the board might be empty or private"
    return images, None

def savejson(url, boardname, images, elapsed):
    outfile = f"{boardname}.json"
    output = {
        "metadata": {
            "board_url": url,
            "board_name": boardname,
            "scraped_at": datetime.now().isoformat(),
            "total_images": len(images),
            "elapsed_seconds": elapsed,
            "credits": "https://github.com/lastanswtcf/pinlogic"
        },
        "images": images
    }
    ld = loader("saving json")
    ld.start()
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    ld.stop(f"saved: {outfile}")
    return outfile

def askurl():
    while True:
        print(cl("  paste a pinterest board url below", c.w))
        print(cl("  → ", c.cy), end="")
        try:
            raw = input().strip()
        except (KeyboardInterrupt, EOFError):
            print(cl("\n\n  bye\n", c.d))
            sys.exit(0)

        if not raw:
            print(cl("\n  nothing entered: try again\n", c.y))
            continue

        valid, url = validateurl(raw)
        if not valid:
            print(cl("\n  " + "─" * 52, c.d))
            print(cl("  couldn't find that: doesn't look like a pinterest board url", c.r))
            print(cl("  it should look like: https://pinterest.com/username/boardname/", c.d))
            print(cl("  " + "─" * 52 + "\n", c.d))
            continue
        return url

def runonce(sess):
    url = askurl()
    boardname = getboardname(url)
    print(cl(f"\n  output file: {boardname}.json\n", c.d))
    print(cl("  " + "─" * 52 + "\n", c.d))
    start = time.time()
    images, err = scrapeboard(url, sess)
    elapsed = round(time.time() - start, 2)
    print(cl("\n  " + "─" * 52 + "\n", c.d))

    if err:
        print(cl(f"  {err}", c.r))
        print(cl("\n  " + "─" * 52 + "\n", c.d))
        return

    unique = list({img["url"]: img for img in images}.values())
    outfile = savejson(url, boardname, unique, elapsed)
    print(cl(f"\n  images: {cl(len(unique), c.cy + c.bo)}", c.w))
    print(cl(f"  time: {elapsed}s", c.d))
    print(cl(f"  file: {cl(outfile, c.cy)}", c.w))
    print(cl(f"  credits: github.com/lastanswtcf/pinlogic\n", c.d))
    print(cl("  preview\n", c.d))

    for i, img in enumerate(unique[:3], 1):
        short = img["url"][:65] + ("..." if len(img["url"]) > 65 else "")
        print(cl(f"  {i}.  {short}", c.d))
    print(cl("\n  " + "─" * 52 + "\n", c.d))
    print(cl("  all done\n", c.g))

def main():
    showbanner()
    sess = requests.Session()
    sess.headers.update(HDRS)
    ld0 = loader("connecting")
    ld0.start()
    try:
        sess.get("https://www.pinterest.com/", timeout=10)
    except Exception:
        pass
    ld0.stop("connected")
    time.sleep(0.2)
    print()

    while True:
        runonce(sess)
        print(cl("  want to scrape another board", c.w))
        print(cl("  y  →  yes    n  →  exit\n", c.d))
        print(cl("  → ", c.cy), end="")

        try:
            ans = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(cl("\n\n  bye\n", c.d))
            break

        if ans == "y":
            print(cl("\n  " + "─" * 52 + "\n", c.d))
            continue
        else:
            print(cl("\n  bye\n", c.d))
            break

if __name__ == "__main__":
    main()
