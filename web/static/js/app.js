/**
 * Main application bootstrap and lifecycle coordinator.
 */

import { api } from "./api.js?v=4";
import { CSVModalController } from "./modal.js?v=4";
import { DataModelController } from "./data_model.js?v=4";
import { IntroAnimationController } from "./intro.js?v=4";
import { RecentSearchesController } from "./recent.js?v=12";
import { WizardController } from "./wizard.js?v=4";

document.addEventListener("DOMContentLoaded", () => {
  // 0. Initialize Fastball Pitch Intro Animation
  const introController = new IntroAnimationController();

  // 1. Initialize Three-Source Velocity Data Model Controller
  const dataModelController = new DataModelController();

  // 2. Initialize CSV Pop-out Modal Controller (equipped with Run Data Model triggers)
  const modalController = new CSVModalController({ dataModelController });

  // 3. Initialize Top-Right Recent Searches Dropdown Controller
  const recentController = new RecentSearchesController({ modalController, dataModelController });

  // 4. Initialize Progressive Input Wizard Controller
  const wizardController = new WizardController({
    recentController,
    modalController,
  });

  // 5. Header quick launch button for Velocity Model
  const headerModelBtn = document.getElementById("btn-open-model-header");
  if (headerModelBtn) {
    headerModelBtn.addEventListener("click", () => {
      dataModelController.open();
    });
  }

  // 4. Automatic cleanup on closure of interface:
  // "On closure of the interface, it clears all the outputs generated."
  window.addEventListener("pagehide", () => {
    api.sendUnloadCleanupBeacon();
  });

  window.addEventListener("beforeunload", () => {
    api.sendUnloadCleanupBeacon();
  });

  console.log("⚾ Pitch Perfect Interface initialized.");
});
