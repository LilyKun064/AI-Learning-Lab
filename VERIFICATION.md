# Verification

Checked on 2026-09-30, using Python 3.12, OpenAI SDK 2.54.0, Streamlit 1.64.0,
and Pydantic 2.13.5.

- 22 offline automated tests pass.
- Streamlit student flow passes: clarification, initial explanation, adaptive
  discussion, readiness, final writing, feedback, and requested direct explanation.
- Real OpenAI SDK serialization/parsing passes against an in-memory HTTP transport.
  No external API request or credential was used.
- Activity/rubric configuration validates; a second, prose-only genetic-drift
  activity loads without topic-specific Python changes.
- Evidence validation retains valid citations when another citation is invalid.
- Repeated questions are repaired instead of replaced with a canned question.
- Full-answer requests, partial-answer requests, failed deliveries, retry behavior,
  and student-export privacy are covered.
- Local Streamlit server starts and its health endpoint responds.

No live-model evaluation was run. Fake-response tests establish software behavior,
not whether the configured model reliably recognizes understanding or teaches well.
Use the included optional live evaluation and real conversational pilots before
research use. Model-based answer-disclosure checks are not an absolute guarantee.
