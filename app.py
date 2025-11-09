import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import pytz
import base64
import requests
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import buildimport streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import pytz
import base64
import requests
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GSHEETS_AVAILABLE = True
    st.info("Google Sheets API libraries loaded.")
except ImportError:
    GSHEETS_AVAILABLE = False
    st.warning(
        "Google Sheets API libraries not installed. Falling back to GitHub CSV.\n\n"
        "Add 'google-api-python-client>=2.0.0' and 'google-auth>=2.0.0' to requirements.txt to enable Google Sheets."
    )

# -------------------------------
# CONFIGURATION
# -------------------------------
st.set_page_config(
    page_title="Employee & Sales Task Tracker",
    page_icon="⏱️",
    layout="wide",
)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASKS_FILE = DATA_DIR / "tasks.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"
TIMEZONE = pytz.timezone('America/New_York')  # Adjust to your timezone
# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
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
# HELPERS
# -------------------------------
def load_csv(path: Path, columns: list) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        if "employee_id" in df.columns and df["employee_id"].duplicated().any():
            st.warning("Duplicate employee IDs detected. Please ensure unique IDs.")
        if "task_type_id" in df.columns and df["task_type_id"].duplicated().any():
            st.warning("Duplicate task type IDs detected. Please ensure unique IDs.")
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
# GOOGLE SHEETS HELPERS
# -------------------------------
@st.cache_resource
def connect_gsheet_api():
    if not GSHEETS_AVAILABLE:
        st.error("Google Sheets API libraries not installed. Using GitHub CSV.")
        return None
    try:
        creds_dict = st.secrets.get("gcp_service_account", {})
        if not creds_dict:
            st.error("Missing [gcp_service_account] in Streamlit secrets.")
            return None
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        st.error(f"Google Sheets API Connection Error: {e}")
        return None

def write_task_to_gsheet_api(task_data: dict):
    service = connect_gsheet_api()
    if not service:
        return False
    try:
        sheet_cfg = st.secrets.get("google_sheet", {})
        sheet_id = sheet_cfg.get("sheet_id", "1RVRUtL-y-F5e5KCqpdDQkN6voBIiGSvHjX_9fMNANqI")
        worksheet_name = sheet_cfg.get("worksheet_name", "Tasks")
        # Check if headers exist
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"{worksheet_name}!A1:Z1"
        ).execute()
        if not result.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{worksheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [TASK_COLUMNS]},
            ).execute()
        # Append task
        row = [str(task_data.get(col, "")) for col in TASK_COLUMNS]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{worksheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        st.success(f"Appended task to Google Sheet (Worksheet: {worksheet_name}).")
        return True
    except Exception as e:
        st.error(f"Failed to write to Google Sheet: {e}")
        return False

# -------------------------------
# GITHUB CSV HELPERS
# -------------------------------
def write_task_to_github(task_data: dict):
    try:
        github_cfg = st.secrets.get("github", {})
        token = github_cfg.get("token")
        repo = github_cfg.get("repo")
        branch = github_cfg.get("branch", "main")
        file_path = github_cfg.get("file_path", "data/tasks.csv")
        if not all([token, repo, file_path]):
            st.error(f"Missing GitHub configuration: token={bool(token)}, repo={bool(repo)}, file_path={bool(file_path)}")
            return False
        # Get current file content
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
        response = requests.get(url, headers=headers)
        df = pd.DataFrame(columns=TASK_COLUMNS)
        sha = None
        if response.status_code == 200:
            content_data = response.json()
            content = base64.b64decode(content_data["content"]).decode("utf-8")
            df = pd.read_csv(pd.StringIO(content))
            sha = content_data["sha"]
            st.write(f"GitHub GET: File found, SHA: {sha}")
        elif response.status_code == 404:
            st.write("GitHub GET: File not found, creating new file.")
        else:
            st.error(f"GitHub GET failed (status {response.status_code}): {response.json().get('message', 'Unknown error')}")
            return False
        # Append new task
        new_row = pd.DataFrame([task_data], columns=TASK_COLUMNS)
        df = pd.concat([df, new_row], ignore_index=True)
        # Encode updated content
        content = df.to_csv(index=False).encode("utf-8")
        encoded_content = base64.b64encode(content).decode("utf-8")
        # Update or create file
        data = {
            "message": f"Append task {task_data.get('task_id', 'unknown')} to {file_path}",
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            data["sha"] = sha
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            st.success(f"Appended task {task_data.get('task_id', 'unknown')} to GitHub CSV ({file_path}).")
            return True
        else:
            error_msg = response.json().get('message', 'Unknown error')
            st.error(f"GitHub PUT failed (status {response.status_code}): {error_msg}")
            st.write("Response details:", response.json())
            return False
    except Exception as e:
        st.error(f"GitHub CSV write error: {e}")
        return False

def write_task_to_storage(task_data: dict):
    st.write(f"Attempting to write task {task_data.get('task_id', 'unknown')} to storage.")
    success = False
    if GSHEETS_AVAILABLE:
        success = write_task_to_gsheet_api(task_data)
        if success:
            st.write("Google Sheets write successful.")
    if not success:
        success = write_task_to_github(task_data)
        if success:
            st.write("GitHub CSV write successful.")
    if not success:
        st.error("Failed to write to both Google Sheets and GitHub CSV. Task saved locally.")

# -------------------------------
# DATA LOADERS (CACHED)
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

def refresh_employees_cache():
    get_employees.clear()

def refresh_task_types_cache():
    get_task_types.clear()

def refresh_tasks_cache():
    get_tasks.clear()

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
st.sidebar.title("⏱️ Task Tracker")
page = st.sidebar.radio(
    label="Go to",
    options=[
        "1️⃣ Task List",
        "2️⃣ Employee Tasks",
        "3️⃣ Admin",
    ],
    index=1,
    key="main_nav",
)

# -------------------------------
# PAGE 1: TASK LIST (LIBRARY)
# -------------------------------
if page == "1️⃣ Task List":
    st.title("Task Library")
    task_types = get_task_types()
    st.subheader("Add / Update Task Type")
    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input(
                "Task Name",
                placeholder="e.g., Sales – Schedule Site Survey",
            )
        with c2:
            category = st.text_input(
                "Category",
                placeholder="e.g., Sales, Construction, Admin",
            )
        task_type_id = st.text_input("Task ID (optional, auto if blank)").strip()
        submitted = st.form_submit_button("Save Task Type")
        if submitted:
            if not task_name:
                st.warning("Task name required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now(TIMEZONE).timestamp())}"
                mask = task_types["task_type_id"] == task_type_id
                new_row = {
                    "task_type_id": task_type_id,
                    "task_name": task_name,
                    "category": category or "General",
                }
                if mask.any():
                    task_types.loc[mask, :] = new_row
                    st.success(f"Updated {task_name}.")
                else:
                    task_types = pd.concat(
                        [task_types, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    st.success(f"Added {task_name}.")
                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()
    st.subheader("Existing Tasks")
    st.dataframe(get_task_types(), use_container_width=True)

# -------------------------------
# PAGE 2: EMPLOYEE TASKS
# -------------------------------
elif page == "2️⃣ Employee Tasks":
    st.title("Employee Tasks (Start/Finish Timer)")
    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()
    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None
    if employees.empty:
        st.warning("Add employees first under Admin → Employees.")
    elif task_types.empty:
        st.warning("Add task types first on the Task List page.")
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
            start_submitted = st.form_submit_button("▶️ Start Task")
            if start_submitted:
                if st.session_state["active_task_id"]:
                    st.error("A task is already running. Finish it first.")
                else:
                    emp = employees[employees["name"] == employee_name].iloc[0]
                    tt = task_types[task_types["task_name"] == task_choice].iloc[0]
                    start_time = datetime.now(TIMEZONE)
                    tid = f"T{int(start_time.timestamp())}"
                    new_task = {
                        "task_id": tid,
                        "date": start_time.date().isoformat(),
                        "employee_id": emp["employee_id"],
                        "employee_name": emp["name"],
                        "task_type_id": tt["task_type_id"],
                        "task_name": tt["task_name"],
                        "task_category": tt["category"],
                        "customer": customer or "",
                        "task_description": desc,
                        "start_time": start_time.isoformat(),
                        "end_time": None,
                        "duration_minutes": None,
                        "cost": None,
                    }
                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = tid
                    st.success(
                        f"Started '{tt['task_name']}' for {employee_name}"
                        + (f" (Customer: {customer})" if customer else "")
                        + f" at {start_time.strftime('%H:%M:%S')}"
                    )
        st.subheader("Active Task")
        active_id = st.session_state["active_task_id"]
        tasks = get_tasks()
        if not active_id:
            st.info("No active task running.")
        else:
            active = tasks[tasks["task_id"] == active_id]
            if active.empty:
                st.session_state["active_task_id"] = None
                st.warning("Active task not found, resetting.")
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
                if st.button("⏹️ Finish Task", key="finish_btn"):
                    end_dt = datetime.now(TIMEZONE)
                    emp = employees[employees["employee_id"] == row["employee_id"]].iloc[0]
                    minutes = (end_dt - start_dt).total_seconds() / 60
                    cost = round((minutes / 60) * float(emp["hourly_rate"]), 2)
                    tasks.loc[tasks["task_id"] == active_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_id, "duration_minutes"] = minutes
                    tasks.loc[tasks["task_id"] == active_id, "cost"] = cost
                    completed_task_row = tasks[tasks["task_id"] == active_id].iloc[0]
                    write_task_to_storage(completed_task_row.to_dict())
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = None
                    st.success(
                        f"Task finished. Duration {minutes:.1f} minutes. "
                        "Logged to local CSV and Google Sheet/GitHub (if configured)."
                    )
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
elif page == "3️⃣ Admin":
    st.title("Admin Area")
    admin_users = st.secrets.get("admin_users", None)
    if admin_users is None:
        st.error(
            "Admin users not configured in secrets.\n\n"
            "In Streamlit Cloud, go to 'Edit secrets' and add:\n\n"
            "[admin_users]\n"
            "brian = \"yourPasswordHere\""
        )
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
                        st.error("Invalid username or password.")
        else:
            st.success(f"Admin access granted ({st.session_state['admin_username']}).")
            if st.button("Logout", key="admin_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_username"] = None
                st.rerun()
            st.subheader("Storage Status")
            if st.button("🔍 Test Google Sheets Connection"):
                service = connect_gsheet_api()
                if service:
                    sheet_cfg = st.secrets.get("google_sheet", {})
                    sheet_id = sheet_cfg.get("sheet_id", "1RVRUtL-y-F5e5KCqpdDQkN6voBIiGSvHjX_9fMNANqI")
                    worksheet_name = sheet_cfg.get("worksheet_name", "Tasks")
                    try:
                        result = service.spreadsheets().values().get(
                            spreadsheetId=sheet_id, range=f"{worksheet_name}!A1:Z1"
                        ).execute()
                        row_count = len(service.spreadsheets().values().get(
                            spreadsheetId=sheet_id, range=worksheet_name
                        ).execute().get("values", []))
                        st.success(f"Connected! Sheet ID: {sheet_id}, Worksheet: {worksheet_name}, Rows: {row_count}")
                    except Exception as e:
                        st.error(f"Test failed: {e}")
                else:
                    st.error("Google Sheets connection failed. Check secrets or library installation.")
            if st.button("🔍 Test GitHub Connection"):
                github_cfg = st.secrets.get("github", {})
                token = github_cfg.get("token")
                repo = github_cfg.get("repo")
                branch = github_cfg.get("branch", "main")
                file_path = github_cfg.get("file_path", "data/tasks.csv")
                if not all([token, repo, file_path]):
                    st.error(f"Missing GitHub configuration: token={bool(token)}, repo={bool(repo)}, file_path={bool(file_path)}")
                else:
                    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                    url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        content = base64.b64decode(response.json()["content"]).decode("utf-8")
                        df = pd.read_csv(pd.StringIO(content))
                        st.success(f"Connected to GitHub repo {repo}, file {file_path} (rows: {len(df)}).")
                    else:
                        st.error(f"GitHub connection failed (status {response.status_code}): {response.json().get('message', 'Unknown error')}")
            # Debug and Test Write
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔧 Debug Pending Tasks"):
                    pending = st.session_state.get("pending_tasks", [])
                    st.write(f"Pending tasks: {len(pending)}")
                    if pending:
                        st.json(pending[-1])
                    else:
                        st.info("No pending tasks.")
            with col2:
                if st.button("💾 Test Write to GitHub"):
                    dummy_task = {
                        "task_id": f"T{int(datetime.now(TIMEZONE).timestamp())}",
                        "date": datetime.now(TIMEZONE).date().isoformat(),
                        "employee_id": "E_TEST",
                        "employee_name": "Test User",
                        "task_type_id": "TT_TEST",
                        "task_name": "Test Task",
                        "task_category": "Test",
                        "customer": "Test Customer",
                        "task_description": "Debug write",
                        "start_time": datetime.now(TIMEZONE).isoformat(),
                        "end_time": datetime.now(TIMEZONE).isoformat(),
                        "duration_minutes": 10.0,
                        "cost": 5.0,
                    }
                    write_task_to_github(dummy_task)
            if st.session_state["admin_authenticated"]:
                section = st.radio(
                    "Admin Section",
                    ["Employees", "Reports"],
                    key="admin_section_radio",
                )
                if section == "Employees":
                    st.header("Manage Employees")
                    employees = get_employees()
                    st.subheader("Add / Update Employee")
                    with st.form("admin_employee_form", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            name = st.text_input("Name")
                            role = st.text_input("Role", value="Technician")
                        with col2:
                            hourly_rate = st.number_input(
                                "Hourly Rate ($/hour)", min_value=0.0, step=0.5, value=25.0
                            )
                            employee_id = st.text_input(
                                "Employee ID (optional, auto if blank)"
                            ).strip()
                        submitted = st.form_submit_button("Save Employee")
                        if submitted:
                            if not name:
                                st.warning("Name is required.")
                            else:
                                if not employee_id:
                                    employee_id = f"E{int(datetime.now(TIMEZONE).timestamp())}"
                                mask = employees["employee_id"] == employee_id
                                new_row = {
                                    "employee_id": employee_id,
                                    "name": name,
                                    "role": role,
                                    "hourly_rate": hourly_rate,
                                }
                                if mask.any():
                                    employees.loc[mask, :] = new_row
                                    st.success(f"Updated employee {name}.")
                                else:
                                    employees = pd.concat(
                                        [employees, pd.DataFrame([new_row])],
                                        ignore_index=True,
                                    )
                                    st.success(f"Added employee {name}.")
                                save_csv(employees, EMPLOYEE_FILE)
                                refresh_employees_cache()
                    st.subheader("Edit Existing Employee")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees to edit.")
                    else:
                        emp_names = employees["name"].tolist()
                        selected_name = st.selectbox(
                            "Select Employee to Edit",
                            options=emp_names,
                            key="edit_emp_select",
                        )
                        emp_row = employees[employees["name"] == selected_name].iloc[0]
                        current_rate = float(emp_row["hourly_rate"])
                        current_role = emp_row["role"]
                        emp_id = emp_row["employee_id"]
                        with st.form("edit_employee_form"):
                            new_name = st.text_input(
                                "Name",
                                value=selected_name,
                                key=f"edit_name_input_{emp_id}",
                            )
                            new_role = st.text_input(
                                "Role",
                                value=current_role,
                                key=f"edit_role_input_{emp_id}",
                            )
                            new_rate = st.number_input(
                                "New Hourly Rate ($/hour)",
                                min_value=0.0,
                                step=0.5,
                                value=current_rate,
                                key=f"edit_rate_input_{emp_id}",
                            )
                            update = st.form_submit_button("Update Employee")
                            if update:
                                employees.loc[
                                    employees["employee_id"] == emp_row["employee_id"],
                                    ["name", "role", "hourly_rate"],
                                ] = [new_name, new_role, new_rate]
                                save_csv(employees, EMPLOYEE_FILE)
                                refresh_employees_cache()
                                st.success(
                                    f"Updated employee: '{selected_name}' → '{new_name}', "
                                    f"role='{new_role}', hourly rate=${new_rate:.2f}"
                                )
                    st.subheader("Current Employees")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees yet.")
                    else:
                        st.dataframe(employees, use_container_width=True)
                elif section == "Reports":
                    st.header("Reports (with Cost)")
                    tasks = get_tasks()
                    if tasks.empty:
                        st.info("No tasks logged yet.")
                    else:
                        df = tasks.copy()
                        df["date"] = pd.to_datetime(df["date"], errors="coerce")
                        if "customer" not in df.columns:
                            df["customer"] = ""
                        df_done = df[df["duration_minutes"].notna()]
                        if df_done.empty:
                            st.info("No completed tasks yet.")
                        else:
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                start_date = st.date_input(
                                    "Start date",
                                    value=df_done["date"].min().date(),
                                )
                            with c2:
                                end_date = st.date_input(
                                    "End date",
                                    value=df_done["date"].max().date(),
                                )
                            with c3:
                                customer_filter = st.text_input(
                                    "Filter by customer (contains)",
                                    placeholder="leave blank for all",
                                )
                            mask = (df_done["date"] >= pd.to_datetime(start_date)) & (
                                df_done["date"] <= pd.to_datetime(end_date)
                            )
                            if customer_filter:
                                mask &= df_done["customer"].fillna("").str.contains(
                                    customer_filter, case=False, na=False
                                )
                            df_filtered = df_done[mask]
                            if df_filtered.empty:
                                st.warning("No tasks match the selected filters.")
                            else:
                                total_tasks = len(df_filtered)
                                total_minutes = df_filtered["duration_minutes"].fillna(0).sum()
                                total_hours = round(total_minutes / 60.0, 2)
                                total_cost = float(df_filtered["cost"].fillna(0).sum())
                                cust_series = (
                                    df_filtered["customer"]
                                    .fillna("")
                                    .astype(str)
                                    .str.strip()
                                )
                                unique_customers = cust_series.replace("", pd.NA).nunique()
                                k1, k2, k3, k4 = st.columns(4)
                                with k1:
                                    st.metric("Total Tasks", total_tasks)
                                with k2:
                                    st.metric("Total Hours", f"{total_hours:.2f}")
                                with k3:
                                    st.metric("Total Cost", f"${total_cost:,.2f}")
                                with k4:
                                    st.metric("Customers", unique_customers)
                                st.markdown("---")
                                st.subheader("Summary by Customer")
                                cust_df = df_filtered.copy()
                                cust_df["customer"] = cust_df["customer"].fillna("")
                                cust_df.loc[cust_df["customer"] == "", "customer"] = "Unspecified"
                                by_customer = cust_df.groupby("customer").agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(by_customer, use_container_width=True)
                                selected_customer = st.selectbox(
                                    "View KPIs for a single customer",
                                    options=["All"] + sorted(by_customer["customer"].tolist()),
                                    index=0,
                                    key="customer_kpi_select",
                                )
                                if selected_customer != "All":
                                    row = by_customer[
                                        by_customer["customer"] == selected_customer
                                    ].iloc[0]
                                    kc1, kc2, kc3 = st.columns(3)
                                    with kc1:
                                        st.metric("Customer", selected_customer)
                                    with kc2:
                                        st.metric("Total Hours", f"{row['total_hours']:.2f}")
                                    with kc3:
                                        st.metric("Total Cost", f"${row['total_cost']:.2f}")
                                st.markdown("---")
                                st.subheader("Summary by Employee")
                                emp = df_filtered.groupby("employee_name").agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(emp, use_container_width=True)
                                st.subheader("Summary by Task")
                                t = df_filtered.groupby(
                                    ["task_name", "task_category"]
                                ).agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id
    GSHEETS_AVAILABLE = True
    st.info("Google Sheets API libraries loaded.")
except ImportError:
    GSHEETS_AVAILABLE = False
    st.warning(
        "Google Sheets API libraries not installed. Falling back to GitHub CSV.\n\n"
        "Add 'google-api-python-client>=2.0.0' and 'google-auth>=2.0.0' to requirements.txt to enable Google Sheets."
    )

# -------------------------------
# CONFIGURATION
# -------------------------------
st.set_page_config(
    page_title="Employee & Sales Task Tracker",
    page_icon="⏱️",
    layout="wide",
)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASKS_FILE = DATA_DIR / "tasks.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"
TIMEZONE = pytz.timezone('America/New_York')  # Adjust to your timezone
# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
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
# HELPERS
# -------------------------------
def load_csv(path: Path, columns: list) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path)
        for col in columns:
            if col not in df.columns:
                df[col] = None
        if "employee_id" in df.columns and df["employee_id"].duplicated().any():
            st.warning("Duplicate employee IDs detected. Please ensure unique IDs.")
        if "task_type_id" in df.columns and df["task_type_id"].duplicated().any():
            st.warning("Duplicate task type IDs detected. Please ensure unique IDs.")
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
# GOOGLE SHEETS HELPERS
# -------------------------------
@st.cache_resource
def connect_gsheet_api():
    if not GSHEETS_AVAILABLE:
        st.error("Google Sheets API libraries not installed. Using GitHub CSV.")
        return None
    try:
        creds_dict = st.secrets.get("gcp_service_account", {})
        if not creds_dict:
            st.error("Missing [gcp_service_account] in Streamlit secrets.")
            return None
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        st.error(f"Google Sheets API Connection Error: {e}")
        return None

def write_task_to_gsheet_api(task_data: dict):
    service = connect_gsheet_api()
    if not service:
        return False
    try:
        sheet_cfg = st.secrets.get("google_sheet", {})
        sheet_id = sheet_cfg.get("sheet_id", "1RVRUtL-y-F5e5KCqpdDQkN6voBIiGSvHjX_9fMNANqI")
        worksheet_name = sheet_cfg.get("worksheet_name", "Tasks")
        # Check if headers exist
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"{worksheet_name}!A1:Z1"
        ).execute()
        if not result.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{worksheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [TASK_COLUMNS]},
            ).execute()
        # Append task
        row = [str(task_data.get(col, "")) for col in TASK_COLUMNS]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{worksheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        st.success(f"Appended task to Google Sheet (Worksheet: {worksheet_name}).")
        return True
    except Exception as e:
        st.error(f"Failed to write to Google Sheet: {e}")
        return False

# -------------------------------
# GITHUB CSV HELPERS
# -------------------------------
def write_task_to_github(task_data: dict):
    try:
        github_cfg = st.secrets.get("github", {})
        token = github_cfg.get("token")
        repo = github_cfg.get("repo")
        branch = github_cfg.get("branch", "main")
        file_path = github_cfg.get("file_path", "data/tasks.csv")
        if not all([token, repo, file_path]):
            st.error("Missing GitHub configuration in Streamlit secrets (token, repo, file_path).")
            return False
        # Get current file content
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
        response = requests.get(url, headers=headers)
        df = pd.DataFrame(columns=TASK_COLUMNS)
        sha = None
        if response.status_code == 200:
            content_data = response.json()
            content = base64.b64decode(content_data["content"]).decode("utf-8")
            df = pd.read_csv(pd.StringIO(content))
            sha = content_data["sha"]
        else:
            if response.status_code != 404:
                st.error(f"GitHub GET error (status {response.status_code}): {response.json().get('message', 'Unknown error')}")
                return False
        # Append new task
        new_row = pd.DataFrame([task_data], columns=TASK_COLUMNS)
        df = pd.concat([df, new_row], ignore_index=True)
        # Encode updated content
        content = df.to_csv(index=False).encode("utf-8")
        encoded_content = base64.b64encode(content).decode("utf-8")
        # Update file
        data = {
            "message": f"Append task {task_data.get('task_id', 'unknown')} to {file_path}",
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            data["sha"] = sha
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            st.success(f"Appended task {task_data.get('task_id', 'unknown')} to GitHub CSV ({file_path}).")
            return True
        else:
            error_msg = response.json().get('message', 'Unknown error')
            st.error(f"GitHub PUT error (status {response.status_code}): {error_msg}")
            return False
    except Exception as e:
        st.error(f"GitHub CSV write error: {e}")
        return False

def write_task_to_storage(task_data: dict):
    success = False
    if GSHEETS_AVAILABLE:
        success = write_task_to_gsheet_api(task_data)
    if not success:
        success = write_task_to_github(task_data)
    if not success:
        st.error("Failed to write to both Google Sheets and GitHub CSV. Task saved locally.")

# -------------------------------
# DATA LOADERS (CACHED)
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

def refresh_employees_cache():
    get_employees.clear()

def refresh_task_types_cache():
    get_task_types.clear()

def refresh_tasks_cache():
    get_tasks.clear()

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
st.sidebar.title("⏱️ Task Tracker")
page = st.sidebar.radio(
    label="Go to",
    options=[
        "1️⃣ Task List",
        "2️⃣ Employee Tasks",
        "3️⃣ Admin",
    ],
    index=1,
    key="main_nav",
)

# -------------------------------
# PAGE 1: TASK LIST (LIBRARY)
# -------------------------------
if page == "1️⃣ Task List":
    st.title("Task Library")
    task_types = get_task_types()
    st.subheader("Add / Update Task Type")
    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input(
                "Task Name",
                placeholder="e.g., Sales – Schedule Site Survey",
            )
        with c2:
            category = st.text_input(
                "Category",
                placeholder="e.g., Sales, Construction, Admin",
            )
        task_type_id = st.text_input("Task ID (optional, auto if blank)").strip()
        submitted = st.form_submit_button("Save Task Type")
        if submitted:
            if not task_name:
                st.warning("Task name required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now(TIMEZONE).timestamp())}"
                mask = task_types["task_type_id"] == task_type_id
                new_row = {
                    "task_type_id": task_type_id,
                    "task_name": task_name,
                    "category": category or "General",
                }
                if mask.any():
                    task_types.loc[mask, :] = new_row
                    st.success(f"Updated {task_name}.")
                else:
                    task_types = pd.concat(
                        [task_types, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    st.success(f"Added {task_name}.")
                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()
    st.subheader("Existing Tasks")
    st.dataframe(get_task_types(), use_container_width=True)

# -------------------------------
# PAGE 2: EMPLOYEE TASKS
# -------------------------------
elif page == "2️⃣ Employee Tasks":
    st.title("Employee Tasks (Start/Finish Timer)")
    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()
    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None
    if employees.empty:
        st.warning("Add employees first under Admin → Employees.")
    elif task_types.empty:
        st.warning("Add task types first on the Task List page.")
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
            start_submitted = st.form_submit_button("▶️ Start Task")
            if start_submitted:
                if st.session_state["active_task_id"]:
                    st.error("A task is already running. Finish it first.")
                else:
                    emp = employees[employees["name"] == employee_name].iloc[0]
                    tt = task_types[task_types["task_name"] == task_choice].iloc[0]
                    start_time = datetime.now(TIMEZONE)
                    tid = f"T{int(start_time.timestamp())}"
                    new_task = {
                        "task_id": tid,
                        "date": start_time.date().isoformat(),
                        "employee_id": emp["employee_id"],
                        "employee_name": emp["name"],
                        "task_type_id": tt["task_type_id"],
                        "task_name": tt["task_name"],
                        "task_category": tt["category"],
                        "customer": customer or "",
                        "task_description": desc,
                        "start_time": start_time.isoformat(),
                        "end_time": None,
                        "duration_minutes": None,
                        "cost": None,
                    }
                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = tid
                    st.success(
                        f"Started '{tt['task_name']}' for {employee_name}"
                        + (f" (Customer: {customer})" if customer else "")
                        + f" at {start_time.strftime('%H:%M:%S')}"
                    )
        st.subheader("Active Task")
        active_id = st.session_state["active_task_id"]
        tasks = get_tasks()
        if not active_id:
            st.info("No active task running.")
        else:
            active = tasks[tasks["task_id"] == active_id]
            if active.empty:
                st.session_state["active_task_id"] = None
                st.warning("Active task not found, resetting.")
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
                if st.button("⏹️ Finish Task", key="finish_btn"):
                    end_dt = datetime.now(TIMEZONE)
                    emp = employees[employees["employee_id"] == row["employee_id"]].iloc[0]
                    minutes = (end_dt - start_dt).total_seconds() / 60
                    cost = round((minutes / 60) * float(emp["hourly_rate"]), 2)
                    tasks.loc[tasks["task_id"] == active_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_id, "duration_minutes"] = minutes
                    tasks.loc[tasks["task_id"] == active_id, "cost"] = cost
                    completed_task_row = tasks[tasks["task_id"] == active_id].iloc[0]
                    write_task_to_storage(completed_task_row.to_dict())
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = None
                    st.success(
                        f"Task finished. Duration {minutes:.1f} minutes. "
                        "Logged to local CSV and Google Sheet/GitHub (if configured)."
                    )
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
elif page == "3️⃣ Admin":
    st.title("Admin Area")
    admin_users = st.secrets.get("admin_users", None)
    if admin_users is None:
        st.error(
            "Admin users not configured in secrets.\n\n"
            "In Streamlit Cloud, go to 'Edit secrets' and add:\n\n"
            "[admin_users]\n"
            "brian = \"yourPasswordHere\""
        )
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
                        st.error("Invalid username or password.")
        else:
            st.success(f"Admin access granted ({st.session_state['admin_username']}).")
            if st.button("Logout", key="admin_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_username"] = None
                st.rerun()
            st.subheader("Storage Status")
            if st.button("🔍 Test Google Sheets Connection"):
                service = connect_gsheet_api()
                if service:
                    sheet_cfg = st.secrets.get("google_sheet", {})
                    sheet_id = sheet_cfg.get("sheet_id", "1RVRUtL-y-F5e5KCqpdDQkN6voBIiGSvHjX_9fMNANqI")
                    worksheet_name = sheet_cfg.get("worksheet_name", "Tasks")
                    try:
                        result = service.spreadsheets().values().get(
                            spreadsheetId=sheet_id, range=f"{worksheet_name}!A1:Z1"
                        ).execute()
                        row_count = len(service.spreadsheets().values().get(
                            spreadsheetId=sheet_id, range=worksheet_name
                        ).execute().get("values", []))
                        st.success(f"Connected! Sheet ID: {sheet_id}, Worksheet: {worksheet_name}, Rows: {row_count}")
                    except Exception as e:
                        st.error(f"Test failed: {e}")
                else:
                    st.error("Google Sheets connection failed. Check secrets or library installation.")
            if st.button("🔍 Test GitHub Connection"):
                github_cfg = st.secrets.get("github", {})
                token = github_cfg.get("token")
                repo = github_cfg.get("repo")
                branch = github_cfg.get("branch", "main")
                file_path = github_cfg.get("file_path", "data/tasks.csv")
                if not all([token, repo, file_path]):
                    st.error("Missing GitHub configuration in secrets.")
                else:
                    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                    url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={branch}"
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        st.success(f"Connected to GitHub repo {repo}, file {file_path} (rows: {len(pd.read_csv(pd.StringIO(base64.b64decode(response.json()['content']).decode('utf-8'))))} estimated).")
                    else:
                        st.error(f"GitHub connection failed (status {response.status_code}): {response.json().get('message', 'Unknown error')}")
            # NEW: Debug buttons for GitHub
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔧 Debug Pending Tasks"):
                    pending = st.session_state.get("pending_tasks", [])
                    st.write(f"Pending tasks: {len(pending)}")
                    if pending:
                        st.json(pending[-1])  # Show last pending task
            with col2:
                if st.button("💾 Force Flush to GitHub"):
                    pending = st.session_state.get("pending_tasks", [])
                    if pending:
                        success = write_task_to_github(pending[-1])  # Flush last one for test
                        if success:
                            st.session_state.pending_tasks = []
                        st.rerun()
                    else:
                        st.info("No pending tasks to flush.")
            if st.session_state["admin_authenticated"]:
                section = st.radio(
                    "Admin Section",
                    ["Employees", "Reports"],
                    key="admin_section_radio",
                )
                if section == "Employees":
                    st.header("Manage Employees")
                    employees = get_employees()
                    st.subheader("Add / Update Employee")
                    with st.form("admin_employee_form", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            name = st.text_input("Name")
                            role = st.text_input("Role", value="Technician")
                        with col2:
                            hourly_rate = st.number_input(
                                "Hourly Rate ($/hour)", min_value=0.0, step=0.5, value=25.0
                            )
                            employee_id = st.text_input(
                                "Employee ID (optional, auto if blank)"
                            ).strip()
                        submitted = st.form_submit_button("Save Employee")
                        if submitted:
                            if not name:
                                st.warning("Name is required.")
                            else:
                                if not employee_id:
                                    employee_id = f"E{int(datetime.now(TIMEZONE).timestamp())}"
                                mask = employees["employee_id"] == employee_id
                                new_row = {
                                    "employee_id": employee_id,
                                    "name": name,
                                    "role": role,
                                    "hourly_rate": hourly_rate,
                                }
                                if mask.any():
                                    employees.loc[mask, :] = new_row
                                    st.success(f"Updated employee {name}.")
                                else:
                                    employees = pd.concat(
                                        [employees, pd.DataFrame([new_row])],
                                        ignore_index=True,
                                    )
                                    st.success(f"Added employee {name}.")
                                save_csv(employees, EMPLOYEE_FILE)
                                refresh_employees_cache()
                    st.subheader("Edit Existing Employee")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees to edit.")
                    else:
                        emp_names = employees["name"].tolist()
                        selected_name = st.selectbox(
                            "Select Employee to Edit",
                            options=emp_names,
                            key="edit_emp_select",
                        )
                        emp_row = employees[employees["name"] == selected_name].iloc[0]
                        current_rate = float(emp_row["hourly_rate"])
                        current_role = emp_row["role"]
                        emp_id = emp_row["employee_id"]
                        with st.form("edit_employee_form"):
                            new_name = st.text_input(
                                "Name",
                                value=selected_name,
                                key=f"edit_name_input_{emp_id}",
                            )
                            new_role = st.text_input(
                                "Role",
                                value=current_role,
                                key=f"edit_role_input_{emp_id}",
                            )
                            new_rate = st.number_input(
                                "New Hourly Rate ($/hour)",
                                min_value=0.0,
                                step=0.5,
                                value=current_rate,
                                key=f"edit_rate_input_{emp_id}",
                            )
                            update = st.form_submit_button("Update Employee")
                            if update:
                                employees.loc[
                                    employees["employee_id"] == emp_row["employee_id"],
                                    ["name", "role", "hourly_rate"],
                                ] = [new_name, new_role, new_rate]
                                save_csv(employees, EMPLOYEE_FILE)
                                refresh_employees_cache()
                                st.success(
                                    f"Updated employee: '{selected_name}' → '{new_name}', "
                                    f"role='{new_role}', hourly rate=${new_rate:.2f}"
                                )
                    st.subheader("Current Employees")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees yet.")
                    else:
                        st.dataframe(employees, use_container_width=True)
                elif section == "Reports":
                    st.header("Reports (with Cost)")
                    tasks = get_tasks()
                    if tasks.empty:
                        st.info("No tasks logged yet.")
                    else:
                        df = tasks.copy()
                        df["date"] = pd.to_datetime(df["date"], errors="coerce")
                        if "customer" not in df.columns:
                            df["customer"] = ""
                        df_done = df[df["duration_minutes"].notna()]
                        if df_done.empty:
                            st.info("No completed tasks yet.")
                        else:
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                start_date = st.date_input(
                                    "Start date",
                                    value=df_done["date"].min().date(),
                                )
                            with c2:
                                end_date = st.date_input(
                                    "End date",
                                    value=df_done["date"].max().date(),
                                )
                            with c3:
                                customer_filter = st.text_input(
                                    "Filter by customer (contains)",
                                    placeholder="leave blank for all",
                                )
                            mask = (df_done["date"] >= pd.to_datetime(start_date)) & (
                                df_done["date"] <= pd.to_datetime(end_date)
                            )
                            if customer_filter:
                                mask &= df_done["customer"].fillna("").str.contains(
                                    customer_filter, case=False, na=False
                                )
                            df_filtered = df_done[mask]
                            if df_filtered.empty:
                                st.warning("No tasks match the selected filters.")
                            else:
                                total_tasks = len(df_filtered)
                                total_minutes = df_filtered["duration_minutes"].fillna(0).sum()
                                total_hours = round(total_minutes / 60.0, 2)
                                total_cost = float(df_filtered["cost"].fillna(0).sum())
                                cust_series = (
                                    df_filtered["customer"]
                                    .fillna("")
                                    .astype(str)
                                    .str.strip()
                                )
                                unique_customers = cust_series.replace("", pd.NA).nunique()
                                k1, k2, k3, k4 = st.columns(4)
                                with k1:
                                    st.metric("Total Tasks", total_tasks)
                                with k2:
                                    st.metric("Total Hours", f"{total_hours:.2f}")
                                with k3:
                                    st.metric("Total Cost", f"${total_cost:,.2f}")
                                with k4:
                                    st.metric("Customers", unique_customers)
                                st.markdown("---")
                                st.subheader("Summary by Customer")
                                cust_df = df_filtered.copy()
                                cust_df["customer"] = cust_df["customer"].fillna("")
                                cust_df.loc[cust_df["customer"] == "", "customer"] = "Unspecified"
                                by_customer = cust_df.groupby("customer").agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(by_customer, use_container_width=True)
                                selected_customer = st.selectbox(
                                    "View KPIs for a single customer",
                                    options=["All"] + sorted(by_customer["customer"].tolist()),
                                    index=0,
                                    key="customer_kpi_select",
                                )
                                if selected_customer != "All":
                                    row = by_customer[
                                        by_customer["customer"] == selected_customer
                                    ].iloc[0]
                                    kc1, kc2, kc3 = st.columns(3)
                                    with kc1:
                                        st.metric("Customer", selected_customer)
                                    with kc2:
                                        st.metric("Total Hours", f"{row['total_hours']:.2f}")
                                    with kc3:
                                        st.metric("Total Cost", f"${row['total_cost']:.2f}")
                                st.markdown("---")
                                st.subheader("Summary by Employee")
                                emp = df_filtered.groupby("employee_name").agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(emp, use_container_width=True)
                                st.subheader("Summary by Task")
                                t = df_filtered.groupby(
                                    ["task_name", "task_category"]
                                ).agg(
                                    total_hours=(
                                        "duration_minutes",
                                        lambda x: round(x.sum() / 60, 2),
                                    ),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(t, use_container_width=True)
                                st.subheader("Raw Task Data (Admin Only – Edit or Delete)")
                                edit_df = df_filtered.copy()
                                if "delete" not in edit_df.columns:
                                    edit_df["delete"] = False
                                else:
                                    edit_df["delete"] = edit_df["delete"].fillna(False)
                                hidden_cols = ["task_id", "employee_id", "task_type_id"]
                                all_cols = edit_df.columns.tolist()
                                visible_cols = ["delete"] + [
                                    c for c in all_cols if c not in hidden_cols + ["delete"]
                                ]
                                editable_cols = [
                                    "date",
                                    "employee_name",
                                    "task_name",
                                    "task_category",
                                    "customer",
                                    "task_description",
                                    "start_time",
                                    "end_time",
                                    "duration_minutes",
                                    "delete",
                                ]
                                edited_df = st.data_editor(
                                    edit_df[visible_cols],
                                    use_container_width=True,
                                    num_rows="fixed",
                                    disabled=[
                                        c for c in visible_cols if c not in editable_cols
                                    ],
                                    key="raw_task_editor",
                                )
                                if st.button("💾 Save Task Changes", key="save_task_changes"):
                                    employees_all = get_employees()
                                    delete_indices = []
                                    for orig_idx, (_, row) in zip(
                                        df_filtered.index, edited_df.iterrows()
                                    ):
                                        if bool(row.get("delete", False)):
                                            delete_indices.append(orig_idx)
                                            continue
                                        for col in editable_cols:
                                            if col == "delete":
                                                continue
                                            if col in df.columns and col in edited_df.columns:
                                                df.loc[orig_idx, col] = row[col]
                                        try:
                                            duration = row.get("duration_minutes", None)
                                            if pd.notna(duration):
                                                emp_name = row.get("employee_name", None)
                                                emp_row = employees_all[
                                                    employees_all["name"] == emp_name
                                                ]
                                                if not emp_row.empty:
                                                    rate = float(emp_row.iloc[0]["hourly_rate"])
                                                    hours = float(duration) / 60.0
                                                    df.loc[orig_idx, "cost"] = round(
                                                        hours * rate, 2
                                                    )
                                        except Exception:
                                            pass
                                    if delete_indices:
                                        df = df.drop(index=delete_indices)
                                    save_csv(df[TASK_COLUMNS], TASKS_FILE)
                                    refresh_tasks_cache()
                                    msg = "Changes saved locally."
                                    if delete_indices:
                                        msg += f" Deleted {len(delete_indices)} task(s)."
                                    st.success(msg)
                                    st.warning(
                                        "Note: Edits/Deletions here do not affect Google Sheets or GitHub, "
                                        "which are append-only."
                                    )
                                    st.rerun()
