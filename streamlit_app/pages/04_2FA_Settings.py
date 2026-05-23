"""
2FA Settings — manage TOTP two-factor authentication for your account.
"""

import base64
import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="2FA Settings", page_icon="🔐", layout="centered")

st.markdown("""
<style>
@keyframes fadeInUp { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }

.page-hero {
    background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#0f172a 100%);
    border:1px solid #1e40af; border-radius:18px;
    padding:22px 28px; margin-bottom:24px;
    animation: fadeInUp .5s ease;
}
.page-hero-title { font-size:24px; font-weight:800; color:#f1f5f9; margin:0; }
.page-hero-sub   { font-size:13px; color:#94a3b8; margin-top:4px; }

.status-badge {
    display:inline-flex; align-items:center; gap:8px;
    padding:8px 18px; border-radius:30px; font-weight:700;
    font-size:15px; margin:12px 0;
}
.badge-on  { background:#052e16; border:1.5px solid #16a34a; color:#4ade80; }
.badge-off { background:#1c1917; border:1.5px solid #57534e; color:#a8a29e; }

.step-card {
    background:#1e293b; border:1px solid #334155; border-radius:14px;
    padding:16px 20px; margin:10px 0;
    animation: fadeInUp .4s ease both;
}
.step-num {
    display:inline-flex; align-items:center; justify-content:center;
    width:28px; height:28px; border-radius:50%;
    background:#1d4ed8; color:#fff; font-weight:800; font-size:14px;
    flex-shrink:0;
}

section[data-testid="stSidebar"] { background:#0f172a !important; }
section[data-testid="stSidebar"] * { color:#cbd5e1 !important; }
.stButton > button {
    border-radius:10px !important; font-weight:600 !important;
    transition:transform .15s, box-shadow .15s !important;
}
.stButton > button:hover { transform:translateY(-1px) !important; box-shadow:0 4px 12px rgba(0,0,0,.35) !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-hero">
  <div class="page-hero-title">🔐 Two-Factor Authentication</div>
  <div class="page-hero-sub">Protect your account with a time-based one-time password (TOTP).
  Works with <strong>Google Authenticator</strong>, <strong>Authy</strong>, or any TOTP app.</div>
</div>
""", unsafe_allow_html=True)

# ── Auth guard ───────────────────────────────────────────────────────────────
if not st.session_state.get("auth_token"):
    st.info("🔒 Please log in via the **View Documents** page, then come back here.")
    st.stop()

headers: dict[str, str] = {"Authorization": f"Bearer {st.session_state['auth_token']}"}

# ── Fetch current 2FA status ─────────────────────────────────────────────────
try:
    me_resp = requests.get(f"{API_BASE_URL}/auth/me", headers=headers, timeout=5)
    if me_resp.status_code != 200:
        st.error("Could not fetch account info. Please re-login.")
        st.stop()
    me = me_resp.json()
    totp_enabled: bool = me.get("totp_enabled", False)
except Exception as e:
    st.error(f"Connection error: {e}")
    st.stop()

# ── Status badge ─────────────────────────────────────────────────────────────
if totp_enabled:
    st.markdown(
        '<div class="status-badge badge-on">✅ 2FA is <strong>ENABLED</strong> on your account</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-badge badge-off">⚪ 2FA is <strong>disabled</strong> on your account</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── ENABLE flow ──────────────────────────────────────────────────────────────
if not totp_enabled:
    st.subheader("Enable Two-Factor Authentication")

    st.markdown("""
<div class="step-card">
  <span class="step-num">1</span>&nbsp;&nbsp;Click <strong>Generate QR Code</strong> below.
</div>
<div class="step-card">
  <span class="step-num">2</span>&nbsp;&nbsp;Scan the QR code with <strong>Google Authenticator</strong> or <strong>Authy</strong>.
</div>
<div class="step-card">
  <span class="step-num">3</span>&nbsp;&nbsp;Enter the <strong>6-digit code</strong> shown in your app to confirm and activate 2FA.
</div>
""", unsafe_allow_html=True)

    if "totp_setup" not in st.session_state:
        st.session_state.totp_setup = None

    if st.button("🔄 Generate QR Code", use_container_width=False):
        with st.spinner("Generating…"):
            try:
                r = requests.get(f"{API_BASE_URL}/auth/2fa/setup", headers=headers, timeout=5)
                if r.status_code == 200:
                    st.session_state.totp_setup = r.json()
                else:
                    st.error(r.json().get("detail", "Error generating setup."))
            except Exception as e:
                st.error(f"Connection error: {e}")

    setup = st.session_state.get("totp_setup")
    if setup:
        st.markdown("#### Scan this QR code")
        img_bytes = base64.b64decode(setup["qr_image_b64"])
        st.image(img_bytes, width=220)

        with st.expander("Can't scan? Enter the secret key manually"):
            st.code(setup["secret"], language=None)
            st.caption("Add a new account in your authenticator app → 'Enter a setup key'.")

        st.markdown("#### Confirm with your authenticator code")
        with st.form("enable_2fa_form"):
            confirm_code = st.text_input(
                "6-digit code", placeholder="123456", max_chars=6,
                help="Enter the current code from your authenticator app.",
            )
            enable_btn = st.form_submit_button("✅ Enable 2FA", use_container_width=True)

        if enable_btn:
            if len(confirm_code.strip()) != 6:
                st.error("Please enter a 6-digit code.")
            else:
                try:
                    er = requests.post(
                        f"{API_BASE_URL}/auth/2fa/enable",
                        headers=headers,
                        json={"secret": setup["secret"], "code": confirm_code.strip()},
                        timeout=5,
                    )
                    if er.status_code == 200:
                        st.success("🎉 2FA enabled! Your account is now protected.")
                        st.session_state.totp_setup = None
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(er.json().get("detail", "Enable failed."))
                except Exception as e:
                    st.error(f"Connection error: {e}")

# ── DISABLE flow ─────────────────────────────────────────────────────────────
else:
    st.subheader("Disable Two-Factor Authentication")
    st.warning(
        "⚠️ Disabling 2FA reduces your account security. "
        "You will need to confirm with your current authenticator code."
    )

    with st.form("disable_2fa_form"):
        disable_code = st.text_input(
            "Current 6-digit code", placeholder="123456", max_chars=6,
            help="Enter the code currently shown in your authenticator app.",
        )
        disable_btn = st.form_submit_button("🗑️ Disable 2FA", use_container_width=False)

    if disable_btn:
        if len(disable_code.strip()) != 6:
            st.error("Please enter a 6-digit code.")
        else:
            try:
                dr = requests.post(
                    f"{API_BASE_URL}/auth/2fa/disable",
                    headers=headers,
                    json={"code": disable_code.strip()},
                    timeout=5,
                )
                if dr.status_code == 200:
                    st.success("2FA has been disabled on your account.")
                    st.rerun()
                else:
                    st.error(dr.json().get("detail", "Disable failed."))
            except Exception as e:
                st.error(f"Connection error: {e}")