# AI Learning Lab

An experimental AI tutor that helps you develop your own scientific explanations through conversation.

The current activity explores antibiotic resistance. You explain your thinking, discuss it with the tutor, and revise your explanation. The tutor is designed to ask useful questions, explain unfamiliar terms, and provide the answer only when you explicitly request it.

**We’re inviting testers to help find bugs and improve the learning experience. No specialist knowledge is needed.**

## Try it

**Online trial:** Link coming soon.

1. Read the scenario. Ask about any unfamiliar words or details.
2. Write your initial explanation in your own words. It’s fine to be unsure.
3. Discuss your reasoning with the tutor. Ask questions, request a hint, or ask for a direct explanation whenever you want.
4. Write your final explanation and reflect on what changed.
5. Request feedback. Use **Download my conversation** if you want to save or share your trial.

Responses may take a little time. If a response fails, use **Retry saved message**.

## Help us improve

Please report problems through this repository’s **Issues** tab. Useful reports include:

- What you expected and what happened instead.
- The message or steps that triggered the problem.
- A screenshot or downloaded conversation, if you’re comfortable sharing it.

We especially want to know when the tutor repeats questions, gives away answers, misunderstands correct reasoning, provides inaccurate feedback, or takes too long.

**Remove personal information before posting. GitHub issues and their attachments may be public.**

## Run locally

You need Python 3.11+ and an OpenAI API key. Download the repository and open a terminal in its folder. A virtual environment is recommended.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Before starting, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter your own API key there, or set the `OPENAI_API_KEY` environment variable. Never commit your key. API usage incurs charges.

## For educators

Change `activity.json` to edit the student-facing question and `rubric.json` to edit the private answer guidance and scoring criteria. Restart the app and start a new attempt to use your changes.

## Before you participate

This is an early prototype, and the AI can make mistakes. Conversations are sent to OpenAI to generate responses and saved on the computer or server running the app. Avoid entering personal or sensitive information. Feedback is for exploration and improvement, not a validated measure of learning.
