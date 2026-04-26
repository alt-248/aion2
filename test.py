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

    # FIX SORT
    df = df.sort_values("character").reset_index(drop=True)

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

# ================= AUTO NIGHTMARE =================
def auto_nightmare(df):
    today = datetime.now(UTC7).date()
    now = datetime.now(UTC7)

    if "last_nightmare_update" not in st.session_state:
        st.session_state.last_nightmare_update = None

    # chạy sau 3h sáng và chưa chạy hôm nay
    if now.hour >= 3:
        if st.session_state.last_nightmare_update != today:

            df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)

            for i in df.index:
                save_row(df.loc[i])

            st.session_state.last_nightmare_update = today
            st.success("⚔️ Đã tự động +2 Nightmare hôm nay")

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
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    style["energy"] = df["energy"].apply(lambda v: "background-color:red;color:white" if v>=MAX_ENERGY else "")
    style["nightmare"] = df["nightmare"].apply(lambda v: "background-color:red;color:white" if v>=MAX_NIGHTMARE else "")

    return style

# ================= GEAR =================
GEAR_COLUMNS = [
    "luc_chien","dps","vu_khi","khien","non","vai","giap","quan",
    "tay","ao_choang","giay","bong_tai_1","bong_tai_2",
    "day_chuyen","nhan_1","nhan_2","vong_tay_1","vong_tay_2"
]

def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["character"] + GEAR_COLUMNS)
    return df

def save_gear(character, data):
    payload = {"character": character}
    for col in GEAR_COLUMNS:
        val = data.get(col)
        payload[col] = int(val) if val not in [None, ""] else None

    supabase.table("gear_tracker").upsert(payload).execute()

def calc_gear_score(row):
    return sum([row[c] for c in GEAR_COLUMNS[2:] if pd.notna(row.get(c))])

# FIX: chỉ highlight min
def highlight_gear(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    for col in GEAR_COLUMNS[2:]:
        min_val = df[col].min(skipna=True)

        style[col] = df[col].apply(
            lambda v: "background-color:red;color:white"
            if pd.notna(v) and v == min_val else ""
        )

    return style

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

if "gear_df" not in st.session_state:
    st.session_state.gear_df = load_gear()

# ================= APP =================
st.set_page_config(page_title="Energy Tracker PRO", layout="wide")
st.title("⚡ Energy Tracker PRO")

st.session_state.df = update_energy(st.session_state.df)
st.session_state.df = auto_nightmare(st.session_state.df)

# ================= TABLE =================
st.subheader("📊 Energy")
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
energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))
nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))
trial = st.number_input("Trial", 0, 10, int(row["trial"]))

if st.button("💾 Save"):
    st.session_state.df.loc[idx, ["energy","nightmare","trial"]] = [energy,nightmare,trial]
    st.session_state.df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))
    save_row(st.session_state.df.loc[idx])
    st.rerun()

# ================= RESET =================
if st.button("🔁 Reset Trial = 3"):
    st.session_state.df["trial"] = 3
    for i in st.session_state.df.index:
        save_row(st.session_state.df.loc[i])
    st.rerun()

# ================= GEAR =================
st.subheader("🛡️ Gear")

gear_df = load_gear()
gear_row = gear_df[gear_df["character"] == character_name]

gear_data = {}
cols = st.columns(4)

for i, col in enumerate(GEAR_COLUMNS):
    val = None
    if not gear_row.empty:
        val = gear_row.iloc[0].get(col)

    with cols[i % 4]:
        gear_data[col] = st.number_input(col, value=int(val) if pd.notna(val) else 0, key=f"{character_name}_{col}")

if st.button("💾 Save Gear"):
    save_gear(character_name, gear_data)
    st.rerun()

# ================= ALERT GEAR =================
if not gear_row.empty:
    rowg = gear_row.iloc[0]

    missing = [c for c in GEAR_COLUMNS[2:] if pd.isna(rowg.get(c)) or rowg.get(c)==0]

    weak = []
    for col in GEAR_COLUMNS[2:]:
        min_val = gear_df[col].min(skipna=True)
        if rowg.get(col) == min_val:
            weak.append(col)

    if missing:
        st.warning(f"⚠️ Thiếu gear: {', '.join(missing)}")

    if weak:
        st.error(f"🔻 Gear yếu: {', '.join(weak)}")

# ================= TABLE =================
st.subheader("📊 Gear Table")

if not gear_df.empty:
    gear_df["gear_score"] = gear_df.apply(calc_gear_score, axis=1)
    styled = gear_df.style.apply(lambda x: highlight_gear(gear_df), axis=None)
    st.dataframe(styled, use_container_width=True)
