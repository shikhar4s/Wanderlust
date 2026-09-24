from datetime import timedelta
import httpx
from django.core.exceptions import ValidationError
from django.test import TestCase,TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import *
from .services import ItineraryService,AvailabilityService,PlacesService,AIService,ImageService
from rest_framework.test import APIClient
from unittest.mock import patch
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken
class CoreRulesTests(TestCase):
 def setUp(self):
  self.tourist=User.objects.create_user('tourist',email='tourist@example.com',role='TOURIST');self.guide_user=User.objects.create_user('guide',email='guide@example.com',role='GUIDE');self.guide=GuideProfile.objects.create(user=self.guide_user);self.dest=Destination.objects.create(name='Udaipur',country='India',latitude=24.58,longitude=73.68);self.cover=GuideCoverage.objects.create(guide=self.guide,level='CITY',destination=self.dest,label='Udaipur');self.service=GuideService.objects.create(guide=self.guide,title='Walk',description='Heritage walk',coverage=self.cover,duration_minutes=120,price=2000,pricing_type='NEGOTIABLE');self.trip=Trip.objects.create(tourist=self.tourist,destination=self.dest,title='Trip',start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=1))
 def request(self,start=None):
  start=start or (timezone.now()+timedelta(days=2)).replace(hour=11,minute=0,second=0,microsecond=0)
  AvailabilityRule.objects.get_or_create(guide=self.guide,weekday=start.weekday(),start_time='09:00',end_time='19:00')
  return GuideRequest.objects.create(tourist=self.tourist,guide=self.guide,trip=self.trip,service=self.service,start=start,end=start+timedelta(hours=2),people=2)
 def test_overlap_rejected_but_adjacent_allowed(self):
  req=self.request();req.transition('ACCEPTED');Booking.confirm(req,1800)
  overlap=self.request(req.start+timedelta(hours=1));overlap.transition('ACCEPTED')
  with self.assertRaises(ValidationError):Booking.confirm(overlap,1900)
  adjacent=self.request(req.end);adjacent.transition('ACCEPTED');self.assertIsNotNone(Booking.confirm(adjacent,2000))
 def test_state_transitions_are_guarded(self):
  req=self.request();req.transition('NEGOTIATING')
  with self.assertRaises(ValidationError):req.transition('COMPLETED')
 def test_itinerary_is_deterministic_and_complete(self):
  pts=[Place.objects.create(destination=self.dest,name=str(i),latitude=24.5+i/100,longitude=73.6+i/100) for i in range(6)]
  result=ItineraryService.generate(pts.copy(),3);self.assertEqual(sum(map(len,result)),6);self.assertEqual([[p.id for p in x] for x in result],[[p.id for p in x] for x in ItineraryService.generate(pts.copy(),3)])
 def test_available_exception_and_booked_interval_are_subtracted(self):
  day=timezone.localdate()+timedelta(days=3)
  make=lambda hour:timezone.make_aware(__import__('datetime').datetime.combine(day,__import__('datetime').time(hour)))
  AvailabilityRule.objects.create(guide=self.guide,weekday=day.weekday(),start_time='09:00',end_time='19:00')
  AvailabilityException.objects.create(guide=self.guide,start=make(12),end=make(13),available=False)
  AvailabilityException.objects.create(guide=self.guide,start=make(11),end=make(14),available=True)
  slots=AvailabilityService.slots(self.guide,day)
  self.assertEqual([(x.hour,y.hour) for x,y in slots],[(9,12),(13,19)])
  self.assertFalse(AvailabilityService.contains(self.guide,make(11),make(14)))
 def test_weekly_hours_use_guide_timezone(self):
  from zoneinfo import ZoneInfo
  self.guide.timezone='Asia/Kolkata';self.guide.save(update_fields=['timezone'])
  local=(timezone.now()+timedelta(days=3)).astimezone(ZoneInfo('Asia/Kolkata')).replace(hour=10,minute=0,second=0,microsecond=0)
  AvailabilityRule.objects.create(guide=self.guide,weekday=local.weekday(),start_time='09:00',end_time='19:00')
  self.assertTrue(AvailabilityService.contains(self.guide,local.astimezone(__import__('datetime').timezone.utc),(local+timedelta(hours=2)).astimezone(__import__('datetime').timezone.utc)))

class AuthenticationFlowTests(TestCase):
 def setUp(self):self.client=APIClient()
 def test_tourist_signup_creates_profile_and_tokens(self):
  response=self.client.post('/api/auth/signup/',{'name':'Mira Sen','email':'mira@example.com','password':'StrongPass123','confirm_password':'StrongPass123','terms':True,'role':'TOURIST'},format='json')
  self.assertEqual(response.status_code,201);self.assertIn('access',response.data);user=User.objects.get(email='mira@example.com');self.assertEqual(user.role,'TOURIST');self.assertTrue(hasattr(user,'tourist_profile'))
 def test_guide_cannot_create_tourist_trip(self):
  guide=User.objects.create_user('guide@example.com',email='guide@example.com',password='StrongPass123',role='GUIDE');GuideProfile.objects.create(user=guide);self.client.force_authenticate(guide)
  response=self.client.post('/api/trips/',{},format='json');self.assertEqual(response.status_code,403)
 def test_duplicate_email_rejected(self):
  payload={'name':'Mira Sen','email':'mira@example.com','password':'StrongPass123','confirm_password':'StrongPass123','terms':True,'role':'TOURIST'};self.assertEqual(self.client.post('/api/auth/signup/',payload,format='json').status_code,201);self.assertEqual(self.client.post('/api/auth/signup/',payload,format='json').status_code,400)
 def test_cached_destination_survives_provider_outage(self):
  destination=Destination.objects.create(name='Udaipur',country='India',latitude=24.58,longitude=73.68,places_synced_at=timezone.now())
  Place.objects.create(destination=destination,name='City Palace',latitude=24.57,longitude=73.68)
  with patch('core.views.LocationService.search',side_effect=RuntimeError('provider unavailable')),patch('core.views.ImageService.find_photos',return_value={}):
   response=self.client.get('/api/destinations/search/?q=Udaipur%2C%20India')
  self.assertEqual(response.status_code,200)
  self.assertEqual(response.data['places'][0]['name'],'City Palace')
 def test_city_suggestions_and_background_image_enrichment(self):
  with patch('core.views.LocationService.search',return_value=[{'provider_id':'openmeteo:1','name':'Jaipur','country':'India','region':'Rajasthan','latitude':26.9,'longitude':75.8}]):
   suggestions=self.client.get('/api/destinations/suggest/?q=Jai')
   self.assertEqual(suggestions.status_code,200)
   self.assertEqual(suggestions.data['results'][0]['name'],'Jaipur')
   with patch('core.views.PlacesService.nearby',return_value=[{'provider_id':'osm:way:1','name':'Hawa Mahal','description':'Palace','category':'attraction','latitude':26.9,'longitude':75.8,'rating':None,'image_url':''}]),patch('core.views.ImageService.find_photos',side_effect=AssertionError('Photo lookup should not delay search')):
    result=self.client.get('/api/destinations/search/?q=Jaipur&city_id=openmeteo%3A1')
  self.assertEqual(result.status_code,200,result.data)
  self.assertEqual(result.data['image_url'],'')
  tourist=User.objects.create_user('traveler',email='traveler@example.com',role='TOURIST');self.client.force_authenticate(tourist)
  with patch('core.views.ImageService.find_photos',return_value={'jaipur':'https://example.com/city.jpg','hawa mahal':'https://example.com/place.jpg'}):
   photos=self.client.post(f"/api/destinations/{result.data['id']}/photos/",{'place_ids':[result.data['places'][0]['id']]},format='json')
  self.assertEqual(photos.status_code,200,photos.data)
  self.assertEqual(photos.data['destination_image_url'],'https://example.com/city.jpg')
  self.assertEqual(photos.data['photos'][str(result.data['places'][0]['id'])],{'url':'https://example.com/place.jpg','kind':'place'})
 def test_search_returns_only_selected_city_places(self):
  jaipur=Destination.objects.create(name='Jaipur',country='India',latitude=26.9,longitude=75.8)
  Place.objects.create(destination=jaipur,name='Hawa Mahal',latitude=26.9,longitude=75.8)
  paris=Destination.objects.create(name='Paris',country='France',provider_id='openmeteo:2988507',latitude=48.85,longitude=2.35,places_synced_at=timezone.now())
  Place.objects.create(destination=paris,name='Eiffel Tower',latitude=48.85,longitude=2.29)
  with patch('core.views.ImageService.find_photos',return_value={}):
   result=self.client.get('/api/destinations/search/?q=Paris&city_id=openmeteo%3A2988507')
  self.assertEqual(result.status_code,200)
  self.assertEqual(result.data['name'],'Paris')
  self.assertEqual([place['name'] for place in result.data['places']],['Eiffel Tower'])
 def test_same_named_cities_keep_separate_places(self):
  cities=[{'provider_id':'openmeteo:101','name':'Manali','country':'India','region':'Tamil Nadu','latitude':13.17,'longitude':80.26},{'provider_id':'openmeteo:202','name':'Manali','country':'India','region':'Himachal Pradesh','latitude':32.24,'longitude':77.19}]
  def nearby(lat,lng):return [{'provider_id':f'osm:node:{int(lat)}','name':'Hill Trail' if lat>20 else 'City Park','description':'Place','category':'trek' if lat>20 else 'nature','latitude':lat,'longitude':lng,'rating':None,'image_url':''}]
  with patch('core.views.LocationService.search',return_value=cities),patch('core.views.PlacesService.nearby',side_effect=nearby):
   south=self.client.get('/api/destinations/search/?q=Manali&city_id=openmeteo%3A101')
   north=self.client.get('/api/destinations/search/?q=Manali&city_id=openmeteo%3A202')
  self.assertEqual(south.status_code,200,south.data)
  self.assertEqual(north.status_code,200,north.data)
  self.assertNotEqual(south.data['id'],north.data['id'])
  self.assertEqual(north.data['region'],'Himachal Pradesh')
  self.assertEqual([place['name'] for place in north.data['places']],['Hill Trail'])
  self.assertEqual([place['name'] for place in south.data['places']],['City Park'])
 def test_wikimedia_thumbnails_use_working_upload_host(self):
  url='https://thumb.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/960px-test.jpg'
  self.assertEqual(ImageService.normalize_url(url),'https://upload.wikimedia.org/wikipedia/commons/thumb/a/b/test.jpg/960px-test.jpg')
  self.assertEqual(ImageService.from_tags({'image':url}),ImageService.normalize_url(url))
 def test_geotagged_nearby_image_is_labeled_not_claimed_as_exact(self):
  destination=Destination.objects.create(name='Ajmer',country='India',region='Rajasthan',latitude=26.45,longitude=74.64)
  place=Place.objects.create(destination=destination,name='Small Viewpoint',latitude=26.45,longitude=74.64)
  tourist=User.objects.create_user('nearby',email='nearby@example.com',role='TOURIST');self.client.force_authenticate(tourist)
  with patch('core.views.ImageService.find_photos',return_value={}),patch('core.views.ImageService.find_nearby_photos',return_value={place.id:'https://upload.wikimedia.org/example.jpg'}):
   result=self.client.post(f'/api/destinations/{destination.id}/photos/',{'place_ids':[place.id]},format='json')
  self.assertEqual(result.status_code,200)
  self.assertEqual(result.data['photos'][str(place.id)]['kind'],'nearby')
  self.assertEqual(Place.objects.get(pk=place.id).image_kind,'nearby')
 def test_browsed_city_coordinates_create_correct_destination(self):
  with patch('core.views.PlacesService.nearby',return_value=[]),patch('core.views.LocationService.search',return_value=[]):
   result=self.client.get('/api/destinations/search/?q=Manali&city_id=csc%3AIN%3AHP%3A123&country=India&region=Himachal%20Pradesh&latitude=32.24&longitude=77.19')
  self.assertEqual(result.status_code,200,result.data)
  self.assertEqual((result.data['name'],result.data['region'],result.data['country']),('Manali','Himachal Pradesh','India'))
 def test_browsed_city_uses_more_precise_live_coordinates_when_available(self):
  live=[{'provider_id':'openmeteo:1','name':'Jaipur','country':'India','region':'Rajasthan','latitude':26.91962,'longitude':75.78781}]
  with patch('core.views.LocationService.search',return_value=live),patch('core.views.PlacesService.nearby',return_value=[]):
   result=self.client.get('/api/destinations/search/?q=Jaipur&city_id=csc%3AIN%3ARJ%3A132201&country=India&region=Rajasthan&latitude=27&longitude=76')
  self.assertEqual(result.status_code,200,result.data)
  self.assertAlmostEqual(result.data['latitude'],26.91962)
 def test_live_place_categories_include_treks_and_nature(self):
  elements=[{'type':'node','id':1,'lat':26.9,'lon':75.8,'tags':{'name':'Ridge Walk','route':'hiking'}},{'type':'node','id':2,'lat':26.91,'lon':75.81,'tags':{'name':'Waterfall','natural':'waterfall'}}]
  response=httpx.Response(200,json={'elements':elements},request=httpx.Request('POST','https://overpass.example/api'))
  with patch('core.services.httpx.Client') as client,patch('core.services.ImageService.find_photos',return_value={}):
   client.return_value.__enter__.return_value.post.return_value=response
   places=PlacesService().nearby(26.9,75.8)
   query=client.return_value.__enter__.return_value.post.call_args.kwargs['data']['data']
  self.assertEqual({place['category'] for place in places},{'trek','nature'})
  self.assertIn('700',query)
  self.assertIn('hiking',query)
 def test_tourist_profile_update_and_photo_upload(self):
  user=User.objects.create_user('mira',email='mira@example.com',role='TOURIST');TouristProfile.objects.create(user=user);self.client.force_authenticate(user)
  updated=self.client.patch('/api/auth/profile/',{'first_name':'Mira','home_city':'Pune','interests':['Food','Art']},format='json')
  self.assertEqual(updated.status_code,200,updated.data)
  self.assertEqual(updated.data['tourist']['home_city'],'Pune')
  def save_without_disk(field,name,content,save=True):
   field.name='profiles/test.png'
   field.instance.save(update_fields=['profile_photo'])
  with patch('django.db.models.fields.files.FieldFile.save',save_without_disk):
   photo=SimpleUploadedFile('avatar.png',b'\x89PNG\r\n\x1a\n'+b'0'*24,content_type='image/png')
   uploaded=self.client.post('/api/auth/photo/',{'photo':photo},format='multipart')
   self.assertEqual(uploaded.status_code,200,uploaded.data)
   self.assertIn('/media/profiles/',uploaded.data['photo_url'])

class ConnectedFlowTests(TestCase):
 def setUp(self):
  self.client=APIClient();self.tourist=User.objects.create_user('traveller@example.com',email='traveller@example.com',password='StrongPass123',role='TOURIST');TouristProfile.objects.create(user=self.tourist)
  self.guide_user=User.objects.create_user('local@example.com',email='local@example.com',password='StrongPass123',role='GUIDE');self.guide=GuideProfile.objects.create(user=self.guide_user)
  self.destination=Destination.objects.create(name='Gwalior',country='India',latitude=26.2,longitude=78.17)
  self.places=[Place.objects.create(destination=self.destination,name=f'Place {i}',latitude=26.2+i/100,longitude=78.17+i/100) for i in range(3)]
  self.start=(timezone.now()+timedelta(days=3)).replace(hour=11,minute=0,second=0,microsecond=0)
  self.trip=Trip.objects.create(tourist=self.tourist,destination=self.destination,title='Gwalior trip',start_date=self.start.date(),end_date=self.start.date()+timedelta(days=1))
 def auth(self,user):self.client.force_authenticate(user=user)
 def test_roles_and_unconfigured_ai_fail_explicitly(self):
  self.auth(self.tourist)
  self.assertEqual(self.client.get('/api/guide-account/mine/').status_code,403)
  self.assertEqual(self.client.post('/api/services/',{'title':'Not allowed'},format='json').status_code,403)
  with patch.dict('os.environ',{'GEMINI_API_KEY':''}):
   response=self.client.post('/api/assistant/ask/',{'question':'What should I see?','trip_id':self.trip.id},format='json')
  self.assertEqual(response.status_code,503)
  self.assertIn('Gemini API key',response.data['detail'])
 def test_gemini_response_is_returned_without_mutating_trip(self):
  response=httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'Visit the fort early.'}]}}]},request=httpx.Request('POST','https://generativelanguage.googleapis.com'))
  with patch.dict('os.environ',{'GEMINI_API_KEY':'test-key','GEMINI_MODEL':'gemini-3.6-flash'}),patch('core.services.httpx.Client') as client:
   client.return_value.__enter__.return_value.post.return_value=response
   result=AIService().advise('Trip in Gwalior','Where should I go?')
   kwargs=client.return_value.__enter__.return_value.post.call_args.kwargs
  self.assertEqual(result,{'answer':'Visit the fort early.','mutated_trip':False})
  self.assertEqual(kwargs['headers']['x-goog-api-key'],'test-key')
  self.assertEqual(kwargs['json']['contents'][0]['parts'][0]['text'],'Where should I go?')
 def test_all_destination_places_are_available_to_planner(self):
  self.auth(self.tourist)
  for index in range(25):Place.objects.create(destination=self.destination,name=f'Extra {index}',latitude=26.2,longitude=78.17)
  response=self.client.get(f'/api/places/?destination={self.destination.id}')
  self.assertEqual(response.status_code,200)
  self.assertEqual(len(response.data),28)
 def test_optimize_day_saves_a_shorter_route(self):
  self.auth(self.tourist)
  day=TripDay.objects.create(trip=self.trip,date=self.trip.start_date,position=1)
  for index,place in enumerate([self.places[0],self.places[2],self.places[1]],1):TripStop.objects.create(day=day,place=place,position=index)
  result=self.client.post(f'/api/trips/{self.trip.id}/optimize/',{'day_id':day.id},format='json')
  self.assertEqual(result.status_code,200,result.data)
  order=[item['place']['name'] for item in result.data['days'][0]['stops']]
  self.assertIn(order,(['Place 0','Place 1','Place 2'],['Place 2','Place 1','Place 0']))
  refreshed=self.client.get(f'/api/trips/{self.trip.id}/')
  self.assertEqual([item['place']['name'] for item in refreshed.data['days'][0]['stops']],order)
 def test_trip_generation_edit_and_ownership_persist(self):
  self.auth(self.tourist)
  response=self.client.post(f'/api/trips/{self.trip.id}/generate/',{'place_ids':[p.id for p in self.places]},format='json')
  self.assertEqual(response.status_code,200,response.data)
  self.assertEqual(sum(len(d['stops']) for d in response.data['days']),3)
  day1,day2=response.data['days'];ids=[[s['id'] for s in d['stops']] for d in response.data['days']]
  moved=ids[0].pop();ids[1].append(moved)
  edited=self.client.post(f'/api/trips/{self.trip.id}/edit_stops/',{'days':ids},format='json')
  self.assertEqual(edited.status_code,200,edited.data)
  refreshed=self.client.get(f'/api/trips/{self.trip.id}/')
  self.assertEqual([s['id'] for s in refreshed.data['days'][1]['stops']],ids[1])
  self.auth(self.guide_user);self.assertEqual(self.client.get(f'/api/trips/{self.trip.id}/').status_code,403)
 def test_plan_is_atomic_and_saves_places(self):
  self.auth(self.tourist)
  payload={'destination':self.destination.id,'title':'New trip','start_date':self.start.date().isoformat(),'end_date':(self.start.date()+timedelta(days=1)).isoformat(),'place_ids':[p.id for p in self.places]}
  created=self.client.post('/api/trips/plan/',payload,format='json')
  self.assertEqual(created.status_code,201,created.data)
  self.assertEqual(sum(len(d['stops']) for d in created.data['days']),3)
  before=Trip.objects.count();payload['place_ids']=[self.places[0].id,999999]
  self.assertEqual(self.client.post('/api/trips/plan/',payload,format='json').status_code,400)
  self.assertEqual(Trip.objects.count(),before)
 def test_guide_request_can_create_day_trip_automatically(self):
  cover=GuideCoverage.objects.create(guide=self.guide,level='CITY',destination=self.destination,label='Gwalior')
  service=GuideService.objects.create(guide=self.guide,coverage=cover,title='Fort walk',description='Tour',duration_minutes=120,price=2000,pricing_type='FIXED',max_group_size=4)
  AvailabilityRule.objects.create(guide=self.guide,weekday=self.start.weekday(),start_time='09:00',end_time='19:00')
  self.auth(self.tourist)
  result=self.client.post('/api/requests/',{'guide':self.guide.id,'service':service.id,'start':self.start.isoformat(),'end':(self.start+timedelta(hours=2)).isoformat(),'people':2},format='json')
  self.assertEqual(result.status_code,201,result.data)
  created=Trip.objects.get(pk=result.data['trip'])
  self.assertEqual(created.destination,self.destination)
  self.assertEqual(created.start_date,self.start.date())
  self.auth(self.guide_user)
  accepted=self.client.post(f"/api/requests/{result.data['id']}/transition/",{'status':'ACCEPTED'},format='json')
  self.assertEqual(accepted.status_code,200,accepted.data)
  confirmed=self.client.post('/api/bookings/confirm/',{'request_id':result.data['id']},format='json')
  self.assertEqual(confirmed.status_code,201,confirmed.data)
  self.auth(self.tourist)
  self.assertEqual(self.client.get('/api/bookings/').data['count'],1)
 def test_guide_request_chat_booking_and_availability(self):
  self.auth(self.guide_user)
  cover=self.client.post('/api/coverage/',{'level':'CITY','destination':self.destination.id,'label':'Gwalior'},format='json')
  self.assertEqual(cover.status_code,201,cover.data)
  service=self.client.post('/api/services/',{'title':'Fort walk','description':'Historic route','coverage':cover.data['id'],'duration_minutes':120,'price':'2000.00','pricing_type':'NEGOTIABLE','max_group_size':4,'specialties':[]},format='json')
  self.assertEqual(service.status_code,201,service.data)
  rule=self.client.post('/api/availability-rules/',{'weekday':self.start.weekday(),'start_time':'09:00','end_time':'19:00'},format='json')
  self.assertEqual(rule.status_code,201,rule.data)
  self.auth(self.tourist)
  payload={'guide':self.guide.id,'service':service.data['id'],'trip':self.trip.id,'start':self.start.isoformat(),'end':(self.start+timedelta(hours=2)).isoformat(),'people':2,'message':'Please show us the fort.'}
  request=self.client.post('/api/requests/',payload,format='json')
  self.assertEqual(request.status_code,201,request.data)
  offer=self.client.post('/api/offers/',{'request':request.data['id'],'amount':'1800.00'},format='json')
  self.assertEqual(offer.status_code,201,offer.data)
  self.auth(self.guide_user)
  self.assertEqual(self.client.get('/api/requests/').data['count'],1)
  self.assertEqual(self.client.post(f"/api/offers/{offer.data['id']}/accept/",{},format='json').status_code,200)
  booking=self.client.post('/api/bookings/confirm/',{'request_id':request.data['id']},format='json')
  self.assertEqual(booking.status_code,201,booking.data)
  self.assertEqual(booking.data['final_price'],'1800.00')
  slots=self.client.get(f'/api/guide-account/slots/?date={self.start.date().isoformat()}')
  self.assertEqual(slots.status_code,200)
  self.assertEqual(len(slots.data['slots']),2)
  self.assertEqual(slots.data['slots'][0]['end'],self.start.isoformat())
  self.auth(self.tourist)
  overlap=self.client.post('/api/requests/',payload,format='json')
  self.assertEqual(overlap.status_code,409)
  conversations=self.client.get('/api/conversations/').data['results'];self.assertEqual(len(conversations),1)
  sent=self.client.post(f"/api/conversations/{conversations[0]['id']}/messages/",{'body':'Hello!'},format='json')
  self.assertEqual(sent.status_code,201)
  self.auth(self.guide_user)
  received=self.client.get(f"/api/conversations/{conversations[0]['id']}/messages/")
  self.assertEqual(received.data[0]['body'],'Hello!')
  self.assertEqual(self.client.post(f"/api/bookings/{booking.data['id']}/change_status/",{'status':'CANCELLED'},format='json').status_code,200)
  reopened=self.client.get(f'/api/guide-account/slots/?date={self.start.date().isoformat()}')
  self.assertEqual(len(reopened.data['slots']),1)
 def test_review_requires_completed_booking_and_is_unique(self):
  cover=GuideCoverage.objects.create(guide=self.guide,level='CITY',destination=self.destination,label='Gwalior')
  service=GuideService.objects.create(guide=self.guide,coverage=cover,title='Fort walk',description='Tour',duration_minutes=120,price=2000,pricing_type='FIXED')
  req=GuideRequest.objects.create(tourist=self.tourist,guide=self.guide,trip=self.trip,service=service,start=self.start,end=self.start+timedelta(hours=2),people=2,status='CONFIRMED')
  booking=Booking.objects.create(request=req,tourist=self.tourist,guide=self.guide,trip=self.trip,service=service,start=req.start,end=req.end,destination=self.destination,original_price=2000,final_price=2000)
  self.auth(self.tourist)
  payload={'booking':booking.id,'rating':5,'text':'Wonderful guide'}
  self.assertEqual(self.client.post('/api/reviews/',payload,format='json').status_code,403)
  booking.status='COMPLETED';booking.save(update_fields=['status'])
  self.assertEqual(self.client.post('/api/reviews/',payload,format='json').status_code,201)
  self.assertEqual(self.client.post('/api/reviews/',payload,format='json').status_code,409)
  self.auth(self.guide_user);self.assertEqual(self.client.get('/api/reviews/').data['count'],1)

class WebSocketFlowTests(TransactionTestCase):
 def test_jwt_participant_can_chat_but_stranger_cannot(self):
  from wanderlust.asgi import application
  tourist=User.objects.create_user('tourist-ws',email='tourist-ws@example.com',role='TOURIST')
  guide_user=User.objects.create_user('guide-ws',email='guide-ws@example.com',role='GUIDE');guide=GuideProfile.objects.create(user=guide_user)
  stranger=User.objects.create_user('stranger-ws',email='stranger-ws@example.com',role='TOURIST')
  dest=Destination.objects.create(name='Jaipur',country='India',latitude=26.9,longitude=75.8)
  trip=Trip.objects.create(tourist=tourist,destination=dest,title='Trip',start_date=timezone.localdate(),end_date=timezone.localdate())
  cover=GuideCoverage.objects.create(guide=guide,level='CITY',destination=dest,label='Jaipur')
  service=GuideService.objects.create(guide=guide,coverage=cover,title='Walk',description='Tour',duration_minutes=60,price=100,pricing_type='FIXED')
  start=timezone.now()+timedelta(days=1)
  req=GuideRequest.objects.create(tourist=tourist,guide=guide,trip=trip,service=service,start=start,end=start+timedelta(hours=1),people=1)
  conversation=Conversation.objects.create(request=req);conversation.participants.add(tourist,guide_user)
  async def run():
   token=str(RefreshToken.for_user(tourist).access_token)
   socket=WebsocketCommunicator(application,f'/ws/conversations/{conversation.id}/',subprotocols=['jwt',token])
   connected,_=await socket.connect();self.assertTrue(connected)
   await socket.send_json_to({'body':'Hello from socket'})
   reply=await socket.receive_json_from();self.assertEqual(reply['body'],'Hello from socket')
   await socket.disconnect()
   denied=WebsocketCommunicator(application,f'/ws/conversations/{conversation.id}/',subprotocols=['jwt',str(RefreshToken.for_user(stranger).access_token)])
   connected,_=await denied.connect();self.assertFalse(connected)
  async_to_sync(run)()
  self.assertEqual(Message.objects.filter(conversation=conversation).count(),1)
