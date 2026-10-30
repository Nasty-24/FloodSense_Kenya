"""FloodSense officer page.

    .venv\\Scripts\\streamlit run app.py
"""

import pandas as pd
import streamlit as st

from floodsense.agent import MODEL, ask_gemma
from floodsense.alerts import check_alert, list_alerts, set_status
from floodsense.wards import SOURCE, find_ward, load_wards

st.set_page_config(page_title="FloodSense Kenya", page_icon="🌊", layout="wide")
st.title("FloodSense Kenya · Budalangi, Busia County")
st.warning(f"**REPLAY DATA:** {SOURCE}.", icon="⚠️")

wards = load_wards()
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("Wards ranked by flood risk")
    st.map(wards.assign(size=wards["people_exposed"] / 8), latitude="lat", longitude="lon", size="size", zoom=10)
    table = wards[["ward", "risk_score", "flooded_pct", "people_exposed", "schools_flooded", "clinics_flooded"]]
    st.dataframe(table, hide_index=True, use_container_width=True, column_config={
        "risk_score": st.column_config.ProgressColumn("risk", min_value=0, max_value=1, format="%.2f"),
        "flooded_pct": st.column_config.NumberColumn("flooded %"),
        "people_exposed": st.column_config.NumberColumn("people exposed", format="%d"),
    })

with right:
    st.subheader("Ask Gemma")
    with st.form("ask"):
        question = st.text_input("Question", "Ni kata zipi zinahitaji hatua kwanza? Andika tahadhari kwa kata ya kwanza.")
        asked = st.form_submit_button("Ask", type="primary")
    if asked:
        with st.spinner(f"{MODEL} is reading the ward data…"):
            try:
                st.session_state["reply"] = ask_gemma(question)
            except Exception as exc:
                st.session_state["reply"] = None
                st.error(f"Gemma is unavailable right now, so no answer was produced. ({exc})")
    if reply := st.session_state.get("reply"):
        st.markdown(reply["answer"])
        with st.expander(f"Tools Gemma called ({len(reply['tool_calls'])}) · model: {reply['model']}"):
            st.json(reply["tool_calls"])

    st.subheader("Alerts waiting for approval")
    pending = list_alerts("pending")
    if not pending:
        st.caption("No drafts yet. Ask Gemma to draft an alert.")
    for alert in pending:
        with st.container(border=True):
            st.markdown(f"**{alert['ward']}** · {'Kiswahili' if alert['language'] == 'sw' else 'English'} · drafted {alert['created']}")
            text = st.text_area("Alert", alert["text"], key=f"t{alert['id']}", label_visibility="collapsed")
            problems = check_alert(text, find_ward(alert["ward"]))
            st.caption(f"{len(text)}/160 characters")
            for p in problems:
                st.error(p)
            ok, no = st.columns(2)
            if ok.button("Approve", key=f"a{alert['id']}", type="primary", disabled=bool(problems), use_container_width=True):
                set_status(alert["id"], "approved", text)
                st.rerun()
            if no.button("Reject", key=f"r{alert['id']}", use_container_width=True):
                set_status(alert["id"], "rejected")
                st.rerun()

    st.subheader("Approved alerts")
    approved = list_alerts("approved")
    if approved:
        st.dataframe(pd.DataFrame(approved)[["decided", "ward", "language", "text"]], hide_index=True, use_container_width=True)
    else:
        st.caption("Nothing approved yet.")
