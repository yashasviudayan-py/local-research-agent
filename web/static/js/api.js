/**
 * API client for the Local Research Agent backend.
 */
const API = {
    /**
     * Start a new research job.
     * @param {Object} params
     * @param {string} params.topic
     * @param {string} params.model
     * @param {number} params.num_queries
     * @param {number} params.results_per_query
     * @returns {Promise<Object>} JobResponse
     */
    async startResearch({ topic, model, num_queries, results_per_query }) {
        const res = await fetch('/api/research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, model, num_queries, results_per_query }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to start research');
        }
        return res.json();
    },

    /**
     * Get job status.
     * @param {string} jobId
     * @returns {Promise<Object>}
     */
    async getJobStatus(jobId) {
        const res = await fetch(`/api/research/${jobId}`);
        if (!res.ok) throw new Error('Job not found');
        return res.json();
    },

    /**
     * Subscribe to SSE progress events.
     * @param {string} jobId
     * @param {Object} handlers - { onStatus, onQueries, onUrlFound, onScrapeProgress, onComplete, onError }
     * @returns {EventSource}
     */
    streamProgress(jobId, handlers) {
        const es = new EventSource(`/api/research/${jobId}/stream`);

        es.addEventListener('status', (e) => {
            handlers.onStatus?.(JSON.parse(e.data));
        });
        es.addEventListener('queries', (e) => {
            handlers.onQueries?.(JSON.parse(e.data));
        });
        es.addEventListener('url_found', (e) => {
            handlers.onUrlFound?.(JSON.parse(e.data));
        });
        es.addEventListener('scrape_progress', (e) => {
            handlers.onScrapeProgress?.(JSON.parse(e.data));
        });
        es.addEventListener('complete', (e) => {
            es.close();
            handlers.onComplete?.(JSON.parse(e.data));
        });
        es.addEventListener('error', (e) => {
            es.close();
            if (e.data) {
                handlers.onError?.(JSON.parse(e.data));
            } else {
                handlers.onError?.({ message: 'Connection lost' });
            }
        });

        return es;
    },

    /**
     * List all saved reports.
     * @returns {Promise<Array>}
     */
    async listReports() {
        const res = await fetch('/api/reports');
        return res.json();
    },

    /**
     * Get a specific report.
     * @param {string} reportId
     * @returns {Promise<Object>}
     */
    async getReport(reportId) {
        const res = await fetch(`/api/reports/${reportId}`);
        if (!res.ok) throw new Error('Report not found');
        return res.json();
    },

    /**
     * Delete a report.
     * @param {string} reportId
     * @returns {Promise<void>}
     */
    async deleteReport(reportId) {
        const res = await fetch(`/api/reports/${reportId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete report');
    },

    /**
     * Health check.
     * @returns {Promise<Object>}
     */
    async health() {
        const res = await fetch('/api/health');
        return res.json();
    },
};
