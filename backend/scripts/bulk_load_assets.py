import pandas as pd
import psycopg2
from psycopg2 import Error
import os

# Database connection parameters
DB_PARAMS = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "Hospital_Inventory",
    "user": "postgres",
    "password": "Altered_Carb0n!"
}

# File and client ID configuration
PROJECT_DIR = r"/Users/sudeepstephenyalla/Desktop/JobThings/MassTech/MassRx_Current/data"
EXCEL_FILE = os.path.join(PROJECT_DIR, "assets_NDH.xlsx")
CLIENT_ID = "umms"
def load_excel_to_postgres(file_path):
    try:
        # Read Excel file
        print(f"Reading Excel file: {file_path}")
        df = pd.read_excel(file_path, engine="openpyxl")

        # Verify expected columns
        expected_columns = [
            "TAG_NUMBER", "DESCRIPTION", "TYPE_DESC", "MANUFACTURER_DESC",
            "MODEL_NUM", "EQU_MODEL_NAME", "ORIG_MANUFACTURER_DESC",
            "SERIAL_NUM", "EQU_STATUS_DESC", "FACILITY"
        ]
        if not all(col in df.columns for col in expected_columns):
            missing = [col for col in expected_columns if col not in df.columns]
            raise ValueError(f"Missing columns in Excel file: {missing}")

        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()

        # Prepare insert query
        insert_query = """
        INSERT INTO asset_mstr (
            tag_number, description, type_desc, manufacturer_desc,
            model_num, equ_model_name, orig_manufacturer_desc,
            serial_num, equ_status_desc, facility_id, client_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Insert rows
        success_count = 0
        error_count = 0
        for _, row in df.iterrows():
            try:
                values = (
                    row["TAG_NUMBER"],
                    row["DESCRIPTION"] if pd.notna(row["DESCRIPTION"]) else None,
                    row["TYPE_DESC"] if pd.notna(row["TYPE_DESC"]) else None,
                    row["MANUFACTURER_DESC"] if pd.notna(row["MANUFACTURER_DESC"]) else None,
                    row["MODEL_NUM"] if pd.notna(row["MODEL_NUM"]) else None,
                    row["EQU_MODEL_NAME"] if pd.notna(row["EQU_MODEL_NAME"]) else None,
                    row["ORIG_MANUFACTURER_DESC"] if pd.notna(row["ORIG_MANUFACTURER_DESC"]) else None,
                    row["SERIAL_NUM"] if pd.notna(row["SERIAL_NUM"]) else None,
                    row["EQU_STATUS_DESC"] if pd.notna(row["EQU_STATUS_DESC"]) else None,
                    row["FACILITY"],
                    CLIENT_ID
                )
                cursor.execute(insert_query, values)
                success_count += 1
            except Error as e:
                print(f"Error inserting row with TAG_NUMBER {row['TAG_NUMBER']}: {e}")
                error_count += 1
                conn.rollback()  # Rollback on error
                continue
            else:
                conn.commit()  # Commit each successful insert

        print(f"Successfully inserted {success_count} rows")
        if error_count > 0:
            print(f"Failed to insert {error_count} rows")

    except FileNotFoundError:
        print(f"Excel file not found: {file_path}")
    except ValueError as ve:
        print(f"Validation error: {ve}")
    except Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    excel_path = os.path.join(PROJECT_DIR, EXCEL_FILE)
    load_excel_to_postgres(excel_path)