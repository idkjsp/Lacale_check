lacale_check – vérifie la présence de films, séries, saisons ou épisodes sur le tracker La Cale.

Fonctionnalités
---------------
* Lecture de Radarr, Sonarr ou d’un dossier local.
* Recherche sur La Cale au niveau : full, season ou episode.
* Gestion du 429 (rate‑limit) avec retries exponentiels.
* Exécution parallèle des requêtes La Cale.
* Affichage enrichi (titre, année, saison, épisode, présent / absent).
* Export CSV optionnel.
* Tris disponibles : oldest, newest, popular, least‑popular, az.
* `--hide-present` masque les titres déjà présents.

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
|--hide-present|Masquer les titres déjà présents sur La Cale|
|--export FILE.csv|Exporter le tableau affiché au format CSV|
|--sort|Trier par : oldest / newest / az (A-Z) / popular / least-popular|
|--radarr-key KEY / --sonarr-key KEY|Remplacer la clé définie dans config.json.|


## 📚 Exemples concret
### Voir vos films manquants sur La Cale
```bash
python lacale_check.py --radarr  --hide-present --limit 999999
```

Séries Sonarr – quelles saisons manquent ?
```bash
python lacale_check.py --sonarr --mode season --hide-present --limit 30
```

Dossier local – quels épisodes sont absents ? (et on garde un CSV)
```bash
python lacale_check.py --folder ./mes_videos --mode episode --export manquants.csv
```


## Exemple de sortie
```console
Top 10 les plus populaires
--------------------------
| Titre                         |   Année | Sur La Cale   |
|-------------------------------|---------|---------------|
| Avatar : De feu et de cendres |    2025 | ❌ Non         |
| People We Meet on Vacation    |    2026 | ✅ Oui         |
| Zootopie 2                    |    2025 | ✅ Oui         |
| Une bataille après l'autre    |    2025 | ❌ Non         |
| Insaisissables 3              |    2025 | ❌ Non         |
| Fight Club                    |    1999 | ✅ Oui         |
| Troll 2                       |    2025 | ✅ Oui         |
| Avatar : La Voie de l'eau     |    2022 | ✅ Oui         |
| Tron : Ares                   |    2025 | ✅ Oui         |
| Zootopie                      |    2016 | ✅ Oui         |
```

# Changelog
### 1.0.1
* Blocage de recherche des films suivis sur Radarr mais sous l'état "manquant"
* Réduction des faux négatifs (via l'utilisation des titres originaux, des titres vf, et d'une normalisation)
* Modifs mineures

## À venir
- Comparer les versions locales et présentent sur La Cale
- Dire si le fichier est identique ou evaluer si votre version a un intérêt
- Réduction des faux négatifs (encore)
- Amélioration du support de Sonarr (trouver une série en intégrale ou juste toutes les saisons une à une par exemple)

### 📧 Contact
idkjspp@proton.me

### 🛡️ Licence 
MIT – libre d'utilisation, de modification et de redistribution.
