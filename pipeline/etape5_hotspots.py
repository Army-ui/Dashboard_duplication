"""
Étape 5 — Agrégation des points chauds de duplication par dépôt, unité métier, extension.
"""

import pandas as pd


def extraire_segment(chemin, position, defaut="Inconnu"):
    segments = [s for s in chemin.split("/") if s != ""]
    return segments[position] if len(segments) > position else defaut


def agreger_points_chauds(df_exacts, df_quasi, callback_progression=None):
    """Fusionne doublons exacts + quasi-doublons et produit les agrégations + KPIs."""

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    notifier(78, "Fusion des deux sources de duplication...")

    if len(df_exacts) and "est_doublon_exact" in df_exacts.columns:
        df_exacts_flag = df_exacts[df_exacts["est_doublon_exact"] == True].copy()
    else:
        df_exacts_flag = pd.DataFrame()
    if len(df_exacts_flag):
        df_exacts_flag["type_duplication"] = "Exact"
        df_exacts_flag["id_groupe"] = "EXACT_" + df_exacts_flag["id_groupe_doublon"].astype(str)

    if len(df_quasi) and "cluster_dbscan" in df_quasi.columns:
        df_quasi_flag = df_quasi[df_quasi["cluster_dbscan"] != -1].copy()
    else:
        df_quasi_flag = pd.DataFrame()
    if len(df_quasi_flag):
        df_quasi_flag["type_duplication"] = "Quasi"
        df_quasi_flag["id_groupe"] = "QUASI_" + df_quasi_flag["cluster_dbscan"].astype(str)

    colonnes_communes = ["nom_fichier", "chemin", "chemin_dossier", "taille_octets", "extension", "type_duplication", "id_groupe"]

    morceaux = []
    if len(df_exacts_flag):
        morceaux.append(df_exacts_flag[colonnes_communes])
    if len(df_quasi_flag):
        morceaux.append(df_quasi_flag[colonnes_communes])

    if not morceaux:
        notifier(95, "Aucun doublon détecté — rien à agréger.")
        return {"combine": pd.DataFrame(), "kpis": {}, "hotspot": pd.DataFrame()}

    df_combine = pd.concat(morceaux, ignore_index=True)

    notifier(85, "Extraction dépôt / unité métier / propriétaire...")

    df_combine["depot"] = df_combine["chemin"].apply(lambda x: extraire_segment(x, 0))
    df_combine["unite_metier"] = df_combine["chemin"].apply(lambda x: extraire_segment(x, 1))
    df_combine["proprietaire"] = df_combine["chemin"].apply(lambda x: extraire_segment(x, 2))

    notifier(90, "Agrégation par dépôt et unité métier...")

    agg_hotspot = (
        df_combine.groupby(["depot", "unite_metier"])
        .agg(nb_fichiers_dupliques=("chemin", "count"), espace_total_octets=("taille_octets", "sum"))
        .reset_index()
        .sort_values("espace_total_octets", ascending=False)
        .head(20)
    )
    agg_hotspot["espace_total_lisible"] = agg_hotspot["espace_total_octets"].apply(lambda t: f"{round(t / (1024*1024), 2)} MB")
    agg_hotspot["rang"] = range(1, len(agg_hotspot) + 1)

    kpis = {
        "Nombre total de fichiers dupliqués": len(df_combine),
        "Nombre de groupes de duplication distincts": df_combine["id_groupe"].nunique(),
        "Doublons exacts": int((df_combine["type_duplication"] == "Exact").sum()),
        "Quasi-doublons": int((df_combine["type_duplication"] == "Quasi").sum()),
        "Espace total gaspillé (MB)": round(df_combine["taille_octets"].sum() / (1024 * 1024), 2),
        "Nombre de dépôts impactés": df_combine["depot"].nunique(),
        "Nombre d'unités métier impactées": df_combine["unite_metier"].nunique(),
    }

    notifier(95, f"Agrégation terminée : {len(df_combine)} fichiers dupliqués au total.")
    return {"combine": df_combine, "kpis": kpis, "hotspot": agg_hotspot}