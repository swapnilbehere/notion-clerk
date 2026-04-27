"""Notion Clerk — Streamlit chat interface."""

import html
import logging

import streamlit as st

from notion_clerk import run_agent_turn
from notion_clerk.config import DEMO_MODE, NOTION_FEEDBACK_DB_ID
from notion_clerk.demo_tools import make_write_tools
from notion_clerk.tools import submit_feedback, get_recent_feedback

st.set_page_config(
    page_title="Notion Clerk",
    page_icon="🗂",
    layout="centered",
    initial_sidebar_state="expanded",
)


def _init_session() -> None:
    defaults = {
        "messages": [],
        "gemini_history": [],
        "write_buffer": [],
        "feedback_submitted": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🗂 Notion Clerk")
        st.markdown(
            "This is **Swapnil Behere's** portfolio workspace — "
            "an AI/ML Software Engineer (M.S. CS, Santa Clara University). "
            "Ask anything about his experience, projects, or skills."
        )
        st.markdown(
            "**What's here:**\n"
            "- 💼 Work Experience\n"
            "- 🚀 Projects\n"
            "- 🛠 Skills\n"
            "- 🎓 Education"
        )
        st.markdown("[⭐ View on GitHub](https://github.com/swapnilbehere/notion-clerk)")

        st.divider()

        st.subheader("💬 Leave Feedback")
        if st.session_state.feedback_submitted:
            st.success("Thanks! Your feedback was saved to Notion.")
        elif not NOTION_FEEDBACK_DB_ID:
            st.caption("Feedback not configured yet.")
        else:
            name = st.text_input("Your name (optional)", max_chars=50, key="fb_name")
            message = st.text_area(
                "Message", max_chars=280, placeholder="What did you think?", key="fb_msg"
            )
            if st.button("Submit Feedback"):
                clean_msg = html.escape(message.strip())
                if clean_msg:
                    with st.spinner("Saving..."):
                        submit_feedback(name, clean_msg)
                    st.session_state.feedback_submitted = True
                    st.rerun()
                else:
                    st.warning("Please enter a message.")

        st.divider()

        if NOTION_FEEDBACK_DB_ID:
            st.subheader("🗣 Recent Feedback")
            with st.spinner(""):
                entries = get_recent_feedback(limit=5)
            if entries:
                for entry in entries:
                    st.markdown(f"**{entry['name']}** — {entry['message']}")
            else:
                st.caption("No feedback yet. Be the first!")


def _handle_message(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})

    write_tools = make_write_tools(
        session_state=st.session_state,
        demo_mode=DEMO_MODE,
    )

    with st.spinner(""):
        try:
            response, new_entries = run_agent_turn(
                user_message=prompt,
                gemini_history=st.session_state.gemini_history,
                write_tools=write_tools,
            )
        except Exception as exc:
            logging.error("Agent error: %s", exc)
            response = (
                "Sorry, I hit an error talking to the AI backend. "
                "This is usually a temporary API issue — please try again in a moment."
            )
            new_entries = []

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.gemini_history.extend(new_entries)


def main() -> None:
    _init_session()
    _render_sidebar()

    st.title("Notion Clerk")
    st.markdown(
        "👋 This is **Swapnil Behere's** portfolio — an AI/ML Engineer building GenAI & ML systems.  \n"
        "Ask about his projects, skills, or experience. Everything lives in Notion and answers in seconds."
    )

    if not st.session_state.messages:
        st.markdown("**Try one of these:**")
        cols = st.columns(3)
        quick_prompts = [
            ("🚀 His projects", "What projects has Swapnil built?"),
            ("🛠 His skills", "What are Swapnil's top ML and GenAI skills?"),
            ("💼 His experience", "Show Swapnil's work experience"),
        ]
        for col, (label, prompt) in zip(cols, quick_prompts):
            with col:
                if st.button(label, use_container_width=True):
                    st.session_state.pending_prompt = prompt
                    st.rerun()

    if "pending_prompt" in st.session_state:
        queued = st.session_state.pop("pending_prompt")
        _handle_message(queued)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Ask me to manage your Notion workspace..."):
        _handle_message(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
