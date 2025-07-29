import psycopg2
from psycopg2 import pool
import bcrypt
import jwt as pyjwt
import datetime
import os
from tornado.options import options
import smtplib
import mimetypes
from email.mime.text import MIMEText
from psycopg2.extras import RealDictCursor

# Configuration
SECRET_KEY = "super_secret_cookie_key_123"
JWT_ALGORITHM = "HS256"

def send_email(subject, message):
    import os
    from email.mime.text import MIMEText
    import smtplib

    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    from_email = 'ppreity.ashley@gmail.com'
    to_email = 'ppreity.ashley@gmail.com'  # Or any recipient for testing

    # 🔐 Try App Password or fallback
    password = 'fljp umsx oflf jbru'

    print("Preparing to send email...")
    print(f"From: {from_email}, To: {to_email}, Subject: {subject}")

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1)  # 👈 Shows full SMTP log
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
            print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


BASE_UPLOAD_PATH = os.path.join(os.getcwd(), 'static', 'uploads')

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

    def get_user_by_email(self, email):
        query = "SELECT email FROM users WHERE email = %s"
        result = self.db.fetchone(query, (email,))
        return result
    
    async def reset_password(self, email, new_password):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
                if cur.fetchone() is None:
                    return {"success": False, "error": "User not found"}

                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                cur.execute(
                    "UPDATE users SET password = %s WHERE email = %s",
                    (hashed, email)
                )
                conn.commit()
                return {"success": True}
        finally:
            self.db.put_connection(conn)

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
            
    async def get_asset_by_tag_and_facility(self, client_id, tag_number, facility_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tag_number, facility_id, description, type_desc,
                        manufacturer_desc, model_num, equ_model_name,
                        orig_manufacturer_desc, serial_num, equ_status_desc, udi_code, guid
                    FROM asset_mstr
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    """,
                    (tag_number, facility_id, client_id)
                )
                row = cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None
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
                    facility_id, udi_code=None, guid=None):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                columns = [
                    "tag_number", "description", "type_desc", "manufacturer_desc",
                    "model_num", "equ_model_name", "orig_manufacturer_desc",
                    "serial_num", "equ_status_desc", "facility_id", "client_id"
                ]
                values = [
                    tag_number, description, type_desc, manufacturer_desc,
                    model_num, equ_model_name, orig_manufacturer_desc,
                    serial_num, equ_status_desc, facility_id, client_id
                ]

                # Add optional fields if provided
                if udi_code is not None and udi_code != '':
                    columns.append("udi_code")
                    values.append(udi_code)

                if guid is not None and guid != '':
                    columns.append("guid")
                    values.append(guid)

                placeholders = ', '.join(['%s'] * len(values))
                column_names = ', '.join(columns)

                query = f"""
                    INSERT INTO asset_mstr ({column_names})
                    VALUES ({placeholders})
                    RETURNING tag_number
                """
                cur.execute(query, values)
                conn.commit()
                return {"success": True}
        except psycopg2.IntegrityError:
            return {"success": False, "error": "Asset with this tag_number, client_id, and facility_id already exists"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db.put_connection(conn)


    async def update_asset(self, client_id, tag_number, facility_id, description=None,
                        type_desc=None, manufacturer_desc=None, model_num=None,
                        equ_model_name=None, orig_manufacturer_desc=None, serial_num=None,
                        equ_status_desc=None, udi_code=None, guid=None):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Prepare the columns to update dynamically
                updates = []
                values = []

                if description is not None:
                    updates.append("description = %s")
                    values.append(description)
                if type_desc is not None:
                    updates.append("type_desc = %s")
                    values.append(type_desc)
                if manufacturer_desc is not None:
                    updates.append("manufacturer_desc = %s")
                    values.append(manufacturer_desc)
                if model_num is not None:
                    updates.append("model_num = %s")
                    values.append(model_num)
                if equ_model_name is not None:
                    updates.append("equ_model_name = %s")
                    values.append(equ_model_name)
                if orig_manufacturer_desc is not None:
                    updates.append("orig_manufacturer_desc = %s")
                    values.append(orig_manufacturer_desc)
                if serial_num is not None:
                    updates.append("serial_num = %s")
                    values.append(serial_num)
                if equ_status_desc is not None:
                    updates.append("equ_status_desc = %s")
                    values.append(equ_status_desc)
                if udi_code is not None:
                    updates.append("udi_code = %s")
                    values.append(udi_code)
                if guid is not None:
                    updates.append("guid = %s")
                    values.append(guid)

                if not updates:
                    # Nothing to update
                    return {"success": False, "error": "No fields to update"}

                # Build the SQL query string
                set_clause = ", ".join(updates)
                query = f"""
                    UPDATE asset_mstr
                    SET {set_clause}
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                    RETURNING tag_number
                """
                values.extend([tag_number, facility_id, client_id])

                cur.execute(query, values)
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
    
    async def get_image_count(self, tag_number, facility_id, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                SELECT COUNT(*) FROM asset_images
                WHERE tag_number = %s AND facility_id = %s AND client_id = %s
            """, (tag_number, facility_id, client_id))
            return cur.fetchone()[0]
        finally:
            self.db.put_connection(conn)

    async def upload_image_to_disk(self, tag_number, facility_id, client_id, fileinfo, description="", content_type=None):
        try:
            # Step 1: Create directory
            target_folder = os.path.join(BASE_UPLOAD_PATH, client_id, facility_id, tag_number)
            os.makedirs(target_folder, exist_ok=True)
            print("[UPLOAD] Target folder:", target_folder)

            # Step 2: Generate filename
            existing = [f for f in os.listdir(target_folder) if f.startswith("img") and f[3:].split('.')[0].isdigit()]
            next_img_num = max([int(f[3:].split('.')[0]) for f in existing] + [0]) + 1
            ext = os.path.splitext(fileinfo['filename'])[1].lower()
            filename = f"img{next_img_num}{ext}"

            # Step 3: Save file to disk
            file_path = os.path.join(target_folder, filename)
            print("[UPLOAD] Writing file:", file_path)

            with open(file_path, "wb") as f:
                f.write(fileinfo["body"])

            image_path = f"uploads/{client_id}/{facility_id}/{tag_number}/{filename}"
            print("[UPLOAD] Image path saved to DB:", image_path)

            # Step 4: Save DB record including `filename`
            conn = self.db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO asset_images (
                            tag_number, facility_id, client_id, image_path, 
                            description, content_type, filename
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tag_number, facility_id, client_id,
                        image_path, description, content_type, fileinfo['filename']
                    ))
                    conn.commit()
                    print("[UPLOAD] Inserted image record into DB")
            finally:
                self.db.put_connection(conn)

        except Exception as e:
            print("[UPLOAD ERROR]", str(e))


    def get_images_for_asset(self, tag_number, facility_id, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, description, content_type
                    FROM asset_images
                    WHERE tag_number = %s AND facility_id = %s AND client_id = %s
                """, (tag_number, facility_id, client_id))
                
                results = cur.fetchall()
                images = []
                for row in results:
                    image_id, description, content_type = row
                    images.append({
                        "url": f"/media/{image_id}",
                        "description": description or "",
                        "content_type": content_type or "application/octet-stream"
                    })
                return images
        finally:
            self.db.put_connection(conn)

    async def delete_asset_image(self, file_id, client_id):
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM asset_images WHERE id = %s AND client_id = %s RETURNING id",
                    (file_id, client_id)
                )
                row = cur.fetchone()
                return row is not None
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

                if parts_needed and parts_needed.lower() != "not required":

                    # 1. Get current stock and approval requirement
                    cur.execute("""
                        SELECT available_quantity, purchase_order_approval 
                        FROM parts 
                        WHERE part_name = %s AND client_id = %s
                    """, (parts_needed, client_id))
                    row = cur.fetchone()
                    if not row:
                        return {"success": False, "error": f"'{parts_needed}' not found in inventory."}

                    available_quantity, approval_required = row
                    approval_required = approval_required or 'not required'

                    # 2. Block update if request exceeds stock
                    if parts_quantity > available_quantity:
                        quantity_to_purchase = parts_quantity - available_quantity
                        requested_by = assigned_technician or requestercomments or "unknown"

                        # 🔒 Check for existing active purchase request
                        cur.execute("""
                            SELECT 1 FROM purchase_history
                            WHERE part = %s AND client_id = %s
                            AND purchase_order_status IN ('Waiting for approval', 'Created')
                            LIMIT 1
                        """, (parts_needed, client_id))
                        existing = cur.fetchone()

                        if not existing:
                            cur.execute("""
                                INSERT INTO purchase_history (
                                    part, requested_quantity, requested_by,
                                    purchase_order_status, approval_status, client_id, requested_date
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            """, (
                                parts_needed, 100 - available_quantity, requested_by,
                                'Waiting for approval' if approval_required == 'required' else 'Created',
                                'Pending' if approval_required == 'required' else 'Approved',
                                client_id
                            ))

                            conn.commit()

                            if approval_required == 'required':
                                send_email(
                                    subject="🛒 Purchase Request Approval Needed",
                                    message=f"A request for {quantity_to_purchase} unit(s) of '{parts_needed}' has been submitted and needs approval."
                                )

                            return {
                                "success": False,
                                "error": f"❌ Only {available_quantity} '{parts_needed}' in stock.\n"
                                        f"📦 Purchase request created (approval: {approval_required})."
                            }

                        else:
                            return {
                                "success": False,
                                "error": f"⚠️ Only {available_quantity} '{parts_needed}' in stock.\n"
                                        f"🔄 Existing purchase request already in progress. No new request created."
                            }

                # 3. Work order can be updated
                cur.execute("""
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
                """, (
                    wo_description, wo_type, wo_priority, assignedtodept,
                    dateneeded, assigned_technician, requestercomments,
                    parts_needed, parts_quantity, work_order_status,
                    work_activity_description, wo_number, client_id
                ))

                # 4. Deduct quantity from parts
                if parts_needed and parts_needed.lower() != "not required":
                    cur.execute("""
                        UPDATE parts 
                        SET available_quantity = GREATEST(available_quantity - %s, 0)
                        WHERE part_name = %s AND client_id = %s
                    """, (parts_quantity, parts_needed, client_id))

                    # 5. Check threshold AFTER deduction and auto-trigger purchase request
                    cur.execute("""
                        SELECT available_quantity, purchase_order_approval 
                        FROM parts 
                        WHERE part_name = %s AND client_id = %s
                    """, (parts_needed, client_id))
                    updated_row = cur.fetchone()
                    if updated_row:
                        remaining_quantity, approval_required = updated_row
                        approval_required = approval_required or 'not required'

                        if remaining_quantity <= 10:
                            # 🔒 Check again for existing active request before auto-trigger
                            cur.execute("""
                                SELECT 1 FROM purchase_history
                                WHERE part = %s AND client_id = %s
                                AND purchase_order_status IN ('Waiting for approval', 'Created')
                                LIMIT 1
                            """, (parts_needed, client_id))
                            already_exists = cur.fetchone()

                            if not already_exists:
                                cur.execute("""
                                    INSERT INTO purchase_history (
                                        part, requested_quantity, requested_by,
                                        purchase_order_status, approval_status, client_id, requested_date
                                    )
                                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                                """, (
                                    parts_needed, 100 - remaining_quantity,
                                    assigned_technician or requestercomments or "auto-trigger",
                                    'Waiting for approval' if approval_required == 'required' else 'Created',
                                    'Pending' if approval_required == 'required' else 'Approved',
                                    client_id
                                ))
                                conn.commit()

                                if approval_required == 'required':
                                    send_email(
                                        subject="🔔 Auto Purchase Triggered",
                                        message=f"Stock for '{parts_needed}' dropped to {remaining_quantity}. "
                                                f"Auto purchase request created. Waiting for your approval."
                                    )

                conn.commit()
                return {"success": True}

        except Exception as e:
            conn.rollback()
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
    
    