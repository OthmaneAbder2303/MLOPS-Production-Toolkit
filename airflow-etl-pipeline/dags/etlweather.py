from airflow.decorators import dag, task
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
import json
import requests
from pendulum import datetime
from datetime import timedelta

# Latitude and Longitude for Lille, France
LATITUDE = "50.5074"
LONGITUDE = "3.0330"

POSTGRES_CONN_ID = "postgres_default"
WEATHER_API_CONN_ID = "open_meteo_api"

# default_args = {
#     'owner': 'airflow',
#     'start_date': days_ago(1),
#     'retries': 1,
#     'retry_delay': timedelta(minutes=5),
# }
## because airflow stopped working with days_ago

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 1, 31),
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
@dag(
    dag_id='weather_etl_pipeline',
    default_args=default_args,
    #schedule_interval='@daily',
    catchup=False,
)

def weather_etl_pipeline():

    @task
    def extract_weather_data():
        """Extract weather data from open-meteo API using Airflow connection."""

        http_hook = HttpHook(method='GET', http_conn_id=WEATHER_API_CONN_ID)

        ## https://api.open-meteo.com/v1/forecast?latitude=50.5074&longitude=3.0330&current_weather=true
        endpoint = f"/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true"

        ## Make the API request
        response = http_hook.run(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data: {response.status_code}")
        weather_data = response.json()
        return weather_data
    
    @task
    def transform_weather_data(weather_data):
        """Transform the extracted weather data."""

        current_weather = weather_data.get("current_weather", {})
        transformed_data = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "temperature": current_weather.get("temperature"),
            "windspeed": current_weather.get("windspeed"),
            "winddirection": current_weather.get("winddirection"),
            "weathercode": current_weather.get("weathercode"),
        }
        return transformed_data
    
    @task()
    def load_weather_data(transformed_data):
        """Load transformed data into PostgreSQL."""
        pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn = pg_hook.get_conn()
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            latitude FLOAT,
            longitude FLOAT,
            temperature FLOAT,
            windspeed FLOAT,
            winddirection FLOAT,
            weathercode INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Insert transformed data into the table
        cursor.execute("""
        INSERT INTO weather_data (latitude, longitude, temperature, windspeed, winddirection, weathercode)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            transformed_data['latitude'],
            transformed_data['longitude'],
            transformed_data['temperature'],
            transformed_data['windspeed'],
            transformed_data['winddirection'],
            transformed_data['weathercode']
        ))

        conn.commit()
        cursor.close()

    # Define the ETL pipeline
    weather_data = extract_weather_data()
    transformed_data = transform_weather_data(weather_data)
    load_weather_data(transformed_data)

# Instantiate the DAG
weather_etl_pipeline()
