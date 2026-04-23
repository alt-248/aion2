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
    st.error("❌ Thiếu cấu hình GitHub")
    st.stop()

gear_slots = [
    "weapon","shield","shoulder","gloves","armor","pants",
    "cloak","boots","earring1","earring2",
    "necklace","ring1","ring2","bracelet1","bracelet2"
]

# ===== BUILD =====
build_suggest = {
    "Cleric": "Hồi máu + HP + Block",
    "Chanter": "Buff + Tốc độ + Hybrid",
    "Templar": "Tank + HP + DEF",
    "Gladiator": "Crit + ATK",
    "Ranger": "Crit + Speed",
    "Sorcerer": "Magic ATK + Crit",
    "Assassin": "Crit + Speed + Burst",
    "Elementalist": "Magic DPS + AoE"
}

# ===== INIT =====
def init_data():
    chars = list(build_suggest.keys())
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
def get_sha():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.get(url, headers=headers)
    return r.json().get("sha") if r.status_code == 200 else None

def save(df):
    df2 = df.copy()
    df2["last_update"] = df2["last_update"].astype(str)
    df2["last_nm_update"] = df2["last_nm_update"].astype(str)

    content = base64.b64encode(df2.to_csv(index=False).encode()).decode()
    data = {"message":"update","content":content}

    sha = get_sha()
    if sha:
        data["sha"] = sha

    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    r = requests.put(url, json=data, headers=headers)

    return r.status_code in [200,201]

# ===== LOAD =====
@st.cache_data(ttl=5)
def load():
    url = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"
    try:
        df = pd.read_csv(url)
    except:
        df = init_data()
        save(df)
        return df

    for g in gear_slots:
        if f"{g}_level" not in df:
            df[f"{g}_level"] = 0

    df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    df["last_nm_update"] = pd.to_datetime(df["last_nm_update"], errors="coerce")

    now = datetime.now()
    df["last_update"] = df["last_update"].fillna(now)
    df["last_nm_update"] = df["last_nm_update"].fillna(now)

    return df

# ===== LOGIC =====
def get_block_time(dt):
    return dt.replace(hour=(dt.hour//3)*3, minute=0, second=0, microsecond=0)

def update_energy(df):
    now = get_block_time(datetime.now())

    for i in df.index:
        last = df.loc[i,"last_update"]
        diff = int((now-last).total_seconds()//3600)//3

        if diff > 0:
            df.at[i,"energy"] = min(df.loc[i,"energy"]+diff*15, MAX_ENERGY)
            df.at[i,"last_update"] = last + timedelta(hours=diff*3)

    return df

def update_nm(df):
    now = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)

    for i in df.index:
        last = df.loc[i,"last_nm_update"]
        days = (now-last.replace(hour=0,minute=0,second=0,microsecond=0)).days

        if days > 0:
            df.at[i,"nightmare"] = min(df.loc[i,"nightmare"]+days*2, MAX_NIGHTMARE)
            df.at[i,"last_nm_update"] = now

    return df

def calc_score(df):
    df["gear_score"] = df[[f"{g}_level" for g in gear_slots]].sum(axis=1)
    return df

# ===== UI =====
st.title("⚡ Quản Lý Energy PRO")

df = load()
df = update_energy(df)
df = update_nm(df)
df = calc_score(df)

# ===== ALERT GỘP =====
full_energy = []
warn_energy = []
full_nm = []

for i in df.index:
    char = df.loc[i,"character"]
    e = df.loc[i,"energy"]
    nm = df.loc[i,"nightmare"]

    if e >= MAX_ENERGY:
        full_energy.append(char)
    elif e >= MAX_ENERGY*0.8:
        warn_energy.append(char)

    if nm >= MAX_NIGHTMARE:
        full_nm.append(char)

if full_energy:
    st.error("🔴 Full Energy: " + ", ".join(full_energy))

if warn_energy:
    st.warning("🟡 Sắp Full Energy: " + ", ".join(warn_energy))

if full_nm:
    st.error("👻 Full Nightmare: " + ", ".join(full_nm))

# ===== TABLE =====
st.subheader("📊 Bảng Energy")
st.dataframe(df[["character","energy","nightmare","trial"]])

# ===== SELECT =====
idx = st.selectbox("Chọn nhân vật", df.index, format_func=lambda x: df.loc[x,"character"])

# ===== UPDATE =====
st.subheader("Cập nhật")

col1,col2,col3 = st.columns(3)

use_energy = col1.checkbox("Energy")
use_nm = col2.checkbox("Nightmare")
use_trial = col3.checkbox("Trial")

if use_energy:
    val_energy = st.number_input("Energy",0,MAX_ENERGY,int(df.loc[idx,"energy"]))
if use_nm:
    val_nm = st.number_input("Nightmare",0,MAX_NIGHTMARE,int(df.loc[idx,"nightmare"]))
if use_trial:
    val_trial = st.number_input("Trial",0,10,int(df.loc[idx,"trial"]))

if st.button("💾 Lưu cập nhật"):
    if use_energy:
        df.loc[idx,"energy"] = val_energy
        df.loc[idx,"last_update"] = get_block_time(datetime.now())
    if use_nm:
        df.loc[idx,"nightmare"] = val_nm
    if use_trial:
        df.loc[idx,"trial"] = val_trial

    if save(df):
        st.success("Đã lưu!")
        st.cache_data.clear()
        st.rerun()

# ===== GEAR TABLE =====
st.subheader("🛡 Bảng Trang Bị")
gear_df = df[["character","power","dps"] + [f"{g}_level" for g in gear_slots]]
st.dataframe(gear_df)

# ===== EDIT GEAR =====
st.subheader("⚙️ Chỉnh Trang Bị")

power = st.number_input("Lực chiến",0,999999,int(df.loc[idx,"power"]))
dps = st.number_input("DPS",0,999999,int(df.loc[idx,"dps"]))

gear_inputs = {}
for g in gear_slots:
    gear_inputs[g] = st.number_input(g,0,9999,int(df.loc[idx,f"{g}_level"]))

if st.button("💾 Lưu Trang Bị"):
    for g,v in gear_inputs.items():
        df.loc[idx,f"{g}_level"] = v

    df.loc[idx,"power"] = power
    df.loc[idx,"dps"] = dps

    if save(df):
        st.success("Đã lưu gear!")
        st.cache_data.clear()
        st.rerun()

# ===== BUILD =====
st.subheader("🧠 Gợi ý build")
char = df.loc[idx,"character"]
st.info(f"{char}: {build_suggest.get(char,'')}")

# ===== RANK =====
st.subheader("🏆 Xếp hạng")
rank = df.sort_values(["power","dps","gear_score"],ascending=False)
st.dataframe(rank[["character","power","dps","gear_score"]])
