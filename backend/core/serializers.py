from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg
from .models import Destination,Place,Trip,TripDay,TripStop,GuideProfile,GuideService,GuideRequest,Booking,Message,Review,TouristProfile,GuideCoverage,AvailabilityRule,AvailabilityException,Notification,Conversation,NegotiationOffer
User=get_user_model()
class UserSerializer(serializers.ModelSerializer):
 name=serializers.SerializerMethodField()
 photo_url=serializers.SerializerMethodField()
 class Meta:model=User;fields=['id','email','username','name','role','first_name','last_name','phone','photo_url']
 def get_name(self,obj):return obj.get_full_name() or obj.username
 def get_photo_url(self,obj):
  request=self.context.get('request')
  return request.build_absolute_uri(obj.profile_photo.url) if obj.profile_photo and request else (obj.profile_photo.url if obj.profile_photo else '')

class TouristProfileSerializer(serializers.ModelSerializer):
 user=UserSerializer(read_only=True)
 class Meta:model=TouristProfile;fields=['user','bio','home_city','travel_style','interests']
class SignupSerializer(serializers.Serializer):
 name=serializers.CharField(max_length=150);email=serializers.EmailField();password=serializers.CharField(write_only=True,min_length=8);confirm_password=serializers.CharField(write_only=True);terms=serializers.BooleanField();role=serializers.ChoiceField(choices=User.Role.choices)
 def validate(self,data):
  if data['password']!=data['confirm_password']:raise serializers.ValidationError('Passwords do not match.')
  if not data['terms']:raise serializers.ValidationError('Accept the terms to create an account.')
  return data
 def validate_email(self,value):
  value=value.lower().strip()
  if User.objects.filter(email__iexact=value).exists():raise serializers.ValidationError('An account with this email already exists.')
  return value
 def create(self,data):
  data.pop('confirm_password',None);data.pop('terms',None)
  with transaction.atomic():
   parts=data['name'].strip().split(' ',1);user=User.objects.create_user(username=data['email'],email=data['email'],password=data['password'],role=data['role'],first_name=parts[0],last_name=parts[1] if len(parts)>1 else '')
   TouristProfile.objects.create(user=user) if user.role=='TOURIST' else GuideProfile.objects.create(user=user)
   return user
class PlaceSerializer(serializers.ModelSerializer):
 class Meta:model=Place;fields='__all__'
class DestinationSerializer(serializers.ModelSerializer):
 places=PlaceSerializer(many=True,read_only=True)
 class Meta:model=Destination;fields='__all__'
class TripStopSerializer(serializers.ModelSerializer):
 place=PlaceSerializer(read_only=True)
 class Meta:model=TripStop;fields='__all__'
class TripDaySerializer(serializers.ModelSerializer):
 stops=TripStopSerializer(many=True,read_only=True)
 class Meta:model=TripDay;fields='__all__'
class TripSerializer(serializers.ModelSerializer):
 days=TripDaySerializer(many=True,read_only=True)
 destination_detail=DestinationSerializer(source='destination',read_only=True)
 class Meta:model=Trip;fields='__all__';read_only_fields=['tourist']
 def validate(self,data):
  start=data.get('start_date',getattr(self.instance,'start_date',None));end=data.get('end_date',getattr(self.instance,'end_date',None))
  if start and end and end<start:raise serializers.ValidationError('End date must not be before start date.')
  if start and end and (end-start).days>30:raise serializers.ValidationError('Trips are limited to 31 days.')
  return data
class GuideServiceSerializer(serializers.ModelSerializer):
 class Meta:model=GuideService;fields='__all__';read_only_fields=['guide']
 def validate(self,data):
  price=data.get('price',getattr(self.instance,'price',None))
  if price is not None and price<=0:raise serializers.ValidationError('Price must be positive.')
  return data
class GuideProfileSerializer(serializers.ModelSerializer):
 services=GuideServiceSerializer(many=True,read_only=True)
 name=serializers.SerializerMethodField();email=serializers.EmailField(source='user.email',read_only=True);coverage=serializers.SerializerMethodField();rating=serializers.SerializerMethodField();review_count=serializers.SerializerMethodField();photo_url=serializers.SerializerMethodField()
 class Meta:model=GuideProfile;fields='__all__'
 def get_name(self,obj):return obj.user.get_full_name() or obj.user.username
 def get_coverage(self,obj):return [{'id':x.id,'level':x.level,'label':x.label,'destination':x.destination_id,'place':x.place_id} for x in obj.coverage.all()]
 def get_rating(self,obj):return obj.reviews.aggregate(value=Avg('rating'))['value']
 def get_review_count(self,obj):return obj.reviews.count()
 def get_photo_url(self,obj):
  request=self.context.get('request')
  if obj.user.profile_photo:return request.build_absolute_uri(obj.user.profile_photo.url) if request else obj.user.profile_photo.url
  return obj.photo_url
class GuideRequestSerializer(serializers.ModelSerializer):
 trip=serializers.PrimaryKeyRelatedField(queryset=Trip.objects.all(),required=False,allow_null=True)
 guide_name=serializers.CharField(source='guide.user.get_full_name',read_only=True)
 tourist_name=serializers.CharField(source='tourist.get_full_name',read_only=True)
 service_title=serializers.CharField(source='service.title',read_only=True)
 service_pricing_type=serializers.CharField(source='service.pricing_type',read_only=True)
 class Meta:model=GuideRequest;fields='__all__';read_only_fields=['tourist','status']
class BookingSerializer(serializers.ModelSerializer):
 class Meta:model=Booking;fields='__all__';read_only_fields='__all__'.split()
class MessageSerializer(serializers.ModelSerializer):
 class Meta:model=Message;fields='__all__';read_only_fields=['sender']
class ReviewSerializer(serializers.ModelSerializer):
 class Meta:model=Review;fields='__all__';read_only_fields=['tourist','guide']
 def validate_rating(self,value):
  if not 1<=value<=5:raise serializers.ValidationError('Rating must be 1–5.')
  return value
class GuideCoverageSerializer(serializers.ModelSerializer):
 class Meta:model=GuideCoverage;fields='__all__';read_only_fields=['guide']
 def validate(self,data):
  level=data.get('level',getattr(self.instance,'level',None));place=data.get('place',getattr(self.instance,'place',None));destination=data.get('destination',getattr(self.instance,'destination',None))
  if level=='PLACE' and not place:raise serializers.ValidationError('Choose an attraction for place coverage.')
  if place and destination and place.destination_id!=destination.id:raise serializers.ValidationError('Attraction must belong to the selected destination.')
  return data
class AvailabilityRuleSerializer(serializers.ModelSerializer):
 class Meta:model=AvailabilityRule;fields='__all__';read_only_fields=['guide']
 def validate(self,data):
  weekday=data.get('weekday',getattr(self.instance,'weekday',None))
  if weekday is not None and not 0<=weekday<=6:raise serializers.ValidationError('Weekday must be Monday–Sunday.')
  start=data.get('start_time',getattr(self.instance,'start_time',None));end=data.get('end_time',getattr(self.instance,'end_time',None))
  if start and end and end<=start:raise serializers.ValidationError('End time must be after start time.')
  return data
class AvailabilityExceptionSerializer(serializers.ModelSerializer):
 class Meta:model=AvailabilityException;fields='__all__';read_only_fields=['guide']
 def validate(self,data):
  start=data.get('start',getattr(self.instance,'start',None));end=data.get('end',getattr(self.instance,'end',None))
  if start and end and end<=start:raise serializers.ValidationError('End must be after start.')
  return data
class ConversationSerializer(serializers.ModelSerializer):
 request_detail=GuideRequestSerializer(source='request',read_only=True)
 class Meta:model=Conversation;fields=['id','request','request_detail','created_at']
class NegotiationOfferSerializer(serializers.ModelSerializer):
 class Meta:model=NegotiationOffer;fields='__all__';read_only_fields=['sender','accepted_at']
class NotificationSerializer(serializers.ModelSerializer):
 class Meta:model=Notification;fields='__all__';read_only_fields=['user','created_at']
