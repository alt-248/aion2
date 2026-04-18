import streamlit as st
import pandas as pd
from datetime import timezone, timedelta

# ================= CONFIG =================
FILE_PATH = "data_character.csv"
MAX_ENERGY = 840
UTC7 = timezone(timedelta(hours=7))

# ================= INIT DATA =================
def init_data():
    return pd.DataFrame({
        "character": [
            "Cleric", "Chanter", "Templar", "Gladiator",
            "Ranger", "Sorcerer", "Assassin", "Elementalist"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [pd.Timestamp.now(tz=UTC7)]*8
    })

# ================= LOAD / SAVE =================
def load_data():
    try:
        df = pd.read_csv(FILE_PATH)
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    except:
        df = init_data()
    return df

def save_data(df):
    df.to_csv(FILE_PATH, index=False)

# ================= TIME BLOCK =================
def get_block_time(dt):
    if dt.tzinfo is None:
        dt = dt.tz_localize(UTC7)
    else:
        dt = dt.tz_convert(UTC7)

    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY AUTO UPDATE =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = pd.to_datetime(df.loc[i, "last_update"], errors="coerce")

        if pd.isna(last):
            df.loc[i, "last_update"] = now_block
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        diff_hours = int((now_block - last).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last + pd.Timedelta(hours=blocks * 3)

    return df

# ================= UI =================
st.set_page_config(page_title="Energy Tracker", layout="wide")
st.title("⚡ Energy Tracker (UTC+7)")

df = load_data()
df = update_energy(df)
save_data(df)

# ================= TABLE =================
st.subheader("📊 Bảng dữ liệu")
st.dataframe(df, use_container_width=True)

# ================= SELECT CHARACTER =================
st.subheader("🎮 Chọn nhân vật")

idx = st.selectbox(
    "Character",
    df.index,
    format_func=lambda x: df.loc[x, "character"]
)

# ================= ACTION TO ALL =================
st.subheader("🔧 Hành động toàn bộ")

c1, c2 = st.columns(2)

with c1:
    if st.button("🔁 Reset Trial = 3 (All)"):
        df["trial"] = 3
        save_data(df)
        st.success("Đã reset trial!")

with c2:
    if st.button("⚔️ +2 Nightmare (All)"):
        df["nightmare"] = (df["nightmare"] + 2).clip(upper=14)
        save_data(df)
        st.success("Đã cộng nightmare!")

# ================= INPUT SECTION =================
st.subheader("🎯 Nhập dữ liệu theo nhân vật")

energy_val = st.number_input("Energy", 0, MAX_ENERGY, 0)
nightmare_val = st.number_input("Nightmare", 0, 14, 0)
trial_val = st.number_input("Trial", 0, 10, 0)

if st.button("💾 Lưu cho nhân vật"):
    now = pd.Timestamp.now(tz=UTC7)
    block_time = get_block_time(now)

    df.loc[idx, "energy"] = min(energy_val, MAX_ENERGY)
    df.loc[idx, "nightmare"] = min(nightmare_val, 14)
    df.loc[idx, "trial"] = trial_val
    df.loc[idx, "last_update"] = block_time

    save_data(df)
    st.success("Đã lưu dữ liệu!")
    st.rerun()

# ================= MANUAL ENERGY UPDATE =================
st.subheader("⚡ Energy System")

if st.button("Update Energy Now"):
    df = update_energy(df)
    save_data(df)
    st.success("Đã update energy!")
    st.rerun()
