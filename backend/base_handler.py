import traceback
import tornado.web
import tornado.ioloop
from core import UserService

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "authorization, Content-Type")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        error_trace = traceback.format_exc()
        self.finish({
            "error": self._reason,
            "traceback": error_trace
        })

    def initialize(self):
        self.db = self.application.db
        self.user_service = UserService(self.db)

    def get_current_user(self):
        token = self.get_token_from_request()
        if not token:
            return None

        try:
            return self.user_service.verify_jwt(token)
        except Exception:
            return None

    def get_token_from_request(self):
        auth_header = self.request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        cookie_token = self.get_secure_cookie("token")
        if cookie_token:
            return cookie_token.decode()
        return None

    async def get_user_context(self, email):
        return await tornado.ioloop.IOLoop.current().run_in_executor(None, self.user_service.get_user_context, email)
