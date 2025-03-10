-- Table for processed user data
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255),
    password VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    gender VARCHAR(50),
    birth_date DATE,
    email VARCHAR(255),
    phone VARCHAR(100),
    nationality VARCHAR(50),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table to track extraction metadata
CREATE TABLE IF NOT EXISTS extraction_metadata (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    records_count INTEGER,
    status VARCHAR(50)
);

-- Table for user statistics
CREATE TABLE IF NOT EXISTS user_statistics (
    stat_date DATE PRIMARY KEY,
    total_users INTEGER,
    male_count INTEGER,
    female_count INTEGER,
    avg_age NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);