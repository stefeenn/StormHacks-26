/**
 * Pop-out Modal controller for displaying CSV data.
 * Supports both single-view and 3-column head-to-head matchup view:
 * [Left: Player 1 individual stats] [Center: Head-to-Head stats] [Right: Player 2 individual stats]
 */

export class CSVModalController {
  constructor() {
    this.modalEl = document.getElementById("csv-modal");
    this.titleEl = document.getElementById("modal-query-title");
    this.filenameEl = document.getElementById("modal-file-name");
    this.filterInputEl = document.getElementById("modal-filter-input");
    this.rowCountEl = document.getElementById("modal-row-count");
    this.closeBtn = document.getElementById("modal-close-btn");
    this.footerCloseBtn = document.getElementById("modal-footer-close-btn");
    this.downloadBtn = document.getElementById("modal-download-btn");

    // Single-view elements
    this.singleViewEl = document.getElementById("modal-single-view");
    this.tableHeaderEl = document.getElementById("modal-table-headers");
    this.tableBodyEl = document.getElementById("modal-table-body");

    // Matchup 3-column elements
    this.matchupViewEl = document.getElementById("modal-matchup-view");
    // Left column
    this.leftBadgeEl = document.getElementById("matchup-badge-left");
    this.leftTitleEl = document.getElementById("matchup-title-left");
    this.leftMetaEl = document.getElementById("matchup-meta-left");
    this.leftHeadersEl = document.getElementById("matchup-headers-left");
    this.leftBodyEl = document.getElementById("matchup-body-left");
    this.leftCountEl = document.getElementById("matchup-count-left");
    this.leftDownloadBtn = document.getElementById("matchup-download-left");
    // Center column
    this.centerBadgeEl = document.getElementById("matchup-badge-center");
    this.centerTitleEl = document.getElementById("matchup-title-center");
    this.centerMetaEl = document.getElementById("matchup-meta-center");
    this.centerHeadersEl = document.getElementById("matchup-headers-center");
    this.centerBodyEl = document.getElementById("matchup-body-center");
    this.centerCountEl = document.getElementById("matchup-count-center");
    this.centerDownloadBtn = document.getElementById("matchup-download-center");
    // Right column
    this.rightBadgeEl = document.getElementById("matchup-badge-right");
    this.rightTitleEl = document.getElementById("matchup-title-right");
    this.rightMetaEl = document.getElementById("matchup-meta-right");
    this.rightHeadersEl = document.getElementById("matchup-headers-right");
    this.rightBodyEl = document.getElementById("matchup-body-right");
    this.rightCountEl = document.getElementById("matchup-count-right");
    this.rightDownloadBtn = document.getElementById("matchup-download-right");

    this.currentData = null;
    this.filteredRows = [];

    // Ensure dialog starts strictly closed
    this.close();
    this._bindEvents();
  }

  _bindEvents() {
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", (e) => {
        e.preventDefault();
        this.close();
      });
    }
    if (this.footerCloseBtn) {
      this.footerCloseBtn.addEventListener("click", (e) => {
        e.preventDefault();
        this.close();
      });
    }
    if (this.modalEl) {
      this.modalEl.addEventListener("click", (e) => {
        if (e.target === this.modalEl) {
          this.close();
        }
      });
      this.modalEl.addEventListener("cancel", (e) => {
        e.preventDefault();
        this.close();
      });
    }

    // Global Esc shortcut
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.isOpen()) {
        this.close();
      }
    });

    if (this.filterInputEl) {
      this.filterInputEl.addEventListener("input", () => this._onFilterChange());
    }

    // Download buttons
    if (this.downloadBtn) {
      this.downloadBtn.addEventListener("click", () => {
        if (this.currentData?.is_matchup) {
          this._downloadMatchupZip();
        } else {
          this._downloadCSV();
        }
      });
    }
    if (this.leftDownloadBtn) {
      this.leftDownloadBtn.addEventListener("click", () => {
        if (this.currentData?.player1) this._downloadCSV(this.currentData.player1);
      });
    }
    if (this.centerDownloadBtn) {
      this.centerDownloadBtn.addEventListener("click", () => {
        if (this.currentData?.matchup) this._downloadCSV(this.currentData.matchup);
        else this._downloadCSV();
      });
    }
    if (this.rightDownloadBtn) {
      this.rightDownloadBtn.addEventListener("click", () => {
        if (this.currentData?.player2) this._downloadCSV(this.currentData.player2);
      });
    }
  }

  /**
   * Open the modal with CSV data.
   * @param {Object} csvData
   */
  open(csvData) {
    this.currentData = csvData;
    this.titleEl.textContent = csvData.display_name || csvData.filename;
    this.filenameEl.textContent = csvData.filename;

    if (this.filterInputEl) {
      this.filterInputEl.value = "";
    }

    if (csvData.is_matchup && csvData.player1 && csvData.player2) {
      // 3-Column Matchup View
      if (this.modalEl) this.modalEl.classList.add("is-matchup");
      if (this.singleViewEl) this.singleViewEl.style.display = "none";
      if (this.matchupViewEl) this.matchupViewEl.style.display = "grid";
      if (this.downloadBtn) {
        this.downloadBtn.innerHTML = "📦 Download All (ZIP)";
        this.downloadBtn.title = "Download all 3 CSV files as a single ZIP archive";
      }

      this._setupMatchupView(csvData);
    } else {
      // Single Table View
      if (this.modalEl) this.modalEl.classList.remove("is-matchup");
      if (this.matchupViewEl) this.matchupViewEl.style.display = "none";
      if (this.singleViewEl) this.singleViewEl.style.display = "block";
      if (this.downloadBtn) {
        this.downloadBtn.innerHTML = "💾 Download CSV";
        this.downloadBtn.title = "Download CSV file";
      }

      this._setupSingleView(csvData);
    }

    if (this.modalEl && typeof this.modalEl.showModal === "function") {
      this.modalEl.showModal();
    }
  }

  _setupSingleView(csvData) {
    if (this.tableHeaderEl) {
      this._renderHeaders(this.tableHeaderEl, csvData.columns || []);
    }
    this.filteredRows = csvData.rows || [];
    this._renderBody();
  }

  _setupMatchupView(csvData) {
    const p1 = csvData.player1 || {};
    const h2h = csvData.matchup || csvData;
    const p2 = csvData.player2 || {};

    // Left Column (Player 1)
    if (this.leftBadgeEl) {
      this.leftBadgeEl.textContent = p1.role || "Pitcher";
      this.leftBadgeEl.className = `matchup-badge ${p1.role === "Batter" ? "badge-p2" : "badge-p1"}`;
    }
    if (this.leftTitleEl) {
      this.leftTitleEl.textContent = p1.display_name || p1.name || "Player 1";
    }
    if (this.leftMetaEl) {
      this.leftMetaEl.textContent = p1.filename || "";
    }
    if (this.leftHeadersEl) {
      this._renderHeaders(this.leftHeadersEl, p1.columns || []);
    }

    // Center Column (Head-to-Head)
    if (this.centerBadgeEl) {
      this.centerBadgeEl.textContent = "Head-to-Head";
      this.centerBadgeEl.className = "matchup-badge badge-h2h";
    }
    if (this.centerTitleEl) {
      this.centerTitleEl.textContent = h2h.display_name || h2h.name || "Matchup";
    }
    if (this.centerMetaEl) {
      this.centerMetaEl.textContent = h2h.filename || "";
    }
    if (this.centerHeadersEl) {
      this._renderHeaders(this.centerHeadersEl, h2h.columns || csvData.columns || []);
    }

    // Right Column (Player 2)
    if (this.rightBadgeEl) {
      this.rightBadgeEl.textContent = p2.role || "Batter";
      this.rightBadgeEl.className = `matchup-badge ${p2.role === "Pitcher" ? "badge-p1" : "badge-p2"}`;
    }
    if (this.rightTitleEl) {
      this.rightTitleEl.textContent = p2.display_name || p2.name || "Player 2";
    }
    if (this.rightMetaEl) {
      this.rightMetaEl.textContent = p2.filename || "";
    }
    if (this.rightHeadersEl) {
      this._renderHeaders(this.rightHeadersEl, p2.columns || []);
    }

    this._renderBody();
  }

  _renderHeaders(theaderEl, columns) {
    theaderEl.innerHTML = "";
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      tr.appendChild(th);
    });
    theaderEl.appendChild(tr);
  }

  isOpen() {
    return Boolean(this.modalEl && (this.modalEl.open || this.modalEl.hasAttribute("open")));
  }

  close() {
    if (this.modalEl) {
      if (typeof this.modalEl.close === "function" && this.modalEl.open) {
        try {
          this.modalEl.close();
        } catch (_) {}
      }
      this.modalEl.removeAttribute("open");
    }
  }

  _onFilterChange() {
    this._renderBody();
  }

  _renderBody() {
    const term = (this.filterInputEl?.value || "").toLowerCase().trim();

    if (this.currentData?.is_matchup && this.currentData.player1 && this.currentData.player2) {
      this._renderMatchupBody(term);
    } else {
      this._renderSingleBody(term);
    }
  }

  _renderSingleBody(term) {
    if (!this.tableBodyEl) return;
    this.tableBodyEl.innerHTML = "";
    const columns = this.currentData?.columns || [];
    const allRows = this.currentData?.rows || [];

    const filtered = !term
      ? allRows
      : allRows.filter((row) =>
          Object.values(row).some((val) => String(val).toLowerCase().includes(term))
        );

    this._renderRows(this.tableBodyEl, columns, filtered, "No pitch records found matching the filter.");
    if (this.rowCountEl) {
      this.rowCountEl.textContent = `${filtered.length} ${filtered.length === 1 ? "pitch type" : "pitch types"}`;
    }
  }

  _renderMatchupBody(term) {
    const p1 = this.currentData.player1 || {};
    const h2h = this.currentData.matchup || this.currentData;
    const p2 = this.currentData.player2 || {};

    const filterRows = (rows) => {
      if (!term) return rows || [];
      return (rows || []).filter((row) =>
        Object.values(row).some((val) => String(val).toLowerCase().includes(term))
      );
    };

    const p1Filtered = filterRows(p1.rows);
    const h2hFiltered = filterRows(h2h.rows);
    const p2Filtered = filterRows(p2.rows);

    if (this.leftBodyEl) {
      this._renderRows(
        this.leftBodyEl,
        p1.columns || [],
        p1Filtered,
        `No records for ${p1.name || "Player 1"}`
      );
    }
    if (this.centerBodyEl) {
      this._renderRows(
        this.centerBodyEl,
        h2h.columns || this.currentData.columns || [],
        h2hFiltered,
        "No head-to-head records found."
      );
    }
    if (this.rightBodyEl) {
      this._renderRows(
        this.rightBodyEl,
        p2.columns || [],
        p2Filtered,
        `No records for ${p2.name || "Player 2"}`
      );
    }

    // Update distinct column pitch type count badges
    if (this.leftCountEl) {
      this.leftCountEl.textContent = `${p1Filtered.length} ${p1Filtered.length === 1 ? "pitch type" : "pitch types"}`;
    }
    if (this.centerCountEl) {
      this.centerCountEl.textContent = `${h2hFiltered.length} ${h2hFiltered.length === 1 ? "pitch type" : "pitch types"}`;
    }
    if (this.rightCountEl) {
      this.rightCountEl.textContent = `${p2Filtered.length} ${p2Filtered.length === 1 ? "pitch type" : "pitch types"}`;
    }

    if (this.rowCountEl) {
      const total = h2hFiltered.length + p1Filtered.length + p2Filtered.length;
      if (term) {
        this.rowCountEl.textContent = `Filtered: ${total} pitch types across 3 tables`;
      } else {
        this.rowCountEl.textContent = `Total: ${total} pitch types across 3 tables`;
      }
    }
  }

  _renderRows(tbodyEl, columns, rows, emptyMsg) {
    tbodyEl.innerHTML = "";
    if (!rows || rows.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = Math.max(columns.length, 1);
      td.className = "csv-empty-state";
      td.textContent = emptyMsg;
      tr.appendChild(td);
      tbodyEl.appendChild(tr);
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((col) => {
        const td = document.createElement("td");
        td.textContent = row[col] !== undefined ? row[col] : "";
        tr.appendChild(td);
      });
      tbodyEl.appendChild(tr);
    });
  }

  _downloadMatchupZip() {
    if (!this.currentData || !this.currentData.is_matchup) return;
    const p1 = this.currentData.player1?.filename;
    const h2h = this.currentData.matchup?.filename || this.currentData.filename;
    const p2 = this.currentData.player2?.filename;

    const files = [p1, h2h, p2].filter(Boolean);
    const params = new URLSearchParams();
    files.forEach((f) => params.append("files", f));

    const baseName = (h2h || "matchup").replace(/\.csv$/i, "");
    const zipName = `${baseName}_all_stats.zip`;
    params.append("zip_name", zipName);

    const downloadUrl = `/api/download-zip?${params.toString()}`;
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.setAttribute("download", zipName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  _downloadCSV(data = null) {
    const target = data || (this.currentData?.is_matchup ? this.currentData.matchup : this.currentData);
    if (!target || !target.rows) return;
    const columns = target.columns || [];
    const rows = target.rows || [];

    let csvContent = columns.join(",") + "\n";
    rows.forEach((row) => {
      const line = columns.map((col) => {
        const val = row[col] || "";
        return String(val).includes(",") ? `"${val}"` : val;
      }).join(",");
      csvContent += line + "\n";
    });

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", target.filename || "export.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}
