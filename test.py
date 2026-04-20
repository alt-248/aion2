import streamlit as st
import pandas as pd
from datetime import timezone, timedelta

# ================= CONFIG =================
FILE_PATH = "data_character.csv"
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

# ================= GEAR =================
gear_slots = [
    ("weapon","Vũ khí"),("shield","Khiên"),("shoulder","Vai"),
    ("gloves","Tay"),("armor","Giáp"),("pants","Quần"),
    ("cloak","Áo choàng"),("boots","Giày"),
    ("earring1","Bông tai 1"),("earring2","Bông tai 2"),
    ("necklace","Dây chuyền"),
    ("ring1","Nhẫn 1"),("ring2","Nhẫn 2"),
    ("bracelet1","Vòng tay 1"),("bracelet2","Vòng tay 2")
]

# ================= INIT =================
def init_data():
    data = {
        "character": [
            "Cleric","Chanter","Templar","Gladiator",
            "Ranger","Sorcerer","Assassin","Elementalist"
        ],
        "nightmare":[0]*8,
        "trial":[0]*8,
        "energy":[0]*8,
        "last_update":[pd.Timestamp.now(tz=UTC7)]*8,
        "power":[0]*8,
        "dps":[0]*8
    }

    for k,_ in gear_slots:
        data[f"{k}_name"]=[""]*8
        data[f"{k}_level"]=[0]*8

    return pd.DataFrame(data)

# ================= LOAD =================
def load_data():
    try:
        df = pd.read_csv(FILE_PATH)
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    except:
        df = init_data()

    # FIX thiếu cột
    for col in ["power","dps"]:
        if col not in df.columns:
            df[col] = 0

    for k,_ in gear_slots:
        if f"{k}_name" not in df.columns:
            df[f"{k}_name"] = ""
        if f"{k}_level" not in df.columns:
            df[f"{k}_level"] = 0

    return df.fillna("")

def save_data(df):
    df.to_csv(FILE_PATH, index=False)

# ================= TIME =================
def get_block_time(dt):
    if dt.tzinfo is None:
        dt = dt.tz_localize(UTC7)
    else:
        dt = dt.tz_convert(UTC7)

    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = pd.to_datetime(df.loc[i,"last_update"], errors="coerce")

        if pd.isna(last):
            df.loc[i,"last_update"] = now_block
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        diff_hours = int((now_block-last).total_seconds()//3600)
        blocks = diff_hours//3

        if blocks > 0:
            df.loc[i,"energy"] = min(df.loc[i,"energy"]+blocks*15, MAX_ENERGY)
            df.loc[i,"last_update"] = last + pd.Timedelta(hours=blocks*3)

    return df

# ================= UI =================
st.set_page_config(layout="wide")
st.title("⚡ Tracker PRO")

df = load_data()
df = update_energy(df)
save_data(df)

# ===== MAIN TABLE =====
st.subheader("📊 Energy")

main_cols = ["character","nightmare","trial","energy"]
st.dataframe(df[main_cols], use_container_width=True)

# ===== WARNING =====
for i in df.index:
    if df.loc[i,"energy"] >= MAX_ENERGY:
        st.error(f"{df.loc[i,'character']} FULL ENERGY!")
    elif df.loc[i,"energy"] >= MAX_ENERGY*0.8:
        st.warning(f"{df.loc[i,'character']} gần full energy!")

# ===== SELECT =====
idx = st.selectbox("Chọn nhân vật", df.index, format_func=lambda x: df.loc[x,"character"])

# ===== UPDATE =====
st.subheader("✏️ Update")

c1,c2,c3 = st.columns(3)

with c1:
    use_energy = st.checkbox("Energy")
    energy_val = st.number_input("Energy",0,MAX_ENERGY,0)

with c2:
    use_nightmare = st.checkbox("Nightmare")
    nightmare_val = st.number_input("Nightmare",0,MAX_NIGHTMARE,0)

with c3:
    use_trial = st.checkbox("Trial")
    trial_val = st.number_input("Trial",0,10,0)

if st.button("💾 Update"):
    if use_energy:
        df.loc[idx,"energy"] = int(energy_val)
        df.loc[idx,"last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    if use_nightmare:
        df.loc[idx,"nightmare"] = int(nightmare_val)

    if use_trial:
        df.loc[idx,"trial"] = int(trial_val)

    save_data(df)
    st.rerun()

# ===== GLOBAL =====
if st.button("+2 Nightmare"):
    df["nightmare"] = (df["nightmare"]+2).clip(upper=MAX_NIGHTMARE)
    save_data(df)
    st.rerun()

if st.button("Reset Trial"):
    df["trial"] = 3
    save_data(df)
    st.rerun()

# ===== GEAR + STATS =====
st.subheader("⚔️ Stats + 🛡️ Gear")

col1,col2 = st.columns(2)

with col1:
    power_val = st.number_input("Power",0,100000,int(df.loc[idx,"power"]))

with col2:
    dps_val = st.number_input("DPS",0,1000000,int(df.loc[idx,"dps"]))

gear_input = {}

for k,label in gear_slots:
    c1,c2 = st.columns(2)

    with c1:
        name = st.text_input(label, str(df.loc[idx,f"{k}_name"]))

    with c2:
        lv = st.number_input(f"{label} Lv",0,20,int(df.loc[idx,f"{k}_level"]))

    gear_input[k] = (name, lv)

if st.button("💾 Save Gear"):
    for k,(n,lv) in gear_input.items():
        df.loc[idx,f"{k}_name"] = str(n)
        df.loc[idx,f"{k}_level"] = int(lv)

    df.loc[idx,"power"] = int(power_val)
    df.loc[idx,"dps"] = int(dps_val)

    save_data(df)
    st.rerun()

# ===== FULL TABLE =====
st.subheader("⚔️ + 🛡️ Tổng hợp")

rows=[]

for i in df.index:
    row={
        "character":df.loc[i,"character"],
        "Power":df.loc[i,"power"],
        "DPS":df.loc[i,"dps"]
    }

    for k,label in gear_slots:
        name=df.loc[i,f"{k}_name"]
        lv=df.loc[i,f"{k}_level"]

        row[label] = "❌" if name=="" or lv==0 else f"{name}(Lv{lv})"

    rows.append(row)

full_df = pd.DataFrame(rows).set_index("character")

st.dataframe(full_df, use_container_width=True)
