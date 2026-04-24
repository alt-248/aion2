import streamlit as st
import pandas as pd
from datetime import timezone, timedelta
from supabase import create_client

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

NAME_MAP = {
    "Cleric": "Buff",
    "Chanter": "Thương",
    "Templar": "Kiếm khiên",
    "Gladiator": "Đại kiếm",
    "Ranger": "Cung",
    "Sorcerer": "Sách",
    "Assassin": "Sát thủ",
    "Elementalist": "Cầu"
}

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= LOAD =================
def safe_parse_time(col):
    parsed = pd.to_datetime(col, errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=UTC7)
    parsed = parsed.fillna(now)
    return parsed.dt.tz_convert(UTC7)

def load_data():
    res = supabase.table("energy_tracker").select("*").execute()
    df = pd.DataFrame(res.data)
    df["last_update"] = safe_parse_time(df["last_update"])
    return df

def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    return pd.DataFrame(res.data)

# ================= SAVE =================
def save_row(row):
    utc_time = row["last_update"].astimezone(timezone.utc)
    supabase.table("energy_tracker").update({
        "energy": int(row["energy"]),
        "nightmare": int(row["nightmare"]),
        "trial": int(row["trial"]),
        "last_update": utc_time.isoformat()
    }).eq("id", int(row["id"])).execute()

def save_gear(row):
    supabase.table("gear_tracker").update(row.to_dict()).eq("id", int(row["id"])).execute()

# ================= TIME =================
def get_block_time(dt):
    dt = dt.astimezone(UTC7)
    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= AUTO NIGHTMARE =================
def auto_nightmare(df):
    now = pd.Timestamp.now(tz=UTC7)
    if now.hour == 3 and now.minute < 5:
        if "last_daily" not in st.session_state:
            st.session_state.last_daily = now.date()

        if st.session_state.last_daily != now.date():
            df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
            st.session_state.last_daily = now.date()

            for i in df.index:
                save_row(df.loc[i])

    return df

# ================= ENERGY =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = get_block_time(df.loc[i, "last_update"])
        diff_hours = int((now_block - last).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last + pd.Timedelta(hours=blocks * 3)

    return df

# ================= HIGHLIGHT =================
def highlight(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)
    style["energy"] = df["energy"].apply(lambda v: "background:red;color:white" if v>=MAX_ENERGY else ("background:yellow" if v>=0.8*MAX_ENERGY else ""))
    style["nightmare"] = df["nightmare"].apply(lambda v: "background:red;color:white" if v>=MAX_NIGHTMARE else ("background:yellow" if v>=0.8*MAX_NIGHTMARE else ""))
    return style

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()
    st.session_state.gear = load_gear()

# ================= APP =================
st.title("⚡ Energy Tracker PRO")

df = st.session_state.df
df = update_energy(df)
df = auto_nightmare(df)

# ================= TABLE =================
df_display = df.copy()
df_display["character"] = df_display["character"].map(NAME_MAP)
df_display = df_display.drop(columns=["id","last_update"])

st.dataframe(df_display.style.apply(lambda x: highlight(df), axis=None), use_container_width=True)

# ================= GEAR =================
st.subheader("🛡️ Gear")

gear = st.session_state.gear
gear["character"] = gear["character"].map(NAME_MAP)

st.data_editor(gear, use_container_width=True)

# ================= ANALYSIS =================
st.subheader("📊 Phân tích Gear")

gear_numeric = gear.drop(columns=["id","character"]).fillna(0)

avg = gear_numeric.mean()

weak_chars = []
for i,row in gear_numeric.iterrows():
    if (row < avg*0.8).sum() > 5:
        weak_chars.append(gear.loc[i,"character"])

if weak_chars:
    st.warning(f"⚠️ Gear yếu: {', '.join(weak_chars)}")

# ================= RANK =================
st.subheader("🏆 Ranking")

gear["score"] = gear_numeric.sum() + gear_numeric["dps"].fillna(0)
rank = gear.sort_values("score", ascending=False)

st.dataframe(rank[["character","score","dps"]], use_container_width=True)

# ================= SAVE GEAR =================
if st.button("💾 Save Gear"):
    for i in st.session_state.gear.index:
        save_gear(st.session_state.gear.loc[i])
    st.success("Saved Gear!")
    st.rerun()
