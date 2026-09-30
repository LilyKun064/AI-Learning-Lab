"""UI regression with mocked generation and isolated persistence."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_core import reply
from core import DIRECT
from storage import Store

class FlowTests(unittest.TestCase):
    def test_six_step_workflow(self):
        from models import DisplayReview
        from core import READY
        class Fake:
            def __init__(self,*args,**kwargs):self.responses=self
            def parse(self,**kwargs):
                payload=json.loads(kwargs['input'])
                if kwargs['text_format'] is DisplayReview:
                    parsed=DisplayReview(answers_activity=False,supplies_missing_connection=False,
                        leading_question=False,appropriate_for_stage=True,grounded_in_conversation=True)
                else:
                    latest=payload['conversation'][-1]
                    r=reply()
                    if payload['mode']=='clarification':
                        r.update(action='clarify',message='E. coli is a type of bacterium. Some kinds can cause infections.')
                    elif payload['mode']=='feedback':
                        assert payload['reflection']=='I connected my ideas.'
                        r.update(action='feedback',message='You developed your initial idea during discussion and described that change in your reflection.')
                    elif latest['content']=='My complete connections':
                        r=reply(level='supported_explanation',quote=latest['content'],turn=latest['sequence'])
                    parsed=kwargs['text_format'](**r)
                return SimpleNamespace(status='completed',output_parsed=parsed,usage=None,id='mock')
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            with patch('storage.Store',return_value=store),patch('openai.OpenAI',Fake):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
                at.secrets['OPENAI_API_KEY']='mock-not-a-key';at.run()
                self.assertFalse(any(b.label in ('Yes, explain directly','I would like a direct explanation') for b in at.button))
                def click(label):
                    next(b for b in at.button if b.label==label).click().run()
                    self.assertFalse(at.exception)
                at.text_area[0].set_value('What is E coli?');click('Ask the tutor')
                self.assertIn('type of bacterium',at.session_state.activity['transcript'][-1]['content'])
                self.assertEqual(at.session_state.activity['total_turns'],0)
                click('Write my explanation');at.text_area[0].set_value('My first idea');click('Discuss my explanation')
                self.assertFalse(at.session_state.activity['discussion_ended'])
                at.text_area[0].set_value('My complete connections');click('Send')
                self.assertEqual(at.session_state.activity['transcript'][-1]['content'],READY)
                self.assertFalse(any(b.label=='Send' for b in at.button))
                click('Write my final explanation')
                at.text_area[0].set_value('My own complete explanation')
                at.text_area[1].set_value('I connected my ideas.');click('Save final explanation')
                click('Get formative feedback')
                self.assertIn('during discussion',at.session_state.activity['transcript'][-1]['content'])
                self.assertFalse(at.session_state.activity['answer_exposed'])

    def test_writing_draft_survives_workspace_navigation(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            with patch('storage.Store',return_value=store),patch('openai.OpenAI'):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
                at.secrets['OPENAI_API_KEY']='mock-not-a-key';at.run()
                next(b for b in at.button if b.label=='Write my explanation').click().run()
                at.text_area[0].set_value('My unsent draft').run()
                self.assertEqual(store.attempts()[0]['drafts']['initial'],'My unsent draft')
                at.sidebar.radio[0].set_value('Teaching examples').run()
                at.sidebar.radio[0].set_value('Student activity').run()
                self.assertFalse(at.exception)
                self.assertEqual(at.text_area[0].value,'My unsent draft')

    def test_discussion_feedback_and_consent(self):
        class Fake:
            def __init__(self,*args,**kwargs):self.responses=self
            def parse(self,**kwargs):
                payload=json.loads(kwargs['input'])
                assert 'conversation' in payload
                r=reply(action='feedback' if payload['mode']=='feedback' else 'probe')
                r['message']=DIRECT
                return SimpleNamespace(status='completed',output_parsed=kwargs['text_format'](**r),usage=None,id='mock')
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            with patch('storage.Store',return_value=store),patch('openai.OpenAI',Fake):
                at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)
                at.secrets['OPENAI_API_KEY']='mock-not-a-key'
                at.run()
                def click(label):
                    next(b for b in at.button if b.label==label).click().run()
                    self.assertFalse(at.exception)
                click('Write my explanation')
                at.text_area[0].set_value('I am stuck')
                click('Discuss my explanation')
                self.assertFalse(at.session_state.activity['answer_exposed'])
                self.assertNotEqual(at.session_state.activity['transcript'][-1]['content'],DIRECT)
                click('Write my final explanation')
                at.text_area[0].set_value('I still do not know')
                click('Save final explanation')
                click('Get formative feedback')
                self.assertFalse(at.session_state.activity['answer_exposed'])
                click('I would like a direct explanation')
                a=at.session_state.activity
                self.assertEqual(a['transcript'][-1]['content'],DIRECT)
                self.assertEqual(len(a['direct_requests']),1)
                self.assertEqual(a['direct_deliveries'][0]['mode'],'feedback')
                self.assertEqual(store.attempts()[0]['transcript'],a['transcript'])


