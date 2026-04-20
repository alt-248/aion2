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
            "Cleric", "Chanter", "Templar", "Gladiator",
            "Ranger", "Sorcerer", "Assassin", "Elementalist"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [pd.Timestamp.now(tz=UTC7)]*8
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
    scores = []
    for i in df.index:
        total = 0
        for key, _ in gear_slots:
            total += df.loc[i, f"{key}_level"]
        scores.append(total)
    df["gear_score"] = scores
    return df

# ================= SUGGEST =================
def suggest_upgrade(df, idx):
    suggestions = []
    for key, label in gear_slots:
        name = df.loc[idx, f"{key}_name"]
        level = df.loc[idx, f"{key}_level"]

        if name == "" or level == 0:
            suggestions.append(f"🔴 Thiếu {label}")
        elif level < 5:
            suggestions.append(f"🟡 {label} yếu (Lv {level})")
    return suggestions

# ================= COLOR =================
def highlight_status(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    for i in df.index:
        if df.loc[i, "energy"] >= MAX_ENERGY:
            style.loc[i, "energy"] = "background-color:red;color:white"
        elif df.loc[i, "energy"] >= MAX_ENERGY * 0.8:
            style.loc[i, "energy"] = "background-color:yellow"

        if df.loc[i, "nightmare"] >= MAX_NIGHTMARE:
            style.loc[i, "nightmare"] = "background-color:red;color:white"
        elif df.loc[i, "nightmare"] >= MAX_NIGHTMARE * 0.8:
            style.loc[i, "nightmare"] = "background-color:yellow"

    return style

def gear_color(name, level):
    if name == "" or level == 0:
        return "background-color:red;color:white"
    elif level < 5:
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
idx = st.selectbox("Chọn nhân vật", df.index, format_func=lambda x: df.loc[x, "character"])

# ===== SCORE =====
st.metric("Gear Score", df.loc[idx, "gear_score"])

# ===== UPDATE =====
st.subheader("✏️ Update")

c1, c2, c3 = st.columns(3)

with c1:
    use_energy = st.checkbox("Energy")
    energy_val = st.number_input("Energy", 0, MAX_ENERGY, 0)

with c2:
    use_nightmare = st.checkbox("Nightmare")
    nightmare_val = st.number_input("Nightmare", 0, MAX_NIGHTMARE, 0)

with c3:
    use_trial = st.checkbox("Trial")
    trial_val = st.number_input("Trial", 0, 10, 0)

if st.button("💾 Update"):
    if use_energy:
        df.loc[idx, "energy"] = energy_val
        df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))

    if use_nightmare:
        df.loc[idx, "nightmare"] = nightmare_val

    if use_trial:
        df.loc[idx, "trial"] = trial_val

    save_data(df)
    st.rerun()

# ===== GLOBAL =====
st.subheader("🔧 Global")

if st.button("Reset Trial"):
    df["trial"] = 3
    save_data(df)
    st.rerun()

if st.button("+2 Nightmare"):
    df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
    save_data(df)
    st.rerun()

# ===== GEAR INPUT =====
st.subheader("🛡️ Gear")

gear_input = {}

for key, label in gear_slots:
    col1, col2 = st.columns(2)

    with col1:
        name = st.text_input(label, df.loc[idx, f"{key}_name"])

    with col2:
        level = st.number_input(f"{label} Lv", 0, 20, int(df.loc[idx, f"{key}_level"]))

    gear_input[key] = (name, level)

if st.button("💾 Save Gear"):
    for key, (name, level) in gear_input.items():
        df.loc[idx, f"{key}_name"] = name
        df.loc[idx, f"{key}_level"] = level

    save_data(df)
    st.rerun()

# ===== GEAR VIEW =====
st.subheader("📦 Gear Status")

gear_view = []
for key, label in gear_slots:
    gear_view.append({
        "Slot": label,
        "Tên": df.loc[idx, f"{key}_name"],
        "Level": df.loc[idx, f"{key}_level"]
    })

gear_df = pd.DataFrame(gear_view)

def gear_style(row):
    c = gear_color(row["Tên"], row["Level"])
    return [c, c, c]

st.dataframe(gear_df.style.apply(gear_style, axis=1), use_container_width=True)

# ===== CHART =====
st.subheader("📊 So sánh Gear Score")
chart_df = df[["character", "gear_score"]].set_index("character")
st.bar_chart(chart_df)

# ===== SUGGEST =====
st.subheader("🧠 Gợi ý nâng cấp")

suggestions = suggest_upgrade(df, idx)

if suggestions:
    for s in suggestions:
        st.write(s)
else:
    st.success("Trang bị ổn 👍")
