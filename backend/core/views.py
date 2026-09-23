from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from zoneinfo import ZoneInfo
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny,BasePermission,IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from .models import *
from .serializers import *
from .services import ItineraryService,LocationService,PlacesService,AvailabilityService,distance_km

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
  parts=[part.strip() for part in q.split(',') if part.strip()]
  city=parts[0]
  matches=Destination.objects.prefetch_related('places').filter(name__iexact=city)
  cached=matches.filter(country__iexact=parts[-1]).first() if len(parts)>1 else matches.first()
  if cached and cached.places.exists():
   return Response(DestinationSerializer(cached).data)
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
  except Exception:
   if cached:
    data=DestinationSerializer(cached).data
    data['warning']='Live search is temporarily unavailable; showing saved destination data.'
    return Response(data)
   return Response({'detail':'Live search is temporarily unavailable. Please try again.','retryable':True},status=503)
class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Place.objects.select_related('destination');serializer_class=PlaceSerializer
 def get_queryset(self):
  qs=super().get_queryset();destination=self.request.query_params.get('destination');return qs.filter(destination_id=destination) if destination else qs
class TripViewSet(OwnerMixin,viewsets.ModelViewSet):
 permission_classes=[IsTourist]
 queryset=Trip.objects.select_related('destination').prefetch_related('days__stops__place');serializer_class=TripSerializer
 @action(detail=False,methods=['post'])
 def plan(self,request):
  serializer=self.get_serializer(data=request.data);serializer.is_valid(raise_exception=True)
  destination=serializer.validated_data['destination'];ids=request.data.get('place_ids',[])
  if not isinstance(ids,list) or not ids or len(ids)!=len(set(ids)):return Response({'detail':'Select unique attractions.'},status=400)
  places=list(Place.objects.filter(pk__in=ids,destination=destination))
  if len(places)!=len(ids):return Response({'detail':'Some places are not in this destination.'},status=400)
  day_count=(serializer.validated_data['end_date']-serializer.validated_data['start_date']).days+1
  groups=ItineraryService.generate(places,day_count)
  with transaction.atomic():
   trip=serializer.save(tourist=request.user)
   for i,group in enumerate(groups):
    day=TripDay.objects.create(trip=trip,date=trip.start_date+__import__('datetime').timedelta(days=i),position=i+1)
    for j,place in enumerate(group):TripStop.objects.create(day=day,place=place,position=j+1,distance_from_previous_km=round(distance_km(group[j-1],place),2) if j else None)
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data,status=201)
 @action(detail=True,methods=['post'])
 def generate(self,request,pk=None):
  trip=self.get_object();ids=request.data.get('place_ids',[]);day_count=(trip.end_date-trip.start_date).days+1;places=list(Place.objects.filter(pk__in=ids,destination=trip.destination))
  if not places:return Response({'detail':'Select at least one place.'},status=400)
  if len(places)!=len(set(ids)):return Response({'detail':'Some selected places are not in this destination.'},status=400)
  groups=ItineraryService.generate(places,day_count)
  with transaction.atomic():
   trip.days.all().delete()
   for i,group in enumerate(groups):
    day=TripDay.objects.create(trip=trip,date=trip.start_date+__import__('datetime').timedelta(days=i),position=i+1)
    for j,place in enumerate(group):TripStop.objects.create(day=day,place=place,position=j+1,distance_from_previous_km=round(distance_km(group[j-1],place),2) if j else None)
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data)
 @action(detail=True,methods=['post'])
 def add_place(self,request,pk=None):
  trip=self.get_object();day=get_object_or_404(trip.days,pk=request.data.get('day_id'))
  place=get_object_or_404(Place,pk=request.data.get('place_id'),destination=trip.destination)
  if TripStop.objects.filter(day__trip=trip,place=place).exists():return Response({'detail':'Place is already in this trip.'},status=409)
  TripStop.objects.create(day=day,place=place,position=day.stops.count()+1,manually_edited=True)
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data)
 @action(detail=True,methods=['post'])
 def edit_stops(self,request,pk=None):
  trip=self.get_object();groups=request.data.get('days')
  if not isinstance(groups,list) or len(groups)!=trip.days.count():return Response({'detail':'Provide one ordered stop list for each day.'},status=400)
  days=list(trip.days.all());existing=list(TripStop.objects.filter(day__trip=trip));by_id={stop.id:stop for stop in existing}
  supplied=[sid for group in groups for sid in group]
  if len(supplied)!=len(set(supplied)) or set(supplied)!=set(by_id):return Response({'detail':'Stop IDs must match this trip exactly.'},status=400)
  with transaction.atomic():
   for stop in existing:stop.position+=10000;stop.save(update_fields=['position'])
   for day,ids in zip(days,groups):
    previous=None
    for index,sid in enumerate(ids):
     stop=by_id[sid];stop.day=day;stop.position=index+1;stop.manually_edited=True
     stop.distance_from_previous_km=round(distance_km(previous,stop.place),2) if previous else None
     stop.save(update_fields=['day','position','manually_edited','distance_from_previous_km']);previous=stop.place
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data)
 @action(detail=True,methods=['post'])
 def remove_place(self,request,pk=None):
  trip=self.get_object();stop=get_object_or_404(TripStop,pk=request.data.get('stop_id'),day__trip=trip)
  day=stop.day;stop.delete()
  for index,item in enumerate(day.stops.select_related('place'),1):
   item.position=index;item.manually_edited=True;item.save(update_fields=['position','manually_edited'])
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data)
 @action(detail=True,methods=['post'])
 def optimize(self,request,pk=None):
  trip=self.get_object();day=get_object_or_404(trip.days,pk=request.data.get('day_id'))
  stops=list(day.stops.select_related('place'));route=[]
  if stops:route.append(stops.pop(0))
  while stops:
   nxt=min(stops,key=lambda item:distance_km(route[-1].place,item.place));stops.remove(nxt);route.append(nxt)
  with transaction.atomic():
   for stop in route:stop.position+=10000;stop.save(update_fields=['position'])
   for index,stop in enumerate(route):
    stop.position=index+1;stop.distance_from_previous_km=round(distance_km(route[index-1].place,stop.place),2) if index else None
    stop.manually_edited=True;stop.save(update_fields=['position','distance_from_previous_km','manually_edited'])
  return Response(self.get_serializer(self.get_queryset().get(pk=trip.pk)).data)
class GuideViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=GuideProfile.objects.select_related('user').prefetch_related('services','coverage','availability_rules');serializer_class=GuideProfileSerializer
 def get_queryset(self):
  qs=super().get_queryset();params=self.request.query_params
  if params.get('destination'):qs=qs.filter(coverage__destination_id=params['destination']).distinct()
  if params.get('date') and params.get('start') and params.get('end'):
   from django.utils.dateparse import parse_datetime
   start=parse_datetime(params['start']);end=parse_datetime(params['end'])
   if start and end:qs=[g for g in qs if AvailabilityService.contains(g,start,end)]
  return qs
class GuideRequestViewSet(OwnerMixin,viewsets.ModelViewSet):
 permission_classes=[IsAuthenticated]
 queryset=GuideRequest.objects.select_related('guide__user','service','trip');serializer_class=GuideRequestSerializer
 def get_queryset(self):
  qs=self.queryset.order_by('-created_at','-id')
  return qs.filter(guide__user=self.request.user) if self.request.user.role=='GUIDE' else qs.filter(tourist=self.request.user)
 def create(self,request,*args,**kwargs):
  if request.user.role!='TOURIST':return Response({'detail':'Tourist account required.'},status=403)
  serializer=self.get_serializer(data=request.data);serializer.is_valid(raise_exception=True);data=serializer.validated_data
  if data['trip'].tourist_id!=request.user.id:return Response({'detail':'This trip is not yours.'},status=403)
  if data['service'].guide_id!=data['guide'].id:return Response({'detail':'Service and guide do not match.'},status=400)
  if data['service'].coverage.destination_id!=data['trip'].destination_id:return Response({'detail':'This service does not cover your trip destination.'},status=400)
  if data['start']<=timezone.now():return Response({'detail':'Choose a future tour time.'},status=400)
  tour_day=timezone.localtime(data['start'],ZoneInfo(data['guide'].timezone)).date()
  if not data['trip'].start_date<=tour_day<=data['trip'].end_date:return Response({'detail':'Tour date must fall within your trip.'},status=400)
  if data['people']>data['service'].max_group_size:return Response({'detail':'Group size exceeds this service.'},status=400)
  if data['end']<=data['start'] or not AvailabilityService.contains(data['guide'],data['start'],data['end']):return Response({'detail':'Guide is unavailable during that time.'},status=409)
  if not data['service'].active:return Response({'detail':'This service is inactive.'},status=400)
  with transaction.atomic():
   item=serializer.save(tourist=request.user)
   conversation=Conversation.objects.create(request=item);conversation.participants.add(request.user,item.guide.user)
   Notification.objects.create(user=item.guide.user,kind='GUIDE_REQUEST',title='New guide request',body=f'{request.user.get_full_name()} requested {item.service.title}.')
  return Response(self.get_serializer(item).data,status=201)
 @action(detail=True,methods=['post'])
 def transition(self,request,pk=None):
  item=self.get_object();target=request.data.get('status')
  if request.user.role=='GUIDE' and target not in ('ACCEPTED','DECLINED'):return Response({'detail':'Guide cannot make this transition.'},status=403)
  if request.user.role=='TOURIST' and (target!='CANCELLED' or item.status=='CONFIRMED'):return Response({'detail':'Cancel a confirmed tour through its booking.'},status=403)
  try:item.transition(target)
  except (ValidationError,KeyError) as exc:return Response({'detail':str(exc)},status=400)
  other=item.tourist if request.user.role=='GUIDE' else item.guide.user
  Notification.objects.create(user=other,kind='REQUEST_'+target,title='Guide request '+target.lower())
  return Response(self.get_serializer(item).data)
class BookingViewSet(viewsets.ReadOnlyModelViewSet):
 serializer_class=BookingSerializer
 def get_queryset(self):return Booking.objects.filter(Q(tourist=self.request.user)|Q(guide__user=self.request.user)).select_related('guide__user','tourist','service')
 @action(detail=False,methods=['post'])
 def confirm(self,request):
  req=get_object_or_404(GuideRequest.objects.select_related('guide','service','trip__destination'),pk=request.data.get('request_id'))
  if req.guide.user_id!=request.user.id:return Response({'detail':'Only the requested guide can confirm.'},status=403)
  accepted=req.offers.filter(accepted_at__isnull=False).order_by('-accepted_at').first()
  agreed_price=accepted.amount if accepted else req.service.price
  try:booking=Booking.confirm(req,agreed_price)
  except ValidationError as e:return Response({'detail':str(e)},status=409)
  Notification.objects.create(user=req.tourist,kind='BOOKING_CONFIRMED',title='Booking confirmed',body=req.service.title)
  return Response(self.get_serializer(booking).data,status=201)
 @action(detail=True,methods=['post'])
 def change_status(self,request,pk=None):
  booking=self.get_object();target=request.data.get('status')
  if target=='CANCELLED' and request.user.id in (booking.tourist_id,booking.guide.user_id) and booking.status=='CONFIRMED':pass
  elif target=='COMPLETED' and request.user.id==booking.guide.user_id and booking.status=='CONFIRMED' and booking.end<=timezone.now():pass
  else:return Response({'detail':'Invalid booking transition.'},status=400)
  booking.status=target;booking.save(update_fields=['status'])
  booking.request.status=target;booking.request.save(update_fields=['status'])
  other=booking.tourist if request.user.id==booking.guide.user_id else booking.guide.user
  Notification.objects.create(user=other,kind='BOOKING_'+target,title='Booking '+target.lower())
  return Response(self.get_serializer(booking).data)
