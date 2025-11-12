import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
import pytz
import base64
import requests
from io import StringIO
import uuid
import plotly.express as px

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Task Tracker", page_icon="Timer", layout="wide")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TASKS_FILE = DATA_DIR / "tasks.csv"
EMPLOYEES_FILE = DATA_DIR / "employees.csv"
TASKLIST_FILE = DATA_DIR / "Tasklist.csv"
TIMEZONE = pytz.timezone('America/New_York')

# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASKLIST_COLUMNS = ["task_type_id", "task_name", "category"]
TASK_COLUMNS = [
    "task_id", "date", "employee_id", "employee_name", "task_type_id",
    "task_name", "task_category", "customer", "task_description",
    "start_time", "end_time", "duration_minutes", "cost",
]

# -------------------------------
# GITHUB CONFIG
# -------------------------------
def _github_cfg():
    cfg = st.secrets.get("github", {})
    return {
        "token": cfg.get("token"),
        "repo": cfg.get("repo"),
        "branch": cfg.get("branch", "main"),
        "task_file": cfg.get("file_path", "Data/tasks.csv"),
        "emp_file": cfg.get("employee_file_path", "Data/employees.csv"),
        "tasklist_file": cfg.get("tasklist_file_path", "Data/Tasklist.csv"),
    }

# -------------------------------
# LOAD FROM GITHUB (FORCE FRESH)
# -------------------------------
def _load_from_github(file_path: str, columns: list) -> pd.DataFrame:
    try:
        cfg = _github_cfg()
        url = f"https://api.github.com/repos/{cfg['repo']}/contents/{file_path}?ref={cfg['branch']}"
        headers = {"Authorization": f"token {cfg['token']}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            df = pd.read_csv(StringIO(content))
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            df = df.reindex(columns=columns)
            return df.copy()
        elif r.status_code == 404:
            return pd.DataFrame(columns=columns)
        else:
            st.error(f"GitHub error: {r.json().get('message')}")
            return pd.DataFrame(columns=columns)
    except Exception as e:
        st.error(f"Load failed: {e}")
        return pd.DataFrame(columns=columns)

# -------------------------------
# CACHED DATA – FROM GITHUB ONLY
# -------------------------------
@st.cache_data(ttl=30, show_spinner="Loading from GitHub...")
def get_employees():
    return _load_from_github(_github_cfg()["emp_file"], EMPLOYEE_COLUMNS)

@st.cache_data(ttl=30, show_spinner="Loading tasks...")
def get_tasklist():
    df = _load_from_github(_github_cfg()["tasklist_file"], TASKLIST_COLUMNS)
    if df.empty:
        defaults = [
            {"task_type_id":"TT_SALES_1","task_name":"Sales – First Contact Reply","category":"Sales"},
            {"task_type_id":"TT_SALES_2","task_name":"Sales – Schedule Site Survey","category":"Sales"},
            {"task_type_id":"TT_OPS_1","task_name":"Construction – Pull Fiber","category":"Construction"},
        ]
        df = pd.DataFrame(defaults)
        write_tasklist_to_github(df)
    return df

@st.cache_data(ttl=30, show_spinner="Loading tasks...")
def get_tasks():
    df = _load_from_github(_github_cfg()["task_file"], TASK_COLUMNS)
    # FORCE NUMERIC TYPES
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(0)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def clear_cache():
    st.cache_data.clear()

# -------------------------------
# WRITE TO GITHUB
# -------------------------------
def _github_safe_put(df: pd.DataFrame, file_path: str, key_col: str, msg: str, columns: list):
    try:
        cfg = _github_cfg()
        token, repo, branch = cfg["token"], cfg["repo"], cfg["branch"]
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"

        r = requests.get(url, headers=headers)
        if r.status_code == 404:
            payload = {
                "message": msg,
                "content": base64.b64encode(df.to_csv(index=False).encode()).decode(),
                "branch": branch,
            }
            put = requests.put(url, headers=headers, json=payload)
            return put.status_code in (200, 201)

        sha = r.json()["sha"]
        payload = {
            "message": msg,
            "content": base64.b64encode(df.to_csv(index=False).encode()).decode(),
            "branch": branch,
            "sha": sha,
        }
        put = requests.put(url, headers=headers, json=payload)
        return put.status_code in (200, 201)
    except:
        return False

def write_task_to_github(task: dict):
    df = get_tasks()
    if task["task_id"] in df["task_id"].values:
        st.error("Task ID exists!")
        return
    df = pd.concat([df, pd.DataFrame([task])], ignore_index=True)
    _github_safe_put(df, _github_cfg()["task_file"], "task_id", f"Add {task['task_id']}", TASK_COLUMNS)
    clear_cache()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("Task Tracker")
if st.sidebar.button("Force Refresh All Data", type="secondary"):
    clear_cache()
    st.rerun()

page = st.sidebar.radio("Go to", ["1. Task List", "2. Employee Tasks", "3. Admin"], index=1)

# -------------------------------
# PAGE 2 – EMPLOYEE TASKS
# -------------------------------
if page == "2. Employee Tasks":
    st.title("Employee Tasks")
    emps = get_employees()
    tasklist = get_tasklist()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state.active_task_id = None

    if emps.empty or tasklist.empty:
        st.warning("Add employees/tasks in Admin")
    else:
        with st.form("start_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                emp_name = st.selectbox("Employee", emps["name"])
                task_name = st.selectbox("Task", tasklist["task_name"])
            with c2:
                cust = st.text_input("Customer")
            if st.form_submit_button("Start Task", disabled=st.session_state.active_task_id is not None):
                emp = emps[emps["name"] == emp_name].iloc[0]
                typ = tasklist[tasklist["task_name"] == task_name].iloc[0]
                now = datetime.now(TIMEZONE)
                tid = f"T{str(uuid.uuid4())[:8]}"
                new = {
                    "task_id": tid, "date": now.date().isoformat(),
                    "employee_id": emp["employee_id"], "employee_name": emp["name"],
                    "task_type_id": typ["task_type_id"], "task_name": typ["task_name"],
                    "task_category": typ["category"], "customer": cust,
                    "task_description": "", "start_time": now.isoformat(),
                    "end_time": None, "duration_minutes": None, "cost": None,
                }
                write_task_to_github(new)
                st.session_state.active_task_id = tid
                st.success("Started!")
                st.rerun()

        if st.session_state.active_task_id:
            active = tasks[tasks["task_id"] == st.session_state.active_task_id].iloc[0]
            start = datetime.fromisoformat(active["start_time"]).astimezone(TIMEZONE)
            elapsed = datetime.now(TIMEZONE) - start
            st.write(f"**{active['employee_name']}** – {active['task_name']} | Elapsed: {str(elapsed).split('.')[0]}")
            if st.button("Finish Task"):
                end = datetime.now(TIMEZONE)
                mins = (end - start).total_seconds() / 60
                rate = float(emps[emps["employee_id"] == active["employee_id"]].iloc[0]["hourly_rate"])
                cost = round((mins / 60) * rate, 2)
                df = get_tasks()
                df.loc[df["task_id"] == st.session_state.active_task_id, ["end_time", "duration_minutes", "cost"]] = [end.isoformat(), mins, cost]
                _github_safe_put(df, _github_cfg()["task_file"], "task_id", "Finish task", TASK_COLUMNS)
                st.session_state.active_task_id = None
                st.success("Finished!")
                clear_cache()
                st.rerun()

        st.subheader("Task Log")
        if tasks.empty:
            st.info("No tasks yet.")
        else:
            disp = tasks.copy()
            disp["status"] = disp["end_time"].apply(lambda x: "Completed" if pd.notna(x) else "Active")
            disp["date"] = disp["date"].dt.date
            st.data_editor(
                disp[["task_id", "date", "employee_name", "customer", "task_name", "status", "duration_minutes", "cost"]],
                column_config={
                    "task_id": st.column_config.TextColumn("ID", disabled=True),
                    "date": st.column_config.DateColumn("Date", disabled=True),
                    "customer": st.column_config.TextColumn("Customer"),
                    "duration_minutes": st.column_config.NumberColumn("Mins", format="%.1f"),
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                },
                hide_index=True,
                use_container_width=True
            )

# -------------------------------
# PAGE 3 – ADMIN → REPORTS
# -------------------------------
elif page == "3. Admin":
    st.title("Admin")
    if not st.secrets.get("admin_users"):
        st.error("Add [admin_users] to secrets.toml")
    else:
        if "auth" not in st.session_state:
            st.session_state.auth = False
        if not st.session_state.auth:
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    if u in st.secrets.admin_users and p == st.secrets.admin_users[u]:
                        st.session_state.auth = True
                        st.rerun()
        else:
            if st.button("Logout"): st.session_state.auth = False; st.rerun()
            st.success("Admin Mode")

            section = st.radio("Section", ["Reports"], key="sec")

            if section == "Reports":
                st.header("Reports")
                tasks = get_tasks()
                if tasks.empty:
                    st.info("No tasks in GitHub.")
                else:
                    # DATE FILTER
                    col1, col2 = st.columns(2)
                    with col1:
                        start_date = st.date_input("Start", value=tasks["date"].min().date())
                    with col2:
                        end_date = st.date_input("End", value=tasks["date"].max().date())
                    df = tasks[(tasks["date"].dt.date >= start_date) & (tasks["date"].dt.date <= end_date)]

                    # TODAY
                    today = datetime.now(TIMEZONE).date()
                    today_df = df[pd.to_datetime(df["date"]).dt.date == today]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Hours", f"{today_df['duration_minutes'].sum()/60:.1f}")
                    c2.metric("Cost", f"${today_df['cost'].sum():,.2f}")
                    c3.metric("Tasks", len(today_df))

                    st.markdown("---")

                    # TASK CHART
                    task_sum = df.groupby("task_name").agg(
                        hours=("duration_minutes", lambda x: x.sum()/60),
                        cost=("cost", "sum")
                    ).reset_index()
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.bar(task_sum, x="task_name", y="hours", title="Hours by Task")
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        fig = px.pie(task_sum, values="cost", names="task_name", title="Cost by Task")
                        st.plotly_chart(fig, use_container_width=True)

                    # CUSTOMER CHART
                    cust_sum = df[df["customer"].notna()].groupby("customer").agg(
                        hours=("duration_minutes", lambda x: x.sum()/60),
                        cost=("cost", "sum")
                    ).reset_index()
                    if not cust_sum.empty:
                        col1, col2 = st.columns(2)
                        with col1:
                            fig = px.bar(cust_sum, x="customer", y="hours", title="Hours by Customer")
                            st.plotly_chart(fig, use_container_width=True)
                        with col2:
                            fig = px.pie(cust_sum, values="cost", names="customer", title="Revenue by Customer")
                            st.plotly_chart(fig, use_container_width=True)

                    # DOWNLOAD
                    st.download_button("Download All Tasks", df.to_csv(index=False), "tasks.csv", "text/csv")
