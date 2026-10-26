# simulator/views.py
import json
import random
from collections import defaultdict
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

TEAM_COUNT = 16
WEAK_TEAM_START = 9  # 1-based team id
BATCH_RUNS = 10000

def index(request):
    return render(request, 'index.html')

def simulate_match(team_a, team_b, win_rate, is_bo3=False):
    games = []
    wins_a = 0
    wins_b = 0
    while wins_a < 2 and wins_b < 2:
        if random.random() < win_rate:
            winner = team_a
            wins_a += 1
        else:
            winner = team_b
            wins_b += 1
        games.append(winner)
        if not is_bo3:
            break
        if wins_a == 2 or wins_b == 2:
            break
    final_winner = team_a if wins_a > wins_b else team_b
    return final_winner, games

def get_match_format(wins, losses):
    return (wins == 2 or losses == 2)

def generate_pairings_with_rules(group, past_matchups, regions, max_attempts=100):
    n = len(group)
    if n % 2 != 0:
        raise ValueError("Group size must be even")
    team_ids = [t['id'] for t in group]

    def check_pairing(pairing):
        pair_violations = []
        for a, b in pairing:
            viol = []
            if (a, b) in past_matchups or (b, a) in past_matchups:
                viol.append('rule1')
            if regions[a] == regions[b]:
                viol.append('rule2')
            pair_violations.append('+'.join(viol) if viol else 'ok')
        return pair_violations

    # Stage 1: both rules
    for _ in range(max_attempts):
        shuffled = team_ids[:]
        random.shuffle(shuffled)
        pairing = [(shuffled[i], shuffled[i+1]) for i in range(0, n, 2)]
        violations = check_pairing(pairing)
        if all(v == 'ok' for v in violations):
            return pairing, violations

    # Stage 2: only rule1
    for _ in range(max_attempts):
        shuffled = team_ids[:]
        random.shuffle(shuffled)
        pairing = [(shuffled[i], shuffled[i+1]) for i in range(0, n, 2)]
        violations = check_pairing(pairing)
        if all('rule1' not in v for v in violations):
            return pairing, violations

    # Stage 3: only rule2
    for _ in range(max_attempts):
        shuffled = team_ids[:]
        random.shuffle(shuffled)
        pairing = [(shuffled[i], shuffled[i+1]) for i in range(0, n, 2)]
        violations = check_pairing(pairing)
        if all('rule2' not in v for v in violations):
            return pairing, violations

    # Fallback
    shuffled = team_ids[:]
    random.shuffle(shuffled)
    pairing = [(shuffled[i], shuffled[i+1]) for i in range(0, n, 2)]
    violations = check_pairing(pairing)
    return pairing, violations

def run_single_simulation(win_rates, team_names=None, regions=None):
    if team_names is None:
        team_names = [str(i + 1) for i in range(16)]
    if regions is None:
        regions = list(range(1, 17))

    teams = [{'id': i, 'wins': 0, 'losses': 0, 'active': True} for i in range(16)]
    past_matchups = set()
    rounds_log = []

    for round_num in range(1, 6):
        active_teams = [t for t in teams if t['active']]
        if not active_teams:
            break

        groups = defaultdict(list)
        for t in active_teams:
            groups[(t['wins'], t['losses'])].append(t)

        # Sort groups by (wins - losses) descending, then by wins descending
        sorted_group_keys = sorted(groups.keys(), key=lambda x: (x[0] - x[1], x[0]), reverse=True)
        
        round_pools = []
        for key in sorted_group_keys:
            group = groups[key]
            if len(group) == 0:
                continue
            pairings, violations = generate_pairings_with_rules(group, past_matchups, regions)

            is_bo3 = get_match_format(key[0], key[1])
            pool_matches = []
            for idx, (t1_id, t2_id) in enumerate(pairings):
                t1 = next(t for t in teams if t['id'] == t1_id)
                t2 = next(t for t in teams if t['id'] == t2_id)

                win_rate = win_rates[t1_id][t2_id]
                winner, games = simulate_match(t1_id, t2_id, win_rate, is_bo3)

                if winner == t1_id:
                    t1['wins'] += 1
                    t2['losses'] += 1
                else:
                    t2['wins'] += 1
                    t1['losses'] += 1

                for t in [t1, t2]:
                    if t['wins'] == 3 or t['losses'] == 3:
                        t['active'] = False

                past_matchups.add((t1_id, t2_id))

                viol_msg = None
                if violations[idx] == 'rule1':
                    viol_msg = "违反规则1：重复对战"
                elif violations[idx] == 'rule2':
                    viol_msg = "违反规则2：同赛区对战"
                elif violations[idx] == 'rule1+rule2':
                    viol_msg = "违反规则1和2：重复且同赛区"

                pool_matches.append({
                    'team1': t1_id + 1,
                    'team2': t2_id + 1,
                    'team1_name': team_names[t1_id],
                    'team2_name': team_names[t2_id],
                    'games': [g + 1 for g in games],
                    'bo3': is_bo3,
                    'winner': winner + 1,
                    'violation': viol_msg
                })

            round_pools.append({
                'pool_name': f"{key[0]}-{key[1]}",
                'matches': pool_matches
            })

        rounds_log.append({'round': round_num, 'pools': round_pools})

        if all(not t['active'] for t in teams):
            break

    qualifiers = [i + 1 for i, t in enumerate(teams) if t['wins'] == 3]
    return {'rounds': rounds_log, 'qualifiers': sorted(qualifiers)}

def run_single_group_simulation(win_rates, team_names=None, regions=None, group_count=4):
    # One 16-team group stage.
    if team_names is None:
        team_names = [str(i + 1) for i in range(TEAM_COUNT)]
    if regions is None:
        regions = list(range(1, TEAM_COUNT + 1))
    if group_count not in (1, 2, 4, 8):
        group_count = 4
    group_size = TEAM_COUNT // group_count
    shuffled = list(range(TEAM_COUNT))
    random.shuffle(shuffled)
    drawn_groups = [shuffled[i:i + group_size] for i in range(0, TEAM_COUNT, group_size)]
    group_logs = []
    qualifiers = []
    for group_idx, team_ids in enumerate(drawn_groups):
        wins = {team_id: 0 for team_id in team_ids}
        losses = {team_id: 0 for team_id in team_ids}
        matches = []

        for i in range(len(team_ids)):
            for j in range(i + 1, len(team_ids)):
                team1_id = team_ids[i]
                team2_id = team_ids[j]
                winner, games = simulate_match(
                    team1_id,
                    team2_id,
                    win_rates[team1_id][team2_id],
                    is_bo3=False,
                )
                loser = team2_id if winner == team1_id else team1_id
                wins[winner] += 1
                losses[loser] += 1
                matches.append({
                    'team1': team1_id + 1,
                    'team2': team2_id + 1,
                    'team1_name': team_names[team1_id],
                    'team2_name': team_names[team2_id],
                    'winner': winner + 1,
                    'winner_name': team_names[winner],
                    'games': [g + 1 for g in games],
                    'bo3': False,
                    'violation': None,
                })
        ranked_ids = sorted(team_ids, key=lambda team_id: (-wins[team_id], team_id))
        qualified_ids = ranked_ids[:2]
        qualifiers.extend(qualified_ids)

        standings = []
        for rank, team_id in enumerate(ranked_ids, 1):
            standings.append({
                'rank': rank,
                'team': team_id + 1,
                'name': team_names[team_id],
                'wins': wins[team_id],
                'losses': losses[team_id],
                'qualified': team_id in qualified_ids,
            })

        group_logs.append({
            'group_name': "Group " + str(group_idx + 1),
            'teams': [team_id + 1 for team_id in team_ids],
            'standings': standings,
            'matches': matches,
        })

    qualifier_ids = sorted(team_id + 1 for team_id in qualifiers)
    return {
        'format': 'group',
        'groups': group_logs,
        'qualifiers': qualifier_ids,
        'weak_count': sum(1 for team_id in qualifier_ids if team_id >= WEAK_TEAM_START),
    }

def _aggregate_multi(runner, win_rates, team_names=None, regions=None, n=BATCH_RUNS):
    count = [0] * 16
    weak_count_freq = defaultdict(int)  # key: number of teams from 9-16 in qualifiers

    for _ in range(n):
        result = runner(win_rates, team_names, regions)
        qualifiers = result['qualifiers']
        # Count how many are in 9-16 (i.e., id >= 9)
        weak_count = sum(1 for q in qualifiers if q >= WEAK_TEAM_START)
        weak_count_freq[weak_count] += 1
        for q in qualifiers:
            count[q - 1] += 1

    # Convert to list of length 9 (0 to 8)
    weak_freq_list = [weak_count_freq[i] for i in range(9)]
    return count, weak_freq_list


def run_multi_simulation(win_rates, team_names=None, regions=None, n=BATCH_RUNS):
    return _aggregate_multi(run_single_simulation, win_rates, team_names, regions, n)


def run_multi_group_simulation(win_rates, team_names=None, regions=None, n=BATCH_RUNS):
    return _aggregate_multi(run_single_group_simulation, win_rates, team_names, regions, n)


@csrf_exempt
def simulate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=400)

    try:
        data = json.loads(request.body)
        win_rates = data.get('win_rates')
        mode = data.get('mode')
        tournament_format = data.get('tournament_format', 'swiss')
        team_names = data.get('team_names', [str(i) for i in range(1, 17)])
        regions = data.get('regions', list(range(1, 17)))
    except Exception as e:
        return JsonResponse({'error': f'Invalid input: {str(e)}'}, status=400)

    if len(win_rates) != 16 or any(len(row) != 16 for row in win_rates):
        return JsonResponse({'error': 'Win rates must be 16x16'}, status=400)
    if len(team_names) != 16 or len(regions) != 16:
        return JsonResponse({'error': 'team_names and regions must be length 16'}, status=400)
    if tournament_format not in ('swiss', 'group'):
        return JsonResponse({'error': 'tournament_format must be swiss or group'}, status=400)

    for i in range(16):
        if win_rates[i][i] != 0:
            return JsonResponse({'error': 'Diagonal must be 0'}, status=400)

    if mode == 'single':
        if tournament_format == 'group':
            result = run_single_group_simulation(win_rates, team_names, regions)
        else:
            result = run_single_simulation(win_rates, team_names, regions)
        return JsonResponse({
            'type': 'single',
            'format': tournament_format,
            'result': result,
        })
    elif mode == 'multi':
        if tournament_format == 'group':
            stats, weak_freq = run_multi_group_simulation(
                win_rates, team_names, regions, n=BATCH_RUNS,
            )
        else:
            stats, weak_freq = run_multi_simulation(
                win_rates, team_names, regions, n=BATCH_RUNS,
            )
        return JsonResponse({
            'type': 'multi',
            'format': tournament_format,
            'runs': BATCH_RUNS,
            'stats': stats,
            'weak_freq': weak_freq,
        })
    else:
        return JsonResponse({'error': 'Invalid mode'}, status=400)
