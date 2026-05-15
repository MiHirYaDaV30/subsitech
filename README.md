# 🎓 SubsiTech

A centralized financial assistance platform connecting students, founders, donors, and organizations through a transparent and structured subsidy ecosystem.

---

## 👥 Team Details

### Team Members

| Name |
|---|
| Mihir Yadav |
| Sakshi Yelpale |
| Yugandhar Kasar |
| Shravani Patil |

---

## 📖 Overview

SubsiTech is a web-based platform developed using Flask and MySQL that helps students and aspiring founders discover and apply for scholarships, grants, and subsidy programs in one place.

Many deserving students and innovators struggle to access financial support because information is scattered, eligibility criteria are unclear, and application procedures are complicated. At the same time, organizations and donors often lack a reliable platform to reach genuine beneficiaries.

SubsiTech solves this problem by providing a unified platform where seekers can apply for opportunities while organizations can manage and review applications efficiently.

---

## ✨ Key Features

### 👨‍🎓 Student Portal

| Feature | Description |
|---|---|
| Scholarship Discovery | Browse scholarships, grants, and subsidy programs |
| Eligibility Check | Verify eligibility before applying |
| Application System | Submit SOPs and upload required documents |
| Application Tracking | Track application status in real time |
| Profile Management | Manage academic, income, and personal details |

---

### 🏢 Donor & Organization Portal

| Feature | Description |
|---|---|
| Scheme Management | Create and manage funding programs |
| Application Review | Review and filter applications |
| Candidate Analysis | Analyze applicants based on eligibility |
| Impact Tracking | Monitor active schemes and fund distribution |

---

## 🏗️ System Architecture

SubsiTech follows a monolithic web application architecture built around Flask and MySQL.

### Architecture Layers

| Layer | Technologies Used |
|---|---|
| Frontend | HTML5, CSS3, JavaScript |
| Backend | Flask (Python) |
| Database | MySQL |
| Template Engine | Jinja2 |
| Document Processing | PyPDF2, pdfkit, python-docx |
| Image Handling | Pillow |

---

## 🛠️ Tech Stack

| Category | Technology |
|---|---|
| Backend Framework | Flask |
| Programming Language | Python |
| Database | MySQL |
| Frontend | HTML, CSS, JavaScript |
| Template Engine | Jinja2 |
| Database Connector | mysql-connector-python |
| Document Handling | PyPDF2, pdfkit, python-docx |
| Image Processing | Pillow |

---

## 📦 Requirements

Install the following dependencies before running the project:

```txt
Flask
mysql-connector-python
PyPDF2
pdfkit
python-docx
Pillow
```

Install all dependencies using:

```bash
pip install -r requirements.txt
```

---

## 📂 Project Structure

```bash
SubsiTech/
│
├── static/
│   ├── css/
│   ├── js/
│   └── uploads/
│
├── templates/
│   ├── auth/
│   ├── student/
│   └── donor/
│
├── database/
│   └── schema.sql
│
├── app.py
├── config.py
├── requirements.txt
└── README.md
```

---

# 🚀 Setup & Installation

## 1. Clone the Repository

```bash
git clone https://github.com/MiHirYaDaV30/subsitech.git
cd subsitech
```

---

## 2. Create Virtual Environment

```bash
python -m venv venv
```

### Activate Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / macOS

```bash
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Database

Create a MySQL database:

```sql
CREATE DATABASE subsitech;
```

Update your database credentials inside:

```bash
config.py
```

---

## 5. Run the Application

```bash
python app.py
```

Open in browser:

```bash
http://127.0.0.1:5000
```

---

## 📌 Future Enhancements

- AI-based scholarship recommendation system
- Multilingual platform support
- Mobile application support
- Aadhaar verification integration
- Analytics dashboard
- Smart notification system
- Cloud deployment support

---

## 🎯 Vision

SubsiTech aims to ensure that financial limitations never become a barrier to education, innovation, and opportunity.
