# FIFA World Cup 2026 — Monte Carlo Simulator

A static website that runs client-side Monte Carlo simulation of the 2026 FIFA World Cup, from group stage through knockout rounds, using ELO ratings and historical match data for calibration.

## How it works

1. **ELO-based Poisson model**: Match outcomes are predicted using team ELO ratings. The expected goals for each team follow a Poisson distribution where the rate parameter λ is derived from the ELO difference between the two teams.

2. **Model calibration**: The model parameters (base scoring rate, ELO scaling factor, home advantage) are calibrated by fitting against ~15,000+ competitive international matches from 2000–2025.

3. **Monte Carlo simulation**: The tournament is simulated thousands of times (default: 10,000) to estimate probabilities for group stage outcomes, qualification, and knockout round progression.

4. **Conditional on played results**: Already-played matches use actual scores. Update `data/results.json` with new match results, then re-run `uv run build_data.py` to regenerate the simulation data.

## Quick start

```bash
# Generate the simulation data JSON
uv run build_data.py

# Open the simulator in your browser
open index.html
```

## Project structure

```
├── build_data.py              # Python: preprocesses CSV data → JSON
├── index.html                 # Main HTML page (Alpine.js, all logic inline)
├── style.css                  # Stylesheet
├── data/
│   ├── elo_ratings_wc2026.csv # Historical ELO ratings for all 48 qualified teams
│   ├── international_results/ # Match results dataset (49,000+ matches)
│   │   ├── results.csv        # Full match results 1872–2026
│   │   ├── goalscorers.csv    # Goal scorer data
│   │   └── shootouts.csv      # Penalty shootout data
│   ├── results.json           # Manually updated match results for played WC 2026 games
│   └── simulation_data.json   # Generated: compact JSON for the web frontend
└── pyproject.toml             # Python dependencies (numpy, polars, scipy)
```

## Data sources

- **ELO ratings**: [World Football Elo Ratings](https://www.eloratings.net/) (Lange, eloratings.net) — historical ratings from 1901 to present
- **Match results**: [international-results](https://github.com/martj42/international_results) (martj42) — 49,000+ international match results from 1872 to 2026

## Technical details

### Frontend

Uses [Alpine.js](https://alpinejs.dev/) (loaded via CDN) for reactive UI. All simulation logic is inline in `index.html` — no build step, no npm, no separate JS files.

```
λ_home = base_rate × exp((ELO_home - ELO_away + home_advantage) / (2 × scale))
λ_away = base_rate × exp((ELO_away - ELO_home - home_advantage) / (2 × scale))
```

- **base_rate**: Average goals per team per match (~1.15)
- **scale**: ELO point scaling factor (~250)
- **home_advantage**: ELO bonus for home team (~90 points)

### Tournament format

- 48 teams in 12 groups of 4
- Top 2 from each group + 8 best third-place teams advance to Round of 32
- Knockout rounds: R32 → R16 → QF → SF → Final (+ Third Place match)

## Hosting

This is a static website designed for GitHub Pages. No build step required — just push to a branch and enable Pages in repository settings.

## License

Data is subject to the licenses of the original sources (CC BY-SA 4.0 for ELO ratings, CC0 for international results).
