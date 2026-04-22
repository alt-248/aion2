import streamlit as st
import pandas as pd
import requests
import base64
from datetime import timezone, timedelta

# ===== CONFIG =====
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

REPO = st.secrets["GITHUB_REPO"]
TOKEN = st.secrets["GITHUB_TOKEN"]
FILE_PATH = st.secrets["GITHUB_FILE"]

# ===== GEAR =====
gear_slots = [
    "weapon","shield","shoulder","gloves","armor","pants",
    "cloak","boots","earring1","earring2",
    "necklace","ring1","ring2","bracelet1","bracelet2"
]

# ===== LOAD CSV =====
@st.cache_data(ttl=10)
def load_data():
    url = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"

    try:
        df = pd.read_csv(url)
    except:
        st.error("Không load được CSV từ GitHub")
        return pd.DataFrame()

    # đảm bảo có đủ cột gear
    for g in gear_slots:
        col = f"{g}_level"
        if col not in df:
            df[col] = 0

    df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    df["last_nm_update"] = pd.to_datetime(df["last_nm_update"], errors="coerce")

    return df.fillna(0)

# ===== GET SHA =====
def get_file_sha():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    return res.json()["sha"]

# ===== SAVE =====
def save_all(df):
    csv_content = df.to_csv(index=False)
    encoded = base64.b64encode(csv_content.encode()).decode()

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}

    sha = get_file_sha()

    data = {
        "message": "update from streamlit",
        "content": encoded,
        "sha": sha
    }

    res = requests.put(url, json=data, headers=headers)

    if res.status_code != 200:
        st.error(res.text)
        return False

    return True

# ===== TIME =====
def get_block_time(dt):
    dt = dt.tz_convert(UTC7) if dt.tzinfo else dt.tz_localize(UTC7)
    return dt.replace(hour=(dt.hour//3)*3, minute=0, second=0, microsecond=0)

# ===== ENERGY =====
def update_energy(df):
    now_block = get_block_time(pd.Timestamp.now(tz=UTC7))

    for i in df.index:
        last = df.loc[i,"last_update"]

        if pd.isna(last):
            df.loc[i,"last_update"] = now_block
            continue

        last = last.tz_convert(UTC7) if last.tzinfo else last.tz_localize(UTC7)

        diff = int((now_block-last).total_seconds()//3600)//3

        if diff > 0:
            df.loc[i,"energy"] = min(df.loc[i,"energy"]+diff*15, MAX_ENERGY)
            df.loc[i,"last_update"] = last + pd.Timedelta(hours=diff*3)

    return df

# ===== NIGHTMARE =====
def update_nm(df):
    now = pd.Timestamp.now(tz=UTC7).normalize()

    for i in df.index:
        last = df.loc[i,"last_nm_update"]

        if pd.isna(last):
            df.loc[i,"last_nm_update"] = now
            continue

        last = last.tz_convert(UTC7) if last.tzinfo else last.tz_localize(UTC7)
        days = (now-last.normalize()).days

        if days > 0:
            df.loc[i,"nightmare"] = min(df.loc[i,"nightmare"]+days*2, MAX_NIGHTMARE)
            df.loc[i,"last_nm_update"] = now

    return df

# ===== SCORE =====
def calc_score(df):
    df["gear_score"] = df[[f"{g}_level" for g in gear_slots]].sum(axis=1)
    return df

# ===== UI =====
st.set_page_config(layout="wide")
st.title("⚡ Energy Tracker PRO (GitHub CSV)")

df = load_data()
df = update_energy(df)
df = update_nm(df)
df = calc_score(df)

# TABLE
st.subheader("📊 Energy")
st.dataframe(df[["character","energy","nightmare","trial"]])

# SELECT
idx = st.selectbox("Nhân vật", df.index, format_func=lambda x: df.loc[x,"character"])

# UPDATE
st.subheader("Update")

energy = st.number_input("Energy",0,MAX_ENERGY,int(df.loc[idx,"energy"]))
nm = st.number_input("Nightmare",0,MAX_NIGHTMARE,int(df.loc[idx,"nightmare"]))
trial = st.number_input("Trial",0,10,int(df.loc[idx,"trial"]))

if st.button("💾 Save"):
    df.loc[idx,"energy"] = energy
    df.loc[idx,"nightmare"] = nm
    df.loc[idx,"trial"] = trial
    df.loc[idx,"last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    if save_all(df):
        st.success("Saved!")
        st.cache_data.clear()
        st.rerun()

# GEAR
st.subheader("Gear")

power = st.number_input("Power",0,999999,int(df.loc[idx].get("power",0)))
dps = st.number_input("DPS",0,999999,int(df.loc[idx].get("dps",0)))

gear_data = {}
for g in gear_slots:
    gear_data[g] = st.number_input(g,0,9999,int(df.loc[idx].get(f"{g}_level",0)))

if st.button("💾 Save Gear"):
    for g,v in gear_data.items():
        df.loc[idx,f"{g}_level"] = v

    df.loc[idx["power"]] = power
    df.loc[idx,"power"] = power
    df.loc[idx,"dps"] = dps

    if save_all(df):
        st.success("Gear saved!")
        st.cache_data.clear()
        st.rerun()

# RANK
st.subheader("🏆 Rank")
rank = df.sort_values(["power","dps","gear_score"],ascending=False)
st.dataframe(rank[["character","power","dps","gear_score"]])
