"""The only API adapter; replace with a fake in offline tests."""
import json


class ModelFailure(Exception):
    pass


class Gateway:
    def __init__(self, key, model='gpt-5', reasoning_effort='medium'):
        from openai import OpenAI
        self.client = OpenAI(api_key=key, timeout=120, max_retries=1)
        self.model = model
        self.reasoning_effort = reasoning_effort

    def generate(self, instructions, payload, schema):
        options = {}
        if self.reasoning_effort and self.model.startswith(('gpt-5', 'gpt-6', 'o3', 'o4')):
            options['reasoning'] = {'effort': self.reasoning_effort}
        response = self.client.responses.parse(
            model=self.model, instructions=instructions,
            input=json.dumps(payload, ensure_ascii=False), text_format=schema,
            store=False, max_output_tokens=10000, **options)
        if response.status != 'completed' or not isinstance(response.output_parsed, schema):
            raise ModelFailure('No complete structured response was returned.')
        metadata = {'response_id': response.id, 'model': self.model,
                    'usage': response.usage.model_dump() if response.usage else None}
        return response.output_parsed, metadata
