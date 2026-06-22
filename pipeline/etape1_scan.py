"""
Étape 1 — Scan récursif du dossier cible + calcul des métadonnées et hash MD5.
Refactorisé en fonction réutilisable (au lieu d'un script autonome) pour être appelé
depuis le dashboard avec un dossier et un callback de progression en paramètres.
"""

import os
import hashlib
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

EXCLUSIONS_DEFAUT = ["AppData", "Program Files", "Windows", ".git", "__pycache__", "node_modules", ".venv"]


def calculer_md5(chemin):
    """Calcule le hash MD5 d'un fichier par lecture en blocs de 4096 octets."""
    try:
        hash_md5 = hashlib.md5()
        with open(chemin, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def traiter_fichier(chemin_complet):
    """Extrait les métadonnées d'un fichier (nom, taille, dates, hash)."""
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


def scanner_dossier(
    dossier_cible,
    nb_threads=4,
    exclusions=None,
    callback_progression=None,
):
    """
    Scanne récursivement dossier_cible et retourne un DataFrame de métadonnées brutes.

    callback_progression(pourcentage: float, message: str) — appelé régulièrement
    pour permettre au dashboard d'afficher une barre de progression en temps réel.
    """
    exclusions = exclusions or EXCLUSIONS_DEFAUT

    def notifier(pct, msg):
        if callback_progression:
            callback_progression(pct, msg)

    notifier(2, f"Recherche des fichiers dans {dossier_cible}...")

    liste_fichiers = []
    for dossier, sous_dossiers, fichiers in os.walk(dossier_cible):
        sous_dossiers[:] = [d for d in sous_dossiers if not any(ex in d for ex in exclusions)]
        for fichier in fichiers:
            liste_fichiers.append(os.path.join(dossier, fichier))

    total = len(liste_fichiers)
    if total == 0:
        notifier(15, "Aucun fichier trouvé dans ce dossier.")
        return pd.DataFrame(columns=[
            "nom_fichier", "chemin", "taille_octets", "extension",
            "hash_md5", "date_creation", "date_modification",
        ])

    notifier(5, f"{total} fichiers détectés — calcul des empreintes...")

    donnees = []
    with ThreadPoolExecutor(max_workers=nb_threads) as executor:
        futures = {executor.submit(traiter_fichier, f): f for f in liste_fichiers}
        termines = 0
        for future in as_completed(futures):
            termines += 1
            try:
                resultat = future.result()
                if resultat:
                    donnees.append(resultat)
            except Exception:
                pass

            if termines % max(1, total // 50) == 0 or termines == total:
                # Étape 1 occupe la tranche 0-15% de la barre de progression globale
                pct = 5 + (termines / total) * 10
                notifier(pct, f"{termines}/{total} fichiers traités...")

    notifier(15, f"Scan terminé : {len(donnees)} fichiers indexés.")
    return pd.DataFrame(donnees)