import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import gspread  # <-- NEW
from google.oauth2.service_account import Credentials  # <-- NEW

# -------------------------------
# CONFIGURATION
# -------------------------------
st.set_page_config(
    page_title="Employee & Sales Task Tracker",
    page_icon="⏱️",
    layout="wide"
)

# --- NEW GSPREAD CONNECTION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1RVRUtL-y-F5e5KCqpdDQkN6voBIiGSvHjX_9fMNANqI/edit?usp=sharing"

@st.cache_resource
def get_gspread_client():
    """Create and cache the gspread client."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcs"],  # Assumes your secrets are under [gcs] key
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ],
    )
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=10)
def get_worksheet(worksheet_name: str) -> gspread.Worksheet:
    """Get a specific worksheet from the Google Sheet."""
    client = get_gspread_client()
    try:
        spreadsheet = client.open_by_url(SHEET_URL)
        worksheet = spreadsheet.worksheet(worksheet_name)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        # If worksheet doesn't exist, create it with headers
        spreadsheet = client.open_by_url(SHEET_URL)
        if worksheet_name == "Tasks":
            headers = TASK_COLUMNS
        elif worksheet_name == "Employees":
            headers = EMPLOYEE_COLUMNS
        elif worksheet_name == "Task Types":
            headers = TASK_TYPE_COLUMNS
        else:
            headers = []
        
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1, cols=len(headers))
        if headers:
            worksheet.update([headers]) # Set headers in the first row
        return worksheet
# ------------------------------------

# Note: DATA_DIR and file paths are no longer used for primary storage
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"


# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
TASK_COLUMNS = [
    "task_id", "date", "employee_id", "employee_name",
    "task_type_id", "task_name", "task_category",
    "customer",
    "task_description", "start_time", "end_time",
    "duration_minutes", "cost"
]

# -------------------------------
# HELPERS
# -------------------------------
def gsheet_to_dataframe(worksheet: gspread.Worksheet, columns: list) -> pd.DataFrame:
    """Read a worksheet into a DataFrame and ensure schema."""
    try:
        records = worksheet.get_all_records()
        df = pd.DataFrame.from_records(records)
    except Exception:
        return pd.DataFrame(columns=columns)
    
    if df.empty:
        return pd.DataFrame(columns=columns)

    # Ensure all columns from CONSTANTS exist
    for col in columns:
        if col not in df.columns:
            df[col] = None
    
    df = df[columns] # Enforce column order
    return df

def dataframe_to_gsheet(df: pd.DataFrame, worksheet: gspread.Worksheet):
    """Saves a DataFrame to a worksheet, overwriting all data."""
    # gspread needs NaNs, Nones, etc. to be empty strings
    df_clean = df.fillna("")
    
    # Convert datetimes back to iso strings for GSheets
    for col in ['date', 'start_time', 'end_time']:
        if col in df_clean.columns:
            # Coerce to datetime, convert to iso, replace NaT with ""
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').astype(str).replace("NaT", "").replace("None", "")

    # Get all column headers
    headers = df_clean.columns.tolist()
    # Get all values as a list of lists
    values = df_clean.values.tolist()
    
    worksheet.clear()
    worksheet.update([headers] + values, value_input_option='USER_ENTERED')

def create_default_task_types() -> pd.DataFrame:
    """Default tasks including the sales pipeline steps."""
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
# DATA LOADERS (CACHED)
# -------------------------------
@st.cache_data(ttl=5)
def get_employees():
    ws = get_worksheet("Employees")
    df = gsheet_to_dataframe(ws, EMPLOYEE_COLUMNS)
    df['hourly_rate'] = pd.to_numeric(df['hourly_rate'], errors='coerce')
    return df

@st.cache_data(ttl=5)
def get_task_types():
    ws = get_worksheet("Task Types")
    df = gsheet_to_dataframe(ws, TASK_TYPE_COLUMNS)
    if df.empty:
        df = create_default_task_types()
        dataframe_to_gsheet(df, ws) # Save defaults
    return df

@st.cache_data(ttl=5)
def get_tasks():
    ws = get_worksheet("Tasks")
    df = gsheet_to_dataframe(ws, TASK_COLUMNS)
    
    # Coerce types (GSheets reads all as objects)
    df['duration_minutes'] = pd.to_numeric(df['duration_minutes'], errors='coerce')
    df['cost'] = pd.to_numeric(df['cost'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

# --- NEW SAVE FUNCTIONS ---
def save_employees(df: pd.DataFrame):
    ws = get_worksheet("Employees")
    dataframe_to_gsheet(df, ws)
    refresh_employees_cache()

def save_task_types(df: pd.DataFrame):
    ws = get_worksheet("Task Types")
    dataframe_to_gsheet(df, ws)
    refresh_task_types_cache()

def save_tasks(df: pd.DataFrame):
    ws = get_worksheet("Tasks")
    dataframe_to_gsheet(df, ws)
    refresh_tasks_cache()
# --------------------------

def refresh_employees_cache():
    get_employees.clear()
    get_worksheet.clear()

def refresh_task_types_cache():
    get_task_types.clear()
    get_worksheet.clear()

def refresh_tasks_cache():
    get_tasks.clear()
    get_worksheet.clear()


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
    index=1,  # 0 = Task List, 1 = Employee Tasks, 2 = Admin
    key="main_nav"
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
                placeholder="e.g., Sales – Schedule Site Survey"
            )
        with c2:
            category = st.text_input(
                "Category",
                placeholder="e.g., Sales, Construction, Admin"
            )
        task_type_id = st.text_input("Task ID (optional, auto if blank)").strip()
        submitted = st.form_submit_button("Save Task Type")

        if submitted:
            if not task_name:
                st.warning("Task name required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now().timestamp())}"
                
                # Get fresh data for modification
                task_types_df = get_task_types()
                
                mask = task_types_df["task_type_id"] == task_type_id
                new_row = {
                    "task_type_id": task_type_id,
                    "task_name": task_name,
                    "category": category or "General",
                }
                if mask.any():
                    task_types_df.loc[mask, new_row.keys()] = new_row.values()
                    st.success(f"Updated {task_name}.")
                else:
                    task_types_df = pd.concat(
                        [task_types_df, pd.DataFrame([new_row])],
                        ignore_index=True
                    )
                    st.success(f"Added {task_name}.")
                
                save_task_types(task_types_df) # <-- MODIFIED


    st.subheader("Existing Tasks")
    st.dataframe(get_task_types(), use_container_width=True)


# -------------------------------
# PAGE 2: EMPLOYEE TASKS (TIMER, NO COST)
# -------------------------------
elif page == "2️⃣ Employee Tasks":
    st.title("Employee Tasks (Start/Finish Timer)")

    employees = get_employees()
    task_types = get_task_types()
    
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
                    start_time = datetime.now()
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
                    
                    # Get fresh data, append, and save
                    tasks = get_tasks()
                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_tasks(tasks) # <-- MODIFIED
                    
                    st.session_state["active_task_id"] = tid
                    st.success(
                        f"Started '{tt['task_name']}' for {employee_name}"
                        + (f" (Customer: {customer})" if customer else "")
                        + f" at {start_time.strftime('%H:%M:%S')}"
                    )
                    # No rerun, just let it flow to active panel

        # Active Task Panel
        st.subheader("Active Task")
        active_id = st.session_state["active_task_id"]
        
        if not active_id:
            st.info("No active task running.")
        else:
            tasks = get_tasks() # Get fresh data
            active = tasks[tasks["task_id"] == active_id]
            
            if active.empty:
                st.session_state["active_task_id"] = None
                st.warning("Active task not found, resetting.")
            else:
                row = active.iloc[0]
                
                # Handle potential string read from GSheet
                start_time_str = str(row["start_time"])
                if '.' in start_time_str:
                    start_dt = datetime.fromisoformat(start_time_str.split('.')[0])
                elif start_time_str != "None":
                    try:
                        start_dt = datetime.fromisoformat(start_time_str)
                    except ValueError:
                         st.error(f"Could not parse start time: {start_time_str}")
                         st.session_state["active_task_id"] = None
                         st.rerun()

                
                if start_time_str != "None":
                    elapsed = datetime.now() - start_dt
                    elapsed_str = str(elapsed).split(".")[0]

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**Employee:** {row['employee_name']}")
                        st.write(f"**Task:** {row['task_name']}")
                        st.write(f"**Category:** {row['task_category']}")
                    with c2:
                        st.write(f"**Started:** {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        st.write(f"**Elapsed:** {elapsed_str}")
                        if row.get("customer"):
                            st.write(f"**Customer:** {row['customer']}")
                    with c3:
                        st.write("**Notes:**")
                        st.write(row["task_description"])

                    if st.button("⏹️ Finish Task", key="finish_btn"):
                        end_dt = datetime.now()
                        emp = employees[employees["employee_id"] == row["employee_id"]].iloc[0]
                        minutes = (end_dt - start_dt).total_seconds() / 60
                        cost = round((minutes / 60) * float(emp["hourly_rate"]), 2)

                        tasks.loc[tasks["task_id"] == active_id, "end_time"] = end_dt.isoformat()
                        tasks.loc[tasks["task_id"] == active_id, "duration_minutes"] = minutes
                        tasks.loc[tasks["task_id"] == active_id, "cost"] = cost
                        
                        save_tasks(tasks) # <-- MODIFIED
                        
                        st.session_state["active_task_id"] = None
                        st.success(f"Task finished. Duration {minutes:.1f} minutes.")
                        st.rerun() # Rerun to clear active panel

        # Task Log (cost hidden, but customer shown)
        st.subheader("Task Log")
        df = get_tasks()
        if df.empty:
            st.info("No tasks logged yet.")
        else:
            cols = [c for c in df.columns if c != "cost"]
            # Ensure date is datetime for sorting
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            st.dataframe(df[cols].sort_values("date", ascending=False), use_container_width=True)


# -------------------------------
# PAGE 3: ADMIN (USERNAME + PASSWORD)
# -------------------------------
elif page == "3️⃣ Admin":
    st.title("Admin Area")

    admin_users = st.secrets.get("admin_users", None)

    if admin_users is None:
        st.error(
            "Admin users not configured in secrets.\n\n"
            "In Streamlit Cloud, go to 'Edit secrets' and add:\n\n"
            "[admin_users]\n"
            'brian = "yourPasswordHere"'
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
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
        else:
            st.success(f"Admin access granted ({st.session_state['admin_username']}).")
            if st.button("Logout", key="admin_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_username"] = None
                st.rerun()

            if st.session_state["admin_authenticated"]:
                section = st.radio(
                    "Admin Section",
                    ["Employees", "Reports"],
                    key="admin_section_radio"
                )

                # ----- ADMIN: EMPLOYEES -----
                if section == "Employees":
                    st.header("Manage Employees")

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
                                    employee_id = f"E{int(datetime.now().timestamp())}"
                                
                                employees = get_employees() # Get fresh data
                                
                                mask = employees["employee_id"] == employee_id
                                new_row = {
                                    "employee_id": employee_id,
                                    "name": name,
                                    "role": role,
                                    "hourly_rate": hourly_rate,
                                }
                                if mask.any():
                                    employees.loc[mask, new_row.keys()] = new_row.values()
                                    st.success(f"Updated employee {name}.")
                                else:
                                    employees = pd.concat(
                                        [employees, pd.DataFrame([new_row])],
                                        ignore_index=True
                                    )
                                    st.success(f"Added employee {name}.")
                                
                                save_employees(employees) # <-- MODIFIED

                    st.subheader("Edit Existing Employee")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees to edit.")
                    else:
                        emp_names = employees["name"].tolist()
                        selected_name = st.selectbox(
                            "Select Employee to Edit",
                            options=emp_names,
                            key="edit_emp_select"
                        )
                        
                        if selected_name:
                            emp_row = employees[employees["name"] == selected_name].iloc[0]
                            current_rate = float(emp_row["hourly_rate"])
                            current_role = emp_row["role"]
                            emp_id = emp_row["employee_id"]

                            with st.form("edit_employee_form"):
                                new_name = st.text_input(
                                    "Name",
                                    value=selected_name,
                                    key=f"edit_name_input_{emp_id}"
                                )
                                new_role = st.text_input(
                                    "Role",
                                    value=current_role,
                                    key=f"edit_role_input_{emp_id}"
                                )
                                new_rate = st.number_input(
                                    "New Hourly Rate ($/hour)",
                                    min_value=0.0,
                                    step=0.5,
                                    value=current_rate,
                                    key=f"edit_rate_input_{emp_id}"
                                )
                                update = st.form_submit_button("Update Employee")

                                if update:
                                    employees.loc[
                                        employees["employee_id"] == emp_row["employee_id"],
                                        ["name", "role", "hourly_rate"]
                                    ] = [new_name, new_role, new_rate]
                                    
                                    save_employees(employees) # <-- MODIFIED
                                    
                                    st.success(
                                        f"Updated employee: '{selected_name}' → '{new_name}', "
                                        f"role='{new_role}', hourly rate=${new_rate:.2f}"
                                    )
                                    st.rerun()

                    st.subheader("Current Employees")
                    employees = get_employees()
                    if employees.empty:
                        st.info("No employees yet.")
                    else:
                        st.dataframe(employees, use_container_width=True)

                # ----- ADMIN: REPORTS (WITH COST + CUSTOMER KPI + EDIT/DELETE) -----
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
                            # Filters
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                min_date = df_done["date"].min()
                                start_date = st.date_input(
                                    "Start date",
                                    value=min_date.date() if pd.notna(min_date) else datetime.now().date()
                                )
                            with c2:
                                max_date = df_done["date"].max()
                                end_date = st.date_input(
                                    "End date",
                                    value=max_date.date() if pd.notna(max_date) else datetime.now().date()
                                )
                            with c3:
                                customer_filter = st.text_input(
                                    "Filter by customer (contains)",
                                    placeholder="leave blank for all"
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
                                # -------- TOP-LEVEL KPIs (FILTERED) --------
                                total_tasks = len(df_filtered)
                                total_minutes = df_filtered["duration_minutes"].fillna(0).sum()
                                total_hours = round(total_minutes / 60.0, 2)
                                total_cost = float(df_filtered["cost"].fillna(0).sum())
                                cust_series = df_filtered["customer"].fillna("").astype(str).str.strip()
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

                                # -------- Summary by Customer --------
                                st.subheader("Summary by Customer")

                                cust_df = df_filtered.copy()
                                cust_df["customer"] = cust_df["customer"].fillna("")
                                cust_df.loc[cust_df["customer"] == "", "customer"] = "Unspecified"

                                by_customer = cust_df.groupby("customer").agg(
                                    total_hours=("duration_minutes", lambda x: round(x.sum() / 60, 2)),
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
                                    row = by_customer[by_customer["customer"] == selected_customer].iloc[0]
                                    k1c, k2c, k3c = st.columns(3)
                                    with k1c:
                                        st.metric("Customer", selected_customer)
                                    with k2c:
                                        st.metric("Total Hours", f"{row['total_hours']:.2f}")
                                    with k3c:
                                        st.metric("Total Cost", f"${row['total_cost']:.2f}")

                                st.markdown("---")

                                # -------- Summary by Employee --------
                                st.subheader("Summary by Employee")
                                emp = df_filtered.groupby("employee_name").agg(
                                    total_hours=("duration_minutes", lambda x: round(x.sum() / 60, 2)),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(emp, use_container_width=True)

                                # -------- Summary by Task --------
                                st.subheader("Summary by Task")
                                t = df_filtered.groupby(["task_name", "task_category"]).agg(
                                    total_hours=("duration_minutes", lambda x: round(x.sum() / 60, 2)),
                                    total_cost=("cost", "sum"),
                                    tasks=("task_id", "count"),
                                ).reset_index()
                                st.dataframe(t, use_container_width=True)

                                # -------- Editable Raw Data (with Delete) --------
                                st.subheader("Raw Task Data (Admin Only – Edit or Delete)")

                                edit_df = df_filtered.copy()

                                if "delete" not in edit_df.columns:
                                    edit_df["delete"] = False
                                else:
                                    edit_df["delete"] = edit_df["delete"].fillna(False).astype(bool)
                                
                                # Convert date for data_editor
                                edit_df['date'] = pd.to_datetime(edit_df['date']).dt.date


                                hidden_cols = ["task_id", "employee_id", "task_type_id"]
                                all_cols = edit_df.columns.tolist()
                                visible_cols = ["delete"] + [
                                    c for c in all_cols if c not in hidden_cols + ["delete"]
                                ]

                                editable_cols = [
                                    "date", "employee_name", "task_name", "task_category",
                                    "customer", "task_description", "start_time", "end_time",
                                    "duration_minutes", "delete"
                                ]

                                edited_df = st.data_editor(
                                    edit_df[visible_cols],
                                    use_container_width=True,
                                    num_rows="fixed",
                                    disabled=[
                                        c for c in visible_cols if c not in editable_cols
                                    ],
                                    key="raw_task_editor",
                                    column_config={"date": st.column_config.DateColumn()}
                                )

                                if st.button("💾 Save Task Changes", key="save_task_changes"):
                                    employees_all = get_employees()
                                    
                                    # Get the full, fresh tasks dataframe from GSheets
                                    all_tasks_df = get_tasks()
                                    
                                    delete_ids = []
                                    updates = 0

                                    # Iterate over the edited dataframe
                                    for _, row in edited_df.iterrows():
                                        task_id_to_find = row['task_id']
                                        
                                        if bool(row.get("delete", False)):
                                            delete_ids.append(task_id_to_find)
                                            continue

                                        # Find the row in the *full* dataframe
                                        mask = all_tasks_df["task_id"] == task_id_to_find
                                        if mask.any():
                                            updates += 1
                                            # Update editable fields
                                            for col in editable_cols:
                                                if col == "delete":
                                                    continue
                                                if col in all_tasks_df.columns:
                                                    all_tasks_df.loc[mask, col] = row[col]

                                            # Recalculate cost
                                            try:
                                                duration = row.get("duration_minutes", None)
                                                if pd.notna(duration):
                                                    emp_name = row.get("employee_name", None)
                                                    emp_row = employees_all[employees_all["name"] == emp_name]
                                                    if not emp_row.empty:
                                                        rate = float(emp_row.iloc[0]["hourly_rate"])
                                                        hours = float(duration) / 60.0
                                                        all_tasks_df.loc[mask, "cost"] = round(hours * rate, 2)
                                            except Exception:
                                                pass # cost recalc failed, leave as is

                                    # After iterating, drop all rows marked for deletion
                                    if delete_ids:
                                        all_tasks_df = all_tasks_df[~all_tasks_df["task_id"].isin(delete_ids)]

                                    # Save the modified *full* dataframe back to GSheets
                                    save_tasks(all_tasks_df) # <-- MODIFIED

                                    msg = f"Changes saved. {updates} task(s) updated."
                                    if delete_ids:
                                        msg += f" {len(delete_ids)} task(s) deleted."
                                    st.success(msg)
                                    st.rerun()
