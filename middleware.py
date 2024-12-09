from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import jwt

# Middleware for checking our own JWT tokens
class SecurityTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, secret_key: str, required_scope: str):
        super().__init__(app)
        self.secret_key = secret_key
        self.required_scope = required_scope

    async def dispatch(self, request: Request, call_next):
        # Check for X-Security-Token header - sent from UI app
        token = request.headers.get("X-Security-Token")
        if not token:
            return JSONResponse(
                status_code=401, content={"detail": "X-Security-Token header is missing"}
            )

        try:
            # Decode the JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # Validate the required scope
            scopes = payload.get("scope", "").split()
            if self.required_scope not in scopes:
                return JSONResponse(
                    status_code=403, content={"detail": "Insufficient scope"}
                )

        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401, content={"detail": "Token has expired"}
            )
        except jwt.InvalidTokenError:
            return JSONResponse(
                status_code=401, content={"detail": "Invalid token"}
            )

        # If validation is successful, proceed to the next middleware or route
        response = await call_next(request)
        return response
