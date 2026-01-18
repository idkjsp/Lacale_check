lacale_check – vérifie la présence de films, séries, saisons ou épisodes sur le tracker La Cale.

Fonctionnalités
---------------
* Lecture de Radarr, Sonarr ou d’un dossier local.
* Recherche sur La Cale au niveau : full, season ou episode.
* Gestion du 429 (rate‑limit) avec retries exponentiels.
* Export CSV
* Tris disponibles : oldest, newest, popular, least‑popular, az, za
* 4 états: Exact, Proche, Différent, Manquant (✅ / 🟩 / 🟧 / ❌)

## 📦 Prérequis
```bash
pip install requests tabulate
```

> requests gère les appels HTTP proprement, tabulate rend le tableau lisible dans le terminal.

## ⚙️ Configuration (config.json)
Crée un fichier **config.json** à côté du script :
```json
{
  "RADARR_URL": "http://127.0.0.1:7878",
  "SONARR_URL": "http://127.0.0.1:8989",
  "RADARR_API_KEY": "ta‑clé‑radarr",
  "SONARR_API_KEY": "ta‑clé‑sonarr",
  "LACALE_PASSKEY": "ta‑clé‑la‑cale",
  "LACALE_API_BASE": "https://tracker.la-cale.space/api"
}
```

> 🔒 Ne le versionne jamais – ajoute‑le à ton .gitignore. 



## 🚀 Utilisation
```bash
python lacale_check.py [OPTIONS]
```

### Sources (choisis une seule)
| Option | Description  |
|---------|--------|
|--radarr|Analyse la bibliothèque Radarr (films)|
|--sonarr|Analyse la bibliothèque Sonarr (séries)|
|--folder PATH|Analyse un répertoire local contenant des vidéos|

### Modes (défaut : full)

|--mode|Requête|
|-------|-------|
|full|Vérifie si au moins un épisode est disponible|
|season|Une requête par saison|
|episode|Une requête par épisode|


### Options utiles
|Option|Description|
|-------|-------|
|-l / --limit N|Nombre max d’éléments (ou de saisons/épisodes) à traiter (défaut 100)|
|--year-min Y / --year-max Y|Filtrer les titres par année de production|
|--show|All / Missing / Sent / Versioning|
|--export FILE.csv|Exporter le tableau affiché au format CSV|
|--sort|Trier par : oldest / newest / az (A-Z) / za (Z-A) / popular / least-popular|
|--radarr-key KEY / --sonarr-key KEY|Remplacer la clé définie dans config.json|


## 📚 Exemples concret
### Voir vos films manquants sur La Cale
```bash
python lacale_check.py --radarr  --show missing --limit 999999
```

Séries Sonarr – quelles saisons manquent ?
```bash
python lacale_check.py --sonarr --mode season --show missing --limit 30
```

Dossier local – quels épisodes sont absents ? (et on garde un CSV)
```bash
python lacale_check.py --folder ./mes_videos --mode episode --export manquants.csv
```


## Exemple de sortie


```console
╔═══════════════════════════════════════════════════════════════╗
║  La Cale Checker - Légende des statuts                    ║
╚═══════════════════════════════════════════════════════════════╝

  ✅ EXACT      → Fichier identique sur La Cale, tu vas pouvoir seeder facile
  🟩 PROCHE     → Une version similaire est déjà en ligne, à toi de voir !
  🟧 DIFFÉRENT  → Il vaut mieux partager plusieurs versions pour que tout le monde soit heureux..
  ❌ MANQUANT   → Tu vas pouvoir nous offrir ce trésor !





Top 27 éléments (Radarr)
────────────────────────
| Titre                             |   Année | Statut   | Correspondance                                                                                                                    |
|-----------------------------------|---------|----------|-----------------------------------------------------------------------------------------------------------------------------------|
| Thunderbolts*                     |    2025 | 🟩        | Thunderbolts.2025.MULTi.TRUEFRENCH.1080p.WEB-DL.Dolby.Atmos.7.1.H265-Slay3R                                                       |
| People We Meet on Vacation        |    2026 | ✅        | People.We.Meet.on.Vacation.2026.MULTi.1080p.WEBrip.10.bits.EAC3.5.1.x265-TyHD                                                     |
| F1® Le Film                       |    2025 | 🟧        | F1 Le Film (2025) Hybrid MULTi VFF 2160p 10bit 4KLight DV HDR10Plus BluRay DDP 5.1 Atmos x265-QTZ (F1 The Movie)                  |
| Superman                          |    2025 | 🟧        | Superman.And.Lois.S04.MULTI.1080p.WEB.MAX.H265.EAC3.5.1-Amen                                                                      |
| Sinners                           |    2025 | 🟩        | Sinners.2025.MULTi.VF2.1080p.WEBRip.AC3.5.1.H264-LiHDL                                                                            |
| Elio                              |    2025 | 🟩        | Evangelion.1.11.You.Are.Not.Alone.2007.MULTi.1080p.WEB.H265-FW                                                                    |
| The Gorge                         |    2025 | ✅        | The.Gorge.2025.MULTi.1080p.WEB.H265-FW                                                                                            |
| Les 4 Fantastiques : Premiers pas |    2025 | 🟧        | The.Fantastic.Four.First.Steps.2025.MULTi.2160p.IMAX.DV.DSNP.WEB-DL.DDP5.1.Atmos.H265-R3DUCT0 (Les 4 Fantastiques : Premiers pas) |
| Mickey 17                         |    2025 | ✅        | Mickey.17.2025.MULTi.VF2.1080p.WEBrip.EAC3.5.1.x265-TyHD                                                                          |
| Captain America : Brave New World |    2025 | 🟩        | Captain.America.Brave.New.World.2025.MULTi.VF2.1080p.BluRay.HDLight.AC3.5.1.x264-LiHDL                                            |
| Évanouis                          |    2025 | ❌        | -                                                                                                                                 |
| Together                          |    2025 | ✅        | Together.2025.MULTi.VFQ.SDR.2160p.WEBrip.EAC3.5.1.x265-TyHD                                                                       |
| Materialists                      |    2025 | ✅        | Materialists 2025 VFF 1080p BluRay mHD x264 AC3-ROMKENT                                                                           |
| Nobody 2                          |    2025 | 🟧        | Mr Nobody.2009.Extended.BR.EAC3.VFF.VO.1080p.x265.10Bits-T0M                                                                      |
| Pris au piège - Caught Stealing   |    2025 | ❌        | -                                                                                                                                 |
| Le Murder Club du jeudi           |    2025 | ❌        | -                                                                                                                                 |
| Substitution : Bring Her Back     |    2025 | ❌        | -                                                                                                                                 |
| 28 Ans plus tard                  |    2025 | 🟧        | 28 Ans plus tard (2025) Hybrid MULTi VFF 2160p 10bit 4KLight DV HDR10Plus BluRay DDP 5.1 Atmos x265-QTZ (28 Years Later)          |
| La Guerre des Rose                |    2025 | ❌        | -                                                                                                                                 |
| Marche ou crève                   |    2025 | ❌        | -                                                                                                                                 |
| Lilo & Stitch                     |    2025 | 🟧        | Lilo & Stitch (2025) Hybrid MULTi VFF 2160p 10bit 4KLight DV HDR10Plus BluRay DDP 5.1 Atmos x265-QTZ                              |
| Dragons                           |    2025 | 🟧        | Donjons & Dragons : L'Honneur des voleurs 2023 REPACK MULTi VFF 2160p 10bit 4KLight DV HDR BluRay DDP 5.1 Atmos x265-QTZ          |
| Destination finale : Bloodlines   |    2025 | ❌        | -                                                                                                                                 |
| Companion                         |    2025 | 🟧        | Companion.2025.MULTi.VF2.2160p.HDR.DV.WEB.DL.H265-Slay3R                                                                          |
| Balle perdue 3                    |    2025 | 🟧        | Balle.Perdue.3.2025.VOF.AD.2160p.WEBRip.SDR.x265.EAC3.5.1-Amen                                                                    |
| The Amateur                       |    2025 | ✅        | The.Amateur.2025.MULTi.VF2.1080p.WEBrip.EAC3.5.1.x265-TyHD                                                                        |
| Ballerina                         |    2025 | ✅        | Ballerina.2025.PROPER.MULTi.VF2.AD.1080p.WEBrip.EAC3.5.1.x265-TyHD                                                                |


📊 Statistiques :
  ✅ Exact    : 7 (25%)
  🟩 Proche   : 4 (14%)
  🟧 Différent: 9 (33%)
  ❌ Manquant : 7 (25%)
```


# Changelog
### 1.0.2
* Blockage temporaire de Sonarr
* Comparer les versions locales avec celle de La Cale, vous pourrez donc voir si une cargaisson attend d'être partagé urgement, ou si quelqu'un d'autre l'a fait mais sous un format différent !
* Réduction des faux négatifs (encore)
* Modifs CLI
* Bugs/Fixs divers
### 1.0.1
* Blocage de recherche des films suivis sur Radarr mais sous l'état "manquant"
* Réduction des faux négatifs (via l'utilisation des titres originaux, des titres vf, et d'une normalisation)
* Bugs/Fixs divers

## À venirs
- Comparer les versions plus profondemment 
- Réduction des faux négatifs (encore)
- Amélioration du support de Sonarr (trouver une série en intégrale ou juste toutes les saisons une à une par exemple)

### 📧 Contact
idkjspp@proton.me

### 🛡️ Licence 
MIT – libre d'utilisation, de modification et de redistribution.
