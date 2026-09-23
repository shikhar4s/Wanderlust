from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import *
from .serializers import *
from .services import ItineraryService,LocationService

class OwnerMixin:
 def get_queryset(self): return super().get_queryset().filter(tourist=self.request.user)
 def perform_create(self,s): s.save(tourist=self.request.user)
class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Destination.objects.prefetch_related('places');serializer_class=DestinationSerializer
 @action(detail=False,methods=['get'],permission_classes=[AllowAny])
 def search(self,request):
  q=request.query_params.get('q','').strip()
  if not q:return Response({'detail':'Enter a destination.'},status=400)
  try:return Response({'provider':'OpenStreetMap Nominatim','results':LocationService().search(q)})
  except Exception:return Response({'detail':'Live search is temporarily unavailable.','retryable':True},status=503)
class PlaceViewSet(viewsets.ReadOnlyModelViewSet):queryset=Place.objects.select_related('destination');serializer_class=PlaceSerializer
class TripViewSet(OwnerMixin,viewsets.ModelViewSet):
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

