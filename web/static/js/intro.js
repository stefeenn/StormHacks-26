/**
 * IntroAnimationController
 * Orchestrates the 3D baseball zoom-in fastball animation,
 * screen impact, and signature stadium background gradient bloom.
 */

export class IntroAnimationController {
  constructor() {
    this.stage = document.getElementById("intro-stage");
    this.ballTrack = document.querySelector(".intro-ball-track");
    this.shockwave = document.getElementById("intro-shockwave");
    this.skipBtn = document.getElementById("intro-skip-btn");

    this.isPlaying = false;
    this.timers = [];

    this.init();
  }

  init() {
    if (!this.stage) {
      console.warn("Intro stage element (#intro-stage) not found in DOM.");
      return;
    }

    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      this.finishImmediately();
      return;
    }

    // Keyboard shortcut (Escape to skip)
    this.handleKeyDown = (e) => {
      if (e.key === "Escape" && this.isPlaying) {
        this.finishImmediately();
      }
    };
    window.addEventListener("keydown", this.handleKeyDown);

    // Skip button click
    if (this.skipBtn) {
      this.skipBtn.addEventListener("click", () => this.finishImmediately());
    }

    // Start introductory sequence
    this.playSequence();
  }

  /**
   * Run the choreographed pitch flight and gradient bloom.
   */
  playSequence() {
    this.clearTimers();
    this.isPlaying = true;

    // 1. Prime stage and body atmosphere
    document.body.classList.add("intro-active");
    document.body.classList.remove("intro-revealing", "ui-revealed");
    this.stage.classList.remove("intro-finished", "screen-shake");
    if (this.shockwave) {
      this.shockwave.classList.remove("flash-active");
    }

    // Restart CSS animations on ball track, baseball SVG, seams, and speed lines
    const ballSvg = this.stage.querySelector(".intro-baseball-svg");
    const seams = this.stage.querySelector(".intro-seams-group");
    const speedLines = this.stage.querySelector(".intro-speed-lines");
    [this.ballTrack, ballSvg, seams, speedLines].forEach((el) => {
      if (el) {
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "";
      }
    });

    // 2. Climax Impact Timing (~1350ms into 1500ms pitch)
    // The ball reaches full speed and triggers the impact flash
    const impactTimer = setTimeout(() => {
      // Camera impact shake
      this.stage.classList.add("screen-shake");

      // Shockwave impact flash
      if (this.shockwave) {
        this.shockwave.classList.add("flash-active");
      }

      // THIS IS WHEN THE USUAL WEBSITE BACKGROUND GRADIENT LOADS IN IMMEDIATELY!
      document.body.classList.add("intro-revealing");
      document.body.classList.add("ui-revealed");
    }, 1350);
    this.timers.push(impactTimer);

    // 3. Quick fade out of overlay curtain (~1480ms) so white screen does not linger
    const fadeTimer = setTimeout(() => {
      this.stage.classList.add("intro-finished");
    }, 1480);
    this.timers.push(fadeTimer);

    // 4. Complete cleanup (~1800ms)
    const cleanupTimer = setTimeout(() => {
      this.cleanup();
    }, 1800);
    this.timers.push(cleanupTimer);
  }

  /**
   * Instantly skip intro animation and present active website
   */
  finishImmediately() {
    this.clearTimers();
    document.body.classList.remove("intro-active");
    document.body.classList.add("intro-revealing", "ui-revealed");

    if (this.stage) {
      this.stage.classList.add("intro-finished");
    }
    this.isPlaying = false;
  }

  /**
   * Final cleanup after animation ends
   */
  cleanup() {
    this.isPlaying = false;
    document.body.classList.remove("intro-active");
    // Ensure final state retains gradient and visible UI
    document.body.classList.add("intro-revealing", "ui-revealed");
    if (this.stage) {
      this.stage.classList.add("intro-finished");
    }
  }

  /**
   * Replay the intro animation on demand
   */
  replay() {
    window.scrollTo({ top: 0, behavior: "smooth" });
    this.playSequence();
  }

  clearTimers() {
    this.timers.forEach((t) => clearTimeout(t));
    this.timers = [];
  }
}
