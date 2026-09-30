"""Run: python -m streamlit run app.py"""
import hmac
import json
import os
import streamlit as st
from config import load_bundle
from core import fresh, respond, record, save_final, public_export
from gateway import Gateway
from storage import Store

st.set_page_config(page_title='Learning Lab', page_icon='💡', layout='wide')


def setting(name, default=''):
    try:
        return st.secrets.get(name) or os.getenv(name, default)
    except Exception:
        return os.getenv(name, default)


store = Store()
try:
    current_bundle = load_bundle()
except Exception:
    current_bundle = None
    st.error('The activity configuration needs attention. Run python config.py in the project folder for details.')
    if 'attempt' not in st.session_state:
        st.stop()

if 'attempt' not in st.session_state:
    st.session_state.attempt = fresh(current_bundle)
a = st.session_state.attempt
activity = a['bundle']['activity']
key = setting('OPENAI_API_KEY')
model = setting('OPENAI_MODEL', 'gpt-5')
gateway = Gateway(key, model, setting('OPENAI_REASONING_EFFORT', 'medium')) if key else None


def persist():
    store.save(a)


def run(text, stage, control=None, retry=False):
    with st.spinner('Thinking about your response…'):
        respond(a, text, stage, gateway, control, retry)
    persist()
    st.rerun()


def go(stage):
    a['stage'] = stage
    a['pending_offer'] = False
    record(a, 'system', stage, 'navigation', 'stage_change')
    persist()
    st.rerun()


def draft(field):
    a['drafts'][field] = st.session_state[field + '_' + a['attempt_id']]
    persist()


def chat(stage=None):
    for m in a['transcript']:
        if m['role'] in ('user', 'assistant') and (stage is None or m['stage'] == stage):
            with st.chat_message(m['role']):
                st.markdown(m['content'])


def controls(stage):
    disabled = gateway is None or bool(a['last_error'])
    if a['pending_offer']:
        yes, no = st.columns(2)
        if yes.button('Yes, explain directly', key=stage+'_accept', disabled=disabled):
            run('Yes, please explain directly.', stage, 'accept_answer')
        if no.button('Keep guiding me', key=stage+'_decline', disabled=disabled):
            run('Please keep guiding me.', stage, 'decline_answer')
    if stage == 'discussion':
        if st.button('I need a hint', disabled=disabled):
            run('Please give me a hint.', stage, 'hint')
    if st.button('I would like a direct explanation', key=stage+'_direct', disabled=disabled):
        run('Please explain the activity answer directly.', stage, 'request_direct')


with st.sidebar:
    st.header('Your activity')
    st.caption('Clarify → Explain → Discuss → Reflect')
    if st.button('Save and start a new attempt', disabled=current_bundle is None):
        persist()
        st.session_state.attempt = fresh(current_bundle)
        st.rerun()
    st.download_button('Download my conversation', json.dumps(public_export(a), indent=2, ensure_ascii=False),
                       'learning-conversation.json', 'application/json')
    if current_bundle and current_bundle['version'] != a['bundle']['version']:
        st.info('A new activity version is available. Start a new attempt to use it; this attempt keeps its original version.')
    if not gateway:
        st.info('To use the live tutor, keep your existing OPENAI_API_KEY in .streamlit/secrets.toml or your environment.')
    password = setting('TUTOR_INSTRUCTOR_PASSWORD')
    instructor = False
    if password:
        with st.expander('Instructor access'):
            entered = st.text_input('Instructor password', type='password')
            instructor = bool(entered) and hmac.compare_digest(entered, password)
    if instructor:
        st.download_button('Download research record', json.dumps(a, indent=2, ensure_ascii=False),
                           'learning-research-record.json', 'application/json')
        with st.expander('Private rubric and assessment'):
            st.json(a['bundle']['rubric'])
            st.write('Cumulative discussion assessment')
            st.json(a['assessment'])
            st.write('Latest final explanation assessment')
            st.json(a['final_assessment'])
        attempts = store.list()
        if attempts:
            by_id = {x['attempt_id']: x for x in attempts}
            selected = st.selectbox('Saved attempts', list(by_id), format_func=lambda i: by_id[i]['started_at']+' · '+by_id[i]['bundle']['activity']['title'])
            if st.button('Resume selected attempt'):
                persist()
                st.session_state.attempt = by_id[selected]
                st.rerun()

st.title(activity['title'])
left, right = st.columns([1, 1.25], gap='large')
with left:
    if activity['instructions']:
        st.caption(activity['instructions'])
    if activity['scenario']:
        st.write(activity['scenario'])
    if activity['table']:
        t = activity['table']
        st.table({name: [row[i] for row in t['rows']] for i, name in enumerate(t['columns'])})
    if activity['data_note']:
        st.caption(activity['data_note'])
    if activity['assumptions']:
        with st.expander('Given information'):
            for assumption in activity['assumptions']:
                st.write(assumption)
    st.markdown('**'+activity['question']+'**')

with right:
    if a['last_error']:
        st.error(a['last_error'])
        if st.button('Retry saved message', disabled=gateway is None):
            last = a['events'][-1]
            run('', last['stage'], retry=True)
        if st.button('Continue without this reply'):
            a['last_error'] = None
            a['pending_offer'] = False
            persist()
            st.rerun()
    if a['stage'] == 'clarification':
        st.subheader('Clarify the question')
        st.caption('Ask about an unfamiliar word or detail, or move straight to your explanation.')
        chat('clarification')
        with st.form('clarify', clear_on_submit=True):
            question = st.text_area('Your question')
            send = st.form_submit_button('Ask the tutor', disabled=gateway is None or bool(a['last_error']))
        if send and question.strip():
            run(question, 'clarification')
        controls('clarification')
        if st.button('Write my initial explanation', type='primary'):
            go('initial')
    elif a['stage'] == 'initial':
        st.subheader('Your initial explanation')
        text = st.text_area('Explain your current thinking', value=a['drafts'].get('initial', a['initial']),
                            key='initial_'+a['attempt_id'], height=200, on_change=draft, args=('initial',))
        if st.button('Discuss my explanation', type='primary', disabled=gateway is None):
            if text.strip():
                a['initial'] = text
                a['stage'] = 'discussion'
                run(text, 'discussion')
            else:
                st.info('Write your current thinking first. It is fine to be uncertain.')
        if st.button('Back to clarification'):
            go('clarification')
    elif a['stage'] == 'discussion':
        st.subheader('Discuss your thinking')
        chat('discussion')
        if not a['discussion_ended']:
            with st.form('discuss', clear_on_submit=True):
                text = st.text_area('Your response or question')
                send = st.form_submit_button('Send', disabled=gateway is None or bool(a['last_error']))
            if send and text.strip():
                run(text, 'discussion')
            controls('discussion')
        if st.button('Write my final explanation', type='primary'):
            if not a['discussion_ended']:
                a['stop_reason'] = 'student_chose_final'
            a['discussion_ended'] = True
            a['last_error'] = None
            go('final')
    else:
        st.subheader('Your final explanation and reflection')
        with st.expander('Review our conversation'):
            chat()
        final = st.text_area('Your final explanation', value=a['drafts'].get('final', a['final'] or a['initial']),
                             key='final_'+a['attempt_id'], height=200, on_change=draft, args=('final',))
        reflection = st.text_area(activity['reflection_prompt'], value=a['drafts'].get('reflection', a['reflection']),
                                  key='reflection_'+a['attempt_id'], on_change=draft, args=('reflection',))
        if st.button('Save final explanation', type='primary'):
            if final.strip():
                save_final(a, final, reflection)
                persist()
                st.rerun()
            else:
                st.info('Write your current explanation first.')
        if a['finished']:
            dirty = final != a['final'] or reflection != a['reflection']
            st.success('Your explanation is saved.')
            if dirty:
                st.info('Save your changes before requesting feedback.')
            if st.button('Get formative feedback', disabled=gateway is None or dirty or bool(a['last_error'])):
                run('Please give feedback on my explanation and how my thinking developed.', 'feedback')
            chat('feedback')
            if not dirty:
                controls('feedback')
