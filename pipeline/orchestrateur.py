"""
Orchestrateur du pipeline complet — exécute les 5 étapes en séquence pour UNE session
utilisateur donnée, et stocke les résultats intermédiaires sur disque dans un dossier
isolé propre à cette session (sessions/<session_id>/).

Chaque utilisateur ne voit jamais les fichiers ou résultats d'un autre utilisateur :
le session_id est généré côté client (uuid4) et stocké dans un dcc.Store(storage_type="session"),
donc il est unique par onglet de navigateur et expire à la fermeture.
"""

import os
import shutil
import tempfile
import zipfile
import pandas as pd

from pipeline.etape1_scan import scanner_dossier
from pipeline.etape2_nettoyage import nettoyer_metadonnees
from pipeline.etape3_doublons_exacts import detecter_doublons_exacts
from pipeline.etape4_quasi_doublons import detecter_quasi_doublons
from pipeline.etape5_hotspots import agreger_points_chauds

DOSSIER_SESSIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")
os.makedirs(DOSSIER_SESSIONS, exist_ok=True)


def dossier_session(session_id):
    """Retourne (et crée si besoin) le dossier de travail isolé d'une session."""
    chemin = os.path.join(DOSSIER_SESSIONS, session_id)
    os.makedirs(chemin, exist_ok=True)
    return chemin


def nettoyer_session(session_id):
    """Supprime tous les fichiers d'une session (appelé à la fermeture ou sur demande)."""
    chemin = os.path.join(DOSSIER_SESSIONS, session_id)
    if os.path.isdir(chemin):
        shutil.rmtree(chemin, ignore_errors=True)


def preparer_dossier_depuis_upload(session_id, fichiers_contenus, fichiers_noms):
    """
    Reconstitue un dossier sur disque à partir de fichiers uploadés via dcc.Upload
    (mode web déployé, sans accès au système de fichiers du serveur).

    fichiers_contenus : liste de chaînes base64 (format "data:<mime>;base64,<data>")
    fichiers_noms     : liste de noms de fichiers (peut inclure des sous-chemins si webkitdirectory)

    Retourne le chemin du dossier reconstitué, à passer ensuite à scanner_dossier().
    """
    import base64

    dossier_upload = os.path.join(dossier_session(session_id), "upload_brut")
    if os.path.isdir(dossier_upload):
        shutil.rmtree(dossier_upload)
    os.makedirs(dossier_upload, exist_ok=True)

    for contenu, nom in zip(fichiers_contenus, fichiers_noms):
        try:
            _, donnees_b64 = contenu.split(",", 1)
            donnees = base64.b64decode(donnees_b64)
        except Exception:
            continue

        # webkitdirectory renvoie des noms du type "MonDossier/sous/fichier.txt" — on préserve l'arborescence
        chemin_relatif = nom.replace("\\", "/")
        chemin_complet = os.path.join(dossier_upload, chemin_relatif)
        os.makedirs(os.path.dirname(chemin_complet), exist_ok=True)

        with open(chemin_complet, "wb") as f:
            f.write(donnees)

    return dossier_upload


def executer_pipeline_complet(session_id, dossier_cible, callback_progression=None, eps=1.5, min_samples=2):
    """
    Exécute les 5 étapes du pipeline pour une session donnée et persiste chaque résultat
    intermédiaire dans sessions/<session_id>/ pour pouvoir les recharger sans recalculer.

    Retourne un dictionnaire avec toutes les données nécessaires au dashboard.
    """

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    chemin_travail = dossier_session(session_id)

    # ── Étape 1 : scan ────────────────────────────────────────────────────
    df_brut = scanner_dossier(dossier_cible, callback_progression=callback_progression)
    df_brut.to_parquet(os.path.join(chemin_travail, "01_raw.parquet"), index=False)

    # ── Étape 2 : nettoyage ───────────────────────────────────────────────
    df_clean = nettoyer_metadonnees(df_brut, callback_progression=callback_progression)
    df_clean.to_parquet(os.path.join(chemin_travail, "02_cleaned.parquet"), index=False)

    # ── Étape 3 : doublons exacts ─────────────────────────────────────────
    df_exacts = detecter_doublons_exacts(df_clean, callback_progression=callback_progression)
    df_exacts.to_parquet(os.path.join(chemin_travail, "03_exact_duplicates.parquet"), index=False)

    # ── Étape 4 : quasi-doublons ──────────────────────────────────────────
    df_quasi = detecter_quasi_doublons(df_exacts, eps=eps, min_samples=min_samples, callback_progression=callback_progression)
    df_quasi.to_parquet(os.path.join(chemin_travail, "04_near_duplicates.parquet"), index=False)

    # ── Étape 5 : agrégation ──────────────────────────────────────────────
    resultats = agreger_points_chauds(df_exacts, df_quasi, callback_progression=callback_progression)
    resultats["combine"].to_parquet(os.path.join(chemin_travail, "05_combined.parquet"), index=False)
    resultats["hotspot"].to_parquet(os.path.join(chemin_travail, "05_hotspot.parquet"), index=False)
    pd.DataFrame([{"indicateur": k, "valeur": v} for k, v in resultats["kpis"].items()]).to_parquet(
        os.path.join(chemin_travail, "05_kpis.parquet"), index=False
    )

    notifier(100, "Pipeline terminé.")

    return {
        "brut": df_brut,
        "clean": df_clean,
        "exacts": df_exacts,
        "quasi": df_quasi,
        "combine": resultats["combine"],
        "hotspot": resultats["hotspot"],
        "kpis": resultats["kpis"],
    }


def charger_resultats_session(session_id):
    """Recharge les résultats déjà calculés d'une session depuis le disque (sans relancer le pipeline)."""
    chemin_travail = dossier_session(session_id)

    def lire(nom_fichier):
        chemin = os.path.join(chemin_travail, nom_fichier)
        return pd.read_parquet(chemin) if os.path.isfile(chemin) else pd.DataFrame()

    df_kpis = lire("05_kpis.parquet")
    kpis = dict(zip(df_kpis["indicateur"], df_kpis["valeur"])) if len(df_kpis) else {}

    return {
        "exacts": lire("03_exact_duplicates.parquet"),
        "quasi": lire("04_near_duplicates.parquet"),
        "combine": lire("05_combined.parquet"),
        "hotspot": lire("05_hotspot.parquet"),
        "kpis": kpis,
    }


def session_a_des_resultats(session_id):
    """Vérifie rapidement si une session a déjà un pipeline terminé sans tout recharger."""
    return os.path.isfile(os.path.join(dossier_session(session_id), "05_kpis.parquet"))