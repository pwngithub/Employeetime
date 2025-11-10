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

EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASKS_FILE     = DATA_DIR / "tasks.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"
TIMEZONE = pytz.timezone('America/New_York')

# -------------------------------
# CONSTANTS – ORDER MATTERS!
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
TASK_COLUMNS = [
    "task_id","date","employee_id","employee_name","task_type_id",
    "task_name","task_category","customer","task_description",
    "start_time","end_time","duration_minutes","cost",
]

# -------------------------------
# HELPERS
# -------------------------------
def load_csv(path: Path, columns: list) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path)
        for c in columns:
            if c not in df.columns:
                df[c] = None
        return df[columns]
    return pd.DataFrame(columns=columns)

def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(exist_ok=True)
    df.to_csv(path, index=False)

def create_default_task_types() -> pd.DataFrame:
    defaults = [
        {"task_type_id":"TT_SALES_1","task_name":"Sales – First Contact Reply","category":"Sales"},
        {"task_type_id":"TT_SALES_2","task_name":"Sales – Schedule Site Survey","category":"Sales"},
        {"task_type_id":"TT_OPS_1","task_name":"Construction – Pull Fiber","category":"Construction"},
    ]
    return pd.DataFrame(defaults, columns=TASK_TYPE_COLUMNS)

# -------------------------------
# GITHUB CONFIG & SYNC
# -------------------------------
def _github_cfg():
    cfg = st.secrets.get("github", {})
    return {
        "token": cfg.get("token"),
        "repo": cfg.get("repo"),
        "branch": cfg.get("branch", "main"),
        "task_file": cfg.get("file_path", "Data/tasks.csv"),
        "emp_file": cfg.get("employee_file_path", "Data/employees.csv"),
    }

def _github_put(df: pd.DataFrame, file_path: str, msg: str) -> bool:
    try:
        cfg = _github_cfg()
        token, repo, branch = cfg["token"], cfg["repo"], cfg["branch"]
        if not all([token, repo, file_path]):
            st.error("GitHub config missing")
            return False

        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"

        # Get current file
        r = requests.get(url, headers=headers)
        sha = None
        if r.status_code == 200:
            data = r.json()
            sha = data.get("sha")
        elif r.status_code != 404:
            st.error(f"GitHub GET error: {r.json().get('message')}")
            return False

        # Upload
        payload = {
            "message": msg,
            "content": base64.b64encode(df.to_csv(index=False).encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        put = requests.put(url, headers=headers, json=payload)
        if put.status_code in (200, 201):
            st.success(f"Synced → {file_path}")
            return True
        else:
            st.error(f"GitHub error: {put.json().get('message')}")
            return False
    except Exception as e:
        st.error(f"GitHub exception: {e}")
        return False

def write_task_to_github(task: dict) -> bool:
    df = load_csv(TASKS_FILE, TASK_COLUMNS)
    df = pd.concat([df, pd.DataFrame([task])], ignore_index=True)
    save_csv(df, TASKS_FILE)
    return _github_put(df, _github_cfg()["task_file"], f"Append task {task['task_id']}")

def write_employees_to_github(emp_df: pd.DataFrame) -> bool:
    df = emp_df[EMPLOYEE_COLUMNS].copy()  # Enforce order
    save_csv(df, EMPLOYEE_FILE)
    return _github_put(df, _github_cfg()["emp_file"], f"Update employees – {datetime.now(TIMEZONE).isoformat()}")

def write_task_to_storage(task: dict):
    success = write_task_to_github(task)
    if not success:
        st.error("GitHub failed – saved locally only.")

# -------------------------------
# CACHED DATA
# -------------------------------
@st.cache_data
def get_employees():
    return load_csv(EMPLOYEE_FILE, EMPLOYEE_COLUMNS)

@st.cache_data
def get_task_types():
    if not TASK_TYPES_FILE.exists():
        df = create_default_task_types()
        save_csv(df, TASK_TYPES_FILE)
        return df
    df = load_csv(TASK_TYPES_FILE, TASK_TYPE_COLUMNS)
    if df.empty:
        df = create_default_task_types()
        save_csv(df, TASK_TYPES_FILE)
    return df

@st.cache_data
def get_tasks():
    return load_csv(TASKS_FILE, TASK_COLUMNS)

def clear_cache():
    get_employees.clear()
    get_task_types.clear()
    get_tasks.clear()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("Task Tracker")
page = st.sidebar.radio("Go to", ["1. Task List", "2. Employee Tasks", "3. Admin"], index=1, key="nav")

# -------------------------------
# PAGE 1 – TASK LIBRARY
# -------------------------------
if page == "1. Task List":
    st.title("Task Library")
    tt = get_task_types()
    with st.form("add_task_type", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1: name = st.text_input("Task Name")
        with c2: cat  = st.text_input("Category")
        tid = st.text_input("Task ID (optional)").strip()
        if st.form_submit_button("Save"):
            if not name:
                st.warning("Name required")
            else:
                if not tid: tid = f"TT_{int(datetime.now(TIMEZONE).timestamp())}"
                if tid in tt["task_type_id"].values:
                    tt.loc[tt["task_type_id"]==tid] = [tid,name,cat or "General"]
                    st.success("Updated")
                else:
                    tt = pd.concat([tt, pd.DataFrame([{"task_type_id":tid,"task_name":name,"category":cat or "General"}])], ignore_index=True)
                    st.success("Added")
                save_csv(tt, TASK_TYPES_FILE)
                clear_cache()
    st.dataframe(tt, use_container_width=True)

# -------------------------------
# PAGE 2 – TIMER
# -------------------------------
elif page == "2. Employee Tasks":
    st.title("Employee Tasks")
    emps = get_employees()
    types = get_task_types()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state.active_task_id = None

    if emps.empty:
        st.warning("Add employees in **Admin → Employees** first.")
    elif types.empty:
        st.warning("Add task types first.")
    else:
        with st.form("start_form", clear_on_submit=True):
            c1,c2 = st.columns(2)
            with c1:
                emp_name = st.selectbox("Employee", emps["name"])
                task_name = st.selectbox("Task", types["task_name"])
            with c2:
                cust = st.text_input("Customer (optional)")
                note = st.text_area("Notes")
            if st.form_submit_button("Start Task"):
                if st.session_state.active_task_id:
                    st.error("Finish current task first.")
                else:
                    emp = emps[emps["name"]==emp_name].iloc[0]
                    typ = types[types["task_name"]==task_name].iloc[0]
                    now = datetime.now(TIMEZONE)
                    tid = f"T{int(now.timestamp())}"
                    new = {
                        "task_id":tid, "date":now.date().isoformat(),
                        "employee_id":emp["employee_id"], "employee_name":emp["name"],
                        "task_type_id":typ["task_type_id"], "task_name":typ["task_name"],
                        "task_category":typ["category"], "customer":cust,
                        "task_description":note, "start_time":now.isoformat(),
                        "end_time":None, "duration_minutes":None, "cost":None,
                    }
                    tasks = pd.concat([tasks, pd.DataFrame([new])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    clear_cache()
                    st.session_state.active_task_id = tid
                    st.success(f"Started at {now.strftime('%H:%M:%S')}")

        if st.session_state.active_task_id:
            active = tasks[tasks["task_id"]==st.session_state.active_task_id]
            if active.empty:
                st.session_state.active_task_id = None
                st.warning("Task disappeared.")
            else:
                row = active.iloc[0]
                start = datetime.fromisoformat(row["start_time"]).astimezone(TIMEZONE)
                elapsed = datetime.now(TIMEZONE) - start
                c1,c2,c3 = st.columns(3)
                with c1:
                    st.write(f"**{row['employee_name']}** – {row['task_name']}")
                with c2:
                    st.write(f"**Elapsed:** {str(elapsed).split('.')[0]}")
                with c3:
                    if row["customer"]: st.write(f"**Cust:** {row['customer']}")
                if st.button("Finish Task"):
                    end = datetime.now(TIMEZONE)
                    mins = (end-start).total_seconds()/60
                    cost = round((mins/60)*float(emps[emps["employee_id"]==row["employee_id"]].iloc[0]["hourly_rate"]),2)
                    tasks.loc[tasks["task_id"]==st.session_state.active_task_id, ["end_time","duration_minutes","cost"]] = [end.isoformat(),mins,cost]
                    write_task_to_storage(tasks[tasks["task_id"]==st.session_state.active_task_id].iloc[0].to_dict())
                    save_csv(tasks, TASKS_FILE)
                    clear_cache()
                    st.session_state.active_task_id = None
                    st.success(f"Finished – {mins:.1f} min")
                    st.rerun()

        st.subheader("Task Log")
        if tasks.empty:
            st.info("No tasks yet.")
        else:
            st.dataframe(tasks[[c for c in tasks.columns if c!="cost"]].sort_values("date",ascending=False), use_container_width=True)

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
                    else:
                        st.error("Bad credentials")
        else:
            if st.button("Logout"): st.session_state.auth = False; st.rerun()
            st.success("Admin mode")

            # Storage Test
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Test Tasks CSV"):
                    cfg = _github_cfg()
                    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['task_file']}?ref={cfg['branch']}",
                                     headers={"Authorization": f"token {cfg['token']}"})
                    if r.status_code == 200:
                        rows = len(pd.read_csv(StringIO(base64.b64decode(r.json()["content"]).decode()))) if r.json()["content"] else 0
                        st.success(f"{rows} rows")
                    else:
                        st.error("Failed")
            with c2:
                if st.button("Test Employees CSV"):
                    cfg = _github_cfg()
                    r = requests.get(f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['emp_file']}?ref={cfg['branch']}",
                                     headers={"Authorization": f"token {cfg['token']}"})
                    if r.status_code == 200:
                        rows = len(pd.read_csv(StringIO(base64.b64decode(r.json()["content"]).decode()))) if r.json()["content"] else 0
                        st.success(f"{rows} rows")
                    elif r.status_code == 404:
                        st.info("File not created yet")
                    else:
                        st.error("Failed")

            section = st.radio("Section", ["Employees", "Reports"], key="admin_sec")

            # ---------- EMPLOYEES ----------
            if section == "Employees":
                st.header("Employees")
                emps = get_employees().copy()  # Fresh copy
                tasks = get_tasks().copy()

                # ADD / UPDATE
                with st.form("add_emp", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        name = st.text_input("Name", key="add_name")
                        role = st.text_input("Role", value="Technician", key="add_role")
                    with c2:
                        rate = st.number_input("Hourly Rate", min_value=0.0, step=0.5, value=25.0, key="add_rate")
                        eid = st.text_input("Employee ID (optional)", key="add_eid").strip()
                    if st.form_submit_button("Save Employee"):
                        if not name.strip():
                            st.warning("Name is required.")
                        else:
                            if not eid:
                                eid = f"E{int(datetime.now(TIMEZONE).timestamp())}"
                            new_row = {"employee_id": eid, "name": name.strip(), "role": role.strip(), "hourly_rate": rate}

                            if eid in emps["employee_id"].values:
                                emps = emps[emps["employee_id"] != eid]
                                st.success(f"Updated **{name}**")
                            else:
                                st.success(f"Added **{name}**")

                            emps = pd.concat([emps, pd.DataFrame([new_row])], ignore_index=True)

                            if write_employees_to_github(emps):
                                clear_cache()
                                st.rerun()
                            else:
                                st.error("GitHub sync failed")

                # EDIT / DELETE TABLE
                st.subheader("Current Employees")
                if emps.empty:
                    st.info("No employees yet. Add one above.")
                else:
                    disp = emps.copy()
                    disp["delete"] = False

                    edited = st.data_editor(
                        disp[["employee_id", "name", "role", "hourly_rate", "delete"]],
                        column_config={
                            "delete": st.column_config.CheckboxColumn("Delete?", default=False),
                            "employee_id": st.column_config.TextColumn("ID", disabled=True),
                            "name": st.column_config.TextColumn("Name"),
                            "role": st.column_config.TextColumn("Role"),
                            "hourly_rate": st.column_config.NumberColumn("Rate", format="$%.2f"),
                        },
                        hide_index=True,
                        key="emp_editor"
                    )

                    if st.button("Apply Changes", type="primary"):
                        to_save = emps.copy()
                        deleted = []

                        for _, row in edited.iterrows():
                            idx = to_save[to_save["employee_id"] == row["employee_id"]].index[0]
                            if row["delete"]:
                                task_count = len(tasks[tasks["employee_id"] == row["employee_id"]])
                                if task_count:
                                    st.warning(f"**{row['name']}** has {task_count} task(s). History kept.")
                                deleted.append(idx)
                            else:
                                to_save.loc[idx, ["name", "role", "hourly_rate"]] = [row["name"], row["role"], row["hourly_rate"]]

                        if deleted:
                            to_save = to_save.drop(index=deleted).reset_index(drop=True)
                            st.success(f"Deleted {len(deleted)} employee(s)")

                        if write_employees_to_github(to_save):
                            clear_cache()
                            st.success("Synced to GitHub")
                            st.rerun()
                        else:
                            st.error("GitHub sync failed")

                # SYNC & DEBUG
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Force Sync to GitHub"):
                        df = get_employees()[EMPLOYEE_COLUMNS]
                        st.code(df.to_csv(index=False))
                        write_employees_to_github(df)
                with col2:
                    if st.button("Show CSV"):
                        st.code(get_employees()[EMPLOYEE_COLUMNS].to_csv(index=False))

            # ---------- REPORTS ----------
            else:
                st.header("Reports")
                # Add your report code here
                pass
