"""Real SDK serialization/parsing against an in-memory HTTP transport; no network."""
import json
import unittest
import httpx
from openai import OpenAI
from gateway import Gateway, ModelFailure
from models import TutorReply
from test_core import reply


class GatewayTests(unittest.TestCase):
    def test_sdk_structured_response_without_network(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={
                'id':'resp_offline', 'object':'response', 'created_at':0,
                'status':'completed', 'model':'gpt-5', 'error':None,
                'output':[{'id':'msg_offline', 'type':'message', 'role':'assistant',
                           'status':'completed', 'content':[{'type':'output_text',
                           'text':reply().model_dump_json(), 'annotations':[]}]}]})
        g = Gateway.__new__(Gateway)
        g.model = 'gpt-5'; g.reasoning_effort = 'medium'
        g.client = OpenAI(api_key='offline-test-placeholder',
            http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        result, metadata = g.generate('Teaching instructions', {'student':'An explanation'}, TutorReply)
        self.assertEqual(result.move, 'extend')
        self.assertFalse(captured[0]['store'])
        self.assertEqual(captured[0]['text']['format']['type'], 'json_schema')
        self.assertEqual(metadata['response_id'], 'resp_offline')
        g.client.close()


if __name__ == '__main__': unittest.main()
