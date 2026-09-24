from math import radians,sin,cos,asin,sqrt
import os
from hashlib import sha256
from urllib.parse import quote
import httpx
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone
from .models import AvailabilityRule, AvailabilityException, Booking

def distance_km(a,b):
 lon1,lat1,lon2,lat2=map(radians,[a.longitude,a.latitude,b.longitude,b.latitude]);dlon=lon2-lon1;dlat=lat2-lat1
 return 2*6371*asin(sqrt(sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2))

class ItineraryService:
 @staticmethod
 def generate(places,days):
  """Balanced geographic clusters followed by deterministic nearest-neighbour routes."""
  if days<1:return []
  remaining=sorted(places,key=lambda p:(p.latitude,p.longitude,p.pk))
  if not remaining:return [[] for _ in range(days)]
  count=min(days,len(remaining));seeds=[remaining.pop(0)]
  while len(seeds)<count:
   farthest=max(remaining,key=lambda p:(min(distance_km(p,s) for s in seeds),-p.pk))
   seeds.append(farthest);remaining.remove(farthest)
  groups=[[seed] for seed in seeds];capacity=(len(places)+count-1)//count
  for place in sorted(remaining,key=lambda p:(-min(distance_km(p,s) for s in seeds),p.pk)):
   choices=[i for i,g in enumerate(groups) if len(g)<capacity]
   index=min(choices,key=lambda i:(min(distance_km(place,member) for member in groups[i]),len(groups[i]),i))
   groups[index].append(place)
  groups.sort(key=lambda g:(sum(p.latitude for p in g)/len(g),sum(p.longitude for p in g)/len(g)))
  for index,group in enumerate(groups):
   pool=sorted(group,key=lambda p:(p.latitude,p.longitude,p.pk));route=[pool.pop(0)]
   while pool:
    nearest=min(pool,key=lambda p:(distance_km(route[-1],p),p.pk));pool.remove(nearest);route.append(nearest)
   groups[index]=route
  return groups+[[] for _ in range(days-count)]

class LocationService:
 endpoint=os.getenv('GEOCODING_API_URL','https://geocoding-api.open-meteo.com/v1/search')
 def search(self,query):
  key='geocode:'+sha256(query.casefold().strip().encode()).hexdigest()
  saved=cache.get(key)
  if saved is not None:return saved
  with httpx.Client(timeout=8,trust_env=False) as client:
   response=client.get(self.endpoint,params={'name':query,'count':8,'language':'en','format':'json'});response.raise_for_status()
   data=[{'provider_id':f"openmeteo:{item['id']}",'name':item['name'],'country':item.get('country',''),'region':item.get('admin1',''),'latitude':item['latitude'],'longitude':item['longitude']} for item in response.json().get('results',[]) if item.get('feature_code','').startswith('PPL')]
   cache.set(key,data,timeout=24*3600)
   return data

class PlacesService:
 endpoints=(os.getenv('OVERPASS_API_URL','https://overpass.kumi.systems/api/interpreter'),'https://overpass-api.de/api/interpreter')
 def nearby(self,lat,lng,radius_km=15):
  query=f'[out:json][timeout:15];(nwr["tourism"~"attraction|museum|viewpoint|gallery"](around:{int(radius_km*1000)},{lat},{lng}););out center tags 40;'
  raw=None;last_error=None
  with httpx.Client(timeout=22,trust_env=False,headers={'User-Agent':'WanderlustTravelPlanner/1.0'}) as client:
   for endpoint in self.endpoints:
    try:
     response=client.post(endpoint,data={'data':query});response.raise_for_status();raw=response.json().get('elements',[]);break
    except Exception as exc:last_error=exc
  if raw is None:raise last_error
  results=[]
  for item in raw:
   tags=item.get('tags',{});name=tags.get('name') or tags.get('name:en')
   point=item.get('center',item)
   if not name or 'lat' not in point:continue
   results.append({'provider_id':f"osm:{item['type']}:{item['id']}",'name':name,'description':tags.get('description') or tags.get('historic') or tags.get('tourism','Attraction').replace('_',' ').title(),'category':tags.get('tourism') or tags.get('historic') or 'attraction','latitude':point['lat'],'longitude':point['lon'],'rating':None,'image_url':ImageService.from_tags(tags)})
  photos=ImageService.find_photos([item['name'] for item in results if not item['image_url']])
  for item in results:
   if not item['image_url']:item['image_url']=photos.get(item['name'].casefold(),'')
  return results

class ImageService:
 @staticmethod
 def from_tags(tags):
  image=tags.get('image') or tags.get('wikimedia_commons') or ''
  if image.startswith('https://') or image.startswith('http://'):return image
  if image.startswith('File:'):return 'https://commons.wikimedia.org/wiki/Special:FilePath/'+quote(image[5:])+'?width=900'
  return ''

 @staticmethod
 def find_photos(names):
  """Fetch free page thumbnails in one request; omit unmatched places honestly."""
  titles=list(dict.fromkeys(name.strip() for name in names if name.strip()))[:50]
  if not titles:return {}
  key='photos:'+sha256('|'.join(titles).encode()).hexdigest()
  saved=cache.get(key)
  if saved is not None:return saved
  try:
   with httpx.Client(timeout=10,trust_env=False,headers={'User-Agent':'WanderlustTravelPlanner/1.0 (https://github.com/shikhar4s/Wanderlust)'}) as client:
    response=client.get('https://en.wikipedia.org/w/api.php',params={'action':'query','format':'json','prop':'pageimages','titles':'|'.join(titles),'pithumbsize':900,'pilicense':'free','redirects':1})
    response.raise_for_status()
    pages=response.json().get('query',{}).get('pages',{}).values()
    result={page['title'].casefold():page['thumbnail']['source'] for page in pages if 'thumbnail' in page}
    cache.set(key,result,timeout=24*3600)
    return result
  except (httpx.HTTPError,ValueError,KeyError):return {}

class RoutingService:
 """OSRM-compatible route provider boundary with a straight-line fallback."""
 def route(self,places): return {'distance_km':sum(distance_km(a,b) for a,b in zip(places,places[1:])),'geometry':[[p.latitude,p.longitude] for p in places],'estimated':True}

class AvailabilityService:
 @staticmethod
 def slots(guide, day):
  tz=ZoneInfo(guide.timezone)
  intervals=[(timezone.make_aware(datetime.combine(day,r.start_time),tz),timezone.make_aware(datetime.combine(day,r.end_time),tz)) for r in AvailabilityRule.objects.filter(guide=guide,weekday=day.weekday(),active=True)]
  exceptions=list(AvailabilityException.objects.filter(guide=guide,start__lt=timezone.make_aware(datetime.combine(day+timedelta(days=1),datetime.min.time()),tz),end__gt=timezone.make_aware(datetime.combine(day,datetime.min.time()),tz)))
  intervals.extend((item.start,item.end) for item in exceptions if item.available)
  intervals=AvailabilityService._merge(intervals)
  for exception in exceptions:
   if not exception.available:intervals=AvailabilityService._subtract(intervals,exception.start,exception.end)
  for booking in Booking.objects.filter(guide=guide,status='CONFIRMED',start__lt=timezone.make_aware(datetime.combine(day+timedelta(days=1),datetime.min.time()),tz),end__gt=timezone.make_aware(datetime.combine(day,datetime.min.time()),tz)):
   intervals=AvailabilityService._subtract(intervals,booking.start,booking.end)
  return [(max(start,timezone.make_aware(datetime.combine(day,datetime.min.time()),tz)),min(end,timezone.make_aware(datetime.combine(day+timedelta(days=1),datetime.min.time()),tz))) for start,end in AvailabilityService._merge(intervals) if end>start and start.date()<=day]

 @staticmethod
 def _merge(intervals):
  merged=[]
  for start,end in sorted(intervals):
   if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],end))
   else:merged.append((start,end))
  return merged

 @staticmethod
 def _subtract(intervals,start,end):
  result=[]
  for left,right in intervals:
   if right<=start or left>=end:result.append((left,right))
   else:
    if left<start:result.append((left,start))
    if end<right:result.append((end,right))
  return result

 @staticmethod
 def contains(guide,start,end):
  tz=ZoneInfo(guide.timezone)
  local_day=timezone.localtime(start,tz).date()
  return guide.accepting_bookings and local_day==timezone.localtime(end,tz).date() and any(left<=start and end<=right for left,right in AvailabilityService.slots(guide,local_day))

class AIService:
 class Unavailable(Exception):pass
 def advise(self,context,prompt):
  key=os.getenv('AI_API_KEY');url=os.getenv('AI_API_URL');model=os.getenv('AI_MODEL')
  if not all((key,url,model)):raise self.Unavailable('The AI provider is not configured on the server yet.')
  try:
   response=httpx.post(url,headers={'Authorization':f'Bearer {key}'},json={'model':model,'messages':[{'role':'system','content':'You are Wanderlust travel guidance. Give practical, concise suggestions. Never claim to change a trip. Current context: '+context},{'role':'user','content':prompt}]},timeout=25)
   response.raise_for_status()
   answer=response.json()['choices'][0]['message']['content']
   return {'answer':answer,'mutated_trip':False}
  except (httpx.HTTPError,KeyError,IndexError,TypeError):raise self.Unavailable('The AI provider is temporarily unavailable. Your trip was not changed.')
