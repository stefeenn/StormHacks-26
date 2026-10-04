/**
 * Recent Searches Dropdown controller.
 * Manages the top-right dropdown, red square thumbnails, and hyperlink re-access to CSV data.
 */

import { api } from "./api.js";

export class RecentSearchesController {
  /**
   * @param {Object} options
   * @param {import("./modal.js").CSVModalController} options.modalController
   */
  constructor({ modalController }) {
    this.modalController = modalController;

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
   * Extract initials for display inside the red square thumbnail.
   * @param {string} name
   */
  _getInitials(name) {
    if (!name) return "MLB";
    const words = name.replace(/[()]/g, "").split(/\s+/).filter(Boolean);
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
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

      const initials = this._getInitials(item.query_name || item.display_name);

      // Red square thumbnail as requested:
      // "a small thumbnail (lets keep it to a red square for the moment, it will be replaced) with the name of the pitcher/batter search on top of it should be visible for each recent query. the text is a hyperlink so that when you click on it it can pop out a screen reading out the data from the csv, and essentially re-access the generated file."
      li.innerHTML = `
        <div class="thumbnail-red-square" title="Placeholder thumbnail for ${item.query_name || item.display_name}">
          <span class="thumbnail-initials">${initials}</span>
        </div>
        <div class="recent-item-info">
          <a href="#" class="recent-item-link" title="Click to view CSV data">
            ${item.query_name || item.display_name}
          </a>
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

      this.listEl.appendChild(li);
    });
  }
}
