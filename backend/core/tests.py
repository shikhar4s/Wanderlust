from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import *
from .services import ItineraryService
from rest_framework.test import APIClient
from unittest.mock import patch
class CoreRulesTests(TestCase):
 def setUp(self):
  self.tourist=User.objects.create_user('tourist',email='tourist@example.com',role='TOURIST');self.guide_user=User.objects.create_user('guide',email='guide@example.com',role='GUIDE');self.guide=GuideProfile.objects.create(user=self.guide_user);self.dest=Destination.objects.create(name='Udaipur',country='India',latitude=24.58,longitude=73.68);self.cover=GuideCoverage.objects.create(guide=self.guide,level='CITY',destination=self.dest,label='Udaipur');self.service=GuideService.objects.create(guide=self.guide,title='Walk',description='Heritage walk',coverage=self.cover,duration_minutes=120,price=2000,pricing_type='NEGOTIABLE');self.trip=Trip.objects.create(tourist=self.tourist,destination=self.dest,title='Trip',start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=1))
 def request(self,start=None):return GuideRequest.objects.create(tourist=self.tourist,guide=self.guide,trip=self.trip,service=self.service,start=start or timezone.now()+timedelta(days=2),end=(start or timezone.now()+timedelta(days=2))+timedelta(hours=2),people=2)
 def test_overlap_rejected_but_adjacent_allowed(self):
  req=self.request();Booking.confirm(req,1800)
  overlap=self.request(req.start+timedelta(hours=1))
  with self.assertRaises(ValidationError):Booking.confirm(overlap,1900)
  adjacent=self.request(req.end);self.assertIsNotNone(Booking.confirm(adjacent,2000))
 def test_state_transitions_are_guarded(self):
  req=self.request();req.transition('NEGOTIATING')
  with self.assertRaises(ValidationError):req.transition('COMPLETED')
 def test_itinerary_is_deterministic_and_complete(self):
  pts=[Place.objects.create(destination=self.dest,name=str(i),latitude=24.5+i/100,longitude=73.6+i/100) for i in range(6)]
  result=ItineraryService.generate(pts.copy(),3);self.assertEqual(sum(map(len,result)),6);self.assertEqual([[p.id for p in x] for x in result],[[p.id for p in x] for x in ItineraryService.generate(pts.copy(),3)])

class AuthenticationFlowTests(TestCase):
 def setUp(self):self.client=APIClient()
 def test_tourist_signup_creates_profile_and_tokens(self):
  response=self.client.post('/api/auth/signup/',{'name':'Mira Sen','email':'mira@example.com','password':'StrongPass123','role':'TOURIST'},format='json')
  self.assertEqual(response.status_code,201);self.assertIn('access',response.data);user=User.objects.get(email='mira@example.com');self.assertEqual(user.role,'TOURIST');self.assertTrue(hasattr(user,'tourist_profile'))
 def test_guide_cannot_create_tourist_trip(self):
  guide=User.objects.create_user('guide@example.com',email='guide@example.com',password='StrongPass123',role='GUIDE');GuideProfile.objects.create(user=guide);self.client.force_authenticate(guide)
  response=self.client.post('/api/trips/',{},format='json');self.assertEqual(response.status_code,403)
 def test_duplicate_email_rejected(self):
  payload={'name':'Mira Sen','email':'mira@example.com','password':'StrongPass123','role':'TOURIST'};self.assertEqual(self.client.post('/api/auth/signup/',payload,format='json').status_code,201);self.assertEqual(self.client.post('/api/auth/signup/',payload,format='json').status_code,400)
 def test_cached_destination_survives_provider_outage(self):
  destination=Destination.objects.create(name='Udaipur',country='India',latitude=24.58,longitude=73.68)
  Place.objects.create(destination=destination,name='City Palace',latitude=24.57,longitude=73.68)
  with patch('core.views.LocationService.search',side_effect=RuntimeError('provider unavailable')):
   response=self.client.get('/api/destinations/search/?q=Udaipur%2C%20India')
  self.assertEqual(response.status_code,200)
  self.assertEqual(response.data['places'][0]['name'],'City Palace')
