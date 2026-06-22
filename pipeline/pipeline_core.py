"""
pipeline_core.py
================
Les 5 scripts du pipeline (scan, nettoyage, doublons exacts, quasi-doublons,
agrégation) réécrits comme des FONCTIONS PURES :
- Pas de chemins de fichiers codés en dur
- Pas de print() — la progression est remontée via un callback
- Chaque étape retourne un DataFrame, ne lit/écrit rien sur disque sauf
  indication explicite (utile pour l'isolation multi-utilisateur)

Ce module est appelé par worker.py, jamais directement par dashboard_app.py.
"""

import os
import re
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity


EXCLUSIONS_DEFAUT = ["AppData", "Program Files", "Windows", ".git", "__pycache__", "node_modules"]


# =========================================================================
# ÉTAPE 1 — SCAN ET HACHAGE
# =========================================================================

def calculer_md5(chemin):
    """Calcule le hash MD5 d'un fichier par lecture en blocs de 4 Ko."""
    try:
        hash_md5 = hashlib.md5()
        with open(chemin, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def _traiter_fichier(chemin_complet):
    """Extrait les métadonnées d'un seul fichier. Retourne None si inaccessible."""
    try:
        return {
            "nom_fichier": os.path.basename(chemin_complet),
            "chemin": chemin_complet,
            "taille_octets": os.path.getsize(chemin_complet),
            "extension": os.path.splitext(chemin_complet)[1],
            "hash_md5": calculer_md5(chemin_complet),
            "date_creation": datetime.fromtimestamp(os.path.getctime(chemin_complet)).strftime("%Y-%m-%d %H:%M:%S"),
            "date_modification": datetime.fromtimestamp(os.path.getmtime(chemin_complet)).strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (PermissionError, FileNotFoundError, OSError):
        return None


def scanner_dossier(dossier_cible, nb_threads=4, exclusions=None, on_progress=None):
    """
    Parcourt récursivement dossier_cible, calcule les métadonnées + hash MD5
    de chaque fichier en parallèle.

    on_progress(fraction: float, message: str) est appelé régulièrement pour
    remonter l'avancement au worker (et donc à la barre de progression UI).

    Retourne un DataFrame brut (équivalent raw_file_metadata.csv).
    """
    exclusions = exclusions or EXCLUSIONS_DEFAUT

    if on_progress:
        on_progress(0.02, "Listing des fichiers...")

    liste_fichiers = []
    for dossier, sous_dossiers, fichiers in os.walk(dossier_cible):
        sous_dossiers[:] = [d for d in sous_dossiers if not any(ex in d for ex in exclusions)]
        for fichier in fichiers:
            liste_fichiers.append(os.path.join(dossier, fichier))

    total = len(liste_fichiers)
    if total == 0:
        return pd.DataFrame(columns=[
            "nom_fichier", "chemin", "taille_octets", "extension",
            "hash_md5", "date_creation", "date_modification",
        ])

    donnees = []
    with ThreadPoolExecutor(max_workers=nb_threads) as executor:
        futures = {executor.submit(_traiter_fichier, f): f for f in liste_fichiers}
        for i, future in enumerate(as_completed(futures)):
            resultat = future.result()
            if resultat:
                donnees.append(resultat)
            if on_progress and i % max(1, total // 50) == 0:
                fraction = 0.02 + 0.28 * (i / total)   # le scan occupe 2% → 30% de la barre globale
                on_progress(fraction, f"Scan : {i:,}/{total:,} fichiers".replace(",", " "))

    if on_progress:
        on_progress(0.30, f"Scan terminé — {len(donnees):,} fichiers".replace(",", " "))

    return pd.DataFrame(donnees)


# =========================================================================
# ÉTAPE 2 — NETTOYAGE ET FEATURE ENGINEERING
# =========================================================================

def _supprimer_extension(nom):
    if "." in nom:
        return ".".join(nom.split(".")[:-1])
    return nom


def _categoriser_taille(taille):
    if taille < 1_000_000:
        return "Petit"
    elif taille < 100_000_000:
        return "Moyen"
    return "Grand"


def nettoyer_metadonnees(df_brut, on_progress=None):
    """
    Nettoie et enrichit le DataFrame brut issu de scanner_dossier().
    Retourne le dataset prêt pour la détection (équivalent cleaned_file_metadata.xlsx).
    """
    if on_progress:
        on_progress(0.32, "Nettoyage des métadonnées...")

    df = df_brut.copy()

    colonnes_requises = ["nom_fichier", "chemin", "taille_octets", "hash_md5", "date_creation", "date_modification"]
    df = df.dropna(subset=[c for c in colonnes_requises if c in df.columns])

    if "extension" in df.columns:
        df = df.dropna(subset=["extension"])
        df = df[df["extension"].astype(str).str.strip() != ""]

    if len(df) == 0:
        return df

    df["nom_fichier"] = df["nom_fichier"].str.lower().str.strip()
    df["extension"] = df["extension"].str.lower().str.strip()
    df["chemin"] = df["chemin"].astype(str).str.replace("\\\\", "/", regex=True).str.replace("\\", "/", regex=False)

    df["date_creation"] = pd.to_datetime(df["date_creation"], errors="coerce")
    df["date_modification"] = pd.to_datetime(df["date_modification"], errors="coerce")
    df = df.dropna(subset=["date_creation", "date_modification"])
    df = df[df["date_creation"] <= df["date_modification"]]

    df = df.drop_duplicates(subset=["chemin"])

    df["nom_sans_extension"] = df["nom_fichier"].apply(_supprimer_extension)
    df["nom_fichier"] = df["nom_sans_extension"].apply(lambda x: re.sub(r"[^a-zA-Z0-9]", "", str(x)))
    df = df[df["nom_fichier"] != ""]

    if on_progress:
        on_progress(0.38, "Feature engineering...")

    df["chemin_dossier"] = df["chemin"].apply(lambda x: "/".join(x.split("/")[:-1]))
    df["profondeur_dossier"] = df["chemin_dossier"].apply(lambda x: len([p for p in x.split("/") if p != ""]))
    df["categorie_taille_fichier"] = df["taille_octets"].apply(_categoriser_taille)

    aujourdhui = pd.Timestamp(datetime.now())
    df["age_fichier"] = (aujourdhui - df["date_creation"]).dt.days
    df["jours_depuis_modification"] = (aujourdhui - df["date_modification"]).dt.days
    df["taille_lisible"] = df["taille_octets"].apply(lambda t: f"{round(t / (1024 * 1024), 2)} MB")

    colonnes_finales = [
        "nom_fichier", "chemin", "chemin_dossier", "profondeur_dossier",
        "taille_octets", "taille_lisible", "categorie_taille_fichier", "extension",
        "hash_md5", "date_creation", "date_modification", "age_fichier", "jours_depuis_modification",
    ]

    if on_progress:
        on_progress(0.40, f"Nettoyage terminé — {len(df):,} fichiers valides".replace(",", " "))

    return df[colonnes_finales].reset_index(drop=True)


# =========================================================================
# ÉTAPE 3 — DOUBLONS EXACTS
# =========================================================================

def detecter_doublons_exacts(df_clean, on_progress=None):
    """
    Détecte les doublons exacts par (hash_md5, taille_octets).
    Retourne le DataFrame enrichi (équivalent exact_duplicates_flagged.xlsx, onglet Tous_Fichiers).
    """
    if on_progress:
        on_progress(0.45, "Détection des doublons exacts...")

    if len(df_clean) == 0:
        return df_clean.assign(
            nb_occurrences=pd.Series(dtype=int), est_doublon_exact=pd.Series(dtype=bool),
            rang_dans_groupe=pd.Series(dtype=int), id_groupe_doublon=pd.Series(dtype=int),
            statut_doublon=pd.Series(dtype=str),
        )

    df = df_clean.copy()
    cles = ["hash_md5", "taille_octets"]

    comptage = df.groupby(cles).size().reset_index(name="nb_occurrences")
    df = df.merge(comptage, on=cles, how="left")
    df["est_doublon_exact"] = df["nb_occurrences"] > 1

    df["rang_dans_groupe"] = (
        df.sort_values("date_creation").groupby(cles).cumcount() + 1
    )

    groupes = df[df["est_doublon_exact"]].groupby(cles).ngroup()
    df.loc[df["est_doublon_exact"], "id_groupe_doublon"] = groupes.values
    df["id_groupe_doublon"] = df["id_groupe_doublon"].fillna(-1).astype(int)

    def _statut(row):
        if not row["est_doublon_exact"]:
            return "Unique"
        elif row["rang_dans_groupe"] == 1:
            return "Original"
        return f"Doublon #{row['rang_dans_groupe'] - 1}"

    df["statut_doublon"] = df.apply(_statut, axis=1)

    if on_progress:
        nb_doublons = df["est_doublon_exact"].sum()
        on_progress(0.55, f"Doublons exacts détectés — {nb_doublons:,}".replace(",", " "))

    return df


# =========================================================================
# ÉTAPE 4 — QUASI-DOUBLONS (DBSCAN)
# =========================================================================

def detecter_quasi_doublons(df_exact, eps=1.5, min_samples=2, on_progress=None):
    """
    Détecte les quasi-doublons par clustering DBSCAN parmi les fichiers
    "Unique" et "Original" (les copies exactes sont déjà traitées à l'étape 3).
    Retourne le DataFrame enrichi (équivalent near_duplicate_clusters.xlsx, onglet Tous_Candidats).
    """
    if on_progress:
        on_progress(0.60, "Construction des features de similarité...")

    df_candidats = df_exact[df_exact["statut_doublon"].isin(["Unique", "Original"])].copy()

    if len(df_candidats) < 2:
        df_candidats["cluster_dbscan"] = -1
        df_candidats["statut_cluster"] = "Isolé"
        df_candidats["taille_cluster"] = 1
        df_candidats["score_similarite"] = None
        return df_candidats

    extensions_dummies = pd.get_dummies(df_candidats["extension"], prefix="ext")
    taille_dummies = pd.get_dummies(df_candidats["categorie_taille_fichier"], prefix="taille")
    features_numeriques = df_candidats[["taille_octets", "profondeur_dossier", "age_fichier", "jours_depuis_modification"]].copy()

    df_features = pd.concat([features_numeriques, extensions_dummies, taille_dummies], axis=1).fillna(0)

    if on_progress:
        on_progress(0.66, "Normalisation des features...")

    scaler = StandardScaler()
    features_normalisees = scaler.fit_transform(df_features)

    if on_progress:
        on_progress(0.72, "Clustering DBSCAN en cours...")

    dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean", n_jobs=-1)
    labels = dbscan.fit_predict(features_normalisees)

    df_candidats["cluster_dbscan"] = labels
    df_candidats["statut_cluster"] = df_candidats["cluster_dbscan"].apply(
        lambda lbl: "Isolé" if lbl == -1 else f"Cluster #{lbl}"
    )

    taille_clusters = (
        df_candidats[df_candidats["cluster_dbscan"] != -1]
        .groupby("cluster_dbscan").size().reset_index(name="taille_cluster")
    )
    df_candidats = df_candidats.merge(taille_clusters, on="cluster_dbscan", how="left")
    df_candidats["taille_cluster"] = df_candidats["taille_cluster"].fillna(1).astype(int)

    if on_progress:
        on_progress(0.80, "Calcul des scores de similarité...")

    similarites = cosine_similarity(features_normalisees)
    scores = []
    for i, label in enumerate(labels):
        if label == -1:
            scores.append(None)
        else:
            voisins = [j for j, l in enumerate(labels) if l == label and j != i]
            scores.append(round(float(similarites[i, voisins].mean()), 4) if voisins else None)
    df_candidats["score_similarite"] = scores

    if on_progress:
        nb_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        on_progress(0.85, f"Quasi-doublons détectés — {nb_clusters} clusters")

    return df_candidats.reset_index(drop=True)


# =========================================================================
# ÉTAPE 5 — AGRÉGATION DES POINTS CHAUDS
# =========================================================================

def _extraire_segment(chemin, position, defaut="Inconnu"):
    segments = [s for s in str(chemin).split("/") if s != ""]
    if len(segments) > position:
        return segments[position]
    return defaut


def agreger_points_chauds(df_exact, df_quasi, on_progress=None):
    """
    Fusionne doublons exacts + quasi-doublons et agrège par dépôt / unité métier
    / extension / propriétaire. Retourne un dict de DataFrames (un par onglet).
    """
    if on_progress:
        on_progress(0.88, "Agrégation des points chauds...")

    df_exacts_flag = df_exact[df_exact["est_doublon_exact"]].copy()
    df_exacts_flag["type_duplication"] = "Exact"
    df_exacts_flag["id_groupe"] = "EXACT_" + df_exacts_flag["id_groupe_doublon"].astype(str)

    df_quasi_flag = df_quasi[df_quasi["cluster_dbscan"] != -1].copy()
    df_quasi_flag["type_duplication"] = "Quasi"
    df_quasi_flag["id_groupe"] = "QUASI_" + df_quasi_flag["cluster_dbscan"].astype(str)

    colonnes_communes = ["nom_fichier", "chemin", "chemin_dossier", "taille_octets", "extension", "type_duplication", "id_groupe"]
    df_combine = pd.concat(
        [df_exacts_flag.reindex(columns=colonnes_communes), df_quasi_flag.reindex(columns=colonnes_communes)],
        ignore_index=True,
    )

    if len(df_combine) == 0:
        vide = pd.DataFrame()
        return {
            "kpis": pd.DataFrame([{"indicateur": "Nombre total de fichiers dupliqués", "valeur": 0}]),
            "par_depot": vide, "par_unite": vide, "par_extension": vide,
            "par_proprietaire": vide, "top_hotspots": vide, "donnees_brutes": df_combine,
        }

    df_combine["depot"] = df_combine["chemin"].apply(lambda x: _extraire_segment(x, 0))
    df_combine["unite_metier"] = df_combine["chemin"].apply(lambda x: _extraire_segment(x, 1))
    df_combine["proprietaire"] = df_combine["chemin"].apply(lambda x: _extraire_segment(x, 2))

    def _agreger(df, colonne_groupe):
        agg = (
            df.groupby(colonne_groupe)
            .agg(
                nb_fichiers_dupliques=("chemin", "count"),
                nb_groupes_distincts=("id_groupe", "nunique"),
                espace_total_octets=("taille_octets", "sum"),
                nb_doublons_exacts=("type_duplication", lambda x: (x == "Exact").sum()),
                nb_quasi_doublons=("type_duplication", lambda x: (x == "Quasi").sum()),
            )
            .reset_index()
            .sort_values("espace_total_octets", ascending=False)
        )
        agg["espace_total_lisible"] = agg["espace_total_octets"].apply(lambda t: f"{round(t / (1024 * 1024), 2)} MB")
        return agg

    par_depot = _agreger(df_combine, "depot")
    par_unite = _agreger(df_combine, "unite_metier")
    par_extension = _agreger(df_combine, "extension")
    par_proprietaire = _agreger(df_combine, "proprietaire")

    top_hotspots = (
        df_combine.groupby(["depot", "unite_metier"])
        .agg(nb_fichiers_dupliques=("chemin", "count"), espace_total_octets=("taille_octets", "sum"))
        .reset_index().sort_values("espace_total_octets", ascending=False).head(20)
    )
    top_hotspots["espace_total_lisible"] = top_hotspots["espace_total_octets"].apply(lambda t: f"{round(t / (1024 * 1024), 2)} MB")
    top_hotspots["rang"] = range(1, len(top_hotspots) + 1)

    kpis = pd.DataFrame([
        {"indicateur": "Nombre total de fichiers dupliqués", "valeur": len(df_combine)},
        {"indicateur": "Nombre de groupes de duplication distincts", "valeur": df_combine["id_groupe"].nunique()},
        {"indicateur": "Doublons exacts", "valeur": int((df_combine["type_duplication"] == "Exact").sum())},
        {"indicateur": "Quasi-doublons", "valeur": int((df_combine["type_duplication"] == "Quasi").sum())},
        {"indicateur": "Espace total gaspillé (MB)", "valeur": round(df_combine["taille_octets"].sum() / (1024 * 1024), 2)},
        {"indicateur": "Nombre de dépôts impactés", "valeur": df_combine["depot"].nunique()},
        {"indicateur": "Nombre d'unités métier impactées", "valeur": df_combine["unite_metier"].nunique()},
    ])

    if on_progress:
        on_progress(1.0, "Pipeline terminé")

    return {
        "kpis": kpis, "par_depot": par_depot, "par_unite": par_unite,
        "par_extension": par_extension, "par_proprietaire": par_proprietaire,
        "top_hotspots": top_hotspots, "donnees_brutes": df_combine,
    }


# =========================================================================
# ORCHESTRATEUR — exécute les 5 étapes à la suite
# =========================================================================

def executer_pipeline_complet(dossier_cible, exclusions=None, eps=1.5, min_samples=2, on_progress=None):
    """
    Exécute le pipeline de bout en bout sur un dossier donné.
    Retourne un dict contenant tous les DataFrames intermédiaires et finaux,
    prêt à être sérialisé pour une session utilisateur.
    """
    df_brut = scanner_dossier(dossier_cible, exclusions=exclusions, on_progress=on_progress)
    df_clean = nettoyer_metadonnees(df_brut, on_progress=on_progress)
    df_exact = detecter_doublons_exacts(df_clean, on_progress=on_progress)
    df_quasi = detecter_quasi_doublons(df_exact, eps=eps, min_samples=min_samples, on_progress=on_progress)
    resultats_agreges = agreger_points_chauds(df_exact, df_quasi, on_progress=on_progress)

    return {
        "df_exact": df_exact,
        "df_quasi": df_quasi,
        **resultats_agreges,
    }