import json
import os
import tornado.web
import tornado.escape
from core import UserService, AssetService
from types import SimpleNamespace
from base_handler import *


class BaseApiHandler(BaseHandler):
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
            return self.user_service.verify_jwt(token)
        except Exception as e:
            print("JWT decode failed:", e)
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
                self.write({
                    "token": token,
                    "message": "Login successful",
                    "redirect": "/dashboard"
                })
            else:
                self.set_status(401)
                self.write({"error": "Invalid credentials"})

        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})
        except Exception as e:
            self.set_status(500)
            self.write({"error": "Internal Server Error", "details": str(e)})

class ResetPasswordHandler(BaseApiHandler):
    async def post(self):
        try:
            body = tornado.escape.json_decode(self.request.body)
            email = body.get("email")

            if not email:
                self.set_status(400)
                self.write({"error": "Email is required"})
                return

            user = self.user_service.get_user_by_email(email)
            if not user:
                self.set_status(404)
                self.write({"error": "User not found"})
                return

            # Simulate sending reset link (add email logic later)
            self.write({"message": f"Password reset link sent to {email}"})

        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})

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
            tag_number = self.get_argument("tag_number")
            facility_id = self.get_argument("facility_id")
            description = self.get_argument("description", "")
            type_desc = self.get_argument("type_desc", "")
            manufacturer_desc = self.get_argument("manufacturer_desc", "")
            model_num = self.get_argument("model_num", "")
            equ_model_name = self.get_argument("equ_model_name", "")
            orig_manufacturer_desc = self.get_argument("orig_manufacturer_desc", "")
            serial_num = self.get_argument("serial_num", "")
            equ_status_desc = self.get_argument("equ_status_desc", "")
            udi_code = self.get_argument("udi_code", "")
            guid = self.get_argument("guid", "")

            if not tag_number or not facility_id:
                self.set_status(400)
                self.write({"error": "Missing required fields: tag_number, facility_id"})
                return

            # Step 1: Add the asset
            result = await self.asset_service.add_asset(
                client_id, tag_number, description, type_desc, manufacturer_desc,
                model_num, equ_model_name, orig_manufacturer_desc, serial_num,
                equ_status_desc, facility_id, udi_code, guid
            )

            if not result["success"]:
                self.set_status(400)
                self.write({"error": result["error"]})
                return
            self.write({"message": "Asset created successfully!"})

        except Exception as e:
            self.set_status(500)
            self.write({"error": f"Server error: {str(e)}"})

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
            description = self.get_body_argument("description", "")
            type_desc = self.get_body_argument("type_desc", "")
            manufacturer_desc = self.get_body_argument("manufacturer_desc", "")
            model_num = self.get_body_argument("model_num", "")
            equ_model_name = self.get_body_argument("equ_model_name", "")
            orig_manufacturer_desc = self.get_body_argument("orig_manufacturer_desc", "")
            serial_num = self.get_body_argument("serial_num", "")
            equ_status_desc = self.get_body_argument("equ_status_desc", "")
            udi_code = self.get_body_argument("udi_code", "")
            guid = self.get_body_argument("guid", "")

            result = await self.asset_service.update_asset(
                client_id, tag_number, facility_id, description, type_desc,
                manufacturer_desc, model_num, equ_model_name, orig_manufacturer_desc,
                serial_num, equ_status_desc, udi_code, guid
            )

            if result["success"]:
                self.write({"message": "Asset updated successfully"})
            else:
                self.set_status(404 if result["error"] == "Asset not found" else 400)
                self.write({"error": result["error"]})
        except Exception as e:
            self.set_status(500)
            self.write({"error": f"Server error: {str(e)}"})

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

class AssetEditHandler(BaseApiHandler):
    def prepare(self):
        pass

    async def get(self):
        tag = self.get_query_argument("tag_number")
        facility = self.get_query_argument("facility_id")

        service = AssetService(self.db)
        client_id = self.get_current_user()["client_id"]
        asset_data = await service.get_asset_by_tag_and_facility(client_id, tag, facility)

        if asset_data:
            from types import SimpleNamespace
            self.render("asset_edit.html", asset=SimpleNamespace(**asset_data))
        else:
            self.write("Asset not found")

    async def post(self):
        try:
            data = json.loads(self.request.body)
        except json.JSONDecodeError:
            self.set_status(400)
            self.write({"success": False, "error": "Invalid JSON"})
            return

        tag = data.get("tag_number")
        facility = data.get("facility_id")
        client_id = self.get_current_user()["client_id"]
        description = data.get("description")
        type_desc = data.get("type_desc")
        manufacturer_desc = data.get("manufacturer_desc")
        model_num = data.get("model_num")
        equ_model_name = data.get("equ_model_name")
        orig_manufacturer_desc = data.get("orig_manufacturer_desc")
        serial_num = data.get("serial_num")
        equ_status_desc = data.get("equ_status_desc")
        udi_code = data.get("udi_code")
        guid = data.get("guid")

        if not tag or not facility:
            self.set_status(400)
            self.write({"success": False, "error": "Missing tag_number or facility_id"})
            return

        service = AssetService(self.db)
        result = await service.update_asset(
            client_id, tag, facility,
            description, type_desc, manufacturer_desc,
            model_num, equ_model_name, orig_manufacturer_desc,
            serial_num, equ_status_desc, udi_code, guid
        )

        if result["success"]:
            self.write({"success": True})
        else:
            self.set_status(400)
            self.write({"success": False, "error": result["error"]})

class AssetDetailsHandler(BaseApiHandler):
    def prepare(self):
        pass

    async def get(self):
        tag = self.get_query_argument("tag_number")
        facility = self.get_query_argument("facility_id")
        client_id = self.get_current_user()["client_id"]

        service = AssetService(self.db)
        asset_data = await service.get_asset_by_tag_and_facility(client_id, tag, facility)

        if asset_data:
            from types import SimpleNamespace
            self.render("asset_details.html", asset=SimpleNamespace(**asset_data))
        else:
            self.write("Asset not found")

class AssetDeleteHandler(BaseApiHandler):
    def prepare(self):
        pass

    async def get(self):
        tag = self.get_query_argument("tag_number")
        facility = self.get_query_argument("facility_id")
        self.render("asset_delete.html", tag_number=tag, facility_id=facility)

    async def post(self):
        tag = self.get_body_argument("tag_number")
        facility = self.get_body_argument("facility_id")
        client_id = self.get_current_user()["client_id"]

        service = AssetService(self.db)  
        result = await service.delete_asset(client_id, tag, facility)


        if result["success"]:
            self.redirect("/view_assets")
        else:
            self.write(f"Error: {result['error']}")

class UploadAssetImagesHandler(BaseApiHandler):
    async def post(self):
        user = self.get_current_user()
        print("[UPLOAD] User:", user)

        if not user:
            print("[UPLOAD] No user — 401")
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        tag_number = self.get_argument("tag_number", None)
        facility_id = self.get_argument("facility_id", None)
        files = self.request.files.get("files", [])
        descriptions = self.get_arguments("descriptions[]")
        content_types = self.get_arguments("content_types[]")

        print("[UPLOAD] Received:", len(files), "files")

        if not files:
            print("[UPLOAD] No files uploaded")
            self.set_status(400)
            self.write({"error": "No files uploaded."})
            return

        if len(files) != len(descriptions):
            print("[UPLOAD] Mismatch descriptions/files")
            self.set_status(400)
            self.write({"error": "Each image must have a matching description."})
            return

        try:
            for i, fileinfo in enumerate(files):
                description = descriptions[i] if i < len(descriptions) else ""
                content_type = content_types[i] if i < len(content_types) else fileinfo.get("content_type")

                print(f"[UPLOAD] Calling upload_image_to_disk for file: {fileinfo['filename']}")
                await self.asset_service.upload_image_to_disk(
                    tag_number, facility_id, user["client_id"],
                    fileinfo, description, content_type
                )

            print("[UPLOAD] Upload completed successfully")
            self.write({"success": True})
        except Exception as e:
            print("[UPLOAD ERROR]:", e)
            self.set_status(500)
            self.write({"error": "Upload failed: " + str(e)})


class GetAssetImagesHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        tag_number = self.get_argument("tag_number")
        facility_id = self.get_argument("facility_id")
        images = self.asset_service.get_images_for_asset(tag_number, facility_id, user["client_id"])
        self.write({"images": images})

class DeleteAssetFileHandler(BaseApiHandler):
    async def delete(self, file_id):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        success = await self.asset_service.delete_asset_image(file_id, user["client_id"])
        if success:
            self.write({"success": True})
        else:
            self.set_status(400)
            self.write({"error": "Delete failed: Asset not found"})

class MediaFileHandler(BaseApiHandler):
    async def get(self, image_id):
        conn = self.application.db.get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT image_path, content_type FROM asset_images WHERE id = %s
            """, (image_id,))
            row = cur.fetchone()

        if not row:
            self.set_status(404)
            self.write("File not found")
            return

        image_path, content_type = row
        full_path = os.path.join("static", image_path)

        if not os.path.exists(full_path):
            self.set_status(404)
            self.write("File not found on disk")
            return

        with open(full_path, "rb") as f:
            self.set_header("Content-Type", content_type or "application/octet-stream")
            self.write(f.read())

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

class PartsHandler(BaseApiHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.finish({"error": "Unauthorized"})
            return

        client_id = user.get("client_id")

        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT part_name FROM parts WHERE client_id = %s ORDER BY part_name",
                    (client_id,)
                )
                parts = [row[0] for row in cur.fetchall()]
                self.write({"parts": parts})
        finally:
            self.db.put_connection(conn)


      
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
                SELECT id, part, requested_quantity, requested_date, requested_by,
                    purchase_order_status, approval_status, decline_reason
                FROM purchase_history
                WHERE client_id = %s
                ORDER BY requested_date DESC
            """, (client_id,))

                rows = cur.fetchall()
                history = [
                    {
                        "id": row[0],
                        "part": row[1],
                        "requested_quantity": row[2],
                        "requested_date": row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "",
                        "requested_by": row[4],
                        "purchase_order_status": row[5],
                        "approval_status": row[6],
                        "decline_reason": row[7]
                    }
                    for row in rows
                ]
                self.write({"history": history})
        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})
        finally:
            self.application.db.put_connection(conn)


class PurchaseApproveHandler(BaseApiHandler):
    async def post(self, request_id):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Update status to Created
                cur.execute("""
                    UPDATE purchase_history
                    SET approval_status = 'Approved',
                        purchase_order_status = 'Created'
                    WHERE id = %s
                """, (request_id,))
                conn.commit()
                # 2. (Optional) Send email to confirm creation (can be added later)
                self.write({"success": True})
        except Exception as e:
            conn.rollback()
            self.set_status(500)
            self.write({"error": str(e)})
        finally:
            self.application.db.put_connection(conn)


class PurchaseDeclineHandler(BaseApiHandler):
    async def post(self, request_id):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({"error": "Unauthorized"})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            reason = data.get("reason", "").strip()
            if not reason:
                self.set_status(400)
                self.write({"error": "Decline reason is required."})
                return
        except Exception:
            self.set_status(400)
            self.write({"error": "Invalid request body."})
            return

        conn = self.application.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Update status to Declined and save comment
                cur.execute("""
                    UPDATE purchase_history
                    SET approval_status = 'Declined',
                        purchase_order_status = 'Declined',
                        decline_reason = %s
                    WHERE id = %s
                """, (reason, request_id))
                conn.commit()
                self.write({"success": True})
        except Exception as e:
            conn.rollback()
            self.set_status(500)
            self.write({"error": str(e)})
        finally:
            self.application.db.put_connection(conn)

class PurchaseStatusUpdateHandler(BaseApiHandler):
    async def post(self, request_id):
        user = self.get_current_user()
        if not user or user["role"] != "purchaser":
            self.set_status(403)
            self.write({"error": "Only purchasers can update status."})
            return

        try:
            data = tornado.escape.json_decode(self.request.body)
            status = data.get("status")

            if status not in ['Waiting for approval', 'Created', 'In transit', 'Completed']:
                self.set_status(400)
                self.write({"error": "Invalid status."})
                return

            conn = self.application.db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE purchase_history
                        SET purchase_order_status = %s
                        WHERE id = %s
                    """, (status, request_id))
                    conn.commit()
                    self.write({"success": True})
            finally:
                self.application.db.put_connection(conn)

        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})








