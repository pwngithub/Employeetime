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
# LOAD FROM GITHUB
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
# SAFE PUSH
# -------------------------------
def _github_safe_put(df: pd.DataFrame, file_path: str, msg: str, columns: list) -> bool:
    try:
        cfg = _github_cfg()
        token, repo, branch = cfg["token"], cfg["repo"], cfg["branch"]
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
        r = requests.get(url, headers=headers)
        payload = {
            "message": msg,
            "content": base64.b64encode(df.to_csv(index=False).encode()).decode(),
            "branch": branch,
        }
        if r.status_code == 200:
            payload["sha"] = r.json()["sha"]
        put = requests.put(url, headers=headers, json=payload)
        return put.status_code in (200, 201)
    except Exception as e:
        st.error(f"Push failed: {e}")
        return False

# -------------------------------
# CACHED DATA
# -------------------------------
@st.cache_data(ttl=5, show_spinner="Loading from GitHub...")
def get_employees():
    return _load_from_github(_github_cfg()["emp_file"], EMPLOYEE_COLUMNS)

@st.cache_data(ttl=5, show_spinner="Loading task list...")
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

@st.cache_data(ttl=5, show_spinner="Loading tasks...")
def get_tasks():
    df = _load_from_github(_github_cfg()["task_file"], TASK_COLUMNS)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(0)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def clear_cache():
    st.cache_data.clear()

# -------------------------------
# WRITE & DELETE
# -------------------------------
def write_task_to_github(task: dict):
    df = get_tasks()
    if task["task_id"] in df["task_id"].values:
        st.error("Task ID exists!")
        return False
    df = pd.concat([df, pd.DataFrame([task])], ignore_index=True)
    success = _github_safe_put(df, _github_cfg()["task_file"], f"Add {task['task_id']}", TASK_COLUMNS)
    if success:
        clear_cache()
    return success

def delete_tasks_from_github(task_ids: list):
    df = get_tasks()
    before = len(df)
    df = df[~df["task_id"].isin(task_ids)]
    if len(df) == before:
        st.warning("No tasks deleted.")
        return
    if _github_safe_put(df, _github_cfg()["task_file"], f"Delete {len(task_ids)} tasks", TASK_COLUMNS):
        clear_cache()
        st.success(f"Deleted {len(task_ids)} task(s)!")
        st.rerun()

def write_employees_to_github(df: pd.DataFrame):
    if _github_safe_put(df, _github_cfg()["emp_file"], "Update employees", EMPLOYEE_COLUMNS):
        clear_cache()
        st.rerun()

def write_tasklist_to_github(df: pd.DataFrame):
    if _github_safe_put(df, _github_cfg()["tasklist_file"], "Update tasklist", TASKLIST_COLUMNS):
        clear_cache()
        st.rerun()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("Task Tracker")
if st.sidebar.button("Force Refresh All Data", type="secondary"):
    clear_cache()
    st.rerun()

page = st.sidebar.radio("Go to", ["1. Task List", "2. Employee Tasks", "3. Admin"], index=1)

# -------------------------------
# PAGE 1 – TASK LIST
# -------------------------------
if page == "1. Task List":
    st.title("Task Library")
    tasklist = get_tasklist().copy()
    with st.form("add_task_type", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input("Task Name")
        with c2:
            category = st.text_input("Category")
        tid = st.text_input("Task ID (optional)").strip()
        if st.form_submit_button("Save"):
            if not task_name.strip():
                st.warning("Name required")
            else:
                if not tid:
                    tid = f"TT_{str(uuid.uuid4())[:8]}"
                new_row = {
                    "task_type_id": tid,
                    "task_name": task_name.strip(),
                    "category": category.strip() or "General"
                }
                tasklist = tasklist[tasklist["task_type_id"] != tid]
                tasklist = pd.concat([tasklist, pd.DataFrame([new_row])], ignore_index=True)
                write_tasklist_to_github(tasklist)
    st.dataframe(tasklist[["task_type_id", "task_name", "category"]], use_container_width=True)

# -------------------------------
# PAGE 2 – EMPLOYEE TASKS (MULTI-USER + DATE FIX)
# -------------------------------
elif page == "2. Employee Tasks":
    st.title("Employee Tasks")
    emps = get_employees()
    tasklist = get_tasklist()
    tasks = get_tasks()

    if "active_tasks" not in st.session_state:
        st.session_state.active_tasks = []

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

            emp_tasks = tasks[tasks["employee_name"] == emp_name]
            has_active = emp_tasks[emp_tasks["end_time"].isna()].any().any() if not emp_tasks.empty else False

            if st.form_submit_button("Start Task", disabled=has_active):
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
                if write_task_to_github(new):
                    if tid not in st.session_state.active_tasks:
                        st.session_state.active_tasks.append(tid)
                    st.success(f"Task Started for {emp_name}!")
                    st.rerun()

        # ACTIVE TASKS
        active_df = tasks[tasks["task_id"].isin(st.session_state.active_tasks) & tasks["end_time"].isna()]
        if not active_df.empty:
            st.subheader("Active Tasks")
            for _, row in active_df.iterrows():
                start = datetime.fromisoformat(row["start_time"]).astimezone(TIMEZONE)
                elapsed = datetime.now(TIMEZONE) - start
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                st.markdown(
                    f"""
                    <div style="background-color:#e8f5e9;padding:16px;border-radius:10px;margin-bottom:10px;border-left:5px solid #4caf50;">
                        <p><b>{row['employee_name']}</b> → {row['task_name']}</p>
                        <p>Customer: <b>{row['customer'] or 'N/A'}</b> | Elapsed: <b>{hours:02d}:{minutes:02d}:{seconds:02d}</b></p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button(f"Finish##{row['task_id']}", key=f"finish_{row['task_id']}", type="primary"):
                        end = datetime.now(TIMEZONE)
                        mins = (end - start).total_seconds() / 60
                        rate = float(emps[emps["employee_id"] == row["employee_id"]].iloc[0]["hourly_rate"])
                        cost = round((mins / 60) * rate, 2)

                        df = get_tasks()
                        df.loc[df["task_id"] == row["task_id"], 
                               ["end_time", "duration_minutes", "cost"]] = [end.isoformat(), mins, cost]

                        if _github_safe_put(df, _github_cfg()["task_file"], f"Finish {row['task_id']}", TASK_COLUMNS):
                            st.session_state.active_tasks = [t for t in st.session_state.active_tasks if t != row["task_id"]]
                            clear_cache()
                            st.success(f"Task finished for {row['employee_name']}!")
                            st.rerun()
                with col2:
                    if st.button(f"Cancel##{row['task_id']}", key=f"cancel_{row['task_id']}", type="secondary"):
                        st.session_state.active_tasks = [t for t in st.session_state.active_tasks if t != row["task_id"]]
                        st.rerun()
        else:
            st.info("No active tasks.")

        # === TASK LOG (DATE FIXED) ===
        st.subheader("Task Log")
        if tasks.empty:
            st.info("No tasks yet.")
        else:
            disp = tasks.copy()
            disp["status"] = disp["end_time"].apply(lambda x: "Completed" if pd.notna(x) else "Active")
            disp["date_for_editor"] = disp["date"]
            disp["date"] = disp["date"].dt.date

            if "task_log_df" not in st.session_state:
                st.session_state.task_log_df = disp

            if st.session_state.task_log_df.shape[0] != tasks.shape[0]:
                st.session_state.task_log_df = disp

            edited = st.data_editor(
                st.session_state.task_log_df[[
                    "task_id", "date_for_editor", "employee_name", "customer",
                    "task_name", "status", "duration_minutes", "cost", "delete"
                ]].rename(columns={"date_for_editor": "date"}),
                column_config={
                    "task_id": st.column_config.TextColumn("ID", disabled=True),
                    "date": st.column_config.DateColumn("Date", disabled=True),
                    "customer": st.column_config.TextColumn("Customer"),
                    "duration_minutes": st.column_config.NumberColumn("Mins", format="%.1f"),
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                    "delete": st.column_config.CheckboxColumn("Delete?", default=False),
                },
                hide_index=True,
                use_container_width=True,
                key="task_log_editor"
            )

            st.session_state.task_log_df = edited

            if st.button("Delete Selected Tasks", type="primary"):
                to_delete = edited[edited["delete"] == True]["task_id"].tolist()
                if to_delete:
                    st.session_state.active_tasks = [t for t in st.session_state.active_tasks if t not in to_delete]
                    delete_tasks_from_github(to_delete)
                else:
                    st.info("No tasks selected.")

# -------------------------------
# PAGE 3 – ADMIN (unchanged)
# -------------------------------
elif page == "3. Admin":
    st.title("Admin")
    admin_users = st.secrets.get("admin_users")
    if not admin_users:
        st.error("Add [admin_users] to secrets.toml")
    else:
        if "auth" not in st.session_state:
            st.session_state.auth = False
        if not st.session_state.auth:
            with st.form("login"):
                u = st.text_input("User")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    if u in admin_users and p == admin_users[u]:
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error("Invalid")
        else:
            if st.button("Logout"): 
                st.session_state.auth = False
                st.rerun()
            st.success("Admin Mode")

            st.subheader("GitHub Sync")
            cfg = _github_cfg()
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Test Tasks CSV"):
                    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['task_file']}?ref={cfg['branch']}", headers={"Authorization": f"token {cfg['token']}"})
                    st.write("Exists" if r.status_code == 200 else "Not found" if r.status_code == 404 else "Error")
                if st.button("Sync Tasks CSV", type="primary"):
                    df = get_tasks()
                    if _github_safe_put(df, cfg["task_file"], "Manual sync tasks", TASK_COLUMNS):
                        st.success("Synced!")
                        clear_cache()
                        st.rerun()
            with c2:
                if st.button("Test Employees CSV"):
                    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['emp_file']}?ref={cfg['branch']}", headers={"Authorization": f"token {cfg['token']}"})
                    st.write("Exists" if r.status_code == 200 else "Not found" if r.status_code == 404 else "Error")
                if st.button("Sync Employees CSV", type="primary"):
                    df = get_employees()
                    if _github_safe_put(df, cfg["emp_file"], "Manual sync employees", EMPLOYEE_COLUMNS):
                        st.success("Synced!")
                        clear_cache()
                        st.rerun()
            with c3:
                if st.button("Test Tasklist CSV"):
                    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['tasklist_file']}?ref={cfg['branch']}", headers={"Authorization": f"token {cfg['token']}"})
                    st.write("Exists" if r.status_code == 200 else "Not found" if r.status_code == 404 else "Error")
                if st.button("Sync Tasklist CSV", type="primary"):
                    df = get_tasklist()
                    if _github_safe_put(df, cfg["tasklist_file"], "Manual sync tasklist", TASKLIST_COLUMNS):
                        st.success("Synced!")
                        clear_cache()
                        st.rerun()

            st.markdown("---")
            st.header("Reports")
            tasks = get_tasks()
            emps = get_employees()
            tasklist = get_tasklist()
            if tasks.empty:
                st.info("No tasks in GitHub.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start Date", value=tasks["date"].min().date())
                    end_date = st.date_input("End Date", value=tasks["date"].max().date())
                with col2:
                    selected_employee = st.selectbox("Employee", ["All"] + sorted(emps["name"].dropna().unique().tolist()))
                    selected_customer = st.selectbox("Customer", ["All"] + sorted(tasks["customer"].dropna().unique().tolist()))
                task_options = ["All"] + sorted(tasklist["task_name"].dropna().unique().tolist())
                selected_task = st.selectbox("Task", task_options)

                df = tasks.copy()
                df = df[(df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)]
                if selected_employee != "All":
                    df = df[df["employee_name"] == selected_employee]
                if selected_customer != "All":
                    df = df[df["customer"] == selected_customer]
                if selected_task != "All":
                    df = df[df["task_name"] == selected_task]

                if df.empty:
                    st.info("No data for selected filters.")
                else:
                    today = datetime.now(TIMEZONE).date()
                    today_df = df[pd.to_datetime(df["date"]).dt.date == today]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Hours", f"{today_df['duration_minutes'].sum()/60:.1f}")
                    c2.metric("Cost", f"${today_df['cost'].sum():,.2f}")
                    c3.metric("Tasks", len(today_df))
                    st.markdown("---")

                    if selected_task == "All":
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

                    if selected_customer == "All" and df["customer"].notna().any():
                        cust_sum = df.groupby("customer").agg(
                            hours=("duration_minutes", lambda x: x.sum()/60),
                            cost=("cost", "sum")
                        ).reset_index()
                        col1, col2 = st.columns(2)
                        with col1:
                            fig = px.bar(cust_sum, x="customer", y="hours", title="Hours by Customer")
                            st.plotly_chart(fig, use_container_width=True)
                        with col2:
                            fig = px.pie(cust_sum, values="cost", names="customer", title="Revenue by Customer")
                            st.plotly_chart(fig, use_container_width=True)

                    st.download_button("Download Filtered Tasks", df.to_csv(index=False), "filtered_tasks.csv", "text/csv")
