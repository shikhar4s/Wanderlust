from django.core.exceptions import ValidationError
from unicodedata import normalize
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
from rest_framework.parsers import MultiPartParser
from .models import *
from .serializers import *
from .services import ItineraryService,LocationService,PlacesService,AvailabilityService,ImageService,distance_km,distance_coords

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
 def me(self,request):return Response(UserSerializer(request.user,context={'request':request}).data)
 @action(detail=False,methods=['get','patch'],permission_classes=[IsAuthenticated])
 def profile(self,request):
  user=request.user
  if request.method=='PATCH':
   user.first_name=str(request.data.get('first_name',user.first_name)).strip()[:150]
   user.last_name=str(request.data.get('last_name',user.last_name)).strip()[:150]
   user.phone=str(request.data.get('phone',user.phone)).strip()[:30]
   user.save(update_fields=['first_name','last_name','phone'])
   if user.role=='TOURIST':
    profile,_=TouristProfile.objects.get_or_create(user=user)
    for field in ('bio','home_city','travel_style'):
     if field in request.data:setattr(profile,field,str(request.data[field]).strip())
    if 'interests' in request.data:
     if not isinstance(request.data['interests'],list):return Response({'detail':'Interests must be a list.'},status=400)
     profile.interests=[str(item).strip() for item in request.data['interests'] if str(item).strip()][:20]
    profile.full_clean();profile.save()
  data={'user':UserSerializer(user,context={'request':request}).data}
  if user.role=='TOURIST':data['tourist']=TouristProfileSerializer(TouristProfile.objects.get(user=user),context={'request':request}).data
  else:data['guide']=GuideProfileSerializer(user.guide_profile,context={'request':request}).data
  return Response(data)
 @action(detail=False,methods=['post'],permission_classes=[IsAuthenticated],parser_classes=[MultiPartParser])
 def photo(self,request):
  photo=request.FILES.get('photo')
  if not photo:return Response({'detail':'Choose a photo to upload.'},status=400)
  if photo.size>5*1024*1024:return Response({'detail':'Photo must be under 5 MB.'},status=400)
  header=photo.read(16);photo.seek(0)
  extension='png' if header.startswith(b'\x89PNG\r\n\x1a\n') else 'jpg' if header.startswith(b'\xff\xd8\xff') else 'webp' if header[:4]==b'RIFF' and header[8:12]==b'WEBP' else None
  if not extension:return Response({'detail':'Upload a JPG, PNG or WebP photo.'},status=400)
  user=request.user;user.profile_photo.save(f'portrait.{extension}',photo,save=True)
  return Response(UserSerializer(user,context={'request':request}).data)

class OwnerMixin:
 def get_queryset(self): return super().get_queryset().filter(tourist=self.request.user)
 def perform_create(self,s): s.save(tourist=self.request.user)
class DestinationViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Destination.objects.prefetch_related('places');serializer_class=DestinationSerializer
 def get_serializer_class(self):return DestinationSummarySerializer if self.action=='list' else DestinationSerializer
 @action(detail=False,methods=['get'],permission_classes=[AllowAny])
 def suggest(self,request):
  q=request.query_params.get('q','').strip()
  if len(q)<2:return Response({'results':[]})
  city_query=q.split(',')[0].strip()
  qualifier=q.split(',',1)[1].strip().casefold() if ',' in q else ''
  saved=[{'provider_id':d.provider_id,'name':d.name,'country':d.country,'region':d.region,'latitude':d.latitude,'longitude':d.longitude} for d in Destination.objects.filter(name__istartswith=city_query)[:30] if not qualifier or qualifier in (d.region.casefold(),d.country.casefold())]
  try:
   prefix=normalize('NFKD',city_query).encode('ascii','ignore').decode('ascii').casefold()
   live=LocationService().search(q)
   matching=[item for item in live if not prefix or normalize('NFKD',item['name']).encode('ascii','ignore').decode('ascii').casefold().startswith(prefix)]
   live=matching
   seen={item['provider_id'] for item in live if item['provider_id']}
   identities={(item['name'].casefold(),item['country'].casefold(),item['region'].casefold()) for item in live}
   return Response({'results':(live+[item for item in saved if item['provider_id'] not in seen and (item['name'].casefold(),item['country'].casefold(),item['region'].casefold()) not in identities and (item['region'] or not any(other['name'].casefold()==item['name'].casefold() and other['country'].casefold()==item['country'].casefold() for other in live))])[:20]})
  except Exception:return Response({'results':saved,'warning':'Showing saved cities while live suggestions are unavailable.'})
 @action(detail=False,methods=['get'],permission_classes=[AllowAny])
 def search(self,request):
  q=request.query_params.get('q','').strip()
  if not q:return Response({'detail':'Enter a destination.'},status=400)
  parts=[part.strip() for part in q.split(',') if part.strip()];city=parts[0];selected_id=request.query_params.get('city_id','')
  browsed=None
  if selected_id.startswith('csc:'):
   country=request.query_params.get('country','').strip()[:120];region=request.query_params.get('region','').strip()[:160]
   try:lat=float(request.query_params.get('latitude',''));lon=float(request.query_params.get('longitude',''))
   except (TypeError,ValueError):return Response({'detail':'Choose a city from the location list.'},status=400)
   if not country or not region or not city or len(city)>160 or not -90<=lat<=90 or not -180<=lon<=180 or len(selected_id)>200 or len(selected_id.split(':'))!=4:return Response({'detail':'Choose a valid country, state and city.'},status=400)
   try:
    refined=next((item for item in LocationService().search(f'{city}, {region}') if item['name'].casefold()==city.casefold() and item['country'].casefold()==country.casefold() and item['region'].casefold()==region.casefold()),None)
    if refined:lat=float(refined['latitude']);lon=float(refined['longitude'])
   except Exception:pass
   browsed=(country,region,lat,lon)
  matches=Destination.objects.prefetch_related('places').filter(name__iexact=city)
  qualified=matches.filter(Q(country__iexact=parts[-1])|Q(region__iexact=parts[-1])) if len(parts)>1 else matches
  cached=Destination.objects.prefetch_related('places').filter(provider_id=selected_id).first() if selected_id else qualified.first() if qualified.count()==1 else None
  if browsed:
   country,region,lat,lon=browsed
   candidates=[item for item in matches.filter(country__iexact=country) if item.region.casefold() in ('',region.casefold()) and distance_coords(lat,lon,item.latitude,item.longitude)<5]
   if candidates:cached=max(candidates,key=lambda item:(bool(item.places_synced_at),item.places.count()))
  if cached and selected_id and not cached.region:
   try:
    location=next((item for item in LocationService().search(city) if item['provider_id']==selected_id),None)
    if location and location['region']:
     cached.region=location['region'];cached.save(update_fields=['region'])
   except Exception:pass
  if cached and cached.places_synced_at and timezone.now()-cached.places_synced_at<__import__('datetime').timedelta(hours=24):
   data=DestinationSerializer(cached).data
   if browsed:data['region']=browsed[1]
   return Response(data)
  try:
   if cached:dest=cached
   elif browsed:
    country,region,lat,lon=browsed
    dest,_=Destination.objects.update_or_create(name=city,country=country,region=region,defaults={'provider_id':selected_id,'latitude':lat,'longitude':lon})
   else:
    locations=LocationService().search(q)
    if not locations:return Response({'detail':'No destination found.','results':[]},status=404)
    hit=next((item for item in locations if item['provider_id']==selected_id),None) if selected_id else locations[0]
    if hit is None:return Response({'detail':'That city option is no longer available. Choose a city from the suggestions.'},status=404)
    legacy=Destination.objects.filter(name=hit['name'],country=hit['country'],region='',provider_id='').first()
    if legacy:
     legacy.region=hit['region'];legacy.provider_id=hit['provider_id'];legacy.latitude=float(hit['latitude']);legacy.longitude=float(hit['longitude']);legacy.save(update_fields=['region','provider_id','latitude','longitude']);dest=legacy
    else:
     dest,_=Destination.objects.update_or_create(name=hit['name'],country=hit['country'],region=hit['region'],defaults={'provider_id':hit['provider_id'],'latitude':float(hit['latitude']),'longitude':float(hit['longitude'])})
   provider_warning=None
   try:
    live=PlacesService().nearby(dest.latitude,dest.longitude)
    for item in live:
     provider_id=item.pop('provider_id')
     current=Place.objects.filter(destination=dest,provider_id=provider_id).first()
     if current and current.image_url and not item['image_url']:
      item['image_url']=current.image_url;item['image_kind']=current.image_kind
     Place.objects.update_or_create(destination=dest,provider_id=provider_id,defaults=item)
    dest.places_synced_at=timezone.now();dest.save(update_fields=['places_synced_at'])
   except Exception:provider_warning='Attractions provider is temporarily unavailable; showing cached results.'
   data=DestinationSerializer(Destination.objects.prefetch_related('places').get(pk=dest.pk)).data
   if browsed:data['region']=browsed[1]
   if provider_warning:data['warning']=provider_warning
   return Response(data)
  except Exception:
   if cached:
    data=DestinationSerializer(cached).data
    if browsed:data['region']=browsed[1]
    data['warning']='Live search is temporarily unavailable; showing saved destination data.'
    return Response(data)
   return Response({'detail':'Live search is temporarily unavailable. Please try again.','retryable':True},status=503)
 @action(detail=True,methods=['post'],permission_classes=[IsTourist])
 def photos(self,request,pk=None):
  dest=self.get_object();ids=request.data.get('place_ids',[])
  if not isinstance(ids,list) or len(ids)>24:return Response({'detail':'Choose up to 24 places.'},status=400)
  try:ids=[int(value) for value in ids]
  except (TypeError,ValueError):return Response({'detail':'Invalid place IDs.'},status=400)
  places=list(dest.places.filter(pk__in=ids))
  names=([dest.name] if not dest.image_url else [])+[place.name for place in places if not place.image_url]
  photos=ImageService.find_photos(names,city=dest.name)
  if not dest.image_url and photos.get(dest.name.casefold()):
   dest.image_url=photos[dest.name.casefold()];dest.save(update_fields=['image_url'])
  unresolved=[]
  for place in places:
   url=photos.get(place.name.casefold())
   if url and not place.image_url:place.image_url=url;place.image_kind='place';place.save(update_fields=['image_url','image_kind'])
   elif not place.image_url:unresolved.append(place)
  nearby=ImageService.find_nearby_photos(unresolved) if unresolved else {}
  for place in unresolved:
   if nearby.get(place.id):place.image_url=nearby[place.id];place.image_kind='nearby';place.save(update_fields=['image_url','image_kind'])
  return Response({'destination_image_url':ImageService.normalize_url(dest.image_url),'photos':{str(place.id):{'url':ImageService.normalize_url(place.image_url),'kind':place.image_kind or 'place'} for place in places if place.image_url}})
class PlaceViewSet(viewsets.ReadOnlyModelViewSet):
 queryset=Place.objects.select_related('destination');serializer_class=PlaceSerializer
 pagination_class=None
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
  stops=list(day.stops.select_related('place'))
  def candidate(first):
   remaining=[stop for stop in stops if stop.pk!=first.pk];route=[first]
   while remaining:
    nxt=min(remaining,key=lambda item:(distance_km(route[-1].place,item.place),item.pk));remaining.remove(nxt);route.append(nxt)
   return route
  routes=[candidate(first) for first in stops]
  route=min(routes,key=lambda items:(sum(distance_km(a.place,b.place) for a,b in zip(items,items[1:])),[item.pk for item in items])) if routes else []
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
  trip=data.get('trip')
  if trip and trip.tourist_id!=request.user.id:return Response({'detail':'This trip is not yours.'},status=403)
  if data['service'].guide_id!=data['guide'].id:return Response({'detail':'Service and guide do not match.'},status=400)
  destination=data['service'].coverage.destination
  if not destination:return Response({'detail':'This service needs a city coverage area.'},status=400)
  if trip and destination.id!=trip.destination_id:return Response({'detail':'This service does not cover your trip destination.'},status=400)
  if data['start']<=timezone.now():return Response({'detail':'Choose a future tour time.'},status=400)
  tour_day=timezone.localtime(data['start'],ZoneInfo(data['guide'].timezone)).date()
  if trip and not trip.start_date<=tour_day<=trip.end_date:return Response({'detail':'Tour date must fall within your trip.'},status=400)
  if data['people']>data['service'].max_group_size:return Response({'detail':'Group size exceeds this service.'},status=400)
  if data['end']<=data['start'] or not AvailabilityService.contains(data['guide'],data['start'],data['end']):return Response({'detail':'Guide is unavailable during that time.'},status=409)
  if not data['service'].active:return Response({'detail':'This service is inactive.'},status=400)
  with transaction.atomic():
   if not trip:trip=Trip.objects.create(tourist=request.user,destination=destination,title=f'{destination.name} · {data["service"].title}',start_date=tour_day,end_date=tour_day)
   item=serializer.save(tourist=request.user,trip=trip)
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
 def get_queryset(self):return Booking.objects.filter(Q(tourist=self.request.user)|Q(guide__user=self.request.user)).select_related('guide__user','tourist','service').order_by('-start','-pk')
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
