import streamlit as st
import pandas as pd
import requests
import base64
from datetime import timezone, timedelta

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_FILE = st.secrets["GITHUB_FILE"]

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"

# ================= INIT =================
def init_data():
    return pd.DataFrame({
        "character": [
            "Cleric", "Chanter", "Templar", "Gladiator",
            "Ranger", "Sorcerer", "Assassin", "Elementalist"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [pd.Timestamp.now(tz=UTC7)]*8
    })

# ================= LOAD =================
def load_data():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(API_URL, headers=headers)

    if res.status_code == 200:
        content = res.json()
        file_data = base64.b64decode(content["content"])
        df = pd.read_csv(pd.io.common.BytesIO(file_data))
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
        return df, content["sha"]

    return init_data(), None

# ================= SAVE =================
def save_data(df, sha):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    csv_data = df.to_csv(index=False)
    encoded = base64.b64encode(csv_data.encode()).decode()

    payload = {
        "message": "update data",
        "content": encoded,
        "sha": sha
    }

    requests.put(API_URL, json=payload, headers=headers)

# ================= TIME BLOCK =================
def get_block_time(dt):
    if dt.tzinfo is None:
        dt = dt.tz_localize(UTC7)
    else:
        dt = dt.tz_convert(UTC7)

    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = pd.to_datetime(df.loc[i, "last_update"], errors="coerce")

        if pd.isna(last):
            df.loc[i, "last_update"] = now_block
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        diff_hours = int((now_block - last).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last + pd.Timedelta(hours=blocks * 3)

    return df

# ================= ALERT =================
def check_alert(df):
    full_energy = df[df["energy"] >= MAX_ENERGY]["character"].tolist()
    full_nightmare = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].tolist()
    return full_energy, full_nightmare

# ================= HIGHLIGHT =================
def highlight_status(df):
    def color_energy(val):
        if val >= MAX_ENERGY:
            return "background-color: red; color: white"
        elif val >= MAX_ENERGY * 0.8:
            return "background-color: yellow"
        return ""

    def color_nightmare(val):
        if val >= MAX_NIGHTMARE:
            return "background-color: red; color: white"
        elif val >= MAX_NIGHTMARE * 0.8:
            return "background-color: yellow"
        return ""

    style = pd.DataFrame("", index=df.index, columns=df.columns)
    style["energy"] = df["energy"].apply(color_energy)
    style["nightmare"] = df["nightmare"].apply(color_nightmare)
    return style

# ================= INIT SESSION =================
if "df" not in st.session_state:
    df, sha = load_data()
    st.session_state.df = df
    st.session_state.sha = sha

# ================= APP =================
st.set_page_config(page_title="Energy Tracker PRO", layout="wide")
st.title("⚡ Energy Tracker PRO (GitHub Sync)")

# luôn update energy trước khi hiển thị
st.session_state.df = update_energy(st.session_state.df)

# ================= ALERT =================
full_energy, full_nightmare = check_alert(st.session_state.df)

if full_energy or full_nightmare:
    st.warning("⚠️ Cảnh báo trạng thái đầy!")

if full_energy:
    st.error(f"🔥 Full Energy: {', '.join(full_energy)}")

if full_nightmare:
    st.error(f"💀 Full Nightmare: {', '.join(full_nightmare)}")

# ================= TABLE =================
st.subheader("📊 Bảng dữ liệu")
styled_df = st.session_state.df.style.apply(lambda x: highlight_status(st.session_state.df), axis=None)
st.dataframe(styled_df, use_container_width=True)

# ================= SELECT =================
st.subheader("🎮 Chọn nhân vật")

idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

# ================= INPUT =================
col1, col2, col3 = st.columns(3)

with col1:
    energy = st.number_input("Energy", 0, MAX_ENERGY, int(st.session_state.df.loc[idx, "energy"]))

with col2:
    nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(st.session_state.df.loc[idx, "nightmare"]))

with col3:
    trial = st.number_input("Trial", 0, 10, int(st.session_state.df.loc[idx, "trial"]))

# ================= SAVE BUTTON =================
if st.button("💾 Save"):
    # update local state ngay lập tức
    st.session_state.df.loc[idx, "energy"] = energy
    st.session_state.df.loc[idx, "nightmare"] = nightmare
    st.session_state.df.loc[idx, "trial"] = trial

    # save github
    save_data(st.session_state.df, st.session_state.sha)

    # reload lại sha mới (QUAN TRỌNG)
    new_df, new_sha = load_data()
    st.session_state.df = new_df
    st.session_state.sha = new_sha

    st.success("✅ Saved & synced!")
    st.rerun()

# ================= GLOBAL =================
st.subheader("🔧 Toàn server")

c1, c2 = st.columns(2)

with c1:
    if st.button("🔁 Reset Trial = 3"):
        st.session_state.df["trial"] = 3
        save_data(st.session_state.df, st.session_state.sha)

        new_df, new_sha = load_data()
        st.session_state.df = new_df
        st.session_state.sha = new_sha

        st.rerun()

with c2:
    if st.button("⚔️ +2 Nightmare"):
        st.session_state.df["nightmare"] = (st.session_state.df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
        save_data(st.session_state.df, st.session_state.sha)

        new_df, new_sha = load_data()
        st.session_state.df = new_df
        st.session_state.sha = new_sha

        st.rerun()

# ================= MANUAL ENERGY =================
st.subheader("⚡ Energy System")

if st.button("Update Energy Now"):
    st.session_state.df = update_energy(st.session_state.df)
    save_data(st.session_state.df, st.session_state.sha)

    new_df, new_sha = load_data()
    st.session_state.df = new_df
    st.session_state.sha = new_sha

    st.rerun()
