import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import load_bundle, ROOT
from core import fresh, record, respond, reconcile_assessment, public_export, save_final
from models import TutorReply, DeliveryReview
from storage import Store


def reply(message='What evolutionary process connects these ideas?', move='extend', **extra):
    return TutorReply(**dict(dict(message=message, move=move, instructional_purpose='Connect existing reasoning to terminology.',
        consent='none', consent_quote='', answer_scope='full' if move == 'direct' else 'none',
        assessment_updates=[], final_assessment=[]), **extra))


def review(approved=True, **extra):
    return DeliveryReview(**dict(dict(approved=approved, explicit_request=False, consent_quote='',
        reveals_unrequested_answer=False, repeats_answered_question=False, repair_instruction=''), **extra))


class FakeGateway:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, instructions, payload, schema):
        self.calls.append((instructions, copy.deepcopy(payload), schema))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, schema)
        return response, {'model': 'offline-fake', 'usage': None}


def update(cid='frequency_change', points=1, evidence=None, **extra):
    return dict(dict(criterion_id=cid, points=points, understanding='demonstrated',
        evidence=evidence or [], note='Student explains the change.', revises_previous=False), **extra)


class TutorTests(unittest.TestCase):
    def setUp(self):
        self.a = fresh(load_bundle())

    def test_agent_extension_survives_without_score_gate_or_retrieval(self):
        text = 'The susceptible ones died from antibiotics, while the resistant ones reproduce asexually.'
        self.a['initial'] = text
        g = FakeGateway(reply(), review())
        e = respond(self.a, text, 'discussion', g)
        self.assertEqual(e['delivered']['move'], 'extend')
        self.assertEqual(self.a['transcript'][-1]['content'], 'What evolutionary process connects these ideas?')
        self.assertNotIn('examples', json.dumps(g.calls[0][1]))
        self.assertEqual(g.calls[0][1]['initial_explanation'], text)

    def test_agent_readiness_not_overridden_by_empty_scores(self):
        g = FakeGateway(reply('You can bring your ideas together in your final explanation.', 'ready'), review())
        respond(self.a, 'I have explained it across these turns.', 'discussion', g)
        self.assertTrue(self.a['discussion_ended'])
        self.assertEqual(self.a['assessment'], {})
        self.assertEqual(self.a['transcript'][-1]['kind'], 'ready')

    def test_bad_citation_does_not_erase_good_evidence(self):
        record(self.a, 'user', 'The resistant fraction increases.', 'discussion')
        record(self.a, 'assistant', 'Why?', 'discussion')
        updates = [update(evidence=[{'turn':1, 'quote':'resistant fraction increases'}, {'turn':2, 'quote':'Why?'}])]
        assessed, issues = reconcile_assessment(self.a, updates)
        self.assertEqual(assessed['frequency_change']['points'], 1)
        self.assertEqual(len(assessed['frequency_change']['evidence']), 1)
        self.assertTrue(issues)
        self.a['assessment'] = assessed
        new, _ = reconcile_assessment(self.a, [update(points=0, understanding='not_yet_demonstrated')])
        self.assertEqual(new, assessed)

    def test_contradiction_can_revise_credit(self):
        record(self.a, 'user', 'Their fraction increases.', 'discussion')
        self.a['assessment'], _ = reconcile_assessment(self.a, [update(evidence=[{'turn':1,'quote':'fraction increases'}])])
        record(self.a, 'user', 'Actually their fraction cannot change.', 'discussion')
        new, _ = reconcile_assessment(self.a, [update(points=0, understanding='contradicted',
            evidence=[{'turn':2,'quote':'their fraction cannot change'}], revises_previous=True)])
        self.assertEqual(new['frequency_change']['points'], 0)

    def test_definition_allowed_in_every_stage(self):
        for stage in ('clarification', 'discussion', 'feedback'):
            a = fresh(load_bundle())
            g = FakeGateway(reply('Fitness means reproductive success in a particular environment.', 'clarify'), review())
            e = respond(a, 'What does fitness mean?', stage, g)
            self.assertEqual(e['status'], 'delivered')
            self.assertFalse(a['answer_exposed'])

    def test_language_request_requires_independent_agreement(self):
        text = 'Could you walk me through the answer to this problem?'
        g = FakeGateway(reply('An explanation tailored to the activity.', 'direct', consent='explicit_request', consent_quote=text),
                        review(explicit_request=True, consent_quote=text))
        respond(self.a, text, 'discussion', g)
        self.assertTrue(self.a['answer_exposed'])
        self.assertEqual(self.a['direct_requests'][0]['origin'], 'language')

    def test_hint_or_model_label_cannot_authorize_direct_answer(self):
        for control in (None, 'hint'):
            a = fresh(load_bundle())
            g = FakeGateway(reply('Unrequested answer.', 'direct', consent='explicit_request', consent_quote='Help me'),
                review(explicit_request=False), reply('Which part feels unclear?', 'probe'), review())
            e = respond(a, 'Help me', 'discussion', g, control)
            self.assertEqual(e['delivered']['move'], 'probe')
            self.assertFalse(a['answer_exposed'])

    def test_clarification_is_not_disclosure_bypass(self):
        g = FakeGateway(reply('Unrequested case answer.', 'clarify'),
            review(False, reveals_unrequested_answer=True, repair_instruction='Define only the requested term.'),
            reply('An inherited trait can pass from parent to offspring.', 'clarify'), review())
        e = respond(self.a, 'What does inherited mean?', 'clarification', g)
        self.assertNotIn('Unrequested', e['delivered']['message'])
        self.assertFalse(self.a['answer_exposed'])

    def test_explicit_button_and_pending_offer(self):
        for control, pending in [('request_direct', False), ('accept_answer', True)]:
            a = fresh(load_bundle()); a['pending_offer'] = pending
            g = FakeGateway(reply('Requested explanation.', 'direct'), review())
            respond(a, 'Please explain.', 'discussion', g, control)
            self.assertTrue(a['answer_exposed'])
        a = fresh(load_bundle())
        g = FakeGateway(reply('Answer.', 'direct'), review(), reply('What would you like explained?', 'clarify'), review())
        respond(a, 'yes', 'discussion', g, 'accept_answer')
        self.assertFalse(a['answer_exposed'])

    def test_exposure_does_not_authorize_future_answer(self):
        self.a['answer_exposed'] = True
        g = FakeGateway(reply('Another answer.', 'direct'), review(), reply('You revised your initial idea.', 'feedback'), review())
        respond(self.a, 'Give feedback', 'feedback', g)
        self.assertEqual(len(self.a['direct_deliveries']), 0)

    def test_repetition_is_repaired_not_replaced_by_canned_question(self):
        record(self.a, 'assistant', 'What do the samples show?', 'discussion')
        g = FakeGateway(reply('What do the samples show?', 'probe'), review(), reply(), review())
        e = respond(self.a, 'I already explained the frequency change.', 'discussion', g)
        self.assertEqual(e['delivered']['move'], 'extend')
        self.assertTrue(g.calls[2][1]['repairs'])

    def test_failure_preserves_text_and_retry_is_transactional(self):
        g = FakeGateway(RuntimeError('private error text'))
        e = respond(self.a, 'My explanation', 'discussion', g)
        self.assertEqual(e['status'], 'failed')
        self.assertNotIn('private error', self.a['last_error'])
        g = FakeGateway(reply(), review())
        respond(self.a, '', 'discussion', g, retry=True)
        self.assertEqual(len([m for m in self.a['transcript'] if m['role']=='user']), 1)
        self.assertIsNone(self.a['last_error'])

    def test_no_delivery_or_assessment_when_all_reviews_fail(self):
        responses = []
        for _ in range(3):
            responses += [reply('Bad answer.', 'ready'), review(False)]
        e = respond(self.a, 'Thinking', 'discussion', FakeGateway(*responses))
        self.assertEqual(e['status'], 'failed')
        self.assertFalse(self.a['discussion_ended'])
        self.assertEqual(self.a['assessment'], {})
        self.assertEqual(len(self.a['transcript']), 1)

    def test_final_assessment_uses_only_latest_final(self):
        record(self.a, 'user', 'Earlier correct explanation.', 'discussion')
        save_final(self.a, 'First final', 'reflection')
        save_final(self.a, 'My current final', 'reflection')
        old = update(evidence=[{'turn':1,'quote':'Earlier correct explanation.'}])
        new = update(cid='natural_selection', evidence=[{'turn':4,'quote':'My current final'}])
        result, issues = reconcile_assessment(self.a, [old, new], final_only=True)
        self.assertNotIn('frequency_change', result)
        self.assertIn('natural_selection', result)

    def test_student_export_does_not_contain_private_material(self):
        self.a['events'] = [{'raw':'SECRET'}]
        self.a['assessment'] = {'secret':1}
        exported = json.dumps(public_export(self.a))
        self.assertNotIn('SECRET', exported)
        self.assertNotIn('rubric', exported)
        self.assertNotIn('assessment', exported)
        self.assertNotIn('teaching_policy', exported)

    def test_configuration_swap_and_snapshot(self):
        before = copy.deepcopy(self.a['bundle'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('activity.json', 'rubric.json'):
                (root/name).write_bytes((ROOT/'examples/genetic-drift'/name).read_bytes())
            for name in ('teaching_policy.md', 'boundary_policy.md'):
                (root/name).write_bytes((ROOT/name).read_bytes())
            b = load_bundle(root)
            self.assertEqual(b['activity']['id'], 'founder-effect')
            self.assertIsNone(b['activity']['table'])
            self.assertEqual(self.a['bundle'], before)
            data = json.loads((root/'rubric.json').read_text()); data['activity_id'] = 'wrong'
            (root/'rubric.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError): load_bundle(root)

    def test_storage_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'test.db'); store.save(self.a)
            self.assertEqual(store.list()[0], self.a)

    def test_request_logged_even_when_delivery_fails_and_retry_not_double_counted(self):
        respond(self.a, 'Explain it.', 'discussion', FakeGateway(RuntimeError()), 'request_direct')
        self.assertEqual(len(self.a['direct_requests']), 1)
        self.assertEqual(self.a['direct_deliveries'], [])
        respond(self.a, '', 'discussion', FakeGateway(reply('Requested answer.', 'direct'), review()), retry=True)
        self.assertEqual(len(self.a['direct_requests']), 1)
        self.assertEqual(len(self.a['direct_deliveries']), 1)

    def test_rubric_ids_and_point_limits_are_not_hardcoded(self):
        self.a['bundle']['rubric']['criteria'] = [dict(id='custom_skill', description='New topic', points=4, credit_guidance='Explanation')]
        record(self.a, 'user', 'I explain the new idea.', 'discussion')
        result, _ = reconcile_assessment(self.a, [update(cid='custom_skill', points=3,
            evidence=[{'turn':1,'quote':'I explain the new idea.'}])])
        self.assertEqual(result['custom_skill']['points'], 3)
        invalid, _ = reconcile_assessment(self.a, [update(cid='custom_skill', points=5,
            evidence=[{'turn':1,'quote':'I explain the new idea.'}])])
        self.assertEqual(invalid, {})

    def test_requested_partial_answer_does_not_end_discussion(self):
        text = 'Please tell me which factor is the selection pressure here.'
        g = FakeGateway(reply('The antibiotic is the selection pressure in this case.', 'direct',
            consent='explicit_request', consent_quote=text, answer_scope='partial'),
            review(explicit_request=True, consent_quote=text))
        respond(self.a, text, 'discussion', g)
        self.assertTrue(self.a['answer_exposed'])
        self.assertFalse(self.a['discussion_ended'])
        self.assertEqual(self.a['direct_deliveries'][0]['scope'], 'partial')


if __name__ == '__main__':
    unittest.main()
