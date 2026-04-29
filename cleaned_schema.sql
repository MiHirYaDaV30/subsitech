-- Cleaned up Subsitech Database Schema
-- Removed unnecessary tables: student_documents, application_documents, reviews, consultations
-- These were unused (0 rows) and not referenced in the current application code

CREATE DATABASE IF NOT EXISTS subsitech
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE subsitech;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'donor', 'admin') NOT NULL,
    is_active TINYINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NULL,
    date_of_birth DATE NULL,
    gender VARCHAR(30) NULL,
    address TEXT NULL,
    city VARCHAR(100) NULL,
    state VARCHAR(100) NULL,
    country VARCHAR(100) NULL,
    education_level VARCHAR(100) NULL,
    institution_name VARCHAR(200) NULL,
    annual_income DECIMAL(12,2) NULL,
    cgpa DECIMAL(4,2) NULL,
    bio TEXT NULL,
    -- Bank details for disbursements
    bank_name VARCHAR(100) NULL,
    account_holder_name VARCHAR(100) NULL,
    account_number VARCHAR(100) NULL,
    ifsc_code VARCHAR(100) NULL,
    account_type ENUM('savings', 'current') DEFAULT 'savings',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_students_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE donors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    contact_person_name VARCHAR(150) NOT NULL,
    organization_name VARCHAR(200) NOT NULL,
    account_type VARCHAR(100) NULL,
    phone VARCHAR(30) NULL,
    website VARCHAR(255) NULL,
    organization_type VARCHAR(100) NULL,
    registration_number VARCHAR(100) NULL,
    address TEXT NULL,
    city VARCHAR(100) NULL,
    state VARCHAR(100) NULL,
    country VARCHAR(100) NULL,
    bio TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_donors_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NULL
);

CREATE TABLE schemes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    donor_id INT NOT NULL,
    category_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    target_audience VARCHAR(150) NOT NULL,
    budget DECIMAL(12,2) NOT NULL,
    deadline DATE NOT NULL,
    description TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    benefits TEXT NULL,
    total_slots INT NULL,
    min_cgpa DECIMAL(4,2) NULL,
    status ENUM('draft', 'open', 'closed', 'completed') NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_schemes_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_schemes_category
        FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scheme_id INT NOT NULL,
    student_id INT NOT NULL,
    status ENUM('draft', 'submitted', 'in_review', 'approved', 'rejected', 'completed') NOT NULL DEFAULT 'submitted',
    statement_of_purpose TEXT NULL,
    remarks TEXT NULL,
    submitted_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_application_student_scheme UNIQUE (scheme_id, student_id),
    CONSTRAINT fk_applications_scheme
        FOREIGN KEY (scheme_id) REFERENCES schemes(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_applications_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE CASCADE
);

CREATE TABLE eligibility_checks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NULL,
    student_name VARCHAR(150) NOT NULL,
    residency_status VARCHAR(50) NOT NULL,
    age_range VARCHAR(30) NOT NULL,
    academic_interest VARCHAR(100) NOT NULL,
    match_score INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_eligibility_student
        FOREIGN KEY (student_id) REFERENCES students(id)
        ON DELETE SET NULL
);

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    is_read TINYINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    activity_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NULL,
    entity_id INT NULL,
    details TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activity_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_students_full_name ON students(full_name);
CREATE INDEX idx_donors_org_name ON donors(organization_name);
CREATE INDEX idx_schemes_donor_id ON schemes(donor_id);
CREATE INDEX idx_schemes_category_id ON schemes(category_id);
CREATE INDEX idx_schemes_status ON schemes(status);
CREATE INDEX idx_schemes_deadline ON schemes(deadline);
CREATE INDEX idx_applications_student_id ON applications(student_id);
CREATE INDEX idx_applications_scheme_id ON applications(scheme_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);