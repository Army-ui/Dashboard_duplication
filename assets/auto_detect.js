/* ============================================================
   AUTO-DÉTECTION LANGUE & THÈME SYSTÈME
   S'exécute avant le rendu Dash pour éviter le flash de mauvais thème
   ============================================================ */

(function () {
    function detecterThemeSysteme() {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
    }

    function detecterLangueNavigateur() {
        var langues = navigator.languages || [navigator.language || 'en'];
        for (var i = 0; i < langues.length; i++) {
            var code = langues[i].toLowerCase();
            if (code.startsWith('fr')) return 'fr';
        }
        return 'en'; // Langue par défaut si aucune préférence française détectée
    }

    // Applique immédiatement le thème pour éviter le flash blanc/sombre au chargement
    var themeInitial = localStorage.getItem('dash-theme-override') || detecterThemeSysteme();
    document.documentElement.setAttribute('data-theme', themeInitial);

    // Stocke la détection initiale pour que Dash puisse la lire au montage
    window.__dashboardDetection = {
        theme: themeInitial,
        langue: localStorage.getItem('dash-lang-override') || detecterLangueNavigateur(),
    };

    // Réagit en direct si l'utilisateur change le thème de son OS pendant que l'app est ouverte
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
            if (!localStorage.getItem('dash-theme-override')) {
                var nouveauTheme = e.matches ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', nouveauTheme);
                var store = document.getElementById('store-theme');
                if (store) {
                    var event = new CustomEvent('theme-system-change', { detail: nouveauTheme });
                    document.dispatchEvent(event);
                }
            }
        });
    }
})();