/**
 * History — loads report list into the sidebar.
 */
const History = (() => {

    async function load() {
        const container = document.getElementById('history-list');
        const emptyMsg = document.getElementById('history-empty');

        try {
            const reports = await API.listReports();

            if (reports.length === 0) {
                emptyMsg.style.display = 'block';
                // Remove any leftover cards
                container.querySelectorAll('.history-card').forEach(el => el.remove());
                return;
            }

            emptyMsg.style.display = 'none';
            // Clear existing cards (keep empty msg element)
            container.querySelectorAll('.history-card').forEach(el => el.remove());

            reports.forEach(report => {
                const card = document.createElement('div');
                card.className = 'history-card';
                card.onclick = () => {
                    location.hash = '#/report/' + report.id;
                    if (window.AppViews) AppViews.closeSidebar();
                };

                const date = _formatDate(report.created_at);
                const time = _formatMs(report.elapsed_ms);

                card.innerHTML =
                    '<span class="topic">' + _escapeHtml(report.topic) + '</span>' +
                    '<span class="date">' + date + '</span>' +
                    '<div class="stats">' +
                        '<span>' + report.urls_found + ' URLs</span>' +
                        '<span>' + report.pages_scraped + ' scraped</span>' +
                        '<span>' + time + '</span>' +
                    '</div>';

                container.appendChild(card);
            });

        } catch (err) {
            container.innerHTML = '<p class="sidebar-empty">Failed to load reports.</p>';
        }
    }

    function _formatDate(isoString) {
        const d = new Date(isoString);
        const now = new Date();
        const diffMs = now - d;
        const diffMins = Math.round(diffMs / 60000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return diffMins + ' min ago';
        if (diffMins < 1440) return Math.round(diffMins / 60) + 'h ago';
        return d.toLocaleDateString();
    }

    function _formatMs(ms) {
        if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
        return Math.round(ms) + 'ms';
    }

    function _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { load };
})();
