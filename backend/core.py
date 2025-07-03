import psycopg2
from psycopg2 import pool
import bcrypt
import jwt as pyjwt
import datetime
import os
from tornado.options import options

# Configuration
SECRET_KEY = "super_secret_cookie_key_123"
JWT_ALGORITHM = "HS256"

class Database:
    def __init__(self):
        self.pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            host=options.db_host,
            port=options.db_port,
            database=options.db_name,
            user=options.db_user,
            password=options.db_password
        )

    def get_connection(self):
        return self.pool.getconn()

    def put_connection(self, conn):
        self.pool.putconn(conn)

class UserService:
    def __init__(self, db):
        self.db = db

    async def register_user(self, email, client_id, password):
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, client_id, password) VALUES (%s, %s, %s) RETURNING id",
                    (email, client_id, hashed_password.decode("utf-8"))
                )
                conn.commit()
                return {"success": True}
        except psycopg2.IntegrityError:
            return {"success": False, "error": "Email or client_id already exists"}
        finally:
            self.db.put_connection(conn)

    async def login_user(self, email, password):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT client_id, password FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                if user and bcrypt.checkpw(password.encode("utf-8"), user[1].encode("utf-8")):
                    token = pyjwt.encode(
                        {
                            "email": email,
                            "client_id": user[0],
                            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
                        },
                        SECRET_KEY,
                        algorithm=JWT_ALGORITHM
                    )
                    return {"success": True, "token": token}
                return {"success": False}
        finally:
            self.db.put_connection(conn)

    @staticmethod
    def verify_jwt(token):
        return pyjwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    

    def get_user_context(self, email):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.email, ur.role, u.client_id
                    FROM users u
                    JOIN user_roles ur ON u.email = ur.email
                    WHERE u.email = %s
                """, (email,))
                row = cur.fetchone()
                if row:
                    return {
                        "email": row[0],
                        "role": row[1],
                        "client_id": row[2]
                    }
                return None
        finally:
            self.db.put_connection(conn)


class AssetService:
    def __init__(self, db):
        self.db = db

    async def get_assets(self, client_id, facility_ids=None, tag_number=None, type_desc=None, page=1, per_page=10):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT tag_number, description, type_desc, manufacturer_desc,
                        model_num, equ_model_name, orig_manufacturer_desc,
                        serial_num, equ_status_desc, facility_id, udi_code, guid
                    FROM asset_mstr
                    WHERE client_id = %s
                """
                count_query = "SELECT COUNT(*) FROM asset_mstr WHERE client_id = %s"
                params = [client_id]
                count_params = [client_id]

                # Facility filter
                if facility_ids:
                    if len(facility_ids) == 1:
                        query += " AND facility_id = %s"
                        count_query += " AND facility_id = %s"
                        params.append(facility_ids[0])
                        count_params.append(facility_ids[0])
                    else:
                        placeholders = ','.join(['%s'] * len(facility_ids))
                        query += f" AND facility_id IN ({placeholders})"
                        count_query += f" AND facility_id IN ({placeholders})"
                        params.extend(facility_ids)
                        count_params.extend(facility_ids)

                if tag_number:
                    query += " AND tag_number ILIKE %s"
                    count_query += " AND tag_number ILIKE %s"
                    params.append(f'%{tag_number}%')
                    count_params.append(f'%{tag_number}%')

                if type_desc:
                    query += " AND type_desc = %s"
                    count_query += " AND type_desc = %s"
                    params.append(type_desc)
                    count_params.append(type_desc)

                query += " ORDER BY tag_number LIMIT %s OFFSET %s"
                params.extend([per_page, (page - 1) * per_page])

                cur.execute(count_query, count_params)
                total = cur.fetchone()[0]

                cur.execute(query, params)
                assets = [
                    {
                        "tag_number": row[0],
                        "description": row[1],
                        "type_desc": row[2],
                        "manufacturer_desc": row[3],
                        "model_num": row[4],
                        "equ_model_name": row[5],
                        "orig_manufacturer_desc": row[6],
                        "serial_num": row[7],
                        "equ_status_desc": row[8],
                        "facility_id": row[9],
                        "udi_code": row[10],
                        "guid": row[11],
                    }
                    for row in cur.fetchall()
                ]
                return assets, total
        finally:
            self.db.put_connection(conn)


    async def get_asset_by_id(self, client_id, tag_number, facility_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tag_number, description, type_desc, manufacturer_desc,
                           model_num, equ_model_name, orig_manufacturer_desc,
                           serial_num, equ_status_desc, facility_id, udi_code, guid
                    FROM asset_mstr
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    """,
                    (tag_number, facility_id, client_id)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "success": True,
                        "asset": {
                            "tag_number": row[0],
                            "description": row[1],
                            "type_desc": row[2],
                            "manufacturer_desc": row[3],
                            "model_num": row[4],
                            "equ_model_name": row[5],
                            "orig_manufacturer_desc": row[6],
                            "serial_num": row[7],
                            "equ_status_desc": row[8],
                            "facility_id": row[9],
                            "udi_code": row[10],
                            "guid": row[11]
                        }
                    }
                return {"success": False, "error": "Asset not found"}
        finally:
            self.db.put_connection(conn)

    async def get_facilities(self, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT facility_id
                    FROM facility
                    WHERE client_id = %s
                    ORDER BY facility_id
                    """,
                    (client_id,)
                )
                facilities = [{"facility_id": row[0]} for row in cur.fetchall()]
                return facilities
        finally:
            self.db.put_connection(conn)


    async def get_asset_types(self, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT type_desc FROM asset_mstr WHERE client_id = %s AND type_desc IS NOT NULL ORDER BY type_desc",
                    (client_id,)
                )
                asset_types = [row[0] for row in cur.fetchall()]
                return asset_types
        finally:
            self.db.put_connection(conn)

    async def add_asset(self, client_id, tag_number, description, type_desc,
                       manufacturer_desc, model_num, equ_model_name,
                       orig_manufacturer_desc, serial_num, equ_status_desc,
                       facility_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO asset_mstr (
                        tag_number, description, type_desc, manufacturer_desc,
                        model_num, equ_model_name, orig_manufacturer_desc,
                        serial_num, equ_status_desc, facility_id, client_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING tag_number
                    """,
                    (
                        tag_number, description, type_desc, manufacturer_desc,
                        model_num, equ_model_name, orig_manufacturer_desc,
                        serial_num, equ_status_desc, facility_id, client_id
                    )
                )
                conn.commit()
                return {"success": True}
        except psycopg2.IntegrityError:
            return {"success": False, "error": "Asset with this tag_number, client_id, and facility_id already exists"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)

    async def update_asset(self, client_id, tag_number, facility_id, description,
                          type_desc, manufacturer_desc, model_num, equ_model_name,
                          orig_manufacturer_desc, serial_num, equ_status_desc):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE asset_mstr
                    SET description = %s, type_desc = %s, manufacturer_desc = %s,
                        model_num = %s, equ_model_name = %s, orig_manufacturer_desc = %s,
                        serial_num = %s, equ_status_desc = %s
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    RETURNING tag_number
                    """,
                    (
                        description, type_desc, manufacturer_desc, model_num,
                        equ_model_name, orig_manufacturer_desc, serial_num,
                        equ_status_desc, tag_number, facility_id, client_id
                    )
                )
                if cur.fetchone():
                    conn.commit()
                    return {"success": True}
                return {"success": False, "error": "Asset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)

    async def delete_asset(self, client_id, tag_number, facility_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM asset_mstr
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    RETURNING tag_number
                    """,
                    (tag_number, facility_id, client_id)
                )
                if cur.fetchone():
                    conn.commit()
                    return {"success": True}
                return {"success": False, "error": "Asset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)

    async def create_work_order(self, client_id, tag_number, facility_id, description, wo_type, wo_priority, assigned_to_dept, dateneeded, requestercomments, assigned_technician):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # First, verify the asset exists
                cur.execute(
                    """
                    SELECT tag_number, manufacturer_desc, model_num, serial_num
                    FROM asset_mstr
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    """,
                    (tag_number, facility_id, client_id)
                )
                asset = cur.fetchone()
                if not asset:
                    return {"success": False, "error": "Asset not found"}

                # Generate the wo_number in the format client_id||facility_id||autonumber
                # Extract the highest autonumber for this client_id and facility_id
                cur.execute(
                    """
                    SELECT wo_number
                    FROM work_order
                    WHERE client_id = %s AND wo_number LIKE %s
                    ORDER BY wo_number DESC
                    LIMIT 1
                    """,
                    (client_id, f"{client_id}||{facility_id}||%")
                )
                last_wo = cur.fetchone()
                if last_wo:
                    # Extract the autonumber part (last segment after ||)
                    last_number = int(last_wo[0].split("||")[-1])
                    next_number = last_number + 1
                else:
                    next_number = 1000  # Start at 1000 if no previous work orders

                wo_number = f"{client_id}||{facility_id}||{next_number}"


                # Insert the work order
                cur.execute(
                    """
                    INSERT INTO work_order (
                        wo_number, wo_description, WO_Type, WO_Priority, AssetNumber,
                        ManufacturerName, ModelNumber, SerialNumber, AssignedToDept,
                        client_id, DateCreated, facility_id, dateneeded, requestercomments, assigned_technician
                    ) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
                    RETURNING wo_number
                    """,
                    (
                        wo_number, description, wo_type, wo_priority, tag_number,
                        asset[1], asset[2], asset[3], assigned_to_dept, client_id,
                        facility_id, dateneeded, requestercomments, assigned_technician
                    )
                )

                conn.commit()
                return {"success": True, "wo_number": wo_number}
        except psycopg2.IntegrityError:
            return {"success": False, "error": "Work order with this wo_number and client_id already exists"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)

    from datetime import datetime

    async def get_work_orders(self, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        wo_number,
                        wo_description,
                        AssetNumber,
                        WO_Type,
                        WO_Priority,
                        AssignedToDept,
                        DateCreated,
                        dateneeded
                    FROM work_order
                    WHERE client_id = %s
                    ORDER BY DateCreated DESC
                    """,
                    (client_id,)
                )
                rows = cur.fetchall()

                work_orders = []
                for row in rows:
                    work_orders.append({
                        "wo_number": row[0],
                        "wo_description": row[1],
                        "AssetNumber": row[2],
                        "WO_Type": row[3],
                        "WO_Priority": row[4],
                        "AssignedToDept": row[5],
                        "DateCreated": row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else None,
                        "dateneeded": row[7].strftime('%Y-%m-%d') if row[7] else None
                    })

                return {"success": True, "work_orders": work_orders}

        except Exception as e:
            return {"success": False, "error": str(e)}

        finally:
            self.db.put_connection(conn)
    
    # Get a specific work order by wo_number
    async def get_work_order_by_wo_number(self, client_id, wo_number):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT wo_number, wo_description, WO_Type, WO_Priority, AssignedToDept,
                           dateneeded, assigned_technician, requestercomments, 
                           parts_needed, work_order_status, work_activity_description
                    FROM work_order
                    WHERE client_id = %s AND wo_number = %s
                    """,
                    (client_id, wo_number)
                )
                row = cur.fetchone()
                if not row:
                    return {"success": False, "error": "Work order not found"}

                return {
                    "success": True,
                    "work_order": {
                        "wo_number": row[0],
                        "wo_description": row[1],
                        "wo_type": row[2],
                        "wo_priority": row[3],
                        "assignedtodept": row[4],
                        "dateneeded": row[5].strftime("%Y-%m-%d") if row[5] else "",
                        "assigned_technician": row[6] or "",
                        "requestercomments": row[7] or "",
                        "parts_needed": row[8] or "",
                        "work_order_status": row[9] or "",
                        "work_activity_description": row[10] or ""
                    }
                }
        finally:
            self.db.put_connection(conn)


    # Update a work order
    async def update_work_order(self, client_id, wo_number, wo_description, wo_type,
                                wo_priority, assignedtodept, dateneeded, assigned_technician,
                                requestercomments, parts_needed, parts_quantity, work_order_status, work_activity_description):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE work_order
                    SET wo_description = %s,
                        WO_Type = %s,
                        WO_Priority = %s,
                        AssignedToDept = %s,
                        dateneeded = %s,
                        assigned_technician = %s,
                        requestercomments = %s,
                        parts_needed = %s,
                        parts_quantity = %s,
                        work_order_status = %s,
                        work_activity_description = %s
                    WHERE wo_number = %s AND client_id = %s
                    """,
                    (
                        wo_description, wo_type, wo_priority, assignedtodept,
                        dateneeded, assigned_technician, requestercomments, parts_needed, parts_quantity, work_order_status,
                        work_activity_description, wo_number, client_id
                    )
                )
                # ✅ 3. PARTS INVENTORY CHECK & DEDUCT
                if parts_needed and parts_needed.lower() != "not required":
                    cur.execute(
                        "SELECT available_quantity FROM parts WHERE part_name = %s",
                        (parts_needed,)
                    )
                    row = cur.fetchone()
                    if not row or row[0] < parts_quantity:
                        return {
                            "success": False,
                            "error": f"Not enough stock for {parts_needed}. Available: {row[0] if row else 0}"
                        }
                    # Deduct parts
                    cur.execute(
                        "UPDATE parts SET available_quantity = available_quantity - %s WHERE part_name = %s",
                        (parts_quantity, parts_needed)
                    )
                    # Automatically create purchase entry if Battery drops below 10
                    if parts_needed == "Battery":
                        cur.execute(
                            "SELECT available_quantity FROM parts WHERE part_name = %s",
                            (parts_needed,)
                        )
                        row = cur.fetchone()
                        if row and row[0] < 10:
                            available_quantity = row[0]
                            quantity_to_purchase = 100 - available_quantity
                            cur.execute(
                                """
                                INSERT INTO purchase_history (part_name, quantity_purchased)
                                VALUES (%s, %s)
                                """,
                                (parts_needed, quantity_to_purchase)  # purchase 100 units
                            )
                conn.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)


    async def get_work_order_types(self):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT wo_type_cd, wo_type_cd_desc FROM wo_type_code ORDER BY wo_type_cd")
                types = [{"wo_type_cd": row[0], "wo_type_cd_desc": row[1]} for row in cur.fetchall()]
                return types
        finally:
            self.db.put_connection(conn)

    async def get_work_order_priorities(self):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT wo_priority_cd, wo_priority_cd_desc FROM wo_priority ORDER BY wo_priority_cd")
                priorities = [{"wo_priority_cd": row[0], "wo_priority_cd_desc": row[1]} for row in cur.fetchall()]
                return priorities
        finally:
            self.db.put_connection(conn)

    async def get_departments(self):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT dept_cd, dept_cd_desc FROM dept ORDER BY dept_cd")
                depts = [{"dept_cd": row[0], "dept_cd_desc": row[1]} for row in cur.fetchall()]
                return depts
        finally:
            self.db.put_connection(conn)