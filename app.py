import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date, time

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(
    page_title="Employee & Sales Task Tracker",
    page_icon="⏱️",
    layout="wide"
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

EMPLOYEE_FILE = DATA_DIR / "employees.csv"
TASKS_FILE = DATA_DIR / "tasks.csv"
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"  # Task library


# -------------------------------
# COLUMNS / CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]

TASK_TYPE_COLUMNS = [
    "task_type_id",
    "task_name",
    "category",
]

TASK_COLUMNS = [
    "task_id",
    "date",
    "employee_id",
    "employee_name",
    "task_type_id",
    "task_name",
    "task_category",
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
        # Ensure all expected columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = None
        return df[columns]
    else:
        return pd.DataFrame(columns=columns)


def save_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)


def combine_date_time(d: date, t: time) -> datetime:
    return datetime(
        year=d.year,
        month=d.month,
        day=d.day,
        hour=t.hour,
        minute=t.minute,
        second=t.second,
    )


def create_default_task_types() -> pd.DataFrame:
    """Default tasks including the sales pipeline steps."""
    defaults = [
        # Sales pipeline
        {"task_type_id": "TT_SALES_1", "task_name": "Sales – First Contact Reply", "category": "Sales"},
        {"task_type_id": "TT_SALES_2", "task_name": "Sales – Schedule Site Survey", "category": "Sales"},
        {"task_type_id": "TT_SALES_3", "task_name": "Sales – Record Site Survey Results", "category": "Sales"},
        {"task_type_id": "TT_SALES_4", "task_name": "Sales – Schedule Prep", "category": "Sales"},
        {"task_type_id": "TT_SALES_5", "task_name": "Sales – Schedule Install", "category": "Sales"},
        # Generic ops examples (you can delete or rename in the UI)
        {"task_type_id": "TT_OPS_1", "task_name": "Construction – Pull Fiber", "category": "Construction"},
        {"task_type_id": "TT_OPS_2", "task_name": "Construction – Lash Fiber", "category": "Construction"},
    ]
    return pd.DataFrame(defaults, columns=TASK_TYPE_COLUMNS)


# -------------------------------
# DATA LOADERS (CACHED)
# -------------------------------
@st.cache_data
def get_employees():
    return load_csv(EMPLOYEE_FILE, EMPLOYEE_COLUMNS)


@st.cache_data
def get_task_types():
    if TASK_TYPES_FILE.exists():
        df = load_csv(TASK_TYPES_FILE, TASK_TYPE_COLUMNS)
        if df.empty:
            df = create_default_task_types()
            save_csv(df, TASK_TYPES_FILE)
        return df
    else:
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
# SIDEBAR NAV
# -------------------------------
st.sidebar.title("⏱️ Task Tracker")
page = st.sidebar.radio(
    "Go to",
    [
        "1️⃣ Employees",
        "2️⃣ Task List",
        "3️⃣ Employee Tasks",
        "4️⃣ Reports",
    ]
)


# -------------------------------
# PAGE 1: EMPLOYEES
# -------------------------------
if page == "1️⃣ Employees":
    st.title("Employees")

    employees = get_employees()

    st.subheader("Add / Update Employee")

    with st.form("employee_form", clear_on_submit=True):
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
                st.warning("Name is required.")
            else:
                if not employee_id:
                    # Auto-generate a simple ID
                    employee_id = f"E{int(datetime.now().timestamp())}"

                # Check if employee exists -> update
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
                    employees = pd.concat([employees, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added employee {name}.")

                save_csv(employees, EMPLOYEE_FILE)
                refresh_employees_cache()

    st.subheader("Current Employees")
    if employees.empty:
        st.info("No employees yet. Add one above.")
    else:
        st.dataframe(employees, use_container_width=True)


# -------------------------------
# PAGE 2: TASK LIST (LIBRARY)
# -------------------------------
elif page == "2️⃣ Task List":
    st.title("Task List (Task Library)")

    task_types = get_task_types()

    st.subheader("Add / Update Task Type")

    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input(
                "Task Name (what the employee selects)",
                placeholder="e.g., Sales – First Contact Reply"
            )
        with c2:
            category = st.text_input(
                "Category",
                placeholder="e.g., Sales, Construction, Admin"
            )

        task_type_id = st.text_input(
            "Task Type ID (optional, auto if blank)",
            help="Internal ID; leave blank and it will be auto-generated.",
        ).strip()

        submitted = st.form_submit_button("Save Task Type")

        if submitted:
            if not task_name:
                st.warning("Task Name is required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now().timestamp())}"

                mask = task_types["task_type_id"] == task_type_id
                new_row = {
                    "task_type_id": task_type_id,
                    "task_name": task_name,
                    "category": category or "General",
                }

                if mask.any():
                    task_types.loc[mask, :] = new_row
                    st.success(f"Updated task type {task_name}.")
                else:
                    task_types = pd.concat([task_types, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added task type {task_name}.")

                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()

    st.subheader("Existing Task Types")
    task_types = get_task_types()

    if task_types.empty:
        st.info("No task types yet. Add some above.")
    else:
        st.dataframe(task_types, use_container_width=True)
        st.caption(
            "Tip: Add your sales pipeline steps here so they appear in the Task dropdown on the Employee Tasks page."
        )


# -------------------------------
# PAGE 3: EMPLOYEE TASKS (TIMER + DROPDOWN)
# -------------------------------
elif page == "3️⃣ Employee Tasks":
    st.title("Employee Tasks (Timer)")

    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()

    # Track active task in this browser session
    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None

    if employees.empty:
        st.warning("You need to add employees first on the 'Employees' page.")
    elif task_types.empty:
        st.warning("You need to add task types first on the 'Task List' page.")
    else:
        st.subheader("Start a Task")

        with st.form("start_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)

            with c1:
                employee_name = st.selectbox(
                    "Employee",
                    options=employees["name"].tolist()
                )

                task_choice = st.selectbox(
                    "Task (from list)",
                    options=task_types["task_name"].tolist(),
                    help="Includes your sales pipeline steps and any other tasks you've added.",
                )

            with c2:
                task_description = st.text_area(
                    "Optional Notes / Description",
                    height=100,
                    placeholder="Extra details about this specific task instance..."
                )

            start_submitted = st.form_submit_button("▶️ Start Task")

            if start_submitted:
                if st.session_state["active_task_id"] is not None:
                    st.error("A task is already running in this session. Finish it before starting a new one.")
                else:
                    employee_row = employees[employees["name"] == employee_name].iloc[0]
                    employee_id = employee_row["employee_id"]

                    task_type_row = task_types[task_types["task_name"] == task_choice].iloc[0]
                    task_type_id = task_type_row["task_type_id"]
                    task_category = task_type_row["category"]

                    start_dt = datetime.now()
                    task_id = f"T{int(start_dt.timestamp())}"

                    new_task = {
                        "task_id": task_id,
                        "date": start_dt.date().isoformat(),
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "task_type_id": task_type_id,
                        "task_name": task_choice,
                        "task_category": task_category,
                        "task_description": task_description,
                        "start_time": start_dt.isoformat(),
                        "end_time": None,
                        "duration_minutes": None,
                        "cost": None,
                    }

                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = task_id
                    st.success(
                        f"Started task '{task_choice}' for {employee_name} at "
                        f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                    )

        # ----------------- Active Task Panel -----------------
        st.subheader("Active Task (This Browser Session)")

        active_task_id = st.session_state.get("active_task_id", None)
        tasks = get_tasks()  # reload fresh

        if active_task_id is None:
            st.info("No active task for this session.")
        else:
            active_row = tasks[tasks["task_id"] == active_task_id]
            if active_row.empty:
                st.warning("Active task not found (may have been deleted). Clearing active task state.")
                st.session_state["active_task_id"] = None
            else:
                row = active_row.iloc[0]
                try:
                    start_dt = datetime.fromisoformat(str(row["start_time"]))
                except Exception:
                    start_dt = None

                if start_dt is not None:
                    elapsed = datetime.now() - start_dt
                    elapsed_minutes = elapsed.total_seconds() / 60
                    elapsed_str = str(elapsed).split(".")[0]  # strip microseconds
                else:
                    elapsed_str = "Unknown"
                    elapsed_minutes = None

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Employee:** {row['employee_name']}")
                    st.write(f"**Task:** {row['task_name']}")
                    st.write(f"**Category:** {row['task_category']}")
                with c2:
                    st.write(f"**Started:** {row['start_time']}")
                    st.write(f"**Elapsed:** {elapsed_str}")
                with c3:
                    st.write("**Notes:**")
                    st.write(row["task_description"])

                finish_clicked = st.button("⏹️ Finish Task")

                if finish_clicked:
                    end_dt = datetime.now()

                    # Get employee hourly rate
                    emp_df = get_employees()
                    emp_row = emp_df[emp_df["employee_id"] == row["employee_id"]]
                    if emp_row.empty:
                        hourly_rate = 0.0
                    else:
                        hourly_rate = float(emp_row.iloc[0]["hourly_rate"])

                    if start_dt is not None:
                        duration_minutes = (end_dt - start_dt).total_seconds() / 60
                        duration_hours = duration_minutes / 60
                    else:
                        duration_minutes = None
                        duration_hours = 0

                    cost = round(duration_hours * hourly_rate, 2) if duration_minutes is not None else None

                    # Update row in tasks df
                    tasks.loc[tasks["task_id"] == active_task_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_task_id, "duration_minutes"] = duration_minutes
                    tasks.loc[tasks["task_id"] == active_task_id, "cost"] = cost

                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = None
                    st.success(
                        f"Task finished. Duration: {duration_minutes:.1f} minutes, Cost: ${cost:.2f}"
                        if duration_minutes is not None
                        else "Task finished."
                    )

        # ----------------- Task Log -----------------
        st.subheader("Task Log")

        tasks = get_tasks()
        if tasks.empty:
            st.info("No tasks logged yet.")
        else:
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                emp_filter = st.selectbox(
                    "Filter by Employee",
                    options=["All"] + employees["name"].tolist(),
                    index=0
                )
            with f2:
                task_filter = st.selectbox(
                    "Filter by Task Name",
                    options=["All"] + sorted(task_types["task_name"].tolist()),
                    index=0
                )
            with f3:
                cat_filter = st.text_input("Filter by Category (contains)")
            with f4:
                show_in_progress_only = st.checkbox("Show only in-progress tasks", value=False)

            df_display = tasks.copy()

            if emp_filter != "All":
                df_display = df_display[df_display["employee_name"] == emp_filter]

            if task_filter != "All":
                df_display = df_display[df_display["task_name"] == task_filter]

            if cat_filter:
                df_display = df_display[
                    df_display["task_category"].str.contains(cat_filter, case=False, na=False)
                ]

            if show_in_progress_only:
                df_display = df_display[
                    df_display["end_time"].isna() | (df_display["end_time"] == "")
                ]

            # Sort newest first
            df_display = df_display.sort_values(["date", "start_time"], ascending=False)

            st.dataframe(df_display, use_container_width=True)


# -------------------------------
# PAGE 4: REPORTS
# -------------------------------
elif page == "4️⃣ Reports":
    st.title("Reports")

    employees = get_employees()
    tasks = get_tasks()

    # ---------- Employee Task Reports ----------
    st.header("Employee Task Cost & Time")

    if tasks.empty:
        st.info("No tasks logged yet.")
    else:
        df = tasks.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Only completed tasks have an end_time and duration
        df_completed = df[df["duration_minutes"].notna()]

        if df_completed.empty:
            st.info("No completed tasks yet to report on.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.date_input("Start Date", value=df_completed["date"].min().date())
            with c2:
                end_date = st.date_input("End Date", value=df_completed["date"].max().date())

            mask = (
                (df_completed["date"] >= pd.to_datetime(start_date)) &
                (df_completed["date"] <= pd.to_datetime(end_date))
            )
            df_filtered = df_completed[mask]

            st.subheader("Summary by Employee")
            by_emp = df_filtered.groupby("employee_name").agg(
                total_minutes=("duration_minutes", "sum"),
                total_hours=("duration_minutes", lambda x: x.sum() / 60),
                total_cost=("cost", "sum"),
                task_count=("task_id", "count")
            ).reset_index()

            st.dataframe(by_emp, use_container_width=True)

            st.subheader("Summary by Task Name")
            by_task = df_filtered.groupby(["task_name", "task_category"]).agg(
                total_minutes=("duration_minutes", "sum"),
                total_hours=("duration_minutes", lambda x: x.sum() / 60),
                total_cost=("cost", "sum"),
                task_count=("task_id", "count")
            ).reset_index()

            st.dataframe(by_task, use_container_width=True)

            st.caption(
                "Sales pipeline steps are just tasks with category 'Sales', "
                "so they'll show up here like everything else."
            )
    df.to_csv(path, index=False)


def combine_date_time(d: date, t: time) -> datetime:
    return datetime(
        year=d.year,
        month=d.month,
        day=d.day,
        hour=t.hour,
        minute=t.minute,
        second=t.second,
    )


def create_default_task_types() -> pd.DataFrame:
    """Default tasks including the sales pipeline steps."""
    defaults = [
        # Sales pipeline
        {"task_type_id": "TT_SALES_1", "task_name": "Sales – First Contact Reply", "category": "Sales"},
        {"task_type_id": "TT_SALES_2", "task_name": "Sales – Schedule Site Survey", "category": "Sales"},
        {"task_type_id": "TT_SALES_3", "task_name": "Sales – Record Site Survey Results", "category": "Sales"},
        {"task_type_id": "TT_SALES_4", "task_name": "Sales – Schedule Prep", "category": "Sales"},
        {"task_type_id": "TT_SALES_5", "task_name": "Sales – Schedule Install", "category": "Sales"},
        # Generic ops examples (you can delete or rename in the UI)
        {"task_type_id": "TT_OPS_1", "task_name": "Construction – Pull Fiber", "category": "Construction"},
        {"task_type_id": "TT_OPS_2", "task_name": "Construction – Lash Fiber", "category": "Construction"},
    ]
    return pd.DataFrame(defaults, columns=TASK_TYPE_COLUMNS)


# -------------------------------
# DATA LOADERS (CACHED)
# -------------------------------
@st.cache_data
def get_employees():
    return load_csv(EMPLOYEE_FILE, EMPLOYEE_COLUMNS)


@st.cache_data
def get_task_types():
    if TASK_TYPES_FILE.exists():
        df = load_csv(TASK_TYPES_FILE, TASK_TYPE_COLUMNS)
        if df.empty:
            df = create_default_task_types()
            save_csv(df, TASK_TYPES_FILE)
        return df
    else:
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
# SIDEBAR NAV
# -------------------------------
st.sidebar.title("⏱️ Task Tracker")
page = st.sidebar.radio(
    "Go to",
    [
        "1️⃣ Employees",
        "2️⃣ Task List",
        "3️⃣ Employee Tasks",
        "4️⃣ Reports",
    ]
)


# -------------------------------
# PAGE 1: EMPLOYEES
# -------------------------------
if page == "1️⃣ Employees":
    st.title("Employees")

    employees = get_employees()

    st.subheader("Add / Update Employee")

    with st.form("employee_form", clear_on_submit=True):
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
                st.warning("Name is required.")
            else:
                if not employee_id:
                    # Auto-generate a simple ID
                    employee_id = f"E{int(datetime.now().timestamp())}"

                # Check if employee exists -> update
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
                    employees = pd.concat([employees, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added employee {name}.")

                save_csv(employees, EMPLOYEE_FILE)
                refresh_employees_cache()

    st.subheader("Current Employees")
    if employees.empty:
        st.info("No employees yet. Add one above.")
    else:
        st.dataframe(employees, use_container_width=True)


# -------------------------------
# PAGE 2: TASK LIST (LIBRARY)
# -------------------------------
elif page == "2️⃣ Task List":
    st.title("Task List (Task Library)")

    task_types = get_task_types()

    st.subheader("Add / Update Task Type")

    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input("Task Name (what the employee selects)", placeholder="e.g., Sales – First Contact Reply")
        with c2:
            category = st.text_input("Category", placeholder="e.g., Sales, Construction, Admin")

        task_type_id = st.text_input(
            "Task Type ID (optional, auto if blank)",
            help="Internal ID; leave blank and it will be auto-generated.",
        ).strip()

        submitted = st.form_submit_button("Save Task Type")

        if submitted:
            if not task_name:
                st.warning("Task Name is required.")
            else:
                if not task_type_id:
                    task_type_id = f"TT_{int(datetime.now().timestamp())}"

                mask = task_types["task_type_id"] == task_type_id
                new_row = {
                    "task_type_id": task_type_id,
                    "task_name": task_name,
                    "category": category or "General",
                }

                if mask.any():
                    task_types.loc[mask, :] = new_row
                    st.success(f"Updated task type {task_name}.")
                else:
                    task_types = pd.concat([task_types, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added task type {task_name}.")

                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()

    st.subheader("Existing Task Types")
    task_types = get_task_types()

    if task_types.empty:
        st.info("No task types yet. Add some above.")
    else:
        st.dataframe(task_types, use_container_width=True)

        st.caption("Tip: Add your sales pipeline steps here so they appear in the dropdown on the Employee Tasks page.")


# -------------------------------
# PAGE 3: EMPLOYEE TASKS (TIMER + DROPDOWN)
# -------------------------------
elif page == "3️⃣ Employee Tasks":
    st.title("Employee Tasks (Timer)")

    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()

    # Track active task in this browser session
    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None

    if employees.empty:
        st.warning("You need to add employees first on the 'Employees' page.")
    elif task_types.empty:
        st.warning("You need to add task types first on the 'Task List' page.")
    else:
        st.subheader("Start a Task")

        with st.form("start_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)

            with c1:
                employee_name = st.selectbox(
                    "Employee",
                    options=employees["name"].tolist()
                )

                task_choice = st.selectbox(
                    "Task (from list)",
                    options=task_types["task_name"].tolist(),
                    help="Includes your sales pipeline steps and any other tasks you've added.",
                )

            with c2:
                task_description = st.text_area(
                    "Optional Notes / Description",
                    height=100,
                    placeholder="Extra details about this specific task instance..."
                )

            start_submitted = st.form_submit_button("▶️ Start Task")

            if start_submitted:
                if st.session_state["active_task_id"] is not None:
                    st.error("A task is already running in this session. Finish it before starting a new one.")
                else:
                    employee_row = employees[employees["name"] == employee_name].iloc[0]
                    employee_id = employee_row["employee_id"]

                    task_type_row = task_types[task_types["task_name"] == task_choice].iloc[0]
                    task_type_id = task_type_row["task_type_id"]
                    task_category = task_type_row["category"]

                    start_dt = datetime.now()
                    task_id = f"T{int(start_dt.timestamp())}"

                    new_task = {
                        "task_id": task_id,
                        "date": start_dt.date().isoformat(),
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "task_type_id": task_type_id,
                        "task_name": task_choice,
                        "task_category": task_category,
                        "task_description": task_description,
                        "start_time": start_dt.isoformat(),
                        "end_time": None,
                        "duration_minutes": None,
                        "cost": None,
                    }

                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = task_id
                    st.success(f"Started task '{task_choice}' for {employee_name} at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")

        # ----------------- Active Task Panel -----------------
        st.subheader("Active Task (This Browser Session)")

        active_task_id = st.session_state.get("active_task_id", None)
        tasks = get_tasks()  # reload fresh

        if active_task_id is None:
            st.info("No active task for this session.")
        else:
            active_row = tasks[tasks["task_id"] == active_task_id]
            if active_row.empty:
                st.warning("Active task not found (may have been deleted). Clearing active task state.")
                st.session_state["active_task_id"] = None
            else:
                row = active_row.iloc[0]
                try:
                    start_dt = datetime.fromisoformat(str(row["start_time"]))
                except Exception:
                    start_dt = None

                if start_dt is not None:
                    elapsed = datetime.now() - start_dt
                    elapsed_minutes = elapsed.total_seconds() / 60
                    elapsed_str = str(elapsed).split(".")[0]  # strip microseconds
                else:
                    elapsed_str = "Unknown"
                    elapsed_minutes = None

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Employee:** {row['employee_name']}")
                    st.write(f"**Task:** {row['task_name']}")
                    st.write(f"**Category:** {row['task_category']}")
                with c2:
                    st.write(f"**Started:** {row['start_time']}")
                    st.write(f"**Elapsed:** {elapsed_str}")
                with c3:
                    st.write("**Notes:**")
                    st.write(row["task_description"])

                finish_clicked = st.button("⏹️ Finish Task")

                if finish_clicked:
                    end_dt = datetime.now()

                    # Get employee hourly rate
                    emp_df = get_employees()
                    emp_row = emp_df[emp_df["employee_id"] == row["employee_id"]]
                    if emp_row.empty:
                        hourly_rate = 0.0
                    else:
                        hourly_rate = float(emp_row.iloc[0]["hourly_rate"])

                    if start_dt is not None:
                        duration_minutes = (end_dt - start_dt).total_seconds() / 60
                        duration_hours = duration_minutes / 60
                    else:
                        duration_minutes = None
                        duration_hours = 0

                    cost = round(duration_hours * hourly_rate, 2) if duration_minutes is not None else None

                    # Update row in tasks df
                    tasks.loc[tasks["task_id"] == active_task_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_task_id, "duration_minutes"] = duration_minutes
                    tasks.loc[tasks["task_id"] == active_task_id, "cost"] = cost

                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = None
                    st.success(
                        f"Task finished. Duration: {duration_minutes:.1f} minutes, Cost: ${cost:.2f}"
                        if duration_minutes is not None
                        else "Task finished."
                    )

        # ----------------- Task Log -----------------
        st.subheader("Task Log")

        tasks = get_tasks()
        if tasks.empty:
            st.info("No tasks logged yet.")
        else:
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                emp_filter = st.selectbox(
                    "Filter by Employee",
                    options=["All"] + employees["name"].tolist(),
                    index=0
                )
            with f2:
                task_filter = st.selectbox(
                    "Filter by Task Name",
                    options=["All"] + sorted(task_types["task_name"].tolist()),
                    index=0
                )
            with f3:
                cat_filter = st.text_input("Filter by Category (contains)")
            with f4:
                show_in_progress_only = st.checkbox("Show only in-progress tasks", value=False)

            df_display = tasks.copy()

            if emp_filter != "All":
                df_display = df_display[df_display["employee_name"] == emp_filter]

            if task_filter != "All":
                df_display = df_display[df_display["task_name"] == task_filter]

            if cat_filter:
                df_display = df_display[df_display["task_category"].str.contains(cat_filter, case=False, na=False)]

            if show_in_progress_only:
                df_display = df_display[df_display["end_time"].isna() | (df_display["end_time"] == "")]

            # Sort newest first
            df_display = df_display.sort_values(["date", "start_time"], ascending=False)

            st.dataframe(df_display, use_container_width=True)


# -------------------------------
# PAGE 4: REPORTS
# -------------------------------
elif page == "4️⃣ Reports":
    st.title("Reports")

    employees = get_employees()
    tasks = get_tasks()

    # ---------- Employee Task Reports ----------
    st.header("Employee Task Cost & Time")

    if tasks.empty:
        st.info("No tasks logged yet.")
    else:
        df = tasks.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Only completed tasks have an end_time and duration
        df_completed = df[df["duration_minutes"].notna()]

        if df_completed.empty:
            st.info("No completed tasks yet to report on.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.date_input("Start Date", value=df_completed["date"].min().date())
            with c2:
                end_date = st.date_input("End Date", value=df_completed["date"].max().date())

            mask = (df_completed["date"] >= pd.to_datetime(start_date)) & (df_completed["date"] <= pd.to_datetime(end_date))
            df_filtered = df_completed[mask]

            st.subheader("Summary by Employee")
            by_emp = df_filtered.groupby("employee_name").agg(
                total_minutes=("duration_minutes", "sum"),
                total_hours=("duration_minutes", lambda x: x.sum() / 60),
                total_cost=("cost", "sum"),
                task_count=("task_id", "count")
            ).reset_index()

            st.dataframe(by_emp, use_container_width=True)

            st.subheader("Summary by Task Name")
            by_task = df_filtered.groupby(["task_name", "task_category"]).agg(
                total_minutes=("duration_minutes", "sum"),
                total_hours=("duration_minutes", lambda x: x.sum() / 60),
                total_cost=("cost", "sum"),
                task_count=("task_id", "count")
            ).reset_index()

            st.dataframe(by_task, use_container_width=True)

            st.caption("Sales pipeline steps are just tasks with category 'Sales', so they'll show up here like everything else.")
    "duration_minutes",
    "cost"
]
LEAD_COLUMNS = [
    "lead_id",
    "customer_name",
    "salesperson",
    "contact_method",
    "first_contact_received",
    "first_response_sent",
    "site_survey_scheduled",
    "site_survey_completed",
    "prep_scheduled",
    "install_scheduled",
    "notes"
]

@st.cache_data
def get_employees():
    return load_csv(EMPLOYEE_FILE, EMPLOYEE_COLUMNS)

@st.cache_data
def get_tasks():
    return load_csv(TASKS_FILE, TASK_COLUMNS)

@st.cache_data
def get_leads():
    return load_csv(LEADS_FILE, LEAD_COLUMNS)


def refresh_employees_cache():
    get_employees.clear()

def refresh_tasks_cache():
    get_tasks.clear()

def refresh_leads_cache():
    get_leads.clear()


# -------------------------------
# SIDEBAR NAV
# -------------------------------
st.sidebar.title("⏱️ Task Tracker")
page = st.sidebar.radio(
    "Go to",
    [
        "1️⃣ Employees",
        "2️⃣ Employee Tasks",
        "3️⃣ Sales Pipeline",
        "4️⃣ Reports"
    ]
)


# -------------------------------
# PAGE 1: EMPLOYEES
# -------------------------------
if page == "1️⃣ Employees":
    st.title("Employees")

    employees = get_employees()

    st.subheader("Add / Update Employee")

    with st.form("employee_form", clear_on_submit=True):
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
                st.warning("Name is required.")
            else:
                if not employee_id:
                    # Auto-generate a simple ID
                    employee_id = f"E{int(datetime.now().timestamp())}"

                # Check if employee exists -> update
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
                    employees = pd.concat([employees, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added employee {name}.")

                save_csv(employees, EMPLOYEE_FILE)
                refresh_employees_cache()

    st.subheader("Current Employees")
    if employees.empty:
        st.info("No employees yet. Add one above.")
    else:
        st.dataframe(employees, use_container_width=True)


# -------------------------------
# PAGE 2: EMPLOYEE TASKS (TIMER-BASED)
# -------------------------------
elif page == "2️⃣ Employee Tasks":
    st.title("Employee Tasks")

    employees = get_employees()
    tasks = get_tasks()

    # Track active task in this browser session
    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None

    if employees.empty:
        st.warning("You need to add employees first on the 'Employees' page.")
    else:
        st.subheader("Start a Task (Timer)")

        with st.form("start_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)

            with c1:
                employee_name = st.selectbox(
                    "Employee",
                    options=employees["name"].tolist()
                )
                task_category = st.text_input("Task Category", value="General")

            with c2:
                task_description = st.text_area("Task Description", height=100)

            start_submitted = st.form_submit_button("▶️ Start Task")

            if start_submitted:
                if st.session_state["active_task_id"] is not None:
                    st.error("A task is already running in this session. Finish it before starting a new one.")
                else:
                    employee_row = employees[employees["name"] == employee_name].iloc[0]
                    employee_id = employee_row["employee_id"]

                    start_dt = datetime.now()
                    task_id = f"T{int(start_dt.timestamp())}"

                    new_task = {
                        "task_id": task_id,
                        "date": start_dt.date().isoformat(),
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "task_category": task_category,
                        "task_description": task_description,
                        "start_time": start_dt.isoformat(),
                        "end_time": None,
                        "duration_minutes": None,
                        "cost": None,
                    }

                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = task_id
                    st.success(f"Started task for {employee_name} at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")

        # ----------------- Active Task Panel -----------------
        st.subheader("Active Task")

        active_task_id = st.session_state.get("active_task_id", None)
        tasks = get_tasks()  # reload fresh

        if active_task_id is None:
            st.info("No active task for this session.")
        else:
            active_row = tasks[tasks["task_id"] == active_task_id]
            if active_row.empty:
                st.warning("Active task not found (may have been deleted). Clearing active task state.")
                st.session_state["active_task_id"] = None
            else:
                row = active_row.iloc[0]
                try:
                    start_dt = datetime.fromisoformat(str(row["start_time"]))
                except Exception:
                    start_dt = None

                if start_dt is not None:
                    elapsed = datetime.now() - start_dt
                    elapsed_minutes = elapsed.total_seconds() / 60
                    elapsed_str = str(elapsed).split(".")[0]  # strip microseconds
                else:
                    elapsed_str = "Unknown"
                    elapsed_minutes = None

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Employee:** {row['employee_name']}")
                    st.write(f"**Task Category:** {row['task_category']}")
                with c2:
                    st.write(f"**Started:** {row['start_time']}")
                    st.write(f"**Elapsed:** {elapsed_str}")
                with c3:
                    st.write("**Description:**")
                    st.write(row["task_description"])

                finish_clicked = st.button("⏹️ Finish Task")

                if finish_clicked:
                    end_dt = datetime.now()

                    # Get employee hourly rate
                    emp_df = get_employees()
                    emp_row = emp_df[emp_df["employee_id"] == row["employee_id"]]
                    if emp_row.empty:
                        hourly_rate = 0.0
                    else:
                        hourly_rate = float(emp_row.iloc[0]["hourly_rate"])

                    if start_dt is not None:
                        duration_minutes = (end_dt - start_dt).total_seconds() / 60
                        duration_hours = duration_minutes / 60
                    else:
                        duration_minutes = None
                        duration_hours = 0

                    cost = round(duration_hours * hourly_rate, 2) if duration_minutes is not None else None

                    # Update row in tasks df
                    tasks.loc[tasks["task_id"] == active_task_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_task_id, "duration_minutes"] = duration_minutes
                    tasks.loc[tasks["task_id"] == active_task_id, "cost"] = cost

                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.session_state["active_task_id"] = None
                    st.success(
                        f"Task finished. Duration: {duration_minutes:.1f} minutes, Cost: ${cost:.2f}"
                        if duration_minutes is not None
                        else "Task finished."
                    )

        # ----------------- Task Log -----------------
        st.subheader("Task Log")

        tasks = get_tasks()
        if tasks.empty:
            st.info("No tasks logged yet.")
        else:
            f1, f2, f3 = st.columns(3)
            with f1:
                emp_filter = st.selectbox(
                    "Filter by Employee",
                    options=["All"] + employees["name"].tolist(),
                    index=0
                )
            with f2:
                cat_filter = st.text_input("Filter by Task Category (contains)")
            with f3:
                show_in_progress_only = st.checkbox("Show only in-progress tasks", value=False)

            df_display = tasks.copy()

            if emp_filter != "All":
                df_display = df_display[df_display["employee_name"] == emp_filter]

            if cat_filter:
                df_display = df_display[df_display["task_category"].str.contains(cat_filter, case=False, na=False)]

            if show_in_progress_only:
                df_display = df_display[df_display["end_time"].isna() | (df_display["end_time"] == "")]

            # Sort newest first
            df_display = df_display.sort_values("date", ascending=False)

            st.dataframe(df_display, use_container_width=True)


# -------------------------------
# PAGE 3: SALES PIPELINE
# -------------------------------
elif page == "3️⃣ Sales Pipeline":
    st.title("Sales Pipeline Tracker")

    employees = get_employees()
    leads = get_leads()

    # Assume your salesperson is one of the employees with role containing "Sales"
    sales_people = employees[employees["role"].str.contains("sales", case=False, na=False)]
    if sales_people.empty and not employees.empty:
        sales_people = employees  # fallback: allow any employee

    st.subheader("Add / Update Lead")

    with st.form("lead_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            lead_id = st.text_input("Lead ID (blank for new)").strip()
            customer_name = st.text_input("Customer Name")
            salesperson = st.selectbox(
                "Salesperson",
                options=sales_people["name"].tolist() if not sales_people.empty else employees["name"].tolist()
            )
            contact_method = st.selectbox("Primary Contact Method", ["Email", "Phone", "In-person", "Other"])

        with c2:
            # datetime inputs
            today = date.today()
            first_contact_date = st.date_input("First Contact Received Date", value=today)
            first_contact_time = st.time_input("First Contact Received Time", value=time(9, 0))
            first_response_date = st.date_input("First Response Sent Date", value=today)
            first_response_time = st.time_input("First Response Sent Time", value=time(9, 30))

        st.markdown("**Pipeline Steps (optional: fill as they happen)**")
        c3, c4, c5 = st.columns(3)

        with c3:
            ssched_date = st.date_input("Site Survey Scheduled Date", value=None, key="ssched_date") \
                if st.checkbox("Site Survey Scheduled?") else None
            ssched_time = st.time_input("Site Survey Scheduled Time", value=time(10, 0), key="ssched_time") \
                if ssched_date else None

        with c4:
            scomp_date = st.date_input("Site Survey Completed Date", value=None, key="scomp_date") \
                if st.checkbox("Site Survey Completed?") else None
            scomp_time = st.time_input("Site Survey Completed Time", value=time(11, 0), key="scomp_time") \
                if scomp_date else None

        with c5:
            prep_date = st.date_input("Prep Scheduled Date", value=None, key="prep_date") \
                if st.checkbox("Prep Scheduled?") else None
            prep_time = st.time_input("Prep Scheduled Time", value=time(12, 0), key="prep_time") \
                if prep_date else None

        install_date = st.date_input("Install Scheduled Date", value=None, key="install_date") \
            if st.checkbox("Install Scheduled?") else None
        install_time = st.time_input("Install Scheduled Time", value=time(13, 0), key="install_time") \
            if install_date else None

        notes = st.text_area("Notes", height=100)

        submitted = st.form_submit_button("Save Lead")

        if submitted:
            if not customer_name:
                st.warning("Customer name is required.")
            else:
                if not lead_id:
                    lead_id = f"L{int(datetime.now().timestamp())}"

                first_contact_received = combine_date_time(first_contact_date, first_contact_time)
                first_response_sent = combine_date_time(first_response_date, first_response_time)

                site_survey_scheduled = combine_date_time(ssched_date, ssched_time).isoformat() \
                    if ssched_date and ssched_time else None
                site_survey_completed = combine_date_time(scomp_date, scomp_time).isoformat() \
                    if scomp_date and scomp_time else None
                prep_scheduled = combine_date_time(prep_date, prep_time).isoformat() \
                    if prep_date and prep_time else None
                install_scheduled = combine_date_time(install_date, install_time).isoformat() \
                    if install_date and install_time else None

                new_row = {
                    "lead_id": lead_id,
                    "customer_name": customer_name,
                    "salesperson": salesperson,
                    "contact_method": contact_method,
                    "first_contact_received": first_contact_received.isoformat(),
                    "first_response_sent": first_response_sent.isoformat(),
                    "site_survey_scheduled": site_survey_scheduled,
                    "site_survey_completed": site_survey_completed,
                    "prep_scheduled": prep_scheduled,
                    "install_scheduled": install_scheduled,
                    "notes": notes
                }

                mask = leads["lead_id"] == lead_id
                if mask.any():
                    leads.loc[mask, :] = new_row
                    st.success(f"Updated lead {lead_id} – {customer_name}.")
                else:
                    leads = pd.concat([leads, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added new lead {lead_id} – {customer_name}.")

                save_csv(leads, LEADS_FILE)
                refresh_leads_cache()

    st.subheader("Leads Table")
    leads = get_leads()

    if leads.empty:
        st.info("No leads yet.")
    else:
        st.dataframe(leads, use_container_width=True)

        # Calculate KPIs
        st.subheader("Sales Response Time KPIs")

        df = leads.copy()
        for col in [
            "first_contact_received",
            "first_response_sent",
            "site_survey_scheduled",
            "site_survey_completed",
            "prep_scheduled",
            "install_scheduled"
        ]:
            df[col] = pd.to_datetime(df[col], errors="coerce")

        # Time to first response
        df["mins_to_first_response"] = (
            df["first_response_sent"] - df["first_contact_received"]
        ).dt.total_seconds() / 60

        # Time from first contact to key milestones
        df["hours_to_site_survey_scheduled"] = (
            df["site_survey_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_prep_scheduled"] = (
            df["prep_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_install_scheduled"] = (
            df["install_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric(
                "Avg Minutes to First Response",
                value=f"{df['mins_to_first_response'].dropna().mean():.1f}"
                if df["mins_to_first_response"].notna().any() else "N/A"
            )
        with k2:
            st.metric(
                "Avg Hours to Site Survey Scheduled",
                value=f"{df['hours_to_site_survey_scheduled'].dropna().mean():.1f}"
                if df["hours_to_site_survey_scheduled"].notna().any() else "N/A"
            )
        with k3:
            st.metric(
                "Avg Hours to Prep Scheduled",
                value=f"{df['hours_to_prep_scheduled'].dropna().mean():.1f}"
                if df["hours_to_prep_scheduled"].notna().any() else "N/A"
            )
        with k4:
            st.metric(
                "Avg Hours to Install Scheduled",
                value=f"{df['hours_to_install_scheduled'].dropna().mean():.1f}"
                if df["hours_to_install_scheduled"].notna().any() else "N/A"
            )


# -------------------------------
# PAGE 4: REPORTS
# -------------------------------
elif page == "4️⃣ Reports":
    st.title("Reports")

    employees = get_employees()
    tasks = get_tasks()
    leads = get_leads()

    # ---------- Employee Task Reports ----------
    st.header("Employee Task Cost & Time")

    if tasks.empty:
        st.info("No tasks logged yet.")
    else:
        df = tasks.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        # Only completed tasks have an end_time and duration
        df_completed = df[df["duration_minutes"].notna()]

        if df_completed.empty:
            st.info("No completed tasks yet to report on.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.date_input("Start Date", value=df_completed["date"].min().date())
            with c2:
    
                # Check if employee exists -> update
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
                    employees = pd.concat([employees, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added employee {name}.")

                save_csv(employees, EMPLOYEE_FILE)
                refresh_employees_cache()

    st.subheader("Current Employees")
    if employees.empty:
        st.info("No employees yet. Add one above.")
    else:
        st.dataframe(employees, use_container_width=True)


# -------------------------------
# PAGE 2: EMPLOYEE TASKS
# -------------------------------
elif page == "2️⃣ Employee Tasks":
    st.title("Employee Tasks")

    employees = get_employees()
    tasks = get_tasks()

    if employees.empty:
        st.warning("You need to add employees first on the 'Employees' page.")
    else:
        st.subheader("Log a Task")

        with st.form("task_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                employee_name = st.selectbox(
                    "Employee",
                    options=employees["name"].tolist()
                )
                task_date = st.date_input("Task Date", value=date.today())
                task_category = st.text_input("Task Category", value="General")

            with c2:
                start_t = st.time_input("Start Time", value=time(8, 0))
                end_t = st.time_input("End Time", value=time(9, 0))

            with c3:
                task_description = st.text_area("Task Description", height=100)

            submitted = st.form_submit_button("Save Task")

            if submitted:
                if end_t <= start_t:
                    st.error("End time must be after start time.")
                else:
                    employee_row = employees[employees["name"] == employee_name].iloc[0]
                    employee_id = employee_row["employee_id"]
                    hourly_rate = float(employee_row["hourly_rate"])

                    start_dt = combine_date_time(task_date, start_t)
                    end_dt = combine_date_time(task_date, end_t)

                    duration_minutes = (end_dt - start_dt).total_seconds() / 60
                    duration_hours = duration_minutes / 60.0
                    cost = round(duration_hours * hourly_rate, 2)

                    task_id = f"T{int(datetime.now().timestamp())}"

                    new_task = {
                        "task_id": task_id,
                        "date": task_date.isoformat(),
                        "employee_id": employee_id,
                        "employee_name": employee_name,
                        "task_category": task_category,
                        "task_description": task_description,
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat(),
                        "duration_minutes": duration_minutes,
                        "cost": cost
                    }

                    tasks = pd.concat([tasks, pd.DataFrame([new_task])], ignore_index=True)
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()

                    st.success(f"Task saved. Duration: {duration_minutes:.1f} minutes, Cost: ${cost:.2f}")

        st.subheader("Task Log")

        if tasks.empty:
            st.info("No tasks logged yet.")
        else:
            # Optional filters
            f1, f2, f3 = st.columns(3)
            with f1:
                emp_filter = st.selectbox(
                    "Filter by Employee",
                    options=["All"] + employees["name"].tolist(),
                    index=0
                )
            with f2:
                cat_filter = st.text_input("Filter by Task Category (contains)")
            with f3:
                date_filter = st.date_input("Filter by Date (optional)", value=None)

            df_display = tasks.copy()

            if emp_filter != "All":
                df_display = df_display[df_display["employee_name"] == emp_filter]

            if cat_filter:
                df_display = df_display[df_display["task_category"].str.contains(cat_filter, case=False, na=False)]

            if isinstance(date_filter, date):
                df_display = df_display[df_display["date"] == date_filter.isoformat()]

            st.dataframe(df_display.sort_values("date", ascending=False), use_container_width=True)


# -------------------------------
# PAGE 3: SALES PIPELINE
# -------------------------------
elif page == "3️⃣ Sales Pipeline":
    st.title("Sales Pipeline Tracker")

    employees = get_employees()
    leads = get_leads()

    # Assume your salesperson is one of the employees with role containing "Sales"
    sales_people = employees[employees["role"].str.contains("sales", case=False, na=False)]
    if sales_people.empty and not employees.empty:
        sales_people = employees  # fallback: allow any employee

    st.subheader("Add / Update Lead")

    with st.form("lead_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            lead_id = st.text_input("Lead ID (blank for new)").strip()
            customer_name = st.text_input("Customer Name")
            salesperson = st.selectbox(
                "Salesperson",
                options=sales_people["name"].tolist() if not sales_people.empty else employees["name"].tolist()
            )
            contact_method = st.selectbox("Primary Contact Method", ["Email", "Phone", "In-person", "Other"])

        with c2:
            # datetime inputs
            today = date.today()
            first_contact_date = st.date_input("First Contact Received Date", value=today)
            first_contact_time = st.time_input("First Contact Received Time", value=time(9, 0))
            first_response_date = st.date_input("First Response Sent Date", value=today)
            first_response_time = st.time_input("First Response Sent Time", value=time(9, 30))

        st.markdown("**Pipeline Steps (optional: fill as they happen)**")
        c3, c4, c5 = st.columns(3)

        with c3:
            ssched_date = st.date_input("Site Survey Scheduled Date", value=None, key="ssched_date") \
                if st.checkbox("Site Survey Scheduled?") else None
            ssched_time = st.time_input("Site Survey Scheduled Time", value=time(10, 0), key="ssched_time") \
                if ssched_date else None

        with c4:
            scomp_date = st.date_input("Site Survey Completed Date", value=None, key="scomp_date") \
                if st.checkbox("Site Survey Completed?") else None
            scomp_time = st.time_input("Site Survey Completed Time", value=time(11, 0), key="scomp_time") \
                if scomp_date else None

        with c5:
            prep_date = st.date_input("Prep Scheduled Date", value=None, key="prep_date") \
                if st.checkbox("Prep Scheduled?") else None
            prep_time = st.time_input("Prep Scheduled Time", value=time(12, 0), key="prep_time") \
                if prep_date else None

        install_date = st.date_input("Install Scheduled Date", value=None, key="install_date") \
            if st.checkbox("Install Scheduled?") else None
        install_time = st.time_input("Install Scheduled Time", value=time(13, 0), key="install_time") \
            if install_date else None

        notes = st.text_area("Notes", height=100)

        submitted = st.form_submit_button("Save Lead")

        if submitted:
            if not customer_name:
                st.warning("Customer name is required.")
            else:
                if not lead_id:
                    lead_id = f"L{int(datetime.now().timestamp())}"

                first_contact_received = combine_date_time(first_contact_date, first_contact_time)
                first_response_sent = combine_date_time(first_response_date, first_response_time)

                site_survey_scheduled = combine_date_time(ssched_date, ssched_time).isoformat() \
                    if ssched_date and ssched_time else None
                site_survey_completed = combine_date_time(scomp_date, scomp_time).isoformat() \
                    if scomp_date and scomp_time else None
                prep_scheduled = combine_date_time(prep_date, prep_time).isoformat() \
                    if prep_date and prep_time else None
                install_scheduled = combine_date_time(install_date, install_time).isoformat() \
                    if install_date and install_time else None

                new_row = {
                    "lead_id": lead_id,
                    "customer_name": customer_name,
                    "salesperson": salesperson,
                    "contact_method": contact_method,
                    "first_contact_received": first_contact_received.isoformat(),
                    "first_response_sent": first_response_sent.isoformat(),
                    "site_survey_scheduled": site_survey_scheduled,
                    "site_survey_completed": site_survey_completed,
                    "prep_scheduled": prep_scheduled,
                    "install_scheduled": install_scheduled,
                    "notes": notes
                }

                mask = leads["lead_id"] == lead_id
                if mask.any():
                    leads.loc[mask, :] = new_row
                    st.success(f"Updated lead {lead_id} – {customer_name}.")
                else:
                    leads = pd.concat([leads, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added new lead {lead_id} – {customer_name}.")

                save_csv(leads, LEADS_FILE)
                refresh_leads_cache()

    st.subheader("Leads Table")
    leads = get_leads()

    if leads.empty:
        st.info("No leads yet.")
    else:
        st.dataframe(leads, use_container_width=True)

        # Calculate KPIs
        st.subheader("Sales Response Time KPIs")

        df = leads.copy()
        for col in [
            "first_contact_received",
            "first_response_sent",
            "site_survey_scheduled",
            "site_survey_completed",
            "prep_scheduled",
            "install_scheduled"
        ]:
            df[col] = pd.to_datetime(df[col], errors="coerce")

        # Time to first response
        df["mins_to_first_response"] = (
            df["first_response_sent"] - df["first_contact_received"]
        ).dt.total_seconds() / 60

        # Time from first contact to key milestones
        df["hours_to_site_survey_scheduled"] = (
            df["site_survey_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_prep_scheduled"] = (
            df["prep_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_install_scheduled"] = (
            df["install_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric(
                "Avg Minutes to First Response",
                value=f"{df['mins_to_first_response'].dropna().mean():.1f}"
                if df["mins_to_first_response"].notna().any() else "N/A"
            )
        with k2:
            st.metric(
                "Avg Hours to Site Survey Scheduled",
                value=f"{df['hours_to_site_survey_scheduled'].dropna().mean():.1f}"
                if df["hours_to_site_survey_scheduled"].notna().any() else "N/A"
            )
        with k3:
            st.metric(
                "Avg Hours to Prep Scheduled",
                value=f"{df['hours_to_prep_scheduled'].dropna().mean():.1f}"
                if df["hours_to_prep_scheduled"].notna().any() else "N/A"
            )
        with k4:
            st.metric(
                "Avg Hours to Install Scheduled",
                value=f"{df['hours_to_install_scheduled'].dropna().mean():.1f}"
                if df["hours_to_install_scheduled"].notna().any() else "N/A"
            )


# -------------------------------
# PAGE 4: REPORTS
# -------------------------------
elif page == "4️⃣ Reports":
    st.title("Reports")

    employees = get_employees()
    tasks = get_tasks()
    leads = get_leads()

    # ---------- Employee Task Reports ----------
    st.header("Employee Task Cost & Time")

    if tasks.empty:
        st.info("No tasks logged yet.")
    else:
        df = tasks.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start Date", value=df["date"].min().date())
        with c2:
            end_date = st.date_input("End Date", value=df["date"].max().date())

        mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
        df = df[mask]

        st.subheader("Summary by Employee")
        by_emp = df.groupby("employee_name").agg(
            total_minutes=("duration_minutes", "sum"),
            total_hours=("duration_minutes", lambda x: x.sum() / 60),
            total_cost=("cost", "sum"),
            task_count=("task_id", "count")
        ).reset_index()

        st.dataframe(by_emp, use_container_width=True)

        st.subheader("Summary by Task Category")
        by_cat = df.groupby("task_category").agg(
            total_minutes=("duration_minutes", "sum"),
            total_hours=("duration_minutes", lambda x: x.sum() / 60),
            total_cost=("cost", "sum"),
            task_count=("task_id", "count")
        ).reset_index()

        st.dataframe(by_cat, use_container_width=True)

    st.markdown("---")

    # ---------- Sales Pipeline Reports ----------
    st.header("Sales Pipeline Performance")

    if leads.empty:
        st.info("No leads yet.")
    else:
        df = leads.copy()
        for col in [
            "first_contact_received",
            "first_response_sent",
            "site_survey_scheduled",
            "site_survey_completed",
            "prep_scheduled",
            "install_scheduled"
        ]:
            df[col] = pd.to_datetime(df[col], errors="coerce")

        df["mins_to_first_response"] = (
            df["first_response_sent"] - df["first_contact_received"]
        ).dt.total_seconds() / 60

        df["hours_to_site_survey_scheduled"] = (
            df["site_survey_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_prep_scheduled"] = (
            df["prep_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        df["hours_to_install_scheduled"] = (
            df["install_scheduled"] - df["first_contact_received"]
        ).dt.total_seconds() / 3600

        st.subheader("Sales KPIs by Salesperson")

        by_sales = df.groupby("salesperson").agg(
            leads_count=("lead_id", "count"),
            avg_mins_to_first_response=("mins_to_first_response", "mean"),
            avg_hours_to_site_survey_scheduled=("hours_to_site_survey_scheduled", "mean"),
            avg_hours_to_prep_scheduled=("hours_to_prep_scheduled", "mean"),
            avg_hours_to_install_scheduled=("hours_to_install_scheduled", "mean"),
        ).reset_index()

        # Round numeric columns
        for col in by_sales.columns:
            if "avg_" in col:
                by_sales[col] = by_sales[col].round(1)

        st.dataframe(by_sales, use_container_width=True)

        st.subheader("Lead Detail with Timings")
        st.dataframe(df[
            [
                "lead_id",
                "customer_name",
                "salesperson",
                "mins_to_first_response",
                "hours_to_site_survey_scheduled",
                "hours_to_prep_scheduled",
                "hours_to_install_scheduled"
            
        ], use_container_width=True)
