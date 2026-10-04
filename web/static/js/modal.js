/**
 * Pop-out Modal controller for displaying CSV data.
 */

export class CSVModalController {
  constructor() {
    this.modalEl = document.getElementById("csv-modal");
    this.titleEl = document.getElementById("modal-query-title");
    this.filenameEl = document.getElementById("modal-file-name");
    this.tableHeaderEl = document.getElementById("modal-table-headers");
    this.tableBodyEl = document.getElementById("modal-table-body");
    this.filterInputEl = document.getElementById("modal-filter-input");
    this.rowCountEl = document.getElementById("modal-row-count");
    this.closeBtn = document.getElementById("modal-close-btn");
    this.footerCloseBtn = document.getElementById("modal-footer-close-btn");
    this.downloadBtn = document.getElementById("modal-download-btn");

    this.currentData = null;
    this.filteredRows = [];

    this._bindEvents();
  }

  _bindEvents() {
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.close());
    }
    if (this.footerCloseBtn) {
      this.footerCloseBtn.addEventListener("click", () => this.close());
    }
    if (this.modalEl) {
      // Close on backdrop click
      this.modalEl.addEventListener("click", (e) => {
        const rect = this.modalEl.getBoundingClientRect();
        const isInDialog = (
          rect.top <= e.clientY &&
          e.clientY <= rect.top + rect.height &&
          rect.left <= e.clientX &&
          e.clientX <= rect.left + rect.width
        );
        if (!isInDialog) {
          this.close();
        }
      });
    }

    if (this.filterInputEl) {
      this.filterInputEl.addEventListener("input", () => this._onFilterChange());
    }

    if (this.downloadBtn) {
      this.downloadBtn.addEventListener("click", () => this._downloadCSV());
    }
  }

  /**
   * Open the modal with CSV data.
   * @param {Object} csvData - { filename, display_name, columns, rows }
   */
  open(csvData) {
    this.currentData = csvData;
    this.titleEl.textContent = csvData.display_name || csvData.filename;
    this.filenameEl.textContent = csvData.filename;

    if (this.filterInputEl) {
      this.filterInputEl.value = "";
    }

    // Render Headers
    this.tableHeaderEl.innerHTML = "";
    const trHead = document.createElement("tr");
    (csvData.columns || []).forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      trHead.appendChild(th);
    });
    this.tableHeaderEl.appendChild(trHead);

    this.filteredRows = csvData.rows || [];
    this._renderBody();

    if (this.modalEl && typeof this.modalEl.showModal === "function") {
      this.modalEl.showModal();
    }
  }

  close() {
    if (this.modalEl && this.modalEl.open) {
      this.modalEl.close();
    }
  }

  _onFilterChange() {
    const term = (this.filterInputEl.value || "").toLowerCase().trim();
    if (!term) {
      this.filteredRows = this.currentData ? this.currentData.rows : [];
    } else {
      this.filteredRows = (this.currentData?.rows || []).filter((row) => {
        return Object.values(row).some((val) =>
          String(val).toLowerCase().includes(term)
        );
      });
    }
    this._renderBody();
  }

  _renderBody() {
    this.tableBodyEl.innerHTML = "";
    const columns = this.currentData?.columns || [];

    if (!this.filteredRows || this.filteredRows.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = Math.max(columns.length, 1);
      td.className = "csv-empty-state";
      td.textContent = "No pitch records found matching the filter.";
      tr.appendChild(td);
      this.tableBodyEl.appendChild(tr);
      this.rowCountEl.textContent = "0 rows";
      return;
    }

    this.filteredRows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((col) => {
        const td = document.createElement("td");
        td.textContent = row[col] !== undefined ? row[col] : "";
        tr.appendChild(td);
      });
      this.tableBodyEl.appendChild(tr);
    });

    this.rowCountEl.textContent = `${this.filteredRows.length} ${this.filteredRows.length === 1 ? "pitch type" : "pitch types"}`;
  }

  _downloadCSV() {
    if (!this.currentData || !this.currentData.rows) return;
    const columns = this.currentData.columns || [];
    const rows = this.currentData.rows || [];

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
    link.setAttribute("download", this.currentData.filename || "export.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}
