import os
import uuid
import pandas as pd
import plotly.express as px

from dash import (
    Dash, dcc, html, Input, Output, State, ctx,
    clientside_callback, DiskcacheManager, no_update,
)

from i18n import t
from pipeline.orchestrateur import (
    executer_pipeline_complet,
    preparer_dossier_depuis_upload,
    charger_resultats_session,
    session_a_des_resultats,
)
from pipeline.export_pdf import generer_pdf_doublons_exacts, generer_pdf_quasi_doublons

# =========================
# 1. BACKGROUND CALLBACK MANAGER
#    Diskcache = zéro infra à installer (pas besoin de Redis/Celery) pour exécuter
#    le pipeline en tâche de fond sans bloquer l'interface, avec barre de progression.
# =========================

import diskcache
CHEMIN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions", "_diskcache")
os.makedirs(CHEMIN_CACHE, exist_ok=True)
cache = diskcache.Cache(CHEMIN_CACHE)
background_callback_manager = DiskcacheManager(cache)

# =========================
# 2. PALETTE — blanc / doré, cohérente clair & sombre
# =========================

PALETTE = {
    "light": {
        "bg_card": "#FFFFFF", "text_primary": "#21201B", "text_secondary": "#6B6354",
        "grid": "#EDE7D6", "navy": "#8A6A1F", "steel": "#B08A2E", "coral": "#B0552C", "teal": "#156A56",
    },
    "dark": {
        "bg_card": "#1C1A12", "text_primary": "#F3EEDF", "text_secondary": "#B6AD93",
        "grid": "#332C18", "navy": "#D4AF52", "steel": "#D4AF52", "coral": "#DD8A5C", "teal": "#4FC2A0",
    },
}

# =========================
# 3. APP
# =========================

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    background_callback_manager=background_callback_manager,
    assets_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
)
app.title = "Duplicate Detection Dashboard"

app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""

# =========================
# 4. ICÔNES SVG INLINE
# =========================

ICONE_SOLEIL = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>
</svg>"""

ICONE_LUNE = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
</svg>"""

ICONE_MARQUE = """<svg viewBox="0 0 24 24" fill="none" stroke="#8A6A1F" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>
<rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M17.5 14v7M14 17.5h7"/>
</svg>"""

ICONE_DOSSIER = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>
</svg>"""

ICONE_UPLOAD = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 16V4M12 4l-4 4M12 4l4 4"/><path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3"/>
</svg>"""

ICONE_PDF = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/>
</svg>"""

ICONE_RECHERCHE = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
</svg>"""


def svg_inline(svg_str):
    return dcc.Markdown(svg_str, dangerously_allow_html=True)


# =========================
# 5. COMPOSANTS RÉUTILISABLES
# =========================

def carte_kpi(kpi_id, valeur, suffixe, couleur_var):
    return html.Div(
        [
            html.Div("", className="kpi-label", id={"type": "kpi-label", "index": kpi_id}),
            html.Div(
                [
                    html.Span(valeur, className="kpi-value", id={"type": "kpi-value", "index": kpi_id}),
                    html.Span(suffixe, className="kpi-unit") if suffixe else None,
                ],
                className="kpi-value-row",
            ),
        ],
        className="kpi-card",
        style={"--kpi-accent": couleur_var},
    )


def en_tete_section(titre_id, sous_titre_id):
    return html.Div([
        html.Div("", className="section-title", id=titre_id),
        html.Div("", className="section-subtitle", id=sous_titre_id),
    ])


def panneau_liste_doublons(prefixe):
    """
    Fenêtre réutilisable pour afficher une liste de doublons filtrable + recherche + export PDF.
    prefixe = "exact" ou "quasi", utilisé pour préfixer tous les ids des composants enfants.
    """
    return html.Div(
        className="list-panel-card",
        children=[
            html.Div(
                className="list-panel-header",
                children=[
                    en_tete_section(f"titre-panel-{prefixe}", f"sous-titre-panel-{prefixe}"),
                    html.Div(
                        className="list-panel-actions",
                        children=[
                            html.Span(id=f"compteur-panel-{prefixe}", className="list-panel-count"),
                            html.Button(
                                [svg_inline(ICONE_PDF), html.Span(id=f"txt-export-{prefixe}")],
                                id=f"btn-export-{prefixe}",
                                className="btn-export-pdf",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="list-panel-search",
                children=[
                    svg_inline(ICONE_RECHERCHE),
                    dcc.Input(id=f"recherche-{prefixe}", type="text", className="list-search-input", debounce=True),
                ],
            ),
            html.Div(id=f"contenu-panel-{prefixe}", className="list-panel-body"),
            dcc.Download(id=f"download-pdf-{prefixe}"),
        ],
    )


# =========================
# 6. FORMULAIRE DE LANCEMENT D'ANALYSE
# =========================

formulaire_scan = html.Div(
    className="scan-card",
    children=[
        en_tete_section("titre-scan", "sous-titre-scan"),

        html.Div(
            className="control-pill scan-mode-pill",
            children=[
                html.Button([svg_inline(ICONE_DOSSIER), html.Span(id="txt-mode-path")], id="btn-mode-path", className="control-pill-btn is-active"),
                html.Button([svg_inline(ICONE_UPLOAD), html.Span(id="txt-mode-upload")], id="btn-mode-upload", className="control-pill-btn"),
            ],
        ),

        # ── Mode chemin serveur ──────────────────────────────────────────
        html.Div(
            id="bloc-mode-path",
            children=[
                html.Label(id="lbl-scan-path", className="filter-label"),
                dcc.Input(id="input-scan-path", type="text", className="scan-path-input"),
                html.Div(id="txt-scan-path-hint", className="scan-hint"),
            ],
        ),

        # ── Mode upload (caché par défaut) ───────────────────────────────
        html.Div(
            id="bloc-mode-upload",
            style={"display": "none"},
            children=[

                dcc.Input(
                    id="upload-dossier",
                    type="file",
                    multiple=True,
                    style={"display": "none"},
                    **{"webkitdirectory": ""}   # ✅ Correction : syntaxe React pour attribut personnalisé
                ),

                html.Label(
                    [
                        svg_inline(ICONE_UPLOAD),
                        html.Div(id="txt-upload-zone", className="upload-zone-text"),
                    ],
                    className="upload-zone",
                    htmlFor="upload-dossier"  # ✅ Correction : htmlFor au lieu de for
                ),

                html.Div(id="txt-upload-hint", className="scan-hint"),
                html.Div(id="upload-fichiers-resume", className="upload-resume"),
            ],
        ),

        html.Div(id="zone-erreur-scan", className="scan-error"),

        html.Div(
            className="scan-actions",
            children=[
                html.Button(id="btn-lancer-scan", className="btn-primary-gold"),
            ],
        ),

        # ── Barre de progression (cachée tant qu'aucun scan n'est en cours) ──
        html.Div(
            id="bloc-progression",
            style={"display": "none"},
            children=[
                html.Div(id="txt-progression-titre", className="progress-title"),
                html.Div(className="progress-track", children=[
                    html.Div(id="progress-bar-fill", className="progress-bar-fill"),
                ]),
                html.Div(id="txt-progression-message", className="progress-message"),
            ],
        ),
    ],
)


# =========================
# 7. MISE EN PAGE GLOBALE
# =========================

app.layout = html.Div(
    id="app-shell",
    className="app-shell",
    children=[

        dcc.Store(id="store-theme", storage_type="local", data="light"),
        dcc.Store(id="store-langue", storage_type="local", data="fr"),
        dcc.Store(id="store-detection-faite", storage_type="memory", data=False),
        # session_id : un par onglet de navigateur, jamais partagé entre utilisateurs
        dcc.Store(id="store-session-id", storage_type="session", data=None),
        dcc.Store(id="store-mode-scan", storage_type="memory", data="path"),
        dcc.Store(id="store-pipeline-termine", storage_type="memory", data=False),
        dcc.Store(id="store-upload-data", storage_type="memory", data=None),

        html.Div(
            className="topbar",
            children=[
                html.Div(className="brand-block", children=[
                    html.Div(svg_inline(ICONE_MARQUE), className="brand-mark"),
                    html.Div([
                        html.Div(id="txt-brand-title", className="brand-text-title"),
                        html.Div(id="txt-brand-subtitle", className="brand-text-subtitle"),
                    ]),
                ]),
                html.Div(className="topbar-controls", children=[
                    html.Div(className="live-chip", children=[html.Span(className="live-dot"), html.Span(id="txt-live")]),
                    html.Div(className="control-pill", children=[
                        html.Button("FR", id="btn-lang-fr", className="control-pill-btn"),
                        html.Button("EN", id="btn-lang-en", className="control-pill-btn"),
                    ]),
                    html.Button(svg_inline(ICONE_LUNE), id="btn-theme-toggle", className="theme-toggle-btn", title="Basculer le thème"),
                ]),
            ],
        ),

        html.Div(
            className="main-content",
            children=[

                formulaire_scan,

                # ── Tout ce qui suit n'apparaît qu'une fois un pipeline terminé ──
                html.Div(
                    id="zone-resultats",
                    style={"display": "none"},
                    children=[

                        html.Div(className="kpi-row", children=[
                            carte_kpi("total_files", "0", "", "var(--gold-600)"),
                            carte_kpi("groups", "0", "", "var(--accent-teal)"),
                            carte_kpi("space", "0", "MB", "var(--accent-coral)"),
                            carte_kpi("depots", "0", "", "var(--gold-600)"),
                            carte_kpi("unites", "0", "", "var(--accent-teal)"),
                        ]),

                        html.Div(className="filter-panel", children=[
                            html.Div([
                                html.Label(id="lbl-filter-depot", className="filter-label"),
                                dcc.Dropdown(id="filtre-depot", clearable=True),
                            ], className="filter-field"),
                            html.Div([
                                html.Label(id="lbl-filter-unite", className="filter-label"),
                                dcc.Dropdown(id="filtre-unite", clearable=True),
                            ], className="filter-field"),
                            html.Div([
                                html.Label(id="lbl-filter-type", className="filter-label"),
                                dcc.Dropdown(id="filtre-type", value="Tous", clearable=False),
                            ], className="filter-field"),
                        ]),

                        html.Div(className="chart-grid-2", children=[
                            html.Div([en_tete_section("titre-unite", "sous-titre-unite"),
                                      dcc.Graph(id="graphique-unite", config={"displayModeBar": False, "responsive": True}, style={"width": "100%", "height": "350px"})],
                                     className="chart-card"),
                            html.Div([en_tete_section("titre-depot", "sous-titre-depot"),
                                      dcc.Graph(id="graphique-depot", config={"displayModeBar": False, "responsive": True}, style={"width": "100%", "height": "350px"})],
                                     className="chart-card"),
                        ]),

                        html.Div(className="chart-grid-2", children=[
                            html.Div([en_tete_section("titre-extension", "sous-titre-extension"),
                                      dcc.Graph(id="graphique-extension", config={"displayModeBar": False, "responsive": True}, style={"width": "100%", "height": "350px"})],
                                     className="chart-card"),
                            html.Div([en_tete_section("titre-type", "sous-titre-type"),
                                      dcc.Graph(id="graphique-type", config={"displayModeBar": False, "responsive": True}, style={"width": "100%", "height": "350px"})],
                                     className="chart-card"),
                        ]),

                        html.Div(className="table-card", children=[
                            en_tete_section("titre-table", "sous-titre-table"),
                            html.Div(id="tableau-hotspot"),
                        ]),

                        # ── Les deux nouvelles fenêtres demandées ────────────────
                        html.Div(className="list-panels-grid", children=[
                            panneau_liste_doublons("exact"),
                            panneau_liste_doublons("quasi"),
                        ]),
                    ],
                ),
            ],
        ),

        html.Div(id="txt-footer", className="app-footer"),
    ],
)


# =========================
# 8. CALLBACKS CLIENT-SIDE — détection auto thème + langue + génération du session_id
# =========================

clientside_callback(
    """
    function(_) {
        let sessionId = window.__currentSessionId;
        if (!sessionId) {
            sessionId = 'sess_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
            window.__currentSessionId = sessionId;
        }
        const theme = window.__dashboardDetection ? window.__dashboardDetection.theme
            : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        const langue = window.__dashboardDetection ? window.__dashboardDetection.langue
            : ((navigator.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en');
        return [theme, langue, true, sessionId];
    }
    """,
    Output("store-theme", "data"),
    Output("store-langue", "data"),
    Output("store-detection-faite", "data"),
    Output("store-session-id", "data"),
    Input("store-detection-faite", "data"),
    prevent_initial_call=False,
)

clientside_callback(
    """
    function(theme) {
        document.documentElement.setAttribute('data-theme', theme || 'light');
        return window.dash_clientside.no_update;
    }
    """,
    Output("app-shell", "data-theme"),
    Input("store-theme", "data"),
)


@app.callback(Output("store-theme", "data", allow_duplicate=True), Input("btn-theme-toggle", "n_clicks"),
              State("store-theme", "data"), prevent_initial_call=True)
def basculer_theme(n_clicks, theme_actuel):
    return "dark" if theme_actuel == "light" else "light"


@app.callback(Output("store-langue", "data", allow_duplicate=True),
              Input("btn-lang-fr", "n_clicks"), Input("btn-lang-en", "n_clicks"), prevent_initial_call=True)
def changer_langue(clic_fr, clic_en):
    return "fr" if ctx.triggered_id == "btn-lang-fr" else "en"


@app.callback(Output("btn-lang-fr", "className"), Output("btn-lang-en", "className"), Input("store-langue", "data"))
def style_boutons_langue(langue):
    base = "control-pill-btn"
    if langue == "en":
        return base, base + " is-active"
    return base + " is-active", base


@app.callback(Output("btn-theme-toggle", "children"), Input("store-theme", "data"))
def icone_theme(theme):
    return svg_inline(ICONE_SOLEIL if theme == "dark" else ICONE_LUNE)


# =========================
# 9. CALLBACK — bascule mode chemin / upload
# =========================

@app.callback(
    Output("store-mode-scan", "data"),
    Output("btn-mode-path", "className"),
    Output("btn-mode-upload", "className"),
    Output("bloc-mode-path", "style"),
    Output("bloc-mode-upload", "style"),
    Input("btn-mode-path", "n_clicks"),
    Input("btn-mode-upload", "n_clicks"),
    prevent_initial_call=True,
)
def basculer_mode_scan(n_path, n_upload):
    base = "control-pill-btn"
    if ctx.triggered_id == "btn-mode-upload":
        return "upload", base, base + " is-active", {"display": "none"}, {"display": "block"}
    return "path", base + " is-active", base, {"display": "block"}, {"display": "none"}


# =========================
# 10. CALLBACK — réception des fichiers uploadés (stockage en mémoire avant lancement)
# =========================

@app.callback(
    Output("store-upload-data", "data"),
    Output("upload-fichiers-resume", "children"),
    Input("upload-dossier", "contents"),
    Input("upload-dossier", "filename"),
    prevent_initial_call=True,
)
def reception_upload(contenus, noms):
    if not contenus:
        return no_update, no_update
    resume = f"{len(noms)} fichier(s) sélectionné(s)"
    return {"contenus": contenus, "noms": noms}, resume


# =========================
# 11. CALLBACK PRINCIPAL DE LANCEMENT — BACKGROUND CALLBACK avec progression live
# =========================

@app.callback(
    output=[
        Output("zone-resultats", "style"),
        Output("store-pipeline-termine", "data"),
        Output("zone-erreur-scan", "children"),
    ],
    inputs=Input("btn-lancer-scan", "n_clicks"),
    state=[
        State("store-mode-scan", "data"),
        State("input-scan-path", "value"),
        State("store-upload-data", "data"),
        State("store-session-id", "data"),
        State("store-langue", "data"),
    ],
    background=True,
    manager=background_callback_manager,
    running=[
        (Output("bloc-progression", "style"), {"display": "block"}, {"display": "none"}),
        (Output("btn-lancer-scan", "disabled"), True, False),
    ],
    progress=[
        Output("progress-bar-fill", "style"),
        Output("txt-progression-message", "children"),
    ],
    prevent_initial_call=True,
)
def lancer_pipeline(set_progress, n_clicks, mode, chemin_saisi, upload_data, session_id, langue):
    if not session_id:
        session_id = str(uuid.uuid4())

    def callback_progression(pct, message):
        set_progress((
            {"width": f"{min(100, max(0, pct)):.0f}%"},
            message,
        ))

    langue = langue or "fr"

    # ── Résolution du dossier à scanner selon le mode actif ──────────────
    if mode == "upload":
        if not upload_data or not upload_data.get("contenus"):
            return {"display": "none"}, False, t("scan_error_no_upload", langue)
        dossier_cible = preparer_dossier_depuis_upload(session_id, upload_data["contenus"], upload_data["noms"])
    else:
        if not chemin_saisi or not chemin_saisi.strip():
            return {"display": "none"}, False, t("scan_error_no_path", langue)
        chemin_saisi = chemin_saisi.strip()
        if not os.path.isdir(chemin_saisi):
            return {"display": "none"}, False, t("scan_error_path_not_found", langue)
        dossier_cible = chemin_saisi

    try:
        executer_pipeline_complet(session_id, dossier_cible, callback_progression=callback_progression)
    except Exception as exc:
        return {"display": "none"}, False, f"Erreur pendant l'analyse : {exc}"

    return {"display": "block"}, True, ""


# =========================
# 12. CALLBACK PRINCIPAL — traduction + graphiques + filtres (se déclenche une fois le pipeline terminé)
# =========================

@app.callback(
    Output("txt-brand-title", "children"), Output("txt-brand-subtitle", "children"), Output("txt-live", "children"),
    Output("titre-scan", "children"), Output("sous-titre-scan", "children"),
    Output("txt-mode-path", "children"), Output("txt-mode-upload", "children"),
    Output("lbl-scan-path", "children"), Output("input-scan-path", "placeholder"), Output("txt-scan-path-hint", "children"),
    Output("txt-upload-zone", "children"), Output("txt-upload-hint", "children"),
    Output("btn-lancer-scan", "children"),
    Output("lbl-filter-depot", "children"), Output("filtre-depot", "placeholder"),
    Output("lbl-filter-unite", "children"), Output("filtre-unite", "placeholder"),
    Output("lbl-filter-type", "children"), Output("filtre-type", "options"),
    Output("titre-unite", "children"), Output("sous-titre-unite", "children"),
    Output("titre-depot", "children"), Output("sous-titre-depot", "children"),
    Output("titre-extension", "children"), Output("sous-titre-extension", "children"),
    Output("titre-type", "children"), Output("sous-titre-type", "children"),
    Output("titre-table", "children"), Output("sous-titre-table", "children"),
    Output("titre-panel-exact", "children"), Output("sous-titre-panel-exact", "children"), Output("txt-export-exact", "children"),
    Output("titre-panel-quasi", "children"), Output("sous-titre-panel-quasi", "children"), Output("txt-export-quasi", "children"),
    Output("recherche-exact", "placeholder"), Output("recherche-quasi", "placeholder"),
    Output("txt-footer", "children"),
    Output({"type": "kpi-label", "index": "total_files"}, "children"),
    Output({"type": "kpi-label", "index": "groups"}, "children"),
    Output({"type": "kpi-label", "index": "space"}, "children"),
    Output({"type": "kpi-label", "index": "depots"}, "children"),
    Output({"type": "kpi-label", "index": "unites"}, "children"),
    Output({"type": "kpi-value", "index": "total_files"}, "children"),
    Output({"type": "kpi-value", "index": "groups"}, "children"),
    Output({"type": "kpi-value", "index": "space"}, "children"),
    Output({"type": "kpi-value", "index": "depots"}, "children"),
    Output({"type": "kpi-value", "index": "unites"}, "children"),
    Output("filtre-depot", "options"), Output("filtre-unite", "options"),
    Output("graphique-unite", "figure"), Output("graphique-depot", "figure"),
    Output("graphique-extension", "figure"), Output("graphique-type", "figure"),
    Output("tableau-hotspot", "children"),
    Output("contenu-panel-exact", "children"), Output("compteur-panel-exact", "children"),
    Output("contenu-panel-quasi", "children"), Output("compteur-panel-quasi", "children"),
    Input("store-langue", "data"), Input("store-theme", "data"),
    Input("filtre-depot", "value"), Input("filtre-unite", "value"), Input("filtre-type", "value"),
    Input("store-pipeline-termine", "data"),
    Input("recherche-exact", "value"), Input("recherche-quasi", "value"),
    State("store-session-id", "data"),
)
def rafraichir_interface(langue, theme, depot, unite, type_dup, pipeline_termine,
                          recherche_exact, recherche_quasi, session_id):
    langue = langue or "fr"
    theme = theme or "light"
    couleurs = PALETTE[theme if theme in PALETTE else "light"]

    textes_statiques = (
        t("brand_title", langue), t("brand_subtitle", langue), t("live", langue),
        t("scan_section_title", langue), t("scan_section_subtitle", langue),
        t("scan_mode_path", langue), t("scan_mode_upload", langue),
        t("scan_path_label", langue), t("scan_path_placeholder", langue), t("scan_path_hint", langue),
        t("scan_upload_text", langue), t("scan_upload_hint", langue),
        t("scan_btn_relaunch", langue) if pipeline_termine else t("scan_btn_launch", langue),
        t("filter_depot", langue), t("filter_depot_all", langue),
        t("filter_unite", langue), t("filter_unite_all", langue),
        t("filter_type", langue),
        [
            {"label": t("filter_type_all", langue), "value": "Tous"},
            {"label": t("filter_type_exact", langue), "value": "Exact"},
            {"label": t("filter_type_quasi", langue), "value": "Quasi"},
        ],
        t("chart_unite_title", langue), t("chart_unite_subtitle", langue),
        t("chart_depot_title", langue), t("chart_depot_subtitle", langue),
        t("chart_extension_title", langue), t("chart_extension_subtitle", langue),
        t("chart_type_title", langue), t("chart_type_subtitle", langue),
        t("table_title", langue), t("table_subtitle", langue),
        t("panel_exact_title", langue), t("panel_exact_subtitle", langue), t("panel_export_pdf", langue),
        t("panel_quasi_title", langue), t("panel_quasi_subtitle", langue), t("panel_export_pdf", langue),
        t("panel_search_placeholder", langue), t("panel_search_placeholder", langue),
        t("footer_text", langue),
        t("kpi_total_files", langue), t("kpi_groups", langue), t("kpi_space", langue),
        t("kpi_depots", langue), t("kpi_unites", langue),
    )

    # ── Tant qu'aucun pipeline n'a tourné pour cette session, on n'a rien à afficher ──
    if not session_id or not session_a_des_resultats(session_id):
        figure_vide = px.scatter()
        figure_vide.update_layout(paper_bgcolor=couleurs["bg_card"], plot_bgcolor=couleurs["bg_card"])
        return textes_statiques + (
            "0", "0", "0", "0", "0",
            [], [], figure_vide, figure_vide, figure_vide, figure_vide,
            None, None, "0", None, "0",
        )

    resultats = charger_resultats_session(session_id)
    df_combine = resultats["combine"]
    df_hotspot = resultats["hotspot"]
    df_exacts = resultats["exacts"]
    df_quasi = resultats["quasi"]
    kpis_dict = resultats["kpis"]
    cle_unites = "Nombre d'unités métier impactées"

    df = df_combine.copy()
    if depot:
        df = df[df["depot"] == depot]
    if unite:
        df = df[df["unite_metier"] == unite]
    if type_dup and type_dup != "Tous":
        df = df[df["type_duplication"] == type_dup]

    options_depot = [{"label": d, "value": d} for d in sorted(df_combine["depot"].dropna().unique())] if len(df_combine) else []
    options_unite = [{"label": u, "value": u} for u in sorted(df_combine["unite_metier"].dropna().unique())] if len(df_combine) else []

    layout_commun = dict(
        plot_bgcolor=couleurs["bg_card"], paper_bgcolor=couleurs["bg_card"],
        font_color=couleurs["text_secondary"], font_family="IBM Plex Sans, sans-serif",
        margin=dict(l=20, r=20, t=20, b=70), autosize=True,
    )

    # ── Graphiques ─────────────────────────────────────────────────────────
    if len(df):
        agg_unite = df.groupby("unite_metier")["taille_octets"].sum().reset_index().sort_values("taille_octets", ascending=True).tail(10)
        agg_unite["mb"] = agg_unite["taille_octets"] / (1024 * 1024)
        fig_unite = px.bar(agg_unite, x="mb", y="unite_metier", orientation="h",
                            labels={"mb": t("axis_space_mb", langue), "unite_metier": ""},
                            color_discrete_sequence=[couleurs["navy"]])
    else:
        fig_unite = px.bar()
    fig_unite.update_layout(**layout_commun)
    fig_unite.update_xaxes(gridcolor=couleurs["grid"])
    fig_unite.update_yaxes(gridcolor=couleurs["grid"])

    if len(df):
        agg_depot = df.groupby("depot")["taille_octets"].sum().reset_index()
        fig_depot = px.treemap(agg_depot, path=["depot"], values="taille_octets", color="taille_octets",
                                color_continuous_scale=[couleurs["grid"], couleurs["navy"]])
        fig_depot.update_traces(textinfo="label+percent root",
                                 textfont_color=couleurs["text_primary"] if theme == "light" else "#FFFFFF")
    else:
        fig_depot = px.treemap()
    fig_depot.update_layout(paper_bgcolor=couleurs["bg_card"], margin=dict(l=10, r=10, t=10, b=10), height=300, coloraxis_showscale=False)

    if len(df):
        agg_ext = df.groupby("extension")["chemin"].count().reset_index(name="nb").sort_values("nb", ascending=False).head(8)
        fig_extension = px.bar(agg_ext, x="extension", y="nb", labels={"extension": "", "nb": t("axis_nb_files", langue)},
                                color_discrete_sequence=[couleurs["steel"]])
    else:
        fig_extension = px.bar()
    fig_extension.update_layout(**layout_commun)
    fig_extension.update_xaxes(gridcolor=couleurs["grid"])
    fig_extension.update_yaxes(gridcolor=couleurs["grid"])

    if len(df):
        repartition = df["type_duplication"].value_counts().reset_index()
        repartition.columns = ["type_duplication", "nb"]
        repartition["label"] = repartition["type_duplication"].map({"Exact": t("legend_exact", langue), "Quasi": t("legend_quasi", langue)})
        fig_type = px.pie(repartition, names="label", values="nb", hole=0.6, color="type_duplication",
                           color_discrete_map={"Exact": couleurs["navy"], "Quasi": couleurs["coral"]})
    else:
        fig_type = px.pie()
    fig_type.update_layout(paper_bgcolor=couleurs["bg_card"], margin=dict(l=10, r=10, t=10, b=10), height=300,
                            showlegend=True, legend=dict(orientation="h", y=-0.12, font=dict(color=couleurs["text_secondary"])),
                            font_color=couleurs["text_secondary"])

    # ── Tableau top points chauds ─────────────────────────────────────────
    if len(df_hotspot):
        entetes = html.Tr([html.Th(t("table_col_rank", langue)), html.Th(t("table_col_depot", langue)),
                            html.Th(t("table_col_unite", langue)), html.Th(t("table_col_files", langue)), html.Th(t("table_col_space", langue))])
        lignes_t = [entetes]
        for _, ligne in df_hotspot.iterrows():
            lignes_t.append(html.Tr([
                html.Td(html.Span(int(ligne["rang"]), className="rank-chip")),
                html.Td(ligne["depot"]), html.Td(ligne["unite_metier"]),
                html.Td(f"{int(ligne['nb_fichiers_dupliques']):,}".replace(",", " ")),
                html.Td(ligne["espace_total_lisible"]),
            ]))
        tableau = html.Table([html.Thead(lignes_t[0]), html.Tbody(lignes_t[1:])], className="hotspot-table")
    else:
        tableau = html.Div(t("panel_empty", langue), className="list-panel-empty")

    # ── Fenêtre 1 : liste des doublons exacts (avec filtres + recherche) ──
    if len(df_exacts) and "est_doublon_exact" in df_exacts.columns:
        df_exact_filtre = df_exacts[df_exacts["est_doublon_exact"] == True].copy()
    else:
        df_exact_filtre = pd.DataFrame()
    if depot and len(df_exact_filtre):
        df_exact_filtre = df_exact_filtre[df_exact_filtre["chemin"].str.contains(depot, regex=False, na=False)]
    if recherche_exact and len(df_exact_filtre):
        rq = recherche_exact.lower()
        df_exact_filtre = df_exact_filtre[
            df_exact_filtre["nom_fichier"].str.lower().str.contains(rq, na=False)
            | df_exact_filtre["chemin"].str.lower().str.contains(rq, na=False)
        ]

    contenu_exact, compteur_exact = _construire_table_liste(
        df_exact_filtre, langue, colonnes=["statut_doublon", "nom_fichier", "chemin", "taille_lisible", "date_creation"],
        cles_traduction=["panel_col_status", "panel_col_name", "panel_col_path", "panel_col_size", "panel_col_date"],
    )

    # ── Fenêtre 2 : liste des quasi-doublons ──────────────────────────────
    if len(df_quasi) and "cluster_dbscan" in df_quasi.columns:
        df_quasi_filtre = df_quasi[df_quasi["cluster_dbscan"] != -1].copy()
    else:
        df_quasi_filtre = pd.DataFrame()
    if depot and len(df_quasi_filtre):
        df_quasi_filtre = df_quasi_filtre[df_quasi_filtre["chemin"].str.contains(depot, regex=False, na=False)]
    if recherche_quasi and len(df_quasi_filtre):
        rq = recherche_quasi.lower()
        df_quasi_filtre = df_quasi_filtre[
            df_quasi_filtre["nom_fichier"].str.lower().str.contains(rq, na=False)
            | df_quasi_filtre["chemin"].str.lower().str.contains(rq, na=False)
        ]

    contenu_quasi, compteur_quasi = _construire_table_liste(
        df_quasi_filtre, langue, colonnes=["statut_cluster", "nom_fichier", "chemin", "taille_lisible", "score_similarite"],
        cles_traduction=["panel_col_cluster", "panel_col_name", "panel_col_path", "panel_col_size", "panel_col_score"],
    )

    return textes_statiques + (
        f"{int(kpis_dict.get('Nombre total de fichiers dupliqués', 0)):,}".replace(",", " "),
        f"{int(kpis_dict.get('Nombre de groupes de duplication distincts', 0)):,}".replace(",", " "),
        f"{kpis_dict.get('Espace total gaspillé (MB)', 0):,.0f}".replace(",", " "),
        f"{int(kpis_dict.get('Nombre de dépôts impactés', 0)):,}",
        f"{int(kpis_dict.get(cle_unites, 0)):,}",
        options_depot, options_unite,
        fig_unite, fig_depot, fig_extension, fig_type, tableau,
        contenu_exact, compteur_exact, contenu_quasi, compteur_quasi,
    )


def _construire_table_liste(df, langue, colonnes, cles_traduction):
    """Construit la table HTML pour les fenêtres de listes de doublons (factorisé exact/quasi)."""
    if df is None or len(df) == 0:
        return html.Div(t("panel_empty", langue), className="list-panel-empty"), f"0 {t('panel_count_suffix', langue)}"

    entetes = html.Tr([html.Th(t(cle, langue)) for cle in cles_traduction])
    lignes = [entetes]
    for _, ligne in df.head(500).iterrows():  # plafond d'affichage pour rester fluide ; le PDF contient tout
        cellules = []
        for col in colonnes:
            val = ligne.get(col, "")
            if col == "score_similarite":
                val = f"{val:.3f}" if pd.notna(val) else "—"
                cellules.append(html.Td(str(val)))
                continue
            if col in ("statut_doublon", "statut_cluster"):
                cellules.append(html.Td(html.Span(str(val), className="status-chip")))
                continue
            cellules.append(html.Td(str(val)[:80]))
        lignes.append(html.Tr(cellules))

    table = html.Table([html.Thead(lignes[0]), html.Tbody(lignes[1:])], className="list-table")
    compteur = f"{len(df):,}".replace(",", " ") + f" {t('panel_count_suffix', langue)}"
    return table, compteur


# =========================
# 13. CALLBACKS — EXPORT PDF DES DEUX FENÊTRES
# =========================

@app.callback(
    Output("download-pdf-exact", "data"),
    Input("btn-export-exact", "n_clicks"),
    State("store-session-id", "data"), State("store-langue", "data"),
    State("filtre-depot", "value"), State("filtre-unite", "value"), State("filtre-type", "value"),
    prevent_initial_call=True,
)
def exporter_pdf_exact(n_clicks, session_id, langue, depot, unite, type_dup):
    if not session_id or not session_a_des_resultats(session_id):
        return no_update
    resultats = charger_resultats_session(session_id)
    pdf_bytes = generer_pdf_doublons_exacts(
        resultats["exacts"], langue=langue or "fr",
        filtres_actifs={"depot": depot, "unite": unite, "type_dup": type_dup},
    )
    return dcc.send_bytes(pdf_bytes, "doublons_exacts.pdf")


@app.callback(
    Output("download-pdf-quasi", "data"),
    Input("btn-export-quasi", "n_clicks"),
    State("store-session-id", "data"), State("store-langue", "data"),
    State("filtre-depot", "value"), State("filtre-unite", "value"), State("filtre-type", "value"),
    prevent_initial_call=True,
)
def exporter_pdf_quasi(n_clicks, session_id, langue, depot, unite, type_dup):
    if not session_id or not session_a_des_resultats(session_id):
        return no_update
    resultats = charger_resultats_session(session_id)
    pdf_bytes = generer_pdf_quasi_doublons(
        resultats["quasi"], langue=langue or "fr",
        filtres_actifs={"depot": depot, "unite": unite, "type_dup": type_dup},
    )
    return dcc.send_bytes(pdf_bytes, "quasi_doublons.pdf")


# =========================
# 14. LANCEMENT
# =========================

server = app.server

if __name__ == "__main__":
    app.run(debug=True, port=8050)
