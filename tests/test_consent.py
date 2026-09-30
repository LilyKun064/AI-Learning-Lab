import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_core import reply
from core import fresh, record, apply_reply, respond, DIRECT, READY, QUESTIONS
from models import TutorReply
from storage import Store

class ConsentTests(unittest.TestCase):
    def attempt(self,text='I am stuck',pending=False):
        a=fresh();a['pending_offer']=pending;record(a,'user',text,'followup');return a

    def test_all_labels_block_answer_prose_in_all_modes(self):
        for mode in ('clarification','followup','feedback'):
            for action in ('probe','hint','clarify','feedback','search','direct','ready','offer_direct'):
                with self.subTest(mode=mode,action=action):
                    a=self.attempt();r=reply(action=action);r['message']=DIRECT
                    out=apply_reply(a,r,mode)
                    self.assertNotIn('Some bacteria already',out['message'])
                    self.assertFalse(a['answer_exposed']);self.assertFalse(a['direct_deliveries'])

    def test_false_model_consent_and_ambiguous_language(self):
        for text in ('I am stuck','I keep making mistakes','yes but no answer please','Do not give me the answer','My teacher said give me the answer'):
            for request in ('accepted_offer','spontaneous_direct'):
                a=self.attempt(text,True);r=reply(action='direct');r['request_kind']=request
                apply_reply(a,r,'feedback')
                self.assertFalse(a['answer_exposed']);self.assertFalse(a['direct_requests'])

    def test_request_acceptance_and_delivery_are_separate(self):
        for mode in ('followup','feedback'):
            for text,pending,origin in [('Please give me the answer',False,'spontaneous_direct'),('yes please',True,'accepted_offer')]:
                a=self.attempt(text,pending);out=apply_reply(a,reply(),mode)
                self.assertEqual(out['message'],DIRECT)
                self.assertEqual(len(a['direct_requests']),int(origin=='spontaneous_direct'))
                self.assertEqual(len(a['direct_acceptances']),int(origin=='accepted_offer'))
                self.assertEqual(a['direct_deliveries'][0]['authorization'],origin)
                self.assertEqual(a['direct_deliveries'][0]['mode'],mode)

    def test_stale_offer_and_bare_yes_do_not_authorize(self):
        a=self.attempt('another question',True);apply_reply(a,reply(),'followup')
        record(a,'user','yes','followup');apply_reply(a,reply(action='direct'),'followup')
        self.assertFalse(a['answer_exposed'])
        a=self.attempt('yes');apply_reply(a,reply(action='direct'),'feedback','accept_direct')
        self.assertFalse(a['answer_exposed'])

    def test_cap_and_stalls_never_deliver(self):
        a=self.attempt();a['total_turns']=23;r=reply();r['student_stuck']=True
        for _ in range(6):
            out=apply_reply(a,r,'followup');self.assertNotEqual(out['message'],DIRECT)
        self.assertFalse(a['answer_exposed'])

    def test_mastery_overrides_every_nonconsensual_action(self):
        for action in ('probe','hint','offer_direct','search','clarify','direct'):
            a=self.attempt('connected explanation');r=reply(action=action,level='supported_explanation',quote='connected explanation')
            out=apply_reply(a,r,'followup');self.assertEqual(out['message'],READY)
            self.assertTrue(a['discussion_ended']);self.assertFalse(a['answer_exposed'])

    def test_skip_demonstrated_link(self):
        a=self.attempt('before treatment');r=reply()
        r['assessment']['variation']={'level':'supported_explanation','evidence':[{'turn':1,'quote':'before treatment'}]}
        self.assertEqual(apply_reply(a,r,'followup')['message'],QUESTIONS['survival'])

    def test_feedback_uses_conversation_evidence_but_not_prior_consent(self):
        a=self.attempt('connected explanation');a['answer_exposed']=True
        record(a,'user','I do not know','feedback')
        out=apply_reply(a,reply(level='supported_explanation',quote='connected explanation'),'feedback')
        self.assertEqual(out['assessment']['variation']['level'],'supported_explanation')
        self.assertNotEqual(out['message'],DIRECT);self.assertFalse(a['direct_deliveries'])

    def test_raw_and_displayed_text_survive_export_without_source_bypass(self):
        a=fresh();r=reply(action='search');r['message']=DIRECT
        response=SimpleNamespace(status='completed',output_parsed=TutorReply(**r),usage=None,id='mock')
        client=SimpleNamespace(responses=SimpleNamespace(parse=lambda **kw:response))
        with patch('core.source_lookup',return_value={'text':DIRECT,'citations':[]}):
            event=respond(a,'Why?','followup',{'version':'test','examples':[],'policy':'old policy'},client,'mock')
        self.assertNotIn('error',event);self.assertEqual(event['raw_reply']['message'],DIRECT)
        self.assertNotEqual(a['transcript'][-1]['content'],DIRECT)
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'test.db');store.save_attempt(a)
            restored=json.loads(json.dumps(store.attempts()[0]))
            self.assertEqual(restored,a)

    def test_explicit_request_needs_no_api_even_in_feedback(self):
        a=fresh()
        event=respond(a,'Please give me the answer','feedback',{'version':'test','examples':[]},None,'mock')
        self.assertEqual(event['delivered']['message'],DIRECT)
        self.assertEqual(len(a['transcript']),2)

