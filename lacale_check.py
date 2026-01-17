#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, csv, json, re, sys, time, unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tabulate import tabulate

cfg = json.loads(Path(__file__).with_name("config.json").read_text())
RADARR_URL, SONARR_URL = cfg["RADARR_URL"], cfg["SONARR_URL"]
RADARR_KEY, SONARR_KEY = cfg["RADARR_API_KEY"], cfg["SONARR_API_KEY"]
PASSKEY, API_BASE = cfg["LACALE_PASSKEY"], cfg["LACALE_API_BASE"]

TIMEOUT, DELAY, MAX_R, BF = 15, 0.30, 3, 2

def http_get(url, *, hdr=None, prm=None):
    attempts = 0
    while True:
        try:
            r = requests.get(url, headers=hdr, params=prm, timeout=TIMEOUT)
            if r.status_code == 429:
                if attempts >= MAX_R: return {}
                time.sleep(BF ** attempts)
                attempts += 1
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"[ERROR] {url} → {e}", file=sys.stderr)
            return {}

def radarr_items(key):
    data = http_get(f"{RADARR_URL.rstrip('/')}/api/v3/movie", hdr={"X-Api-Key": key})
    if not isinstance(data, list): return []
    out = []
    for m in data:
        mf = m.get("movieFile")
        if not mf: continue
        out.append({
            "title": m.get("title", ""),
            "year": m.get("year"),
            "originalTitle": m.get("originalTitle"),
        })
    return out

def sonarr_series(key):
    data = http_get(f"{SONARR_URL.rstrip('/')}/api/v3/series", hdr={"X-Api-Key": key})
    if not isinstance(data, list): return []
    for s in data:
        s["season_numbers"] = [sn["seasonNumber"] for sn in s.get("seasons", [])]
    return data

def sonarr_items(key):
    series = sonarr_series(key)
    by_id = {s["id"]: s for s in series}
    eps = []
    lst = http_get(f"{SONARR_URL.rstrip('/')}/api/v3/episode", hdr={"X-Api-Key": key}) or []
    for e in lst:
        sid = e.get("seriesId")
        ser = by_id.get(sid)
        if not ser: continue
        ef = e.get("episodeFile")
        if not ef: continue
        eps.append({
            "title": ser.get("title", ""),
            "year": ser.get("year"),
            "originalTitle": ser.get("originalTitle"),
            "season": e.get("seasonNumber"),
            "episode": e.get("episodeNumber"),
        })
    return eps

def normalize(t):
    t = unicodedata.normalize('NFKD', t).encode('ascii','ignore').decode().lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^(the|le|la|les|un|une|l\'|d\')\s+', '', t)
    t = re.sub(r'\s+(the|le|la|les|un|une|l\'|d\')$', '', t)
    return t

def parse_se_ep(name):
    m = re.search(r'(?i)s(?P<season>\d{1,2})(?:[xe]?(?P<episode>\d{1,2}))?', name)
    if not m: return None, None
    season = int(m.group('season'))
    ep = m.group('episode')
    episode = int(ep) if ep else None
    return season, episode

def variants(item):
    seen = set()
    out = []
    primary = item.get("title", "").strip()
    primary = re.sub(r'\s*$$.*?$$', '', primary).strip()
    if primary and primary not in seen:
        out.append(("FR", primary)); seen.add(primary)
    orig = item.get("originalTitle")
    if orig:
        orig = orig.strip()
        orig = re.sub(r'\s*$$.*?$$', '', orig).strip()
        if orig and orig not in seen:
            out.append(("VO", orig)); seen.add(orig)
    return out

def lacale_search(q, pk, s=None, e=None):
    params = {"q": q.strip() + (f" S{s:02d}" if s else "") + (f"E{e:02d}" if e else ""), "passkey": pk}
    data = http_get(f"{API_BASE.rstrip('/')}/external", prm=params)
    if isinstance(data, list): return bool(data)
    if isinstance(data, dict): return bool(data.get("results", []))
    return False

def lacale_multi(item, pk, s=None, e=None):
    found = []
    for name, title in variants(item):
        if lacale_search(title, pk, s, e):
            found.append(name)
    if not found: return False, "None"
    if len(found) == 2: return True, "Both"
    return True, found[0]

def sort_items(lst, mode):
    if mode == "oldest":   return sorted(lst, key=lambda x:(x.get("year",9999),x.get("title","").lower()))
    if mode == "newest":   return sorted(lst, key=lambda x:(-x.get("year",0),x.get("title","").lower()))
    if mode == "popular":  return sorted(lst, key=lambda x:x.get("popularity",0),reverse=True)
    if mode == "least-popular": return sorted(lst, key=lambda x:x.get("popularity",0))
    if mode == "az":  return sorted(lst, key=lambda x:x.get("title","").lower())
    return sorted(lst, key=lambda x:x.get("title","").lower())

def check_one(item, pk, lvl, season=None, episode=None):
    t = item.get("title","??")
    y = str(item.get("year",""))
    present, var = lacale_multi(item, pk, season, episode)
    return (t, y, season, episode, present, var)

def parallel(items, pk, limit, workers, lvl):
    sel = items[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_one, it, pk, lvl): it for it in sel}
        for f in as_completed(futures):
            out.append(f.result())
            time.sleep(DELAY)
    return out

def build_seasons(series, pk, limit, workers):
    tasks = [(s, sn) for s in series for sn in s.get("season_numbers", [])][:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(check_one, ser, pk, "season", sn, None): (ser, sn) for ser, sn in tasks}
        for f in as_completed(futs):
            out.append(f.result())
            time.sleep(DELAY)
    return out

def build_episodes(eps, pk, limit, workers):
    tasks = eps[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(check_one, ep, pk, "episode", ep.get("season"), ep.get("episode")): ep for ep in tasks}
        for f in as_completed(futs):
            out.append(f.result())
            time.sleep(DELAY)
    return out

def display(header, rows, csv_path=None, hide=False, mode="full", test=False):
    print("\n"+header); print("-"*len(header))
    cols = ["Titre","Année"]
    if mode in ("season","episode"): cols.append("Saison")
    if mode=="episode": cols.append("Épisode")
    cols.append("Sur La Cale")
    if test: cols.append("Variant")
    filtered = [r for r in rows if not (hide and r[4])]
    tbl = []
    for t,y,s,e,present,var in filtered:
        row=[t,y]
        if mode in ("season","episode"): row.append(str(s) if s else "")
        if mode=="episode": row.append(str(e) if e else "")
        row.append("✅ Oui" if present else "❌ Non")
        if test: row.append(var)
        tbl.append(row)
    print(tabulate(tbl, headers=cols, tablefmt="github"))
    if csv_path:
        mode_w = "a" if csv_path.exists() else "w"
        with csv_path.open(mode_w, newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if mode_w=="w": w.writerow(cols)
            w.writerows(tbl)

def main():
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--radarr", action="store_true")
    src.add_argument("--sonarr", action="store_true")
    p.add_argument("--folder", type=Path)
    p.add_argument("--export", type=Path, metavar="fichier.csv")
    p.add_argument("--radarr-key", default=RADARR_KEY)
    p.add_argument("--sonarr-key", default=SONARR_KEY)
    p.add_argument("-l","--limit",type=int,default=100)
    p.add_argument("--sort",choices=["oldest","newest","popular","least-popular","az"])
    p.add_argument("--mode",choices=["full","season","episode"],default="full")
    p.add_argument("--hide-present",action="store_true")
    p.add_argument("--year-min",type=int)
    p.add_argument("--year-max",type=int)
    p.add_argument("--test",action="store_true")
    a = p.parse_args()

    if not PASSKEY:
        print("[ERROR] PASSKEY missing",file=sys.stderr); sys.exit(1)

    if a.radarr and a.mode!="full":
        print("[ERROR] Radarr only supports full mode",file=sys.stderr); sys.exit(1)

    if a.folder:
        if not a.folder.is_dir():
            print("[ERROR] Invalid folder",file=sys.stderr); sys.exit(1)
        items = []
        for f in a.folder.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".mkv",".mp4",".avi",".mov"}:
                t = f.stem
                y = ""
                if "(" in t and ")" in t.split("(")[-1]:
                    yy = t.split("(")[-1].split(")")[0]
                    if yy.isdigit() and len(yy)==4: y, t = yy, t.split("(")[0].strip()
                s,e = parse_se_ep(t)
                items.append({"title":t,"year":int(y) if y else None,"season":s,"episode":e})
        source = "folder"
    else:
        if a.radarr:
            items = radarr_items(a.radarr_key or RADARR_KEY)
            source = "radarr"
        else:
            key = a.sonarr_key or SONARR_KEY
            if a.mode in ("full","season"):
                items = sonarr_series(key)
            else:
                items = sonarr_items(key)
            source = "sonarr"

    if not items:
        print("[ERROR] No items with associated files found",file=sys.stderr); sys.exit(1)

    if a.year_min is not None or a.year_max is not None:
        items = [i for i in items if i.get("year") and
                 (a.year_min is None or i["year"]>=a.year_min) and
                 (a.year_max is None or i["year"]<=a.year_max)]
        if not items:
            print("[ERROR] No items match year filter",file=sys.stderr); sys.exit(1)

    if a.mode=="full":
        if a.sort:
            items = sort_items(items, a.sort)
            hdr = {
                "oldest":"Top {} oldest".format(a.limit),
                "newest":"Top {} newest".format(a.limit),
                "popular":"Top {} popular".format(a.limit),
                "least-popular":"Top {} least popular".format(a.limit),
                "az":"Top {} (original order)".format(a.limit)
            }[a.sort]
        else:
            hdr = f"First {a.limit} items (original order)"
        rows = parallel(items, PASSKEY, a.limit, 5, "full")
        display(hdr, rows, a.export, a.hide_present, mode="full", test=a.test)
    elif a.mode=="season":
        rows = build_seasons(items, PASSKEY, a.limit, 5)
        display(f"Seasons (max {a.limit})", rows, a.export, a.hide_present, mode="season", test=a.test)
    else:
        rows = build_episodes(items, PASSKEY, a.limit, 5)
        display(f"Episodes (max {a.limit})", rows, a.export, a.hide_present, mode="episode", test=a.test)

if __name__ == "__main__":
    main()
