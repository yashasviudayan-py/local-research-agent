/**
 * App — sidebar toggle, hash router, initialization.
 */
(function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const btnSidebar = document.getElementById('btn-sidebar');
    const btnCloseSidebar = document.getElementById('btn-close-sidebar');

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
