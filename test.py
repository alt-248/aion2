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
    res = supabase.table("energy_tracker1").select("*").execute()
    df = pd.DataFrame(res.data)
    df["last_update"] = safe_parse_time(df["last_update"])
    return df

def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    return pd.DataFrame(res.data)

# ================= SAVE =================
def save_row(row):
    utc_time = row["last_update"].astimezone(timezone.utc)
    supabase.table("energy_tracker1").update({
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

            # FIX QUAN TRỌNG: luôn snap về block
            df.loc[i, "last_update"] = last_block + pd.Timedelta(hours=blocks * 3)

    return df


# ================= ALERT =================
def check_alert(df):
    full_e = df[df["energy"] >= MAX_ENERGY]["character"].map(NAME_MAP).tolist()
    warn_e = df[(df["energy"] >= MAX_ENERGY*0.8) & (df["energy"] < MAX_ENERGY)]["character"].map(NAME_MAP).tolist()

    full_n = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].map(NAME_MAP).tolist()
    warn_n = df[(df["nightmare"] >= MAX_NIGHTMARE*0.8) & (df["nightmare"] < MAX_NIGHTMARE)]["character"].map(NAME_MAP).tolist()

    return full_e, warn_e, full_n, warn_n

# ================= HIGHLIGHT =================
def highlight(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    if "energy" in df.columns:
        style["energy"] = df["energy"].apply(
            lambda v: "background:red;color:white"
            if v >= MAX_ENERGY else
            ("background:yellow" if v >= MAX_ENERGY*0.8 else "")
        )

    if "nightmare" in df.columns:
        style["nightmare"] = df["nightmare"].apply(
            lambda v: "background:red;color:white"
            if v >= MAX_NIGHTMARE else
            ("background:yellow" if v >= MAX_NIGHTMARE*0.8 else "")
        )

    return style

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()
    st.session_state.gear = load_gear()

# ================= APP =================
st.title("⚡ Energy Tracker PRO")

# FIX: luôn lưu lại session
st.session_state.df = update_energy(st.session_state.df)
df = st.session_state.df

# ================= ALERT =================
full_e, warn_e, full_n, warn_n = check_alert(df)

if full_e:
    st.error(f"🔥 Full Energy: {', '.join(full_e)}")
if warn_e:
    st.warning(f"⚠️ Energy 80%+: {', '.join(warn_e)}")
if full_n:
    st.error(f"💀 Full Nightmare: {', '.join(full_n)}")
if warn_n:
    st.warning(f"⚠️ Nightmare 80%+: {', '.join(warn_n)}")

# ================= TABLE =================
df_display = df.copy()
df_display["character"] = df_display["character"].map(NAME_MAP)
df_display = df_display.drop(columns=["id", "last_update"])

st.dataframe(
    df_display.style.apply(lambda x: highlight(df_display), axis=None),
    use_container_width=True
)

# ================= SELECT + INPUT =================
st.subheader("🎮 Chọn nhân vật")

idx = st.selectbox(
    "Character",
    df.index,
    format_func=lambda x: NAME_MAP[df.loc[x, "character"]]
)

row = df.loc[idx]

col1, col2, col3 = st.columns(3)

with col1:
    energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))

with col2:
    nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))

with col3:
    trial = st.number_input("Trial", 0, 10, int(row["trial"]))

# ================= SAVE =================
if st.button("💾 Save"):
    df.loc[idx, "energy"] = energy
    df.loc[idx, "nightmare"] = nightmare
    df.loc[idx, "trial"] = trial
    df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    save_row(df.loc[idx])

    st.success("✅ Saved!")
    st.rerun()

# ================= GEAR =================
st.subheader("🛡️ Gear")

gear = st.session_state.gear.copy()
gear_display = gear.copy()
gear_display["character"] = gear_display["character"].map(NAME_MAP)

edited_gear = st.data_editor(gear_display, use_container_width=True)

# ================= SAVE GEAR =================
if st.button("💾 Save Gear"):
    reverse_map = {v: k for k, v in NAME_MAP.items()}
    edited_gear["character"] = edited_gear["character"].map(reverse_map)

    for i in edited_gear.index:
        save_gear(edited_gear.loc[i])

    st.success("Saved Gear!")
    st.rerun()

# ================= ANALYSIS =================
st.subheader("📊 Phân tích Gear")

gear_numeric = edited_gear.drop(columns=["id", "character"]).fillna(0)
avg = gear_numeric.mean()

weak_chars = []
for i, row in gear_numeric.iterrows():
    if (row < avg*0.8).sum() > 5:
        weak_chars.append(edited_gear.loc[i, "character"])

if weak_chars:
    st.warning(f"⚠️ Gear yếu: {', '.join(weak_chars)}")

# ================= RANK =================
st.subheader("🏆 Ranking")

edited_gear["score"] = gear_numeric.sum() + gear_numeric["dps"]
rank = edited_gear.sort_values("score", ascending=False)

st.dataframe(rank[["character", "score", "dps"]], use_container_width=True)
