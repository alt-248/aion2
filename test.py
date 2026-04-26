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

# ================= GEAR LABEL =================
GEAR_LABELS = {
    "luc_chien":"Lực chiến","dps":"Dps","vu_khi":"Vũ khí","khien":"Khiên","non":"Nón",
    "vai":"Vai","giap":"Giáp","quan":"Quần","tay":"Tay","ao_choang":"Áo choàng",
    "giay":"Giầy","bong_tai_1":"Bông tai 1","bong_tai_2":"Bông tai 2",
    "day_chuyen":"Dây chuyền","nhan_1":"Nhẫn 1","nhan_2":"Nhẫn 2",
    "vong_tay_1":"Vòng tay 1","vong_tay_2":"Vòng tay 2"
}

GEAR_COLUMNS = list(GEAR_LABELS.keys())

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

# ================= FIX AUTO NIGHTMARE =================
def auto_nightmare(df):
    today = datetime.now(UTC7).date()

    for i in df.index:
        last_date = df.loc[i].get("last_nightmare_date")

        if pd.isna(last_date) or str(last_date) != str(today):
            if datetime.now(UTC7).hour >= 3:
                df.loc[i, "nightmare"] = min(df.loc[i, "nightmare"] + 2, MAX_NIGHTMARE)
                df.loc[i, "last_nightmare_date"] = str(today)

                supabase.table("energy_tracker1").update({
                    "nightmare": int(df.loc[i, "nightmare"]),
                    "last_nightmare_date": str(today)
                }).eq("id", int(df.loc[i, "id"])).execute()

    return df

# ================= GEAR =================
def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["character"] + GEAR_COLUMNS)
    return df

def save_gear(character, data):
    payload = {"character": character}
    for col in GEAR_COLUMNS:
        payload[col] = int(data[col]) if data[col] else None
    supabase.table("gear_tracker").upsert(payload).execute()

def calc_gear_score(row):
    return sum([row[c] for c in GEAR_COLUMNS[2:] if pd.notna(row.get(c))])

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

st.session_state.df = update_energy(st.session_state.df)
st.session_state.df = auto_nightmare(st.session_state.df)

# ================= UI =================
st.title("⚡ Energy Tracker PRO")

st.dataframe(st.session_state.df, use_container_width=True)

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

# ================= GEAR UI =================
st.subheader("🛡️ Gear")

gear_df = load_gear()
gear_row = gear_df[gear_df["character"] == character_name]

gear_data = {}
cols = st.columns(4)

for i, col in enumerate(GEAR_COLUMNS):
    val = gear_row.iloc[0][col] if not gear_row.empty else 0

    with cols[i % 4]:
        gear_data[col] = st.number_input(
            GEAR_LABELS[col],
            value=int(val) if pd.notna(val) else 0,
            key=f"{character_name}_{col}"
        )

if st.button("💾 Save Gear"):
    save_gear(character_name, gear_data)
    st.rerun()

# ================= RANKING =================
st.subheader("🏆 Ranking")

if not gear_df.empty:
    gear_df["gear_score"] = gear_df.apply(calc_gear_score, axis=1)

    rank_power = gear_df.sort_values("luc_chien", ascending=False)[["character","luc_chien"]]
    rank_dps = gear_df.sort_values("dps", ascending=False)[["character","dps"]]
    rank_gear = gear_df.sort_values("gear_score", ascending=False)[["character","gear_score"]]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("⚔️ Lực chiến")
        st.dataframe(rank_power)

    with col2:
        st.write("💥 DPS")
        st.dataframe(rank_dps)

    with col3:
        st.write("🛡️ Gear Score")
        st.dataframe(rank_gear)
