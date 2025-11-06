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
LEADS_FILE = DATA_DIR / "sales_leads.csv"


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


# -------------------------------
# INITIAL DATA LOAD
# -------------------------------
EMPLOYEE_COLUMNS = ["employee_id", "name", "role", "hourly_rate"]
TASK_COLUMNS = [
    "task_id",
    "date",
    "employee_id",
    "employee_name",
    "task_category",
    "task_description",
    "start_time",
    "end_time",
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
            ]
        ], use_container_width=True)
