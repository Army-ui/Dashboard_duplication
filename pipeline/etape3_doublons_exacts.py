"""
Étape 3 — Détection des doublons exacts (même hash_md5 + même taille_octets).
"""

import pandas as pd


def detecter_doublons_exacts(df_cleaned, callback_progression=None):
    """Retourne le DataFrame enrichi avec les colonnes de détection des doublons exacts."""

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    if len(df_cleaned) == 0:
        notifier(45, "Aucune donnée à analyser.")
        return pd.DataFrame()

    notifier(33, "Comptage des occurrences par empreinte...")

    df = df_cleaned.copy()
    cles_doublons = ["hash_md5", "taille_octets"]

    comptage = df.groupby(cles_doublons).size().reset_index(name="nb_occurrences")
    df = df.merge(comptage, on=cles_doublons, how="left")
    df["est_doublon_exact"] = df["nb_occurrences"] > 1

    notifier(38, "Classement des originaux et copies...")

    df["rang_dans_groupe"] = (
        df.sort_values("date_creation").groupby(cles_doublons).cumcount() + 1
    )

    groupes = df[df["est_doublon_exact"]].groupby(cles_doublons).ngroup()
    df.loc[df["est_doublon_exact"], "id_groupe_doublon"] = groupes.values
    df["id_groupe_doublon"] = df["id_groupe_doublon"].fillna(-1).astype(int)

    def statut_doublon(row):
        if not row["est_doublon_exact"]:
            return "Unique"
        elif row["rang_dans_groupe"] == 1:
            return "Original"
        else:
            return f"Doublon #{row['rang_dans_groupe'] - 1}"

    df["statut_doublon"] = df.apply(statut_doublon, axis=1)

    notifier(45, f"Doublons exacts détectés : {df['est_doublon_exact'].sum()} fichiers concernés.")
    return df