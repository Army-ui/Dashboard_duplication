# Tableau de bord de Détection de Doublons — Guide de déploiement

## 1. Installation

```bash
cd dashboard
pip install -r requirements.txt
```

## 2. Lancement en développement (sur ton PC)

```bash
python dashboard_app.py
```
Ouvre ensuite `http://127.0.0.1:8050`.

En ce mode, le champ **"Chemin serveur"** fonctionne directement : tape un
chemin local (ex: `C:/Users/toi/Documents`) car le serveur tourne sur la
même machine que toi.

## 3. Comment fonctionne le choix du dossier

Tu as deux modes, sélectionnables via la pilule en haut du formulaire :

| Mode | Quand l'utiliser | Comment ça marche |
|---|---|---|
| **Chemin serveur** | App lancée en local, ou déployée sur un serveur dont l'utilisateur connaît les chemins (ex: NAS d'entreprise monté sur la machine qui héberge l'app) | L'utilisateur tape un chemin texte, le serveur le scanne directement avec `os.walk` |
| **Déposer des fichiers** | App déployée sur le web (Render, Heroku, VM cloud...) — le navigateur de l'utilisateur n'a aucun accès au système de fichiers du serveur | L'utilisateur glisse un dossier depuis son ordinateur ; les fichiers sont uploadés en base64 puis reconstitués sur le serveur dans un dossier temporaire **propre à sa session uniquement** |

Les deux modes utilisent ensuite **exactement le même pipeline** derrière —
aucune duplication de logique.

## 4. Isolation multi-utilisateur — comment ça marche

Chaque onglet de navigateur génère un `session_id` unique (UUID côté
JavaScript, stocké dans un `dcc.Store(storage_type="session")`). Tous les
résultats d'un utilisateur sont sauvegardés dans :

```
dashboard/sessions/<session_id>/
    01_raw.parquet
    02_cleaned.parquet
    03_exact_duplicates.parquet
    04_near_duplicates.parquet
    05_combined.parquet
    05_hotspot.parquet
    05_kpis.parquet
    upload_brut/              (si mode upload utilisé)
```

**Un utilisateur ne peut jamais voir les fichiers ou résultats d'un autre** :
chaque session lit/écrit uniquement dans son propre sous-dossier.

### Nettoyage des sessions

Le dossier `sessions/` grossit avec le temps. En production, mets en place
une tâche planifiée (cron) qui supprime les sous-dossiers de plus de
quelques heures :

```bash
find dashboard/sessions -maxdepth 1 -type d -mmin +120 -exec rm -rf {} \;
```
(supprime tout dossier de session inactif depuis plus de 2h)

## 5. Pourquoi ça ne bloque jamais l'interface pendant un scan

Le bouton "Lancer l'analyse" déclenche un **Background Callback** Dash
(`background=True` + `DiskcacheManager`). Concrètement :

- Le scan tourne dans un processus séparé, pas dans le thread qui répond
  aux clics des autres utilisateurs.
- Une barre de progression se met à jour en temps réel via le paramètre
  `progress=[...]` du callback.
- **`diskcache` ne nécessite aucune infrastructure externe** — pas de Redis,
  pas de Celery à installer. Le cache vit simplement dans
  `dashboard/sessions/_diskcache/`.

## 6. Déploiement en production — points d'attention

### Un seul worker (recommandé pour démarrer)
```bash
gunicorn dashboard_app:server -w 1 -b 0.0.0.0:8000 --timeout 600
```
`--timeout 600` est important : un gros scan peut prendre plusieurs minutes,
augmente ce délai si besoin selon la taille des dossiers attendus.

### Plusieurs workers (si tu as besoin de scalabilité)
`DiskcacheManager` fonctionne aussi en multi-worker car il écrit sur disque
(pas en mémoire RAM du process), donc **pas de modification nécessaire**
contrairement à un cache en mémoire classique. Teste tout de même en
charge avant un vrai déploiement multi-worker.

### Limite de taille d'upload
Si tu utilises le mode "Déposer des fichiers" en production avec de gros
volumes, configure une limite cohérente côté reverse proxy (nginx) :
```nginx
client_max_body_size 500M;
```

## 7. Bugs corrigés lors de la revue de code

Pendant la vérification de ce projet, deux bugs ont été identifiés et
corrigés (DataFrame vide ou colonne manquante provoquant une `KeyError`
silencieuse) :
- `dashboard_app.py` — filtrage des fenêtres de listes exact/quasi
- `pipeline/etape5_hotspots.py` — fusion des deux sources de duplication

Le pipeline a été testé bout-en-bout sur un dossier réel (avec doublon
détecté correctement) et sur un dossier vide (aucun crash).

## 8. Limites connues / pistes d'amélioration

- Le score de similarité cosinus (étape 4) est désactivé au-delà de 5000
  fichiers candidats pour éviter un calcul trop lent (complexité O(n²)).
  Sur de très gros dépôts, augmente ce seuil seulement si tu as les
  ressources CPU nécessaires.
- L'extraction `dépôt / unité métier / propriétaire` (étape 5) suppose une
  convention de chemin `/<dépôt>/<unité>/<propriétaire>/...`. Adapte la
  fonction `extraire_segment()` dans `pipeline/etape5_hotspots.py` si ta
  structure de dossiers réelle est différente.
- Les paramètres DBSCAN (`eps`, `min_samples`) sont actuellement fixés en
  dur dans l'appel au pipeline. Un panneau "Paramètres avancés" est déjà
  prévu dans les traductions (`i18n.py` → `scan_eps_label`,
  `scan_minsamples_label`) mais pas encore branché dans l'interface.