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

    # FIX: giữ thứ tự DB
    df = df.sort_values("id").reset_index(drop=True)

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

# ================= AUTO NIGHTMARE (FIX DB) =================
def auto_nightmare(df):
    today = datetime.now(UTC7).date()
    now = datetime.now(UTC7)

    res = supabase.table("system_state").select("*").eq("key", "nightmare_date").execute()
    last_date = None

    if res.data:
        last_date = res.data[0]["value"]

    if now.hour >= 3 and str(today) != str(last_date):

        df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)

        for i in df.index:
            save_row(df.loc[i])

        supabase.table("system_state").upsert({
            "key": "nightmare_date",
            "value": str(today)
        }).execute()

        st.success("⚔️ Đã tự động +2 Nightmare hôm nay")

    return df

# ================= GEAR CONFIG =================
GEAR_COLUMNS = [
    "luc_chien","dps","vu_khi","khien","non","vai","giap","quan",
    "ao_choang","giay","bong_tai_1","bong_tai_2",
    "day_chuyen","nhan_1","nhan_2","vong_tay_1","vong_tay_2"
]

GEAR_LABEL = {
    "luc_chien":"Lực chiến","dps":"Dps","vu_khi":"Vũ khí","khien":"Khiên",
    "non":"Nón","vai":"Vai","giap":"Giáp","quan":"Quần",
    "ao_choang":"Áo choàng","giay":"Giầy","bong_tai_1":"Bông tai 1",
    "bong_tai_2":"Bông tai 2","day_chuyen":"Dây chuyền",
    "nhan_1":"Nhẫn 1","nhan_2":"Nhẵn 2",
    "vong_tay_1":"Vòng tay 1","vong_tay_2":"Vòng tay 2"
}

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
        val = data.get(col)
        payload[col] = int(val) if val not in [None, ""] else None

    supabase.table("gear_tracker").upsert(payload).execute()

def calc_gear_score(row):
    return sum([row[c] for c in GEAR_COLUMNS[2:] if pd.notna(row.get(c))])

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

# ================= APP =================
st.set_page_config(page_title="Energy Tracker PRO", layout="wide")
st.title("⚡ Energy Tracker PRO")

st.session_state.df = update_energy(st.session_state.df)
st.session_state.df = auto_nightmare(st.session_state.df)

# ================= TABLE =================
st.subheader("📊 Energy")
st.dataframe(st.session_state.df, use_container_width=True)

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
        gear_data[col] = st.number_input(
            GEAR_LABEL[col],
            value=int(val) if pd.notna(val) else 0,
            key=f"{character_name}_{col}"
        )

if st.button("💾 Save Gear"):
    save_gear(character_name, gear_data)
    st.rerun()

# ================= GEAR TABLE =================
st.subheader("📊 Gear Table")

if not gear_df.empty:
    gear_df["gear_score"] = gear_df.apply(calc_gear_score, axis=1)

    # rename column hiển thị
    display_df = gear_df.rename(columns=GEAR_LABEL)

    st.dataframe(display_df, use_container_width=True)

# ================= RANK =================
st.subheader("🏆 Ranking")

if not gear_df.empty:
    rank_df = gear_df.copy()
    rank_df["gear_score"] = rank_df.apply(calc_gear_score, axis=1)

    st.write("🔥 Lực chiến")
    st.dataframe(rank_df.sort_values("luc_chien", ascending=False)[["character","luc_chien"]])

    st.write("⚡ DPS")
    st.dataframe(rank_df.sort_values("dps", ascending=False)[["character","dps"]])

    st.write("🛡️ Gear Core")
    st.dataframe(rank_df.sort_values("gear_score", ascending=False)[["character","gear_score"]])
