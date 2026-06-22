"""
Génération de PDF téléchargeables pour les listes de doublons (exacts et quasi-doublons),
en tenant compte des filtres actifs côté utilisateur.
"""

import io
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

COULEUR_ENTETE = colors.HexColor("#8A6A1F")
COULEUR_LIGNE_ALT = colors.HexColor("#F6F1E6")
COULEUR_TEXTE = colors.HexColor("#21201B")


def _styles():
    feuille = getSampleStyleSheet()
    feuille.add(ParagraphStyle(
        name="TitrePrincipal", fontSize=16, leading=20, textColor=COULEUR_ENTETE,
        fontName="Helvetica-Bold", spaceAfter=4,
    ))
    feuille.add(ParagraphStyle(
        name="SousTitre", fontSize=9.5, leading=12, textColor=colors.HexColor("#6B6354"),
        fontName="Helvetica", spaceAfter=14,
    ))
    return feuille


def _construire_tableau(lignes_entete, lignes_donnees, largeurs_colonnes):
    data = [lignes_entete] + lignes_donnees
    tableau = Table(data, colWidths=largeurs_colonnes, repeatRows=1)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ENTETE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), COULEUR_TEXTE),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E8E1CF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), COULEUR_LIGNE_ALT))
    tableau.setStyle(TableStyle(style))
    return tableau


def generer_pdf_doublons_exacts(df_exacts, langue="fr", filtres_actifs=None):
    """
    Génère un PDF listant les doublons exacts (Original + Doublon #N), en respectant
    les filtres déjà appliqués par l'utilisateur dans le dashboard.

    Retourne les bytes du PDF (prêts pour dcc.Download).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    feuille = _styles()
    elements = []

    titre = "Liste des doublons exacts" if langue == "fr" else "Exact duplicates list"
    sous_titre_filtre = _decrire_filtres(filtres_actifs, langue)
    horodatage = datetime.now().strftime("%d/%m/%Y %H:%M")

    elements.append(Paragraph(titre, feuille["TitrePrincipal"]))
    elements.append(Paragraph(f"{sous_titre_filtre} — généré le {horodatage}", feuille["SousTitre"]))

    df_aff = df_exacts[df_exacts["est_doublon_exact"] == True].copy() if len(df_exacts) else df_exacts
    df_aff = df_aff.sort_values(["id_groupe_doublon", "rang_dans_groupe"]) if len(df_aff) else df_aff

    if len(df_aff) == 0:
        msg = "Aucun doublon exact trouvé pour cette sélection." if langue == "fr" else "No exact duplicates found for this selection."
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(msg, feuille["Normal"]))
    else:
        entetes = ["Statut", "Nom du fichier", "Chemin", "Taille", "Date création"] if langue == "fr" \
            else ["Status", "File name", "Path", "Size", "Creation date"]

        lignes = []
        for _, ligne in df_aff.iterrows():
            lignes.append([
                str(ligne.get("statut_doublon", "")),
                str(ligne.get("nom_fichier", ""))[:40],
                str(ligne.get("chemin", ""))[:70],
                str(ligne.get("taille_lisible", "")),
                str(ligne.get("date_creation", ""))[:10],
            ])

        largeurs = [28 * mm, 42 * mm, 110 * mm, 22 * mm, 26 * mm]
        elements.append(_construire_tableau(entetes, lignes, largeurs))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generer_pdf_quasi_doublons(df_quasi, langue="fr", filtres_actifs=None):
    """Génère un PDF listant les quasi-doublons (clusters DBSCAN), filtré selon la sélection active."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    feuille = _styles()
    elements = []

    titre = "Liste des quasi-doublons" if langue == "fr" else "Near-duplicates list"
    sous_titre_filtre = _decrire_filtres(filtres_actifs, langue)
    horodatage = datetime.now().strftime("%d/%m/%Y %H:%M")

    elements.append(Paragraph(titre, feuille["TitrePrincipal"]))
    elements.append(Paragraph(f"{sous_titre_filtre} — généré le {horodatage}", feuille["SousTitre"]))

    if len(df_quasi) and "cluster_dbscan" in df_quasi.columns:
        df_aff = df_quasi[df_quasi["cluster_dbscan"] != -1].copy()
        df_aff = df_aff.sort_values(["cluster_dbscan"])
    else:
        df_aff = pd.DataFrame()

    if len(df_aff) == 0:
        msg = "Aucun quasi-doublon trouvé pour cette sélection." if langue == "fr" else "No near-duplicates found for this selection."
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(msg, feuille["Normal"]))
    else:
        entetes = ["Cluster", "Nom du fichier", "Chemin", "Taille", "Score similarité"] if langue == "fr" \
            else ["Cluster", "File name", "Path", "Size", "Similarity score"]

        lignes = []
        for _, ligne in df_aff.iterrows():
            score = ligne.get("score_similarite")
            score_str = f"{score:.3f}" if pd.notna(score) else "—"
            lignes.append([
                str(ligne.get("statut_cluster", "")),
                str(ligne.get("nom_fichier", ""))[:40],
                str(ligne.get("chemin", ""))[:70],
                str(ligne.get("taille_lisible", "")),
                score_str,
            ])

        largeurs = [26 * mm, 42 * mm, 110 * mm, 22 * mm, 28 * mm]
        elements.append(_construire_tableau(entetes, lignes, largeurs))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _decrire_filtres(filtres_actifs, langue):
    """Construit une phrase descriptive des filtres actifs pour le sous-titre du PDF."""
    if not filtres_actifs:
        return "Toutes les données" if langue == "fr" else "All data"

    parties = []
    depot = filtres_actifs.get("depot")
    unite = filtres_actifs.get("unite")
    type_dup = filtres_actifs.get("type_dup")

    if depot:
        parties.append(f"Dépôt: {depot}" if langue == "fr" else f"Repository: {depot}")
    if unite:
        parties.append(f"Unité: {unite}" if langue == "fr" else f"Unit: {unite}")
    if type_dup and type_dup != "Tous":
        parties.append(f"Type: {type_dup}")

    if not parties:
        return "Toutes les données" if langue == "fr" else "All data"
    return " · ".join(parties)