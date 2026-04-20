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
        "last_nm_update":[pd.Timestamp.now(tz=UTC7)]*8,
        "power":[0]*8,
        "dps":[0]*8
    }

    for k,_ in gear_slots:
        data[f"{k}_level"]=[0]*8

    return pd.DataFrame(data)

# ================= LOAD =================
def load_data():
    try:
        df = pd.read_csv(FILE_PATH)
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
        df["last_nm_update"] = pd.to_datetime(df["last_nm_update"], errors="coerce")
    except:
        df = init_data()

    # đảm bảo cột tồn tại
    for col in ["power","dps","last_nm_update"]:
        if col not in df.columns:
            df[col]=0

    for k,_ in gear_slots:
        if f"{k}_level" not in df.columns:
            df[f"{k}_level"]=0

    return df.fillna(0)

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
            df.loc[i,"last_update"]=now_block
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        diff_hours = int((now_block-last).total_seconds()//3600)
        blocks = diff_hours//3

        if blocks>0:
            df.loc[i,"energy"]=min(df.loc[i,"energy"]+blocks*15,MAX_ENERGY)
            df.loc[i,"last_update"]=last+pd.Timedelta(hours=blocks*3)

    return df

# ================= NIGHTMARE AUTO =================
def update_nightmare_daily(df):
    now = pd.Timestamp.now(tz=UTC7).normalize()  # 00:00 hôm nay

    for i in df.index:
        last = pd.to_datetime(df.loc[i,"last_nm_update"], errors="coerce")

        if pd.isna(last):
            df.loc[i,"last_nm_update"] = now
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        days = (now - last.normalize()).days

        if days > 0:
            df.loc[i,"nightmare"] = min(df.loc[i,"nightmare"] + days*2, MAX_NIGHTMARE)
            df.loc[i,"last_nm_update"] = now

    return df

# ================= SCORE =================
def calc_gear_score(df):
    df["gear_score"] = [
        sum(df.loc[i,f"{k}_level"] for k,_ in gear_slots)
        for i in df.index
    ]
    return df

# ================= UI =================
st.set_page_config(layout="wide")
st.title("⚡ Energy Tracker PRO")

df = load_data()
df = update_energy(df)
df = update_nightmare_daily(df)
df = calc_gear_score(df)
save_data(df)

# ================= TABLE =================
st.subheader("📊 Energy")

main_cols = ["character","nightmare","trial","energy"]

# highlight bằng emoji (không crash)
display_df = df[main_cols].copy()

def mark(val, max_val):
    if val >= max_val:
        return f"🔴 {val}"
    elif val >= max_val*0.8:
        return f"🟡 {val}"
    return f"{val}"

display_df["energy"] = display_df["energy"].apply(lambda x: mark(x, MAX_ENERGY))
display_df["nightmare"] = display_df["nightmare"].apply(lambda x: mark(x, MAX_NIGHTMARE))

st.dataframe(display_df, use_container_width=True)

# ================= SELECT =================
idx = st.selectbox("Chọn nhân vật", df.index, format_func=lambda x: df.loc[x,"character"])

# ================= UPDATE =================
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
        df.loc[idx,"energy"]=energy_val
        df.loc[idx,"last_update"]=get_block_time(pd.Timestamp.now(tz=UTC7))
    if use_nightmare:
        df.loc[idx,"nightmare"]=nightmare_val
    if use_trial:
        df.loc[idx,"trial"]=trial_val

    save_data(df)
    st.rerun()

# ================= GEAR =================
st.subheader("🛡️ Gear + Stats")

power = st.number_input("Power",0,1000000,int(df.loc[idx,"power"]))
dps = st.number_input("DPS",0,1000000,int(df.loc[idx,"dps"]))

gear_input={}
for k,label in gear_slots:
    lv=st.number_input(label,0,9999,int(df.loc[idx,f"{k}_level"]))
    gear_input[k]=lv

if st.button("💾 Save Gear"):
    for k,lv in gear_input.items():
        df.loc[idx,f"{k}_level"]=lv

    df.loc[idx,"power"]=power
    df.loc[idx,"dps"]=dps

    save_data(df)
    st.rerun()

# ================= TABLE FULL =================
st.subheader("📊 Stats + Gear")

rows=[]
for i in df.index:
    row={
        "character":df.loc[i,"character"],
        "Power":df.loc[i,"power"],
        "DPS":df.loc[i,"dps"],
        "GearScore":df.loc[i,"gear_score"]
    }

    for k,label in gear_slots:
        lv=df.loc[i,f"{k}_level"]

        if lv==0:
            row[label]="❌"
        elif lv<5:
            row[label]=f"{lv} ⚠️"
        else:
            row[label]=lv

    rows.append(row)

st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ================= RANK =================
st.subheader("🏆 Ranking")

rank_df = df[["character","power","dps","gear_score"]].sort_values(
    ["power","dps","gear_score"], ascending=False
)

st.dataframe(rank_df, use_container_width=True)

# ================= SUGGEST =================
st.subheader("🧠 Gợi ý nâng cấp")

for k,label in gear_slots:
    lv=df.loc[idx,f"{k}_level"]

    if lv==0:
        st.write(f"❌ Thiếu {label}")
    elif lv<5:
        st.write(f"⚠️ {label} yếu (Lv {lv})")
