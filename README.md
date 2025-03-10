## Architecture Overview

This project demonstrates a robust data pipeline that:

1. Extracts user data daily from the RandomUser.me API
2. Stores the raw data in Cassandra for high availability and write performance
3. Processes and transforms the data using Apache Spark
4. Loads processed data into PostgreSQL for analysis and reporting
5. Tracks metadata for all extraction and transformation operations


## Technology Stack

- **Apache Airflow**: Orchestrates the ETL workflow with scheduled execution
- **Apache Spark**: Distributed computing for large-scale data transformations
- **Apache Cassandra**: NoSQL database for storing raw JSON data
- **PostgreSQL**: Relational database for structured data and analytics
- **Docker & Docker Compose**: Containerization for consistent deployment

## Data Flow

### Extract
- The pipeline fetches 1,000 random user records daily from the RandomUser.me API
- Raw data is stored in Cassandra's `raw_users` table with extraction metadata
- Each extraction is tracked with unique identifiers and timestamps

### Transform
- Spark reads the raw data from Cassandra
- Performs data transformations:
  - JSON parsing and structure flattening
  - Data type conversions
  - Field extraction (username, name, gender, age, etc.)
- Calculates statistics (user counts by gender, average age)

### Load
- Processed user data is stored in PostgreSQL's `users` table
- Daily statistics are stored in the `user_statistics` table
- Extraction metadata is maintained for audit and tracking

## Data Model

### Cassandra (Raw Data)
- **Keyspace**: `batch_keyspace`
- **Tables**:
  - `raw_users`: Stores raw JSON data with date-based partitioning
  - `extraction_metadata`: Tracks extraction runs with metadata

### PostgreSQL (Processed Data)
- **Tables**:
  - `users`: Clean, structured user data
  - `user_statistics`: Daily aggregated statistics
  - `extraction_metadata`: Tracks ETL job execution

## Project Structure

```
├── dags/                 # Airflow DAG definitions
│   └── dag.py            # Main ETL pipeline DAG
├── plugins/              # Airflow plugins (db_utils, spark_utils)
├── db-init/              # Database initialization scripts
│   ├── cassandra/        # Cassandra schema setup
│   └── postgresql/       # PostgreSQL schema setup
├── data/                 # Persistent data storage
│   ├── cassandra/        # Cassandra data files
│   └── postgres/         # PostgreSQL data files
├── logs/                 # Airflow logs
├── docker-compose.yaml   # Docker services configuration
└── requirements.txt      # Python dependencies
```

## Setup Instructions

### Installation & Deployment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd batch-data-processing
   ```
2. Install packages:
   ```
   pip install -r requirements.txt
   ```
3. Start the services:
   ```bash
   docker-compose up -d
   ```
4. Initialize databases:
   - Check db-init folder
5. Access Airflow UI:
   - URL: http://localhost:8080
   - Username: airflow
   - Password: airflow

6. Access Spark UI:
   - URL: http://localhost:8081
