from math import radians,sin,cos,asin,sqrt
import httpx
from django.conf import settings

def distance_km(a,b):
 lon1,lat1,lon2,lat2=map(radians,[a.longitude,a.latitude,b.longitude,b.latitude]);dlon=lon2-lon1;dlat=lat2-lat1
 return 2*6371*asin(sqrt(sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2))

class ItineraryService:
 @staticmethod
 def generate(places,days):
  """Deterministic proximity grouping plus nearest-neighbour ordering."""
  ordered=sorted(places,key=lambda p:(p.latitude,p.longitude,p.pk));groups=[[] for _ in range(days)]
  for i,p in enumerate(ordered): groups[min(i*days//max(len(ordered),1),days-1)].append(p)
  for group in groups:
   if not group: continue
   route=[group.pop(0)]
   while group:
    nxt=min(group,key=lambda p:distance_km(route[-1],p));group.remove(nxt);route.append(nxt)
   group.extend(route)
  return groups

class LocationService:
 endpoint='https://nominatim.openstreetmap.org/search'
 def search(self,query):
  with httpx.Client(timeout=8,headers={'User-Agent':'Wanderlust/1.0'}) as client:
   r=client.get(self.endpoint,params={'q':query,'format':'jsonv2','limit':5});r.raise_for_status();return r.json()

class PlacesService:
 endpoints=('https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter')
 def nearby(self,lat,lng,radius_km=15):
  query=f'[out:json][timeout:15];(nwr["tourism"~"attraction|museum|viewpoint|gallery"](around:{int(radius_km*1000)},{lat},{lng}););out center tags 40;'
  raw=None;last_error=None
  with httpx.Client(timeout=22,headers={'User-Agent':'Wanderlust/1.0'}) as client:
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
   results.append({'provider_id':f"osm:{item['type']}:{item['id']}",'name':name,'description':tags.get('description') or tags.get('historic') or tags.get('tourism','Attraction').replace('_',' ').title(),'category':tags.get('tourism') or tags.get('historic') or 'attraction','latitude':point['lat'],'longitude':point['lon'],'rating':None,'image_url':tags.get('image','')})
  return results

class RoutingService:
 """OSRM-compatible route provider boundary with a straight-line fallback."""
 def route(self,places): return {'distance_km':sum(distance_km(a,b) for a,b in zip(places,places[1:])),'geometry':[[p.latitude,p.longitude] for p in places],'estimated':True}

class AIService:
 def advise(self,context,prompt):
  return {'answer':'AI provider is not configured. Your itinerary remains available; add an LLM key to enable contextual advice.','mutated_trip':False}
