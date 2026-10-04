/**
 * Recent Searches Dropdown controller.
 * Manages the top-right dropdown, red square thumbnails, and hyperlink re-access to CSV data.
 */

import { api } from "./api.js?v=2";

export class RecentSearchesController {
  /**
   * @param {Object} options
   * @param {import("./modal.js").CSVModalController} options.modalController
   * @param {import("./data_model.js").DataModelController} [options.dataModelController]
   */
  constructor({ modalController, dataModelController = null }) {
    this.modalController = modalController;
    this.dataModelController = dataModelController;

    this.containerEl = document.getElementById("recent-dropdown-container");
    this.triggerBtn = document.getElementById("recent-dropdown-trigger");
    this.badgeEl = document.getElementById("recent-count-badge");
    this.listEl = document.getElementById("recent-items-list");
    this.clearBtn = document.getElementById("recent-clear-btn");

    this._bindEvents();
    this.loadRecent();
  }

  _bindEvents() {
    if (this.triggerBtn) {
      this.triggerBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggle();
      });
    }

    // Close dropdown on outside click
    document.addEventListener("click", (e) => {
      if (this.containerEl && !this.containerEl.contains(e.target)) {
        this.close();
      }
    });

    if (this.clearBtn) {
      this.clearBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm("Clear all recent searches and generated CSV files?")) {
          await api.clearOutput();
          this.loadRecent();
        }
      });
    }
  }

  toggle() {
    if (this.containerEl) {
      this.containerEl.classList.toggle("open");
    }
  }

  open() {
    if (this.containerEl) {
      this.containerEl.classList.add("open");
    }
  }

  close() {
    if (this.containerEl) {
      this.containerEl.classList.remove("open");
    }
  }

  /**
   * Fetch and render recent searches.
   */
  async loadRecent() {
    try {
      const items = await api.getRecentSearches();
      this.render(items);
    } catch (e) {
      console.warn("Could not load recent searches:", e);
    }
  }

  /**
   * Extract initials for display inside thumbnail fallback.
   * @param {string} name
   */
  _getInitials(name) {
    if (!name) return "MLB";
    const words = name.replace(/[()]/g, "").split(/\s+/).filter(Boolean);
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  }

  /**
   * Build HTML for thumbnail:
   * - Single player: 44x44 square with official headshot (or initials fallback).
   * - H2H matchup: 44x44 square merging both headshots with a diagonal line cut.
   * @param {Object} item
   * @returns {string}
   */
  _renderThumbnailHtml(item) {
    const isMatchup = Boolean(item.is_matchup || (item.filename && item.filename.includes("_vs_")));
    const fullTitle = item.query_name || item.display_name || "Recent Search";

    if (isMatchup) {
      // Resolve Player 1 (Top-Left)
      const p1Raw = item.player1_name || (fullTitle.includes(" vs ") ? fullTitle.split(" vs ")[0] : "Player 1");
      const p1Name = p1Raw.replace(/[()]/g, "").trim();
      const p1Initials = this._getInitials(p1Name);
      const p1Headshot = item.player1_headshot_url || (item.player1_id ? `https://content.mlb.com/images/headshots/current/60x60/${item.player1_id}@3x.png` : null);

      // Resolve Player 2 (Bottom-Right)
      let p2Raw = item.player2_name;
      if (!p2Raw && fullTitle.includes(" vs ")) {
        const afterVs = fullTitle.split(" vs ")[1] || "";
        p2Raw = afterVs.split("[")[0].split("(")[0].trim();
      }
      const p2Name = (p2Raw || "Player 2").replace(/[()]/g, "").trim();
      const p2Initials = this._getInitials(p2Name);
      const p2Headshot = item.player2_headshot_url || (item.player2_id ? `https://content.mlb.com/images/headshots/current/60x60/${item.player2_id}@3x.png` : null);

      const p1ImgHtml = p1Headshot
        ? `<img src="${p1Headshot}" alt="${p1Name}" style="position: absolute; width: 135%; height: 135%; max-width: none; max-height: none; left: -24%; top: -10%; object-fit: cover; object-position: center 12%; display: block;" loading="lazy" onerror="this.style.display='none'; const el = this.parentElement.querySelector('.h2h-half-initials-p1'); if (el) el.style.display='block';" /><span class="h2h-half-initials-p1" style="display:none;">${p1Initials}</span>`
        : `<span class="h2h-half-initials-p1">${p1Initials}</span>`;

      const p2ImgHtml = p2Headshot
        ? `<img src="${p2Headshot}" alt="${p2Name}" style="position: absolute; width: 135%; height: 135%; max-width: none; max-height: none; left: -8%; top: 18%; object-fit: cover; object-position: center 12%; display: block;" loading="lazy" onerror="this.style.display='none'; const el = this.parentElement.querySelector('.h2h-half-initials-p2'); if (el) el.style.display='block';" /><span class="h2h-half-initials-p2" style="display:none;">${p2Initials}</span>`
        : `<span class="h2h-half-initials-p2">${p2Initials}</span>`;

      return `
        <div class="thumbnail-square thumbnail-red-square thumbnail-h2h" style="width: 40px; height: 40px; min-width: 40px; max-width: 40px; max-height: 40px; overflow: hidden; border-radius: 6px; position: relative; flex-shrink: 0;" title="${fullTitle} (${p1Name} vs ${p2Name})">
          <div class="h2h-half-p1" title="${p1Name}">
            ${p1ImgHtml}
          </div>
          <div class="h2h-half-p2" title="${p2Name}">
            ${p2ImgHtml}
          </div>
          <svg class="h2h-diagonal-svg" viewBox="0 0 40 40" preserveAspectRatio="none" aria-hidden="true">
            <line x1="40" y1="0" x2="0" y2="40" />
          </svg>
        </div>
      `;
    }

    // Single Player
    const playerName = item.player_name || fullTitle;
    const initials = this._getInitials(playerName);
    const headshotUrl = item.headshot_url || (item.player_id ? `https://content.mlb.com/images/headshots/current/60x60/${item.player_id}@3x.png` : null);

    if (headshotUrl) {
      return `
        <div class="thumbnail-square thumbnail-red-square thumbnail-single" style="width: 40px; height: 40px; min-width: 40px; max-width: 40px; max-height: 40px; overflow: hidden; border-radius: 6px; flex-shrink: 0;" title="${fullTitle}">
          <img src="${headshotUrl}" alt="${playerName}" class="thumbnail-headshot-img" style="width: 100%; height: 100%; max-width: 40px; max-height: 40px; object-fit: cover; object-position: center 12%; display: block;" loading="lazy" onerror="this.style.display='none'; const el = this.parentElement.querySelector('.thumbnail-initials'); if (el) el.style.display='block';" />
          <span class="thumbnail-initials" style="display:none;">${initials}</span>
        </div>
      `;
    }

    return `
      <div class="thumbnail-square thumbnail-red-square thumbnail-single" style="width: 40px; height: 40px; min-width: 40px; max-width: 40px; max-height: 40px; overflow: hidden; border-radius: 6px; flex-shrink: 0;" title="${fullTitle}">
        <span class="thumbnail-initials">${initials}</span>
      </div>
    `;
  }

  /**
   * Render list of recent items.
   * @param {Array} items
   */
  render(items) {
    if (!this.listEl) return;

    if (this.badgeEl) {
      this.badgeEl.textContent = items.length;
    }

    if (!items || items.length === 0) {
      this.listEl.innerHTML = `
        <li class="dropdown-empty">
          No recent searches yet.<br>Complete a search to see it here!
        </li>
      `;
      return;
    }

    this.listEl.innerHTML = "";

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "recent-item";

      const isMatchup = item.is_matchup || (item.filename && item.filename.includes("_vs_"));
      const modelBtnHtml = isMatchup
        ? `<button class="btn-recent-model-direct" type="button" title="Evaluate velocity betting model for this matchup">🎯 Model</button>`
        : "";

      const thumbnailHtml = this._renderThumbnailHtml(item);

      li.innerHTML = `
        ${thumbnailHtml}
        <div class="recent-item-info">
          <div class="recent-item-title-row">
            <a href="#" class="recent-item-link" title="Click to view CSV data">
              ${item.query_name || item.display_name}
            </a>
            ${modelBtnHtml}
          </div>
          <span class="recent-item-meta">
            <span>${item.rows_count ? `${item.rows_count} pitch types` : "CSV Export"}</span>
            ${item.season ? `<span>• Season ${item.season}</span>` : ""}
          </span>
        </div>
      `;

      // Hyperlink click pops out the CSV data viewer
      const link = li.querySelector(".recent-item-link");
      link.addEventListener("click", async (e) => {
        e.preventDefault();
        try {
          const csvData = await api.getCSVData(item.filename);
          this.modalController.open(csvData);
          this.close();
        } catch (err) {
          alert(`Could not open CSV file: ${err.message}`);
        }
      });

      // Direct model button click
      const modelDirectBtn = li.querySelector(".btn-recent-model-direct");
      if (modelDirectBtn) {
        modelDirectBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          e.preventDefault();
          this.close();
          if (this.dataModelController) {
            await this.dataModelController.loadSample(item.filename);
            this.dataModelController.open({ is_matchup: true, filename: item.filename });
          }
        });
      }

      this.listEl.appendChild(li);
    });
  }
}
