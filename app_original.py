import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import pytz
import base64
import requests
from io import StringIO

# -------------------------------
# CONFIGURATION
# -------------------------------
st.set_page_config(page_title="Employee & Sales Task Tracker", page_icon="Timer", layout="wide")
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
    "task_id","date","employee_id","employee_name","task_type_id",
    "task_name","task_category","customer","task_description",
    "start_time","end_time","duration_minutes","cost",
]

# -------------------------------
# HELPERS
# -------------------------------
def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(exist_ok=True)
    df.to_csv(path, index=False)

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
# GITHUB: LOAD FROM GITHUB (SAFE)
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
            return df[columns].copy()
        elif r.status_code == 404:
            st.warning(f"{file_path} not found. Starting fresh.")
            return pd.DataFrame(columns=columns)
        else:
            st.error(f"GitHub error: {r.json().get('message', 'Unknown')}")
            return pd.DataFrame(columns=columns)
    except Exception as e:
        st.error(f"Failed to load {file_path}: {e}")
        return pd.DataFrame(columns=columns)

# -------------------------------
# GITHUB: SAFE PUSH (MERGE + UPDATE)
# -------------------------------
def _github_safe_put(local_df: pd.DataFrame, file_path: str, key_col: str, msg: str) -> tuple[bool, str]:
    try:
        cfg = _github_cfg()
        token, repo, branch = cfg["token"], cfg["repo"], cfg["branch"]
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"

        r = requests.get(url, headers=headers)
        if r.status_code == 404:
            payload = {
                "message": msg,
                "content": base64.b64encode(local_df.to_csv(index=False).encode()).decode(),
                "branch": branch,
            }
            put = requests.put(url, headers=headers, json=payload)
            return put.status_code in (200, 201), "Created on GitHub"
        
        if r.status_code != 200:
            return False, f"GitHub error: {r.json().get('message')}"

        github_content = base64.b64decode(r.json()["content"]).decode("utf-8")
        github_df = pd.read_csv(StringIO(github_content))
        sha = r.json()["sha"]

        merged = github_df.copy()
        for _, row in local_df.iterrows():
            if row[key_col] in merged[key_col].values:
                merged.loc[merged[key_col] == row[key_col]] = row
            else:
                merged = pd.concat([merged, pd.DataFrame([row])], ignore_index=True)

        if merged.to_csv(index=False) == github_df.to_csv(index=False):
            return True, "No changes"

        payload = {
            "message": msg,
            "content": base64.b64encode(merged.to_csv(index=False).encode()).decode(),
            "branch": branch,
            "sha": sha,
        }
        put = requests.put(url, headers=headers, json=payload)
        if put.status_code in (200, 201):
            return True, "Synced safely"
        else:
            return False, f"Push failed: {put.json().get('message')}"
    except Exception as e:
        return False, f"Exception: {e}"

# -------------------------------
# WRITE & DELETE FUNCTIONS (SAFE)
# -------------------------------
def write_task_to_github(task: dict) -> bool:
    df = pd.read_csv(TASKS_FILE) if TASKS_FILE.exists() else pd.DataFrame(columns=TASK_COLUMNS)
    df = pd.concat([df, pd.DataFrame([task])], ignore_index=True)
    save_csv(df, TASKS_FILE)
    success, msg = _github_safe_put(df, _github_cfg()["task_file"], "task_id", f"Append task {task['task_id']}")
    if success:
        st.success(msg)
    else:
        st.error(msg)
    return success

def write_employees_to_github(emp_df: pd.DataFrame) -> bool:
    df = emp_df[EMPLOYEE_COLUMNS].copy()
    save_csv(df, EMPLOYEES_FILE)
    success, msg = _github_safe_put(df, _github_cfg()["emp_file"], "employee_id", f"Update employees")
    if success:
        st.success(msg)
    else:
        st.error(msg)
    return success

def write_tasklist_to_github(df: pd.DataFrame) -> bool:
    df = df[TASKLIST_COLUMNS].copy()
    save_csv(df, TASKLIST_FILE)
    success, msg = _github_safe_put(df, _github_cfg()["tasklist_file"], "task_type_id", f"Update Tasklist")
    if success:
        st.success(msg)
    else:
        st.error(msg)
    return success

def delete_task_from_storage(task_id: str) -> bool:
    df = pd.read_csv(TASKS_FILE) if TASKS_FILE.exists() else pd.DataFrame(columns=TASK_COLUMNS)
    if task_id in df["task_id"].values:
        df = df[df["task_id"] != task_id]
        save_csv(df, TASKS_FILE)
        get_tasks.clear()
        success, msg = _github_safe_put(df, _github_cfg()["task_file"], "task_id", f"Deleted task {task_id}")
        if success:
            st.success(msg)
        else:
            st.error(msg)
        return success
    return False

def write_task_to_storage(task: dict):
    write_task_to_github(task)
    get_tasks.clear()

# -------------------------------
# CACHED DATA – FROM GITHUB
# -------------------------------
@st.cache_data(ttl=60)
def get_employees():
    return _load_from_github(_github_cfg()["emp_file"], EMPLOYEE_COLUMNS)

@st.cache_data(ttl=60)
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

@st.cache_data(ttl=60)
def get_tasks():
    if TASKS_FILE.exists():
        return pd.read_csv(TASKS_FILE)
    return pd.DataFrame(columns=TASK_COLUMNS)

def clear_cache():
    get_employees.clear()
    get_tasklist.clear()
    get_tasks.clear()
    st.rerun()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("Task Tracker")
if st.sidebar.button("Refresh Data from GitHub", type="secondary"):
    clear_cache()

page = st.sidebar.radio("Go to", ["1. Task List", "2. Employee Tasks", "3. Admin"], index=1, key="nav")

# -------------------------------
# PAGE 1 – TASK LIST
# -------------------------------
if page == "1. Task List":
    st.title("Task Library")
    tasklist = get_tasklist().copy()

    with st.form("add_task_type", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1: task_name = st.text_input("Task Name")
        with c2: category = st.text_input("Category")
        tid = st.text_input("Task ID (optional)").strip()
        if st.form_submit_button("Save"):
            if not task_name.strip():
                st.warning("Name required")
            else:
                if not tid:
                    tid = f"TT_{int(datetime.now(TIMEZONE).timestamp())}"
                new_row = {"task_type_id": tid, "task_name": task_name.strip(), "category": category.strip() or "General"}
                if tid in tasklist["task_type_id"].values:
                    tasklist = tasklist[tasklist["task_type_id"] != tid]
                    st.success("Updated")
                else:
                    st.success("Added")
                tasklist = pd.concat([tasklist, pd.DataFrame([new_row])], ignore_index=True)
                write_tasklist_to_github(tasklist)
                clear_cache()

    st.dataframe(tasklist[["task_type_id", "task_name", "category"]], use_container_width=True)

# -------------------------------
# PAGE 2 – EMPLOYEE TASKS
# -------------------------------
elif page == "2. Employee Tasks":
    st.title("Employee Tasks")
    emps = get_employees()
    tasklist = get_tasklist()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state.active_task_id = None

    if emps.empty:
        st.warning("Add employees in Admin to Employees")
    elif tasklist.empty:
        st.warning("Add tasks in Task List")
    else:
        with st.form("start_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                emp_name = st.selectbox("Employee", emps["name"])
                task_name = st.selectbox("Task", tasklist["task_name"])
            with c2:
                cust = st.text_input("Customer")
                note = st.text_area("Notes")
            if st.form_submit_button("Start Task"):
                if st.session_state.active_task_id:
                    st.error("Finish current task first.")
                else:
                    emp = emps[emps["name"] == emp_name].iloc[0]
                    typ = tasklist[tasklist["task_name"] == task_name].iloc[0]
                    now = datetime.now(TIMEZONE)
                    tid = f"T{int(now.timestamp())}"
                    new = {
                        "task_id": tid, "date": now.date().isoformat(),
                        "employee_id": emp["employee_id"], "employee_name": emp["name"],
                        "task_type_id": typ["task_type_id"], "task_name": typ["task_name"],
                        "task_category": typ["category"], "customer": cust,
                        "task_description": note, "start_time": now.isoformat(),
                        "end_time": None, "duration_minutes": None, "cost": None,
                    }
                    write_task_to_storage(new)
                    st.session_state.active_task_id = tid
                    st.success(f"Started at {now.strftime('%H:%M:%S')}")
                    st.rerun()

        # ACTIVE TASK DISPLAY
        if st.session_state.active_task_id:
            active_row = tasks[tasks["task_id"] == st.session_state.active_task_id]
            if active_row.empty:
                st.warning("Active task not found – clearing...")
                st.session_state.active_task_id = None
                st.rerun()
            else:
                active = active_row.iloc[0]
                start = datetime.fromisoformat(active["start_time"]).astimezone(TIMEZONE)
                elapsed = datetime.now(TIMEZONE) - start
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**{active['employee_name']}** – {active['task_name']}")
                with c2:
                    st.write(f"**Elapsed:** {str(elapsed).split('.')[0]}")
                if st.button("Finish Task"):
                    end = datetime.now(TIMEZONE)
                    mins = (end - start).total_seconds() / 60
                    rate = float(emps[emps["employee_id"] == active["employee_id"]].iloc[0]["hourly_rate"])
                    cost = round((mins / 60) * rate, 2)
                    tasks.loc[tasks["task_id"] == st.session_state.active_task_id, ["end_time", "duration_minutes", "cost"]] = [end.isoformat(), mins, cost]
                    save_csv(tasks, TASKS_FILE)
                    _github_safe_put(tasks, _github_cfg()["task_file"], "task_id", f"Finish task {st.session_state.active_task_id}")
                    st.session_state.active_task_id = None
                    st.success(f"Finished – {mins:.1f} min")
                    st.rerun()

        # TASK LOG WITH STOP + DELETE
        st.subheader("Task Log")
        if tasks.empty:
            st.info("No tasks yet.")
        else:
            disp = tasks.copy()
            disp["status"] = disp["end_time"].apply(lambda x: "Completed" if pd.notna(x) else "Active")
            disp["duration_minutes"] = disp["duration_minutes"].fillna(0.0)
            disp["cost"] = disp["cost"].fillna(0.0)
            disp["delete"] = False
            disp["date"] = pd.to_datetime(disp["date"], errors="coerce").dt.date

            # Stop function
            def stop_task(tid):
                row = tasks[tasks["task_id"] == tid].iloc[0]
                end = datetime.now(TIMEZONE)
                start = datetime.fromisoformat(row["start_time"]).astimezone(TIMEZONE)
                mins = (end - start).total_seconds() / 60
                rate = float(emps[emps["employee_id"] == row["employee_id"]].iloc[0]["hourly_rate"])
                cost = round((mins / 60) * rate, 2)
                tasks.loc[tasks["task_id"] == tid, ["end_time", "duration_minutes", "cost"]] = [end.isoformat(), mins, cost]
                save_csv(tasks, TASKS_FILE)
                _github_safe_put(tasks, _github_cfg()["task_file"], "task_id", f"Stopped active task {tid}")
                if st.session_state.active_task_id == tid:
                    st.session_state.active_task_id = None
                st.success(f"Stopped task – {mins:.1f} min")
                st.rerun()

            # Add Stop column
            disp["stop"] = ""
            for idx, row in disp.iterrows():
                if row["status"] == "Active":
                    disp.loc[idx, "stop"] = "Stop"

            edited = st.data_editor(
                disp[["task_id", "date", "employee_name", "task_name", "status", "duration_minutes", "cost", "stop", "delete"]],
                column_config={
                    "stop": st.column_config.TextColumn("Action", disabled=True),
                    "delete": st.column_config.CheckboxColumn("Delete?", default=False),
                    "task_id": st.column_config.TextColumn("ID", disabled=True),
                    "date": st.column_config.DateColumn("Date", disabled=True),
                    "employee_name": st.column_config.TextColumn("Employee"),
                    "task_name": st.column_config.TextColumn("Task"),
                    "status": st.column_config.TextColumn("Status"),
                    "duration_minutes": st.column_config.NumberColumn("Mins", format="%.1f"),
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                },
                hide_index=True,
                key="task_log_editor",
                use_container_width=True
            )

            # Handle Stop buttons
            for _, row in edited.iterrows():
                if row["stop"] == "Stop" and row["status"] == "Active":
                    if st.button(f"Stop##{row['task_id']}", key=f"stop_{row['task_id']}"):
                        stop_task(row["task_id"])

            # Handle Deletions (now allows active)
            if st.button("Apply Deletions", type="primary"):
                deleted = []
                for _, row in edited.iterrows():
                    if row["delete"]:
                        deleted.append(row["task_id"])
                if deleted:
                    for tid in deleted:
                        if tid == st.session_state.active_task_id:
                            st.session_state.active_task_id = None
                        delete_task_from_storage(tid)
                    st.success(f"Deleted {len(deleted)} task(s)")
                    st.rerun()
                else:
                    st.info("No tasks selected for deletion.")

# -------------------------------
# PAGE 3 – ADMIN
# -------------------------------
elif page == "3. Admin":
    st.title("Admin")
    admin_users = st.secrets.get("admin_users")
    if not admin_users:
        st.error("Add `[admin_users]` to secrets.toml")
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
                        st.success("Logged in")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        else:
            if st.button("Logout"):
                st.session_state.auth = False
                st.rerun()
            st.success("Admin Mode")

            # GITHUB CONNECTION TEST + SAFE SYNC
            st.subheader("GitHub Connection Test & Safe Sync")
            c1, c2, c3 = st.columns(3)
            cfg = _github_cfg()

            # --- TASKS CSV ---
            with c1:
                if st.button("Test Tasks CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['task_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
                    if r.status_code == 200:
                        rows = len(pd.read_csv(StringIO(base64.b64decode(r.json()["content"]).decode()))) if r.json()["content"] else 0
                        st.success(f"{rows} rows")
                    elif r.status_code == 404:
                        st.info("Not created yet")
                    else:
                        st.error("Failed")
                if st.button("Sync Tasks CSV", type="primary"):
                    if TASKS_FILE.exists():
                        df = pd.read_csv(TASKS_FILE)
                        success, msg = _github_safe_put(df, cfg["task_file"], "task_id", f"Manual sync tasks – {datetime.now(TIMEZONE).isoformat()}")
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("No local tasks.csv")

            # --- EMPLOYEES CSV ---
            with c2:
                if st.button("Test Employees CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['emp_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
                    if r.status_code == 200:
                        rows = len(pd.read_csv(StringIO(base64.b64decode(r.json()["content"]).decode()))) if r.json()["content"] else 0
                        st.success(f"{rows} rows")
                    elif r.status_code == 404:
                        st.info("Not created yet")
                    else:
                        st.error("Failed")
                if st.button("Sync Employees CSV", type="primary"):
                    if EMPLOYEES_FILE.exists():
                        df = pd.read_csv(EMPLOYEES_FILE)
                        success, msg = _github_safe_put(df, cfg["emp_file"], "employee_id", f"Manual sync employees – {datetime.now(TIMEZONE).isoformat()}")
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("No local employees.csv")

            # --- TASKLIST CSV ---
            with c3:
                if st.button("Test Tasklist CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['tasklist_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
                    if r.status_code == 200:
                        rows = len(pd.read_csv(StringIO(base64.b64decode(r.json()["content"]).decode()))) if r.json()["content"] else 0
                        st.success(f"{rows} rows")
                    elif r.status_code == 404:
                        st.info("Not created yet")
                    else:
                        st.error("Failed")
                if st.button("Sync Tasklist CSV", type="primary"):
                    if TASKLIST_FILE.exists():
                        df = pd.read_csv(TASKLIST_FILE)
                        success, msg = _github_safe_put(df, cfg["tasklist_file"], "task_type_id", f"Manual sync tasklist – {datetime.now(TIMEZONE).isoformat()}")
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("No local Tasklist.csv")

            # ADMIN SECTIONS
            section = st.radio("Section", ["Employees", "Reports"], key="admin_sec")

            if section == "Employees":
                st.header("Employees")
                emps = get_employees().copy()

                with st.form("add_emp", clear_on_submit=True):
                    c1,c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Name")
                        role = st.text_input("Role", value="Support")
                    with c2:
                        rate = st.number_input("Hourly Rate", min_value=0.0, step=0.1, value=18.0)
                        eid = st.text_input("ID (optional)").strip()
                    if st.form_submit_button("Save"):
                        if not name.strip():
                            st.warning("Name required")
                        else:
                            if not eid:
                                eid = f"E{int(datetime.now(TIMEZONE).timestamp())}"
                            new_row = {"employee_id": eid, "name": name.strip(), "role": role.strip(), "hourly_rate": rate}
                            if eid in emps["employee_id"].values:
                                emps = emps[emps["employee_id"] != eid]
                                st.success("Updated")
                            else:
                                st.success("Added")
                            emps = pd.concat([emps, pd.DataFrame([new_row])], ignore_index=True)
                            write_employees_to_github(emps)
                            clear_cache()

                st.subheader("Current Employees")
                if emps.empty:
                    st.info("No employees")
                else:
                    disp = emps.copy()
                    disp["delete"] = False
                    edited = st.data_editor(disp[["employee_id","name","role","hourly_rate","delete"]],
                        column_config={"delete": st.column_config.CheckboxColumn("Delete?", default=False)},
                        hide_index=True, key="emp_edit")
                    if st.button("Apply Changes", type="primary"):
                        to_save = emps.copy()
                        deleted = []
                        for _, row in edited.iterrows():
                            idx = to_save[to_save["employee_id"] == row["employee_id"]].index[0]
                            if row["delete"]:
                                deleted.append(idx)
                            else:
                                to_save.loc[idx, ["name","role","hourly_rate"]] = [row["name"], row["role"], row["hourly_rate"]]
                        if deleted:
                            to_save = to_save.drop(index=deleted).reset_index(drop=True)
                            st.success(f"Deleted {len(deleted)}")
                        write_employees_to_github(to_save)
                        clear_cache()
                        st.rerun()

            else:
                st.header("Reports")
                st.info("Coming soon")
