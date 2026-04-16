-- MultiText tables — added to propertypulse database
-- Run once to set up. Does NOT touch existing tables.

-- Message templates
CREATE TABLE IF NOT EXISTS outreach_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Send history
CREATE TABLE IF NOT EXISTS send_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contact_id INT,
    contact_name VARCHAR(200),
    phone VARCHAR(20),
    template_id INT,
    message_text TEXT,
    status ENUM('sent', 'failed', 'skipped', 'dry_run') NOT NULL,
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_contact (contact_id),
    INDEX idx_template (template_id),
    INDEX idx_sent_at (sent_at),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Scheduled outreach jobs
CREATE TABLE IF NOT EXISTS outreach_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    query_filter TEXT NOT NULL,
    template_id INT,
    cron_expression VARCHAR(100),
    is_active TINYINT(1) DEFAULT 1,
    last_run_at TIMESTAMP NULL,
    next_run_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_template (template_id)
) ENGINE=InnoDB;
