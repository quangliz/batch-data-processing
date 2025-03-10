-- create keyspace
CREATE KEYSPACE IF NOT EXISTS batch_keyspace
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE batch_keyspace;

-- raw table to store raw data
CREATE TABLE IF NOT EXISTS raw_users (
    date text,              -- Partition key (date when data was loaded, e.g., '2025-03-09')
    user_id uuid,           -- Clustering key (unique ID for each user)
    raw_data text,          -- Column storing the original JSON
    created_at timestamp,   -- Storage timestamp
    PRIMARY KEY (date, user_id)
);

-- Create a table to track extraction metadata
CREATE TABLE IF NOT EXISTS extraction_metadata (
    id uuid PRIMARY KEY,
    extraction_date text,
    records_count int,
    status text,
    created_at timestamp
);