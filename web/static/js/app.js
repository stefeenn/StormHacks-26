/**
 * Main application bootstrap and lifecycle coordinator.
 */

import { api } from "./api.js?v=2";
import { CSVModalController } from "./modal.js?v=2";
import { RecentSearchesController } from "./recent.js?v=2";
import { WizardController } from "./wizard.js?v=2";

document.addEventListener("DOMContentLoaded", () => {
  // 1. Initialize CSV Pop-out Modal Controller
  const modalController = new CSVModalController();

  // 2. Initialize Top-Right Recent Searches Dropdown Controller
  const recentController = new RecentSearchesController({ modalController });

  // 3. Initialize Progressive Input Wizard Controller
  const wizardController = new WizardController({
    recentController,
    modalController,
  });

  // 4. Automatic cleanup on closure of interface:
  // "On closure of the interface, it clears all the outputs generated."
  window.addEventListener("pagehide", () => {
    api.sendUnloadCleanupBeacon();
  });

  window.addEventListener("beforeunload", () => {
    api.sendUnloadCleanupBeacon();
  });

  console.log("⚾ Baseball Savant Explorer Interface initialized.");
});
