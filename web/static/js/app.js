/**
 * App — sidebar toggle, hash router, theme, initialization.
 */
(function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const btnSidebar = document.getElementById('btn-sidebar');
    const btnCloseSidebar = document.getElementById('btn-close-sidebar');

    // Theme toggle
    const btnTheme = document.getElementById('btn-theme-toggle');
    const iconSun = document.getElementById('theme-icon-sun');
    const iconMoon = document.getElementById('theme-icon-moon');

    function applyTheme(theme) {
        if (theme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
            iconSun.style.display = '';
            iconMoon.style.display = 'none';
        } else {
            document.documentElement.removeAttribute('data-theme');
            iconSun.style.display = 'none';
            iconMoon.style.display = '';
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', next);
        applyTheme(next);
    }

    btnTheme.addEventListener('click', toggleTheme);
    applyTheme(localStorage.getItem('theme') || 'dark');

    function openSidebar() {
        sidebar.classList.add('open');
        overlay.classList.add('visible');
        History.load();
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('visible');
    }

    btnSidebar.addEventListener('click', openSidebar);
    btnCloseSidebar.addEventListener('click', closeSidebar);
    overlay.addEventListener('click', closeSidebar);

    // Views
    const views = {
        welcome: document.getElementById('view-welcome'),
        progress: document.getElementById('view-progress'),
        report: document.getElementById('view-report'),
    };

    function showView(name) {
        Object.values(views).forEach(v => { if (v) v.style.display = 'none'; });
        if (views[name]) views[name].style.display = (name === 'welcome') ? 'flex' : 'block';
    }

    function route() {
        const hash = location.hash || '#/';

        if (hash.startsWith('#/report/')) {
            const reportId = hash.split('/')[2];
            showView('report');
            Report.load(reportId);
        } else if (hash === '#/history') {
            openSidebar();
        } else {
            // Default: show welcome unless progress is visible
            if (views.progress.style.display !== 'block') {
                showView('welcome');
            }
        }
    }

    // Expose globally for other modules
    window.AppViews = { showView, closeSidebar };

    // Initialize
    Research.init();
    Report.init();

    // Router
    window.addEventListener('hashchange', route);
    route();
})();
