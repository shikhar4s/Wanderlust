from math import radians,sin,cos,asin,sqrt
import os
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
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
  key='geocode:v2:'+sha256(query.casefold().strip().encode()).hexdigest()
  saved=cache.get(key)
  if saved is not None:return saved
  with httpx.Client(timeout=8,trust_env=False) as client:
   response=client.get(self.endpoint,params={'name':query,'count':30,'language':'en','format':'json'});response.raise_for_status()
   data=[];seen=set()
   for item in response.json().get('results',[]):
    if not item.get('feature_code','').startswith('PPL'):continue
    identity=(item['name'].casefold(),item.get('admin1','').casefold(),item.get('country','').casefold())
    if identity in seen:continue
    seen.add(identity)
    data.append({'provider_id':f"openmeteo:{item['id']}",'name':item['name'],'country':item.get('country',''),'region':item.get('admin1',''),'latitude':item['latitude'],'longitude':item['longitude']})
   cache.set(key,data,timeout=24*3600)
   return data

class PlacesService:
 endpoints=(os.getenv('OVERPASS_API_URL','https://overpass.kumi.systems/api/interpreter'),'https://overpass-api.de/api/interpreter')
 def nearby(self,lat,lng,radius_km=25):
  area=f'(around:{int(radius_km*1000)},{lat},{lng})'
  query=('[out:json][timeout:30];('
   f'nwr["tourism"~"^(attraction|museum|viewpoint|gallery|artwork|zoo|theme_park|picnic_site)$"]{area};'
   f'nwr["historic"~"^(castle|fort|monument|ruins|archaeological_site|memorial|city_gate)$"]{area};'
   f'nwr["natural"~"^(peak|waterfall|cave_entrance|beach|spring)$"]{area};'
   f'nwr["leisure"~"^(park|nature_reserve|garden)$"]{area};'
   f'nwr["route"~"^(hiking|foot)$"]{area};'
   f'nwr["highway"="path"]["sac_scale"]{area};'
   ');out center tags 700;')
  raw=None;last_error=None
  with httpx.Client(timeout=38,trust_env=False,headers={'User-Agent':'WanderlustTravelPlanner/1.0'}) as client:
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
   natural=tags.get('natural','');tourism=tags.get('tourism','');historic=tags.get('historic','');leisure=tags.get('leisure','')
   category=('trek' if tags.get('route') in ('hiking','foot') or tags.get('sac_scale') or natural=='peak' else
             'museum' if tourism=='museum' else 'viewpoint' if tourism=='viewpoint' else
             'nature' if natural or leisure in ('park','nature_reserve','garden') else
             'heritage' if historic else 'gallery' if tourism=='gallery' else 'attraction')
   photo=ImageService.from_tags(tags)
   results.append({'provider_id':f"osm:{item['type']}:{item['id']}",'name':name,'description':tags.get('description') or tags.get('description:en') or historic or natural or tourism.replace('_',' ').title() or leisure.replace('_',' ').title() or 'Place to explore','category':category,'latitude':point['lat'],'longitude':point['lon'],'rating':None,'image_url':photo,'image_kind':'place' if photo else ''})
  results.sort(key=lambda item:(distance_coords(lat,lng,item['latitude'],item['longitude']),item['name'].casefold()))
  return results

def distance_coords(lat1,lon1,lat2,lon2):
 dlat=radians(lat2-lat1);dlon=radians(lon2-lon1)
 return 2*6371*asin(sqrt(sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2))

class ImageService:
 @staticmethod
 def normalize_url(url):
  if not url:return ''
  return url.replace('https://thumb.wikimedia.org/', 'https://upload.wikimedia.org/', 1) if url.startswith('https://thumb.wikimedia.org/') else url

 @staticmethod
 def from_tags(tags):
  image=tags.get('image') or tags.get('wikimedia_commons') or ''
  if image.startswith('https://') or image.startswith('http://'):return ImageService.normalize_url(image)
  # FilePath redirects to a thumbnail host that may reject hotlinks; enrich it through the API instead.
  if image.startswith('File:'):return ''
  return ''

 @staticmethod
 def find_photos(names,city=''):
  """Find place-specific Wikimedia thumbnails, leaving unverified matches empty."""
  titles=list(dict.fromkeys(name.strip() for name in names if name.strip()))[:50]
  if not titles:return {}
  key='photos:'+sha256((city+'|'+ '|'.join(titles)).encode()).hexdigest()
  saved=cache.get(key)
  if saved is not None:return {name:ImageService.normalize_url(url) for name,url in saved.items()}
  try:
   with httpx.Client(timeout=10,trust_env=False,headers={'User-Agent':'WanderlustTravelPlanner/1.0 (https://github.com/shikhar4s/Wanderlust)'}) as client:
    response=client.get('https://en.wikipedia.org/w/api.php',params={'action':'query','format':'json','prop':'pageimages','titles':'|'.join(titles),'pithumbsize':900,'pilicense':'free','redirects':1})
    response.raise_for_status()
    pages=response.json().get('query',{}).get('pages',{}).values()
    result={page['title'].casefold():ImageService.normalize_url(page['thumbnail']['source']) for page in pages if 'thumbnail' in page}
    missing=[name for name in titles if name.casefold() not in result]
    def commons_photo(name):
     try:
      response=client.get('https://commons.wikimedia.org/w/api.php',params={'action':'query','format':'json','generator':'search','gsrsearch':f'{name} {city} filetype:bitmap','gsrnamespace':6,'gsrlimit':5,'prop':'imageinfo','iiprop':'url','iiurlwidth':900})
      response.raise_for_status()
      pages=sorted(response.json().get('query',{}).get('pages',{}).values(),key=lambda page:page.get('index',99))
      words=[word.casefold() for word in name.split() if len(word)>2]
      for page in pages:
       title=page.get('title','').casefold()
       if words and sum(word in title for word in words)<max(1,len(words)-1):continue
       info=page.get('imageinfo',[{}])[0]
       url=info.get('thumburl') or info.get('url')
       if url:return name.casefold(),ImageService.normalize_url(url)
     except (httpx.HTTPError,ValueError,KeyError,IndexError):pass
     return name.casefold(),''
    if missing:
     with ThreadPoolExecutor(max_workers=5) as pool:
      result.update({name:url for name,url in pool.map(commons_photo,missing) if url})
    cache.set(key,result,timeout=24*3600)
    return result
  except (httpx.HTTPError,ValueError,KeyError):return {}

 @staticmethod
 def find_nearby_photos(places):
  """Find geotagged Commons files close to mapped places, never claiming an exact match."""
  def lookup(place):
   key=f'nearby-photo:{round(place.latitude,4)}:{round(place.longitude,4)}'
   cached=cache.get(key)
   if cached is not None:return place.id,cached
   try:
    with httpx.Client(timeout=8,trust_env=False,headers={'User-Agent':'WanderlustTravelPlanner/1.0 (https://github.com/shikhar4s/Wanderlust)'}) as client:
     response=client.get('https://commons.wikimedia.org/w/api.php',params={'action':'query','format':'json','generator':'geosearch','ggscoord':f'{place.latitude}|{place.longitude}','ggsradius':600,'ggslimit':12,'ggsnamespace':6,'prop':'imageinfo','iiprop':'url|mime','iiurlwidth':900})
     response.raise_for_status()
     pages=sorted(response.json().get('query',{}).get('pages',{}).values(),key=lambda page:page.get('index',99))
     words=[word.casefold() for word in place.name.split() if len(word)>3]
     pages.sort(key=lambda page:(-sum(word in page.get('title','').casefold() for word in words),page.get('index',99)))
     for page in pages:
      info=page.get('imageinfo',[{}])[0]
      url=info.get('thumburl') or info.get('url')
      if url and info.get('mime','').startswith('image/'):
       result=ImageService.normalize_url(url);cache.set(key,result,timeout=24*3600);return place.id,result
   except (httpx.HTTPError,ValueError,KeyError,IndexError):pass
   cache.set(key,'',timeout=6*3600)
   return place.id,''
  with ThreadPoolExecutor(max_workers=8) as pool:return {place_id:url for place_id,url in pool.map(lookup,places) if url}

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
  key=os.getenv('GEMINI_API_KEY','').strip();model=os.getenv('GEMINI_MODEL','gemini-3.6-flash').strip()
  if not key:raise self.Unavailable('The AI assistant needs a Gemini API key. Add GEMINI_API_KEY to backend/.env and restart the server.')
  url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
  try:
   with httpx.Client(timeout=30,trust_env=False) as client:
    response=client.post(url,headers={'x-goog-api-key':key,'Content-Type':'application/json'},json={'system_instruction':{'parts':[{'text':'You are Wanderlust, a practical travel assistant. Be concise, be honest about uncertainty, and never claim to have changed a saved trip. Current context: '+context}]},'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'maxOutputTokens':700}})
   response.raise_for_status()
   answer='\n'.join(part.get('text','') for part in response.json()['candidates'][0]['content']['parts'] if part.get('text')).strip()
   if not answer:raise self.Unavailable('The AI provider returned no text. Please try again.')
   return {'answer':answer,'mutated_trip':False}
  except httpx.HTTPStatusError as exc:
   if exc.response.status_code==429:raise self.Unavailable('The free AI quota is busy or exhausted. Please try again later.')
   if exc.response.status_code in (400,401,403):raise self.Unavailable('The Gemini key or model was rejected. Check backend/.env and restart the server.')
   raise self.Unavailable('The AI provider is temporarily unavailable. Your trip was not changed.')
  except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError):raise self.Unavailable('The AI provider is temporarily unavailable. Your trip was not changed.')
