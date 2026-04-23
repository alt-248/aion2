import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

# ===== CONFIG =====
MAX_ENERGY = 840
MAX_NIGHTMARE = 14

REPO = st.secrets.get("GITHUB_REPO", "")
TOKEN = st.secrets.get("GITHUB_TOKEN", "")
FILE_PATH = st.secrets.get("GITHUB_FILE", "data.csv")

if not REPO or not TOKEN:
    st.error("❌ Thiếu cấu hình GitHub trong secrets")
    st.stop()

# ===== GEAR =====
gear_slots = [
    "weapon","shield","shoulder","gloves","armor","pants",
    "cloak","boots","earring1","earring2",
    "necklace","ring1","ring2","bracelet1","bracelet2"
]

# ===== INIT =====
def init_default_data():
    chars = ["Cleric","Chanter","Templar","Gladiator",
             "Ranger","Sorcerer","Assassin","Elementalist"]

    now = datetime.now()

    data = []
    for c in chars:
        row = {
            "character": c,
            "energy": 0,
            "nightmare": 0,
            "trial": 0,
            "power": 0,
            "dps": 0,
            "last_update": now,
            "last_nm_update": now
        }

        for g in gear_slots:
            row[f"{g}_level"] = 0

        data.append(row)

    return pd.DataFrame(data)

# ===== GITHUB =====
def get_file_sha():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)

    if res.status_code == 200:
        return res.json()["sha"]
    return None

def save_all(df):
    df_copy = df.copy()

    df_copy["last_update"] = df_copy["last_update"].astype(str)
    df_copy["last_nm_update"] = df_copy["last_nm_update"].astype(str)

    csv_content = df_copy.to_csv(index=False)
    encoded = base64.b64encode(csv_content.encode()).decode()

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}

    sha = get_file_sha()

    data = {
        "message": "update data",
        "content": encoded
    }

    if sha:
        data["sha"] = sha

    res = requests.put(url, json=data, headers=headers)

    if res.status_code not in [200, 201]:
        st.error(res.text)
        return False

    return True

# ===== LOAD =====
@st.cache_data(ttl=10)
def load_data():
    url = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"

    try:
        df = pd.read_csv(url)
    except:
        df = init_default_data()
        save_all(df)
        return df

    # đảm bảo có gear
    for g in gear_slots:
        col = f"{g}_level"
        if col not in df:
            df[col] = 0

    # FIX datetime (NO TZ)
    df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    df["last_nm_update"] = pd.to_datetime(df["last_nm_update"], errors="coerce")

    now = datetime.now()

    df["last_update"] = df["last_update"].fillna(now)
    df["last_nm_update"] = df["last_nm_update"].fillna(now)

    return df

# ===== TIME =====
def get_block_time(dt):
    return dt.replace(hour=(dt.hour//3)*3, minute=0, second=0, microsecond=0)

# ===== ENERGY =====
def update_energy(df):
    now_block = get_block_time(datetime.now())

    for i in df.index:
        last = df.loc[i,"last_update"]

        if pd.isna(last):
            df.at[i,"last_update"] = now_block
            continue

        diff = int((now_block - last).total_seconds() // 3600) // 3

        if diff > 0:
            df.at[i,"energy"] = min(df.loc[i,"energy"] + diff*15, MAX_ENERGY)
            df.at[i,"last_update"] = last + timedelta(hours=diff*3)

    return df

# ===== NIGHTMARE =====
def update_nm(df):
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for i in df.index:
        last = df.loc[i,"last_nm_update"]

        if pd.isna(last):
            df.at[i,"last_nm_update"] = now
            continue

        days = (now - last.replace(hour=0, minute=0, second=0, microsecond=0)).days

        if days > 0:
            df.at[i,"nightmare"] = min(df.loc[i,"nightmare"] + days*2, MAX_NIGHTMARE)
            df.at[i,"last_nm_update"] = now

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
    df.loc[idx,"last_update"] = get_block_time(datetime.now())

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
