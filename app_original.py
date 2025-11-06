import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date, time

# -------------------------------
# CONFIGURATION
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
TASK_TYPES_FILE = DATA_DIR / "task_types.csv"

# -------------------------------
# CONSTANTS
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_TYPE_COLUMNS = ["task_type_id", "task_name", "category"]
TASK_COLUMNS = [
    "task_id", "date", "employee_id", "employee_name",
    "task_type_id", "task_name", "task_category",
    "task_description", "start_time", "end_time",
    "duration_minutes", "cost"
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
        return df[columns]
    return pd.DataFrame(columns=columns)


def save_csv(df: pd.DataFrame, path: Path):
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
        "1️⃣ Employees",
        "2️⃣ Task List",
        "3️⃣ Employee Tasks",
        "4️⃣ Reports",
    ],
    key="main_nav"  # ensures unique ID and prevents duplicate element error
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
                    employee_id = f"E{int(datetime.now().timestamp())}"
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
        st.info("No employees yet.")
    else:
        st.dataframe(employees, use_container_width=True)

# -------------------------------
# PAGE 2: TASK LIST (LIBRARY)
# -------------------------------
elif page == "2️⃣ Task List":
    st.title("Task Library")
    task_types = get_task_types()

    st.subheader("Add / Update Task Type")

    with st.form("task_type_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            task_name = st.text_input("Task Name", placeholder="e.g., Sales – Schedule Site Survey")
        with c2:
            category = st.text_input("Category", placeholder="e.g., Sales, Construction, Admin")
        task_type_id = st.text_input("Task ID (optional, auto if blank)").strip()
        submitted = st.form_submit_button("Save Task Type")

        if submitted:
            if not task_name:
                st.warning("Task name required.")
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
                    st.success(f"Updated {task_name}.")
                else:
                    task_types = pd.concat([task_types, pd.DataFrame([new_row])], ignore_index=True)
                    st.success(f"Added {task_name}.")
                save_csv(task_types, TASK_TYPES_FILE)
                refresh_task_types_cache()

    st.subheader("Existing Tasks")
    st.dataframe(get_task_types(), use_container_width=True)

# -------------------------------
# PAGE 3: EMPLOYEE TASKS (TIMER)
# -------------------------------
elif page == "3️⃣ Employee Tasks":
    st.title("Employee Tasks (Start/Finish Timer)")

    employees = get_employees()
    task_types = get_task_types()
    tasks = get_tasks()

    if "active_task_id" not in st.session_state:
        st.session_state["active_task_id"] = None

    if employees.empty:
        st.warning("Add employees first.")
    elif task_types.empty:
        st.warning("Add task types first.")
    else:
        st.subheader("Start a Task")

        with st.form("start_task_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                employee_name = st.selectbox("Employee", employees["name"])
                task_choice = st.selectbox("Task", task_types["task_name"])
            with col2:
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
                    st.success(f"Started '{tt['task_name']}' for {employee_name} at {start_time.strftime('%H:%M:%S')}")

        # Active Task Panel
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
                start_dt = datetime.fromisoformat(str(row["start_time"]))
                elapsed = datetime.now() - start_dt
                elapsed_str = str(elapsed).split(".")[0]
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

                if st.button("⏹️ Finish Task", key="finish_btn"):
                    end_dt = datetime.now()
                    emp = employees[employees["employee_id"] == row["employee_id"]].iloc[0]
                    minutes = (end_dt - start_dt).total_seconds() / 60
                    cost = round((minutes / 60) * float(emp["hourly_rate"]), 2)
                    tasks.loc[tasks["task_id"] == active_id, "end_time"] = end_dt.isoformat()
                    tasks.loc[tasks["task_id"] == active_id, "duration_minutes"] = minutes
                    tasks.loc[tasks["task_id"] == active_id, "cost"] = cost
                    save_csv(tasks, TASKS_FILE)
                    refresh_tasks_cache()
                    st.session_state["active_task_id"] = None
                    st.success(f"Task finished. Duration {minutes:.1f} min, cost ${cost:.2f}")

        st.subheader("Task Log")
        df = get_tasks()
        if df.empty:
            st.info("No tasks logged yet.")
        else:
            st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)

# -------------------------------
# PAGE 4: REPORTS
# -------------------------------
elif page == "4️⃣ Reports":
    st.title("Reports")

    tasks = get_tasks()
    if tasks.empty:
        st.info("No tasks logged yet.")
    else:
        df = tasks.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df_done = df[df["duration_minutes"].notna()]

        if df_done.empty:
            st.info("No completed tasks yet.")
        else:
            st.subheader("Summary by Employee")
            emp = df_done.groupby("employee_name").agg(
                total_hours=("duration_minutes", lambda x: round(x.sum() / 60, 2)),
                total_cost=("cost", "sum"),
                tasks=("task_id", "count")
            ).reset_index()
            st.dataframe(emp, use_container_width=True)

            st.subheader("Summary by Task")
            t = df_done.groupby(["task_name", "task_category"]).agg(
                total_hours=("duration_minutes", lambda x: round(x.sum() / 60, 2)),
                total_cost=("cost", "sum"),
                tasks=("task_id", "count")
            ).reset_index()
            st.dataframe(t, use_container_width=True)

            st.caption("Sales pipeline steps appear here automatically under category 'Sales'.")
