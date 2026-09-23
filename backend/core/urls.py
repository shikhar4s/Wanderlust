from rest_framework.routers import DefaultRouter
from .views import AuthViewSet,DestinationViewSet,PlaceViewSet,TripViewSet,GuideViewSet,GuideRequestViewSet,BookingViewSet
router=DefaultRouter();router.register('auth',AuthViewSet,basename='auth');router.register('destinations',DestinationViewSet);router.register('places',PlaceViewSet);router.register('trips',TripViewSet);router.register('guides',GuideViewSet);router.register('requests',GuideRequestViewSet);router.register('bookings',BookingViewSet,basename='booking')
urlpatterns=router.urls
