"""
utils/sql_connectors.py
Multi-dialect SQL connector that:
1. Connects to MySQL, PostgreSQL, Snowflake, or SQL Server.
2. Extracts the full schema as a normalised DataFrame.
3. Executes read-only SELECT queries and returns results as a DataFrame.

Safety
- Only SELECT statements are allowed through ``execute_query``.
- DDL / DML keywords trigger an immediate ValueError.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_IGNORE_SCHEMAS = {
    "mysql", "information_schema", "performance_schema", "sys",
    "pg_catalog", "pg_toast", "pg_temp_1", "pg_toast_temp_1",
    "snowflake", "snowflake_sample_data", "snowflake_account_usage",
    "sys", "guest", "db_owner", "db_accessadmin",
    "db_securityadmin", "db_ddladmin", "db_backupoperator",
    "db_datareader", "db_datawriter", "db_denydatareader",
    "db_denydatawriter",
}

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|EXEC|EXECUTE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class SQLConnector:
    """Connects to a target database, extracts schema, and executes queries."""

    def __init__(
        self,
        db_type: str,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ) -> None:
        self.db_type = db_type.lower()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.dialect: str = ""

        self._connection = None
        self.schema_df: pd.DataFrame | None = None

    def connect(self) -> None:
        """Establish a connection to the configured database."""
        dispatch = {
            "mysql": self._connect_mysql,
            "postgresql": self._connect_postgresql,
            "postgres": self._connect_postgresql,
            "snowflake": self._connect_snowflake,
            "sqlserver": self._connect_sqlserver,
            "mssql": self._connect_sqlserver,
        }
        func = dispatch.get(self.db_type)
        if func is None:
            raise ValueError(
                f"Unsupported db_type '{self.db_type}'. "
                f"Supported: {list(dispatch.keys())}"
            )
        func()
        logger.info("Connected to %s database '%s'.", self.dialect, self.database)

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    def _connect_mysql(self) -> None:
        import pymysql  # type: ignore

        self._connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=self.database,
        )
        self.dialect = "MySQL"
        self.schema_df = self._fetch_mysql_schema()

    def _connect_postgresql(self) -> None:
        import psycopg2  # type: ignore

        self._connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            dbname=self.database,
        )
        self.dialect = "PostgreSQL"
        self.schema_df = self._fetch_postgresql_schema()

    def _connect_snowflake(self) -> None:
        import snowflake.connector  # type: ignore

        self._connection = snowflake.connector.connect(
            user=self.username,
            password=self.password,
            account=self.host,
            database=self.database,
        )
        self.dialect = "Snowflake"
        self.schema_df = self._fetch_snowflake_schema()

    def _connect_sqlserver(self) -> None:
        import pyodbc  # type: ignore

        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={self.host},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};PWD={self.password};"
            "TrustServerCertificate=yes;"
        )
        self._connection = pyodbc.connect(conn_str)
        self.dialect = "SQL Server"
        self.schema_df = self._fetch_sqlserver_schema()

    def get_schema(self) -> pd.DataFrame | None:
        """Connect (if not already) and return the normalised schema DataFrame."""
        if self.schema_df is not None:
            return self.schema_df
        self.connect()
        return self.schema_df

    def _run_schema_query(self, sql: str) -> pd.DataFrame:
        with self._connection.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        df.columns = df.columns.str.lower()
        return df

    def _fetch_postgresql_schema(self) -> pd.DataFrame:
        sql = """
        SELECT
            c.table_schema,
            c.table_name,
            c.column_name,
            c.data_type,
            c.column_default,
            CASE WHEN pk.column_name IS NOT NULL THEN 'YES' ELSE 'NO' END AS is_primary_key,
            fk.foreign_table_name   AS referenced_table,
            fk.foreign_column_name  AS referenced_column,
            ''                       AS column_comment
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.table_schema, ku.table_name, ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
                AND tc.table_schema   = ku.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk
            ON c.table_schema = pk.table_schema
            AND c.table_name  = pk.table_name
            AND c.column_name = pk.column_name
        LEFT JOIN (
            SELECT
                kcu.table_schema, kcu.table_name, kcu.column_name,
                ccu.table_name  AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.referential_constraints rc
                ON kcu.constraint_name = rc.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = rc.unique_constraint_name
        ) fk
            ON c.table_schema = fk.table_schema
            AND c.table_name  = fk.table_name
            AND c.column_name = fk.column_name
        WHERE LOWER(c.table_schema) NOT IN ({placeholders})
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """.format(
            placeholders=", ".join(f"'{s}'" for s in _IGNORE_SCHEMAS)
        )
        return self._run_schema_query(sql)

    def _fetch_mysql_schema(self) -> pd.DataFrame:
        sql = """
        SELECT
            c.table_schema,
            c.table_name,
            c.column_name,
            c.data_type,
            c.column_default,
            CASE WHEN kcu.constraint_name = 'PRIMARY' THEN 'YES' ELSE 'NO' END AS is_primary_key,
            kcu2.referenced_table_name  AS referenced_table,
            kcu2.referenced_column_name AS referenced_column,
            c.column_comment
        FROM information_schema.columns c
        LEFT JOIN information_schema.key_column_usage kcu
            ON c.table_schema = kcu.table_schema
            AND c.table_name  = kcu.table_name
            AND c.column_name = kcu.column_name
            AND kcu.constraint_name = 'PRIMARY'
        LEFT JOIN information_schema.key_column_usage kcu2
            ON c.table_schema = kcu2.table_schema
            AND c.table_name  = kcu2.table_name
            AND c.column_name = kcu2.column_name
            AND kcu2.referenced_table_name IS NOT NULL
        WHERE LOWER(c.table_schema) NOT IN ({placeholders})
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """.format(
            placeholders=", ".join(f"'{s}'" for s in _IGNORE_SCHEMAS)
        )
        return self._run_schema_query(sql)

    def _fetch_snowflake_schema(self) -> pd.DataFrame:
        sql = f"""
        SELECT
            c.table_schema,
            c.table_name,
            c.column_name,
            c.data_type,
            c.column_default,
            CASE WHEN pk.column_name IS NOT NULL THEN 'YES' ELSE 'NO' END AS is_primary_key,
            '' AS referenced_table,
            '' AS referenced_column,
            c.comment AS column_comment
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT kcu.table_schema, kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk
            ON c.table_schema = pk.table_schema
            AND c.table_name  = pk.table_name
            AND c.column_name = pk.column_name
        WHERE LOWER(c.table_schema) NOT IN ({', '.join(f"'{s}'" for s in _IGNORE_SCHEMAS)})
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """
        return self._run_schema_query(sql)

    def _fetch_sqlserver_schema(self) -> pd.DataFrame:
        sql = """
        SELECT
            s.name  AS table_schema,
            t.name  AS table_name,
            c.name  AS column_name,
            tp.name AS data_type,
            dc.definition AS column_default,
            CASE WHEN pk.column_id IS NOT NULL THEN 'YES' ELSE 'NO' END AS is_primary_key,
            fk_ref.referenced_table  AS referenced_table,
            fk_ref.referenced_column AS referenced_column,
            ISNULL(ep.value, '')     AS column_comment
        FROM sys.columns c
        JOIN sys.tables t  ON c.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.types tp  ON c.user_type_id = tp.user_type_id
        LEFT JOIN sys.default_constraints dc
            ON c.default_object_id = dc.object_id
        LEFT JOIN (
            SELECT ic.object_id, ic.column_id
            FROM sys.index_columns ic
            JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            WHERE i.is_primary_key = 1
        ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
        LEFT JOIN (
            SELECT
                fkc.parent_object_id, fkc.parent_column_id,
                OBJECT_NAME(fkc.referenced_object_id)     AS referenced_table,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
            FROM sys.foreign_key_columns fkc
        ) fk_ref ON c.object_id = fk_ref.parent_object_id AND c.column_id = fk_ref.parent_column_id
        LEFT JOIN sys.extended_properties ep
            ON ep.major_id = c.object_id
            AND ep.minor_id = c.column_id
            AND ep.name = 'MS_Description'
        WHERE LOWER(s.name) NOT IN ({placeholders})
        ORDER BY s.name, t.name, c.column_id
        """.format(
            placeholders=", ".join(f"'{s}'" for s in _IGNORE_SCHEMAS)
        )
        return self._run_schema_query(sql)

    def execute_query(self, sql: str, max_rows: int = 500) -> pd.DataFrame:
        """Execute a SELECT query and return results as a DataFrame.

        Raises
        ------
        ValueError
            If the SQL contains forbidden DML/DDL keywords.
        RuntimeError
            If not connected.
        """
        if _FORBIDDEN_KEYWORDS.search(sql):
            raise ValueError(
                "Only SELECT queries are allowed. "
                "DDL and DML statements are prohibited for safety."
            )

        if self._connection is None:
            self.connect()

        logger.info("Executing SQL (preview): %.120s", sql.strip().replace("\n", " "))

        with self._connection.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchmany(max_rows)
            cols = [d[0] for d in cur.description] if cur.description else []

        df = pd.DataFrame(rows, columns=cols)

        # Convert datetime columns to ISO strings for JSON serialisation
        for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        logger.info("Query returned %d rows.", len(df))
        return df
