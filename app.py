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

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

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
    res = requests.get(API_URL, headers=HEADERS)

    if res.status_code == 200:
        content = res.json()
        file_data = base64.b64decode(content["content"])

        df = pd.read_csv(pd.io.common.BytesIO(file_data))
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")

        return df, content["sha"]

    elif res.status_code == 404:
        st.warning("⚠️ File chưa tồn tại trên GitHub → tạo mới")
        df = init_data()
        sha = create_file(df)
        return df, sha

    else:
        st.error(f"❌ Load lỗi GitHub: {res.text}")
        return init_data(), None

# ================= CREATE FILE =================
def create_file(df):
    csv_data = df.to_csv(index=False)
    encoded = base64.b64encode(csv_data.encode()).decode()

    payload = {
        "message": "create data file",
        "content": encoded
    }

    res = requests.put(API_URL, json=payload, headers=HEADERS)

    if res.status_code in [200, 201]:
        return res.json()["content"]["sha"]
    else:
        st.error(f"❌ Create file lỗi: {res.text}")
        return None

# ================= SAVE =================
def save_data(df, sha):
    csv_data = df.to_csv(index=False)
    encoded = base64.b64encode(csv_data.encode()).decode()

    payload = {
        "message": "update data",
        "content": encoded,
    }

    if sha:
        payload["sha"] = sha

    res = requests.put(API_URL, json=payload, headers=HEADERS)

    if res.status_code in [200, 201]:
        return res.json()["content"]["sha"]
    else:
        st.error(f"❌ Save lỗi: {res.text}")
        return sha

# ================= TIME =================
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

# ================= SESSION =================
if "df" not in st.session_state:
    df, sha = load_data()
    st.session_state.df = df
    st.session_state.sha = sha

# ================= APP =================
st.title("⚡ Energy Tracker GitHub FIX")

# update energy mỗi lần load
st.session_state.df = update_energy(st.session_state.df)

st.dataframe(st.session_state.df, use_container_width=True)

idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

energy = st.number_input("Energy", 0, MAX_ENERGY, int(st.session_state.df.loc[idx, "energy"]))
nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(st.session_state.df.loc[idx, "nightmare"]))
trial = st.number_input("Trial", 0, 10, int(st.session_state.df.loc[idx, "trial"]))

# ================= SAVE =================
if st.button("💾 Save"):
    st.session_state.df.loc[idx, "energy"] = energy
    st.session_state.df.loc[idx, "nightmare"] = nightmare
    st.session_state.df.loc[idx, "trial"] = trial

    new_sha = save_data(st.session_state.df, st.session_state.sha)
    st.session_state.sha = new_sha

    st.success("✅ Saved thành công!")
    st.rerun()
