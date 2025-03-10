from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import json
import uuid
from cassandra.cluster import Cluster
import psycopg2
from psycopg2 import sql
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_date, count, avg, lit, when


def extract_data(**kwargs):
    """
    Extract data from RandomUser.me API and store in Cassandra
    """
    try:
        # Extract data from API
        response = requests.get("https://randomuser.me/api/?results=1000")
        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}")
        
        raw_data = response.json()["results"]
        extraction_date = datetime.now().strftime('%Y-%m-%d')
        
        # Connect to Cassandra and store data
        cluster = Cluster(['cassandra'])
        session = cluster.connect('batch_keyspace')
        
        # Insert extraction metadata
        metadata_id = uuid.uuid4()
        session.execute(
            """
            INSERT INTO extraction_metadata (id, extraction_date, records_count, status, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (metadata_id, extraction_date, len(raw_data), 'completed', datetime.now())
        )
        
        # Insert raw user data
        for user in raw_data:
            user_id = uuid.uuid4()
            session.execute(
                """
                INSERT INTO raw_users (date, user_id, raw_data, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (extraction_date, user_id, json.dumps(user), datetime.now())
            )
        
        logging.info(f"Extracted {len(raw_data)} records on {extraction_date}")
        return {
            "extraction_date": extraction_date,
            "records_count": len(raw_data),
            "metadata_id": str(metadata_id)
        }
    except Exception as e:
        logging.error(f"Data extraction failed: {str(e)}")
        raise
    finally:
        if 'session' in locals():
            session.shutdown()
        if 'cluster' in locals():
            cluster.shutdown()

def transform_data(**kwargs):
    """
    Transform data using Spark by submitting to Spark cluster
    """
    try:
        ti = kwargs['ti']
        extraction_info = ti.xcom_pull(task_ids='extract_data')
        extraction_date = extraction_info['extraction_date']
        
        # Initialize Spark session to connect to Spark cluster
        spark = SparkSession.builder \
            .appName("UserDataTransformation") \
            .master("spark://spark-master:7077") \
            .config("spark.jars.packages", "com.datastax.spark:spark-cassandra-connector_2.12:3.4.1") \
            .config("spark.cassandra.connection.host", "cassandra") \
            .getOrCreate()
            
        logging.info("Spark session created successfully, connected to spark-master")
        
        # Đọc dữ liệu trực tiếp từ Cassandra bằng Spark
        df = spark.read \
            .format("org.apache.spark.sql.cassandra") \
            .options(table="raw_users", keyspace="batch_keyspace") \
            .load() \
            .filter(col("date") == extraction_date)
        
        if df.count() == 0:
            logging.warning(f"No data found for date {extraction_date}")
            return {"status": "no_data", "extraction_date": extraction_date}
        
        # Parse JSON từ cột raw_data
        processed_df = df.select(
            col("user_id"),
            col("raw_data").cast("string").alias("json_data")
        ).select(
            col("user_id"),
            from_json(col("json_data"), "STRUCT<login: STRUCT<username: STRING, password: STRING>, name: STRUCT<first: STRING, last: STRING>, gender: STRING, dob: STRUCT<date: STRING, age: INT>, location: STRUCT<country: STRING>, email: STRING, phone: STRING>").alias("data")
        ).select(
            col("user_id"),
            col("data.login.username").alias("username"),
            col("data.login.password").alias("password"),
            col("data.name.first").alias("first_name"),
            col("data.name.last").alias("last_name"),
            col("data.gender"),
            to_date(col("data.dob.date")).alias("birth_date"),
            col("data.dob.age").alias("age"),  # Thêm cột age từ data.dob.age
            col("data.location.country").alias("nationality"),
            col("data.email"),
            col("data.phone")
        )
        
        # Calculate statistics
        stats_df = processed_df.agg(
            count("*").alias("total_users"),
            count(when(col("gender") == "male", 1)).alias("male_count"),
            count(when(col("gender") == "female", 1)).alias("female_count"),
            avg(col("age")).alias("avg_age")  # Sửa thành col("age")
        )
        
        # Add date to statistics
        stats_df = stats_df.withColumn("stat_date", lit(extraction_date))
        
        # Collect results
        processed_users = processed_df.collect()
        statistics = stats_df.collect()[0]
        
        # Return data for the load step
        return {
            "extraction_date": extraction_date,
            "processed_users": [user.asDict() for user in processed_users],
            "statistics": statistics.asDict()
        }
    except Exception as e:
        logging.error(f"Data transformation failed: {str(e)}")
        raise
    finally:
        if 'spark' in locals():
            spark.stop()

def load_data(**kwargs):
    """
    Load transformed data into PostgreSQL
    """
    try:
        ti = kwargs['ti']
        transform_result = ti.xcom_pull(task_ids='transform_data')
        
        if transform_result.get("status") == "no_data":
            logging.info(f"No data to load for date {transform_result['extraction_date']}")
            return
        
        processed_users = transform_result['processed_users']
        statistics = transform_result['statistics']
        extraction_date = transform_result['extraction_date']
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname="airflow",
            user="airflow",
            password="airflow",
            host="postgres"
        )
        cur = conn.cursor()
        
        # Insert processed users
        for user in processed_users:
            cur.execute(
                """
                INSERT INTO users (
                    user_id, username, password, first_name, last_name, 
                    gender, birth_date, nationality, email, phone
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    password = EXCLUDED.password,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    gender = EXCLUDED.gender,
                    birth_date = EXCLUDED.birth_date,
                    nationality = EXCLUDED.nationality,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    processed_at = CURRENT_TIMESTAMP
                """,
                (
                    user['user_id'], user['username'], user['password'], 
                    user['first_name'], user['last_name'], user['gender'], 
                    user['birth_date'], user['nationality'], user['email'], user['phone']
                )
            )
        
        # Insert statistics
        cur.execute(
            """
            INSERT INTO user_statistics (
                stat_date, total_users, male_count, female_count, avg_age
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (stat_date) DO UPDATE SET
                total_users = EXCLUDED.total_users,
                male_count = EXCLUDED.male_count,
                female_count = EXCLUDED.female_count,
                avg_age = EXCLUDED.avg_age,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                statistics['stat_date'], statistics['total_users'], 
                statistics['male_count'], statistics['female_count'], 
                statistics['avg_age']
            )
        )
        
        # Update extraction metadata
        cur.execute(
            """
            INSERT INTO extraction_metadata (timestamp, records_count, status)
            VALUES (%s, %s, %s)
            """,
            (datetime.now(), len(processed_users), 'completed')
        )
        
        conn.commit()
        logging.info(f"Successfully loaded {len(processed_users)} records into PostgreSQL")
        
        return {
            "status": "success",
            "loaded_records": len(processed_users),
            "extraction_date": extraction_date
        }
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        logging.error(f"Data loading failed: {str(e)}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Define the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'batch_etl_pipeline',
    default_args=default_args,
    description='ETL pipeline for batch data processing with Spark cluster',
    schedule_interval='@daily',
    start_date=datetime(2025, 3, 9),
    catchup=False
) as dag:
    
    extract_task = PythonOperator(
        task_id='extract_data',
        python_callable=extract_data,
        provide_context=True,
    )
    
    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data,
        provide_context=True,
    )
    
    load_task = PythonOperator(
        task_id='load_data',
        python_callable=load_data,
        provide_context=True,
    )
    
    # Define task dependencies
    extract_task >> transform_task >> load_task