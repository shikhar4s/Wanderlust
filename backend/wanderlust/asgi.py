import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','wanderlust.settings')
from django.core.asgi import get_asgi_application
django_asgi_app=get_asgi_application()
from channels.routing import ProtocolTypeRouter,URLRouter
from core.ws_auth import JwtSubprotocolAuthMiddleware
from core.routing import websocket_urlpatterns
application=ProtocolTypeRouter({'http':django_asgi_app,'websocket':JwtSubprotocolAuthMiddleware(URLRouter(websocket_urlpatterns))})
