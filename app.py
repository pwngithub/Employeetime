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
st.set_page_config(
    page_title="Employee & Sales Task Tracker",
    page_icon="Timer",
    layout="wide",
)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASKS_FILE = DATA_DIR / "tasks.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"
TIMEZONE = pytz.timezone('America/New_York')

# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
TASK_COLUMNS = [
    "task_id", "date", "employee_id", "employee_name", "task_type_id",
    "task_name", "task_category", "customer", "task_description",
    "start_time", "end_time", "duration_minutes", "cost",
]

# -------------------------------
# HELPERS
# -------------------------------
def load_csv(path: Path, columns: list) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        if "employee_id" in df.columns and df["employee_id"].duplicated().any():
            st.warning("Duplicate employee IDs detected.")
        if "task_type_id" in df.columns and df["task_type_id"].duplicated().any():
            st.warning("Duplicate task type IDs detected.")
        return df[columns]
    return pd.DataFrame(columns=columns)

def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(exist_ok=True)
    df.to_csv(path, index=False)

def create_default_task_types() -> pd.DataFrame:
    defaults = [
        {"task_type_id": "TT_SALES_1", "task_name": "Sales – First Contact Reply", "category": "Sales"},
        {"task_type_id": "TT_SALES_2", "task_name": "Sales – Schedule Site Survey", "category": "Sales"},
        {"task_type_id": "TT_SALES_3", "task_name": "Sales – Record Site Survey Results", "category": "Sales"},
        {"task_type_id": "TT_SALES_4", "task_name": "Sales – Schedule Prep", "category": "Sales"},
        {"task_type_id": "TT_SALES_5", "task_name": "Sales – Schedule Install", "category": "Sales"},
        {"task_type_id": "TT_OPS_1", "task_name": "Construction – Pull Fiber", "category": "Construction"},
        {"task_type_id": "TT_OPS_2", "task_name": "Construction – Lash Fiber", "category": "Construction"},
    ]
    return pd.DataFrame(defaults, columns=TASK_TYPE_COLUMNS)

# -------------------------------
# GITHUB CONFIG & HELPERS
# -------------------------------
def _github_config():
    cfg = st.secrets.get("github", {})
    return {
        "token": cfg.get("token"),
        "repo": cfg.get("repo"),
        "branch": cfg.get("branch", "main"),
        "task_file": cfg.get("file_path", "data/tasks.csv"),
        "employee_file": cfg.get("employee_file_path", "data/employees.csv"),
    }

def _github_put(df: pd.DataFrame, file_path: str, message: str) -> bool:
    try:
        cfg = _github_config()
        token, repo, branch = cfg["token"], cfg["repo"], cfg["branch"]
        if not all([token, repo, file_path]):
            st.error(f"Missing GitHub config for {file_path}")
            return False

        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"

        # Get current file
        resp = requests.get(url, headers=headers)
        sha = None
        if resp.status_code == 200:
            data = resp.json()
            if "content" in data:
                content = base64.b64decode(data["content"]).decode("utf-8")
                if content.strip():
                    existing_df = pd.read_csv(StringIO(content))
                    if not all(col in existing_df.columns for col in df.columns):
                        st.warning(f"Column mismatch in {file_path}; overwriting.")
                sha = data["sha"]
        elif resp.status_code != 404:
            st.error(f"GitHub GET error: {resp.json().get('message')}")
            return False

        # Upload
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        payload = {
            "message": message,
            "content": base64.b64encode(csv_bytes).decode("utf-8"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(url, headers=headers, json=payload)
        if put_resp.status_code in (200, 201):
            st.success(f"Updated GitHub: {file_path}")
            return True
        else:
            st.error(f"GitHub PUT error: {put_resp.json().get('message')}")
            return False
    except Exception as e:
        st.error(f"GitHub error: {e}")
        return False

def write_task_to_github(task_data: dict) -> bool:
    df = load_csv(TASKS_FILE, TASK_COLUMNS)
    df = pd.concat([df, pd.DataFrame([task_data])], ignore_index=True)
    save_csv(df, TASKS_FILE)
    return _github_put(df, _github_config()["task_file"], f"Append task {task_data.get('task_id')}")

def write_employees_to_github(employees_df: pd.DataFrame) -> bool:
    save_csv(employees_df, EMPLOYEE_FILE)
    return _github_put(employees_df, _github_config()["employee_file"], "Update employees.csv")

def write_task_to_storage(task_data: dict):
    st.write(f"Writing task {task_data.get('task_id')}…")
    success = write_task_to_github(task_data)
    if not success:
        st.error("GitHub write failed – saved locally only.")

# -------------------------------
# DATA LOADERS
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

def refresh_employees_cache(): get_employees.clear()
def refresh_task_types_cache(): get_task_types.clear()
def refresh_tasks_cache(): get_tasks.clear()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("Task Tracker")
page = st.sidebar.radio(
    "Go to",
    ["1. Task List", "2. Employee Tasks", "3. Admin"],
    index=1,
    key="main_nav",
)

# -------------------------------
# PAGE 1: TASK LIST
# -------------------------------
if page == "1. Task List":
    st.title("Task Library")
    task_types = get_task_types()
    st.subheader("Add / Update Task Type")
    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input("Task Name", placeholder="e.g., Sales – Schedule Site Survey")
        with c2:
            category = st.text_input("Category", placeholder="e.g., Sales, Construction")
        task_type_id = st.text_input("Task ID (optional, auto if blank)").strip()
        submitted = st.form_submit_button("Save Task Type")
        if submitted:
            if not task_name:
                st.warning("Task name required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now(TIMEZONE).timestamp())}"
                mask = task_types["task_type_id"] == task_type_id
                new_row = {"task_type_id": task_type_id, "task_name": task_name, "category": category or "General"}
                if mask.any():
                    task_types.loc[mask, :] = new_row
                    st.success(f"Updated {task_name}.")
                else:
                    task_types = pd.concat([task_types, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added {task_name}.")
                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()
    st.subheader("Existing Tasks")
    st.dataframe(get_task_types(), use_container_width=True)

# -------------------------------
# PAGE 2: EMPLOYEE TASKS
# -------------------------------
elif page == "2. Employee Tasks":
    st.title("Employee Tasks (Start/Finish Timer)")
    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None

    if employees.empty:
        st.warning("Add employees first under **Admin → Employees**.")
    elif task_types.empty:
        st.warning("Add task types first on the **Task List** page.")
    else:
        st.subheader("Start a Task")
        with st.form("start_task_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                employee_name = st.selectbox("Employee", employees["name"])
                task_choice = st.selectbox("Task", task_types["task_name"])
            with col2:
                customer = st.text_input("Customer / Lead (optional)")
                desc = st.text_area("Notes", placeholder="Optional notes...")
            start_submitted = st.form_submit_button("Start Task")
            if start_submitted:
                if st.session_state["active_task_id"]:
                    st.error("A task is already running. Finish it first.")
                else:
                    emp = employees[employees["name"] == employee_name].iloc[0]
                    tt = task_types[task_types["task_name"] == task_choice].iloc[0]
                    start_time = datetime.now(TIMEZONE)
                    tid = f"T{int(start_time.timestamp())}"
                    new_task = {
                        "task_id": tid, "date": start_time.date().isoformat(),
                        "employee_id": emp["employee_id"], "employee_name": emp["name"],
                        "task_type_id": tt["task_type_id"], "task_name": tt["task_name"],
                        "task_category": tt["category"], "customer": customer or "",
                        "task_description": desc, "start_time": start_time.isoformat(),
                        "end_time": None, "duration_minutes": None, "cost": None,
                    }
                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = tid
                    st.success(f"Started '{tt['task_name']}' for {employee_name} at {start_time.strftime('%H:%M:%S')}")

        st.subheader("Active Task")
        active_id = st.session_state["active_task_id"]
        tasks = get_tasks()
        if not active_id:
            st.info("No active task.")
        else:
            active = tasks[tasks["task_id"] == active_id]
            if active.empty:
                st.session_state["active_task_id"] = None
                st.warning("Active task not found.")
            else:
                row = active.iloc[0]
                start_dt = datetime.fromisoformat(str(row["start_time"])).astimezone(TIMEZONE)
                elapsed = datetime.now(TIMEZONE) - start_dt
                elapsed_str = str(elapsed).split(".")[0]
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Employee:** {row['employee_name']}")
                    st.write(f"**Task:** {row['task_name']}")
                    st.write(f"**Category:** {row['task_category']}")
                with c2:
                    st.write(f"**Started:** {row['start_time']}")
                    st.write(f"**Elapsed:** {elapsed_str}")
                    if row.get("customer"):
                        st.write(f"**Customer:** {row['customer']}")
                with c3:
                    st.write("**Notes:**")
                    st.write(row["task_description"])
                if st.button("Finish Task", key="finish_btn"):
                    end_dt = datetime.now(TIMEZONE)
                    emp = employees[employees["employee_id"] == row["employee_id"]].iloc[0]
                    minutes = (end_dt - start_dt).total_seconds() / 60
                    cost = round((minutes / 60) * float(emp["hourly_rate"]), 2)
                    tasks.loc[tasks["task_id"] == active_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_id, "duration_minutes"] = minutes
                    tasks.loc[tasks["task_id"] == active_id, "cost"] = cost
                    completed = tasks[tasks["task_id"] == active_id].iloc[0]
                    write_task_to_storage(completed.to_dict())
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = None
                    st.success(f"Task finished – {minutes:.1f} min. Saved to GitHub.")
                    st.rerun()

        st.subheader("Task Log")
        df = get_tasks()
        if df.empty:
            st.info("No tasks logged yet.")
        else:
            cols = [c for c in df.columns if c != "cost"]
            st.dataframe(df[cols].sort_values("date", ascending=False), use_container_width=True)

# -------------------------------
# PAGE 3: ADMIN
# -------------------------------
elif page == "3. Admin":
    st.title("Admin Area")
    admin_users = st.secrets.get("admin_users", None)
    if admin_users is None:
        st.error("Admin users not configured in secrets.")
    else:
        if "admin_authenticated" not in st.session_state:
            st.session_state["admin_authenticated"] = False
            st.session_state["admin_username"] = None

        if not st.session_state["admin_authenticated"]:
            st.subheader("Login")
            with st.form("admin_login_form"):
                username = st.text_input("Username")
                pw = st.text_input("Password", type="password")
                login = st.form_submit_button("Login")
                if login:
                    if username in admin_users and pw == admin_users[username]:
                        st.session_state["admin_authenticated"] = True
                        st.session_state["admin_username"] = username
                        st.success(f"Welcome, {username}!")
                    else:
                        st.error("Invalid credentials.")
        else:
            st.success(f"Admin access – {st.session_state['admin_username']}")
            if st.button("Logout", key="admin_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_username"] = None
                st.rerun()

            st.subheader("Storage Status")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Test GitHub Tasks CSV"):
                    cfg = _github_config()
                    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['task_file']}?ref={cfg['branch']}"
                    hdr = {"Authorization": f"token {cfg['token']}", "Accept": "application/vnd.github.v3+json"}
                    r = requests.get(url, headers=hdr)
                    if r.status_code == 200:
                        data = r.json()
                        content = base64.b64decode(data["content"]).decode("utf-8")
                        rows = len(pd.read_csv(StringIO(content))) if content.strip() else 0
                        st.success(f"Tasks CSV OK – {rows} rows")
                    else:
                        st.error(f"Error {r.status_code}")
            with col2:
                if st.button("Test GitHub Employees CSV"):
                    cfg = _github_config()
                    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['employee_file']}?ref={cfg['branch']}"
                    hdr = {"Authorization": f"token {cfg['token']}", "Accept": "application/vnd.github.v3+json"}
                    r = requests.get(url, headers=hdr)
                    if r.status_code == 200:
                        data = r.json()
                        content = base64.b64decode(data["content"]).decode("utf-8")
                        rows = len(pd.read_csv(StringIO(content))) if content.strip() else 0
                        st.success(f"Employees CSV OK – {rows} rows")
                    elif r.status_code == 404:
                        st.info("Employees CSV not created yet.")
                    else:
                        st.error(f"Error {r.status_code}")

            section = st.radio("Admin Section", ["Employees", "Reports"], key="admin_section_radio")

            # ================================
            # EMPLOYEES (WITH DELETE)
            # ================================
            if section == "Employees":
                st.header("Manage Employees")
                employees = get_employees()
                tasks = get_tasks()

                st.subheader("Add / Update Employee")
                with st.form("admin_employee_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Name")
                        role = st.text_input("Role", value="Technician")
                    with col2:
                        hourly_rate = st.number_input("Hourly Rate ($/hour)", min_value=0.0, step=0.5, value=25.0)
                        employee_id = st.text_input("Employee ID (optional, auto if blank)").strip()
                    submitted = st.form_submit_button("Save Employee")
                    if submitted:
                        if not name:
                            st.warning("Name required.")
                        else:
                            if not employee_id:
                                employee_id = f"E{int(datetime.now(TIMEZONE).timestamp())}"
                            mask = employees["employee_id"] == employee_id
                            new_row = {"employee_id": employee_id, "name": name, "role": role, "hourly_rate": hourly_rate}
                            if mask.any():
                                employees.loc[mask, :] = new_row
                                st.success(f"Updated {name}.")
                            else:
                                employees = pd.concat([employees, pd.DataFrame([new_row])], ignore_index=True)
                                st.success(f"Added {name}.")
                            write_employees_to_github(employees)
                            refresh_employees_cache()

                st.subheader("Current Employees")
                if employees.empty:
                    st.info("No employees yet.")
                else:
                    emp_display = employees.copy()
                    emp_display["delete"] = False

                    edited_emp = st.data_editor(
                        emp_display[["employee_id", "name", "role", "hourly_rate", "delete"]],
                        use_container_width=True,
                        column_config={
                            "delete": st.column_config.CheckboxColumn("Delete?", default=False),
                            "employee_id": st.column_config.TextColumn("ID", disabled=True),
                            "name": st.column_config.TextColumn("Name"),
                            "role": st.column_config.TextColumn("Role"),
                            "hourly_rate": st.column_config.NumberColumn("Rate ($/hr)", format="$%.2f"),
                        },
                        hide_index=True,
                        key="employee_editor"
                    )

                    if st.button("Apply Changes (Save & Delete)", type="primary"):
                        deleted = []
                        for idx, row in edited_emp.iterrows():
                            orig_idx = employees[employees["employee_id"] == row["employee_id"]].index
                            if len(orig_idx) == 0:
                                continue
                            orig_idx = orig_idx[0]

                            emp_tasks = tasks[tasks["employee_id"] == row["employee_id"]]
                            if row["delete"]:
                                if not emp_tasks.empty:
                                    st.warning(f"**{row['name']}** has {len(emp_tasks)} task(s). History preserved.")
                                deleted.append(orig_idx)
                            else:
                                employees.loc[orig_idx, ["name", "role", "hourly_rate"]] = [
                                    row["name"], row["role"], row["hourly_rate"]
                                ]

                        if deleted:
                            employees = employees.drop(index=deleted).reset_index(drop=True)
                            st.success(f"Deleted {len(deleted)} employee(s).")

                        write_employees_to_github(employees)
                        refresh_employees_cache()
                        st.rerun()

                st.dataframe(get_employees(), use_container_width=True)

            # ================================
            # REPORTS (unchanged)
            # ================================
            elif section == "Reports":
                st.header("Reports (with Cost)")
                tasks = get_tasks()
                if tasks.empty:
                    st.info("No tasks logged yet.")
                else:
                    df = tasks.copy()
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df_done = df[df["duration_minutes"].notna()]
                    if df_done.empty:
                        st.info("No completed tasks.")
                    else:
                        # [Keep your original report code here]
                        pass
