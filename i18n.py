"""
Dictionnaire de traductions FR / EN.
Toutes les chaînes affichées dans l'interface passent par t(cle, langue).
"""

TRADUCTIONS = {
    "brand_title": {"fr": "Détection de doublons", "en": "Duplicate Detection"},
    "brand_subtitle": {"fr": "Gouvernance des données — Tableau de bord", "en": "Data Governance — Dashboard"},
    "live": {"fr": "Données à jour", "en": "Data up to date"},

    # ── Saisie du dossier à scanner ──────────────────────────────────────
    "scan_section_title": {"fr": "Lancer une nouvelle analyse", "en": "Start a new scan"},
    "scan_section_subtitle": {
        "fr": "Choisissez un chemin sur ce serveur ou déposez vos fichiers directement",
        "en": "Pick a path on this server or drop your files directly",
    },
    "scan_mode_path": {"fr": "Chemin serveur", "en": "Server path"},
    "scan_mode_upload": {"fr": "Déposer des fichiers", "en": "Upload files"},
    "scan_path_label": {"fr": "Dossier à scanner", "en": "Folder to scan"},
    "scan_path_placeholder": {"fr": "ex: C:/Utilisateurs/moi/Documents", "en": "e.g. C:/Users/me/Documents"},
    "scan_path_hint": {
        "fr": "Le dossier doit exister sur la machine qui exécute l'application.",
        "en": "The folder must exist on the machine running the application.",
    },
    "scan_upload_text": {"fr": "Glissez un dossier ici ou cliquez pour sélectionner", "en": "Drag a folder here or click to select"},
    "scan_upload_hint": {
        "fr": "Tout reste privé : vos fichiers ne sont visibles que par vous pendant cette session.",
        "en": "Everything stays private: your files are only visible to you during this session.",
    },
    "scan_btn_launch": {"fr": "Lancer l'analyse", "en": "Start scan"},
    "scan_btn_relaunch": {"fr": "Relancer une analyse", "en": "Run a new scan"},
    "scan_btn_cancel": {"fr": "Annuler", "en": "Cancel"},
    "scan_advanced_toggle": {"fr": "Paramètres avancés", "en": "Advanced settings"},
    "scan_eps_label": {"fr": "Sensibilité du clustering (eps)", "en": "Clustering sensitivity (eps)"},
    "scan_minsamples_label": {"fr": "Taille minimale d'un cluster", "en": "Minimum cluster size"},
    "scan_empty_state_title": {"fr": "Aucune analyse pour le moment", "en": "No scan yet"},
    "scan_empty_state_text": {
        "fr": "Indiquez un dossier ou déposez vos fichiers ci-dessus pour démarrer.",
        "en": "Point to a folder or drop your files above to get started.",
    },
    "scan_error_no_path": {"fr": "Merci d'indiquer un dossier valide.", "en": "Please provide a valid folder."},
    "scan_error_no_upload": {"fr": "Merci de déposer au moins un fichier.", "en": "Please drop at least one file."},
    "scan_error_path_not_found": {"fr": "Ce dossier n'existe pas sur le serveur.", "en": "This folder does not exist on the server."},

    # ── Progression ──────────────────────────────────────────────────────
    "progress_title": {"fr": "Analyse en cours...", "en": "Scan in progress..."},
    "progress_step_scan": {"fr": "Scan des fichiers", "en": "Scanning files"},
    "progress_step_clean": {"fr": "Nettoyage", "en": "Cleaning"},
    "progress_step_exact": {"fr": "Doublons exacts", "en": "Exact duplicates"},
    "progress_step_quasi": {"fr": "Quasi-doublons", "en": "Near-duplicates"},
    "progress_step_hotspot": {"fr": "Agrégation", "en": "Aggregation"},

    "kpi_total_files": {"fr": "Fichiers dupliqués", "en": "Duplicated files"},
    "kpi_groups": {"fr": "Groupes distincts", "en": "Distinct groups"},
    "kpi_space": {"fr": "Espace gaspillé", "en": "Wasted space"},
    "kpi_depots": {"fr": "Dépôts impactés", "en": "Impacted repositories"},
    "kpi_unites": {"fr": "Unités métier", "en": "Business units"},

    "filter_depot": {"fr": "Dépôt", "en": "Repository"},
    "filter_depot_all": {"fr": "Tous les dépôts", "en": "All repositories"},
    "filter_unite": {"fr": "Unité métier", "en": "Business unit"},
    "filter_unite_all": {"fr": "Toutes les unités", "en": "All business units"},
    "filter_type": {"fr": "Type de duplication", "en": "Duplication type"},
    "filter_type_all": {"fr": "Tous", "en": "All"},
    "filter_type_exact": {"fr": "Doublons exacts", "en": "Exact duplicates"},
    "filter_type_quasi": {"fr": "Quasi-doublons", "en": "Near-duplicates"},

    "chart_unite_title": {"fr": "Espace gaspillé par unité métier", "en": "Wasted space by business unit"},
    "chart_unite_subtitle": {"fr": "Triées par impact décroissant", "en": "Sorted by decreasing impact"},
    "chart_depot_title": {"fr": "Répartition par dépôt", "en": "Breakdown by repository"},
    "chart_depot_subtitle": {"fr": "Taille = espace gaspillé", "en": "Size = wasted space"},
    "chart_extension_title": {"fr": "Top extensions dupliquées", "en": "Top duplicated extensions"},
    "chart_extension_subtitle": {"fr": "Nombre de fichiers concernés", "en": "Number of affected files"},
    "chart_type_title": {"fr": "Exact vs quasi-doublons", "en": "Exact vs near-duplicates"},
    "chart_type_subtitle": {"fr": "Répartition globale par type", "en": "Overall breakdown by type"},

    "table_title": {"fr": "Top 20 points chauds", "en": "Top 20 hotspots"},
    "table_subtitle": {
        "fr": "Combinaison dépôt + unité métier les plus critiques",
        "en": "Most critical repository + business unit combinations",
    },
    "table_col_rank": {"fr": "Rang", "en": "Rank"},
    "table_col_depot": {"fr": "Dépôt", "en": "Repository"},
    "table_col_unite": {"fr": "Unité métier", "en": "Business unit"},
    "table_col_files": {"fr": "Fichiers dupliqués", "en": "Duplicated files"},
    "table_col_space": {"fr": "Espace gaspillé", "en": "Wasted space"},

    "axis_space_mb": {"fr": "Espace gaspillé (MB)", "en": "Wasted space (MB)"},
    "axis_nb_files": {"fr": "Nombre de fichiers", "en": "Number of files"},
    "legend_exact": {"fr": "Exact", "en": "Exact"},
    "legend_quasi": {"fr": "Quasi", "en": "Near"},

    # ── Fenêtres listes de doublons ──────────────────────────────────────
    "panel_exact_title": {"fr": "Liste des doublons exacts", "en": "Exact duplicates list"},
    "panel_exact_subtitle": {"fr": "Filtrée selon votre sélection ci-dessus", "en": "Filtered by your selection above"},
    "panel_quasi_title": {"fr": "Liste des quasi-doublons", "en": "Near-duplicates list"},
    "panel_quasi_subtitle": {"fr": "Groupés par cluster de similarité", "en": "Grouped by similarity cluster"},
    "panel_search_placeholder": {"fr": "Rechercher un fichier ou un chemin...", "en": "Search a file or path..."},
    "panel_col_status": {"fr": "Statut", "en": "Status"},
    "panel_col_name": {"fr": "Fichier", "en": "File"},
    "panel_col_path": {"fr": "Chemin", "en": "Path"},
    "panel_col_size": {"fr": "Taille", "en": "Size"},
    "panel_col_date": {"fr": "Date création", "en": "Creation date"},
    "panel_col_cluster": {"fr": "Cluster", "en": "Cluster"},
    "panel_col_score": {"fr": "Similarité", "en": "Similarity"},
    "panel_export_pdf": {"fr": "Exporter en PDF", "en": "Export to PDF"},
    "panel_empty": {"fr": "Aucun résultat pour cette sélection.", "en": "No results for this selection."},
    "panel_count_suffix": {"fr": "fichiers", "en": "files"},

    "footer_text": {
        "fr": "Pipeline de déduplication — vos données restent privées à votre session",
        "en": "Deduplication pipeline — your data stays private to your session",
    },
}


def t(cle, langue):
    """Retourne la traduction d'une clé pour la langue donnée, avec repli sur le français."""
    entree = TRADUCTIONS.get(cle, {})
    return entree.get(langue, entree.get("fr", cle))