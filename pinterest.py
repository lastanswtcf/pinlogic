import sys
import json
import time
import re
import os
import threading
import hashlib
import argparse
import concurrent.futures
from datetime import datetime
from urllib.parse import urlparse
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def installdeps():
    import subprocess
    for imp, pkg in [("selenium","selenium"),("webdriver_manager","webdriver-manager"),("requests","requests")]:
        try:
            __import__(imp)
        except ImportError:
            subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q"])
installdeps()


class co:
    r="\033[91m"; g="\033[92m"; y="\033[93m"; cy="\033[96m"
    w="\033[97m"; m="\033[95m"; bo="\033[1m"; d="\033[2m"; rs="\033[0m"
def cl(t,*x): return "".join(x)+str(t)+co.rs

class Spin:
    def __init__(self,msg):
        self.msg=msg; self.on=False; self.t=None; self.n=0
    def start(self):
        self.on=True; self.t=threading.Thread(target=self.loop,daemon=True); self.t.start()
    def loop(self):
        f=["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]; i=0
        while self.on:
            c=f"  {cl(self.n,co.cy+co.bo)} found" if self.n else ""
            print(f"\r  {cl(f[i%len(f)],co.cy)} {cl(self.msg,co.d)}{c}   ",end="",flush=True)
            i+=1; time.sleep(0.08)
    def upd(self,n): self.n=n
    def stop(self,msg=None):
        self.on=False
        if self.t: self.t.join()
        print(f"\r  {cl('✓',co.g)} {msg or cl('done',co.g)}                                    ")

def banner():
    os.system("cls" if os.name=="nt" else "clear")
    print(cl(r"""
        _ _ _
       (_) | | (_)
  _ __ _ _ __ | | ___ __ _ _ ___
 | '_ \| | '_ \| |/ _ \ / _` | |/ __|
 | |_) | | | | | | (_) | (_| | | (__
 | .__/|_|_| |_|_|\___/ \__, |_|\___|
 | |                     __/ |
 |_|                    |___/
""",co.m,co.bo))
    print(cl("  pinlogic v2.0 by lastanswtcf.lol",co.d))
    print(cl("  ─────────────────────────────────────\n",co.d))

def parseurl(url):
    url=url.strip()
    if not url.startswith("http"): url="https://"+url
    p=urlparse(url)
    if "pinterest" not in p.netloc: raise ValueError("not pinterest")
    parts=[x for x in p.path.strip("/").split("/") if x]
    if len(parts)<2: raise ValueError("need /user/board/")
    return parts[0],parts[1]

ADFLAGS={"is_promoted","is_promoted_pin","is_shopping_showcase","ad_destination_url"}
ADKW={"promoted","sponsored","advertisement","shop now","buy now","#ad","affiliate","promo code"}

def isad(pin):
    for k in ADFLAGS:
        if pin.get(k): return True
    txt=" ".join([pin.get("description") or "",pin.get("title") or "",pin.get("grid_title") or ""]).lower()
    return any(k in txt for k in ADKW)
_SZRE=re.compile(r'/\d+x[\w]*/')

def toorig(url):
    if not url: return url
    url=url.replace("\\u002F","/").replace("\\/","/")
    if "/originals/" in url: return url
    return _SZRE.sub("/originals/",url,count=1)

def bestimg(pin):
    imgs=pin.get("images") or {}
    for sz in ("orig","736x","600x315","474x","236x"):
        i=imgs.get(sz)
        if i and i.get("url"): return toorig(i["url"]),i.get("width",0),i.get("height",0)
    for i in imgs.values():
        if isinstance(i,dict) and i.get("url"): return toorig(i["url"]),i.get("width",0),i.get("height",0)
    return None,0,0

def extractpins(obj,imgs,depth=0):
    if depth>25 or not obj: return
    if isinstance(obj,dict):
        im=obj.get("images"); pid=obj.get("id") or obj.get("pin_id")
        if im and isinstance(im,dict) and pid:
            url,w,h=bestimg(obj)
            if url and "pinimg.com" in url and url not in imgs and not isad(obj):
                imgs[url]={"url_orig":url,"pin_id":str(pid),
                           "description":(obj.get("description") or "").strip(),
                           "title":(obj.get("title") or "").strip(),
                           "width":w,"height":h,
                           "link":obj.get("link") or "",
                           "source_domain":obj.get("domain") or ""}
        for v in obj.values(): extractpins(v,imgs,depth+1)
    elif isinstance(obj,list):
        for i in obj: extractpins(i,imgs,depth+1)

BRAVE_PATHS=[
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/usr/bin/brave-browser","/usr/bin/brave",
    os.path.expanduser("~/.local/share/BraveSoftware/Brave-Browser/brave"),
]

def findbrave():
    for p in BRAVE_PATHS:
        if os.path.exists(p): return p
    return None

def makedriver(headless=False,usebrave=True):
    opts=Options()
    brave=findbrave() if usebrave else None
    if brave:
        opts.binary_location=brave
    if headless: opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--mute-audio")
    opts.add_argument("--block-new-web-contents")
    opts.add_experimental_option("excludeSwitches",["enable-automation"])
    opts.add_experimental_option("useAutomationExtension",False)
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    opts.set_capability("goog:loggingPrefs",{"performance":"ALL"})

    try:
        svc=Service(ChromeDriverManager().install())
        d=webdriver.Chrome(service=svc,options=opts)
    except:
        d=webdriver.Chrome(options=opts)

    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",{
        "source":"Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"
    })

    if brave:
        try:
            d.execute_cdp_cmd("Network.enable",{})
            d.execute_cdp_cmd("Network.setBlockedURLs",{"urls":[
                "*doubleclick.net*","*googlesyndication.com*","*adservice.google.*",
                "*ads.pinterest.com*","*promoted*","*sponsored*",
                "*/promoted_pin*","*ad_type*","*ad_account*",
                "*cm.g.doubleclick.net*","*securepubads.g.doubleclick.net*",
            ]})
        except: pass
    return d,brave is not None and usebrave

def drainlogs(driver,imgs):
    new=0
    try: logs=driver.get_log("performance")
    except: return 0
    for entry in logs:
        try:
            msg=json.loads(entry["message"])["message"]
            if msg.get("method")!="Network.responseReceived": continue
            resp=msg.get("params",{}).get("response",{})
            url=resp.get("url",""); ct=resp.get("mimeType","")
            if "pinterest.com" not in url: continue
            if "json" not in ct and "javascript" not in ct: continue
            if not any(k in url for k in ("BoardFeedResource","BoardSectionPins","react_grid_pin")): continue
            rid=msg["params"].get("requestId")
            if not rid: continue
            try:
                body=driver.execute_cdp_cmd("Network.getResponseBody",{"requestId":rid}).get("body","")
                if not body: continue
                before=len(imgs)
                extractpins(json.loads(body),imgs)
                new+=len(imgs)-before
            except: pass
        except: pass
    return new

def scrollboard(driver,imgs,spin=None,timeout=360):
    last=0; stale=0; maxstale=7
    start=time.time()
    while time.time()-start<timeout:
        drainlogs(driver,imgs)
        try:
            for el in driver.find_elements(By.CSS_SELECTOR,"img[src*='pinimg.com']"):
                src=el.get_attribute("src") or ""
                if "pinimg.com" not in src: continue
                orig=toorig(src)
                if orig not in imgs:
                    imgs[orig]={"url_orig":orig,
                                "pin_id":hashlib.md5(orig.encode()).hexdigest()[:14],
                                "description":el.get_attribute("alt") or "",
                                "title":"","width":0,"height":0,"link":"","source_domain":""}
        except: pass

        n=len(imgs)
        if spin: spin.upd(n)
        if n==last:
            stale+=1
            if stale>=maxstale: break
        else:
            stale=0; last=n

        driver.execute_script("window.scrollTo(0,document.body.scrollHeight);")
        time.sleep(2.8)
        try:
            btn=driver.find_element(By.XPATH,"//*[contains(text(),'Show more') or contains(text(),'See more')]")
            driver.execute_script("arguments[0].click();",btn)
            time.sleep(1.5)
        except: pass

def scrapeboard(url,headless=False,usebrave=True):
    try: username,slug=parseurl(url)
    except ValueError as e: return None,str(e)
    print(cl(f"  user  : {username}",co.d))
    print(cl(f"  board : {slug}\n",co.d))
    sp=Spin("launching browser"); sp.start()
    try: driver,usingbrave=makedriver(headless=headless,usebrave=usebrave)
    except Exception as e: sp.stop(cl(f"failed {e}",co.r)); return None,str(e)
    browser="brave" if usingbrave else "chrome"
    sp.stop(cl(f"using {browser}",co.g))

    imgs={}
    board_url=f"https://www.pinterest.com/{username}/{slug}/"

    try:
        driver.execute_cdp_cmd("Network.enable",{})
        sp2=Spin("loading board"); sp2.start()
        driver.get(board_url)
        time.sleep(3)

        for sel in ["[data-test-id='gdpr-accept-button']","[aria-label='Accept']","button[class*='accept']"]:
            try: driver.find_element(By.CSS_SELECTOR,sel).click(); time.sleep(0.4)
            except: pass

        try:
            WebDriverWait(driver,15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,"img[src*='pinimg.com']")))
        except: pass

        drainlogs(driver,imgs)
        try:
            title=driver.title
            m=re.search(r'(\d+)\s*[Pp]in',title)
            sp2.stop(cl(f"board loaded  stated ~{m.group(1)} pins" if m else "board loaded",co.g))
        except: sp2.stop(cl("board loaded",co.g))

        sp3=Spin("collecting pins"); sp3.start()
        scrollboard(driver,imgs,spin=sp3)
        drainlogs(driver,imgs)
        sp3.stop(cl(f"{len(imgs)} pins collected",co.g))

    finally:
        driver.quit()
    if not imgs:
        return None,(
            "no images found\n"
            "  board may be private or a login wall appeared\n"
            "  try running without --headless"
        )

    print(cl(f"\n  total : {cl(len(imgs),co.cy+co.bo)}",co.w))
    return list(imgs.values()),None

def dlimages(records,workers=16):
    outdir="images"; os.makedirs(outdir,exist_ok=True)
    sess=requests.Session()
    sess.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://www.pinterest.com/"})
    done=0; fail=0; lock=threading.Lock()

    def dl(rec):
        nonlocal done,fail
        url=rec["url_orig"]
        ext=url.split("?")[0].rsplit(".",1)[-1].lower()
        if ext not in {"jpg","jpeg","png","webp","gif","avif"}: ext="jpg"
        pid=rec.get("pin_id") or hashlib.md5(url.encode()).hexdigest()[:14]
        fp=os.path.join(outdir,f"{pid}.{ext}")
        if os.path.exists(fp):
            with lock: done+=1; return f"{pid}.{ext}"
        try:
            r=sess.get(url,timeout=30,stream=True); r.raise_for_status()
            with open(fp,"wb") as f:
                for ch in r.iter_content(65536): f.write(ch)
            with lock: done+=1; return f"{pid}.{ext}"
        except:
            with lock: fail+=1; return None

    sp=Spin(f"downloading {len(records)} images"); sp.start()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs={ex.submit(dl,rec):rec for rec in records}
        for fut in concurrent.futures.as_completed(futs):
            sp.upd(done); fn=fut.result()
            if fn: futs[fut]["local_file"]=fn
    sp.stop(cl(f"saved {done}  failed {fail}",co.g if not fail else co.y))
    return done,fail

def savejson(url,name,imgs,elapsed):
    p=f"{name}.json"
    with open(p,"w",encoding="utf-8") as f:
        json.dump({"meta":{"board_url":url,"board_name":name,
                           "scraped_at":datetime.now().isoformat(),
                           "total":len(imgs),"elapsed_s":elapsed},
                   "images":imgs},f,ensure_ascii=False,indent=2)
    return p

def askurl():
    while True:
        print(cl("  board url",co.w)); print(cl("  > ",co.cy),end="",flush=True)
        try: raw=input().strip()
        except (KeyboardInterrupt,EOFError): sys.exit(0)
        if not raw: continue
        try: u,b=parseurl(raw); return raw,u,b
        except ValueError: print(cl("  example  pinterest.com/user/board\n",co.r))

def askyesno(msg):
    print(cl(f"\n  {msg}  [y/n]",co.w)); print(cl("  > ",co.cy),end="",flush=True)
    try: return input().strip().lower()=="y"
    except (KeyboardInterrupt,EOFError): return False

def askbrowser():
    print(cl("  browser",co.w))
    print(cl("  1  brave",co.d))
    print(cl("  2  chrome",co.d))
    while True:
        print(cl("  > ",co.cy),end="",flush=True)
        try: ch=input().strip()
        except (KeyboardInterrupt,EOFError): sys.exit(0)
        if ch=="1":
            if not findbrave():
                print(cl("  brave not found  falling back to chrome",co.y))
                return False
            return True
        if ch=="2": return False
        print(cl("  type 1 or 2",co.r))

def runonce(headless):
    usebrave=askbrowser()
    print()
    raw,_,slug=askurl()
    print(cl(f"\n  output : {slug}.json",co.d))
    print(cl("  ─────────────────────────────────────\n",co.d))

    t0=time.time()
    imgs,err=scrapeboard(raw,headless=headless,usebrave=usebrave)
    elapsed=round(time.time()-t0,2)
    print(cl("\n  ─────────────────────────────────────\n",co.d))
    if err: print(cl(f"  {err}",co.r)); return

    print(cl(f"  time : {elapsed}s\n",co.d))
    jf=savejson(raw,slug,imgs,elapsed)
    print(cl(f"  json : {jf}",co.g))

    if askyesno("download images to disk"):
        dlimages(imgs)
        savejson(raw,slug,imgs,round(time.time()-t0,2))
        print(cl("  json updated with local filenames",co.g))

    print(cl("\n  preview\n",co.d))
    for i,img in enumerate(imgs[:5],1):
        s=img["url_orig"][:72]+("..." if len(img["url_orig"])>72 else "")
        print(cl(f"  {i}  {s}",co.d))
    print(cl("\n  done\n",co.g))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--url",help="board url")
    p.add_argument("--headless",action="store_true",default=False)
    args=p.parse_args()
    banner()
    
    if args.url:
        usebrave=askbrowser(); print()
        try: _,slug=parseurl(args.url)
        except ValueError as e: print(cl(f"  {e}",co.r)); sys.exit(1)
        t0=time.time()
        imgs,err=scrapeboard(args.url,headless=args.headless,usebrave=usebrave)
        if err: print(cl(f"  {err}",co.r)); sys.exit(1)
        jf=savejson(args.url,slug,imgs,round(time.time()-t0,2))
        print(cl(f"  json : {jf}",co.g))
    else:
        while True:
            runonce(headless=args.headless)
            if not askyesno("scrape another board"): print(cl("\n  bye\n",co.d)); break

if __name__=="__main__":
    main()
