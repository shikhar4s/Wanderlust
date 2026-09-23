from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny,BasePermission,IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from .models import *
from .serializers import *
from .services import ItineraryService,LocationService,PlacesService

class IsTourist(BasePermission):
 def has_permission(self,request,view):return request.user.is_authenticated and request.user.role=='TOURIST'
class IsGuide(BasePermission):
 def has_permission(self,request,view):return request.user.is_authenticated and request.user.role=='GUIDE'

class AuthViewSet(viewsets.ViewSet):
 permission_classes=[AllowAny]
 @action(detail=False,methods=['post'])
 def signup(self,request):
  serializer=SignupSerializer(data=request.data);serializer.is_valid(raise_exception=True);user=serializer.save();refresh=RefreshToken.for_user(user)
  return Response({'access':str(refresh.access_token),'refresh':str(refresh),'user':UserSerializer(user).data},status=201)
 @action(detail=False,methods=['get'],permission_classes=[IsAuthenticated])
 def me(self,request):return Response(UserSerializer(request.user).data)

class OwnerMixin:
 def get_queryset(self): return super().get_queryset().filter(tourist=self.request.user)
 def perform_create(self,s): s.save(tourist=self.request.user)
class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Destination.objects.prefetch_related('places');serializer_class=DestinationSerializer
 @action(detail=False,methods=['get'],permission_classes=[AllowAny])
 def search(self,request):
  q=request.query_params.get('q','').strip()
  if not q:return Response({'detail':'Enter a destination.'},status=400)
  try:
   locations=LocationService().search(q)
   if not locations:return Response({'detail':'No destination found.','results':[]},status=404)
   hit=locations[0];parts=hit.get('display_name',q).split(',');dest,_=Destination.objects.update_or_create(provider_id=f"nominatim:{hit['place_id']}",defaults={'name':parts[0].strip(),'country':parts[-1].strip(),'latitude':float(hit['lat']),'longitude':float(hit['lon'])})
   provider_warning=None
   try:
    live=PlacesService().nearby(dest.latitude,dest.longitude)
    for item in live:Place.objects.update_or_create(provider_id=item.pop('provider_id'),defaults={**item,'destination':dest})
   except Exception:provider_warning='Attractions provider is temporarily unavailable; showing cached results.'
   data=DestinationSerializer(dest).data
   if provider_warning:data['warning']=provider_warning
   return Response(data)
  except Exception:return Response({'detail':'Live search is temporarily unavailable.','retryable':True},status=503)
class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Place.objects.select_related('destination');serializer_class=PlaceSerializer
 def get_queryset(self):
  qs=super().get_queryset();destination=self.request.query_params.get('destination');return qs.filter(destination_id=destination) if destination else qs
class TripViewSet(OwnerMixin,viewsets.ModelViewSet):
 permission_classes=[IsTourist]
 queryset=Trip.objects.select_related('destination').prefetch_related('days__stops__place');serializer_class=TripSerializer
 @action(detail=True,methods=['post'])
 def generate(self,request,pk=None):
  trip=self.get_object();ids=request.data.get('place_ids',[]);day_count=(trip.end_date-trip.start_date).days+1;places=list(Place.objects.filter(pk__in=ids,destination=trip.destination))
  if not places:return Response({'detail':'Select at least one place.'},status=400)
  groups=ItineraryService.generate(places,day_count)
  with transaction.atomic():
   trip.days.all().delete()
   for i,group in enumerate(groups):
    day=TripDay.objects.create(trip=trip,date=trip.start_date+__import__('datetime').timedelta(days=i),position=i+1)
    for j,place in enumerate(group):TripStop.objects.create(day=day,place=place,position=j+1)
  return Response(self.get_serializer(trip).data)
class GuideViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=GuideProfile.objects.select_related('user').prefetch_related('services','coverage','availability_rules');serializer_class=GuideProfileSerializer
class GuideRequestViewSet(OwnerMixin,viewsets.ModelViewSet):
 permission_classes=[IsTourist]
 queryset=GuideRequest.objects.select_related('guide__user','service','trip');serializer_class=GuideRequestSerializer
class BookingViewSet(viewsets.ReadOnlyModelViewSet):
 serializer_class=BookingSerializer
 def get_queryset(self):return Booking.objects.filter(Q(tourist=self.request.user)|Q(guide__user=self.request.user)).select_related('guide__user','tourist','service')
 @action(detail=False,methods=['post'])
 def confirm(self,request):
  req=GuideRequest.objects.select_related('guide','service','trip__destination').get(pk=request.data['request_id'])
  if req.guide.user_id!=request.user.id:return Response({'detail':'Only the requested guide can confirm.'},status=403)
  try:booking=Booking.confirm(req,request.data.get('final_price',req.service.price))
  except ValidationError as e:return Response({'detail':e.message},status=409)
  return Response(self.get_serializer(booking).data,status=201)
