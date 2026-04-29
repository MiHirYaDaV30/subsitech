-- Create documents table for tracking uploaded files
CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    file_size INT,
    verification_status ENUM('pending', 'verified', 'rejected') DEFAULT 'pending',
    rejection_reason TEXT,
    verified_by INT,
    verified_at TIMESTAMP NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_application (application_id),
    INDEX idx_status (verification_status)
);

-- Add documents_uploaded column to applications table to track if docs exist
ALTER TABLE applications ADD COLUMN IF NOT EXISTS documents_uploaded BOOLEAN DEFAULT FALSE;
