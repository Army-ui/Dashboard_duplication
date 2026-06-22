"""
Étape 2 — Nettoyage des métadonnées brutes + ingénierie des caractéristiques.
"""

import re
import pandas as pd
from datetime import datetime


def categoriser_taille(taille):
    if taille < 1_000_000:
        return "Petit"
    elif taille < 100_000_000:
        return "Moyen"
    else:
        return "Grand"


def supprimer_extension(nom):
    if "." in nom:
        return ".".join(nom.split(".")[:-1])
    return nom


def nettoyer_metadonnees(df_brut, callback_progression=None):
    """
    Prend le DataFrame brut produit par l'étape 1 et retourne le DataFrame nettoyé
    avec les colonnes dérivées (profondeur, âge, catégorie de taille...).
    """

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    notifier(17, "Suppression des lignes invalides...")

    df = df_brut.dropna(subset=["nom_fichier", "chemin", "taille_octets", "hash_md5", "date_creation", "date_modification"])
    df = df.dropna(subset=["extension"])
    df = df[df["extension"].astype(str).str.strip() != ""]

    if len(df) == 0:
        notifier(30, "Aucune donnée valide après nettoyage.")
        return pd.DataFrame()

    df["nom_fichier"] = df["nom_fichier"].str.lower().str.strip()
    df["extension"] = df["extension"].str.lower().str.strip()
    df["chemin"] = df["chemin"].str.replace("\\\\", "/", regex=True).str.replace("\\", "/", regex=False)

    notifier(20, "Validation des dates...")

    df["date_creation"] = pd.to_datetime(df["date_creation"], errors="coerce")
    df["date_modification"] = pd.to_datetime(df["date_modification"], errors="coerce")
    df = df.dropna(subset=["date_creation", "date_modification"])
    df = df[df["date_creation"] <= df["date_modification"]]

    df = df.drop_duplicates(subset=["chemin"])

    notifier(23, "Normalisation des noms de fichiers...")

    df["nom_sans_extension"] = df["nom_fichier"].apply(supprimer_extension)
    df["nom_fichier"] = df["nom_sans_extension"].apply(lambda x: re.sub(r"[^a-zA-Z0-9]", "", str(x)))
    df = df[df["nom_fichier"] != ""]

    notifier(26, "Feature engineering...")

    df["chemin_dossier"] = df["chemin"].apply(lambda x: "/".join(x.split("/")[:-1]))
    df["profondeur_dossier"] = df["chemin_dossier"].apply(lambda x: len([p for p in x.split("/") if p != ""]))
    df["categorie_taille_fichier"] = df["taille_octets"].apply(categoriser_taille)

    aujourdhui = pd.Timestamp(datetime.now())
    df["age_fichier"] = (aujourdhui - df["date_creation"]).dt.days
    df["jours_depuis_modification"] = (aujourdhui - df["date_modification"]).dt.days
    df["taille_lisible"] = df["taille_octets"].apply(lambda t: f"{round(t / (1024 * 1024), 2)} MB")

    colonnes_finales = [
        "nom_fichier", "chemin", "chemin_dossier", "profondeur_dossier",
        "taille_octets", "taille_lisible", "categorie_taille_fichier", "extension",
        "hash_md5", "date_creation", "date_modification", "age_fichier", "jours_depuis_modification",
    ]
    df_final = df[colonnes_finales].copy()

    notifier(30, f"Nettoyage terminé : {len(df_final)} fichiers valides.")
    return df_final