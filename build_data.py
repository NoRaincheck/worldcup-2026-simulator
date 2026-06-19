import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")
ELO_FILE = DATA_DIR / "elo_ratings_wc2026.csv"
RESULTS_FILE = DATA_DIR / "international_results" / "results.csv"
PLAYED_FILE = DATA_DIR / "results.json"
OUTPUT_FILE = DATA_DIR / "simulation_data.json"

GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

NAME_MAP = {"Czech Republic": "Czechia"}
ELO_TO_FIXTURE = {v: k for k, v in NAME_MAP.items()}

HOSTS = {"Mexico", "United States", "Canada"}

KNOCKOUT_BRACKET = {
    "round_of_32": [
        ["2A", "2B"],
        ["1E", "3rd_1"],
        ["1F", "2C"],
        ["1C", "2F"],
        ["1I", "3rd_2"],
        ["2E", "2I"],
        ["1A", "3rd_3"],
        ["1L", "3rd_4"],
        ["1D", "3rd_5"],
        ["1G", "3rd_6"],
        ["2K", "2L"],
        ["1H", "2J"],
        ["1B", "3rd_7"],
        ["1J", "2H"],
        ["1K", "3rd_8"],
        ["2D", "2G"],
    ],
    "round_of_16": [
        ["R32_M1", "R32_M3"],
        ["R32_M2", "R32_M5"],
        ["R32_M4", "R32_M6"],
        ["R32_M7", "R32_M8"],
        ["R32_M11", "R32_M12"],
        ["R32_M9", "R32_M10"],
        ["R32_M14", "R32_M16"],
        ["R32_M13", "R32_M15"],
    ],
    "quarter_finals": [
        ["R16_M1", "R16_M2"],
        ["R16_M5", "R16_M6"],
        ["R16_M3", "R16_M4"],
        ["R16_M7", "R16_M8"],
    ],
    "semi_finals": [["QF_M1", "QF_M2"], ["QF_M3", "QF_M4"]],
    "final": [["SF_M1", "SF_M2"]],
    "third_place": [["SF_L1", "SF_L2"]],
}


def fixture_name_to_elo(name):
    return NAME_MAP.get(name, name)


def load_played_results():
    """Load already-played match results from results.json."""
    if not PLAYED_FILE.exists():
        return {}
    with open(PLAYED_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_elo_ratings():
    all_fixture_names = {t for group in GROUPS.values() for t in group}
    elo_name_to_fixture_map = {}
    for name in all_fixture_names:
        elo_name_to_fixture_name = fixture_name_to_elo(name)
        elo_name_to_fixture_map[elo_name_to_fixture_name] = name

    teams = {}
    with open(ELO_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["snapshot_date"] == "2026-05-27":
                elo_name = row["country"]
                if elo_name in elo_name_to_fixture_map:
                    fixture_name = elo_name_to_fixture_map[elo_name]
                    teams[fixture_name] = {
                        "elo": int(row["rating"]),
                        "code": row["country_code"],
                        "confederation": row["confederation"],
                        "is_host": row["is_host"] == "1",
                        "rank": int(row["rank"]),
                    }
    return teams


def build_fixtures(played_results):
    """Extract WC 2026 fixtures, merging in played results from results.json."""
    fixtures = []
    with open(RESULTS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["tournament"] == "FIFA World Cup" and row["date"] >= "2026-06-11":
                fixtures.append(
                    {
                        "home": row["home_team"],
                        "away": row["away_team"],
                        "date": row["date"],
                        "venue": row["city"],
                        "country": row["country"],
                        "neutral": row["neutral"] == "TRUE",
                    }
                )

    # Merge played results
    for date, matches in played_results.items():
        for m in matches:
            key = (m["home"], m["away"])
            for fix in fixtures:
                if (
                    fix["date"] == date
                    and fix["home"] == m["home"]
                    and fix["away"] == m["away"]
                ):
                    fix["home_score"] = m["home_score"]
                    fix["away_score"] = m["away_score"]
                    break

    return fixtures


def assign_fixtures_to_groups(fixtures):
    team_to_group = {}
    for group, teams in GROUPS.items():
        for team in teams:
            team_to_group[team] = group

    group_fixtures = defaultdict(list)
    for fix in fixtures:
        home_group = team_to_group.get(fix["home"])
        away_group = team_to_group.get(fix["away"])
        if home_group and away_group and home_group == away_group:
            group_fixtures[home_group].append(fix)
    return dict(group_fixtures)


def calibrate_model(results_file):
    elo_by_team_year = defaultdict(dict)
    with open(ELO_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            elo_by_team_year[row["country"]][int(row["year"])] = int(row["rating"])

    matches = []
    with open(results_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year = int(row["date"][:4])
            if year < 2000 or row["home_score"] == "NA":
                continue
            tournament = row["tournament"]
            if tournament not in (
                "FIFA World Cup",
                "FIFA World Cup qualification",
                "UEFA Euro",
                "UEFA Euro qualification",
                "Copa América",
                "Copa América qualification",
                "Africa Cup of Nations",
                "Africa Cup of Nations qualification",
                "Asian Cup",
                "Asian Cup qualification",
                "CONCACAF Gold Cup",
                "CONCACAF Gold Cup qualification",
                "FIFA World Cup qualification (inter-confederation playoffs)",
            ):
                continue
            home_elo = elo_by_team_year.get(row["home_team"], {}).get(year)
            away_elo = elo_by_team_year.get(row["away_team"], {}).get(year)
            if not home_elo or not away_elo:
                continue
            matches.append(
                {
                    "home_elo": home_elo,
                    "away_elo": away_elo,
                    "home_goals": int(row["home_score"]),
                    "away_goals": int(row["away_score"]),
                    "neutral": row["neutral"] == "TRUE",
                }
            )

    if not matches:
        return {"base_rate": 1.35, "scale": 400, "home_advantage": 100}

    best_loss = float("inf")
    best_params = {"base_rate": 1.35, "scale": 400, "home_advantage": 100}
    for base_rate in [x / 100 for x in range(100, 180, 5)]:
        for scale in range(200, 600, 25):
            for home_adv in range(50, 200, 10):
                loss = 0
                for m in matches:
                    elo_diff = m["home_elo"] - m["away_elo"]
                    if not m["neutral"]:
                        elo_diff += home_adv
                    lh = max(
                        0.1, min(5.0, base_rate * math.exp(elo_diff / (2 * scale)))
                    )
                    la = max(
                        0.1, min(5.0, base_rate * math.exp(-elo_diff / (2 * scale)))
                    )
                    loss += (lh - m["home_goals"]) ** 2 + (la - m["away_goals"]) ** 2
                if loss < best_loss:
                    best_loss = loss
                    best_params = {
                        "base_rate": base_rate,
                        "scale": scale,
                        "home_advantage": home_adv,
                    }
    return best_params


def strip_played_results(data):
    """Deep-copy data and clear all played match scores for baseline simulation."""
    import copy

    d = copy.deepcopy(data)
    for g, info in d["groups"].items():
        for m in info["matches"]:
            m["home_score"] = None
            m["away_score"] = None
    return d


def hash_results_seed():
    """Hash results.json to produce a deterministic seed for the client-side PRNG."""
    if not PLAYED_FILE.exists():
        return 0
    h = hashlib.sha256()
    h.update(PLAYED_FILE.read_bytes())
    return int.from_bytes(h.digest()[:4], "big")


def poisson_random(lam, rng):
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            break
    return k - 1


MOMENTUM_FACTOR = 1.8  # Multiplier for ELO adjustments during tournament


def elo_adjust(winner_elo, loser_elo, drawn=False, k=20):
    """Calculate ELO adjustment with momentum factor."""
    expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    if drawn:
        return k * (0.5 - expected)
    return k * (1 - expected)


def sim_match(
    home_elo, away_elo, params, rng, knockout=False, home_team=None, away_team=None
):
    elo_diff = home_elo - away_elo
    ha = params["home_advantage"]
    if home_team in HOSTS:
        elo_diff += ha
    if away_team in HOSTS:
        elo_diff -= ha
    br = params["base_rate"]
    sc = params["scale"]
    lh = max(0.1, br * math.exp(elo_diff / (2 * sc)))
    la = max(0.1, br * math.exp(-elo_diff / (2 * sc)))
    hg = poisson_random(lh, rng)
    ag = poisson_random(la, rng)
    if knockout and hg == ag:
        avg = (lh + la) / 2
        hg += poisson_random(max(0.1, avg * 0.85 + (lh - avg) * 0.3), rng)
        ag += poisson_random(max(0.1, avg * 0.85 + (la - avg) * 0.3), rng)
        if hg == ag:
            wp = 1 / (1 + 10 ** (-(home_elo - away_elo) / 400))
            if rng.random() < wp:
                hg += 1
            else:
                ag += 1
    return hg, ag


def apply_momentum(elo_ratings, home, away, hg, ag):
    """Apply momentum-adjusted ELO changes after a match."""
    if hg > ag:
        adj = elo_adjust(elo_ratings[home], elo_ratings[away]) * MOMENTUM_FACTOR
        elo_ratings[home] += adj
        elo_ratings[away] -= adj
    elif hg < ag:
        adj = elo_adjust(elo_ratings[away], elo_ratings[home]) * MOMENTUM_FACTOR
        elo_ratings[away] += adj
        elo_ratings[home] -= adj
    else:
        adj = (
            elo_adjust(elo_ratings[home], elo_ratings[away], drawn=True)
            * MOMENTUM_FACTOR
        )
        elo_ratings[home] += adj
        elo_ratings[away] -= adj


def sort_group(st, match_results):
    """Sort group standings using FIFA tiebreakers including head-to-head.

    Tiebreaking order:
    1. Points (all group matches)
    2. Goal difference (all group matches)
    3. Goals scored (all group matches)
    4. Points (head-to-head among tied teams)
    5. Goal difference (head-to-head among tied teams)
    6. Goals scored (head-to-head among tied teams)
    """
    teams = list(st.keys())
    if len(teams) <= 1:
        result = []
        for idx, t in enumerate(teams):
            entry = dict(st[t])
            entry["pos"] = idx + 1
            result.append(entry)
        return result

    def primary_key(team):
        return (st[team]["pts"], st[team]["gd"], st[team]["gf"])

    sorted_teams = sorted(teams, key=primary_key, reverse=True)

    result = []
    i = 0
    while i < len(sorted_teams):
        pk = primary_key(sorted_teams[i])
        tied = []
        while i < len(sorted_teams) and primary_key(sorted_teams[i]) == pk:
            tied.append(sorted_teams[i])
            i += 1

        if len(tied) > 1:
            h2h = {t: {"pts": 0, "gd": 0, "gf": 0} for t in tied}
            for m in match_results:
                home, away, hg, ag = m["home"], m["away"], m["hg"], m["ag"]
                if home in h2h and away in h2h:
                    if hg > ag:
                        h2h[home]["pts"] += 3
                    elif hg < ag:
                        h2h[away]["pts"] += 3
                    else:
                        h2h[home]["pts"] += 1
                        h2h[away]["pts"] += 1
                    h2h[home]["gd"] += hg - ag
                    h2h[home]["gf"] += hg
                    h2h[away]["gd"] += ag - hg
                    h2h[away]["gf"] += ag

            def h2h_key(team):
                return (h2h[team]["pts"], h2h[team]["gd"], h2h[team]["gf"])

            tied.sort(key=h2h_key, reverse=True)

        result.extend(tied)

    sorted_st = []
    for idx, team in enumerate(result):
        entry = dict(st[team])
        entry["pos"] = idx + 1
        sorted_st.append(entry)
    return sorted_st


def best_third_from_standings(sorted_groups):
    thirds = []
    for g, st in sorted_groups.items():
        if len(st) >= 3:
            t = st[2]
            thirds.append(
                {
                    "team": t["team"],
                    "group": g,
                    "pts": t["pts"],
                    "gd": t["gd"],
                    "gf": t["gf"],
                }
            )
    thirds.sort(key=lambda x: (-x["pts"], -x["gd"], -x["gf"]))
    return thirds[:8]


def sim_knockout(sorted_groups, bracket, elo_ratings, params, rng):
    btp = best_third_from_standings(sorted_groups)

    def resolve(slot):
        if slot.startswith("1"):
            g = slot[1]
            return (
                sorted_groups[g][0]["team"]
                if g in sorted_groups and sorted_groups[g]
                else None
            )
        if slot.startswith("2"):
            g = slot[1]
            return (
                sorted_groups[g][1]["team"]
                if g in sorted_groups and len(sorted_groups[g]) > 1
                else None
            )
        if slot.startswith("3rd_"):
            idx = int(slot.split("_")[1]) - 1
            return btp[idx]["team"] if idx < len(btp) else None
        return None

    b = {}
    for rn in ["round_of_32", "round_of_16", "quarter_finals", "semi_finals"]:
        b[rn] = []
        for hs, as_ in bracket[rn]:
            if hs.startswith(("R", "QF", "SF")):
                pr = (
                    "round_of_32"
                    if hs.startswith("R32")
                    else "round_of_16"
                    if hs.startswith("R16")
                    else "quarter_finals"
                    if hs.startswith("QF")
                    else "semi_finals"
                )
                home = (
                    b[pr][int(hs.split("_M")[1]) - 1]["winner"] if b.get(pr) else None
                )
            else:
                home = resolve(hs)
            if as_.startswith(("R", "QF", "SF")):
                pr = (
                    "round_of_32"
                    if as_.startswith("R32")
                    else "round_of_16"
                    if as_.startswith("R16")
                    else "quarter_finals"
                    if as_.startswith("QF")
                    else "semi_finals"
                )
                away = (
                    b[pr][int(as_.split("_M")[1]) - 1]["winner"] if b.get(pr) else None
                )
            else:
                away = resolve(as_)
            if not home or not away:
                b[rn].append(
                    {
                        "home": home or "TBD",
                        "away": away or "TBD",
                        "winner": None,
                        "hg": 0,
                        "ag": 0,
                    }
                )
                continue
            hg, ag = sim_match(
                elo_ratings[home],
                elo_ratings[away],
                params,
                rng,
                True,
                home_team=home,
                away_team=away,
            )
            apply_momentum(elo_ratings, home, away, hg, ag)
            b[rn].append(
                {
                    "home": home,
                    "away": away,
                    "winner": home if hg >= ag else away,
                    "hg": hg,
                    "ag": ag,
                }
            )
    sf = b.get("semi_finals", [])
    if len(sf) == 2 and sf[0]["winner"] and sf[1]["winner"]:
        h, a = sf[0]["winner"], sf[1]["winner"]
        hg, ag = sim_match(
            elo_ratings[h], elo_ratings[a], params, rng, True, home_team=h, away_team=a
        )
        apply_momentum(elo_ratings, h, a, hg, ag)
        b["final"] = [
            {"home": h, "away": a, "winner": h if hg >= ag else a, "hg": hg, "ag": ag}
        ]
    else:
        b["final"] = [{"home": "TBD", "away": "TBD", "winner": None, "hg": 0, "ag": 0}]
    return b


def run_simulation(data, n=10000):
    teams = data["teams"]
    params = data["model_params"]
    bracket = data["knockout_bracket"]
    seed = data["seed"]
    rng = random.Random(seed)

    team_stats = {
        t: {
            "champion": 0,
            "finalist": 0,
            "semifinalist": 0,
            "quarterfinalist": 0,
            "round16": 0,
            "round32": 0,
            "groupWinner": 0,
            "groupRunnerUp": 0,
            "groupThird": 0,
            "groupFourth": 0,
            "totalPoints": 0.0,
            "totalGoalsFor": 0.0,
            "totalGoalsAgainst": 0.0,
            "matchesPlayed": 0.0,
            "totalWins": 0.0,
            "totalDraws": 0.0,
            "totalLosses": 0.0,
        }
        for t in teams
    }

    match_stats = {}
    for g, info in data["groups"].items():
        match_stats[g] = {}
        for m in info["matches"]:
            match_stats[g][m["home"] + "|" + m["away"]] = {"w": 0, "d": 0, "l": 0}

    ko_stats = {}

    for _ in range(n):
        elo_ratings = {t: teams[t]["elo"] for t in teams}
        sorted_groups = {}
        for g, info in data["groups"].items():
            st = {
                t: {
                    "team": t,
                    "p": 0,
                    "w": 0,
                    "d": 0,
                    "l": 0,
                    "gf": 0,
                    "ga": 0,
                    "pts": 0,
                }
                for t in info["teams"]
            }
            group_results = []
            for m in info["matches"]:
                home, away = m["home"], m["away"]
                if m.get("home_score") is not None:
                    hg, ag = m["home_score"], m["away_score"]
                else:
                    hg, ag = sim_match(
                        elo_ratings[home],
                        elo_ratings[away],
                        params,
                        rng,
                        home_team=home,
                        away_team=away,
                    )
                apply_momentum(elo_ratings, home, away, hg, ag)
                group_results.append({"home": home, "away": away, "hg": hg, "ag": ag})
                h, a = st[home], st[away]
                h["p"] += 1
                a["p"] += 1
                h["gf"] += hg
                h["ga"] += ag
                a["gf"] += ag
                a["ga"] += hg
                if hg > ag:
                    h["w"] += 1
                    h["pts"] += 3
                    a["l"] += 1
                elif hg < ag:
                    a["w"] += 1
                    a["pts"] += 3
                    h["l"] += 1
                else:
                    h["d"] += 1
                    h["pts"] += 1
                    a["d"] += 1
                    a["pts"] += 1
                key = home + "|" + away
                if hg > ag:
                    match_stats[g][key]["w"] += 1
                elif hg < ag:
                    match_stats[g][key]["l"] += 1
                else:
                    match_stats[g][key]["d"] += 1
            for t in st.values():
                t["gd"] = t["gf"] - t["ga"]
            sl = sort_group(st, group_results)
            for i, t in enumerate(sl):
                t["pos"] = i + 1
            sorted_groups[g] = sl
            for t in sl:
                ts = team_stats[t["team"]]
                ts["totalPoints"] += t["pts"]
                ts["totalGoalsFor"] += t["gf"]
                ts["totalGoalsAgainst"] += t["ga"]
                ts["matchesPlayed"] += t["p"]
                ts["totalWins"] += t["w"]
                ts["totalDraws"] += t["d"]
                ts["totalLosses"] += t["l"]
                if t["pos"] == 1:
                    ts["groupWinner"] += 1
                elif t["pos"] == 2:
                    ts["groupRunnerUp"] += 1
                elif t["pos"] == 3:
                    ts["groupThird"] += 1
                else:
                    ts["groupFourth"] += 1

        ko = sim_knockout(sorted_groups, bracket, elo_ratings, params, rng)
        for rn, matches in ko.items():
            for i, m in enumerate(matches):
                key = rn + "_" + str(i)
                if key not in ko_stats:
                    ko_stats[key] = {
                        "w": 0,
                        "d": 0,
                        "l": 0,
                        "hg": 0,
                        "ag": 0,
                        "scorelines": {},
                    }
                ks = ko_stats[key]
                if m["home"] == "TBD" or m["away"] == "TBD":
                    continue
                ks["hg"] += m["hg"]
                ks["ag"] += m["ag"]
                sl = str(m["hg"]) + "-" + str(m["ag"])
                ks["scorelines"][sl] = ks["scorelines"].get(sl, 0) + 1
                if m["hg"] > m["ag"]:
                    ks["w"] += 1
                elif m["hg"] < m["ag"]:
                    ks["l"] += 1
                else:
                    ks["d"] += 1
                for tm in [m["home"], m["away"]]:
                    if tm in team_stats:
                        if rn == "round_of_32":
                            team_stats[tm]["round32"] += 1
                        elif rn == "round_of_16":
                            team_stats[tm]["round16"] += 1
                        elif rn == "quarter_finals":
                            team_stats[tm]["quarterfinalist"] += 1
                        elif rn == "semi_finals":
                            team_stats[tm]["semifinalist"] += 1
                if rn == "final" and m["winner"]:
                    team_stats[m["winner"]]["champion"] += 1
                    team_stats[m["home"]]["finalist"] += 1
                    team_stats[m["away"]]["finalist"] += 1

    for t in team_stats:
        for k in team_stats[t]:
            team_stats[t][k] = team_stats[t][k] / n

    avg_ko = {}
    for rn, matches in ko.items():
        avg_ko[rn] = []
        for i, m in enumerate(matches):
            key = rn + "_" + str(i)
            ks = ko_stats.get(key, {})
            total = ks.get("w", 0) + ks.get("d", 0) + ks.get("l", 0)
            if total > 0:
                ah = ks["hg"] / total
                aa = ks["ag"] / total
                winner = m["home"] if ah >= aa else m["away"]
            else:
                ah, aa = float(m["hg"]), float(m["ag"])
                winner = m["winner"]
            avg_ko[rn].append(
                {
                    "home": m["home"],
                    "away": m["away"],
                    "winner": winner,
                    "hg": round(ah, 1),
                    "ag": round(aa, 1),
                }
            )

    return {
        "N": n,
        "team_stats": team_stats,
        "match_stats": match_stats,
        "knockout_stats": ko_stats,
        "knockout_bracket": avg_ko,
    }


def compute_prob_history(data, played_results, n=10000):
    """Compute per-date probability snapshots for qualify and win probabilities."""
    if not played_results:
        return {"dates": [], "qualify": {}, "win": {}}

    dates = sorted(played_results.keys())

    history = {
        "dates": [],
        "qualify": {t: [] for t in data["teams"]},
        "win": {t: [] for t in data["teams"]},
    }

    # Baseline (no results played)
    baseline = strip_played_results(data)
    baseline["seed"] = 0
    sim = run_simulation(baseline, n)
    for t in data["teams"]:
        s = sim["team_stats"][t]
        history["qualify"][t].append(
            round((s["groupWinner"] + s["groupRunnerUp"]) * 100, 1)
        )
        history["win"][t].append(round(s["champion"] * 100, 1))
    history["dates"].append("Baseline")

    # Each date prefix (cumulative)
    partial = {}
    for date in dates:
        partial[date] = played_results[date]
        fixtures = build_fixtures(partial)
        group_fix = assign_fixtures_to_groups(fixtures)

        groups_output = {}
        for g in sorted(GROUPS.keys()):
            matches = group_fix.get(g, [])
            groups_output[g] = {
                "teams": GROUPS[g],
                "matches": [
                    {
                        "home": m["home"],
                        "away": m["away"],
                        "date": m["date"],
                        "venue": m["venue"],
                        "neutral": m["neutral"],
                        "home_score": m.get("home_score"),
                        "away_score": m.get("away_score"),
                    }
                    for m in sorted(matches, key=lambda x: x["date"])
                ],
            }

        h = hashlib.sha256()
        h.update(json.dumps(partial, sort_keys=True).encode())
        date_seed = int.from_bytes(h.digest()[:4], "big")

        date_data = {
            "teams": data["teams"],
            "groups": groups_output,
            "knockout_bracket": KNOCKOUT_BRACKET,
            "model_params": data["model_params"],
            "seed": date_seed,
        }

        sim = run_simulation(date_data, n)
        for t in data["teams"]:
            s = sim["team_stats"][t]
            history["qualify"][t].append(
                round((s["groupWinner"] + s["groupRunnerUp"]) * 100, 1)
            )
            history["win"][t].append(round(s["champion"] * 100, 1))

        history["dates"].append(date)

    return history


def main():
    print("Loading ELO ratings...")
    teams = load_elo_ratings()
    print(f"  Found {len(teams)} teams")

    print("Loading played results...")
    played_results = load_played_results()
    played_count = sum(len(v) for v in played_results.values())
    print(f"  {played_count} matches already played")

    print("Computing RNG seed from results.json...")
    seed = hash_results_seed()
    print(f"  Seed: {seed}")

    print("Building fixtures...")
    all_fixtures = build_fixtures(played_results)
    group_fixtures = assign_fixtures_to_groups(all_fixtures)
    total = sum(len(v) for v in group_fixtures.values())
    played = sum(1 for f in all_fixtures if f.get("home_score") is not None)
    print(f"  {total} group matches ({played} played, {total - played} remaining)")

    print("Calibrating scoring model...")
    model_params = calibrate_model(RESULTS_FILE)
    print(
        f"  base_rate={model_params['base_rate']:.2f}, scale={model_params['scale']}, home_adv={model_params['home_advantage']}"
    )

    groups_output = {}
    for g in sorted(GROUPS.keys()):
        matches = group_fixtures.get(g, [])
        groups_output[g] = {
            "teams": GROUPS[g],
            "matches": [
                {
                    "home": m["home"],
                    "away": m["away"],
                    "date": m["date"],
                    "venue": m["venue"],
                    "neutral": m["neutral"],
                    "home_score": m.get("home_score"),
                    "away_score": m.get("away_score"),
                }
                for m in sorted(matches, key=lambda x: x["date"])
            ],
        }

    data = {
        "teams": teams,
        "groups": groups_output,
        "knockout_bracket": KNOCKOUT_BRACKET,
        "model_params": model_params,
        "seed": seed,
    }

    print("Running simulation (10K iterations)...")
    sim = run_simulation(data, 10000)
    data["simulation"] = sim
    print(
        f"  Done — champion prob range: {min(s['champion'] for s in sim['team_stats'].values()):.1%} – {max(s['champion'] for s in sim['team_stats'].values()):.1%}"
    )

    print("Running baseline simulation (no played results)...")
    baseline_data = strip_played_results(data)
    baseline_sim = run_simulation(baseline_data, 10000)
    data["baseline_team_stats"] = baseline_sim["team_stats"]
    print(
        f"  Done — baseline champion prob range: {min(s['champion'] for s in baseline_sim['team_stats'].values()):.1%} – {max(s['champion'] for s in baseline_sim['team_stats'].values()):.1%}"
    )

    print("Computing per-date probability history...")
    prob_history = compute_prob_history(data, played_results, 10000)
    data["prob_history"] = prob_history
    print(
        f"  Done — {len(prob_history['dates'])} snapshots: {', '.join(prob_history['dates'])}"
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Written to {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
