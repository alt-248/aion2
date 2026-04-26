import streamlit as st
import pandas as pd
from datetime import timezone, timedelta, datetime
from supabase import create_client

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= SYSTEM STATE =================
def load_system_state():
    res = supabase.table("system_state").select("*").execute()
    if not res.data:
        supabase.table("system_state").insert({
            "id": 1,
            "last_nightmare_date": None,
            "last_trial_reset_date": None
        }).execute()
        return {"last_nightmare_date": None, "last_trial_reset_date": None}

    return res.data[0]

def update_system_state(data):
    supabase.table("system_state").update(data).eq("id", 1).execute()

# ================= LOAD =================
def safe_parse_time(col):
    parsed = pd.to_datetime(col, errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=UTC7)
    parsed = parsed.fillna(now)
    return parsed.dt.tz_convert(UTC7)

def load_data():
    res = supabase.table("energy_tracker1").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    df["last_update"] = safe_parse_time(df["last_update"])
    return df

# ================= SAVE =================
def save_row(row):
    utc_time = row["last_update"].astimezone(timezone.utc)

    supabase.table("energy_tracker1").update({
        "energy": int(row["energy"]),
        "nightmare": int(row["nightmare"]),
        "trial": int(row["trial"]),
        "last_update": utc_time.isoformat()
    }).eq("id", int(row["id"])).execute()

# ================= ENERGY =================
def get_block_time(dt):
    dt = dt.astimezone(UTC7)
    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = df.loc[i, "last_update"]
        last_block = get_block_time(last)

        diff_hours = int((now_block - last_block).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last_block + pd.Timedelta(hours=blocks * 3)

    return df

# ================= AUTO SYSTEM =================
def auto_system(df):
    state = load_system_state()
    now = datetime.now(UTC7)
    today = str(now.date())

    # ===== NIGHTMARE =====
    if now.hour >= 3 and state["last_nightmare_date"] != today:
        df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)

        for i in df.index:
            save_row(df.loc[i])

        update_system_state({"last_nightmare_date": today})
        st.success("⚔️ Đã auto +2 Nightmare")

    # ===== RESET TRIAL (THỨ 4) =====
    if now.weekday() == 2 and now.hour >= 3:  # Thứ 4 = 2
        if state["last_trial_reset_date"] != today:
            df["trial"] = 3

            for i in df.index:
                save_row(df.loc[i])

            update_system_state({"last_trial_reset_date": today})
            st.warning("🔁 Đã reset Trial (Thứ 4)")

    return df

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

# ================= RUN =================
st.session_state.df = update_energy(st.session_state.df)
st.session_state.df = auto_system(st.session_state.df)

# ================= UI =================
st.title("⚡ Energy Tracker PRO")

# ẨN CỘT
display_df = st.session_state.df.drop(columns=["id", "last_update"], errors="ignore")

st.dataframe(display_df, use_container_width=True)

# ================= SELECT =================
idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

row = st.session_state.df.loc[idx]

# ================= INPUT =================
energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))
nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))
trial = st.number_input("Trial", 0, 10, int(row["trial"]))

# ================= SAVE =================
if st.button("💾 Save"):
    st.session_state.df.loc[idx, ["energy","nightmare","trial"]] = [energy,nightmare,trial]
    st.session_state.df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    save_row(st.session_state.df.loc[idx])
    st.rerun()
