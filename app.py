from __future__ import annotations

import os
from io import StringIO
import csv
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:  # pragma: no cover - handled at runtime
    mysql = None
    MySQLError = Exception


PAGE_TEMPLATES = {
    "about.html",
    "account-history.html",
    "account-settings.html",
    "apply-scholarship.html",
    "contact.html",
    "cookie-policy.html",
    "disclaimer.html",
    "donor-create-scheme.html",
    "donor-dashboard.html",
    "donor-impact-reports.html",
    "donor-registration.html",
    "donor-review-applications.html",
    "donor-settings.html",
    "eligibility-checker.html",
    "forgot-password.html",
    "index.html",
    "login-donor.html",
    "login-student.html",
    "privacy-policy.html",
    "search-dashboard.html",
    "search.html",
    "services.html",
    "signup.html",
    "student-dashboard.html",
    "terms-of-service.html",
    "track-status.html",
}

DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "Mi123456#"),
    "database": os.environ.get("MYSQL_DATABASE", "subsitech"),
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "subsitech-dev-secret")


def get_db():
    if mysql is None:
        raise RuntimeError(
            "MySQL connector is not installed. Run `pip install mysql-connector-python` first."
        )
    if "db" not in g:
        g.db = mysql.connector.connect(**DB_CONFIG)
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def execute_write(sql: str, params: tuple[Any, ...] = ()) -> int:
    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def get_student_profile(user_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT s.*
        FROM students s
        WHERE s.user_id = %s
        """,
        (user_id,),
    )


def split_name(full_name: str | None) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def get_donor_profile(user_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT d.*
        FROM donors d
        WHERE d.user_id = %s
        """,
        (user_id,),
    )


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return fetch_one(
        """
        SELECT
            u.id,
            u.email,
            u.role,
            u.is_active,
            COALESCE(s.full_name, d.contact_person_name, SUBSTRING_INDEX(u.email, '@', 1)) AS full_name,
            d.organization_name,
            d.account_type
        FROM users u
        LEFT JOIN students s ON s.user_id = u.id
        LEFT JOIN donors d ON d.user_id = u.id
        WHERE u.id = %s
        """,
        (user_id,),
    )


def login_required(role: str | None = None):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("Please sign in to continue.", "error")
                return redirect(url_for("student_login_page"))
            if role and user["role"] != role:
                flash("You do not have access to that page.", "error")
                target = "student_dashboard_page" if user["role"] == "student" else "donor_dashboard_page"
                return redirect(url_for(target))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def format_status(status: str | None) -> str:
    mapping = {
        "draft": "Draft",
        "submitted": "In Review",
        "in_review": "In Review",
        "approved": "Completed",
        "completed": "Completed",
        "rejected": "Rejected",
    }
    return mapping.get(status or "", (status or "").replace("_", " ").title())


def format_inr(amount: int | float | Decimal | None) -> str:
    numeric = Decimal(amount or 0)
    if numeric == numeric.to_integral():
        value = f"{int(numeric):,}"
    else:
        value = f"{numeric:,.2f}"
    return f"Rs {value}"


def ensure_category(name: str) -> int:
    category = fetch_one("SELECT id FROM categories WHERE name = %s", (name,))
    if category:
        return int(category["id"])
    return execute_write(
        "INSERT INTO categories (name, description) VALUES (%s, %s)",
        (name, f"{name} opportunities on Subsitech."),
    )


def query_schemes(limit: int | None = None, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    conditions = ["s.status = 'open'"]
    params: list[Any] = []

    if filters.get("q"):
        conditions.append("(s.title LIKE %s OR c.name LIKE %s OR d.organization_name LIKE %s)")
        term = f"%{filters['q']}%"
        params.extend([term, term, term])
    if filters.get("category"):
        conditions.append("c.name = %s")
        params.append(filters["category"])

    sql = f"""
        SELECT
            s.id,
            s.title,
            c.name AS category,
            s.target_audience,
            s.budget,
            DATE_FORMAT(s.deadline, '%%Y-%%m-%%d') AS deadline,
            s.description,
            s.eligibility,
            d.organization_name
        FROM schemes s
        JOIN categories c ON c.id = s.category_id
        JOIN donors d ON d.id = s.donor_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.deadline ASC, s.id DESC
    """
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    return fetch_all(sql, tuple(params))


def get_student_applications(user_id: int) -> list[dict[str, Any]]:
    student = get_student_profile(user_id)
    if student is None:
        return []

    rows = fetch_all(
        """
        SELECT
            a.id,
            a.status AS raw_status,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%%Y-%%m-%%d %%H:%%i:%%s') AS submitted_at,
            DATE_FORMAT(s.deadline, '%%Y-%%m-%%d') AS deadline,
            s.title,
            s.budget
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        WHERE a.student_id = %s
        ORDER BY COALESCE(a.submitted_at, a.created_at) DESC, a.id DESC
        """,
        (student["id"],),
    )
    for row in rows:
        row["status"] = format_status(row.pop("raw_status", None))
    return rows


def get_student_stats(user_id: int) -> dict[str, Any]:
    student = get_student_profile(user_id)
    empty_totals = {"received_total": 0, "total_applications": 0, "pending_count": 0}
    if student is None:
        return {"totals": empty_totals, "next_scheme": None}

    totals = fetch_one(
        """
        SELECT
            COALESCE(SUM(CASE WHEN a.status IN ('approved', 'completed') THEN s.budget ELSE 0 END), 0) AS received_total,
            COUNT(*) AS total_applications,
            SUM(CASE WHEN a.status IN ('draft', 'submitted', 'in_review') THEN 1 ELSE 0 END) AS pending_count
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        WHERE a.student_id = %s
        """,
        (student["id"],),
    ) or empty_totals

    next_scheme = fetch_one(
        """
        SELECT
            s.title,
            s.budget,
            DATE_FORMAT(s.deadline, '%%Y-%%m-%%d') AS deadline
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        WHERE a.student_id = %s
          AND a.status IN ('draft', 'submitted', 'in_review')
        ORDER BY s.deadline ASC
        LIMIT 1
        """,
        (student["id"],),
    )
    return {"totals": totals, "next_scheme": next_scheme}


def get_donor_stats(user_id: int) -> dict[str, Any]:
    donor = get_donor_profile(user_id)
    empty_summary = {"budget_total": 0, "active_programs": 0}
    if donor is None:
        return {
            "summary": empty_summary,
            "pending_reviews": 0,
            "programs": [],
            "recent_disbursements": [],
        }

    summary = fetch_one(
        """
        SELECT
            COALESCE(SUM(budget), 0) AS budget_total,
            SUM(CASE WHEN status IN ('draft', 'open') THEN 1 ELSE 0 END) AS active_programs
        FROM schemes
        WHERE donor_id = %s
        """,
        (donor["id"],),
    ) or empty_summary

    review_count = fetch_one(
        """
        SELECT COUNT(*) AS pending_reviews
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        WHERE s.donor_id = %s
          AND a.status IN ('submitted', 'in_review')
        """,
        (donor["id"],),
    ) or {"pending_reviews": 0}

    programs = fetch_all(
        """
        SELECT
            s.id,
            s.title,
            s.budget,
            COUNT(a.id) AS application_count
        FROM schemes s
        LEFT JOIN applications a ON a.scheme_id = s.id
        WHERE s.donor_id = %s
        GROUP BY s.id, s.title, s.budget
        ORDER BY s.deadline ASC, s.id DESC
        LIMIT 6
        """,
        (donor["id"],),
    )

    recent_rows = fetch_all(
        """
        SELECT
            st.full_name,
            a.status AS raw_status,
            s.title,
            s.budget
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        JOIN students st ON st.id = a.student_id
        WHERE s.donor_id = %s
        ORDER BY COALESCE(a.submitted_at, a.created_at) DESC, a.id DESC
        LIMIT 5
        """,
        (donor["id"],),
    )

    recent_disbursements = []
    for row in recent_rows:
        full_name = row.get("full_name") or "Student"
        parts = full_name.split()
        recent_disbursements.append(
            {
                "first_name": parts[0],
                "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
                "title": row["title"],
                "budget": row["budget"],
                "status": format_status(row.get("raw_status")),
            }
        )

    return {
        "summary": summary,
        "pending_reviews": review_count["pending_reviews"],
        "programs": programs,
        "recent_disbursements": recent_disbursements,
    }


def get_account_history_rows(user_id: int, date_from: str = "") -> list[dict[str, Any]]:
    student = get_student_profile(user_id)
    if student is None:
        return []

    conditions = ["a.student_id = %s", "a.status IN ('approved', 'completed', 'in_review', 'submitted')"]
    params: list[Any] = [student["id"]]
    if date_from:
        conditions.append("DATE(COALESCE(a.submitted_at, a.created_at)) >= %s")
        params.append(date_from)

    rows = fetch_all(
        f"""
        SELECT
            a.id,
            a.status AS raw_status,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%%b %%d, %%Y') AS display_date,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%%Y-%%m-%%d') AS sort_date,
            s.title,
            s.budget
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        WHERE {' AND '.join(conditions)}
        ORDER BY COALESCE(a.submitted_at, a.created_at) DESC
        """,
        tuple(params),
    )
    for row in rows:
        row["status"] = format_status(row.pop("raw_status", None))
    return rows


def get_donor_review_applications(user_id: int, category_filter: str = "") -> list[dict[str, Any]]:
    donor = get_donor_profile(user_id)
    if donor is None:
        return []

    conditions = ["s.donor_id = %s", "a.status IN ('submitted', 'in_review', 'approved', 'rejected', 'completed')"]
    params: list[Any] = [donor["id"]]
    if category_filter:
        conditions.append("c.name = %s")
        params.append(category_filter)

    rows = fetch_all(
        f"""
        SELECT
            a.id,
            a.status AS raw_status,
            st.full_name,
            st.annual_income,
            st.education_level,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%%Y-%%m-%%d') AS submitted_at,
            s.title,
            c.name AS category
        FROM applications a
        JOIN schemes s ON s.id = a.scheme_id
        JOIN categories c ON c.id = s.category_id
        JOIN students st ON st.id = a.student_id
        WHERE {' AND '.join(conditions)}
        ORDER BY COALESCE(a.submitted_at, a.created_at) DESC
        """,
        tuple(params),
    )
    for index, row in enumerate(rows):
        income = Decimal(row.get("annual_income") or 0)
        row["status"] = format_status(row.pop("raw_status", None))
        row["match_score"] = min(99, max(72, 96 - (index * 4)))
        row["gpa_text"] = row.get("education_level") or "Student Profile"
        row["income_text"] = format_inr(income)
    return rows


def get_donor_settings_profile(user_id: int) -> dict[str, Any]:
    donor = get_donor_profile(user_id) or {}
    return {
        "organization_name": donor.get("organization_name") or "",
        "bio": donor.get("bio") or "",
        "website": donor.get("website") or "",
        "headquarters": ", ".join(
            [part for part in [donor.get("city"), donor.get("state"), donor.get("country")] if part]
        ),
    }


def make_csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.context_processor
def inject_globals() -> dict[str, Any]:
    user = current_user()
    return {
        "current_user": user,
        "student_stats": get_student_stats(user["id"]) if user and user["role"] == "student" else None,
        "donor_stats": get_donor_stats(user["id"]) if user and user["role"] == "donor" else None,
    }


def init_db() -> None:
    connection = get_db()
    cursor = connection.cursor(dictionary=True)
    try:
        categories = [
            ("Education", "Support for academic growth and scholarships."),
            ("Business", "Funding for startups, entrepreneurship, and innovation."),
            ("Arts & Culture", "Programs for creative, cultural, and heritage work."),
        ]
        cursor.executemany(
            "INSERT IGNORE INTO categories (name, description) VALUES (%s, %s)",
            categories,
        )

        cursor.execute("SELECT id FROM users WHERE email = %s", ("admin@foundation.org",))
        donor_user = cursor.fetchone()
        if donor_user is None:
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, role, is_active)
                VALUES (%s, %s, 'donor', 1)
                """,
                ("admin@foundation.org", generate_password_hash("donor123")),
            )
            donor_user_id = cursor.lastrowid
        else:
            donor_user_id = donor_user["id"]

        cursor.execute("SELECT id FROM donors WHERE user_id = %s", (donor_user_id,))
        donor_profile = cursor.fetchone()
        if donor_profile is None:
            cursor.execute(
                """
                INSERT INTO donors
                (user_id, contact_person_name, organization_name, account_type, organization_type, city, state, country, bio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    donor_user_id,
                    "Sarah Miller",
                    "Global Reach Foundation",
                    "Corporate/Org",
                    "Foundation",
                    "Bengaluru",
                    "Karnataka",
                    "India",
                    "Focused on expanding access to scholarships, innovation, and community grants.",
                ),
            )
            donor_profile_id = cursor.lastrowid
        else:
            donor_profile_id = donor_profile["id"]

        cursor.execute("SELECT id FROM users WHERE email = %s", ("student@example.com",))
        student_user = cursor.fetchone()
        if student_user is None:
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, role, is_active)
                VALUES (%s, %s, 'student', 1)
                """,
                ("student@example.com", generate_password_hash("student123")),
            )
            student_user_id = cursor.lastrowid
        else:
            student_user_id = student_user["id"]

        cursor.execute("SELECT id FROM students WHERE user_id = %s", (student_user_id,))
        student_profile = cursor.fetchone()
        if student_profile is None:
            cursor.execute(
                """
                INSERT INTO students
                (user_id, full_name, phone, date_of_birth, gender, address, city, state, country, education_level, institution_name, annual_income, bio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_user_id,
                    "Alex Johnson",
                    "+91 9876543210",
                    "2004-06-14",
                    "Other",
                    "12 Green Street",
                    "Bengaluru",
                    "Karnataka",
                    "India",
                    "Undergraduate",
                    "City University",
                    280000,
                    "Aspiring computer science student interested in scholarships and civic innovation.",
                ),
            )
            student_profile_id = cursor.lastrowid
        else:
            student_profile_id = student_profile["id"]

        cursor.execute("SELECT COUNT(*) AS total FROM schemes")
        scheme_total = cursor.fetchone()["total"]
        if scheme_total == 0:
            category_map = {
                row["name"]: row["id"]
                for row in fetch_all("SELECT id, name FROM categories")
            }
            today = date.today()
            schemes = [
                (
                    donor_profile_id,
                    category_map["Education"],
                    "STEM Excellence Grant 2026",
                    "Undergraduates",
                    50000,
                    (today + timedelta(days=10)).isoformat(),
                    "Supporting undergraduate students in science, technology, engineering, and mathematics.",
                    "GPA above 3.5, annual household income under Rs 600000, and full-time enrollment.",
                    "Mentorship access and academic support.",
                    25,
                    "open",
                ),
                (
                    donor_profile_id,
                    category_map["Business"],
                    "Startup Seed Subsidy",
                    "Startup Founders",
                    200000,
                    (today + timedelta(days=18)).isoformat(),
                    "Financial backing for early-stage social impact startups in rural communities.",
                    "Founder-led team, working prototype, and rural impact focus.",
                    "Seed capital with donor feedback rounds.",
                    10,
                    "open",
                ),
                (
                    donor_profile_id,
                    category_map["Arts & Culture"],
                    "Arts and Culture Fellowship",
                    "Postgraduates",
                    75000,
                    (today + timedelta(days=26)).isoformat(),
                    "Funding for creators preserving local arts, language, and cultural storytelling.",
                    "Portfolio submission and community outreach plan required.",
                    "Project grant and presentation opportunity.",
                    12,
                    "open",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO schemes
                (donor_id, category_id, title, target_audience, budget, deadline, description, eligibility, benefits, total_slots, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                schemes,
            )

        cursor.execute("SELECT COUNT(*) AS total FROM applications")
        application_total = cursor.fetchone()["total"]
        if application_total == 0:
            scheme_ids = fetch_all("SELECT id, title FROM schemes ORDER BY id ASC LIMIT 2")
            if len(scheme_ids) >= 2:
                cursor.execute(
                    """
                    INSERT INTO applications
                    (scheme_id, student_id, status, statement_of_purpose, submitted_at)
                    VALUES (%s, %s, 'completed', %s, %s)
                    """,
                    (
                        scheme_ids[0]["id"],
                        student_profile_id,
                        "Seeking support to continue advanced STEM coursework.",
                        "2026-03-12 10:30:00",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO applications
                    (scheme_id, student_id, status, statement_of_purpose, submitted_at)
                    VALUES (%s, %s, 'in_review', %s, %s)
                    """,
                    (
                        scheme_ids[1]["id"],
                        student_profile_id,
                        "Building a rural community startup and need prototype funding.",
                        "2026-04-05 09:15:00",
                    ),
                )

        connection.commit()
    finally:
        cursor.close()


app.jinja_env.filters["inr"] = format_inr


@app.route("/")
def home() -> str:
    return render_template("index.html", featured_schemes=query_schemes(limit=3))


@app.route("/profile")
def profile_hub() -> Any:
    user = current_user()
    if user is None:
        flash("Please log in first to open your profile.", "error")
        return redirect(url_for("student_login_page"))
    if user["role"] == "donor":
        return redirect(url_for("donor_dashboard_page"))
    return redirect(url_for("student_dashboard_page"))


@app.route("/index.html")
def home_page() -> str:
    return redirect(url_for("home"))


@app.route("/signup.html")
def signup_page() -> str:
    return render_template("signup.html")


@app.route("/login-student.html")
def student_login_page() -> str:
    return render_template("login-student.html")


@app.route("/login-donor.html")
def donor_login_page() -> str:
    return render_template("login-donor.html")


@app.route("/student-dashboard.html")
@login_required("student")
def student_dashboard_page() -> str:
    user = current_user()
    apps = get_student_applications(user["id"])
    return render_template("student-dashboard.html", applications=apps)


@app.route("/search-dashboard.html")
@login_required("student")
def search_dashboard_page() -> str:
    filters = {"q": request.args.get("q", "").strip(), "category": request.args.get("category", "").strip()}
    schemes = query_schemes(filters=filters)
    return render_template("search-dashboard.html", schemes=schemes, filters=filters)


@app.route("/track-status.html")
@login_required("student")
def track_status_page() -> str:
    user = current_user()
    applications = get_student_applications(user["id"])
    latest_application = applications[0] if applications else None
    return render_template("track-status.html", application=latest_application)


@app.route("/account-history.html")
@login_required("student")
def account_history_page() -> str:
    user = current_user()
    date_from = request.args.get("date_from", "").strip()
    history_rows = get_account_history_rows(user["id"], date_from)
    total_disbursed = sum(Decimal(row["budget"] or 0) for row in history_rows if row["status"] == "Completed")
    pending_disbursement = sum(
        Decimal(row["budget"] or 0) for row in history_rows if row["status"] in {"In Review", "Draft"}
    )
    next_payment = next((row for row in history_rows if row["status"] in {"In Review", "Draft"}), None)
    return render_template(
        "account-history.html",
        history_rows=history_rows,
        history_filters={"date_from": date_from},
        history_summary={
            "total_disbursed": total_disbursed,
            "pending_disbursement": pending_disbursement,
            "next_payment": Decimal(next_payment["budget"]) if next_payment else Decimal(0),
        },
    )


@app.route("/account-settings.html")
@login_required("student")
def account_settings_page() -> str:
    user = current_user()
    student = get_student_profile(user["id"]) or {}
    first_name, last_name = split_name(student.get("full_name") or user.get("full_name"))
    profile = {
        "first_name": first_name,
        "last_name": last_name,
        "email": user.get("email", ""),
        "phone": student.get("phone") or "",
        "bio": student.get("bio") or "",
        "institution_name": student.get("institution_name") or "",
        "education_level": student.get("education_level") or "",
        "annual_income": student.get("annual_income") or "",
        "address": student.get("address") or "",
    }
    return render_template("account-settings.html", profile=profile)


@app.route("/donor-dashboard.html")
@login_required("donor")
def donor_dashboard_page() -> str:
    return render_template("donor-dashboard.html")


@app.route("/donor-review-applications.html")
@login_required("donor")
def donor_review_applications_page() -> str:
    program_filter = request.args.get("program", "").strip()
    applications = get_donor_review_applications(current_user()["id"], program_filter)
    return render_template(
        "donor-review-applications.html",
        review_applications=applications,
        review_filters={"program": program_filter},
    )


@app.route("/donor-impact-reports.html")
@login_required("donor")
def donor_impact_reports_page() -> str:
    return render_template("donor-impact-reports.html")


@app.route("/donor-settings.html")
@login_required("donor")
def donor_settings_page() -> str:
    return render_template("donor-settings.html", donor_profile=get_donor_settings_profile(current_user()["id"]))


@app.route("/donor-create-scheme.html")
@login_required("donor")
def donor_create_scheme_page() -> str:
    return render_template("donor-create-scheme.html")


@app.route("/search.html")
def search_page() -> str:
    filters = {"q": request.args.get("q", "").strip(), "category": request.args.get("category", "").strip()}
    schemes = query_schemes(filters=filters)
    return render_template("search.html", schemes=schemes, filters=filters)


@app.route("/apply-scholarship.html")
@login_required("student")
def apply_scholarship_page() -> str:
    scheme_id = request.args.get("scheme_id", type=int)
    scheme = None
    if scheme_id:
        matching = query_schemes(filters={})
        scheme = next((row for row in matching if row["id"] == scheme_id), None)
    if scheme is None:
        fallback = query_schemes(limit=1)
        scheme = fallback[0] if fallback else None
    return render_template("apply-scholarship.html", scheme=scheme)


@app.route("/donor-registration.html")
def donor_registration_page() -> str:
    return render_template("donor-registration.html")


@app.route("/eligibility-checker.html")
def eligibility_checker_page() -> str:
    last_result = None
    check_id = session.get("eligibility_check_id")
    if check_id:
        last_result = fetch_one(
            """
            SELECT
                id,
                student_name,
                residency_status,
                age_range,
                academic_interest,
                match_score,
                DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') AS created_at
            FROM eligibility_checks
            WHERE id = %s
            """,
            (check_id,),
        )
    return render_template("eligibility-checker.html", last_result=last_result)


@app.route("/logout")
def logout() -> Any:
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/social-auth/<provider>")
def social_auth(provider: str) -> Any:
    provider_name = provider.replace("-", " ").title()
    flash(f"{provider_name} sign-in is not configured in this demo yet. Please use email sign-in.", "error")
    destination = request.args.get("next", "student_login_page")
    if destination not in {
        "student_login_page",
        "donor_login_page",
        "signup_page",
        "donor_registration_page",
    }:
        destination = "student_login_page"
    return redirect(url_for(destination))


@app.route("/forgot-password", methods=["POST"])
def forgot_password() -> Any:
    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Please enter your email address.", "error")
        return redirect(url_for("student_login_page"))
    flash(f"Password reset instructions have been queued for {email}.", "success")
    return redirect(url_for("student_login_page"))


@app.route("/account-history/export")
@login_required("student")
def export_account_history() -> Response:
    rows = get_account_history_rows(current_user()["id"], request.args.get("date_from", "").strip())
    data = [
        [row["display_date"], row["title"], row["budget"], row["status"]]
        for row in rows
    ]
    return make_csv_response("student-account-history.csv", ["Date", "Scheme", "Amount", "Status"], data)


@app.route("/student-dashboard/export")
@login_required("student")
def export_student_dashboard() -> Response:
    rows = get_student_applications(current_user()["id"])
    data = [[row["title"], row["submitted_at"], row["status"], row["budget"]] for row in rows]
    return make_csv_response("student-applications.csv", ["Scheme", "Submitted At", "Status", "Amount"], data)


@app.route("/account-settings", methods=["POST"])
@login_required("student")
def update_account_settings() -> Any:
    user = current_user()
    student = get_student_profile(user["id"])
    if student is None:
        flash("Your student profile could not be found.", "error")
        return redirect(url_for("account_settings_page"))

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    phone = request.form.get("phone", "").strip()
    bio = request.form.get("bio", "").strip()
    institution_name = request.form.get("institution_name", "").strip()
    education_level = request.form.get("education_level", "").strip()
    annual_income = request.form.get("annual_income", "").strip()
    address = request.form.get("address", "").strip()

    if not first_name:
        flash("First name is required.", "error")
        return redirect(url_for("account_settings_page"))

    full_name = f"{first_name} {last_name}".strip()
    income_value = None
    if annual_income:
        try:
            income_value = float(annual_income)
        except ValueError:
            flash("Annual income must be a valid number.", "error")
            return redirect(url_for("account_settings_page"))

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE students
            SET full_name = %s,
                phone = %s,
                bio = %s,
                institution_name = %s,
                education_level = %s,
                annual_income = %s,
                address = %s
            WHERE user_id = %s
            """,
            (
                full_name,
                phone or None,
                bio or None,
                institution_name or None,
                education_level or None,
                income_value,
                address or None,
                user["id"],
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    flash("Account settings updated successfully.", "success")
    return redirect(url_for("account_settings_page"))


@app.route("/donor-settings", methods=["POST"])
@login_required("donor")
def update_donor_settings() -> Any:
    user = current_user()
    organization_name = request.form.get("organization_name", "").strip()
    bio = request.form.get("bio", "").strip()
    website = request.form.get("website", "").strip()
    headquarters = request.form.get("headquarters", "").strip()

    if not organization_name:
        flash("Organization name is required.", "error")
        return redirect(url_for("donor_settings_page"))

    city = state = country = None
    if headquarters:
        pieces = [piece.strip() for piece in headquarters.split(",") if piece.strip()]
        if pieces:
            city = pieces[0]
        if len(pieces) > 1:
            state = pieces[1]
        if len(pieces) > 2:
            country = pieces[2]

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE donors
            SET organization_name = %s,
                bio = %s,
                website = %s,
                city = %s,
                state = %s,
                country = %s
            WHERE user_id = %s
            """,
            (organization_name, bio or None, website or None, city, state, country, user["id"]),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    flash("Organization settings saved.", "success")
    return redirect(url_for("donor_settings_page"))


@app.route("/signup", methods=["POST"])
def signup() -> Any:
    full_name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not full_name or not email or not password:
        flash("Please complete every required field.", "error")
        return redirect(url_for("signup_page"))

    if fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
        flash("That email is already registered. Try signing in instead.", "error")
        return redirect(url_for("student_login_page"))

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, role, is_active)
            VALUES (%s, %s, 'student', 1)
            """,
            (email, generate_password_hash(password)),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO students (user_id, full_name)
            VALUES (%s, %s)
            """,
            (user_id, full_name),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    session.clear()
    session["user_id"] = user_id
    flash("Your student account is ready.", "success")
    return redirect(url_for("student_dashboard_page"))


def handle_login(role: str, fallback: str, success: str) -> Any:
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = fetch_one(
        "SELECT id, email, password_hash, role, is_active FROM users WHERE email = %s AND role = %s",
        (email, role),
    )
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Incorrect email or password.", "error")
        return redirect(url_for(fallback))
    if not user["is_active"]:
        flash("This account is currently inactive.", "error")
        return redirect(url_for(fallback))

    profile = current_user() if session.get("user_id") == user["id"] else None
    if profile is None:
        session.clear()
        session["user_id"] = user["id"]
        profile = current_user()

    flash(f"Welcome back, {(profile.get('full_name') or 'there').split()[0]}.", "success")
    return redirect(url_for(success))


@app.route("/login/student", methods=["POST"])
def student_login() -> Any:
    return handle_login("student", "student_login_page", "student_dashboard_page")


@app.route("/login/donor", methods=["POST"])
def donor_login() -> Any:
    return handle_login("donor", "donor_login_page", "donor_dashboard_page")


@app.route("/register/donor", methods=["POST"])
def donor_register() -> Any:
    account_type = request.form.get("account_type", "Individual Donor").strip()
    full_name = request.form.get("contact_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    organization_name = request.form.get("organization_name", "").strip() or full_name

    if not full_name or not email:
        flash("Please fill in your contact name and email.", "error")
        return redirect(url_for("donor_registration_page"))

    if fetch_one("SELECT id FROM users WHERE email = %s", (email,)):
        flash("That donor email already exists. Please sign in instead.", "error")
        return redirect(url_for("donor_login_page"))

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, role, is_active)
            VALUES (%s, %s, 'donor', 1)
            """,
            (email, generate_password_hash("donor123")),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO donors (user_id, contact_person_name, organization_name, account_type)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, full_name, organization_name, account_type),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    session.clear()
    session["user_id"] = user_id
    flash("Donor profile created. A starter password of donor123 has been assigned for this demo.", "success")
    return redirect(url_for("donor_dashboard_page"))


@app.route("/donor/schemes", methods=["POST"])
@login_required("donor")
def create_scheme() -> Any:
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    target_audience = request.form.get("target_audience", "").strip()
    budget = request.form.get("budget", type=int)
    deadline = request.form.get("deadline", "").strip()
    description = request.form.get("description", "").strip()
    eligibility_items = request.form.getlist("eligibility")
    scheme_status = request.form.get("scheme_status", "open").strip()
    if scheme_status not in {"open", "draft"}:
        scheme_status = "open"

    if not all([title, category, target_audience, budget, deadline, description]) or not eligibility_items:
        flash("Please complete the scheme details before publishing.", "error")
        return redirect(url_for("donor_create_scheme_page"))

    donor = get_donor_profile(current_user()["id"])
    if donor is None:
        flash("Your donor profile is incomplete.", "error")
        return redirect(url_for("donor_dashboard_page"))

    category_id = ensure_category(category)
    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO schemes
            (donor_id, category_id, title, target_audience, budget, deadline, description, eligibility, benefits, total_slots, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                donor["id"],
                category_id,
                title,
                target_audience,
                budget,
                deadline,
                description,
                ", ".join(eligibility_items),
                "Published from donor workspace",
                25,
                scheme_status,
            ),
        )
        cursor.execute(
            """
            INSERT INTO activity_logs (user_id, activity_type, entity_type, entity_id, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                current_user()["id"],
                "scheme_created",
                "scheme",
                cursor.lastrowid,
                f"Created {scheme_status} scheme '{title}' in {category}.",
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    flash("Scheme saved as draft." if scheme_status == "draft" else "Funding round published successfully.", "success")
    return redirect(url_for("donor_dashboard_page"))


@app.route("/schemes/<int:scheme_id>/apply", methods=["POST"])
@login_required("student")
def apply_for_scheme(scheme_id: int) -> Any:
    user = current_user()
    student = get_student_profile(user["id"])
    if student is None:
        flash("Your student profile is incomplete.", "error")
        return redirect(url_for("student_dashboard_page"))

    existing = fetch_one(
        "SELECT id FROM applications WHERE scheme_id = %s AND student_id = %s",
        (scheme_id, student["id"]),
    )
    if existing:
        flash("You have already applied for this scheme.", "error")
        return redirect(url_for("track_status_page"))

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    dob = request.form.get("date_of_birth", "").strip()
    gender = request.form.get("gender", "").strip()
    address = request.form.get("address", "").strip()

    if not first_name or not last_name or not address:
        flash("Please complete the personal information section.", "error")
        return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))

    full_name = f"{first_name} {last_name}".strip()
    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            UPDATE students
            SET full_name = %s,
                date_of_birth = NULLIF(%s, ''),
                gender = %s,
                address = %s
            WHERE id = %s
            """,
            (full_name, dob, gender, address, student["id"]),
        )
        cursor.execute(
            """
            INSERT INTO applications
            (scheme_id, student_id, status, statement_of_purpose)
            VALUES (%s, %s, 'submitted', %s)
            """,
            (
                scheme_id,
                student["id"],
                f"{full_name} applied through the scholarship form on Subsitech.",
            ),
        )
        application_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (%s, %s, %s, 0)
            """,
            (
                user["id"],
                "Application Submitted",
                "Your scholarship application has been submitted and is now under review.",
            ),
        )
        cursor.execute(
            """
            INSERT INTO activity_logs (user_id, activity_type, entity_type, entity_id, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                user["id"],
                "application_submitted",
                "application",
                application_id,
                f"Submitted application for scheme #{scheme_id}.",
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    flash("Application submitted. Nice work.", "success")
    return redirect(url_for("track_status_page"))


@app.route("/schemes/<int:scheme_id>/save-progress", methods=["POST"])
@login_required("student")
def save_application_progress(scheme_id: int) -> Any:
    flash("Application progress saved for later. Return when you're ready to submit.", "success")
    return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))


@app.route("/eligibility-save", methods=["POST"])
def save_eligibility_progress() -> Any:
    session["eligibility_draft"] = {
        "student_name": request.form.get("student_name", "").strip(),
        "residency_status": request.form.get("residency_status", "").strip(),
        "age_range": request.form.get("age_range", "").strip(),
        "academic_interest": request.form.get("academic_interest", "").strip(),
    }
    flash("Eligibility details saved for later.", "success")
    return redirect(url_for("eligibility_checker_page"))


@app.route("/eligibility-check", methods=["POST"])
def eligibility_check() -> Any:
    student_name = request.form.get("student_name", "").strip()
    residency_status = request.form.get("residency_status", "").strip()
    age_range = request.form.get("age_range", "").strip()
    academic_interest = request.form.get("academic_interest", "").strip()

    if not all([student_name, residency_status, age_range, academic_interest]):
        flash("Fill out the profile fields so we can estimate your fit.", "error")
        return redirect(url_for("eligibility_checker_page"))

    score = 58
    if residency_status == "Citizen":
        score += 14
    if age_range in {"18-24", "25-30"}:
        score += 8
    if academic_interest in {"Computer Science", "Mathematics", "Physics"}:
        score += 12
    score = min(score, 97)

    user = current_user()
    student = get_student_profile(user["id"]) if user and user["role"] == "student" else None

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO eligibility_checks
            (student_id, student_name, residency_status, age_range, academic_interest, match_score)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (student["id"] if student else None, student_name, residency_status, age_range, academic_interest, score),
        )
        check_id = cursor.lastrowid
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    session["eligibility_check_id"] = check_id
    flash("Eligibility estimate updated.", "success")
    return redirect(url_for("eligibility_checker_page"))


@app.route("/donor/review/<int:application_id>", methods=["POST"])
@login_required("donor")
def review_application(application_id: int) -> Any:
    decision = request.form.get("decision", "approved").strip()
    status_map = {"approve": "approved", "reject": "rejected", "complete": "completed"}
    new_status = status_map.get(decision, "approved")

    connection = get_db()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE applications SET status = %s, reviewed_at = NOW() WHERE id = %s", (new_status, application_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()

    flash(f"Application #{application_id} marked as {format_status(new_status)}.", "success")
    return redirect(url_for("donor_review_applications_page"))


@app.route("/donor-impact-reports/export")
@login_required("donor")
def export_donor_impact_report() -> Response:
    donor_stats = get_donor_stats(current_user()["id"])
    data = [
        ["Total Grant Budget", donor_stats["summary"]["budget_total"], "", ""],
        ["Active Programs", donor_stats["summary"]["active_programs"], "", ""],
        ["Applications To Review", donor_stats["pending_reviews"], "", ""],
    ]
    for item in donor_stats["recent_disbursements"]:
        data.append([f"Recent - {item['first_name']} {item['last_name']}".strip(), item["title"], item["budget"], item["status"]])
    return make_csv_response("donor-impact-report.csv", ["Metric", "Value", "Amount", "Status"], data)


@app.route("/<path:page_name>")
def static_page(page_name: str) -> Any:
    if page_name not in PAGE_TEMPLATES:
        return "Page not found", 404

    if page_name == "search.html":
        return redirect(url_for("search_page"))
    if page_name == "apply-scholarship.html":
        return redirect(url_for("apply_scholarship_page"))
    if page_name == "donor-registration.html":
        return redirect(url_for("donor_registration_page"))
    if page_name == "eligibility-checker.html":
        return redirect(url_for("eligibility_checker_page"))
    if page_name == "signup.html":
        return redirect(url_for("signup_page"))
    if page_name == "login-student.html":
        return redirect(url_for("student_login_page"))
    if page_name == "login-donor.html":
        return redirect(url_for("donor_login_page"))

    return render_template(page_name)


with app.app_context():
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - startup guard for missing local DB setup
        app.logger.warning("Database initialization skipped: %s", exc)


if __name__ == "__main__":
    app.run(debug=True)
