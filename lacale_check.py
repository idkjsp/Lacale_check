#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
lacale_check – vérifie la présence de films, séries, saisons ou épisodes
sur le tracker La Cale.

Fonctionnalités
---------------
* Lecture de Radarr, Sonarr ou d’un dossier local.
* Recherche sur La Cale au niveau : full, season ou episode.
* Gestion du 429 (rate‑limit) avec retries exponentiels.
* Exécution parallèle des requêtes La Cale.
* Affichage enrichi (titre, année, saison, épisode, présent / absent).
* Export CSV optionnel.
* Tris disponibles : oldest, newest, popular, least‑popular, instant.
* `--hide-present` masque les titres déjà présents.
"""

import argparse, csv, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import requests
from tabulate import tabulate

# ----------------------------------------------------------------------
# 1️⃣  Configuration (config.json à la racine)
# ----------------------------------------------------------------------
CFG_PATH = Path(__file__).with_name("config.json")
if not CFG_PATH.is_file():
    print(f"[ERROR] config.json manquant : {CFG_PATH}", file=sys.stderr)
    sys.exit(1)

CFG = json.loads(CFG_PATH.read_text())
RADARR_URL = CFG["RADARR_URL"]
SONARR_URL = CFG["SONARR_URL"]
RADARR_KEY = CFG["RADARR_API_KEY"]
SONARR_KEY = CFG["SONARR_API_KEY"]
PASSKEY    = CFG["LACALE_PASSKEY"]
API_BASE   = CFG["LACALE_API_BASE"]

# ----------------------------------------------------------------------
# 2️⃣  Paramètres généraux
# ----------------------------------------------------------------------
TIMEOUT = 15                # secondes
DELAY   = 0.30              # secondes entre deux appels La Cale
MAX_R   = 3
BF      = 2                 # back‑off factor (2, 4, 8…)

# ----------------------------------------------------------------------
# 3️⃣  HTTP wrapper (rate‑limit aware)
# ----------------------------------------------------------------------
def http_get(url: str, *, hdr: dict = None, prm: dict = None) -> dict:
    attempt = 0
    while True:
        try:
            r = requests.get(url, headers=hdr, params=prm, timeout=TIMEOUT)
            if r.status_code == 429:
                if attempt >= MAX_R:
                    print(f"[ERROR] 429 trop de fois pour {url}", file=sys.stderr)
                    return {}
                wait = BF ** attempt
                print(f"[WARN] 429 – pause {wait}s", file=sys.stderr)
                time.sleep(wait)
                attempt += 1
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"[ERROR] {url} → {e}", file=sys.stderr)
            return {}

# ----------------------------------------------------------------------
# 4️⃣  API helpers
# ----------------------------------------------------------------------
def radarr_movies(key: str) -> List[Dict]:
    return http_get(f"{RADARR_URL.rstrip('/')}/api/v3/movie",
                    hdr={"X-Api-Key": key}) or []


def sonarr_series(key: str) -> List[Dict]:
    """Renvoie les séries avec leurs numéros de saisons."""
    data = http_get(f"{SONARR_URL.rstrip('/')}/api/v3/series",
                    hdr={"X-Api-Key": key}) or []
    for s in data:
        s["season_numbers"] = [sn["seasonNumber"] for sn in s.get("seasons", [])]
    return data


def sonarr_episodes(key: str) -> List[Dict]:
    """Liste plate d’épisodes : title, year, season, episode."""
    series = sonarr_series(key)
    id_title = {s["id"]: s.get("title", "??") for s in series}
    id_year  = {s["id"]: s.get("year") for s in series}
    eps = []
    for sid in id_title:
        ep_url = f"{SONARR_URL.rstrip('/')}/api/v3/episode"
        lst = http_get(ep_url, hdr={"X-Api-Key": key},
                       prm={"seriesId": sid}) or []
        for e in lst:
            eps.append({
                "title":   id_title[sid],
                "year":    id_year[sid],
                "season":  e.get("seasonNumber"),
                "episode": e.get("episodeNumber"),
            })
    return eps

# ----------------------------------------------------------------------
# 5️⃣  Parse saison/épisode depuis le nom de fichier
# ----------------------------------------------------------------------
SE_RE = re.compile(r"(?i)s(?P<season>\d{1,2})(?:[xe]?(?P<episode>\d{1,2}))?")

def parse_se_ep(name: str) -> Tuple[Optional[int], Optional[int]]:
    m = SE_RE.search(name)
    if not m:
        return None, None
    season = int(m.group("season"))
    ep = m.group("episode")
    episode = int(ep) if ep else None
    return season, episode

# ----------------------------------------------------------------------
# 6️⃣  Recherche sur La Cale
# ----------------------------------------------------------------------
def build_query(t: str, s: Optional[int] = None, e: Optional[int] = None) -> str:
    q = t.strip()
    if s is not None:
        q += f" S{s:02d}"
    if e is not None:
        q += f"E{e:02d}"
    return q


def lacale_search(t: str, pk: str,
                  s: Optional[int] = None,
                  e: Optional[int] = None) -> bool:
    params = {"q": build_query(t, s, e), "passkey": pk}
    data = http_get(f"{API_BASE.rstrip('/')}/external", prm=params)
    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = data.get("results", [])
    else:
        results = []
    return bool(results)

# ----------------------------------------------------------------------
# 7️⃣  Sorting (full‑mode uniquement)
# ----------------------------------------------------------------------
def sort_items(lst: List[Dict], mode: str) -> List[Dict]:
    """
    mode ∈ {oldest, newest, popular, least-popular, instant}
    - oldest         → année croissante
    - newest         → année décroissante
    - popular        → tri descendant sur le champ `popularity`
    - least-popular  → tri ascendant sur le champ `popularity`
    - instant        → aucun tri (retour tel quel, ou alphabétique si besoin)
    """
    if mode == "oldest":
        return sorted(lst, key=lambda x: (x.get("year", 9999), x.get("title", "").lower()))

    if mode == "newest":
        return sorted(lst, key=lambda x: (-(x.get("year", 0)), x.get("title", "").lower()))

    if mode == "popular":
        return sorted(lst, key=lambda x: x.get("popularity", 0), reverse=True)

    if mode == "least-popular":
        return sorted(lst, key=lambda x: x.get("popularity", 0))

    if mode == "instant":
        # Aucun tri réel : on garde l’ordre d’origine.
        # Si on veut un fallback stable, on trie alphabétiquement.
        return sorted(lst, key=lambda x: x.get("title", "").lower())

    # fallback (ne devrait jamais arriver)
    return sorted(lst, key=lambda x: x.get("title", "").lower())

# ----------------------------------------------------------------------
# 8️⃣  Build rows (parallelisé)
# ----------------------------------------------------------------------
def check_one(item: Dict, pk: str, lvl: str,
              season: Optional[int] = None,
              episode: Optional[int] = None) -> Tuple[str, str,
                                                      Optional[int],
                                                      Optional[int],
                                                      bool]:
    """Retourne (title, year, season, episode, présent?)."""
    t = item.get("title", "??")
    y = str(item.get("year", ""))
    present = lacale_search(t, pk, season, episode)
    return (t, y, season, episode, present)


def parallel_report(items: List[Dict], pk: str, limit: int,
                    workers: int, lvl: str) -> List[Tuple]:
    sel = items[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_one, it, pk, lvl): it for it in sel}
        for f in as_completed(futures):
            out.append(f.result())
            time.sleep(DELAY)
    return out


def build_report_seasons(series: List[Dict], pk: str,
                         limit: int, workers: int) -> List[Tuple]:
    """Un appel par (série, saison)."""
    tasks = []
    for s in series:
        for sn in s.get("season_numbers", []):
            tasks.append((s, sn))
    tasks = tasks[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(check_one, serie, pk, "season", sn, None): (serie, sn)
            for serie, sn in tasks
        }
        for f in as_completed(futs):
            out.append(f.result())
            time.sleep(DELAY)
    return out


def build_report_episodes(episodes: List[Dict], pk: str,
                          limit: int, workers: int) -> List[Tuple]:
    """Un appel par (série, saison, épisode)."""
    tasks = episodes[:limit]
    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(check_one, ep, pk, "episode",
                        ep.get("season"), ep.get("episode")): ep
            for ep in tasks
        }
        for f in as_completed(futs):
            out.append(f.result())
            time.sleep(DELAY)
    return out

# ----------------------------------------------------------------------
# 9️⃣  Display / CSV (colonnes dynamiques)
# ----------------------------------------------------------------------
def display(header: str, rows: List[Tuple],
            csv_path: Optional[Path] = None,
            hide_present: bool = False,
            mode: str = "full") -> None:
    print("\n" + header)
    print("-" * len(header))

    cols = ["Titre", "Année"]
    if mode in ("season", "episode"):
        cols.append("Saison")
    if mode == "episode":
        cols.append("Épisode")
    cols.append("Sur La Cale")

    filtered = [r for r in rows if not (hide_present and r[-1])]

    table = []
    for t, y, s, e, pres in filtered:
        row = [t, y]
        if mode in ("season", "episode"):
            row.append(str(s) if s is not None else "")
        if mode == "episode":
            row.append(str(e) if e is not None else "")
        row.append("✅ Oui" if pres else "❌ Non")
        table.append(row)

    print(tabulate(table, headers=cols, tablefmt="github"))

    if csv_path:
        mode_write = "a" if csv_path.exists() else "w"
        with csv_path.open(mode_write, newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if mode_write == "w":
                w.writerow(cols)
            w.writerows(table)

# ----------------------------------------------------------------------
# 🔟  Main
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--radarr", action="store_true")
    grp.add_argument("--sonarr", action="store_true")
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--export", type=Path, metavar="fichier.csv")
    parser.add_argument("--radarr-key", default=RADARR_KEY)
    parser.add_argument("--sonarr-key", default=SONARR_KEY)
    parser.add_argument("-l", "--limit", type=int, default=10)
    parser.add_argument(
        "--sort",
        choices=["oldest", "newest", "popular", "least-popular", "instant"],
        help="Tri (mode full uniquement)."
    )
    parser.add_argument(
        "--mode",
        choices=["full", "season", "episode"],
        default="full",
        help="full = titre, season = Sxx, episode = SxxExx."
    )
    parser.add_argument(
        "--hide-present",
        action="store_true",
        help="Masquer les titres déjà présents sur La Cale."
    )
    parser.add_argument("--year-min", type=int, help="Année minimale.")
    parser.add_argument("--year-max", type=int, help="Année maximale.")
    args = parser.parse_args()

    if not PASSKEY:
        print("[ERROR] PASSKEY manquant dans config.json.", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------
    # Validation : les films n’ont ni saison ni épisode
    # -------------------------------------------------
    if args.radarr and args.mode != "full":
        print("[ERROR] Mode 'season' ou 'episode' impossible avec --radarr (films).",
              file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------
    # Load source data
    # -------------------------------------------------
    if args.folder:
        if not args.folder.is_dir():
            print(f"[ERROR] {args.folder} n'est pas un répertoire.", file=sys.stderr)
            sys.exit(1)

        items = []
        for p in args.folder.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov"}:
                title = p.stem
                year = ""
                if "(" in title and ")" in title.split("(")[-1]:
                    y = title.split("(")[-1].split(")")[0]
                    if y.isdigit() and len(y) == 4:
                        year = y
                        title = title.split("(")[0].strip()
                s, e = parse_se_ep(title)
                items.append({
                    "title": title,
                    "year": int(year) if year else None,
                    "season": s,
                    "episode": e,
                })
        source = "folder"
    else:
        if args.radarr:
            items = radarr_movies(args.radarr_key or RADARR_KEY)
            source = "radarr"
        else:  # Sonarr
            key = args.sonarr_key or SONARR_KEY
            if args.mode == "full" or args.mode == "season":
                items = sonarr_series(key)
            else:  # episode
                items = sonarr_episodes(key)
            source = "sonarr"

    if not items:
        print("[ERROR] Aucun élément trouvé.", file=sys.stderr)
        sys.exit(1)

    # -------------------------------------------------
    # Apply year filters (if any)
    # -------------------------------------------------
    if args.year_min is not None or args.year_max is not None:
        def in_range(item):
            yr = item.get("year")
            if yr is None:
                return False
            if args.year_min is not None and yr < args.year_min:
                return False
            if args.year_max is not None and yr > args.year_max:
                return False
            return True
        items = [it for it in items if in_range(it)]
        if not items:
            print("[ERROR] Aucun élément ne correspond aux filtres d'année.", file=sys.stderr)
            sys.exit(1)

    # -------------------------------------------------
    # Display / export
    # -------------------------------------------------
    if args.mode == "full":
        if args.sort:
            sorted_items = sort_items(items, args.sort)
            hdr = {
                "oldest":        f"Top {args.limit} plus anciens",
                "newest":        f"Top {args.limit} plus récents",
                "popular":       f"Top {args.limit} les plus populaires",
                "least-popular": f"Top {args.limit} les moins populaires",
                "instant":       f"Top {args.limit} (ordre d'origine)",
            }[args.sort]
            rows = parallel_report(sorted_items, PASSKEY, args.limit, 5, "full")
            display(hdr, rows, args.export, args.hide_present, mode="full")
        else:
            rows = parallel_report(items, PASSKEY, args.limit, 5, "full")
            display(f"Premiers {args.limit} éléments (ordre d'origine)",
                    rows, args.export, args.hide_present, mode="full")

    elif args.mode == "season":
        rows = build_report_seasons(items, PASSKEY, args.limit, workers=5)
        display(f"Saisons (max {args.limit})", rows,
                args.export, args.hide_present, mode="season")

    else:  # episode
        rows = build_report_episodes(items, PASSKEY, args.limit, workers=5)
        display(f"Épisodes (max {args.limit})", rows,
                args.export, args.hide_present, mode="episode")


if __name__ == "__main__":
    main()
