"""
================================================================================
 README -- THREE-SOURCE PITCH VELOCITY MODEL (over/under bet evaluator)
================================================================================

FILE
  dataModel/threeSourceModel.py   stormHack26 project, Python port of the original
  MATLAB model. Requires Python 3 with numpy, pandas, matplotlib (no SciPy).
  Run:  python threeSourceModel.py      (edit only the USER INPUT section below)
  Works from any working directory: relative file names are resolved against
  this script's folder (dataModel/), not where you launch it from.

  dataModel/ folder layout:
    threeSourceModel.py    this model
    inputPitcher.csv       \
    inputBatter.csv         > written by the external data scraper (any tool);
    inputH2H.csv           /  overwrite them, keep the names and column layout
    model_output.json      written by this model on every run

--------------------------------------------------------------------------------
 INPUTS
--------------------------------------------------------------------------------
Three CSV files (Baseball Savant-style exports), in the dataModel/ folder next
to this script (or give full paths in USER INPUT). Any one can be set to "" to
leave it out, but at least inputPitcher.csv or inputH2H.csv is needed (they
are the only speed sources).

  1. inputPitcher.csv -- the pitcher's season arsenal, split by BATTER hand
       Pitch Type, Average Velocity - Left (mph), Average Velocity - Right (mph),
       Occurrence Percentage - Left (%), Occurrence Percentage - Right (%)
     Set arsenal_column to the batter's hand ("Left" for a left-handed batter).

  2. inputBatter.csv  -- every pitch the batter has faced (from ALL pitchers),
                         split by PITCHER hand. Same columns as above.
     Set batter_column to the pitcher's hand ("Left" for a left-handed pitcher).
     Only the percentages are used; its speeds belong to other pitchers.

  3. inputH2H.csv     -- head-to-head: this pitcher vs this batter (no split)
       Pitch Type, Average Velocity (mph), Occurrence Percentage (%)
     Pitch count is inferred from the percentages (e.g. 38.1/33.3/28.6 -> 21).

  Format notes: percentages may be written "37.8%" or "37.8"; "N/A" and 0% rows
  are skipped. Pitch names are matched to the 11 types in the key below
  (case/punctuation ignored; "Splitter" = Split-Finger, "Knuckle Curve" = Knuckle-Curve).
  If a file has both "Pitcher Left" and "Batter Left" columns, write the full
  label, e.g. arsenal_column = "Batter Left".

Plus, in USER INPUT: the sportsbook line (bet_line, mph) and American odds for
each side (over_odds, under_odds), the stake ($ per bet) and optional bankroll.

--------------------------------------------------------------------------------
 WHAT THE PROGRAM DOES
--------------------------------------------------------------------------------
  1. Reads the three files and keeps the pitch types the pitcher throws
     (inputBatter.csv is cut down to those types and renormalized).
  2. Pitch mix  = weighted average of the three mixes:
        p = (kappa_arsenal*pPitcher + kappa_batter*pBatter + n_H2H*pH2H) / (sum of weights)
     Weights are "pitches of evidence"; n_H2H is the real head-to-head pitch count.
  3. Speed per pitch type = season average pulled toward the head-to-head average:
        mu_k = (m_velocity*muPitcher_k + nH2H_k*muH2H_k) / (m_velocity + nH2H_k)
  4. Velocity = Gaussian MIXTURE: one bell per pitch type (SD assumed, the files
     only give averages), weighted by the pitch mix.  P(V > line) = sum of each
     bell's share above the line.
  5. Uncertainty: 5000 simulations, each drawing the weights from their ranges,
     the pitch mix, each type's mean speed and the SD. Final P(over) = average.
  6. Betting: odds -> break-even probability; edge = model win chance - break-even.
     Each side is rated on its own:
        STRONG   edge >= 3 pts, beats break-even in >= 90% of sims, win >= 60%
        MEDIUM   edge >= 3 pts
        NOT GOOD otherwise
  7. Money: payout, average result per bet, optional quarter-Kelly bet size, and
     chances of being ahead / about even / behind after 10 and 50 bets.

  PLACEHOLDERS (not yet backtested): kappa_* and m_velocity weights and their
  ranges, sd_default and sd_range. Results depend on them -- see the WHY lines.

--------------------------------------------------------------------------------
 OUTPUT
--------------------------------------------------------------------------------
  Console report:
    - One block per side (better side first, "<- recommended" if worth betting):
      rating [STRONG / MEDIUM / NOT GOOD], chance to win vs break-even, edge,
      "how sure", ONE BET payout and chances, MANY BETS table (10 and 50 bets).
    - NO BET line at the top if neither side clears the edge threshold.
    - NOTES, WHY (what drives the answer; + supports it, - works against it),
      CAUTION and any warnings.
    - With show_details = True: per-pitch-type table, weights, scenario P(over)s.
  model_output.json -- every number above, for a user interface. Top-level keys:
      answer, line, p_over, p_over_90_range, sides (OVER/UNDER: win_prob, edge,
      rating, suggested_bet, ...), money, outcomes (single_bet, many_bets, by_side),
      why, cautions, warnings, rules, details (pitch_types table), plot (curves).
  Plot window (show_plot = True): per-type bells, combined curve, season-only and
      head-to-head-only curves, shaded OVER region and the bet line.

  From other Python code (e.g. a UI):
      from threeSourceModel import run_model
      result = run_model(bet_line=96.0, over_odds=-120)  # any USER INPUT name
  returns a dict with the same content as model_output.json.

  Limits: one average speed per pitch type (SDs assumed); small head-to-head
  samples; no game context (count, inning, fatigue); the book may know more.
================================================================================
"""

import os
import sys
import re
import math
import json
import numpy as np
import pandas as pd

# ===== USER INPUT =====
# Pitcher's season arsenal. Column = the BATTER's hand ("Left" for a lefty batter).
arsenal_csv    = "inputPitcher.csv"
arsenal_column = "Left"
# Pitches the batter has faced. Column = the PITCHER's hand ("Left" for a lefty pitcher).
batter_csv     = "inputBatter.csv"
batter_column  = "Left"
# Head-to-head: this pitcher vs this batter (one mix, no Left/Right split).
matchup_csv    = "inputH2H.csv"
# Set any file to "" to leave it out (inputPitcher or inputH2H is needed for speeds).
# For a file with "Pitcher Left" AND "Batter Left" columns, write e.g. "Batter Left".

# ----- BETTING LINE -----
bet_line   = 95.5     # mph (example -- replace with the site's line)
over_odds  = -110     # American odds for OVER  (example)
under_odds = -110     # American odds for UNDER (example)

# ----- MONEY -----
stake          = 100      # $ per bet
bankroll       = 1000     # $ total betting budget, for a suggested bet size; None to skip
kelly_fraction = 0.25     # share of the full Kelly size to suggest (0.25 = quarter-Kelly)
n_bets_list    = [10, 50] # "if you made N bets like this" outcome tables
even_band      = 50       # $: a final result within +/- this counts as "about even"

# ----- WEIGHTING (PLACEHOLDERS until backtested) -----
# Central value (used for the detail tables and plot) and the plausible range
# that the simulations draw from. "Pitches of evidence" = how many matchup
# pitches that file is worth.
kappa_arsenal = 100;  kappa_arsenal_range = (50, 200)  # file A, pitch mix (log-uniform)
kappa_batter  = 30;   kappa_batter_range  = (0, 60)    # file B, pitch mix (uniform)
m_velocity    = 20;   m_velocity_range    = (5, 80)    # file A, speed (log-uniform)
n_matchup     = "auto"  # real pitch count behind file C; "auto" = infer from its percentages

# The CSVs hold one AVERAGE speed per pitch type, so the pitch-to-pitch spread
# (SD) is unknown and ASSUMED. sd_default is a PLACEHOLDER.
sd_default = 1.5
sd_override_list = [   # optional per-type SD: (type_number, sd), type numbers below
    # (1, 1.0),
]
# Plausible range for sd_default (mph), used in the simulations. Overridden SDs
# are scaled by the same proportion.
sd_range = (1.0, 2.5)
n_sims   = 5000

# Verdict rules (in probability: 0.03 = 3 percentage points)
min_edge          = 0.03  # average edge over break-even needed to bet (MEDIUM)
strong_min_sure   = 0.90  # STRONG: side beats break-even in at least this share of simulations
strong_min_win    = 0.60  # STRONG: and the win chance is at least this

# Output
show_details = False                 # True = also print the full tables
show_plot    = True                  # False = no plot window
output_json  = "model_output.json"   # every number, for a UI; "" to skip

# PITCH TYPE KEY (CSV names are matched to these automatically):
#  1 = 4-Seam Fastball    5 = Sweeper         9  = Slurve
#  2 = Sinker             6 = Changeup        10 = Knuckle-Curve
#  3 = Slider             7 = Curveball       11 = Knuckleball
#  4 = Cutter             8 = Split-Finger
names = ["4-Seam Fastball", "Sinker", "Slider", "Cutter", "Sweeper",
         "Changeup", "Curveball", "Split-Finger", "Slurve",
         "Knuckle-Curve", "Knuckleball"]
# ===== END USER INPUT =====

SETTINGS = ["arsenal_csv", "arsenal_column", "batter_csv", "batter_column", "matchup_csv",
            "bet_line", "over_odds", "under_odds", "stake", "bankroll", "kelly_fraction",
            "n_bets_list", "even_band", "kappa_arsenal", "kappa_arsenal_range",
            "kappa_batter", "kappa_batter_range", "m_velocity", "m_velocity_range",
            "n_matchup", "sd_default", "sd_override_list", "sd_range", "n_sims",
            "min_edge", "strong_min_sure", "strong_min_win"]

K = len(names)
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
ALIASES = {"splitter": 8, "4seam": 1, "fourseam": 1}


# ----- helper functions -----
def in_model_dir(path):
    """Relative paths are taken from this script's folder, so the model finds
    the scraper's files no matter where it is launched from."""
    return path if os.path.isabs(path) else os.path.join(MODEL_DIR, path)

def key_of(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def num(s):
    t = str(s).replace("%", "").strip()
    if t == "" or t.upper() in ("N/A", "NAN"):
        return np.nan
    try:
        return float(t)
    except ValueError:
        return np.nan

def type_index(name, label):
    """0-based index into names for a CSV pitch name."""
    k = key_of(name)
    keys = [key_of(x) for x in names]
    if k in keys:
        return keys.index(k)
    if k in ALIASES:
        return ALIASES[k] - 1
    raise ValueError(f'{label}: pitch type "{name}" is not one of the {K} types.')

def read_source(path, column, label):
    """Return (percent vector, velocity vector, column used) from a Savant-style CSV."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    low = {c: c.lower() for c in df.columns}
    type_col = next((c for c in df.columns if "pitch type" in low[c]), None)
    if type_col is None:
        raise ValueError(f'{label} ({path}): no "Pitch Type" column.')
    occ = [c for c in df.columns if "occurrence" in low[c] or "usage" in low[c]]
    vel = [c for c in df.columns if "velocity" in low[c]]
    where = ""
    if any("left" in low[c] or "right" in low[c] for c in occ):
        want = column.strip().lower()
        occ = [c for c in occ if want and want in low[c]]
        vel = [c for c in vel if want and want in low[c]]
        where = f' matching "{column}"'
    if len(occ) != 1:
        raise ValueError(f"{label} ({path}): found {len(occ)} occurrence columns{where}. "
                         f"Columns are: {list(df.columns)}")
    vc = vel[0] if len(vel) == 1 else None
    pct = np.zeros(K)
    v = np.full(K, np.nan)
    for _, row in df.iterrows():
        pc = num(row[occ[0]])
        if np.isnan(pc) or pc <= 0:
            continue
        i = type_index(row[type_col], label)
        if pct[i] > 0:
            raise ValueError(f"{label}: {names[i]} appears twice.")
        pct[i] = pc
        if vc is not None:
            v[i] = num(row[vc])
    if pct.sum() == 0:
        raise ValueError(f"{label} ({path}): no usable percentages.")
    return pct, v, occ[0]

def infer_mix_n(pcts, max_n=300, tol=0.051):
    """Smallest pitch count n where every percentage is a rounded k/n."""
    for n in range(1, max_n + 1):
        counts = [round(pc * n / 100) for pc in pcts]
        if sum(counts) != n:
            continue
        if all(abs(pc - c * 100 / n) <= tol for pc, c in zip(pcts, counts)):
            return n
    return None

def pdf_n(x, m, s):
    x = np.asarray(x, dtype=float)
    if s <= 0:
        return np.zeros_like(x)
    return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * math.sqrt(2 * math.pi))

def mix_pdf(x, p, mu, sd):
    return sum(p[j] * pdf_n(x, mu[j], sd[j]) for j in range(len(p)))

def mix_stats(p, mu, sd):
    m = np.sum(p * mu)
    s = np.sqrt(np.sum(p * sd**2) + np.sum(p * (mu - m)**2))  # law of total variance
    return m, s

erf_v = np.vectorize(math.erf, otypes=[float])

def p_over(L, p, mu, sd):
    """P(V > L) for a Gaussian mixture. Works on single values or rows of draws."""
    z = (L - mu) / (np.maximum(sd, 1e-9) * math.sqrt(2))
    return np.sum(p * 0.5 * (1 - erf_v(z)), axis=-1)

def american_to_prob(odds):
    """Break-even win probability for American odds (includes the book's cut)."""
    if -100 < odds < 100:
        raise ValueError(f"American odds must be <= -100 or >= +100 (got {odds}).")
    return (-odds) / (-odds + 100) if odds < 0 else 100 / (odds + 100)

def american_profit(odds):
    """Profit per 1 unit staked if the bet wins."""
    return 100 / (-odds) if odds < 0 else odds / 100

def outcome_table(win_draws, n, stake_, prof, band):
    """Chances after n equal bets. Wins ~ Binomial(n, P), averaged over the
    simulated P's -- so if the model's P is off, it is off for every bet."""
    k = np.arange(n + 1)
    lc = np.array([math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) for i in k])
    P = np.clip(win_draws[:, None], 1e-12, 1 - 1e-12)
    pmf = np.exp(lc + k * np.log(P) + (n - k) * np.log(1 - P)).mean(axis=0)
    net = stake_ * (k * prof - (n - k))
    cdf = np.cumsum(pmf)
    pick = lambda q: float(net[min(np.searchsorted(cdf, q), n)])
    return {"n_bets": n,
            "total_staked": stake_ * n,
            "chance_ahead": float(pmf[net > band].sum()),
            "chance_about_even": float(pmf[np.abs(net) <= band].sum()),
            "chance_behind": float(pmf[net < -band].sum()),
            "chance_any_profit": float(pmf[net > 0].sum()),
            "wins_needed_to_profit": int(k[net > 0][0]) if np.any(net > 0) else None,
            "net_p10": pick(0.10), "net_median": pick(0.50), "net_p90": pick(0.90),
            "net_average": float((pmf * net).sum())}


def run_model(**overrides):
    """Run the model. Keyword arguments override USER INPUT values by name.
    Returns a dict with every result (also what gets saved to output_json)."""
    bad = [k for k in overrides if k not in SETTINGS]
    if bad:
        raise ValueError(f"Unknown setting(s): {bad}. Valid: {SETTINGS}")
    c = {k: globals()[k] for k in SETTINGS}
    c.update(overrides)

    # ----- read the files -----
    srcs = {}
    for key, path, col, label in [("A", c["arsenal_csv"], c["arsenal_column"], "Arsenal (A)"),
                                  ("B", c["batter_csv"], c["batter_column"], "Batter faced (B)"),
                                  ("C", c["matchup_csv"], "", "Matchup (C)")]:
        if path:
            srcs[key] = read_source(in_model_dir(path), col, label)
    hasA, hasB, hasC = "A" in srcs, "B" in srcs, "C" in srcs
    if not (hasA or hasC):
        raise ValueError("Need arsenal_csv or matchup_csv -- they are the only speed sources.")
    if c["bet_line"] is None:
        raise ValueError("Set bet_line to the sportsbook's line (mph).")

    zero = np.zeros(K)
    pctA, velA = (srcs["A"][0], srcs["A"][1]) if hasA else (zero, np.full(K, np.nan))
    pctB = srcs["B"][0] if hasB else zero
    pctC, velC = (srcs["C"][0], srcs["C"][1]) if hasC else (zero, np.full(K, np.nan))

    # Pitcher's types = anything in the arsenal or the matchup (file B is other pitchers)
    T = np.where((pctA > 0) | (pctC > 0))[0]
    nm = [names[i] for i in T]
    A_ = len(T)
    warnings = []
    if hasA and hasC:
        extra = [names[i] for i in T if pctA[i] == 0]
        if extra:
            warnings.append(f"The matchup has {', '.join(extra)}, which the arsenal does not. "
                            f"Check that A and C are the same pitcher.")

    def norm(v):
        s = v.sum()
        return v / s if s > 0 else v
    pA, pB, pC = norm(pctA[T]), norm(pctB[T]), norm(pctC[T])
    covered_B = pctB[T].sum() / pctB.sum() if hasB else 0
    if hasB and pB.sum() == 0:
        raise ValueError("File B has 0% for every pitch type this pitcher throws.")
    muA_src, muC_src = velA[T], velC[T]
    for j in range(A_):
        if np.isnan(muA_src[j]) and np.isnan(muC_src[j]):
            raise ValueError(f"{nm[j]} has no speed in file A or C.")

    # Matchup pitch count
    if not hasC:
        nC = 0
    elif c["n_matchup"] == "auto":
        nC = infer_mix_n(list(pctC[pctC > 0]))
        if nC is None:
            raise ValueError("Could not infer the matchup pitch count. Set n_matchup to a number.")
    else:
        nC = int(c["n_matchup"])
    nC_k = np.round(pC * nC)

    # SDs (assumed) and the scale factors used to vary them
    if c["sd_default"] <= 0:
        raise ValueError("sd_default must be > 0.")
    sdT = np.full(A_, float(c["sd_default"]))
    for idx, s in c["sd_override_list"]:
        hit = np.where(T == idx - 1)[0]
        if len(hit):
            sdT[hit[0]] = s
    sd_lo_f, sd_hi_f = c["sd_range"][0] / c["sd_default"], c["sd_range"][1] / c["sd_default"]

    has_vA = ~np.isnan(muA_src)
    has_vC = ~np.isnan(muC_src)
    muA0, muC0 = np.nan_to_num(muA_src), np.nan_to_num(muC_src)
    fallback = np.where(has_vA, muA_src, muC_src)

    def build(wA, wB, wC, vA, vC=1):
        """Combine sources with fixed weights. Returns mix p and speeds mu."""
        alpha = wA * pA + wB * pB + wC * pC
        wa = np.where(has_vA, vA, 0.0)
        wc = np.where(has_vC, vC * nC_k, 0.0)
        den = wa + wc
        mu = np.where(den > 0, (wa * muA0 + wc * muC0) / np.where(den > 0, den, 1), fallback)
        return alpha / alpha.sum(), mu

    rng = np.random.default_rng()
    N = c["n_sims"]

    def draw(rngs, log):
        lo, hi = rngs
        if log and lo > 0:
            return np.exp(rng.uniform(math.log(lo), math.log(hi), (N, 1)))
        return rng.uniform(lo, hi, (N, 1))

    def simulate(L, rA, rB, rV, useC=True):
        """P(over) in each of N simulations. Each draws the weights from their
        ranges, then the pitch mix ~ Dirichlet(weights), each type's mean speed
        ~ N(mu, sd/sqrt(evidence)), and the assumed SDs scaled across sd_range."""
        kA = draw(rA, True) if hasA else np.zeros((N, 1))
        kB = draw(rB, False) if hasB else np.zeros((N, 1))
        mV = draw(rV, True)
        wC = nC if useC else 0
        alpha = kA * pA + kB * pB + wC * pC
        wa = np.where(has_vA, mV, 0.0)
        wc = np.where(has_vC, nC_k if useC else 0.0, 0.0)
        den = wa + wc
        mu = np.where(den > 0, (wa * muA0 + wc * muC0) / np.where(den > 0, den, 1), fallback)
        g = rng.gamma(np.maximum(alpha, 0.0))                     # Dirichlet via gammas
        pb = g / np.maximum(g.sum(axis=1, keepdims=True), 1e-300)
        sb = sdT * rng.uniform(sd_lo_f, sd_hi_f, (N, 1))
        mub = mu + rng.standard_normal((N, A_)) * sb / np.sqrt(np.maximum(den, 1.0))
        return p_over(L, pb, mub, sb)

    L = float(c["bet_line"])
    stake_ = float(c["stake"])
    odds = {"OVER": c["over_odds"], "UNDER": c["under_odds"]}

    # ----- THE ANSWER: average over everything -----
    draws = simulate(L, c["kappa_arsenal_range"], c["kappa_batter_range"], c["m_velocity_range"])
    P_over = float(draws.mean())
    win_draws = {"OVER": draws, "UNDER": 1 - draws}
    sides = {}
    for k in ("OVER", "UNDER"):
        be, prof = american_to_prob(odds[k]), american_profit(odds[k])
        P = float(win_draws[k].mean())
        sides[k] = {"odds": odds[k], "win_prob": P, "lose_prob": 1 - P,
                    "break_even_prob": be, "edge": P - be,
                    "sure": float(np.mean(win_draws[k] > be)),
                    "profit_if_win": stake_ * prof, "return_if_win": stake_ * (1 + prof),
                    "loss_if_lose": stake_,
                    "average_per_bet": stake_ * (P * prof - (1 - P)),
                    "average_pct": 100 * (P * prof - (1 - P))}
    # Rate each side on its own; suggested size (Kelly) only for a side worth betting
    for k, s in sides.items():
        if (s["edge"] >= c["min_edge"] and s["sure"] >= c["strong_min_sure"]
                and s["win_prob"] >= c["strong_min_win"]):
            s["rating"] = "STRONG"
        elif s["edge"] >= c["min_edge"]:
            s["rating"] = "MEDIUM"
        else:
            s["rating"] = "NOT GOOD"
        b = american_profit(odds[k])
        s["kelly_full_fraction"] = max(0.0, (b * s["win_prob"] - s["lose_prob"]) / b)
        s["suggested_bet"] = (c["bankroll"] * c["kelly_fraction"] * s["kelly_full_fraction"]
                              if (s["rating"] != "NOT GOOD" and c["bankroll"]) else None)
    side = max(sides, key=lambda k: sides[k]["edge"])
    S = sides[side]
    level = None if S["rating"] == "NOT GOOD" else S["rating"]
    kelly_full, suggested = S["kelly_full_fraction"], S["suggested_bet"]

    # Outcome chances for both sides; the top-level keys are the chosen side
    # (or the better-looking side if no bet), by_side has both for comparison.
    def side_outcomes(k):
        s = sides[k]
        return {"single_bet": {"chance_profit": s["win_prob"], "chance_even": 0.0,
                               "chance_loss": s["lose_prob"],
                               "profit": s["profit_if_win"], "loss": stake_},
                "many_bets": [outcome_table(win_draws[k], int(n), stake_,
                                            american_profit(odds[k]), float(c["even_band"]))
                              for n in c["n_bets_list"]]}
    by_side = {k: side_outcomes(k) for k in ("OVER", "UNDER")}
    outcomes = {"side": side, **by_side[side], "by_side": by_side,
                "even_band": float(c["even_band"])}

    # Central (placeholder-weight) model, for the "why" lines, details and plot
    wA0 = c["kappa_arsenal"] if hasA else 0
    wB0 = c["kappa_batter"] if hasB else 0
    p, mu = build(wA0, wB0, nC, c["m_velocity"])
    m_all, s_all = mix_stats(p, mu, sdT)
    p_type = np.array([float(p_over(L, np.array([1.0]), mu[j:j+1], sdT[j:j+1]))
                       for j in range(A_)])

    # ----- why: "+" supports the answer, "-" against it, "*" neutral -----
    toward_over = (side == "OVER") if level else None
    def mark(pushes_over):
        if toward_over is None:
            return "*"
        return "+" if pushes_over == toward_over else "-"
    why = []
    for j in np.argsort(-p):
        if p[j] < 0.05:
            continue
        if p_type[j] < 0.05:
            sg, where = mark(False), "almost certain unders"
        elif p_type[j] > 0.95:
            sg, where = mark(True), "almost certain overs"
        else:
            sg = mark(p_type[j] > 0.5)
            where = ("mostly overs" if p_type[j] > 0.75 else
                     "mostly unders" if p_type[j] < 0.25 else "near the line")
            where += f", over {100*p_type[j]:.0f}% of the time"
        why.append({"sign": sg, "text": f"{100*p[j]:.0f}% {nm[j].lower()}s "
                                        f"(~{mu[j]:.1f} mph): {where}"})
    P_A = P_C = None
    if hasA and hasC:
        diff = np.where((nC_k > 0) & has_vA & has_vC, muC_src - muA_src, np.nan)
        if np.any(~np.isnan(diff)) and np.nanmax(np.abs(diff)) > 1.0:
            faster = np.nanmean(diff) > 0
            why.append({"sign": mark(faster),
                        "text": f"The {nC} matchup pitches ran "
                                f"{np.nanmin(np.abs(diff)):.1f}-{np.nanmax(np.abs(diff)):.1f} mph "
                                f"{'faster' if faster else 'slower'} than his season averages "
                                f"(pushes toward {'OVER' if faster else 'UNDER'}; partly trusted)"})
        P_A = float(simulate(L, c["kappa_arsenal_range"], (0, 0), c["m_velocity_range"],
                             useC=False).mean())
        P_C = float(simulate(L, (0, 0), (0, 0), (0, 0)).mean())
        if (P_A - 0.5) * (P_C - 0.5) < 0:   # one favors OVER, the other UNDER
            why.append({"sign": "!",
                        "text": f"Season data alone says {100*P_A:.0f}% over; the matchup alone "
                                f"says {100*P_C:.0f}%. They disagree, so the answer rests on how "
                                f"much the {nC} matchup pitches are trusted."})
    be_o, be_u = sides["OVER"]["break_even_prob"], sides["UNDER"]["break_even_prob"]
    book_over = be_o / (be_o + be_u)
    why.append({"sign": "*", "text": f"The book's line (vig removed) implies "
                                     f"{100*book_over:.0f}% over; the model says {100*P_over:.0f}%."})

    cautions = ["Speed spreads (SDs) are assumed -- the CSVs give one average per pitch type."]
    if hasC:
        cautions.append(f"The matchup is only {nC} pitches.")
    cautions += ["The weights are unbacktested guesses.",
                 "The book may know things the model doesn't (injury, fatigue, weather)."]

    # ----- plot data -----
    lo = float(np.min(mu - 4 * sdT) - 2)
    hi = float(np.max(mu + 4 * sdT) + 2)
    v = np.linspace(lo, hi, 400)
    plot = {"x_mph": v, "combined": mix_pdf(v, p, mu, sdT),
            "by_type": {nm[j]: p[j] * pdf_n(v, mu[j], sdT[j]) for j in range(A_)}}
    if hasA:
        pa, mua = build(1, 0, 0, 1, 0)
        plot["season_only"] = mix_pdf(v, pa, mua, sdT)
    if hasC:
        pc, muc = build(0, 0, max(nC, 1), 0, 1)
        plot["matchup_only"] = mix_pdf(v, pc, muc, sdT)

    W = wA0 + wB0 + nC
    lo5, hi95 = np.percentile(draws, [5, 95])
    nan2none = lambda x: None if np.isnan(x) else float(x)
    result = {
        "answer": {"bet": level is not None, "side": side if level else None,
                   "level": level, "best_side": side,
                   "headline": (f"BET {side} {L:g} mph at {odds[side]:+d} [{level}]" if level
                                else f"NO BET on {L:g} mph -- neither side has a big enough edge")},
        "line": {"bet_line": L, "over_odds": c["over_odds"], "under_odds": c["under_odds"],
                 "book_no_vig_p_over": book_over,
                 "vig": be_o + be_u - 1},
        "p_over": P_over, "p_over_90_range": [float(lo5), float(hi95)],
        "sides": sides,
        "money": {"stake": stake_, "bankroll": c["bankroll"],
                  "kelly_fraction": c["kelly_fraction"], "kelly_full_fraction": kelly_full,
                  "suggested_bet": suggested},
        "outcomes": outcomes,
        "why": why, "cautions": cautions, "warnings": warnings,
        "rules": {"min_edge": c["min_edge"], "strong_min_sure": c["strong_min_sure"],
                  "strong_min_win": c["strong_min_win"], "n_sims": N},
        "details": {
            "files": {k: {"path": c[f], "column": srcs[k][2]}
                      for k, f in [("A", "arsenal_csv"), ("B", "batter_csv"), ("C", "matchup_csv")]
                      if k in srcs},
            "n_matchup_pitches": nC,
            "batter_file_coverage": covered_B if hasB else None,
            "central_weight_shares": {"arsenal": wA0 / W, "batter": wB0 / W, "matchup": nC / W},
            "mean_mph": float(m_all), "sd_mph": float(s_all),
            "single_bell_p_over": 0.5 * (1 - math.erf((L - m_all) / (s_all * math.sqrt(2)))),
            "p_over_season_only": P_A, "p_over_matchup_only": P_C,
            "pitch_types": [{"name": nm[j],
                             "pct_arsenal": float(pA[j]) if hasA else None,
                             "pct_batter": float(pB[j]) if hasB else None,
                             "pct_matchup": float(pC[j]) if hasC else None,
                             "pct_used": float(p[j]),
                             "mph_arsenal": nan2none(muA_src[j]),
                             "mph_matchup": nan2none(muC_src[j]),
                             "n_matchup": int(nC_k[j]), "mph_used": float(mu[j]),
                             "sd_assumed": float(sdT[j]), "p_over_line": float(p_type[j])}
                            for j in range(A_)]},
        "plot": plot,
    }
    return result


def to_json(obj):
    """Convert numpy values to plain Python so json can save them."""
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [to_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(obj) else round(float(obj), 6)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def print_report(r):
    a = r["answer"]
    L = r["line"]["bet_line"]
    o = r["outcomes"]
    m = r["money"]
    st = m["stake"]
    f = lambda x: f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"
    blk = lambda x: "#" * round(20 * x) + "." * (20 - round(20 * x))
    bar = "=" * 62

    if not a["bet"]:
        print(f"NO BET on {L:g} mph -- neither side clears an average edge of "
              f"{100*r['rules']['min_edge']:.0f} points.\n")

    # One block per side, better side first
    best = a["best_side"]
    for k in [best, "UNDER" if best == "OVER" else "OVER"]:
        s = r["sides"][k]
        tag = "   <- recommended" if (a["bet"] and k == best) else ""
        print(bar)
        print(f"  {k} {L:g} mph at {s['odds']:+d}   [{s['rating']}]{tag}")
        print(bar)
        print(f"Chance {k} wins : {100*s['win_prob']:.1f}%   (break-even "
              f"{100*s['break_even_prob']:.1f}%)  ->  edge {100*s['edge']:+.1f} pts")
        print(f"How sure{' ' * (len(k) + 5)}: {k} beat break-even in {100*s['sure']:.0f}% "
              f"of {r['rules']['n_sims']} simulations")

        sb = o["by_side"][k]["single_bet"]
        print(f"\nONE BET (${st:,.0f})")
        print(f"  Profit {f(s['profit_if_win']):>10} : {100*sb['chance_profit']:5.1f}%  "
              f"{blk(sb['chance_profit'])}   (get back ${s['return_if_win']:,.2f})")
        print(f"  Lose   {f(-st):>10} : {100*sb['chance_loss']:5.1f}%  {blk(sb['chance_loss'])}")
        print(f"  Break even        :   0.0%  (a .5 line can't tie)")
        print(f"  Average per bet   : {f(s['average_per_bet'])} ({s['average_pct']:+.1f}%)")
        if s["suggested_bet"] is not None:
            print(f"  Suggested size    : ${s['suggested_bet']:,.2f} "
                  f"({m['kelly_fraction']:g} Kelly on a ${m['bankroll']:,.0f} bankroll)")

        print(f"\nMANY BETS (${st:,.0f} each)")
        print(f"  {'Bets':>5} {'Ahead':>7} {'Even':>7} {'Behind':>7}   "
              f"{'Middle 80% of results':<26} {'Average':>11}  Wins to profit")
        for t in o["by_side"][k]["many_bets"]:
            rng_ = f"{f(t['net_p10'])} to {f(t['net_p90'])}"
            print(f"  {t['n_bets']:>5} {100*t['chance_ahead']:>6.0f}% "
                  f"{100*t['chance_about_even']:>6.0f}% {100*t['chance_behind']:>6.0f}%   "
                  f"{rng_:<26} {f(t['net_average']):>11}  "
                  f"{t['wins_needed_to_profit']} of {t['n_bets']}")
        print()

    print(f"NOTES: Average = over many bets, not a promise. Even = within +/-${o['even_band']:,.0f}.\n"
          f"Many-bet chances include the chance the model itself is off (it would hit every\n"
          f"bet at once). Suggested size is only as good as the model's probability.")

    print("\nWHY")
    for w in r["why"]:
        print(f"  {w['sign']} {w['text']}")
    print("\nCAUTION: " + " ".join(r["cautions"]))
    for w in r["warnings"]:
        print(f"Warning: {w}")


def print_details(r):
    d = r["details"]
    sh = d["central_weight_shares"]
    print(f"\n----- DETAILS (central weights: arsenal {100*sh['arsenal']:.0f}%, batter "
          f"{100*sh['batter']:.0f}%, matchup {100*sh['matchup']:.0f}%) -----")
    for k, info in d["files"].items():
        print(f'File {k}: {info["path"]}  [column "{info["column"]}"]')
    f = lambda x, s=1: "   -" if x is None else f"{s*x:.1f}"
    print(f"\n{'Pitch type':<17}{'A%':>7}{'B%':>7}{'C%':>7}{'Used%':>8}   "
          f"{'A mph':>6}{'C mph':>7}{'(n)':>5}{'Used':>7}{'P(>line)':>10}")
    for t in d["pitch_types"]:
        print(f"{t['name']:<17}{f(t['pct_arsenal'], 100):>7}{f(t['pct_batter'], 100):>7}"
              f"{f(t['pct_matchup'], 100):>7}{100*t['pct_used']:>8.1f}   "
              f"{f(t['mph_arsenal']):>6}{f(t['mph_matchup']):>7}{t['n_matchup']:>5}"
              f"{t['mph_used']:>7.2f}{100*t['p_over_line']:>9.1f}%")
    if d["batter_file_coverage"] is not None:
        print(f"(B is cut to this pitcher's types: they cover {100*d['batter_file_coverage']:.0f}% "
              f"of what the batter saw. B's speeds are other pitchers' and are not used.)")
    print(f"Predicted mean {d['mean_mph']:.2f} mph, SD {d['sd_mph']:.2f} mph (central weights). "
          f"Single-bell P(over) would be {100*d['single_bell_p_over']:.1f}%.")
    lo, hi = r["p_over_90_range"]
    print(f"P(over): {100*r['p_over']:.1f}% overall, 90% range across simulations "
          f"{100*lo:.0f}-{100*hi:.0f}%")
    if d["p_over_season_only"] is not None:
        print(f"P(over) season data only: {100*d['p_over_season_only']:.1f}%   "
              f"matchup only: {100*d['p_over_matchup_only']:.1f}%")
    print(f"Book: vig {100*r['line']['vig']:.1f}%, no-vig P(over) "
          f"{100*r['line']['book_no_vig_p_over']:.1f}%")


def plot_result(r):
    import matplotlib.pyplot as plt
    pl, L = r["plot"], r["line"]["bet_line"]
    v = pl["x_mph"]
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    plt.figure(figsize=(9, 5.5), facecolor="w")
    for j, (name, y) in enumerate(pl["by_type"].items()):
        c = colors[j % 10]
        plt.plot(v, y, color=0.5 * c[:3] + 0.5, linewidth=1, label=name + " (assumed SD)")
    plt.plot(v, pl["combined"], "k-", linewidth=2.5, label="Combined model")
    if "season_only" in pl:
        plt.plot(v, pl["season_only"], "b--", linewidth=1.5, label="Season data only")
    if "matchup_only" in pl:
        plt.plot(v, pl["matchup_only"], ":", color="orange", linewidth=2, label="Matchup only")
    plt.fill_between(v, pl["combined"], where=(v >= L), color="green", alpha=0.15,
                     label=f"OVER {L:g} region")
    plt.axvline(L, color="green", linewidth=1.5, label=f"Bet line {L:g} mph")
    plt.xlabel("Velocity (mph)")
    plt.ylabel("Probability density")
    a = r["answer"]
    ans = f"BET {a['side']} [{a['level']}]" if a["bet"] else "NO BET"
    plt.title(f"Answer: {ans}  --  P(over {L:g}) = {100*r['p_over']:.1f}%")
    plt.legend(loc="upper left", fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def main():
    r = run_model()
    print_report(r)
    if show_details:
        print_details(r)
    if output_json:
        out = in_model_dir(output_json)
        with open(out, "w") as fh:
            json.dump(to_json(r), fh, indent=2)
        print(f"\nAll results saved to {out}")
    if show_plot:
        plot_result(r)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
