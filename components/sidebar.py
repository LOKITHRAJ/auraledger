import streamlit as st


def render_sidebar():
    """
    Renders the sidebar navigation. Styling lives in components/theme.py
    (injected once in app.py) -- this only renders markup.
    """
    with st.sidebar:
        st.markdown(
            '<div class="al-sidebar-logo"><div style="justify-content: center"><h2>AuraLedgerIQ</h2></div></div>',
            unsafe_allow_html=True,
        )

        if "current_page" not in st.session_state:
            st.session_state["current_page"] = "Dashboard"

        # Kept deliberately short -- one entry per real feature, nothing added
        # just to fill space. "Results" is the internal page key (unchanged, to
        # avoid touching every place that routes to it); "Transactions" is what
        # the user sees.
        pages = [
            ("📊 Dashboard", "Dashboard"),
            ("📤 Upload Statement", "Upload"),
            ("📋 Transactions", "Results"),
            ("⚙️ Settings", "Settings"),
        ]

        for label, val in pages:
            is_active = st.session_state["current_page"] == val
            if is_active:
                st.button(label, key=f"nav_{val}", use_container_width=True, type="primary")
            else:
                if st.button(label, key=f"nav_{val}", use_container_width=True):
                    st.session_state["current_page"] = val
                    st.rerun()

        username = st.session_state.get("username", "Guest")
        # st.markdown(f"""
        #     <div class="al-sidebar-profile">
        #         <div class="al-sidebar-profile-name">👤 {username}</div>
        #     </div>
        # """, unsafe_allow_html=True)
        
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state["authenticated"] = False
            st.session_state["current_page"] = "Login"
            st.rerun()
