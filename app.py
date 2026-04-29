from __future__ import annotations

import os
from io import StringIO
import csv
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any
from pathlib import Path
import secrets

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:  # pragma: no cover - handled at runtime
    mysql = None
    MySQLError = Exception

try:
    from PIL import Image
    import pdfkit
    from docx import Document
    import PyPDF2
except ImportError:
    Image = None
    pdfkit = None
    Document = None
    PyPDF2 = None


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

# Document upload configuration
UPLOADS_FOLDER = Path(__file__).parent / "uploads" / "documents"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "docx", "doc"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per file
MAX_REQUEST_SIZE = 50 * 1024 * 1024  # 50MB total request size (for multiple files)

# Create uploads folder if it doesn't exist
UPLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "subsitech-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_SIZE


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
            DATE_FORMAT(s.deadline, '%Y-%m-%d') AS deadline,
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
            a.scheme_id,
            a.status AS raw_status,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%Y-%m-%d %H:%i:%S') AS submitted_at,
            DATE_FORMAT(s.deadline, '%Y-%m-%d') AS deadline,
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
        row["status"] = format_status(row.get("raw_status"))
    return rows


def get_user_notifications(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT
            id,
            title,
            message,
            is_read,
            DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%S') AS created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, limit),
    )


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
            DATE_FORMAT(s.deadline, '%Y-%m-%d') AS deadline
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
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%b %d, %Y') AS display_date,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%Y-%m-%d') AS sort_date,
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

    conditions = ["s.donor_id = %s", "a.status IN ('submitted', 'in_review')"]
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
            st.cgpa,
            DATE_FORMAT(COALESCE(a.submitted_at, a.created_at), '%Y-%m-%d') AS submitted_at,
            s.title,
            c.name AS category,
            COALESCE((
                SELECT SUM(s2.budget)
                FROM applications a2
                JOIN schemes s2 ON s2.id = a2.scheme_id
                WHERE a2.student_id = st.id AND a2.status IN ('approved', 'completed')
            ), 0) AS total_grants_received
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
        total_grants = Decimal(row.get("total_grants_received") or 0)
        cgpa = row.get("cgpa")
        
        row["status"] = format_status(row.pop("raw_status", None))
        row["match_score"] = min(99, max(72, 96 - (index * 4)))
        row["gpa_text"] = f"CGPA: {cgpa}" if cgpa else "CGPA: Not specified"
        row["income_text"] = format_inr(income)
        row["total_grants_text"] = format_inr(total_grants)
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
    student = get_student_profile(user["id"])
    apps = get_student_applications(user["id"])
    
    # Get recommended schemes, excluding ones the student has already applied to
    all_schemes = query_schemes(limit=10)  # Get more to filter
    applied_scheme_ids = {app["scheme_id"] for app in apps}
    recommended_schemes = [scheme for scheme in all_schemes if scheme["id"] not in applied_scheme_ids][:3]
    
    notifications = get_user_notifications(user["id"])
    return render_template("student-dashboard.html", applications=apps, recommended_schemes=recommended_schemes, notifications=notifications)


@app.route("/track-status.html")
@login_required("student")
def track_status_page() -> str:
    user = current_user()
    applications = get_student_applications(user["id"])
    
    app_id = request.args.get("id", type=int)
    if app_id:
        latest_application = next((app for app in applications if app["id"] == app_id), None)
    else:
        latest_application = applications[0] if applications else None
        
    return render_template("track-status.html", application=latest_application, all_applications=applications)


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
        "city": student.get("city") or "",
        "state": student.get("state") or "",
        "country": student.get("country") or "",
        "bank_name": student.get("bank_name") or "",
        "account_holder_name": student.get("account_holder_name") or "",
        "account_number": student.get("account_number") or "",
        "ifsc_code": student.get("ifsc_code") or "",
        "account_type": student.get("account_type") or "savings",
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
@login_required("student")
def search_page() -> str:
    user = current_user()
    student = get_student_profile(user["id"]) if user else None
    
    filters = {"q": request.args.get("q", "").strip(), "category": request.args.get("category", "").strip()}
    schemes = query_schemes(filters=filters)
    
    # Check which schemes the student has already applied to
    applied_scheme_ids = set()
    if student:
        applied_applications = fetch_all(
            "SELECT scheme_id FROM applications WHERE student_id = %s",
            (student["id"],)
        )
        applied_scheme_ids = {app["scheme_id"] for app in applied_applications}
    
    # Mark schemes as applied
    for scheme in schemes:
        scheme["already_applied"] = scheme["id"] in applied_scheme_ids
    
    return render_template("search.html", schemes=schemes, filters=filters)


@app.route("/apply-scholarship.html")
@login_required("student")
def apply_scholarship_page() -> str:
    user = current_user()
    student = get_student_profile(user["id"])
    if student is None:
        flash("Your student profile is incomplete.", "error")
        return redirect(url_for("student_dashboard_page"))
    
    scheme_id = request.args.get("scheme_id", type=int)
    scheme = None
    if scheme_id:
        matching = query_schemes(filters={})
        scheme = next((row for row in matching if row["id"] == scheme_id), None)
        
        # Check if student has already applied to this scheme
        if scheme:
            existing = fetch_one(
                "SELECT id FROM applications WHERE scheme_id = %s AND student_id = %s",
                (scheme_id, student["id"]),
            )
            if existing:
                flash("You have already applied for this scheme.", "error")
                return redirect(url_for("track_status_page"))
    
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
                DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%S') AS created_at
            FROM eligibility_checks
            WHERE id = %s
            """,
            (check_id,),
        )
        
    if not last_result and "eligibility_draft" in session:
        last_result = session["eligibility_draft"]
        
    scheme_count = 0
    matched_category = ""
    if last_result and last_result.get("academic_interest"):
        interest = last_result["academic_interest"]
        if interest in ["Computer Science", "Mathematics", "Physics"]:
            matched_category = "Education"
        elif interest == "Social Impact":
            matched_category = "Arts & Culture"
        else:
            matched_category = "Business"
            
        category_row = fetch_one("SELECT id FROM categories WHERE name = %s", (matched_category,))
        if category_row:
            count_row = fetch_one("SELECT COUNT(*) as cnt FROM schemes WHERE category_id = %s AND status = 'open'", (category_row["id"],))
            scheme_count = count_row["cnt"] if count_row else 0

    return render_template("eligibility-checker.html", last_result=last_result, scheme_count=scheme_count, matched_category=matched_category)


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

    # Get form data - only update fields that were actually submitted
    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()
    phone = request.form.get("phone", "").strip()
    bio = request.form.get("bio", "").strip()
    institution_name = request.form.get("institution_name", "").strip()
    education_level = request.form.get("education_level", "").strip()
    annual_income = request.form.get("annual_income", "").strip()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "").strip()
    country = request.form.get("country", "").strip()
    bank_name = request.form.get("bank_name", "").strip()
    account_holder_name = request.form.get("account_holder_name", "").strip()
    account_number = request.form.get("account_number", "").strip()
    ifsc_code = request.form.get("ifsc_code", "").strip()
    account_type = request.form.get("account_type", "").strip()

    # Build dynamic update query - only update fields that were submitted
    update_fields = []
    update_values = []

    # Profile fields
    if first_name or last_name:
        full_name = f"{first_name} {last_name}".strip()
        update_fields.append("full_name = %s")
        update_values.append(full_name)

    if phone:
        update_fields.append("phone = %s")
        update_values.append(phone)

    if bio:
        update_fields.append("bio = %s")
        update_values.append(bio)

    if institution_name:
        update_fields.append("institution_name = %s")
        update_values.append(institution_name)

    if education_level:
        update_fields.append("education_level = %s")
        update_values.append(education_level)

    if annual_income:
        try:
            income_value = float(annual_income)
            update_fields.append("annual_income = %s")
            update_values.append(income_value)
        except ValueError:
            flash("Annual income must be a valid number.", "error")
            return redirect(url_for("account_settings_page"))

    if address:
        update_fields.append("address = %s")
        update_values.append(address)

    if city:
        update_fields.append("city = %s")
        update_values.append(city)

    if state:
        update_fields.append("state = %s")
        update_values.append(state)

    if country:
        update_fields.append("country = %s")
        update_values.append(country)

    # Bank fields
    if bank_name:
        update_fields.append("bank_name = %s")
        update_values.append(bank_name)

    if account_holder_name:
        update_fields.append("account_holder_name = %s")
        update_values.append(account_holder_name)

    if account_number:
        update_fields.append("account_number = %s")
        update_values.append(account_number)

    if ifsc_code:
        update_fields.append("ifsc_code = %s")
        update_values.append(ifsc_code)

    if account_type:
        update_fields.append("account_type = %s")
        update_values.append(account_type)

    # Only validate first_name if profile fields are being submitted
    if first_name or phone or bio or institution_name or education_level or annual_income or address or city or state or country:
        if not first_name and not student.get("full_name"):
            flash("First name is required.", "error")
            return redirect(url_for("account_settings_page"))

    # If no fields to update, just redirect
    if not update_fields:
        flash("No changes to save.", "info")
        return redirect(url_for("account_settings_page"))

    connection = get_db()
    cursor = connection.cursor()
    try:
        # Build the dynamic UPDATE query
        update_query = f"""
            UPDATE students
            SET {', '.join(update_fields)}
            WHERE user_id = %s
        """
        update_values.append(user["id"])

        cursor.execute(update_query, update_values)
        connection.commit()

        flash("Account settings updated successfully.", "success")
    except Exception as e:
        connection.rollback()
        flash(f"Error updating account settings: {str(e)}", "error")
    finally:
        cursor.close()

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


@app.route("/bank-details", methods=["GET", "POST"])
@login_required("student")
def bank_details_page() -> Any:
    user = current_user()
    student = get_student_profile(user["id"])
    if student is None:
        flash("Your student profile could not be found.", "error")
        return redirect(url_for("student_dashboard_page"))

    if request.method == "POST":
        bank_name = request.form.get("bank_name", "").strip()
        account_holder_name = request.form.get("account_holder_name", "").strip()
        account_number = request.form.get("account_number", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        account_type = request.form.get("account_type", "savings").strip()

        if not all([bank_name, account_holder_name, account_number, ifsc_code]):
            flash("Please fill in all bank details.", "error")
            return redirect(url_for("bank_details_page"))

        connection = get_db()
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT a.id, s.title FROM applications a JOIN schemes s ON a.scheme_id = s.id WHERE a.student_id = %s AND a.status = 'approved'",
                (student["id"],)
            )
            approved_apps_to_notify = cursor.fetchall()
            cursor.close()

            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE students
                SET bank_name = %s,
                    account_holder_name = %s,
                    account_number = %s,
                    ifsc_code = %s,
                    account_type = %s
                WHERE id = %s
                """,
                (bank_name, account_holder_name, account_number, ifsc_code, account_type, student["id"]),
            )
            
            # Update approved applications to 'completed' status when bank details are provided
            cursor.execute(
                """
                UPDATE applications 
                SET status = 'completed', completed_at = NOW() 
                WHERE student_id = %s AND status = 'approved'
                """,
                (student["id"],)
            )
            
            # Send notifications for the grants disbursed
            for app_info in approved_apps_to_notify:
                cursor.execute(
                    """
                    INSERT INTO notifications (user_id, title, message, is_read)
                    VALUES (%s, %s, %s, 0)
                    """,
                    (
                        user["id"],
                        "Grant Disbursed!",
                        f"Great news! The grant money for '{app_info['title']}' has been successfully disbursed to your account.",
                    )
                )
            
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

        flash("Bank details saved successfully. Your approved applications have been marked as completed and we'll process disbursements soon.", "success")
        return redirect(url_for("student_dashboard_page"))

    # Check if student has approved applications that need bank details
    approved_apps = fetch_all(
        """
        SELECT a.id, s.title, s.budget
        FROM applications a
        JOIN schemes s ON a.scheme_id = s.id
        WHERE a.student_id = %s AND a.status = 'approved'
        AND (SELECT COUNT(*) FROM students st WHERE st.id = a.student_id AND st.account_number IS NOT NULL) = 0
        """,
        (student["id"],)
    )

    return render_template("bank-details.html", approved_applications=approved_apps)


@app.route("/mark-notification-read/<int:notification_id>", methods=["POST"])
@login_required()
def mark_notification_read(notification_id: int) -> Any:
    user = current_user()
    execute_write(
        "UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s",
        (notification_id, user["id"])
    )
    return {"success": True}


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
    password = request.form.get("password", "").strip()
    organization_name = request.form.get("organization_name", "").strip() or full_name

    if not full_name or not email or not password:
        flash("Please fill in your contact name, email, and password.", "error")
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
            (email, generate_password_hash(password)),
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
    flash("Donor profile created successfully.", "success")
    return redirect(url_for("donor_dashboard_page"))


@app.route("/donor/schemes", methods=["POST"])
@login_required("donor")
def create_scheme() -> Any:
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    target_audience = request.form.get("target_audience", "").strip()
    budget = request.form.get("budget", type=int)
    total_slots = request.form.get("total_slots", type=int, default=25)
    deadline = request.form.get("deadline", "").strip()
    description = request.form.get("description", "").strip()
    min_cgpa = request.form.get("min_cgpa", type=float)
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
            (donor_id, category_id, title, target_audience, budget, deadline, description, eligibility, benefits, total_slots, status, min_cgpa)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                total_slots,
                scheme_status,
                min_cgpa,
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
    annual_income = request.form.get("annual_income", "").strip()
    cgpa = request.form.get("cgpa", "").strip()

    # Get scheme details for eligibility check
    scheme = fetch_one("SELECT min_cgpa FROM schemes WHERE id = %s", (scheme_id,))
    if scheme and scheme["min_cgpa"] and cgpa:
        if float(cgpa) < scheme["min_cgpa"]:
            flash(f"Your CGPA ({cgpa}) does not meet the minimum requirement of {scheme['min_cgpa']} for this scheme.", "error")
            return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))

    if not first_name or not last_name:
        flash("Please complete the personal information section.", "error")
        return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))

    full_name = f"{first_name} {last_name}".strip()
    connection = get_db()
    cursor = connection.cursor()
    documents_uploaded = False
    
    try:
        # Create application (DO NOT update student profile)
        cursor.execute(
            """
            INSERT INTO applications
            (scheme_id, student_id, status, statement_of_purpose, documents_uploaded)
            VALUES (%s, %s, 'submitted', %s, %s)
            """,
            (
                scheme_id,
                student["id"],
                f"{full_name} applied through the scholarship form on Subsitech.",
                documents_uploaded,
            ),
        )
        application_id = cursor.lastrowid

        # Process uploaded documents
        document_types = {
            'income_certificate': 'Income Certificate',
            'id_proof': 'ID Proof',
            'address_proof': 'Address Proof',
            'academic_records': 'Academic Records',
            'caste_certificate': 'Caste Certificate',
            'bank_proof': 'Bank Account Proof'
        }

        # Check for mandatory documents
        mandatory_docs = ['income_certificate', 'id_proof', 'address_proof', 'academic_records']
        missing_mandatory = []
        
        for field_name in mandatory_docs:
            if field_name not in request.files or not request.files[field_name].filename:
                missing_mandatory.append(document_types[field_name])

        if missing_mandatory:
            flash(f"Please upload all mandatory documents: {', '.join(missing_mandatory)}", "error")
            return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))

        for field_name, doc_type in document_types.items():
            if field_name in request.files:
                file = request.files[field_name]
                if file and file.filename and allowed_file(file.filename):
                    # Generate secure filename for original file
                    original_ext = file.filename.rsplit(".", 1)[1].lower()
                    temp_name = f"{application_id}_{secrets.token_hex(8)}_temp.{original_ext}"
                    temp_filepath = UPLOADS_FOLDER / temp_name
                    
                    # Save original file temporarily
                    file.save(temp_filepath)
                    
                    try:
                        # Convert to standard format (PDF or JPG)
                        final_ext = 'pdf' if original_ext in ['pdf', 'docx'] else 'jpg'
                        final_name = f"{application_id}_{secrets.token_hex(8)}.{final_ext}"
                        final_filepath = UPLOADS_FOLDER / final_name
                        
                        # Convert the document
                        converted_format = convert_to_standard_format(temp_filepath, final_filepath)
                        
                        # Get file size of converted file
                        file_size = final_filepath.stat().st_size
                        
                        if file_size <= MAX_FILE_SIZE:
                            # Store in database with converted file info
                            cursor.execute(
                                """INSERT INTO documents (application_id, document_type, filename, filepath, file_size, verification_status)
                                   VALUES (%s, %s, %s, %s, %s, 'pending')""",
                                (application_id, doc_type, f"{file.filename.rsplit('.', 1)[0]}.{final_ext}", str(final_filepath), file_size)
                            )
                            documents_uploaded = True
                        else:
                            flash(f"Converted file for {doc_type} is too large (max {MAX_FILE_SIZE//(1024*1024)}MB).", "error")
                            
                    except Exception as e:
                        flash(f"Failed to process {doc_type}: {str(e)}", "error")
                    finally:
                        # Clean up temporary file
                        if temp_filepath.exists():
                            temp_filepath.unlink()

        # Update documents_uploaded flag if any documents were uploaded
        if documents_uploaded:
            cursor.execute(
                "UPDATE applications SET documents_uploaded = TRUE WHERE id = %s",
                (application_id,)
            )

        # Create notification
        cursor.execute(
            """
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (%s, %s, %s, 0)
            """,
            (
                user["id"],
                "Application Submitted",
                f"Your scholarship application has been submitted with documents and is now under review.",
            ),
        )

        # Log activity
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
                f"Submitted application for scheme #{scheme_id} with documents.",
            ),
        )

        connection.commit()
    except Exception as e:
        connection.rollback()
        flash(f"Error submitting application: {str(e)}", "error")
        return redirect(url_for("apply_scholarship_page", scheme_id=scheme_id))
    finally:
        cursor.close()

    flash("Application submitted successfully! Documents uploaded and pending verification.", "success")
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
    cursor = connection.cursor(dictionary=True)
    try:
        # Get application details for notification
        cursor.execute("""
            SELECT u.id AS user_id, s.title, u.email as student_email
            FROM applications a
            JOIN schemes s ON a.scheme_id = s.id
            JOIN students st ON a.student_id = st.id
            JOIN users u ON st.user_id = u.id
            WHERE a.id = %s
        """, (application_id,))
        app_details = cursor.fetchone()
        
        cursor.execute("UPDATE applications SET status = %s, reviewed_at = NOW() WHERE id = %s", (new_status, application_id))
        
        # Send notification to student if approved or completed
        if new_status == "approved" and app_details:
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, is_read)
                VALUES (%s, %s, %s, 0)
                """,
                (
                    app_details["user_id"],
                    "Application Approved!",
                    f"Congratulations! Your application for '{app_details['title']}' has been approved. You will be contacted for disbursement details.",
                ),
            )
        elif new_status == "completed" and app_details:
            cursor.execute(
                """
                INSERT INTO notifications (user_id, title, message, is_read)
                VALUES (%s, %s, %s, 0)
                """,
                (
                    app_details["user_id"],
                    "Grant Disbursed!",
                    f"Great news! The grant money for '{app_details['title']}' has been successfully disbursed to your account.",
                ),
            )
        
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


def convert_to_standard_format(file_path: Path, output_path: Path) -> str:
    """Convert document to PDF or JPG format"""
    if not Image or not pdfkit or not Document or not PyPDF2:
        # Fallback: just copy the file if conversion libraries are not available
        import shutil
        shutil.copy2(file_path, output_path)
        return file_path.suffix.lower().lstrip('.')

    file_ext = file_path.suffix.lower()

    try:
        if file_ext in ['.pdf']:
            # PDF files are already in standard format, just copy
            import shutil
            shutil.copy2(file_path, output_path)
            return 'pdf'

        elif file_ext in ['.jpg', '.jpeg', '.png']:
            # Convert images to JPG
            if Image:
                with Image.open(file_path) as img:
                    # Convert to RGB if necessary (for PNG with transparency)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    img.save(output_path, 'JPEG', quality=85)
                return 'jpg'
            else:
                # Fallback: copy as-is
                import shutil
                shutil.copy2(file_path, output_path)
                return file_ext.lstrip('.')

        elif file_ext in ['.docx']:
            # Convert DOCX to PDF
            if pdfkit:
                pdfkit.from_file(str(file_path), str(output_path))
                return 'pdf'
            else:
                # Fallback: copy as-is
                import shutil
                shutil.copy2(file_path, output_path)
                return 'docx'

        elif file_ext in ['.doc']:
            # For DOC files, we'll need to handle them differently
            # For now, let's raise an error as DOC conversion is complex
            raise ValueError("DOC files are not supported. Please convert to DOCX or PDF.")

        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

    except Exception as e:
        # If conversion fails, copy the original file
        import shutil
        shutil.copy2(file_path, output_path)
        return file_ext.lstrip('.')


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload-document", methods=["POST"])
@login_required("student")
def upload_document() -> Any:
    """Upload a document for scholarship application"""
    user = current_user()
    if not user or user["role"] != "student":
        flash("Only students can upload documents.", "error")
        return redirect(url_for("student_login_page"))
    
    application_id = request.form.get("application_id")
    document_type = request.form.get("document_type", "").strip()
    
    if not application_id or not document_type:
        flash("Missing application ID or document type.", "error")
        return redirect(url_for("account_settings_page"))
    
    # Verify application belongs to this student
    application = fetch_one(
        "SELECT a.id FROM applications a WHERE a.id = %s AND a.student_id = (SELECT id FROM students WHERE user_id = %s)",
        (application_id, user["id"])
    )
    
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("student_dashboard_page"))
    
    if "document" not in request.files:
        flash("No file provided.", "error")
        return redirect(url_for("account_settings_page"))
    
    file = request.files["document"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("account_settings_page"))
    
    if not allowed_file(file.filename):
        flash("File type not allowed. Use: PDF, JPG, PNG, DOCX", "error")
        return redirect(url_for("account_settings_page"))
    
    try:
        # Generate secure filename for original file
        original_ext = file.filename.rsplit(".", 1)[1].lower()
        temp_name = f"{application_id}_{secrets.token_hex(8)}_temp.{original_ext}"
        temp_filepath = UPLOADS_FOLDER / temp_name
        
        # Save original file temporarily
        file.save(temp_filepath)
        
        try:
            # Convert to standard format (PDF or JPG)
            final_ext = 'pdf' if original_ext in ['pdf', 'docx'] else 'jpg'
            final_name = f"{application_id}_{secrets.token_hex(8)}.{final_ext}"
            final_filepath = UPLOADS_FOLDER / final_name
            
            # Convert the document
            converted_format = convert_to_standard_format(temp_filepath, final_filepath)
            
            # Get file size of converted file
            file_size = final_filepath.stat().st_size
            
            if file_size > MAX_FILE_SIZE:
                final_filepath.unlink()
                flash("Converted file size exceeds 5MB limit.", "error")
                return redirect(url_for("account_settings_page"))
            
            # Store in database with converted file info
            execute_write(
                """INSERT INTO documents (application_id, document_type, filename, filepath, file_size, verification_status)
                   VALUES (%s, %s, %s, %s, %s, 'pending')""",
                (application_id, document_type, f"{file.filename.rsplit('.', 1)[0]}.{final_ext}", str(final_filepath), file_size)
            )
            
            # Mark application as having documents
            execute_write(
                "UPDATE applications SET documents_uploaded = TRUE WHERE id = %s",
                (application_id,)
            )
            
        except Exception as e:
            flash(f"Failed to process document: {str(e)}", "error")
            return redirect(url_for("account_settings_page"))
        finally:
            # Clean up temporary file
            if temp_filepath.exists():
                temp_filepath.unlink()
        
        flash("Document uploaded successfully! It's pending verification.", "success")
        return redirect(url_for("account_settings_page"))
        
    except Exception as e:
        flash(f"Error uploading document: {str(e)}", "error")
        return redirect(url_for("account_settings_page"))


@app.route("/verify-document", methods=["POST"])
@login_required("donor")
def verify_document() -> Any:
    """Verify or reject a document (donor only)"""
    user = current_user()
    if not user or user["role"] != "donor":
        flash("Only donors can verify documents.", "error")
        return redirect(url_for("donor_login_page"))
    
    document_id = request.form.get("document_id")
    action = request.form.get("action")  # 'verify' or 'reject'
    rejection_reason = request.form.get("rejection_reason", "").strip()
    
    if not document_id or action not in ("verify", "reject"):
        flash("Invalid request.", "error")
        return redirect(url_for("donor_review_applications_page"))
    
    # Get document
    document = fetch_one(
        """SELECT d.* FROM documents d
           JOIN applications a ON d.application_id = a.id
           JOIN schemes s ON a.scheme_id = s.id
           WHERE d.id = %s AND s.donor_id = (SELECT id FROM donors WHERE user_id = %s)""",
        (document_id, user["id"])
    )
    
    if not document:
        flash("Document not found or not authorized.", "error")
        return redirect(url_for("donor_review_applications_page"))
    
    status = "verified" if action == "verify" else "rejected"
    
    # Update document
    execute_write(
        """UPDATE documents 
           SET verification_status = %s, verified_by = (SELECT id FROM donors WHERE user_id = %s), 
               verified_at = NOW(), rejection_reason = %s
           WHERE id = %s""",
        (status, user["id"], rejection_reason if action == "reject" else None, document_id)
    )
    
    flash(f"Document {status} successfully!", "success")
    return redirect(url_for("donor_review_applications_page"))


@app.route("/application-documents/<int:application_id>", methods=["GET"])
@login_required()
def view_application_documents(application_id: int) -> Any:
    """View documents for an application"""
    user = current_user()
    if not user:
        return redirect(url_for("student_login_page"))
    
    # Get application
    application = fetch_one(
        """SELECT a.*, s.title as scheme_title, st.full_name as student_name
           FROM applications a
           JOIN schemes s ON a.scheme_id = s.id
           JOIN students st ON a.student_id = st.id
           WHERE a.id = %s""",
        (application_id,)
    )
    
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("student_dashboard_page"))
    
    # Check authorization
    if user["role"] == "student":
        student = get_student_profile(user["id"])
        if application["student_id"] != student["id"]:
            flash("Not authorized to view this application.", "error")
            return redirect(url_for("student_dashboard_page"))
    elif user["role"] == "donor":
        donor = get_donor_profile(user["id"])
        scheme = fetch_one("SELECT donor_id FROM schemes WHERE id = %s", (application["scheme_id"],))
        if scheme["donor_id"] != donor["id"]:
            flash("Not authorized to view this application.", "error")
            return redirect(url_for("donor_review_applications_page"))
    
    # Get documents
    documents = fetch_all(
        """SELECT d.*, u.email as verified_by_email
           FROM documents d
           LEFT JOIN users u ON d.verified_by = u.id
           WHERE d.application_id = %s
           ORDER BY d.uploaded_at DESC""",
        (application_id,)
    )
    
    return render_template(
        "view-documents.html",
        application=application,
        documents=documents
    )


@app.route("/download-document/<int:document_id>", methods=["GET"])
@login_required()
def download_document(document_id: int) -> Any:
    """Download a document"""
    user = current_user()
    if not user:
        return redirect(url_for("student_login_page"))
    
    # Get document
    document = fetch_one(
        """SELECT d.* FROM documents d
           JOIN applications a ON d.application_id = a.id
           WHERE d.id = %s""",
        (document_id,)
    )
    
    if not document:
        flash("Document not found.", "error")
        return redirect(url_for("student_dashboard_page"))
    
    # Check authorization
    if user["role"] == "student":
        student = get_student_profile(user["id"])
        if document["application_id"] != student.get("id"):
            # Check if they own the application
            app_check = fetch_one(
                "SELECT student_id FROM applications WHERE id = %s",
                (document["application_id"],)
            )
            if app_check["student_id"] != student["id"]:
                flash("Not authorized to download this document.", "error")
                return redirect(url_for("student_dashboard_page"))
    elif user["role"] == "donor":
        donor = get_donor_profile(user["id"])
        app = fetch_one(
            "SELECT a.scheme_id FROM applications a WHERE a.id = %s",
            (document["application_id"],)
        )
        scheme = fetch_one("SELECT donor_id FROM schemes WHERE id = %s", (app["scheme_id"],))
        if scheme["donor_id"] != donor["id"]:
            flash("Not authorized to download this document.", "error")
            return redirect(url_for("donor_review_applications_page"))
    
    filepath = Path(document["filepath"])
    if not filepath.exists():
        flash("File not found.", "error")
        return redirect(url_for("student_dashboard_page"))
    
    return send_file(filepath, as_attachment=True, download_name=document["filename"])


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
