/**
 * Wizard Controller: Manages sequential input box progression, validation,
 * smooth step transitions, and triggering Statcast scraping.
 */

import { api } from "./api.js?v=2";

export class WizardController {
  /**
   * @param {Object} options
   * @param {import("./recent.js").RecentSearchesController} options.recentController
   * @param {import("./modal.js").CSVModalController} options.modalController
   */
  constructor({ recentController, modalController }) {
    this.recentController = recentController;
    this.modalController = modalController;

    this.searchMode = "pitcher"; // 'pitcher' | 'batter'
    this.currentStep = 1;
    this.totalSteps = 6;

    // Form state
    this.state = {
      pitcher_name: "",
      pitcher_id: null,
      pitcher_hand: "both",
      batter_name: "",
      batter_id: null,
      batter_stance: "both",
      count: "",
      season: 2026,
    };

    this.loadingOverlay = document.getElementById("loading-overlay");
    this.loadingTitle = document.getElementById("loading-title");
    this.loadingDesc = document.getElementById("loading-desc");

    this._bindElements();
    this._bindEvents();
    this.updateUI();
  }

  _bindElements() {
    this.modeTabPitcher = document.getElementById("mode-tab-pitcher");
    this.modeTabBatter = document.getElementById("mode-tab-batter");

    // Pitcher Mode Elements
    this.inputPitcherName = document.getElementById("input-pitcher-name");
    this.feedbackPitcher = document.getElementById("feedback-pitcher");
    this.inputPitcherHand = document.getElementById("input-pitcher-hand");
    this.inputBatterName = document.getElementById("input-batter-name");
    this.feedbackBatter = document.getElementById("feedback-batter");
    this.inputBatterStance = document.getElementById("input-batter-stance");
    this.inputCount = document.getElementById("input-count");
    this.feedbackCount = document.getElementById("feedback-count");
    this.inputSeason = document.getElementById("input-season");

    // Batter Mode Elements
    this.inputBatterNameB = document.getElementById("input-batter-name-bmode");
    this.feedbackBatterB = document.getElementById("feedback-batter-bmode");
    this.inputBatterStanceB = document.getElementById("input-batter-stance-bmode");
    this.inputPitcherNameB = document.getElementById("input-pitcher-name-bmode");
    this.feedbackPitcherB = document.getElementById("feedback-pitcher-bmode");
    this.inputPitcherHandB = document.getElementById("input-pitcher-hand-bmode");
    this.inputCountB = document.getElementById("input-count-bmode");
    this.feedbackCountB = document.getElementById("feedback-count-bmode");
    this.inputSeasonB = document.getElementById("input-season-bmode");

    // Buttons
    this.btnPrev = document.getElementById("btn-prev");
    this.btnNext = document.getElementById("btn-next");
    this.btnSkip = document.getElementById("btn-skip");
  }

  _bindEvents() {
    // Mode switcher
    if (this.modeTabPitcher) {
      this.modeTabPitcher.addEventListener("click", () => this.setMode("pitcher"));
    }
    if (this.modeTabBatter) {
      this.modeTabBatter.addEventListener("click", () => this.setMode("batter"));
    }

    // Navigation buttons
    if (this.btnPrev) {
      this.btnPrev.addEventListener("click", () => this.prevStep());
    }
    if (this.btnNext) {
      this.btnNext.addEventListener("click", () => this.submitCurrentStep());
    }
    if (this.btnSkip) {
      this.btnSkip.addEventListener("click", () => this.skipCurrentStep());
    }

    // Keyboard 'Enter' key advances to next step immediately across all inputs
    const allInputs = [
      this.inputPitcherName,
      this.inputPitcherHand,
      this.inputBatterName,
      this.inputBatterStance,
      this.inputCount,
      this.inputSeason,
      this.inputBatterNameB,
      this.inputBatterStanceB,
      this.inputPitcherNameB,
      this.inputPitcherHandB,
      this.inputCountB,
      this.inputSeasonB,
    ];

    allInputs.forEach((inp) => {
      if (inp) {
        inp.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            this.submitCurrentStep();
          }
        });
      }
    });

    // Clear error feedback on input
    if (this.inputCount) {
      this.inputCount.addEventListener("input", () => {
        this._clearFeedback(this.feedbackCount);
        this.inputCount.classList.remove("input-error");
      });
    }
    if (this.inputCountB) {
      this.inputCountB.addEventListener("input", () => {
        this._clearFeedback(this.feedbackCountB);
        this.inputCountB.classList.remove("input-error");
      });
    }

    // Quick Option Chips
    document.querySelectorAll(".chip-btn").forEach((chip) => {
      chip.addEventListener("click", (e) => {
        const targetId = chip.getAttribute("data-target");
        const val = chip.getAttribute("data-value");
        const input = document.getElementById(targetId);
        if (input) {
          input.value = val;
          input.classList.remove("input-error");
          if (targetId === "input-count") this._clearFeedback(this.feedbackCount);
          if (targetId === "input-count-bmode") this._clearFeedback(this.feedbackCountB);
          // Highlight active chip in this group
          const parent = chip.closest(".options-chips");
          if (parent) {
            parent.querySelectorAll(".chip-btn").forEach((c) => c.classList.remove("active"));
            chip.classList.add("active");
          }
          // Fast-advance when chip is clicked
          this.submitCurrentStep();
        }
      });
    });

    // Step Nodes click to jump back
    document.querySelectorAll(".step-node").forEach((node) => {
      node.addEventListener("click", () => {
        const stepNum = parseInt(node.getAttribute("data-step"), 10);
        if (stepNum < this.currentStep) {
          this.goToStep(stepNum);
        }
      });
    });
  }

  setMode(mode) {
    if (this.searchMode === mode) return;
    this.searchMode = mode;
    this.currentStep = 1;

    // Reset mode tabs
    if (this.modeTabPitcher && this.modeTabBatter) {
      if (mode === "pitcher") {
        this.modeTabPitcher.classList.add("active");
        this.modeTabBatter.classList.remove("active");
      } else {
        this.modeTabBatter.classList.add("active");
        this.modeTabPitcher.classList.remove("active");
      }
    }

    this.updateUI();
  }

  goToStep(step) {
    if (step < 1 || step > this.totalSteps) return;
    this.currentStep = step;
    this.updateUI();
  }

  prevStep() {
    if (this.currentStep > 1) {
      this.goToStep(this.currentStep - 1);
    }
  }

  skipCurrentStep() {
    if (this.currentStep === 3) {
      if (this.searchMode === "pitcher") {
        this.state.batter_name = "";
        this.state.batter_id = null;
        if (this.inputBatterName) this.inputBatterName.value = "";
      } else {
        this.state.pitcher_name = "";
        this.state.pitcher_id = null;
        if (this.inputPitcherNameB) this.inputPitcherNameB.value = "";
      }
      this.goToStep(4);
    } else if (this.currentStep === 5) {
      this.state.count = "";
      if (this.inputCount) {
        this.inputCount.value = "";
        this.inputCount.classList.remove("input-error");
      }
      if (this.inputCountB) {
        this.inputCountB.value = "";
        this.inputCountB.classList.remove("input-error");
      }
      this._clearFeedback(this.feedbackCount);
      this._clearFeedback(this.feedbackCountB);
      this.goToStep(6);
    }
  }

  _validateAndNormalizeCount(rawCount) {
    if (!rawCount) {
      return { valid: true, count: "" };
    }
    const cleaned = rawCount.trim().toLowerCase();
    if (!cleaned || ["all", "any", "none", "overall", "null"].includes(cleaned)) {
      return { valid: true, count: "" };
    }
    const aliases = {
      "full": "3-2",
      "full count": "3-2",
      "fullcount": "3-2",
    };
    if (aliases[cleaned]) {
      return { valid: true, count: aliases[cleaned] };
    }
    const match = cleaned.match(/^([0-9])\s*[-–—,/:\s]?\s*([0-9])$/);
    if (match) {
      const balls = parseInt(match[1], 10);
      const strikes = parseInt(match[2], 10);
      if (balls >= 0 && balls <= 3 && strikes >= 0 && strikes <= 2) {
        return { valid: true, count: `${balls}-${strikes}` };
      }
      return {
        valid: false,
        error: `Invalid count '${rawCount}': Balls must be 0–3 and Strikes must be 0–2 (e.g. 0-0, 2-1, 3-2).`,
      };
    }
    return {
      valid: false,
      error: `Invalid count format '${rawCount}'. Please enter a valid count (e.g. 0-0, 2-1, 3-2) or leave blank for all counts.`,
    };
  }

  async submitCurrentStep() {
    if (this.searchMode === "pitcher") {
      await this._handlePitcherModeStep();
    } else {
      await this._handleBatterModeStep();
    }
  }

  /* ---------------- Pitcher Mode Steps ---------------- */
  async _handlePitcherModeStep() {
    switch (this.currentStep) {
      case 1: {
        // Step 1: Pitcher Name
        const name = (this.inputPitcherName.value || "").trim();
        if (!name) {
          this._showFeedback(this.feedbackPitcher, "Pitcher name is required.", "error");
          this.inputPitcherName.focus();
          return;
        }

        this._showFeedback(this.feedbackPitcher, "Searching MLB registry...", "info");
        try {
          const results = await api.searchPlayer(name, "pitcher");
          if (!results || results.length === 0) {
            this._showFeedback(
              this.feedbackPitcher,
              `No pitcher found matching '${name}'. Please check the spelling.`,
              "error"
            );
            return;
          }
          const player = results[0];
          this.state.pitcher_name = player.full_name;
          this.state.pitcher_id = player.id;
          this.state.pitcher_hand = player.pitch_hand ? player.pitch_hand.toUpperCase() : "both";

          // Auto-fill hand in step 2
          if (this.inputPitcherHand) {
            this.inputPitcherHand.value = this.state.pitcher_hand;
          }

          this._showFeedback(
            this.feedbackPitcher,
            `✓ Found: ${player.full_name} (${player.primary_position || "P"}, Throws: ${player.pitch_hand || "N/A"})`,
            "success"
          );

          // Change to next text box after short delay for user feedback
          setTimeout(() => {
            this.goToStep(2);
          }, 350);
        } catch (e) {
          this._showFeedback(this.feedbackPitcher, `Search error: ${e.message}`, "error");
        }
        break;
      }

      case 2: {
        // Step 2: Pitcher Hand
        let hand = (this.inputPitcherHand.value || "").trim().toUpperCase();
        if (!["L", "R", "BOTH"].includes(hand)) {
          hand = "BOTH";
        }
        this.state.pitcher_hand = hand === "BOTH" ? "both" : hand;
        this.goToStep(3);
        break;
      }

      case 3: {
        // Step 3: Batter Name (Optional)
        const bName = (this.inputBatterName.value || "").trim();
        if (!bName) {
          this.state.batter_name = "";
          this.state.batter_id = null;
          this.goToStep(4);
          return;
        }

        this._showFeedback(this.feedbackBatter, "Searching MLB registry for batter...", "info");
        try {
          const results = await api.searchPlayer(bName, "batter");
          if (!results || results.length === 0) {
            this._showFeedback(
              this.feedbackBatter,
              `No batter found matching '${bName}'. (Leave blank to search all batters)`,
              "error"
            );
            return;
          }
          const batter = results[0];
          this.state.batter_name = batter.full_name;
          this.state.batter_id = batter.id;
          if (batter.bat_side) {
            const side = batter.bat_side.toLowerCase() === "l" ? "Left" : "Right";
            this.state.batter_stance = side.toLowerCase();
            if (this.inputBatterStance) {
              this.inputBatterStance.value = side;
            }
          }

          this._showFeedback(
            this.feedbackBatter,
            `✓ Found: ${batter.full_name} (Bats: ${batter.bat_side || "N/A"})`,
            "success"
          );

          setTimeout(() => {
            this.goToStep(4);
          }, 350);
        } catch (e) {
          this._showFeedback(this.feedbackBatter, `Search error: ${e.message}`, "error");
        }
        break;
      }

      case 4: {
        // Step 4: Batter Stance
        let rawStance = (this.inputBatterStance.value || "").trim();
        let stance = rawStance.toLowerCase();
        if (!["left", "right", "both"].includes(stance)) {
          stance = "both";
        }
        const formattedStance = stance.charAt(0).toUpperCase() + stance.slice(1);
        if (this.inputBatterStance) {
          this.inputBatterStance.value = formattedStance;
        }
        this.state.batter_stance = stance;
        this.goToStep(5);
        break;
      }

      case 5: {
        // Step 5: Count Filter (Optional)
        const rawCount = (this.inputCount ? this.inputCount.value : "").trim();
        const check = this._validateAndNormalizeCount(rawCount);
        if (!check.valid) {
          this._showFeedback(this.feedbackCount, check.error, "error");
          if (this.inputCount) {
            this.inputCount.classList.add("input-error");
            this.inputCount.focus();
            setTimeout(() => this.inputCount.classList.remove("input-error"), 500);
          }
          return;
        }
        this._clearFeedback(this.feedbackCount);
        this.state.count = check.count;
        this.goToStep(6);
        break;
      }

      case 6: {
        // Step 6: Season Year & Execute!
        const rawYear = (this.inputSeason.value || "").trim();
        const year = parseInt(rawYear, 10) || 2026;
        if (year < 2008 || year > 2026) {
          alert("Season must be between 2008 and 2026 (Statcast era).");
          return;
        }
        this.state.season = year;
        await this._executeScrape();
        break;
      }
    }
  }

  /* ---------------- Batter Mode Steps ---------------- */
  async _handleBatterModeStep() {
    switch (this.currentStep) {
      case 1: {
        // Step 1: Batter Name
        const name = (this.inputBatterNameB.value || "").trim();
        if (!name) {
          this._showFeedback(this.feedbackBatterB, "Batter name is required.", "error");
          this.inputBatterNameB.focus();
          return;
        }

        this._showFeedback(this.feedbackBatterB, "Searching MLB registry...", "info");
        try {
          const results = await api.searchPlayer(name, "batter");
          if (!results || results.length === 0) {
            this._showFeedback(
              this.feedbackBatterB,
              `No batter found matching '${name}'. Please check the spelling.`,
              "error"
            );
            return;
          }
          const player = results[0];
          this.state.batter_name = player.full_name;
          this.state.batter_id = player.id;
          const side = player.bat_side && player.bat_side.toUpperCase() === "L" ? "Left" : "Right";
          this.state.batter_stance = side.toLowerCase();

          if (this.inputBatterStanceB) {
            this.inputBatterStanceB.value = side;
          }

          this._showFeedback(
            this.feedbackBatterB,
            `✓ Found: ${player.full_name} (${player.primary_position || "B"}, Bats: ${player.bat_side || "N/A"})`,
            "success"
          );

          setTimeout(() => {
            this.goToStep(2);
          }, 350);
        } catch (e) {
          this._showFeedback(this.feedbackBatterB, `Search error: ${e.message}`, "error");
        }
        break;
      }

      case 2: {
        // Step 2: Batter Stance
        let rawStance = (this.inputBatterStanceB.value || "").trim();
        let stance = rawStance.toLowerCase();
        if (!["left", "right", "both"].includes(stance)) {
          stance = "both";
        }
        const formattedStance = stance.charAt(0).toUpperCase() + stance.slice(1);
        if (this.inputBatterStanceB) {
          this.inputBatterStanceB.value = formattedStance;
        }
        this.state.batter_stance = stance;
        this.goToStep(3);
        break;
      }

      case 3: {
        // Step 3: Pitcher Name (Optional)
        const pName = (this.inputPitcherNameB.value || "").trim();
        if (!pName) {
          this.state.pitcher_name = "";
          this.state.pitcher_id = null;
          this.goToStep(4);
          return;
        }

        this._showFeedback(this.feedbackPitcherB, "Searching MLB registry for pitcher...", "info");
        try {
          const results = await api.searchPlayer(pName, "pitcher");
          if (!results || results.length === 0) {
            this._showFeedback(
              this.feedbackPitcherB,
              `No pitcher found matching '${pName}'. (Leave blank to query against all pitchers)`,
              "error"
            );
            return;
          }
          const pitcher = results[0];
          this.state.pitcher_name = pitcher.full_name;
          this.state.pitcher_id = pitcher.id;
          if (pitcher.pitch_hand) {
            this.state.pitcher_hand = pitcher.pitch_hand.toUpperCase();
            if (this.inputPitcherHandB) {
              this.inputPitcherHandB.value = this.state.pitcher_hand;
            }
          }

          this._showFeedback(
            this.feedbackPitcherB,
            `✓ Found: ${pitcher.full_name} (Throws: ${pitcher.pitch_hand || "N/A"})`,
            "success"
          );

          setTimeout(() => {
            this.goToStep(4);
          }, 350);
        } catch (e) {
          this._showFeedback(this.feedbackPitcherB, `Search error: ${e.message}`, "error");
        }
        break;
      }

      case 4: {
        // Step 4: Pitcher Throwing Hand
        let hand = (this.inputPitcherHandB.value || "").trim().toUpperCase();
        if (!["L", "R", "BOTH"].includes(hand)) {
          hand = "BOTH";
        }
        this.state.pitcher_hand = hand === "BOTH" ? "both" : hand;
        this.goToStep(5);
        break;
      }

      case 5: {
        // Step 5: Count Filter (Optional)
        const rawCount = (this.inputCountB ? this.inputCountB.value : "").trim();
        const check = this._validateAndNormalizeCount(rawCount);
        if (!check.valid) {
          this._showFeedback(this.feedbackCountB, check.error, "error");
          if (this.inputCountB) {
            this.inputCountB.classList.add("input-error");
            this.inputCountB.focus();
            setTimeout(() => this.inputCountB.classList.remove("input-error"), 500);
          }
          return;
        }
        this._clearFeedback(this.feedbackCountB);
        this.state.count = check.count;
        this.goToStep(6);
        break;
      }

      case 6: {
        // Step 6: Season Year & Execute!
        const rawYear = (this.inputSeasonB.value || "").trim();
        const year = parseInt(rawYear, 10) || 2026;
        if (year < 2008 || year > 2026) {
          alert("Season must be between 2008 and 2026 (Statcast era).");
          return;
        }
        this.state.season = year;
        await this._executeScrape();
        break;
      }
    }
  }

  /* ---------------- Scraper Execution ---------------- */
  async _executeScrape() {
    this._showLoading(true);

    const payload = {
      search_mode: this.searchMode,
      pitcher_name: this.state.pitcher_name,
      pitcher_hand: this.state.pitcher_hand,
      batter_name: this.state.batter_name,
      batter_stance: this.state.batter_stance,
      count: this.state.count || null,
      season: this.state.season,
    };

    try {
      const response = await api.runScrape(payload);
      this._showLoading(false);

      // Refresh recent searches list
      await this.recentController.loadRecent();

      // Automatically pop out the screen reading out the data from the CSV!
      this.modalController.open(response);

      // Reset to step 1 for subsequent searches
      this.goToStep(1);
    } catch (e) {
      this._showLoading(false);
      alert(`Scraper execution error:\n${e.message}`);
    }
  }

  _showLoading(show) {
    if (this.loadingOverlay) {
      if (show) {
        this.loadingOverlay.classList.add("active");
        const target = this.searchMode === "pitcher" ? this.state.pitcher_name : this.state.batter_name;
        this.loadingTitle.textContent = `Scraping Statcast Data for ${target}...`;
        this.loadingDesc.textContent = "Fetching pitch arsenal breakdown and calculating metrics...";
      } else {
        this.loadingOverlay.classList.remove("active");
      }
    }
  }

  _showFeedback(el, message, type) {
    if (!el) return;
    el.className = `player-feedback ${type}`;
    el.textContent = message;
    el.style.display = "flex";
  }

  _clearFeedback(el) {
    if (!el) return;
    el.className = "player-feedback";
    el.textContent = "";
    el.style.display = "none";
  }

  /**
   * Update the UI state, transitions between input boxes, buttons, and badges.
   */
  updateUI() {
    // 1. Update step nodes (1 to 6)
    document.querySelectorAll(".step-node").forEach((node) => {
      const stepNum = parseInt(node.getAttribute("data-step"), 10);
      node.classList.remove("active", "completed");
      if (stepNum === this.currentStep) {
        node.classList.add("active");
      } else if (stepNum < this.currentStep) {
        node.classList.add("completed");
      }
    });

    // 2. Hide all step views and activate the current step view
    document.querySelectorAll(".step-view").forEach((view) => {
      view.classList.remove("active");
    });

    const activeViewId = `step-view-${this.searchMode}-${this.currentStep}`;
    const activeView = document.getElementById(activeViewId);
    if (activeView) {
      activeView.classList.add("active");

      // Auto focus the input inside the active view
      const activeInput = activeView.querySelector(".input-box");
      if (activeInput) {
        setTimeout(() => activeInput.focus(), 100);
      }
    }

    // 3. Update Prev / Next / Skip button states
    if (this.btnPrev) {
      this.btnPrev.disabled = this.currentStep === 1;
    }

    if (this.btnNext) {
      if (this.currentStep === this.totalSteps) {
        this.btnNext.innerHTML = 'Run Statcast Scrape 🚀';
      } else {
        this.btnNext.innerHTML = 'Next ➔';
      }
    }

    // Step 3 (matchup) and Step 5 (count) are optional
    if (this.btnSkip) {
      if (this.currentStep === 3) {
        this.btnSkip.textContent = "Skip (All Players) ➔";
        this.btnSkip.style.display = "inline-block";
      } else if (this.currentStep === 5) {
        this.btnSkip.textContent = "Skip (All Counts) ➔";
        this.btnSkip.style.display = "inline-block";
      } else {
        this.btnSkip.style.display = "none";
      }
    }
  }
}
