# AGENTS.md

## Project overview

Static website for Monte Carlo simulation of the 2026 FIFA World Cup. Runs entirely client-side in the browser using vanilla JavaScript — no build tools or frameworks.

## Architecture

- `build_data.py` — Python script that preprocesses CSV data into a compact JSON file (`data/simulation_data.json`)
- `index.html` + `style.css` — Static frontend using Alpine.js, loads JSON and runs the simulation
- `data/` — Raw CSV data (ELO ratings, international match results)

## Development workflow

### Regenerating data

If ELO ratings, fixtures, or played results (`data/results.json`) change:

```bash
uv run build_data.py
```

This reads `data/elo_ratings_wc2026.csv` and `data/international_results/results.csv`, calibrates the scoring model, hashes `results.json` into a deterministic seed, and writes `data/simulation_data.json`.

**Regenerating the PRNG seed**: Edit `data/results.json`, then re-run `uv run build_data.py`. The seed is a SHA-256 hash of `results.json` (first 4 bytes) stored in `simulation_data.json` as the `seed` field. The client uses this seed with the mulberry32 PRNG so simulations are reproducible.

### Simulation

The Monte Carlo simulation (10K iterations) runs server-side in `build_data.py` and is stored in `simulation_data.json` under the `simulation` key. The client loads pre-computed results on startup — no client-side simulation needed. The JavaScript simulation code is retained for re-simulation when the user edits match scores.

### Testing

Open `index.html` directly in a browser (file:// protocol works, no server needed). Verify:

- Auto-simulates on load with 10K iterations
- Toggle between "Expected Results" and "Probabilities" mode
- Click any group card → modal shows:
  - Per-match W/D/L probabilities with colored bars
  - Editable score inputs for unplayed matches (re-simulates on change)
  - Expected group standings
  - Qualification probabilities per team
- Champion probability cards update correctly
- Knockout bracket shows expected matchups in expected results mode

### Key data files

| File | Description |
|------|-------------|
| `data/elo_ratings_wc2026.csv` | ELO ratings for all 48 qualified teams, 1901–2026 |
| `data/international_results/results.csv` | 49,000+ international match results, 1872–2026 |
| `data/results.json` | Manually updated match results for played WC 2026 games |
| `data/simulation_data.json` | Generated JSON consumed by the frontend |

### Name mapping

The ELO data uses "Czechia" but the fixture data uses "Czech Republic". The `NAME_MAP` in `build_data.py` handles this conversion.

## Code conventions

- **index.html**: Single file with Alpine.js (`x-data`, `x-for`, etc.). All simulation logic is inline `<script>`.
- **No build tools**: Pure vanilla JS via Alpine.js CDN, no npm packages, no bundler.
- **CSS**: [Catppuccin Macchiato](https://catppuccin.com/) dark theme with these key colors: `#1e1e2e` (base bg), `#cdd6f4` (text), `#89b4fa` (accent blue), `#a6e3a1` (green), `#f38ba8` (red), `#f9e2af` (yellow), `#fab387` (peach). Use these when adding new UI elements.
- **Python**: Standard library only for build script (csv, json, math).

## Simulation model

The ELO-based Poisson model:

```
λ_team = base_rate × exp((ELO_diff) / (2 × scale))
```

Calibrated parameters (from `build_data.py` output):
- `base_rate`: ~1.15 goals/team/match
- `scale`: ~250 ELO points
- `home_advantage`: ~90 ELO points

Knockout matches use extra time + penalties if drawn after 90 minutes.
