import tornado.web
import tornado.escape
from core import UserService, AssetService

class BaseApiHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.db = self.application.db
        self.user_service = UserService(self.db)
        self.asset_service = AssetService(self.db)

    def get_current_user(self):
        token = self.get_secure_cookie("token")
        if token:
            token = token.decode()
        else:
            auth_header = self.request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            return None
        try:
            from core import UserService
            return UserService.verify_jwt(token)
        except Exception:
            return None

        
    async def get_user_context(self, email):
        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Get role and main facility
                cur.execute("""
                    SELECT role, facility_id, assigned_technician, client_id
                    FROM user_roles
                    WHERE email = %s
                    LIMIT 1
                """, (email,))
                row = cur.fetchone()
                if not row:
                    return None

                role, facility_id, assigned_technician, client_id = row
                context = {
                    "role": role,
                    "facility_id": facility_id,
                    "assigned_technician": assigned_technician,
                    "client_id": client_id
                }

                if role == "manager":
                    # Get additional assigned facilities
                    cur.execute("""
                        SELECT facility_id
                        FROM manager_facilities
                        WHERE email = %s
                    """, (email,))
                    rows = cur.fetchall()
                    manager_facilities = [r[0] for r in rows]

                    # Always include their main facility if not already there
                    if facility_id and facility_id not in manager_facilities:
                        manager_facilities.append(facility_id)

                    context["manager_facilities"] = manager_facilities

                return context
        finally:
            self.application.db.put_connection(conn)




class RegisterHandler(BaseApiHandler):
    async def post(self):
        try:
            data = tornado.escape.json_decode(self.request.body)
            email = data.get("email")
            client_id = data.get("client_id")
            password = data.get("password")

            if not all([email, client_id, password]):
                self.set_status(400)
                self.write({"error": "Missing required fields"})
                return

            result = await self.user_service.register_user(email, client_id, password)
            if result["success"]:
                self.write({"message": "User registered successfully"})
            else:
                self.set_status(400)
                self.write({"error": result["error"]})
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})

class LoginHandler(BaseApiHandler):
    async def post(self):
        try:
            data = tornado.escape.json_decode(self.request.body)
            email = data.get("email")
            password = data.get("password")

            result = await self.user_service.login_user(email, password)
            if result["success"]:
                token = result["token"]
                self.set_secure_cookie("token", token, httponly=True)
                self.write({"token": token, "message": "Login successful", "redirect": "/dashboard"})
            else:
                self.set_status(401)
                self.write({"error": "Invalid credentials"})
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})

class CurrentUserHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        context = await self.get_user_context(user["email"])
        if not context:
            self.set_status(403)
            self.write({"error": "User context not found"})
            return

        self.write({
            "email": user["email"],
            "client_id": user["client_id"],
            "role": context["role"]
        })

class ManagerListHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]
        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ur.email, COALESCE(array_agg(mf.facility_id), '{}')
                    FROM user_roles ur
                    LEFT JOIN manager_facilities mf ON ur.email = mf.email
                    WHERE ur.role = 'manager' AND ur.client_id = %s
                    GROUP BY ur.email
                """, (client_id,))
                managers = [{"email": row[0], "facilities": row[1]} for row in cur.fetchall()]
                self.write({"managers": managers})
        finally:
            self.application.db.put_connection(conn)


class AssignFacilityHandler(BaseApiHandler):
    async def post(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        context = await self.get_user_context(user["email"])
        if context["role"] != "director":
            self.set_status(403)
            self.write({"error": "Forbidden – Only directors can assign facilities"})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            email = data.get("email")
            facility_id = data.get("facility_id")

            if not email or not facility_id:
                self.set_status(400)
                self.write({"error": "Missing manager email or facility_id"})
                return

            conn = self.application.db.get_connection()
            try:
                with conn.cursor() as cur:
                    # Avoid duplicates
                    cur.execute("""
                        INSERT INTO manager_facilities (email, facility_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (email, facility_id))
                    conn.commit()
                    self.write({"message": f"Facility '{facility_id}' assigned to manager '{email}' successfully."})
            finally:
                self.application.db.put_connection(conn)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(500)
            self.write({"error": "Internal server error"})

class RemoveFacilityHandler(BaseApiHandler):
    async def post(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        context = await self.get_user_context(user["email"])
        if context["role"] != "director":
            self.set_status(403)
            self.write({"error": "Forbidden – Only directors can remove facilities"})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            email = data.get("email")
            facility_id = data.get("facility_id")

            if not email or not facility_id:
                self.set_status(400)
                self.write({"error": "Missing email or facility_id"})
                return

            conn = self.application.db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM manager_facilities
                        WHERE email = %s AND facility_id = %s
                    """, (email, facility_id))
                    conn.commit()
                    self.write({"message": f"Facility '{facility_id}' removed from manager '{email}' successfully."})
            finally:
                self.application.db.put_connection(conn)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.set_status(500)
            self.write({"error": "Internal server error"})

class AssetHandler(BaseApiHandler):
    async def get(self, tag_number=None, facility_id=None):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]
        email = user["email"]

        if not client_id:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        # Fetch role & facilities
        context = await self.get_user_context(email)
        if not context:
            self.set_status(403)
            self.write({"error": "User role not found"})
            return

        role = context["role"]
        manager_facilities = context.get("manager_facilities", [])

        # Fetch filters from query parameters
        filter_facility_id = self.get_query_argument("facility_id", None)
        filter_tag_number = self.get_query_argument("tag_number", None)
        filter_type_desc = self.get_query_argument("type_desc", None)
        page = int(self.get_query_argument("page", 1))
        per_page = int(self.get_query_argument("per_page", 10))

        if role == "director":
            # If director, allow any facility or all
            if filter_facility_id:
                facility_ids = [filter_facility_id]
            else:
                facility_ids = None
            assets, total = await self.asset_service.get_assets(
                client_id,
                facility_ids,
                filter_tag_number,
                filter_type_desc,
                page,
                per_page
            )

        else:
            # Manager/Technician
            if not manager_facilities:
                self.write({"assets": [], "total": 0, "page": page, "per_page": per_page})
                return

            if filter_facility_id:
                if filter_facility_id not in manager_facilities:
                    self.set_status(403)
                    self.write({"error": "Access denied for the selected facility"})
                    return
                facility_ids = [filter_facility_id]
            else:
                facility_ids = manager_facilities

            assets, total = await self.asset_service.get_assets(
                client_id,
                facility_ids,
                filter_tag_number,
                filter_type_desc,
                page,
                per_page
            )

        self.write({
            "assets": assets,
            "total": total,
            "page": page,
            "per_page": per_page
        })



    async def post(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return
        client_id = user["client_id"]

        if not client_id:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            tag_number = data.get("tag_number")
            description = data.get("description")
            type_desc = data.get("type_desc")
            manufacturer_desc = data.get("manufacturer_desc")
            model_num = data.get("model_num")
            equ_model_name = data.get("equ_model_name")
            orig_manufacturer_desc = data.get("orig_manufacturer_desc")
            serial_num = data.get("serial_num")
            equ_status_desc = data.get("equ_status_desc")
            facility_id = data.get("facility_id")

            if not all([tag_number, facility_id]):
                self.set_status(400)
                self.write({"error": "Missing required fields: tag_number, facility_id"})
                return

            result = await self.asset_service.add_asset(
                client_id, tag_number, description, type_desc, manufacturer_desc,
                model_num, equ_model_name, orig_manufacturer_desc, serial_num,
                equ_status_desc, facility_id
            )
            if result["success"]:
                self.write({"message": "Asset created successfully"})
            else:
                self.set_status(400)
                self.write({"error": result["error"]})
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})

    async def put(self, tag_number, facility_id):
        
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return
        client_id = user["client_id"]

        if not client_id:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            description = data.get("description")
            type_desc = data.get("type_desc")
            manufacturer_desc = data.get("manufacturer_desc")
            model_num = data.get("model_num")
            equ_model_name = data.get("equ_model_name")
            orig_manufacturer_desc = data.get("orig_manufacturer_desc")
            serial_num = data.get("serial_num")
            equ_status_desc = data.get("equ_status_desc")

            result = await self.asset_service.update_asset(
                client_id, tag_number, facility_id, description, type_desc,
                manufacturer_desc, model_num, equ_model_name, orig_manufacturer_desc,
                serial_num, equ_status_desc
            )
            if result["success"]:
                self.write({"message": "Asset updated successfully"})
            else:
                self.set_status(404 if result["error"] == "Asset not found" else 400)
                self.write({"error": result["error"]})
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})

    async def delete(self, tag_number, facility_id):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return
        client_id = user["client_id"]

        if not client_id:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        result = await self.asset_service.delete_asset(client_id, tag_number, facility_id)
        if result["success"]:
            self.write({"message": "Asset deleted successfully"})
        else:
            self.set_status(404 if result["error"] == "Asset not found" else 400)
            self.write({"error": result["error"]})

class FacilityHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]
        email = user["email"]
        context = await self.get_user_context(email)

        if not context:
            self.set_status(403)
            self.write({"error": "User context not found"})
            return

        role = context["role"]

        if role == "director":
            # Director sees all facilities
            facilities = await self.asset_service.get_facilities(client_id)
        else:
            # Manager and technician see only assigned facilities
            manager_facilities = context.get("manager_facilities", [])
            if not manager_facilities:
                facilities = []
            else:
                all_facilities = await self.asset_service.get_facilities(client_id)
                facilities = [f for f in all_facilities if f["facility_id"] in manager_facilities]

        # Include the role in the response
        self.write({"facilities": facilities, "role": role})


class AssetTypeHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]
        print("Extracted client_id:", client_id, type(client_id))  # Debug

        asset_types = await self.asset_service.get_asset_types(client_id)
        self.write({"asset_types": asset_types})


class WorkOrderHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        email = user["email"]
        client_id = user["client_id"]
        context = await self.get_user_context(email)

        if not context:
            self.set_status(403)
            self.write({"error": "User role not found"})
            return

        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                base_query = """
                    SELECT 
                        wo_number,
                        wo_description,
                        assetnumber AS "AssetNumber",
                        wo_type AS "WO_Type",
                        wo_priority AS "WO_Priority",
                        assignedtodept AS "AssignedToDept",
                        assigned_technician,
                        facility_id,
                        datecreated AS "DateCreated",
                        dateneeded,
                        work_order_status AS "Work_Order_Status"
                    FROM work_order
                """

                # Technician: only own work orders
                if context["role"] == "technician":
                    cur.execute(base_query + """
                        WHERE client_id = %s AND assigned_technician = %s
                    """, (client_id, email))

                # Manager: get all assigned facilities
                elif context["role"] == "manager":
                    cur.execute("""
                        SELECT facility_id FROM manager_facilities WHERE email = %s
                    """, (email,))
                    facilities = [row[0] for row in cur.fetchall()]

                    # If no extra assignments, fallback to their original facility
                    if not facilities:
                        facilities = [context["facility_id"]]

                    cur.execute(base_query + """
                        WHERE client_id = %s AND facility_id = ANY(%s)
                    """, (client_id, facilities))

                # Director: all work orders for client
                else:
                    cur.execute(base_query + """
                        WHERE client_id = %s
                    """, (client_id,))

                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                from datetime import datetime, date

                def serialize(row, columns):
                    result = {}
                    for col, val in zip(columns, row):
                        if isinstance(val, (datetime, date)):
                            result[col] = val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(val, datetime) else val.strftime('%Y-%m-%d')
                        else:
                            result[col] = val
                    return result

                self.write({"work_orders": [serialize(row, columns) for row in rows]})

        finally:
            self.application.db.put_connection(conn)

    async def post(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]  

        try:
            data = tornado.escape.json_decode(self.request.body)
            tag_number = data.get("tag_number")
            facility_id = data.get("facility_id")
            description = data.get("description")
            wo_type = data.get("wo_type")
            wo_priority = data.get("wo_priority")
            assigned_to_dept = data.get("assigned_to_dept")
            dateneeded = data.get("dateneeded")
            requestercomments = data.get("requestercomments")
            assigned_technician = data.get("assigned_technician")
    
            if not all([tag_number, facility_id, description, wo_type, wo_priority, assigned_to_dept, dateneeded, requestercomments]):
                self.set_status(400)
                self.write({"error": "Missing required fields"})
                return

            result = await self.asset_service.create_work_order(
                client_id, tag_number, facility_id, description, wo_type, wo_priority, assigned_to_dept, dateneeded, requestercomments, assigned_technician
            )
            if result["success"]:
                self.write({"message": "Work order created successfully", "wo_number": result["wo_number"]})
            else:
                self.set_status(400)
                self.write({"error": result["error"]})
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})

class ModifyWorkOrderHandler(BaseApiHandler):
    async def get(self, wo_number):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]  


        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT wo_number, wo_description, WO_Type, WO_Priority, AssignedToDept,
                           dateneeded, assigned_technician, requestercomments,
                           parts_needed, parts_quantity, work_order_status, work_activity_description
                           
                    FROM work_order
                    WHERE client_id = %s AND wo_number = %s
                    """,
                    (client_id, wo_number)
                )
                row = cur.fetchone()
                if not row:
                    self.set_status(404)
                    self.write({"error": "Work order not found"})
                    return

                work_order = {
                    "wo_number": row[0],
                    "wo_description": row[1],
                    "wo_type": row[2],
                    "wo_priority": row[3],
                    "assignedtodept": row[4],
                    "dateneeded_str": row[5].strftime("%Y-%m-%d") if row[5] else "",
                    "assigned_technician": row[6] or "",
                    "requestercomments": row[7] or "",
                    "parts_needed": row[8] or "",
                    "parts_quantity": row[9] or "",
                    "work_order_status": row[10] or "",
                    "work_activity_description": row[11] or ""
                }

                self.render("modify_work_orders.html", wo=work_order)
        except Exception as e:
            import traceback
            print("Modify GET error:", traceback.format_exc())
            self.set_status(500)
            self.write({"error": "Internal server error"})
        finally:
            self.application.db.put_connection(conn)

    async def post(self, wo_number):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]  

        try:
            data = tornado.escape.json_decode(self.request.body)
            result = await self.asset_service.update_work_order(
                client_id,
                wo_number,
                data.get("wo_description"),
                data.get("wo_type"),
                data.get("wo_priority"),
                data.get("assignedtodept"),
                data.get("dateneeded"),
                data.get("assigned_technician"),
                data.get("requestercomments"),
                data.get("parts_needed"),
                data.get("parts_quantity"),
                data.get("work_order_status"),
                data.get("work_activity_description")
            )

            if result["success"]:
                self.write({"message": "Work order updated successfully"})
            else:
                self.set_status(400)
                self.write({"error": result["error"]})
        except Exception as e:
            import traceback
            print("Error in ModifyWorkOrderHandler POST:", traceback.format_exc())
            self.set_status(500)
            self.write({"error": "Internal server error"})

      
class WorkOrderTypeHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]  


        types = await self.asset_service.get_work_order_types()
        self.write({"work_order_types": types})


class WorkOrderPriorityHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"]  


        priorities = await self.asset_service.get_work_order_priorities()
        self.write({"work_order_priorities": priorities})

class DepartmentHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        client_id = user["client_id"] 


        depts = await self.asset_service.get_departments()
        self.write({"departments": depts})


class PurchaseHistoryHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return
        client_id = user["client_id"]

        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT part_name, quantity_purchased, purchase_date
                    FROM purchase_history
                    ORDER BY purchase_date DESC
                """)
                rows = cur.fetchall()
                history = [
                    {
                        "part_name": row[0],
                        "quantity_purchased": row[1],
                        "purchase_date": row[2].strftime("%Y-%m-%d %H:%M")
                    }
                    for row in rows
                ]
                self.write({"history": history})
        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})
        finally:
            self.application.db.put_connection(conn)
