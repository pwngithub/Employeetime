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
    "task_id",
    "date",
    "employee_id",
    "employee_name",
    "task_type_id",
    "task_name",
    "task_category",
    "customer",
    "task_description",
    "start_time",
    "end_time",
    "duration_minutes",
    "cost",
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
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
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

    for col in TASK_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df.reindex(columns=TASK_COLUMNS)

    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(0)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)

    date_series = pd.to_datetime(df["date"], errors="coerce", utc=True)
    if "start_time" in df.columns:
        start_ts = pd.to_datetime(df["start_time"], errors="coerce", utc=True)
        date_series = date_series.fillna(start_ts)
    df["date"] = date_series

    if "task_category" in df.columns:
        df["task_category"] = df["task_category"].fillna("Uncategorized")
    else:
        df["task_category"] = "Uncategorized"

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
# PAGE 2 – EMPLOYEE TASKS
# -------------------------------
elif page == "2. Employee Tasks":
    st.title("Employee Tasks")
    emps = get_employees()
    tasklist = get_tasklist()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state.active_task_id = None

    if emps.empty or tasklist.empty:
        st.warning("Add employees/tasks in Admin")
    else:

        # ---------------------------
        # START TIMER FIRST
        # ---------------------------
        with st.form("start_form", clear_on_submit=True):
            emp_name = st.selectbox("Employee", emps["name"])
            if st.form_submit_button("Start Timer", disabled=st.session_state.active_task_id is not None):
                emp = emps[emps["name"] == emp_name].iloc[0]
                now = datetime.now(TIMEZONE)
                tid = f"T{str(uuid.uuid4())[:8]}"

                new = {
                    "task_id": tid,
                    "date": now.date().isoformat(),
                    "employee_id": emp["employee_id"],
                    "employee_name": emp["name"],
                    "task_type_id": None,
                    "task_name": "",
                    "task_category": "Uncategorized",
                    "customer": "",
                    "task_description": "",
                    "start_time": now.isoformat(),
                    "end_time": None,
                    "duration_minutes": None,
                    "cost": None,
                }

                if write_task_to_github(new):
                    st.session_state.active_task_id = tid
                    st.success("Timer Started!")
                    st.rerun()

        # ---------------------------
        # ACTIVE TASK — LIVE TIMER + CUSTOMER DROPDOWN
        # ---------------------------
        if st.session_state.active_task_id:
            tasks = get_tasks()
            active_row = tasks[tasks["task_id"] == st.session_state.active_task_id]

            if not active_row.empty:
                active = active_row.iloc[0]
                start = datetime.fromisoformat(active["start_time"]).astimezone(TIMEZONE)
                elapsed = datetime.now(TIMEZONE) - start
                hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)

                # Timer Card
                st.markdown(
                    f"""
                    <div style="background-color:#e3f2fd;padding:20px;border-radius:12px;text-align:center;border:2px solid #1976d2;">
                        <h3>Active Task</h3>
                        <p><b>{active['employee_name']}</b></p>
                        <h2 style="color:#1976d2;font-family:monospace;">{hours:02d}:{minutes:02d}:{seconds:02d}</h2>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.markdown("### Task Details")

                d1, d2 = st.columns(2)

                # -------------------------------
                # TASK SELECT (left side)
                # -------------------------------
                task_names = sorted(tasklist["task_name"].dropna().unique().tolist())
                task_options = ["-- Select Task --"] + task_names

                default_index = 0
                if pd.notna(active["task_name"]) and active["task_name"] in task_names:
                    default_index = task_options.index(active["task_name"])

                with d1:
                    selected_task = st.selectbox(
                        "Task",
                        task_options,
                        index=default_index,
                        key="active_task_select",
                    )

                # -------------------------------
                # NEW CUSTOMER DROPDOWN BLOCK (right side)
                # -------------------------------
                with d2:
                    st.write("Customer")

                    tasks_all = get_tasks()
                    existing_customers = (
                        tasks_all["customer"]
                        .dropna()
                        .unique()
                        .tolist()
                    )
                    existing_customers = sorted([
                        c for c in existing_customers
                        if str(c).strip() not in ("", "None", "nan")
                    ])

                    c1, c2 = st.columns([2, 1])

                    with c1:
                        selected_existing_customer = st.selectbox(
                            "Select Existing",
                            ["-- New Customer --"] + existing_customers,
                            index=0,
                            key="existing_customer_dropdown"
                        )

                    with c2:
                        new_customer_input = st.text_input(
                            "Or New",
                            value=active["customer"] or "",
                            placeholder="Optional",
                            key="new_customer_input"
                        )

                    # Decide which customer is final
                    if selected_existing_customer != "-- New Customer --":
                        final_customer_value = selected_existing_customer
                    else:
                        final_customer_value = new_customer_input.strip()
                # -------------------------------
                # FINISH & CANCEL BUTTONS
                # -------------------------------
                col1, col2 = st.columns([1, 2])

                with col1:
                    if st.button("FINISH TASK", type="primary", use_container_width=True, key="finish_btn"):
                        end = datetime.now(TIMEZONE)
                        mins = (end - start).total_seconds() / 60

                        rate = float(
                            emps[emps["employee_id"] == active["employee_id"]]
                            .iloc[0]["hourly_rate"]
                        )
                        cost = round((mins / 60) * rate, 2)

                        # Determine final task info
                        final_task_name = active["task_name"]
                        final_task_type_id = active["task_type_id"]
                        final_task_category = active["task_category"]

                        if selected_task != "-- Select Task --":
                            typ_row = tasklist[tasklist["task_name"] == selected_task]
                            if not typ_row.empty:
                                typ = typ_row.iloc[0]
                                final_task_name = typ["task_name"]
                                final_task_type_id = typ["task_type_id"]
                                final_task_category = typ["category"]

                        # -------------------------------
                        # UPDATED CUSTOMER LOGIC
                        # -------------------------------
                        final_customer = final_customer_value

                        df = get_tasks()
                        mask = df["task_id"] == st.session_state.active_task_id

                        df.loc[mask, [
                            "task_type_id",
                            "task_name",
                            "task_category",
                            "customer",
                            "end_time",
                            "duration_minutes",
                            "cost",
                        ]] = [
                            final_task_type_id,
                            final_task_name,
                            final_task_category,
                            final_customer,
                            end.isoformat(),
                            mins,
                            cost,
                        ]

                        if _github_safe_put(
                            df,
                            _github_cfg()["task_file"],
                            "Finish task (with details)",
                            TASK_COLUMNS,
                        ):
                            st.session_state.active_task_id = None
                            clear_cache()
                            st.success("Task Finished & Logged!")
                            st.rerun()

                with col2:
                    if st.button("Cancel Active Task", type="secondary", use_container_width=True):
                        st.session_state.active_task_id = None
                        st.rerun()

            else:
                st.warning("Active task not found. Clearing...")
                if st.button("Clear Active Task"):
                    st.session_state.active_task_id = None
                    st.rerun()

        # -------------------------------
        # TASK LOG (unchanged)
        # -------------------------------
        st.subheader("Task Log")
        tasks = get_tasks()

        if tasks.empty:
            st.info("No tasks yet.")
        else:
            disp = tasks.copy()

            disp["status"] = disp["end_time"].apply(lambda x: "Completed" if pd.notna(x) else "Active")

            disp["date"] = pd.to_datetime(disp["start_time"], errors="coerce").dt.date

            disp["delete"] = False

            edited = st.data_editor(
                disp[
                    [
                        "task_id",
                        "date",
                        "employee_name",
                        "customer",
                        "task_name",
                        "status",
                        "duration_minutes",
                        "cost",
                        "delete",
                    ]
                ],
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
                key="task_log_editor",
            )

            if st.button("Delete Selected Tasks", type="primary"):
                to_delete = edited[edited["delete"] == True]["task_id"].tolist()
                if to_delete:
                    if st.session_state.active_task_id in to_delete:
                        st.error("Cannot delete active task!")
                        to_delete = [t for t in to_delete if t != st.session_state.active_task_id]

                    if to_delete:
                        delete_tasks_from_github(to_delete)
                else:
                    st.info("No tasks selected.")

# -------------------------------
# PAGE 3 – ADMIN
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

            # Tasks CSV
            with c1:
                if st.button("Test Tasks CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['task_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
                    st.write("Exists" if r.status_code == 200 else "Not found" if r.status_code == 404 else "Error")

                if st.button("Sync Tasks CSV", type="primary"):
                    df = get_tasks()
                    if _github_safe_put(df, cfg["task_file"], "Manual sync tasks", TASK_COLUMNS):
                        st.success("Synced!")
                        clear_cache()
                        st.rerun()

            # Employees CSV
            with c2:
                if st.button("Test Employees CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['emp_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
                    st.write("Exists" if r.status_code == 200 else "Not found" if r.status_code == 404 else "Error")

                if st.button("Sync Employees CSV", type="primary"):
                    df = get_employees()
                    if _github_safe_put(df, cfg["emp_file"], "Manual sync employees", EMPLOYEE_COLUMNS):
                        st.success("Synced!")
                        clear_cache()
                        st.rerun()

            # Tasklist CSV
            with c3:
                if st.button("Test Tasklist CSV"):
                    r = requests.get(
                        f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['tasklist_file']}?ref={cfg['branch']}",
                        headers={"Authorization": f"token {cfg['token']}"}
                    )
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
                    valid_dates = tasks["date"].dropna()
                    if not valid_dates.empty:
                        min_date = valid_dates.min().date()
                        max_date = valid_dates.max().date()
                    else:
                        today = datetime.now(TIMEZONE).date()
                        min_date = max_date = today

                    start_date = st.date_input("Start Date", value=min_date)
                    end_date = st.date_input("End Date", value=max_date)

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
                    df["hours"] = df["duration_minutes"] / 60.0
                    df["week_start"] = df["date"].dt.to_period("W-SUN").apply(lambda p: p.start_time.date())

                    # KPIs and charts follow…
                    # (same as your existing code)
