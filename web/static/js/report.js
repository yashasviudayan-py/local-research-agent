/**
 * Report view — display rendered markdown report with metadata.
 */
const Report = (() => {
    let _currentReport = null;

    function init() {
        document.getElementById('btn-download').addEventListener('click', _download);
        document.getElementById('btn-delete').addEventListener('click', _delete);
        document.getElementById('btn-back').addEventListener('click', () => {
            location.hash = '#/';
        });
    }

    async function load(reportId) {
        const metaEl = document.getElementById('report-meta');
        const contentEl = document.getElementById('report-content');

        metaEl.innerHTML = '<p style="color:var(--text-muted)">Loading report...</p>';
        contentEl.innerHTML = '';

        try {
            const report = await API.getReport(reportId);
            _currentReport = report;

            // Metadata
            const date = new Date(report.created_at).toLocaleString();
            metaEl.innerHTML =
                '<h3>' + _escapeHtml(report.topic) + '</h3>' +
                '<div class="meta-grid">' +
                    _metaItem('Date', date) +
                    _metaItem('URLs Found', report.urls_found) +
                    _metaItem('Scraped', report.pages_scraped) +
                    _metaItem('Failed', report.pages_failed) +
                    _metaItem('Time', _formatMs(report.elapsed_ms)) +
                    _metaItem('Size', _formatBytes(report.file_size)) +
                '</div>';

            // Render markdown
            contentEl.innerHTML = marked.parse(report.content);

        } catch (err) {
            metaEl.innerHTML = '<p style="color:var(--error)">Failed to load report: ' + _escapeHtml(err.message) + '</p>';
        }
    }

    function _download() {
        if (!_currentReport) return;

        const blob = new Blob([_currentReport.content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = _currentReport.topic.replace(/[^a-z0-9]/gi, '-').toLowerCase() + '.md';
        a.click();
        URL.revokeObjectURL(url);
    }

    async function _delete() {
        if (!_currentReport) return;
        if (!confirm('Delete this report permanently?')) return;

        try {
            await API.deleteReport(_currentReport.id);
            _currentReport = null;
            location.hash = '#/';
        } catch (err) {
            alert('Failed to delete: ' + err.message);
        }
    }

    function _metaItem(label, value) {
        return '<div class="meta-item">' +
            '<span class="meta-label">' + label + '</span>' +
            '<span class="meta-value">' + value + '</span>' +
        '</div>';
    }

    function _formatMs(ms) {
        if (ms >= 1000) return (ms / 1000).toFixed(1) + 's';
        return Math.round(ms) + 'ms';
    }

    function _formatBytes(bytes) {
        if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
        if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
        return bytes + ' B';
    }

    function _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init, load };
})();
