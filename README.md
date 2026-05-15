````md
# 🎓 SubsiTech

> **Bridging the gap between financial assistance providers and deserving students through a transparent and intelligent subsidy platform.**

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Backend-Flask-black?style=flat-square&logo=flask)
![MySQL](https://img.shields.io/badge/Database-MySQL-orange?style=flat-square&logo=mysql)
![HTML](https://img.shields.io/badge/Frontend-HTML5-E34F26?style=flat-square&logo=html5)
![CSS](https://img.shields.io/badge/Styling-CSS3-1572B6?style=flat-square&logo=css3)
![JavaScript](https://img.shields.io/badge/Frontend-JavaScript-yellow?style=flat-square&logo=javascript)

---

# 📖 Project Overview

**SubsiTech** is a centralized financial assistance platform built using **Python (Flask)** and **MySQL** that connects **Students / Founders** with **Donors / Organizations** offering scholarships, grants, and subsidies.

The platform simplifies the discovery, eligibility checking, application, and management of educational and financial support programs through a transparent and structured ecosystem.

Many financially disadvantaged students in India struggle to access available scholarships and subsidies due to:

- Lack of awareness
- Scattered information
- Complex eligibility criteria
- Lengthy application processes

Additionally, donors and organizations willing to support education often lack a transparent and reliable platform to connect with genuine beneficiaries, resulting in underutilized funds and missed opportunities for students.

SubsiTech bridges this gap by creating a reliable digital platform for both seekers and providers.

---

# ✨ Core Features

## 👨‍🎓 For Students / Seekers

### 🔍 Discovery Portal
- Browse active scholarships, grants, and subsidies
- Explore categories such as:
  - Education
  - Business / Startups
  - Arts & Culture

### 📝 Application System
- Check eligibility criteria before applying
- Submit Statements of Purpose (SOPs)
- Upload required documents securely

### 📊 Dashboard
Track application progress in real time:
- Draft
- Submitted
- In Review
- Approved
- Rejected

### 👤 Profile Management
Maintain:
- Academic details
- Income information
- Institutional information
- Personal verification details

---

## 🏢 For Donors / Organizations

### 💰 Scheme Management
Create and publish funding programs with:
- Budget allocation
- Deadlines
- Eligibility rules
- Funding categories

Examples:
- STEM Excellence Grant
- Startup Seed Subsidy

### 📋 Review Portal
- Review incoming applications
- Analyze automated match scores
- Filter candidates based on:
  - GPA
  - Financial background
  - Eligibility criteria

### 📈 Impact Tracking
- Monitor active programs
- Track fund disbursement
- Manage organization profiles

---

# 🏗️ System Architecture

SubsiTech follows a monolithic web application architecture centered around Flask and MySQL.

## Architecture Components

### Frontend Layer
- HTML5
- CSS3
- JavaScript
- Jinja2 Templating Engine

### Backend Layer
- Python Flask Framework
- REST-like route handling
- Business logic processing
- File upload management

### Database Layer
- MySQL Database
- Raw SQL queries using `mysql-connector-python`

### Document Processing
Supports handling:
- PDFs
- Images
- Word Documents

Libraries used:
- PyPDF2
- pdfkit
- python-docx
- Pillow

---

# 🛠️ Tech Stack

| Component | Technology |
|-----------|-------------|
| Backend | Flask (Python) |
| Database | MySQL |
| Frontend | HTML, CSS, JavaScript |
| Templating | Jinja2 |
| Database Connector | mysql-connector-python |
| Document Processing | PyPDF2, pdfkit, python-docx |
| Image Handling | Pillow |

---

# 📂 Project Structure

```bash
SubsiTech/
│
├── static/
│   ├── css/
│   ├── js/
│   └── uploads/
│
├── templates/
│   ├── student/
│   ├── donor/
│   └── auth/
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

# 🚀 Getting Started

## 📋 Prerequisites

Before running the project, make sure you have:

- Python 3.9+
- MySQL Server
- Git

---

# ⚙️ Installation

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/MiHirYaDaV30/subsitech.git
cd subsitech
```

---

## 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

Activate virtual environment:

### Windows
```bash
venv\Scripts\activate
```

### Linux / Mac
```bash
source venv/bin/activate
```

---

## 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4️⃣ Configure Database

Create a MySQL database:

```sql
CREATE DATABASE subsitech;
```

Update database credentials inside:

```bash
config.py
```

---

## 5️⃣ Run the Application

```bash
python app.py
```

Open in browser:

```bash
http://127.0.0.1:5000
```

---

# 📌 Future Enhancements

- 🤖 AI-based scholarship recommendation system
- 🌐 Multilingual support
- 📱 Mobile application
- 🔐 Aadhaar / institutional verification
- 📊 Analytics dashboard
- 📨 Smart notification system
- ☁️ Cloud deployment support

---

# 👥 Project Team

- Mihir Yadav
- Sakshi Yelpale
- Yugandhar Kasar
- Shravani Patil

---

# Vision

SubsiTech aims to ensure that financial limitations never become a barrier to education, innovation, and opportunity.
````
