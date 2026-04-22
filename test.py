import streamlit as st
import pandas as pd
from datetime import timezone, timedelta
from supabase import create_client

# ===== CONFIG =====
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== GEAR =====
gear_slots = [
    "weapon","shield","shoulder","gloves","armor","pants",
    "cloak","boots","earring1","earring2",
    "necklace","ring1","ring2","bracelet1","bracelet2"
]

# ===== INIT =====
def init_data():
    chars = ["Cleric","Chanter","Templar","Gladiator",
             "Ranger","Sorcerer","Assassin","Elementalist"]

    now = pd.Timestamp.now(tz=UTC7)

    for c in chars:
        supabase.table("characters").upsert({
            "character": c,
            "energy": 0,
            "nightmare": 0,
            "trial": 0,
            "power": 0,
            "dps": 0,
            "last_update": str(now),
            "last_nm_update": str(now)
        }, on_conflict="character").execute()

# ===== LOAD =====
def load_data():
    res = supabase.table("characters").select("*").execute()

    if not res.data:
        init_data()
        res = supabase.table("characters").select("*").execute()

    df = pd.DataFrame(res.data)

    df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    df["last_nm_update"] = pd.to_datetime(df["last_nm_update"], errors="coerce")

    return df.fillna(0)

# ===== SAVE =====
def save_row(row):
    supabase.table("characters").upsert(
        row.to_dict(),
        on_conflict="character"
    ).execute()

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
    for g in gear_slots:
        col = f"{g}_level"
        if col not in df:
            df[col] = 0

    df["gear_score"] = df[[f"{g}_level" for g in gear_slots]].sum(axis=1)
    return df

# ===== UI =====
st.set_page_config(layout="wide")
st.title("⚡ Energy Tracker PRO")

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

    save_row(df.loc[idx])
    st.success("Saved!")
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

    save_row(df.loc[idx])
    st.success("Gear saved!")
    st.rerun()

# RANK
st.subheader("🏆 Rank")
rank = df.sort_values(["power","dps","gear_score"],ascending=False)
st.dataframe(rank[["character","power","dps","gear_score"]])
