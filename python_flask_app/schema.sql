-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS ai_question_generator;
USE ai_question_generator;

-- Table for tracking User Profile defaults and statistics
CREATE TABLE IF NOT EXISTS user_profile (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL DEFAULT 'Educator Pro',
    email VARCHAR(100) NOT NULL,
    grade_level VARCHAR(50) DEFAULT 'High School',
    default_subject VARCHAR(100) DEFAULT 'General Science',
    questions_generated INT DEFAULT 0,
    quizzes_taken INT DEFAULT 0,
    average_score FLOAT DEFAULT 0.0
);

-- Table for grouping generated sets
CREATE TABLE IF NOT EXISTS question_sets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    topic VARCHAR(150) NOT NULL,
    difficulty VARCHAR(50) NOT NULL,
    question_type VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table for single questions inside a set
CREATE TABLE IF NOT EXISTS questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    set_id INT NOT NULL,
    question_text TEXT NOT NULL,
    options TEXT, -- JSON array of option strings
    correct_answer VARCHAR(255) NOT NULL,
    explanation TEXT,
    FOREIGN KEY (set_id) REFERENCES question_sets(id) ON DELETE CASCADE
);

-- Insert a default user profile
INSERT INTO user_profile (email, username) VALUES ('user@example.com', 'Educator Pro') ON DUPLICATE KEY UPDATE id=id;
