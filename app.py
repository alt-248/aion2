import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14

REPO = st.secrets.get("GITHUB_REPO", "")
TOKEN = st.secrets.get("GITHUB_TOKEN", "")
FILE_PATH = st.secrets.get("GITHUB_FILE", "data_character.csv")

if not REPO or not TOKEN:
    st.error("❌ Thiếu cấu hình GitHub")
    st.stop()

# ================= INIT =================
def init_data():
    now = datetime.now()
    return pd.DataFrame({
        "character": [
            "Cleric","Chanter","Templar","Gladiator",
            "Ranger","Sorcerer","Assassin","Elementalist"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [now]*8
    })

# ================= SAVE =================
def save_data(df):
    try:
        df2 = df.copy()
        df2["last_update"] = df2["last_update"].astype(str)

        content = base64.b64encode(df2.to_csv(index=False).encode()).decode()

        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        headers = {
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        res = requests.get(url, headers=headers)
        sha = res.json().get("sha") if res.status_code == 200 else None

        data = {
            "message": f"update {datetime.now()}",
            "content": content
        }

        if sha:
            data["sha"] = sha

        r = requests.put(url, json=data, headers=headers)

        if r.status_code not in [200, 201]:
            st.error("❌ Lỗi save: " + r.text)

    except Exception as e:
        st.error(f"❌ Exception: {e}")

# ================= LOAD =================
def load_data():
    url = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}?t={datetime.now().timestamp()}"

    try:
        df = pd.read_csv(url)
    except:
        df = init_data()
        save_data(df)
        return df

    # ép kiểu datetime (KHÔNG timezone)
    df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")

    now = datetime.now()
    df["last_update"] = df["last_update"].fillna(now)

    return df

# ================= TIME =================
def get_block_time(dt):
    return dt.replace(hour=(dt.hour//3)*3, minute=0, second=0, microsecond=0)

# ================= ENERGY =================
def update_energy(df):
    now_block = get_block_time(datetime.now())

    for i in df.index:
        last = df.loc[i, "last_update"]

        if pd.isna(last):
            df.at[i, "last_update"] = now_block
            continue

        diff = int((now_block - last).total_seconds() // 3600) // 3

        if diff > 0:
            df.at[i, "energy"] = min(df.loc[i, "energy"] + diff*15, MAX_ENERGY)
            df.at[i, "last_update"] = last + timedelta(hours=diff*3)

    return df

# ================= ALERT =================
def check_alert(df):
    full_energy = df[df["energy"] >= MAX_ENERGY]["character"].tolist()
    full_nm = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].tolist()

    warn_energy = df[
        (df["energy"] >= MAX_ENERGY*0.8) &
        (df["energy"] < MAX_ENERGY)
    ]["character"].tolist()

    return full_energy, warn_energy, full_nm

# ================= UI =================
st.set_page_config(layout="wide")
st.title("⚡ Energy Tracker PRO (Clean)")

df = load_data()
df = update_energy(df)
save_data(df)

# ===== ALERT =====
full_e, warn_e, full_nm = check_alert(df)

if full_e:
    st.error("🔥 Full Energy: " + ", ".join(full_e))

if warn_e:
    st.warning("⚠️ Sắp Full Energy: " + ", ".join(warn_e))

if full_nm:
    st.error("💀 Full Nightmare: " + ", ".join(full_nm))

# ===== TABLE =====
st.subheader("📊 Bảng dữ liệu")
st.dataframe(df, use_container_width=True)

# ===== SELECT =====
idx = st.selectbox("Chọn nhân vật", df.index,
                   format_func=lambda x: df.loc[x,"character"])

# ===== UPDATE =====
st.subheader("✏️ Cập nhật")

col1, col2, col3 = st.columns(3)

with col1:
    use_energy = st.checkbox("Energy")
    val_energy = st.number_input("Energy",0,MAX_ENERGY,
                                int(df.loc[idx,"energy"]),
                                disabled=not use_energy)

with col2:
    use_nm = st.checkbox("Nightmare")
    val_nm = st.number_input("Nightmare",0,MAX_NIGHTMARE,
                            int(df.loc[idx,"nightmare"]),
                            disabled=not use_nm)

with col3:
    use_trial = st.checkbox("Trial")
    val_trial = st.number_input("Trial",0,10,
                               int(df.loc[idx,"trial"]),
                               disabled=not use_trial)

if st.button("💾 Lưu"):
    if use_energy:
        df.loc[idx,"energy"] = val_energy
        df.loc[idx,"last_update"] = get_block_time(datetime.now())

    if use_nm:
        df.loc[idx,"nightmare"] = val_nm

    if use_trial:
        df.loc[idx,"trial"] = val_trial

    save_data(df)
    st.success("Đã lưu!")
    st.rerun()

# ===== GLOBAL =====
st.subheader("🔧 Toàn server")

c1, c2 = st.columns(2)

with c1:
    if st.button("Reset Trial = 3"):
        df["trial"] = 3
        save_data(df)
        st.success("Done!")
        st.rerun()

with c2:
    if st.button("+2 Nightmare"):
        df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
        save_data(df)
        st.success("Done!")
        st.rerun()

# ===== MANUAL =====
st.subheader("⚡ Energy Manual")

if st.button("Update Energy Now"):
    df = update_energy(df)
    save_data(df)
    st.success("Updated!")
    st.rerun()
