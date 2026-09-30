import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import CLARIFICATION_RULES, DIRECT, OFFER, fresh, respond, retry_control
from models import TutorReply, DisplayReview
from storage import Store
from test_core import reply
from test_workflow import BUNDLE, client_for


class FixTests(unittest.TestCase):
    def test_e_coli_uses_only_clarification_instructions(self):
        calls=[]
        candidate=reply(action='clarify')
        candidate['message']='E. coli is a type of bacterium. Many strains live in the gut; some cause infections.'
        def parse(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status='completed',output_parsed=TutorReply(**candidate),usage=None,id='mock')
        a=fresh();a['pending_offer']=True
        client=SimpleNamespace(responses=SimpleNamespace(parse=parse))
        event=respond(a,'what is E coli','clarification',BUNDLE,client,'mock')
        self.assertNotIn('error',event)
        self.assertEqual(a['transcript'][-1]['content'],candidate['message'])
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['instructions'],CLARIFICATION_RULES)
        self.assertEqual(json.loads(calls[0]['input'])['approved_examples'],[])
        self.assertFalse(a['pending_offer']);self.assertFalse(a['answer_exposed'])
        self.assertFalse(a['direct_offers']);self.assertFalse(a['direct_deliveries'])
        self.assertEqual(a['total_turns'],0)

    def test_wrong_model_labels_cannot_offer_full_answer_during_clarification(self):
        for action in ('direct','offer_direct','ready','probe'):
            candidate=reply(action=action);candidate['message']=OFFER
            candidate['request_kind']='spontaneous_direct'
            a=fresh()
            event=respond(a,'what is E coli','clarification',BUNDLE,client_for(candidate),'mock')
            self.assertIn('type of bacterium',event['delivered']['message'])
            self.assertFalse(a['pending_offer']);self.assertFalse(a['direct_deliveries'])

    def test_clarification_direct_wording_does_not_trigger_packaged_answer(self):
        r=reply(action='clarify');r['message']='Here is the explanation of the term you asked about.'
        a=fresh();a['pending_offer']=True
        event=respond(a,'Please give me the answer','clarification',BUNDLE,client_for(r),'mock')
        self.assertEqual(event['delivered']['message'],r['message'])
        self.assertNotEqual(event['delivered']['message'],DIRECT)
        self.assertNotIn('display_review',event)

    def test_search_delivered_in_clarification_and_reviewed_in_discussion(self):
        source={'text':'A cited answer.','citations':[{'url':'https://cdc.gov/example','title':'CDC'}]}
        for mode,approved,expected in [('clarification',False,True),('followup',True,True),('followup',False,False)]:
            a=fresh();r=reply(action='search')
            with patch('core.source_lookup',return_value=source) as lookup:
                event=respond(a,'Why? ',mode,BUNDLE,client_for(r,approved),'mock')
            lookup.assert_called_once()
            self.assertNotIn('error',event)
            self.assertEqual(event['source_lookup'],source)
            self.assertEqual(event['delivered']['message']==source['text'],expected)
            self.assertEqual(bool(a['transcript'][-1]['citations']),expected)

    def test_disabled_search_preserves_question_without_search_call(self):
        a=fresh()
        with patch('core.source_lookup') as lookup:
            event=respond(a,'A source question','clarification',BUNDLE,client_for(reply(action='search')),'mock',web_enabled=False)
        lookup.assert_not_called()
        self.assertEqual(event['error']['diagnostic']['reason'],'web_disabled')
        self.assertEqual(a['transcript'][0]['content'],'A source question')

    def test_retry_preserves_button_control_and_original_state(self):
        for control in ('hint','accept_direct','decline_direct','request_direct'):
            a=fresh();a['pending_offer']=True
            event=respond(a,'Button text','followup',BUNDLE,client_for(reply()),'mock',control)
            original=copy.deepcopy(a)
            preview=copy.deepcopy(event['before_state']);preview['events']=[]
            retried=respond(preview,event['student'],'followup',BUNDLE,client_for(reply()),'mock',retry_control(a,event))
            self.assertEqual(event['delivered'],retried['delivered'])
            self.assertEqual(a,original)
            legacy=dict(event);legacy.pop('control')
            self.assertEqual(retry_control(a,legacy),control)

    def test_seed_update_preserves_activation_history_and_frozen_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            seed=store.examples()[0]
            legacy=dict(seed);legacy.pop('seed_revision');legacy['preferred_response']='Old teaching text'
            with store.connect() as c:
                c.execute('UPDATE examples SET payload=?,active=0 WHERE id=?',(json.dumps(legacy),seed['id']))
            old_bundle=store.compile()
            Store(store.path)
            updated=next(e for e in store.examples(False) if e['id']==seed['id'])
            self.assertFalse(updated['active'])
            self.assertEqual(updated['seed_revision'],1)
            self.assertEqual(store.bundle(old_bundle['version']),old_bundle)
            with store.connect() as c:
                history=json.loads(c.execute('SELECT payload FROM seed_history WHERE id=?',(seed['id'],)).fetchone()[0])
            self.assertEqual(history['preferred_response'],'Old teaching text')
