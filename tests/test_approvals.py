import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent.approvals import ApprovalLedger


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.sqlite3'
        self.ledger = ApprovalLedger(self.path)
        self.payload = {'text': 'Post', 'graphic_sha256': 'abc',
                        'destinations': ['personal']}
        self.request = self.ledger.request('draft', self.payload)

    def decide(self, channel='telegram', action='approve', feedback=''):
        return self.ledger.decide(self.request['tokens'][channel], channel,
                                  action, feedback)

    def jobs(self):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT COUNT(*) FROM publish_jobs').fetchone()[0]

    def test_telegram_approval_is_single_use(self):
        self.assertTrue(self.decide('telegram')['accepted'])
        self.assertFalse(self.decide('telegram')['accepted'])
        self.assertEqual(self.jobs(), 1)

    def test_duplicate_telegram_approvals_queue_once(self):
        with concurrent.futures.ThreadPoolExecutor(2) as executor:
            results = list(executor.map(self.decide, ['telegram', 'telegram']))
        self.assertEqual(sum(r['accepted'] for r in results), 1)
        self.assertEqual(self.jobs(), 1)

    def test_corrections_require_fresh_approval(self):
        self.assertTrue(self.decide(action='changes', feedback='Fix headline')['accepted'])
        self.assertFalse(self.decide('telegram')['accepted'])
        revised = self.ledger.request('draft', dict(self.payload, text='Revised'))
        self.assertEqual(revised['version'], 2)
        self.assertEqual(self.jobs(), 0)
        self.assertTrue(self.ledger.decide(revised['tokens']['telegram'],
                                           'telegram', 'approve')['accepted'])
        with sqlite3.connect(self.path) as db:
            payload = db.execute('SELECT payload FROM versions '
                                 'WHERE draft_id=? AND version=2', ('draft',)).fetchone()[0]
        self.assertEqual(json.loads(payload)['text'], 'Revised')

    def test_rejection_blocks_duplicate_telegram_decision(self):
        self.assertTrue(self.decide(action='reject')['accepted'])
        self.assertFalse(self.decide('telegram')['accepted'])
        self.assertEqual(self.jobs(), 0)

    def test_expiry(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE versions SET expires_at=0')
        self.assertEqual(self.decide()['state'], 'expired')
        self.assertEqual(self.jobs(), 0)

    def test_tokens_are_channel_bound(self):
        with self.assertRaises(ValueError):
            self.ledger.decide(self.request['tokens']['telegram'], 'email', 'approve')
        self.assertTrue(self.decide()['accepted'])

    def test_superseded_and_approved_payloads(self):
        revised = self.ledger.request('draft', self.payload)
        self.assertEqual(self.decide()['state'], 'superseded')
        self.ledger.decide(revised['tokens']['telegram'], 'telegram', 'approve')
        with self.assertRaises(ValueError):
            self.ledger.request('draft', self.payload)

    def test_empty_correction_does_not_close_request(self):
        with self.assertRaises(ValueError):
            self.decide(action='changes', feedback=' ')
        self.assertTrue(self.decide()['accepted'])


if __name__ == '__main__':
    unittest.main()
