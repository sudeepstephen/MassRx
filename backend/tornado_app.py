import tornado.ioloop
import tornado.web
import os
import traceback
from base_handler import *
import json
from tornado.options import define, options
from api import (
    AssetDeleteHandler, AssetDetailsHandler, AssetEditHandler, DeleteAssetFileHandler, GetAssetImagesHandler, MediaFileHandler, PartsHandler, PurchaseApproveHandler, PurchaseDeclineHandler, PurchaseHistoryHandler, PurchaseStatusUpdateHandler, RegisterHandler, LoginHandler, AssetHandler, FacilityHandler, ManagerListHandler, AssignFacilityHandler, 
    RemoveFacilityHandler, CurrentUserHandler, AssetTypeHandler, UploadAssetImagesHandler, WorkOrderHandler, ModifyWorkOrderHandler, 
    WorkOrderTypeHandler, WorkOrderPriorityHandler, DepartmentHandler
)

# Define command-line options
define("port", default=8888, help="Run on the given port", type=int)
define("db_host", default="127.0.0.1", help="Database host")
define("db_port", default=5432, help="Database port", type=int)
define("db_name", default="Hospital_Inventory", help="Database name")
define("db_user", default="postgres", help="Database user")
define("db_password", default="Altered_Carb0n!", help="Database password")

# Base Handler for web pages
# Web Page Handlers
class LoginPageHandler(BaseHandler):
    def get(self):
        self.render("login.html")

class RegisterPageHandler(BaseHandler):
    def get(self):
        self.render("register.html")

class DashboardPageHandler(BaseHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.redirect("/")
            return
        self.render("dashboard.html")

class AddAssetPageHandler(BaseHandler):
    async def get(self):
        if not self.get_current_user():
            self.redirect("/")
            return
        self.render("add_asset.html")

class ViewAssetsPageHandler(BaseHandler):
    async def get(self):
        if not self.get_current_user():
            self.redirect("/")
            return
        self.render("view_assets.html")

class CreateWorkOrderPageHandler(BaseHandler):
    async def get(self):
        if not self.get_current_user():
            self.redirect("/")
            return
        self.render("create_work_order.html")

class ViewWorkOrdersPageHandler(BaseHandler):
    async def get(self):
        if not self.get_current_user():
            self.redirect("/")
            return
        self.render("view_work_orders.html")

class FacilityAccessPageHandler(BaseHandler):
    async def get(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write("Unauthorized")
            return

        context = await self.get_user_context(user["email"])

        if not context or context["role"] != "director":
            self.set_status(403)
            self.write("Forbidden")
            return

        self.render("facility_access.html")

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("token")
        self.redirect("/")

class NotFoundHandler(tornado.web.RequestHandler):
    def prepare(self):
        raise tornado.web.HTTPError(404)
    
class PurchaseHistoryPageHandler(BaseHandler):
    async def get(self):
        if not self.get_current_user():
            self.redirect("/")
            return
        self.render("purchase_history.html")

# Application Setup
class Application(tornado.web.Application):
    def __init__(self):
        from core import Database
        self.db = Database()
        web_root = os.path.join(os.path.dirname(__file__), "..", "flutter_web_build"
       )
        handlers = [
            (r"/", LoginHandler),
            (r"/login", LoginHandler),
            (r"/register", RegisterPageHandler),
            (r"/dashboard", DashboardPageHandler),
            (r"/add_asset", AddAssetPageHandler),
            (r"/view_assets", ViewAssetsPageHandler),
            (r"/asset_details", AssetDetailsHandler),
            (r"/asset_edit", AssetEditHandler),
            (r"/asset_delete", AssetDeleteHandler),
            (r"/api/assets/upload_images", UploadAssetImagesHandler),
            (r"/api/asset_images", UploadAssetImagesHandler),
            (r"/api/assets/images", GetAssetImagesHandler),
            (r"/api/assets/delete_file/([0-9]+)", DeleteAssetFileHandler),
            (r"/media/([0-9]+)", MediaFileHandler),
            (r"/create_work_order", CreateWorkOrderPageHandler),
            (r"/logout", LogoutHandler),
            (r"/api/register", RegisterHandler),
            (r"/api/login", LoginHandler),
            (r"/api/me", CurrentUserHandler),
            (r"/api/managers", ManagerListHandler),
            (r"/api/assign_facility", AssignFacilityHandler),
            (r"/api/remove_facility", RemoveFacilityHandler),
            (r"/facility_access", FacilityAccessPageHandler),
            (r"/api/assets", AssetHandler),
            (r"/api/assets/([^/]+)/([^/]+)", AssetHandler),
            (r"/api/facilities", FacilityHandler),
            (r"/api/asset_types", AssetTypeHandler),
            (r"/api/work_orders", WorkOrderHandler),
            (r"/api/work_order_types", WorkOrderTypeHandler),
            (r"/api/work_order_priorities", WorkOrderPriorityHandler),
            (r"/view_work_orders", ViewWorkOrdersPageHandler),
            (r"/modify_work_orders/([^/]+)", ModifyWorkOrderHandler), 
            (r"/api/parts", PartsHandler),
            (r"/api/departments", DepartmentHandler),
            (r"/purchase_history", PurchaseHistoryPageHandler),          # for HTML
            (r"/api/purchase_history", PurchaseHistoryHandler),          # for JSON
            (r"/api/purchase_approve/([0-9]+)", PurchaseApproveHandler),
            (r"/api/purchase_decline/([0-9]+)", PurchaseDeclineHandler),
            (r"/api/purchase_status/(\d+)", PurchaseStatusUpdateHandler),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": os.path.join(os.path.dirname(__file__), "static")}),
            #(r"/(.*)", tornado.web.StaticFileHandler, {"path": web_root, "default_filename": "index.html"}),
        ]
        settings = {
            "debug": True,
            "cookie_secret": "super_secret_cookie_key_123",
            "template_path": os.path.join(os.path.dirname(__file__), "templates"),
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
            "default_handler_class": NotFoundHandler
        }
        super().__init__(handlers, **settings)

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    print(f"Server running on http://localhost:{options.port}")
    tornado.ioloop.IOLoop.current().start()