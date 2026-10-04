/**
 * REST API client for Baseball Savant web interface.
 */

export const api = {
  /**
   * Search for MLB player by name or ID.
   * @param {string} query
   * @param {string} [type] - 'pitcher' or 'batter'
   * @returns {Promise<Array>}
   */
  async searchPlayer(query, type = "") {
    if (!query || !query.trim()) return [];
    const params = new URLSearchParams({ query: query.trim() });
    if (type) params.append("type", type);

    const res = await fetch(`/api/search/player?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Player search failed: ${res.statusText}`);
    }
    const data = await res.json();
    return data.results || [];
  },

  /**
   * Run Statcast scrape for pitcher or batter.
   * @param {Object} payload
   * @returns {Promise<Object>}
   */
  async runScrape(payload) {
    const res = await fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || `Scrape failed: ${res.statusText}`);
    }
    return data;
  },

  /**
   * Fetch list of recent searches from server.
   * @returns {Promise<Array>}
   */
  async getRecentSearches() {
    const res = await fetch("/api/recent");
    if (!res.ok) {
      throw new Error(`Failed to load recent searches: ${res.statusText}`);
    }
    const data = await res.json();
    return data.recent || [];
  },

  /**
   * Retrieve and parse CSV file data for modal display.
   * @param {string} filename
   * @returns {Promise<Object>}
   */
  async getCSVData(filename) {
    const params = new URLSearchParams({ filename });
    const res = await fetch(`/api/csv-data?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Failed to read CSV data: ${res.statusText}`);
    }
    return await res.json();
  },

  /**
   * Fetch current data model synchronization status and last run metadata.
   * @returns {Promise<Object>}
   */
  async getModelStatus() {
    const res = await fetch("/api/model/status");
    if (!res.ok) {
      throw new Error(`Failed to fetch model status: ${res.statusText}`);
    }
    return await res.json();
  },

  /**
   * Run three-source velocity data model bet evaluation.
   * @param {Object} payload
   * @returns {Promise<Object>}
   */
  async runDataModel(payload) {
    const res = await fetch("/api/model/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || `Model execution failed: ${res.statusText}`);
    }
    return data;
  },

  /**
   * Fetch list of available matchup data samples for model evaluation.
   * @returns {Promise<Array>}
   */
  async getModelSamples() {
    const res = await fetch("/api/model/samples");
    if (!res.ok) {
      throw new Error(`Failed to load model samples: ${res.statusText}`);
    }
    const data = await res.json();
    return data.samples || [];
  },

  /**
   * Load and sync a specific matchup sample into dataModel.
   * @param {string} filename
   * @param {Object} [options]
   * @returns {Promise<Object>}
   */
  async loadModelSample(filename, options = {}) {
    const res = await fetch("/api/model/load-sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename, ...options }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || `Failed to load sample: ${res.statusText}`);
    }
    return data;
  },

  /**
   * Clear all outputs in the output folder.
   * @returns {Promise<Object>}
   */
  async clearOutput() {
    const res = await fetch("/api/clear-output", { method: "POST" });
    if (!res.ok) {
      throw new Error(`Failed to clear output: ${res.statusText}`);
    }
    return await res.json();
  },

  /**
   * Send unload beacon to clear output when browser window/tab closes.
   */
  sendUnloadCleanupBeacon() {
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/clear-output");
      } else {
        fetch("/api/clear-output", { method: "POST", keepalive: true });
      }
    } catch (e) {
      console.warn("Unload cleanup beacon failed:", e);
    }
  },
};
