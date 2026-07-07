import math, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TILES_DIR = Path("tiles")
BBOX = dict(west=36.5, south=55.3, east=38.2, north=56.1)
STYLE = "dark"
MAX_ZOOM = 14
WORKERS = 10

def deg2tile(lat, lon, z):
    import math
    lr = math.radians(lat)
    n  = 2**z
    x  = int((lon+180)/360*n)
    y  = int((1-math.log(math.tan(lr)+1/math.cos(lr))/math.pi)/2*n)
    return x, max(0,min(n-1,y))

def download(z,x,y):
    p = TILES_DIR/STYLE/str(z)/str(x)/f"{y}.png"
    if p.exists() and p.stat().st_size>0: return "s"
    url=f"https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
    p.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={"User-Agent":"SENTINEL/1.0","Referer":"http://127.0.0.1:8000/"})
    for _ in range(3):
        try:
            with urllib.request.urlopen(req,timeout=12) as r: d=r.read()
            if len(d)>64: p.write_bytes(d); time.sleep(0.03); return "ok"
        except: time.sleep(1)
    return "e"

tasks=[]
for z in range(10, MAX_ZOOM+1):
    x0,y1=deg2tile(BBOX["south"],BBOX["west"],z)
    x1,y0=deg2tile(BBOX["north"],BBOX["east"],z)
    for x in range(x0,x1+1):
        for y in range(y0,y1+1):
            tasks.append((z,x,y))

print(f"HQ tiles Moscow zoom 10-{MAX_ZOOM}: {len(tasks)} tiles")
ok=sk=er=0
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    fs={pool.submit(download,z,x,y):(z,x,y) for z,x,y in tasks}
    for fut in as_completed(fs):
        r=fut.result()
        if r=="ok": ok+=1
        elif r=="s": sk+=1
        else: er+=1
        n=ok+sk+er
        print(f"\r  {n}/{len(tasks)} ok={ok} skip={sk} err={er}", end="", flush=True)
print(f"\nDone: {ok} new, {sk} skip, {er} err")
