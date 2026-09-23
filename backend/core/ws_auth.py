from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


class JwtSubprotocolAuthMiddleware:
    """Authenticate browser WebSockets without putting JWTs in URLs or logs."""
    def __init__(self, inner):self.inner=inner
    async def __call__(self,scope,receive,send):
        protocols=scope.get('subprotocols',[])
        scope['user']=AnonymousUser()
        if len(protocols)>=2 and protocols[0]=='jwt':
            scope['user']=await self.authenticate(protocols[1])
        return await self.inner(scope,receive,send)
    @database_sync_to_async
    def authenticate(self,raw):
        try:
            backend=JWTAuthentication()
            token=backend.get_validated_token(raw)
            return backend.get_user(token)
        except Exception:return AnonymousUser()
