/**
 * Research view — form submission, SSE progress, animated topics, completion.
 */
const Research = (() => {
    let _eventSource = null;
    let _timer = null;
    let _startTime = 0;

    const EXAMPLE_TOPICS = [
        "Impact of LLMs on drug discovery",
        "Quantum computing breakthroughs 2025",
        "How do mRNA vaccines work",
        "Future of nuclear fusion energy",
        "AI agents in software engineering",
        "History of the Internet",
    ];

    function init() {
        document.getElementById('research-form').addEventListener('submit', _onSubmit);
        _checkHealth();
        _renderExampleTopics();
    }

    function _renderExampleTopics() {
        const container = document.getElementById('example-topics');
        if (!container) return;
        container.innerHTML = '';
        EXAMPLE_TOPICS.forEach(topic => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'topic-chip';
            chip.textContent = topic;
            chip.addEventListener('click', () => {
                document.getElementById('topic').value = topic;
                document.getElementById('topic').focus();
            });
            container.appendChild(chip);
        });
    }

    async function _checkHealth() {
        const dot = document.getElementById('health-status');
        try {
            const health = await API.health();
            if (health.ollama_reachable) {
                dot.className = 'health-dot ok';
                dot.title = 'Ollama connected (' + health.ollama_models.length + ' models)';
            } else {
                dot.className = 'health-dot error';
                dot.title = 'Ollama not reachable — start with: ollama serve';
            }
        } catch {
            dot.className = 'health-dot error';
            dot.title = 'Cannot connect to server';
        }
    }

    async function _onSubmit(e) {
        e.preventDefault();

        const topic = document.getElementById('topic').value.trim();
        if (!topic) return;

        const model = document.getElementById('setting-model').value;
        const num_queries = parseInt(document.getElementById('setting-queries').value) || 3;
        const results_per_query = parseInt(document.getElementById('setting-results').value) || 3;

        // Disable send button
        const btn = document.getElementById('btn-start');
        btn.disabled = true;

        // Show progress view
        _resetProgress();
        AppViews.showView('progress');
        document.getElementById('view-progress').style.display = 'block';

        try {
            const job = await API.startResearch({ topic, model, num_queries, results_per_query });
            _startTimer();
            _subscribeToProgress(job.job_id);
        } catch (err) {
            _showError(err.message);
            _enableForm();
        }
    }

    function _subscribeToProgress(jobId) {
        _eventSource = API.streamProgress(jobId, {
            onStatus: _handleStatus,
            onQueries: _handleQueries,
            onUrlFound: _handleUrlFound,
            onScrapeProgress: _handleScrapeProgress,
            onComplete: _handleComplete,
            onError: _handleError,
        });
    }

    function _handleStatus(data) {
        const el = document.getElementById('progress-status');
        el.innerHTML = '<span class="spinner"></span> ' + (data.message || data.status);

        if (data.status === 'searching') {
            _setProgress(10);
        } else if (data.status === 'generating') {
            _setProgress(90);
        }
    }

    function _handleQueries(data) {
        const container = document.getElementById('progress-queries');
        const list = document.getElementById('queries-list');
        container.style.display = 'block';
        list.innerHTML = '';
        data.queries.forEach(q => {
            const li = document.createElement('li');
            li.textContent = q;
            list.appendChild(li);
        });
        _setProgress(25);
    }

    function _handleUrlFound(data) {
        const container = document.getElementById('progress-urls');
        const list = document.getElementById('urls-list');
        const count = document.getElementById('url-count');
        container.style.display = 'block';

        const li = document.createElement('li');
        li.innerHTML = '<span class="icon">&#128279;</span>' +
            '<span>' + _escapeHtml(_truncateUrl(data.url, 70)) + '</span>';
        list.appendChild(li);
        list.scrollTop = list.scrollHeight;

        count.textContent = list.children.length;
        _setProgress(30 + Math.min(20, list.children.length * 2));
    }

    function _handleScrapeProgress(data) {
        const container = document.getElementById('progress-scraping');
        const list = document.getElementById('scrape-list');
        const countEl = document.getElementById('scrape-count');
        container.style.display = 'block';

        const li = document.createElement('li');
        li.className = data.success ? 'success' : 'failed';
        const icon = data.success ? '&#9989;' : '&#10060;';
        const info = data.success
            ? _formatChars(data.chars) + ' \u00b7 ' + _formatMs(data.elapsed_ms)
            : 'failed';
        li.innerHTML = '<span class="icon">' + icon + '</span>' +
            '<span>' + _escapeHtml(_truncateUrl(data.url, 55)) + ' \u2014 ' + info + '</span>';
        list.appendChild(li);
        list.scrollTop = list.scrollHeight;

        countEl.textContent = data.completed + '/' + data.total;
        _setProgress(50 + Math.round((data.completed / data.total) * 40));
    }

    function _handleComplete(data) {
        _stopTimer();
        _setProgress(100);
        document.getElementById('progress-status').innerHTML =
            '<span style="color:var(--success)">&#10003;</span> Research Complete';

        const stats = document.getElementById('complete-stats');
        stats.innerHTML =
            _statCard(data.urls_found, 'URLs Found') +
            _statCard(data.pages_scraped, 'Scraped') +
            _statCard(data.pages_failed, 'Failed') +
            _statCard(_formatMs(data.elapsed_ms), 'Time');

        document.getElementById('btn-view-report').href = '#/report/' + data.report_id;
        document.getElementById('progress-complete').style.display = 'block';
        _enableForm();
    }

    function _handleError(data) {
        _stopTimer();
        _showError(data.message || 'An unknown error occurred');
        _enableForm();
    }

    function _showError(message) {
        document.getElementById('error-message').textContent = message;
        document.getElementById('progress-error').style.display = 'block';
        document.getElementById('progress-status').innerHTML =
            '<span style="color:var(--error)">&#10007;</span> Error';
    }

    function _setProgress(pct) {
        document.getElementById('progress-bar').style.width = pct + '%';
    }

    function _resetProgress() {
        _setProgress(0);
        document.getElementById('progress-status').innerHTML = '<span class="spinner"></span> Starting...';
        document.getElementById('progress-time').textContent = '0s';
        document.getElementById('queries-list').innerHTML = '';
        document.getElementById('urls-list').innerHTML = '';
        document.getElementById('scrape-list').innerHTML = '';
        document.getElementById('url-count').textContent = '0';
        document.getElementById('scrape-count').textContent = '0/0';
        document.getElementById('complete-stats').innerHTML = '';

        ['progress-queries', 'progress-urls', 'progress-scraping',
         'progress-complete', 'progress-error'].forEach(id => {
            document.getElementById(id).style.display = 'none';
        });
    }

    function _enableForm() {
        document.getElementById('btn-start').disabled = false;
    }

    function _startTimer() {
        _startTime = Date.now();
        _timer = setInterval(() => {
            const elapsed = Math.round((Date.now() - _startTime) / 1000);
            document.getElementById('progress-time').textContent = elapsed + 's';
        }, 1000);
    }

    function _stopTimer() {
        if (_timer) { clearInterval(_timer); _timer = null; }
    }

    // ── Helpers ─────────────────────────────────
    function _statCard(value, label) {
        return '<div class="stat-card"><span class="value">' + value +
               '</span><span class="label">' + label + '</span></div>';
    }

    function _truncateUrl(url, max) {
        if (url.length <= max) return url;
        return url.substring(0, max - 3) + '...';
    }

    function _formatChars(n) {
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K chars';
        return n + ' chars';
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

    return { init };
})();
