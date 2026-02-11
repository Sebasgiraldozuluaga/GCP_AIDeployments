import os
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_community.utilities import SQLDatabase

def get_postgres_connection_string():
    """Build PostgreSQL connection string from environment variables."""
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_database = os.getenv("PG_DATABASE", "postgres")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "")
    return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"

def get_sql_db():
    """Returns a LangChain SQLDatabase instance."""
    return SQLDatabase.from_uri(get_postgres_connection_string())
