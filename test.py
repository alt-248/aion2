import streamlit as st
import pandas as pd
from datetime import timezone, timedelta
from supabase import create_client

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

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
    res = supabase.table("energy_tracker1").select("*").execute()
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

# ================= TIME =================
def get_block_time(dt):
    dt = dt.astimezone(UTC7)
    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = df.loc[i, "last_update"]
        last_block = get_block_time(last)

        diff_hours = int((now_block - last_block).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(
                df.loc[i, "energy"] + blocks * 15,
                MAX_ENERGY
            )

            df.loc[i, "last_update"] = last_block + pd.Timedelta(hours=blocks * 3)

    return df

# ================= ALERT =================
def check_alert(df):
    full_energy = df[df["energy"] >= MAX_ENERGY]["character"].tolist()
    warn_energy = df[(df["energy"] >= MAX_ENERGY*0.8) & (df["energy"] < MAX_ENERGY)]["character"].tolist()

    full_nightmare = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].tolist()
    warn_nightmare = df[(df["nightmare"] >= MAX_NIGHTMARE*0.8) & (df["nightmare"] < MAX_NIGHTMARE)]["character"].tolist()

    return full_energy, warn_energy, full_nightmare, warn_nightmare

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

# ================= NEW: GEAR CONFIG =================
GEAR_COLUMNS = [
    "luc_chien","dps","vu_khi","khien","non","vai","giap","quan",
    "tay","ao_choang","giay","bong_tai_1","bong_tai_2",
    "day_chuyen","nhan_1","nhan_2","vong_tay_1","vong_tay_2"
]

# ================= NEW: LOAD GEAR =================
def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        return pd.DataFrame(columns=["character"] + GEAR_COLUMNS)

    return df

# ================= NEW: SAVE GEAR =================
def save_gear(character, data):
    payload = {"character": character}
    for col in GEAR_COLUMNS:
        val = data.get(col)
        payload[col] = int(val) if val not in [None, ""] else None

    supabase.table("gear_tracker").upsert(payload).execute()

# ================= NEW: GEAR SCORE =================
def calc_gear_score(row):
    total = 0
    for col in GEAR_COLUMNS[2:]:  # bỏ lực chiến + dps
        if pd.notna(row.get(col)):
            total += row[col]
    return total

# ================= NEW: HIGHLIGHT GEAR =================
def highlight_gear(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    for col in GEAR_COLUMNS[2:]:
        avg = df[col].mean(skipna=True)

        def color(val):
            if pd.isna(val):
                return ""
            if val < avg:
                return "background-color: red; color: white"
            return ""

        style[col] = df[col].apply(color)

    return style

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

if "gear_df" not in st.session_state:
    st.session_state.gear_df = load_gear()

# ================= APP =================
st.set_page_config(page_title="Energy Tracker PRO", layout="wide")
st.title("⚡ Energy Tracker PRO (Supabase FIXED)")

st.session_state.df = update_energy(st.session_state.df)

# ================= ALERT =================
full_e, warn_e, full_n, warn_n = check_alert(st.session_state.df)

if full_e:
    st.error(f"⚡ Full Energy: {', '.join(full_e)}")

if warn_e:
    st.warning(f"⚡ Energy 80%+: {', '.join(warn_e)}")

if full_n:
    st.error(f"💀 Full Nightmare: {', '.join(full_n)}")

if warn_n:
    st.warning(f"💀 Nightmare 80%+: {', '.join(warn_n)}")

# ================= TABLE =================
st.subheader("📊 Bảng dữ liệu")
styled_df = st.session_state.df.style.apply(lambda x: highlight_status(st.session_state.df), axis=None)
st.dataframe(styled_df, use_container_width=True)

# ================= SELECT =================
idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

row = st.session_state.df.loc[idx]
character_name = row["character"]

# ================= INPUT =================
col1, col2, col3 = st.columns(3)

with col1:
    energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))

with col2:
    nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))

with col3:
    trial = st.number_input("Trial", 0, 10, int(row["trial"]))

# ================= SAVE =================
if st.button("💾 Save"):
    st.session_state.df.loc[idx, "energy"] = energy
    st.session_state.df.loc[idx, "nightmare"] = nightmare
    st.session_state.df.loc[idx, "trial"] = trial
    st.session_state.df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    save_row(st.session_state.df.loc[idx])

    st.success("✅ Saved!")
    st.rerun()

# ================= NEW: GEAR UI =================
st.subheader("🛡️ Gear Tracker")

gear_df = st.session_state.gear_df
gear_row = gear_df[gear_df["character"] == character_name]

gear_data = {}
cols = st.columns(4)

for i, col in enumerate(GEAR_COLUMNS):
    val = None
    if not gear_row.empty and col in gear_row.columns:
        val = gear_row.iloc[0].get(col)

    with cols[i % 4]:
        gear_data[col] = st.number_input(col, 0, 100, int(val) if pd.notna(val) else 0)

if st.button("💾 Save Gear"):
    save_gear(character_name, gear_data)
    st.success("Saved Gear!")
    st.rerun()

# ================= NEW: SHOW GEAR TABLE =================
st.subheader("📊 Gear Table")

gear_df = load_gear()

if not gear_df.empty:
    gear_df["gear_score"] = gear_df.apply(calc_gear_score, axis=1)
    styled = gear_df.style.apply(lambda x: highlight_gear(gear_df), axis=None)
    st.dataframe(styled, use_container_width=True)
