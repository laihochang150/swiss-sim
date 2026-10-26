import json
import random
from unittest.mock import patch

from django.test import TestCase

from .views import (
    run_multi_group_simulation,
    run_single_group_simulation,
    run_single_simulation,
)


def make_rates():
    # Lower team id always wins, regardless of match orientation.
    return [
        [0 if i == j else (1 if i < j else 0) for j in range(16)]
        for i in range(16)
    ]


class GroupStageTests(TestCase):
    def setUp(self):
        self.rates = make_rates()
        self.names = [f'Team {i + 1}' for i in range(16)]
        self.regions = list(range(1, 17))

    def test_single_group_stage_shape_and_qualifiers(self):
        random.seed(1)
        result = run_single_group_simulation(self.rates, self.names, self.regions)

        self.assertEqual(result['format'], 'group')
        self.assertEqual(len(result['groups']), 4)
        self.assertEqual(len(result['qualifiers']), 8)

        for group in result['groups']:
            self.assertEqual(len(group['teams']), 4)
            self.assertEqual(len(group['standings']), 4)
            self.assertEqual(len(group['matches']), 6)
            self.assertEqual(sum(1 for row in group['standings'] if row['qualified']), 2)

            lowest_two = set(sorted(group['teams'])[:2])
            qualified = {
                row['team'] for row in group['standings'] if row['qualified']
            }
            self.assertEqual(qualified, lowest_two)

            for team_id in group['teams']:
                played = sum(
                    1 for match in group['matches']
                    if team_id in (match['team1'], match['team2'])
                )
                self.assertEqual(played, 3)

        self.assertEqual(
            result['weak_count'],
            sum(1 for team_id in result['qualifiers'] if team_id >= 9),
        )

    def test_index_page_exposes_tournament_format_selector(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="tournament_format"')
        self.assertContains(response, '小组赛（4 组 × 4 队）')

    def test_multi_group_stage_aggregates_eight_qualifiers_per_run(self):
        random.seed(2)
        count, weak_freq = run_multi_group_simulation(
            self.rates, self.names, self.regions, n=20,
        )

        self.assertEqual(len(count), 16)
        self.assertEqual(sum(count), 20 * 8)
        self.assertEqual(sum(weak_freq), 20)

    def test_group_api_returns_group_payload(self):
        payload = {
            'mode': 'single',
            'tournament_format': 'group',
            'win_rates': self.rates,
            'team_names': self.names,
            'regions': self.regions,
        }
        response = self.client.post(
            '/simulate/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['type'], 'single')
        self.assertEqual(body['format'], 'group')
        self.assertEqual(body['result']['format'], 'group')
        self.assertEqual(len(body['result']['groups']), 4)
        self.assertEqual(len(body['result']['qualifiers']), 8)

    def test_invalid_tournament_format_is_rejected(self):
        payload = {
            'mode': 'single',
            'tournament_format': 'unknown',
            'win_rates': self.rates,
        }
        response = self.client.post(
            '/simulate/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    @patch('simulator.views.BATCH_RUNS', 20)
    def test_group_multi_api_uses_configured_batch_size(self):
        payload = {
            'mode': 'multi',
            'tournament_format': 'group',
            'win_rates': self.rates,
            'team_names': self.names,
            'regions': self.regions,
        }
        response = self.client.post(
            '/simulate/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['format'], 'group')
        self.assertEqual(body['runs'], 20)
        self.assertEqual(sum(body['stats']), 20 * 8)
        self.assertEqual(sum(body['weak_freq']), 20)


class SwissRegressionTests(TestCase):
    def test_swiss_remains_default_api_format(self):
        rates = make_rates()
        payload = {'mode': 'single', 'win_rates': rates}
        response = self.client.post(
            '/simulate/',
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['format'], 'swiss')
        self.assertIn('rounds', body['result'])
        self.assertTrue(1 <= len(body['result']['qualifiers']) <= 16)

    def test_swiss_single_simulation_still_runs(self):
        random.seed(3)
        result = run_single_simulation(make_rates())

        self.assertIn('rounds', result)
        self.assertTrue(result['rounds'])
        self.assertTrue(all(1 <= team_id <= 16 for team_id in result['qualifiers']))
