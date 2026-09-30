import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_core import reply, review
from models import DeliveryReview
from storage import Store
from config import ROOT


class AdaptiveFake:
    def __init__(self, *args, **kwargs): pass

    def generate(self, instructions, payload, schema):
        if schema is DeliveryReview:
            value = review()
        elif payload['explicit_ui_permission']:
            value = reply('The explanation you requested.', 'direct')
        elif payload['stage'] == 'clarification':
            value = reply('A definition of the requested term.', 'clarify')
        elif payload['stage'] == 'feedback':
            value = reply('Your final explanation develops your initial idea.', 'feedback')
        elif sum(m['role']=='user' and m['stage']=='discussion' for m in payload['conversation']) > 1:
            value = reply('You can now write your complete explanation.', 'ready')
        else:
            value = reply()
        return value, {'model':'offline-fake'}


class AppTests(unittest.TestCase):
    def test_complete_student_flow_and_no_private_ui(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'test.db')
            with patch('storage.Store', return_value=store), patch('gateway.Gateway', AdaptiveFake):
                app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30)
                app.secrets['OPENAI_API_KEY'] = 'offline-test-placeholder'
                app.run()
                def click(label):
                    next(x for x in app.button if x.label == label).click().run()
                    self.assertFalse(app.exception)
                self.assertFalse(app.exception)
                self.assertEqual(len(app.json), 0)
                app.text_area[0].set_value('What does inherited mean?')
                click('Ask the tutor')
                click('Write my initial explanation')
                app.text_area[0].set_value('The susceptible ones died and resistant ones reproduced.')
                click('Discuss my explanation')
                self.assertEqual(app.session_state.attempt['transcript'][-1]['kind'], 'extend')
                app.text_area[0].set_value('I can connect the explanation to the concepts.')
                click('Send')
                self.assertTrue(app.session_state.attempt['discussion_ended'])
                click('Write my final explanation')
                app.text_area[0].set_value('My completed explanation.')
                app.text_area[1].set_value('I connected the concepts.')
                click('Save final explanation')
                click('Get formative feedback')
                self.assertEqual(app.session_state.attempt['transcript'][-1]['kind'], 'feedback')
                self.assertEqual(len(app.json), 0)
                self.assertFalse(app.session_state.attempt['answer_exposed'])
                click('I would like a direct explanation')
                self.assertTrue(app.session_state.attempt['answer_exposed'])
                self.assertEqual(len(store.list()), 1)


if __name__ == '__main__': unittest.main()
