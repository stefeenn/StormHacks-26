/**
 * DataModelController: Coordinates the Three-Source Velocity Model & Bet Evaluator interface.
 * Handles input parameters, sample fetching/switching, model execution,
 * and rendering recommendation, comparison stats, pitch table, and graph.
 */

import { api } from "./api.js?v=2";

export class DataModelController {
  /**
   * @param {Object} [options]
   */
  constructor(options = {}) {
    this.modalEl = document.getElementById("data-model-modal");
    this.closeBtn = document.getElementById("model-close-btn");
    this.footerCloseBtn = document.getElementById("model-footer-close-btn");

    this.matchupBadge = document.getElementById("model-matchup-badge");
    this.sampleSelect = document.getElementById("model-sample-select");
    this.refreshSamplesBtn = document.getElementById("model-refresh-samples-btn");
    this.syncIndicator = document.getElementById("model-sync-indicator");
    this.syncText = document.getElementById("model-sync-text");

    // Inputs
    this.inputLine = document.getElementById("input-model-line");
    this.inputUnder = document.getElementById("input-model-under-odds");
    this.inputOver = document.getElementById("input-model-over-odds");
    this.inputStake = document.getElementById("input-model-stake");
    this.inputBankroll = document.getElementById("input-model-bankroll");
    this.inputKelly = document.getElementById("input-model-kelly");
    this.selectArsenalCol = document.getElementById("select-model-arsenal-col");
    this.selectBatterCol = document.getElementById("select-model-batter-col");
    this.inputSims = document.getElementById("input-model-sims");

    this.btnRun = document.getElementById("btn-run-model");
    this.btnRunText = document.getElementById("btn-run-model-text");
    this.statusEl = document.getElementById("model-running-status");

    // Results elements
    this.emptyState = document.getElementById("model-empty-state");
    this.contentState = document.getElementById("model-content-state");
    this.recBanner = document.getElementById("model-recommendation-banner");
    this.recHeadline = document.getElementById("rec-headline");
    this.recSub = document.getElementById("rec-sub");
    this.recRating = document.getElementById("rec-rating-badge");

    // Sides
    this.valUnderLine = document.getElementById("val-under-line");
    this.valUnderOdds = document.getElementById("val-under-odds");
    this.valUnderWin = document.getElementById("val-under-win");
    this.valUnderBe = document.getElementById("val-under-be");
    this.meterUnderBar = document.getElementById("meter-under-bar");
    this.valUnderEdge = document.getElementById("val-under-edge");
    this.valUnderSure = document.getElementById("val-under-sure");
    this.valUnderAvg = document.getElementById("val-under-avg");
    this.valUnderKelly = document.getElementById("val-under-kelly");

    this.valOverLine = document.getElementById("val-over-line");
    this.valOverOdds = document.getElementById("val-over-odds");
    this.valOverWin = document.getElementById("val-over-win");
    this.valOverBe = document.getElementById("val-over-be");
    this.meterOverBar = document.getElementById("meter-over-bar");
    this.valOverEdge = document.getElementById("val-over-edge");
    this.valOverSure = document.getElementById("val-over-sure");
    this.valOverAvg = document.getElementById("val-over-avg");
    this.valOverKelly = document.getElementById("val-over-kelly");

    // Graph & details
    this.plotImg = document.getElementById("model-plot-img");
    this.graphExpandBtn = document.getElementById("btn-graph-expand");
    this.whyList = document.getElementById("model-why-list");
    this.cautionsText = document.getElementById("model-cautions-text");
    this.cautionsBox = document.getElementById("model-cautions-box");
    this.pitchTableBody = document.getElementById("model-pitch-table-body");
    this.pitchCountBadge = document.getElementById("model-pitch-count-badge");

    this.currentMeta = null;
    this.isRunning = false;

    this.close();
    this.resetResults();
    this._bindEvents();
  }

  _bindEvents() {
    // Dialog close handlers
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.close());
    }
    if (this.footerCloseBtn) {
      this.footerCloseBtn.addEventListener("click", () => this.close());
    }
    if (this.modalEl) {
      this.modalEl.addEventListener("click", (e) => {
        if (e.target === this.modalEl) this.close();
      });
      this.modalEl.addEventListener("cancel", (e) => {
        e.preventDefault();
        this.close();
      });
    }

    // Esc shortcut
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) {
        this.close();
      }
    });

    // Sample selection
    if (this.sampleSelect) {
      this.sampleSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        if (val) this.loadSample(val);
      });
    }

    if (this.refreshSamplesBtn) {
      this.refreshSamplesBtn.addEventListener("click", () => this.fetchSamples());
    }

    // Bet Line Presets
    document.querySelectorAll(".btn-line-preset").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-val");
        if (this.inputLine && val) {
          this.inputLine.value = val;
          document.querySelectorAll(".btn-line-preset").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
        }
      });
    });

    if (this.inputLine) {
      this.inputLine.addEventListener("input", () => {
        const cur = this.inputLine.value;
        document.querySelectorAll(".btn-line-preset").forEach((b) => {
          b.classList.toggle("active", b.getAttribute("data-val") === cur);
        });
      });
    }

    // Odds Presets
    document.querySelectorAll(".btn-odds-preset").forEach((btn) => {
      btn.addEventListener("click", () => {
        const u = btn.getAttribute("data-under");
        const o = btn.getAttribute("data-over");
        if (this.inputUnder && u) this.inputUnder.value = u;
        if (this.inputOver && o) this.inputOver.value = o;
      });
    });

    // Run Button
    if (this.btnRun) {
      this.btnRun.addEventListener("click", () => this.executeModel());
    }
  }

  isOpen() {
    return this.modalEl && this.modalEl.open;
  }

  /**
   * Reset results and graph display back to placeholder state.
   */
  resetResults() {
    if (this.emptyState) {
      this.emptyState.style.display = "block";
    }
    if (this.contentState) {
      this.contentState.style.display = "none";
    }
    if (this.plotImg) {
      this.plotImg.src = "";
      this.plotImg.removeAttribute("src");
    }
    if (this.graphExpandBtn) {
      this.graphExpandBtn.href = "#";
    }
    if (this.whyList) {
      this.whyList.innerHTML = "";
    }
    if (this.cautionsText) {
      this.cautionsText.textContent = "";
    }
    if (this.pitchTableBody) {
      this.pitchTableBody.innerHTML = "";
    }
  }

  /**
   * Open the Data Model Modal.
   * @param {Object} [initialData] - Optional initial matchup or scrape result.
   */
  async open(initialData = null) {
    if (this.modalEl && typeof this.modalEl.showModal === "function") {
      this.modalEl.showModal();
    }

    if (initialData && initialData.filename) {
      this.resetResults();
      await this.loadSample(initialData.filename);
    } else {
      await this.fetchSamples();
      await this.fetchStatus();
    }
  }

  close() {
    if (this.modalEl && typeof this.modalEl.close === "function" && this.modalEl.open) {
      this.modalEl.close();
    }
  }

  /**
   * Populate available historical samples into dropdown.
   */
  async fetchSamples() {
    if (!this.sampleSelect) return;
    this.sampleSelect.innerHTML = '<option value="">Fetching samples...</option>';

    try {
      const samples = await api.getModelSamples();
      if (!samples || samples.length === 0) {
        this.sampleSelect.innerHTML = '<option value="">No historical matchup samples found</option>';
        return;
      }

      this.sampleSelect.innerHTML = "";
      let activeFound = false;

      samples.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.filename;
        opt.textContent = `${s.display_name}${s.is_active ? " (Active)" : ""}`;
        if (s.is_active) {
          opt.selected = true;
          activeFound = true;
        }
        this.sampleSelect.appendChild(opt);
      });

      if (!activeFound && samples.length > 0) {
        this.sampleSelect.selectedIndex = 0;
      }
    } catch (e) {
      console.warn("Could not load model samples:", e);
      this.sampleSelect.innerHTML = '<option value="">Error loading samples</option>';
    }
  }

  /**
   * Fetch current sync status and cached model results.
   */
  async fetchStatus() {
    try {
      const status = await api.getModelStatus();
      if (!status || !status.success) return;

      this.currentMeta = status.meta;
      this._renderMetaBadge(status.meta, status.has_synced_data);

      // Pre-fill stance / hand split recommendations
      if (status.meta?.recommended_model_settings) {
        const rec = status.meta.recommended_model_settings;
        if (this.selectArsenalCol && rec.arsenal_column) {
          this.selectArsenalCol.value = rec.arsenal_column;
        }
        if (this.selectBatterCol && rec.batter_column) {
          this.selectBatterCol.value = rec.batter_column;
        }
      }

      // If output exists from a prior run and has plot, render it; otherwise reset
      if (status.has_output && status.output && status.has_plot) {
        this.renderResults(status.output, status.plot_url);
      } else {
        this.resetResults();
      }
    } catch (e) {
      console.warn("Could not check model status:", e);
    }
  }

  /**
   * Load and sync a chosen previous sample.
   * Clears old results and plot so graph disappears until a new run is triggered.
   * @param {string} filename
   */
  async loadSample(filename) {
    if (!filename) return;
    this.resetResults();
    this._setRunningState(true, "Loading sample data...");

    try {
      const res = await api.loadModelSample(filename);
      this._setRunningState(false);
      this.resetResults();
      await this.fetchStatus();
      await this.fetchSamples();
    } catch (e) {
      this._setRunningState(false);
      alert(`Could not load sample:\n${e.message}`);
    }
  }

  _applyInitialContext(data) {
    if (data && data.is_matchup && data.filename) {
      if (this.sampleSelect) {
        this.sampleSelect.value = data.filename;
      }
    }
  }

  _renderMetaBadge(meta, hasSyncedData) {
    if (!this.matchupBadge || !this.syncIndicator) return;

    if (!hasSyncedData || !meta) {
      this.matchupBadge.textContent = "No Matchup Loaded";
      this.matchupBadge.className = "model-matchup-badge";
      this.syncIndicator.className = "model-sync-indicator warning";
      if (this.syncText) this.syncText.textContent = "Missing Input Data";
      return;
    }

    const pName = meta.pitcher?.name || "Pitcher";
    const pHand = meta.pitcher?.hand ? ` (${meta.pitcher.hand})` : "";
    const bName = meta.batter?.name || "Batter";
    const bStance = meta.batter?.stance ? ` (${meta.batter.stance})` : "";
    const countTag = meta.count ? ` • Count ${meta.count}` : "";
    const seasonTag = meta.season ? ` • ${meta.season}` : "";

    this.matchupBadge.textContent = `${pName}${pHand} vs ${bName}${bStance}${countTag}${seasonTag}`;
    this.matchupBadge.className = "model-matchup-badge";

    this.syncIndicator.className = "model-sync-indicator synced";
    if (this.syncText) this.syncText.textContent = "Data Ready";
  }

  /**
   * Execute model evaluation with input parameters.
   */
  async executeModel() {
    if (this.isRunning) return;

    const betLine = parseFloat(this.inputLine?.value || "95.5");
    if (isNaN(betLine) || betLine < 50 || betLine > 125) {
      alert("Please enter a valid betting velocity line (typically between 50 and 125 mph).");
      this.inputLine?.focus();
      return;
    }

    const underOdds = this.inputUnder?.value?.trim() || "-110";
    const overOdds = this.inputOver?.value?.trim() || "-110";

    const payload = {
      bet_line: betLine,
      under_odds: underOdds,
      over_odds: overOdds,
      stake: parseFloat(this.inputStake?.value || "100"),
      bankroll: parseFloat(this.inputBankroll?.value || "1000"),
      kelly_fraction: parseFloat(this.inputKelly?.value || "0.25"),
      arsenal_column: this.selectArsenalCol?.value || "Right",
      batter_column: this.selectBatterCol?.value || "Right",
      n_sims: parseInt(this.inputSims?.value || "5000", 10),
    };

    this._setRunningState(true, `Simulating 5,000 draws on ${betLine} mph...`);

    try {
      const response = await api.runDataModel(payload);
      this._setRunningState(false);
      if (response.result) {
        this.renderResults(response.result, response.plot_url);
      }
    } catch (e) {
      this._setRunningState(false);
      alert(`Model evaluation failed:\n${e.message}`);
    }
  }

  _setRunningState(running, statusMsg = "") {
    this.isRunning = running;
    if (this.btnRun) this.btnRun.disabled = running;
    if (this.statusEl) {
      this.statusEl.style.display = running ? "inline-flex" : "none";
      if (statusMsg) {
        this.statusEl.innerHTML = `<span class="spinner-sm"></span> ${statusMsg}`;
      }
    }
  }

  /**
   * Render complete model analysis results and distribution graph.
   * @param {Object} r
   * @param {string} [plotUrl]
   */
  renderResults(r, plotUrl) {
    if (!r) return;

    if (this.emptyState) this.emptyState.style.display = "none";
    if (this.contentState) this.contentState.style.display = "flex";

    const a = r.answer || {};
    const sides = r.sides || {};
    const under = sides.UNDER || {};
    const over = sides.OVER || {};
    const line = r.line?.bet_line || 95.5;

    // 1. Recommendation Banner
    if (this.recBanner && this.recHeadline && this.recRating) {
      this.recHeadline.textContent = a.headline || "MODEL EVALUATION COMPLETE";
      this.recRating.textContent = a.level || (a.bet ? "BET" : "NO BET");

      this.recBanner.className = "model-recommendation-banner";
      this.recRating.className = "rec-rating-badge";

      if (a.level === "STRONG") {
        this.recBanner.classList.add("is-strong");
        this.recRating.classList.add("strong");
      } else if (a.level === "MEDIUM") {
        this.recBanner.classList.add("is-medium");
        this.recRating.classList.add("medium");
      } else {
        this.recBanner.classList.add("is-nobet");
        this.recRating.classList.add("nobet");
      }

      if (this.recSub) {
        if (a.bet) {
          const s = sides[a.side] || {};
          this.recSub.textContent = `Model projects ${(100 * (s.win_prob || 0)).toFixed(1)}% win chance (${(100 * (s.edge || 0) >= 0 ? "+" : "") + (100 * (s.edge || 0)).toFixed(1)} pt edge over sportsbook break-even).`;
        } else {
          this.recSub.textContent = "Neither side clears the required 3.0 point edge threshold over sportsbook pricing.";
        }
      }
    }

    // 2. OVER vs UNDER Comparison Cards
    const fmtPct = (p) => `${(100 * (p || 0)).toFixed(1)}%`;
    const fmtOdds = (o) => (o > 0 ? `+${o}` : `${o}`);
    const fmtMoney = (m) => (m >= 0 ? `+$${m.toFixed(2)}` : `-$${Math.abs(m).toFixed(2)}`);

    // UNDER
    if (this.valUnderLine) this.valUnderLine.textContent = line;
    if (this.valUnderOdds) this.valUnderOdds.textContent = fmtOdds(under.odds || -110);
    if (this.valUnderWin) this.valUnderWin.textContent = fmtPct(under.win_prob);
    if (this.valUnderBe) this.valUnderBe.textContent = fmtPct(under.break_even_prob);
    if (this.meterUnderBar) this.meterUnderBar.style.width = fmtPct(under.win_prob);

    if (this.valUnderEdge) {
      const edgePts = 100 * (under.edge || 0);
      this.valUnderEdge.textContent = `${edgePts >= 0 ? "+" : ""}${edgePts.toFixed(1)} pts`;
      this.valUnderEdge.className = `val-edge ${edgePts >= 0 ? "positive" : "negative"}`;
    }
    if (this.valUnderSure) this.valUnderSure.textContent = `${(100 * (under.sure || 0)).toFixed(0)}% of sims`;
    if (this.valUnderAvg) this.valUnderAvg.textContent = `${fmtMoney(under.average_per_bet || 0)} / bet`;
    if (this.valUnderKelly) {
      this.valUnderKelly.textContent = under.suggested_bet
        ? `$${under.suggested_bet.toFixed(2)} (Kelly)`
        : "None (No edge)";
    }

    // OVER
    if (this.valOverLine) this.valOverLine.textContent = line;
    if (this.valOverOdds) this.valOverOdds.textContent = fmtOdds(over.odds || -110);
    if (this.valOverWin) this.valOverWin.textContent = fmtPct(over.win_prob);
    if (this.valOverBe) this.valOverBe.textContent = fmtPct(over.break_even_prob);
    if (this.meterOverBar) this.meterOverBar.style.width = fmtPct(over.win_prob);

    if (this.valOverEdge) {
      const edgePts = 100 * (over.edge || 0);
      this.valOverEdge.textContent = `${edgePts >= 0 ? "+" : ""}${edgePts.toFixed(1)} pts`;
      this.valOverEdge.className = `val-edge ${edgePts >= 0 ? "positive" : "negative"}`;
    }
    if (this.valOverSure) this.valOverSure.textContent = `${(100 * (over.sure || 0)).toFixed(0)}% of sims`;
    if (this.valOverAvg) this.valOverAvg.textContent = `${fmtMoney(over.average_per_bet || 0)} / bet`;
    if (this.valOverKelly) {
      this.valOverKelly.textContent = over.suggested_bet
        ? `$${over.suggested_bet.toFixed(2)} (Kelly)`
        : "None (No edge)";
    }

    // Highlight recommended card
    const cardUnder = document.getElementById("card-side-under");
    const cardOver = document.getElementById("card-side-over");
    if (cardUnder) cardUnder.classList.toggle("recommended", a.bet && a.side === "UNDER");
    if (cardOver) cardOver.classList.toggle("recommended", a.bet && a.side === "OVER");

    // 3. Distribution Graph
    if (this.plotImg) {
      const finalPlotUrl = plotUrl || `/api/model/plot?t=${Date.now()}`;
      this.plotImg.src = finalPlotUrl;
      if (this.graphExpandBtn) this.graphExpandBtn.href = finalPlotUrl;
    }

    // 4. Why & Cautions
    if (this.whyList) {
      this.whyList.innerHTML = "";
      const whyItems = r.why || [];
      whyItems.forEach((w) => {
        const li = document.createElement("li");
        li.className = "why-item";
        let signCls = "star";
        if (w.sign === "+") signCls = "plus";
        else if (w.sign === "-") signCls = "minus";
        else if (w.sign === "!") signCls = "warn";

        li.innerHTML = `
          <span class="why-sign ${signCls}">${w.sign}</span>
          <span class="why-text">${w.text}</span>
        `;
        this.whyList.appendChild(li);
      });
    }

    if (this.cautionsText) {
      const cautions = r.cautions || [];
      const warnings = r.warnings || [];
      const combined = [...cautions, ...warnings.map((w) => `Note: ${w}`)];
      this.cautionsText.textContent = combined.join(" ") || "Standard model assumptions apply.";
    }

    // 5. Pitch Breakdown Table
    if (this.pitchTableBody) {
      this.pitchTableBody.innerHTML = "";
      const pitchTypes = r.details?.pitch_types || [];
      if (this.pitchCountBadge) {
        this.pitchCountBadge.textContent = `${pitchTypes.length} pitch types`;
      }

      pitchTypes.forEach((pt) => {
        const tr = document.createElement("tr");
        const fPct = (val) => (val !== null && val !== undefined ? `${(100 * val).toFixed(1)}%` : "-");
        const fMph = (val) => (val !== null && val !== undefined ? `${val.toFixed(1)} mph` : "-");

        tr.innerHTML = `
          <td><strong>${pt.name}</strong></td>
          <td>${fPct(pt.pct_arsenal)}</td>
          <td>${fPct(pt.pct_batter)}</td>
          <td>${fPct(pt.pct_matchup)}</td>
          <td><strong>${fPct(pt.pct_used)}</strong></td>
          <td>${fMph(pt.mph_arsenal)}</td>
          <td>${fMph(pt.mph_matchup)}</td>
          <td><strong>${fMph(pt.mph_used)}</strong></td>
          <td style="color: ${pt.p_over_line > 0.5 ? "#38bdf8" : "#cbd5e1"}; font-weight: 600;">
            ${fPct(pt.p_over_line)}
          </td>
        `;
        this.pitchTableBody.appendChild(tr);
      });
    }
  }
}
