import copy
import json
import unittest
from types import SimpleNamespace
from test_core import reply
from core import fresh, record, apply_reply, respond, READY, DIRECT
from models import TutorReply, DisplayReview

BUNDLE={'version':'test','policy':'test','examples':[]}

def client_for(candidate, approved=True, captures=None):
    def parse(**kwargs):
        if captures is not None:captures.append(json.loads(kwargs['input']))
        if kwargs['text_format'] is DisplayReview:
            value=DisplayReview(answers_activity=not approved,supplies_missing_connection=False,
                leading_question=False,appropriate_for_stage=True,grounded_in_conversation=True)
        else:value=TutorReply(**candidate)
        return SimpleNamespace(status='completed',output_parsed=value,usage=None,id='mock')
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))

class WorkflowTests(unittest.TestCase):
    def test_clarification_never_probes_or_marks_ready(self):
        for action in ('probe','hint','ready','search','clarify'):
            a=fresh();record(a,'user','What is E coli?','clarification')
            prior=copy.deepcopy(a)
            r=reply(action=action,level='supported_explanation',quote='What is E coli?')
            out=apply_reply(a,r,'clarification')
            self.assertEqual(out['action'],'clarify')
            self.assertIn('type of bacterium',out['message'])
            self.assertNotIn('?',out['message'])
            for key in ('assessment','stalls','total_turns','teaching_turns','question_count','discussion_ended','target_demonstrated'):
                self.assertEqual(a[key],prior[key],key)

    def test_repeated_clarification_does_not_reach_discussion_cap(self):
        a=fresh()
        for _ in range(30):
            record(a,'user','What is an antibiotic?','clarification')
            out=apply_reply(a,reply(),'clarification')
        self.assertIn('medicine',out['message']);self.assertEqual(a['total_turns'],0)
        self.assertFalse(a['pending_offer'])

    def test_arbitrary_clarification_is_answered_without_discussion_review(self):
        r=reply(action='clarify');r['message']='Researchers use the same test both times so the results can be compared fairly.'
        a=fresh();event=respond(a,'Why use the same test?','clarification',BUNDLE,client_for(r),'mock')
        self.assertEqual(event['delivered']['message'],r['message'])
        self.assertNotIn('display_review',event);self.assertEqual(a['question_count'],0)

    def test_rejected_candidate_is_blocked_before_transcript(self):
        r=reply(action='probe');r['message']=DIRECT
        a=fresh();event=respond(a,'What happens next?','followup',BUNDLE,client_for(r,False),'mock')
        self.assertFalse(event['display_review']['approved'])
        self.assertNotEqual(DIRECT,a['transcript'][-1]['content'])
        self.assertFalse(any(m['content']==DIRECT for m in a['transcript']))
        self.assertEqual(event['raw_reply']['message'],DIRECT)

    def test_followup_uses_tailored_question_after_review(self):
        r=reply();r['message']='You mentioned that the bacteria changed. What do you mean by changed?'
        a=fresh();event=respond(a,'The bacteria changed','followup',BUNDLE,client_for(r),'mock')
        self.assertEqual(event['delivered']['message'],r['message'])

    def test_readiness_is_exact_and_cannot_be_overwritten(self):
        r=reply(level='supported_explanation',quote='my connected explanation');r['message']='Another question?'
        a=fresh();event=respond(a,'my connected explanation','followup',BUNDLE,client_for(r),'mock')
        self.assertEqual(event['delivered']['message'],"You're good to go. You can write your complete explanation now.")
        self.assertNotIn('display_review',event);self.assertTrue(a['discussion_ended'])

    def test_feedback_receives_whole_process_and_reflection(self):
        a=fresh();a.update(initial='first idea',final='complete idea',reflection='I reconsidered my assumption')
        for text,stage in [('first idea','followup'),('revised idea','followup'),('complete idea','final'),(a['reflection'],'reflection')]:
            record(a,'user',text,stage)
        r=reply(action='feedback');r['message']='You reconsidered an assumption during discussion and described that revision in your reflection. Your final explanation could identify the observation that supports it more clearly.'
        captures=[]
        event=respond(a,'Review my reasoning process','feedback',BUNDLE,client_for(r,captures=captures),'mock')
        self.assertEqual(event['delivered']['message'],r['message'])
        self.assertEqual(captures[0]['reflection'],a['reflection'])
        self.assertEqual([m['content'] for m in captures[0]['conversation'][:4]],['first idea','revised idea','complete idea',a['reflection']])
        self.assertFalse(a['answer_exposed'])
