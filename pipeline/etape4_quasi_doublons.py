"""
Étape 4 — Détection des quasi-doublons par feature engineering de similarité + DBSCAN.
"""

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity


def detecter_quasi_doublons(df_exacts, eps=1.5, min_samples=2, callback_progression=None):
    """Retourne le DataFrame des candidats (Unique + Original) enrichi des clusters DBSCAN."""

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    if len(df_exacts) == 0:
        notifier(75, "Aucune donnée à clusteriser.")
        return pd.DataFrame()

    notifier(48, "Sélection des candidats au clustering...")

    df_candidats = df_exacts[df_exacts["statut_doublon"].isin(["Unique", "Original"])].copy()

    if len(df_candidats) < 2:
        notifier(75, "Pas assez de candidats pour le clustering.")
        df_candidats["cluster_dbscan"] = -1
        df_candidats["statut_cluster"] = "Isolé"
        df_candidats["taille_cluster"] = 1
        df_candidats["score_similarite"] = None
        return df_candidats

    notifier(52, "Construction des features de similarité...")

    extensions_dummies = pd.get_dummies(df_candidats["extension"], prefix="ext")
    taille_dummies = pd.get_dummies(df_candidats["categorie_taille_fichier"], prefix="taille")
    features_numeriques = df_candidats[["taille_octets", "profondeur_dossier", "age_fichier", "jours_depuis_modification"]].copy()

    df_features = pd.concat([features_numeriques, extensions_dummies, taille_dummies], axis=1).fillna(0)

    notifier(58, "Normalisation des features...")
    scaler = StandardScaler()
    features_normalisees = scaler.fit_transform(df_features)

    notifier(64, "Clustering DBSCAN en cours...")
    dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean", n_jobs=-1)
    labels = dbscan.fit_predict(features_normalisees)
    df_candidats["cluster_dbscan"] = labels

    notifier(70, "Calcul des scores de similarité...")

    def statut_cluster(label):
        return "Isolé" if label == -1 else f"Cluster #{label}"

    df_candidats["statut_cluster"] = df_candidats["cluster_dbscan"].apply(statut_cluster)

    taille_clusters = (
        df_candidats[df_candidats["cluster_dbscan"] != -1]
        .groupby("cluster_dbscan").size().reset_index(name="taille_cluster")
    )
    df_candidats = df_candidats.merge(taille_clusters, on="cluster_dbscan", how="left")
    df_candidats["taille_cluster"] = df_candidats["taille_cluster"].fillna(1).astype(int)

    # Limite la similarité cosinus à un échantillon raisonnable pour rester rapide sur les gros volumes
    if len(features_normalisees) <= 5000:
        similarites = cosine_similarity(features_normalisees)
        scores = []
        for i, label in enumerate(labels):
            if label == -1:
                scores.append(None)
            else:
                indices = [j for j, l in enumerate(labels) if l == label and j != i]
                scores.append(round(float(similarites[i, indices].mean()), 4) if indices else None)
        df_candidats["score_similarite"] = scores
    else:
        df_candidats["score_similarite"] = None  # Évite un calcul O(n²) trop coûteux sur de très gros volumes

    notifier(75, f"Quasi-doublons détectés : {(df_candidats['cluster_dbscan'] != -1).sum()} fichiers en cluster.")
    return df_candidats