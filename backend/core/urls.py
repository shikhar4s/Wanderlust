from rest_framework.routers import DefaultRouter
from .views import AuthViewSet,DestinationViewSet,PlaceViewSet,TripViewSet,GuideViewSet,GuideRequestViewSet,BookingViewSet
from .api_extras import GuideAccountViewSet,CoverageViewSet,ServiceViewSet,RuleViewSet,ExceptionViewSet,ConversationViewSet,OfferViewSet,ReviewViewSet,NotificationViewSet,AssistantViewSet
router=DefaultRouter();router.register('auth',AuthViewSet,basename='auth');router.register('destinations',DestinationViewSet);router.register('places',PlaceViewSet);router.register('trips',TripViewSet);router.register('guides',GuideViewSet);router.register('requests',GuideRequestViewSet);router.register('bookings',BookingViewSet,basename='booking')
router.register('guide-account',GuideAccountViewSet,basename='guide-account');router.register('coverage',CoverageViewSet);router.register('services',ServiceViewSet);router.register('availability-rules',RuleViewSet);router.register('availability-exceptions',ExceptionViewSet);router.register('conversations',ConversationViewSet,basename='conversation');router.register('offers',OfferViewSet,basename='offer');router.register('reviews',ReviewViewSet,basename='review');router.register('notifications',NotificationViewSet,basename='notification')
router.register('assistant',AssistantViewSet,basename='assistant')
urlpatterns=router.urls
