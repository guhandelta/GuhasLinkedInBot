import copy
import json
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
from pathlib import Path

from agent.content import (generate, infographic_svg, response_text, source_urls,
                           validate_draft, validate_freshness, write_draft)


URL = 'https://developer.mozilla.org/en-US/docs/Web/API/AbortController'


def draft():
    return {'post_kind': 'informational',
            'freshness': {'why_now': 'Apply cancellation to an evolving AI interface.',
                          'development_date': None, 'evidence_url': URL},
            'text': 'Explain a UI cancellation pattern and its limitations.',
            'headline': 'Make cancellation explicit',
            'cards': [{'heading': heading, 'body': body} for heading, body in [
                ('Start', 'Begin work when the user requests it.'),
                ('Cancel', 'Offer a clear action to stop waiting.'),
                ('Recover', 'Keep the interface ready for the next request.')]],
            'source_urls': [URL], 'review_notes': ['Illustrative test fixture.']}


class ContentTests(unittest.TestCase):
    def test_custom_request_preserves_topic_context_and_schedule(self):
        calls = []

        class Client:
            def create(self, prompt, schema=None, research=False):
                calls.append(prompt)
                if research:
                    return 'Research', {'output': [{'type': 'web_search_call',
                        'action': {'sources': [{'url': URL}]}}]}
                return copy.deepcopy(draft()), {}

        profile = {'timezone': 'America/New_York',
                   'posting_schedule': {'approval_requests_per_week': 3},
                   'approvals': {'email_recipient': 'private-owner@example.com',
                                 'telegram': {'username': '@private_owner'}}}
        original = copy.deepcopy(profile)
        custom = {'notes': 'Discuss a cancellable AI workflow.',
                  'reference_urls': [URL], 'post_kind': 'informational'}
        result = generate(Client(), profile, 'custom', 'My specific topic',
                          custom_request=custom)
        self.assertEqual(result['request']['origin'], 'owner_custom')
        self.assertEqual(result['request']['topic'], 'My specific topic')
        self.assertEqual(result['request']['reference_urls'], [URL])
        self.assertIn('Discuss a cancellable AI workflow.', calls[0])
        self.assertIn('My specific topic', calls[1])
        self.assertTrue(all('private-owner@example.com' not in prompt and
                            '@private_owner' not in prompt for prompt in calls))
        self.assertEqual(result['status'], 'draft_not_submitted_for_approval')
        self.assertEqual(profile, original)
        self.assertNotIn('origin', custom)

    def test_custom_request_cannot_silently_change_requested_format(self):
        class Client:
            def create(self, prompt, schema=None, research=False):
                if research:
                    return 'Research', {'output': [{'type': 'web_search_call',
                        'action': {'sources': [{'url': URL}]}}]}
                return draft(), {}

        with self.assertRaisesRegex(ValueError, 'post kind does not match'):
            generate(Client(), {'timezone': 'America/New_York'}, 'custom',
                     'My topic', custom_request={'post_kind': 'code_walkthrough'})

    def test_invalid_custom_request_stops_before_research(self):
        class NoCallsClient:
            def create(self, *args, **kwargs):
                raise AssertionError('Invalid request must not call generation')

        for topic, details in [('', {}), ('Topic', {'reference_urls': ['file:///etc/passwd']}),
                               ('Topic', {'post_kind': 'invalid'})]:
            with self.assertRaises(ValueError):
                generate(NoCallsClient(), {'timezone': 'America/New_York'},
                         'custom', topic, custom_request=details)

    def test_freshness_rejects_future_dates_and_missing_angle(self):
        now = datetime(2026, 10, 15, tzinfo=ZoneInfo('America/New_York'))
        evidence = {'why_now': 'Recent release changes a practical tradeoff.',
                    'development_date': '2026-10-01', 'evidence_url': URL}
        self.assertIsNone(validate_freshness(evidence, [URL], now))
        with self.assertRaises(ValueError):
            validate_freshness(dict(evidence, development_date='2026-10-16'), [URL], now)
        with self.assertRaises(ValueError):
            validate_freshness(dict(evidence, why_now=' '), [URL], now)
        self.assertIn('older', validate_freshness(
            dict(evidence, development_date='2020-01-01'), [URL], now))

    def test_undated_draft_gets_an_explicit_review_note(self):
        content = draft()
        validate_draft(content, [URL])
        self.assertTrue(any('date is unverified' in note for note in content['review_notes']))

    def test_no_timely_topics_is_a_valid_skip(self):
        class Client:
            def create(self, prompt, schema=None, research=False):
                if research:
                    return 'Research', {'output': [{'type': 'web_search_call',
                        'action': {'sources': [{'url': URL}]}}]}
                return {'topics': [], 'skip_reason': 'No useful current angle found.'}, {}
        result = generate(Client(), {'timezone': 'America/New_York'}, 'suggest')
        self.assertEqual(result['content']['topics'], [])
        self.assertTrue(result['content']['skip_reason'])

    def test_refused_or_incomplete_output_is_blocked(self):
        for response in [
            {'status': 'incomplete', 'output': []},
            {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'refusal', 'refusal': 'Declined'}]}]},
            {'status': 'completed', 'output': []}
        ]:
            with self.assertRaises(ValueError):
                response_text(response)

    def test_invented_source_and_excess_copy_are_blocked(self):
        validate_draft(draft(), [URL])
        bad = draft()
        bad['source_urls'] = ['https://example.com/invented']
        with self.assertRaises(ValueError):
            validate_draft(bad, [URL])
        bad = draft()
        bad['cards'][0]['body'] = 'x' * 141
        with self.assertRaises(ValueError):
            validate_draft(bad, [URL])

    def test_svg_escapes_generated_markup(self):
        content = draft()
        content['headline'] = '<script>alert(1)</script> & text'
        content['cards'][0]['body'] = '<image href="https://example.com/tracker"/>'
        svg = infographic_svg(content)
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}script')), 0)
        self.assertEqual(len(root.findall('.//{http://www.w3.org/2000/svg}image')), 0)
        self.assertIn('&lt;script&gt;', svg)

    def test_sources_include_search_results_and_citations(self):
        response = {'output': [
            {'type': 'web_search_call', 'action': {'sources': [{'url': URL}]}},
            {'type': 'message', 'content': [{'annotations': [
                {'type': 'url_citation', 'url': URL},
                {'type': 'url_citation', 'url': 'javascript:alert(1)'}]}]}
        ]}
        self.assertEqual(source_urls(response), [URL])

    def test_research_without_sources_cannot_create_a_draft(self):
        class Client:
            def create(self, *args, **kwargs):
                return 'Unsupported research', {'output': []}

        with self.assertRaisesRegex(ValueError, 'no source URLs'):
            generate(Client(), {'timezone': 'America/New_York'}, 'draft', 'UI bugs')

    def test_revision_feedback_is_included_in_research(self):
        calls = []

        class Client:
            def create(self, prompt, schema=None, research=False):
                calls.append(prompt)
                if research:
                    return 'Research', {'output': [{'type': 'web_search_call',
                        'action': {'sources': [{'url': URL}]}}]}
                return copy.deepcopy(draft()), {}

        result = generate(Client(), {'timezone': 'America/New_York'}, 'draft',
                          'Cancellation', previous=draft(), feedback='Check browser support')
        self.assertIn('Check browser support', calls[0])
        self.assertEqual(result['status'], 'draft_not_submitted_for_approval')

    def test_bundle_is_content_addressed_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'preview'
            bundle = {'content': draft(), 'status': 'draft_not_submitted_for_approval'}
            write_draft(output, bundle)
            saved = json.loads((output / 'draft.json').read_text())
            self.assertEqual(len(saved['graphic_sha256']), 64)
            self.assertIn(URL, (output / 'post.txt').read_text())
            self.assertTrue((output / 'preview.html').is_file())
            with self.assertRaises(FileExistsError):
                write_draft(output, bundle)


if __name__ == '__main__':
    unittest.main()
