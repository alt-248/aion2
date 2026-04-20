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
    ("weapon", "Vũ khí"),
    ("shield", "Khiên"),
    ("shoulder", "Vai"),
    ("gloves", "Tay"),
    ("armor", "Giáp"),
    ("pants", "Quần"),
    ("cloak", "Áo choàng"),
    ("boots", "Giày"),
    ("earring1", "Bông tai 1"),
    ("earring2", "Bông tai 2"),
    ("necklace", "Dây chuyền"),
    ("ring1", "Nhẫn 1"),
    ("ring2", "Nhẫn 2"),
    ("bracelet1", "Vòng tay 1"),
    ("bracelet2", "Vòng tay 2"),
]

# ================= INIT =================
def init_data():
    data = {
        "character": [
            "Cleric","Chanter","Templar","Gladiator",
            "Ranger","Sorcerer","Assassin","Elementalist"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [pd.Timestamp.now(tz=UTC7)]*8,
        "power": [0]*8,
        "dps": [0]*8
    }

    for key, _ in gear_slots:
        data[f"{key}_name"] = [""]*8
        data[f"{key}_level"] = [0]*8

    return pd.DataFrame(data)

# ================= LOAD/SAVE =================
def load_data():
    try:
        df = pd.read_csv(FILE_PATH)
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    except:
        df = init_data()
    return df

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

# ================= GEAR SCORE =================
def calc_gear_score(df):
    df["gear_score"] = [
        sum(df.loc[i, f"{k}_level"] for k,_ in gear_slots)
        for i in df.index
    ]
    return df

# ================= SUGGEST =================
def suggest_upgrade(df, idx):
    out = []
    for k, label in gear_slots:
        name = df.loc[idx, f"{k}_name"]
        lv = df.loc[idx, f"{k}_level"]
        if name == "" or lv == 0:
            out.append(f"🔴 Thiếu {label}")
        elif lv < 5:
            out.append(f"🟡 {label} yếu (Lv {lv})")
    return out

# ================= COLOR =================
def highlight_status(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    for i in df.index:
        # energy
        if df.loc[i,"energy"] >= MAX_ENERGY:
            style.loc[i,"energy"] = "background-color:red;color:white"
        elif df.loc[i,"energy"] >= MAX_ENERGY*0.8:
            style.loc[i,"energy"] = "background-color:yellow"

        # nightmare
        if df.loc[i,"nightmare"] >= MAX_NIGHTMARE:
            style.loc[i,"nightmare"] = "background-color:red;color:white"
        elif df.loc[i,"nightmare"] >= MAX_NIGHTMARE*0.8:
            style.loc[i,"nightmare"] = "background-color:yellow"

    return style

def gear_color(name, lv):
    if name == "" or lv == 0:
        return "background-color:red;color:white"
    elif lv < 5:
        return "background-color:yellow"
    else:
        return "background-color:lightgreen"

# ================= UI =================
st.set_page_config(layout="wide")
st.title("⚡ Energy + Gear Tracker PRO")

df = load_data()
df = update_energy(df)
df = calc_gear_score(df)
save_data(df)

# ===== TABLE =====
st.subheader("📊 Data")
st.dataframe(df.style.apply(lambda x: highlight_status(df), axis=None), use_container_width=True)

# ===== TOP =====
top = df.sort_values("gear_score", ascending=False).iloc[0]
st.success(f"🏆 Mạnh nhất: {top['character']} ({top['gear_score']})")

# ===== SELECT =====
idx = st.selectbox("Chọn nhân vật", df.index, format_func=lambda x: df.loc[x,"character"])

# ===== METRIC =====
col1, col2, col3 = st.columns(3)
col1.metric("⭐ Gear Score", df.loc[idx,"gear_score"])
col2.metric("⚔️ Lực chiến", df.loc[idx,"power"])
col3.metric("🔥 DPS", df.loc[idx,"dps"])

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
        df.loc[idx,"energy"] = energy_val
        df.loc[idx,"last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))
    if use_nightmare:
        df.loc[idx,"nightmare"] = nightmare_val
    if use_trial:
        df.loc[idx,"trial"] = trial_val

    save_data(df)
    st.rerun()

# ===== GLOBAL =====
st.subheader("🔧 Global")
if st.button("Reset Trial"):
    df["trial"]=3
    save_data(df)
    st.rerun()

if st.button("+2 Nightmare"):
    df["nightmare"]=(df["nightmare"]+2).clip(upper=MAX_NIGHTMARE)
    save_data(df)
    st.rerun()

# ===== GEAR + STATS =====
st.subheader("🛡️ Gear + Stats")

col1,col2 = st.columns(2)
with col1:
    power_val = st.number_input("Lực chiến",0,100000,int(df.loc[idx,"power"]))
with col2:
    dps_val = st.number_input("DPS",0,1000000,int(df.loc[idx,"dps"]))

gear_input={}
for k,label in gear_slots:
    c1,c2=st.columns(2)
    with c1:
        name=st.text_input(label, df.loc[idx,f"{k}_name"])
    with c2:
        lv=st.number_input(f"{label} Lv",0,20,int(df.loc[idx,f"{k}_level"]))
    gear_input[k]=(name,lv)

if st.button("💾 Save Gear + Stats"):
    for k,(n,lv) in gear_input.items():
        df.loc[idx,f"{k}_name"]=n
        df.loc[idx,f"{k}_level"]=lv

    df.loc[idx,"power"]=power_val
    df.loc[idx,"dps"]=dps_val

    save_data(df)
    st.rerun()

# ===== GEAR VIEW =====
st.subheader("📦 Gear Status")

gear_view=[]
for k,label in gear_slots:
    gear_view.append({
        "Slot":label,
        "Tên":df.loc[idx,f"{k}_name"],
        "Level":df.loc[idx,f"{k}_level"]
    })

gear_df=pd.DataFrame(gear_view)

def gear_style(row):
    c=gear_color(row["Tên"],row["Level"])
    return [c,c,c]

st.dataframe(gear_df.style.apply(gear_style,axis=1),use_container_width=True)

# ===== CHART =====
st.subheader("📊 So sánh Gear Score")
st.bar_chart(df.set_index("character")["gear_score"])

# ===== SUGGEST =====
st.subheader("🧠 Gợi ý nâng cấp")

sug = suggest_upgrade(df,idx)
if sug:
    for s in sug:
        st.write(s)
else:
    st.success("Trang bị ổn 👍")
