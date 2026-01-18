#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""LacaLe Checker – UI minimaliste, légende d’origine et stats.
"""

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------
import argparse, json, re, sys, time, unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tabulate import tabulate

# ----------------------------------------------------------------------
# Couleurs ANSI (légende + stats)
# ----------------------------------------------------------------------
class C:
    R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; O = "\033[38;5;208m"
    C = "\033[96m"; B = "\033[94m"; Z = "\033[0m"; BLD = "\033[1m"

# ----------------------------------------------------------------------
# Configuration (à placer à côté du script)
# ----------------------------------------------------------------------
cfg = json.loads(Path(__file__).with_name("config.json").read_text())
RADARR_URL, RADARR_KEY = cfg["RADARR_URL"], cfg["RADARR_API_KEY"]
PASSKEY, API_BASE = cfg["LACALE_PASSKEY"], cfg["LACALE_API_BASE"]

# ----------------------------------------------------------------------
# HTTP helper (retry on 429)
# ----------------------------------------------------------------------
TIMEOUT, RETRIES, BACKOFF = 15, 3, 2

def http_get(url, *, hdr=None, prm=None):
    for i in range(RETRIES + 1):
        try:
            r = requests.get(url, headers=hdr, params=prm, timeout=TIMEOUT)
            if r.status_code == 429 and i < RETRIES:
                time.sleep(BACKOFF * i)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"{C.R}[ERR]{C.Z} {url} → {e}", file=sys.stderr)
            return {}

# ----------------------------------------------------------------------
# Normalisation de texte (pour comparaison)
# ----------------------------------------------------------------------
def clean(txt: str) -> str:
    txt = unicodedata.normalize('NFKD', txt).encode('ascii','ignore').decode().lower()
    txt = re.sub(r'[^\w\s]', ' ', txt)
    return re.sub(r'\s+', ' ', txt).strip()

# ----------------------------------------------------------------------
# Métadonnées depuis le nom de fichier
# ----------------------------------------------------------------------
def meta_name(fname: str) -> dict:
    stem = Path(fname).stem.lower()
    codec = next((c.replace('x','h'))
                  for c in ("h264","h265","x264","x265","vp9","av1")
                  if re.search(rf'\b{c}\b', stem)), None
    res = (re.search(r'\b(\d{3,4}p|4k)\b', stem) or [None])[0]

    size = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(gb|mb|kb)', stem)
    if m:
        num, unit = float(m.group(1)), m.group(2)
        size = int(num * {"kb":1024, "mb":1024**2, "gb":1024**3}[unit])
    return {"codec": codec, "resolution": res, "size": size}

# ----------------------------------------------------------------------
# Recherche sur La Cale
# ----------------------------------------------------------------------
def lacale(query: str, pk: str, s: int | None = None, e: int | None = None) -> list:
    q = query.strip() + (f" S{s:02d}" if s else "") + (f"E{e:02d}" if e else "")
    resp = http_get(f"{API_BASE.rstrip('/')}/external",
                    prm={"q": q, "passkey": pk})
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        return resp.get("results", [])
    return []

def remote_title(item: dict) -> str:
    return item.get("title") or item.get("name") or ""

# ----------------------------------------------------------------------
# Comparaison locale ↔︎ distante
# ----------------------------------------------------------------------
def compare(local: dict, remote: dict) -> tuple[str, int]:
    score = 0
    sz_l, sz_r = local.get("size"), remote.get("size")
    exact = close = False

    if sz_l and sz_r:
        diff = abs(sz_l - sz_r)
        avg  = (sz_l + sz_r) / 2
        pct  = diff / avg if avg else 1
        if pct <= 0.01:
            exact = True; score += 1000
        elif pct <= 0.20:
            close = True; score += 500

    codec_match = (local.get("codec") and remote.get("codec") and
                   local["codec"].lower() == remote["codec"].lower())
    if codec_match:
        score += 300

    res_match = (local.get("resolution") and remote.get("resolution") and
                 local["resolution"].lower() == remote["resolution"].lower())
    if res_match:
        score += 200

    if exact:
        ok_c = not local.get("codec") or not remote.get("codec") or codec_match
        ok_r = not local.get("resolution") or not remote.get("resolution") or res_match
        if ok_c and ok_r:
            return "Exact", score
    if close or codec_match or res_match:
        return "Proche", score
    return "Différent", score

# ----------------------------------------------------------------------
# Traitement d’un élément (film / série)
# ----------------------------------------------------------------------
def check(item: dict, pk: str) -> tuple:
    remote = lacale(item["title"], pk, item.get("season"), item.get("episode"))
    if not remote:
        return (item["title"], str(item.get("year","")), item.get("season"),
                item.get("episode"), "Manquant", "-")

    best = max(((compare(item["local_meta"], r), r) for r in remote),
               key=lambda x: x[0][1])
    status, _ = best[0]
    match = remote_title(best[1]) or "-"
    return (item["title"], str(item.get("year","")), item.get("season"),
            item.get("episode"), status, match)

# ----------------------------------------------------------------------
# Parallel processing (max 5 threads)
# ----------------------------------------------------------------------
def run_parallel(items: list, pk: str, limit: int) -> list:
    sel = items[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(check, it, pk): it for it in sel}
        for f in as_completed(futures):
            out.append(f.result())
    time.sleep(0.3)            # pause douce entre lots
    return out

# ----------------------------------------------------------------------
# Légende d’origine
# ----------------------------------------------------------------------
def legend():
    print("\n")
    print(f"{C.BLD}{C.C}╔═══════════════════════════════════════════════════════════════╗{C.Z}")
    print(f"{C.BLD}{C.C}║{C.Z}  {C.BLD}La Cale Checker - Légende des statuts{C.Z}                    {C.BLD}{C.C}║{C.Z}")
    print(f"{C.BLD}{C.C}╚═══════════════════════════════════════════════════════════════╝{C.Z}\n")
    print(f"  {C.G}✅ EXACT{C.Z}      → Fichier identique sur La Cale, tu vas pouvoir seeder facile")
    print(f"  {C.Y}🟩 PROCHE{C.Z}     → Une version similaire est déjà en ligne, à toi de voir !")
    print(f"  {C.O}🟧 DIFFÉRENT{C.Z}  → Il vaut mieux partager plusieurs versions pour que tout le monde soit heureux..")
    print(f"  {C.R}❌ MANQUANT{C.Z}   → Tu vas pouvoir nous offrir ce trésor !\n")
    print("\n")

# ----------------------------------------------------------------------
# Affichage tableau + stats (avec marges)
# ----------------------------------------------------------------------
def show(header: str, rows: list, mode: str):
    # -------- filter ----------
    if mode == "missing":
        rows = [r for r in rows if r[4] == "Manquant"]
    elif mode == "sent":
        rows = [r for r in rows if r[4] == "Exact"]
    elif mode == "versioning":
        rows = [r for r in rows if r[4] in ("Proche", "Différent")]

    # -------- dynamic columns ----------
    has_s = any(r[2] is not None for r in rows)
    has_e = any(r[3] is not None for r in rows)

    cols = ["Titre", "Année"]
    if has_s: cols.append("Saison")
    if has_e: cols.append("Épisode")
    cols.extend(["Statut", "Correspondance"])

    emoji = {"Exact":"✅","Proche":"🟩","Différent":"🟧","Manquant":"❌"}
    table = []
    for t, y, s, e, st, mt in rows:
        row = [t, y]
        if has_s: row.append(str(s) if s else "")
        if has_e: row.append(str(e) if e else "")
        row.append(emoji[st])
        row.append(mt)
        table.append(row)

    print("\n")
    print(f"{C.BLD}{header}{C.Z}\n{'─'*len(header)}")
    print(tabulate(table, headers=cols, tablefmt="github"))
    print("\n")

    # -------- stats ----------
    total = len(rows) or 1
    cnt = {k: sum(1 for r in rows if r[4] == k)
           for k in ("Exact","Proche","Différent","Manquant")}
    print(f"{C.C}📊 Statistiques :{C.Z}")
    for k in ("Exact","Proche","Différent","Manquant"):
        col = getattr(C, {"Exact":"G","Proche":"Y","Différent":"O","Manquant":"R"}[k])
        print(f"  {col}{emoji[k]} {k:<9}{C.Z}: {cnt[k]} ({cnt[k]*100//total}%)")
    print("\n")

# ----------------------------------------------------------------------
# Extraction depuis Radarr
# ----------------------------------------------------------------------
def radarr_items(key: str) -> list:
    data = http_get(f"{RADARR_URL.rstrip('/')}/api/v3/movie",
                    hdr={"X-Api-Key": key})
    if not isinstance(data, list):
        return []
    out = []
    for m in data:
        mf = m.get("movieFile")
        if not mf:
            continue
        path = mf.get("path") or mf.get("relativePath", "")
        fname = Path(path).stem if path else m.get("title", "")
        meta = {
            "size": mf.get("size"),
            "codec": mf.get("mediaInfo",{}).get("videoCodec"),
            "resolution": mf.get("mediaInfo",{}).get("resolution")
        }
        # Si l'API fournit un champ `popularity`, on le garde tel quel.
        out.append({
            "title": m.get("title",""),
            "year": m.get("year"),
            "local_meta": meta,
            "file_name": fname,
            "popularity": m.get("popularity")          # <-- possible champ
        })
    return out

# ----------------------------------------------------------------------
# Extraction depuis un dossier local
# ----------------------------------------------------------------------
def folder_items(root: Path) -> list:
    items = []
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in {".mkv",".mp4",".avi",".mov"}:
            continue
        name = f.stem
        year = None
        m = re.search(r"$$(\d{4})$$", name)
        if m:
            year = int(m.group(1))
            name = name[:m.start()].strip()
        se = re.search(r'(?i)s(?P<season>\d{1,2})(?:[xe]?(?P<episode>\d{1,2}))?', name)
        season = int(se.group('season')) if se else None
        episode = int(se.group('episode')) if se and se.group('episode') else None
        items.append({
            "title": name,
            "year": year,
            "season": season,
            "episode": episode,
            "local_meta": meta_name(f.name),
            # Aucun champ `popularity` dans un dossier local, on laisse vide.
            "popularity": None
        })
    return items

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Comparer votre collection à La Cale.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Tri disponible :
  az               → alphabétique A → Z
  za               → alphabétique Z → A
  newest           → du plus récent au plus ancien (année)
  oldest           → du plus ancien au plus récent (année)
  popular          → par champ `popularity` (descendant)
  least-popular    → par champ `popularity` (ascendant)"""
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--radarr", action="store_true", help="Utiliser l'API Radarr.")
    group.add_argument("--folder", type=Path, help="Analyser un répertoire local.")
    parser.add_argument("-l","--limit", type=int, default=100,
                       help="Nombre max d'éléments à vérifier.")
    parser.add_argument("--sort", choices=[
        "az","za","newest","oldest","popular","least-popular"
    ], default="az", help="Mode de tri.")
    parser.add_argument("--show", choices=["all","missing","sent","versioning"],
                       default="all", help="Filtre d'affichage.")
    parser.add_argument("--radarr-key", default=RADARR_KEY,
                       help="Clé API Radarr (surcharge).")
    args = parser.parse_args()

    if not PASSKEY:
        print(f"{C.R}[ERR]{C.Z} PASSKEY absent dans config.json", file=sys.stderr)
        sys.exit(1)

    # --------------------------------------------------------------
    # Chargement des items
    # --------------------------------------------------------------
    if args.folder:
        if not args.folder.is_dir():
            print(f"{C.R}[ERR]{C.Z} Le chemin indiqué n'est pas un dossier.", file=sys.stderr)
            sys.exit(1)
        items = folder_items(args.folder)
    else:
        items = radarr_items(args.radarr_key)

    if not items:
        print(f"{C.Y}[WARN]{C.Z} Aucun élément trouvé.", file=sys.stderr)
        sys.exit(0)

    # --------------------------------------------------------------
    # Tri
    # --------------------------------------------------------------
    if args.sort in ("az", "za"):
        reverse = args.sort == "za"
        items.sort(key=lambda x: x["title"].lower(), reverse=reverse)

    elif args.sort in ("newest", "oldest"):
        reverse = args.sort == "newest"
        items.sort(key=lambda x: x.get("year") or 0, reverse=reverse)

    elif args.sort == "popular":
        # Si le champ `popularity` existe, on l’utilise ; sinon on revient à l’alphabet.
        if any(item.get("popularity") is not None for item in items):
            items.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        else:
            print(f"{C.Y}[INFO]{C.Z} Popularité non disponible – tri alphabétique appliqué.")
            items.sort(key=lambda x: x["title"].lower())

    elif args.sort == "least-popular":
        if any(item.get("popularity") is not None for item in items):
            items.sort(key=lambda x: x.get("popularity", 0))
        else:
            print(f"{C.Y}[INFO]{C.Z} Popularité non disponible – tri alphabétique inversé appliqué.")
            items.sort(key=lambda x: x["title"].lower(), reverse=True)

    # --------------------------------------------------------------
    # Vérification
    # --------------------------------------------------------------
    rows = run_parallel(items, PASSKEY, args.limit)

    # --------------------------------------------------------------
    # Affichage
    # --------------------------------------------------------------
    legend()
    hdr = f"Top {args.limit} éléments ({'dossier' if args.folder else 'Radarr'})"
    show(hdr, rows, args.show)

if __name__ == "__main__":
    main()
