from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Destination,Place,Trip,TripDay,TripStop,GuideProfile,GuideService,GuideRequest,Booking,Message,Review,TouristProfile,GuideCoverage,AvailabilityRule,AvailabilityException,Notification
User=get_user_model()
class UserSerializer(serializers.ModelSerializer):
 name=serializers.SerializerMethodField()
 class Meta:model=User;fields=['id','email','username','name','role']
 def get_name(self,obj):return obj.get_full_name() or obj.username
class SignupSerializer(serializers.Serializer):
 name=serializers.CharField(max_length=150);email=serializers.EmailField();password=serializers.CharField(write_only=True,min_length=8);role=serializers.ChoiceField(choices=User.Role.choices)
 def validate_email(self,value):
  value=value.lower().strip()
  if User.objects.filter(email__iexact=value).exists():raise serializers.ValidationError('An account with this email already exists.')
  return value
 def create(self,data):
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
class GuideServiceSerializer(serializers.ModelSerializer):
 class Meta:model=GuideService;fields='__all__';read_only_fields=['guide']
class GuideProfileSerializer(serializers.ModelSerializer):
 services=GuideServiceSerializer(many=True,read_only=True)
 name=serializers.SerializerMethodField();email=serializers.EmailField(source='user.email',read_only=True);coverage=serializers.SerializerMethodField()
 class Meta:model=GuideProfile;fields='__all__'
 def get_name(self,obj):return obj.user.get_full_name() or obj.user.username
 def get_coverage(self,obj):return [{'id':x.id,'level':x.level,'label':x.label,'destination':x.destination_id,'place':x.place_id} for x in obj.coverage.all()]
class GuideRequestSerializer(serializers.ModelSerializer):
 class Meta:model=GuideRequest;fields='__all__';read_only_fields=['tourist','status']
class BookingSerializer(serializers.ModelSerializer):
 class Meta:model=Booking;fields='__all__';read_only_fields='__all__'.split()
class MessageSerializer(serializers.ModelSerializer):
 class Meta:model=Message;fields='__all__';read_only_fields=['sender']
class ReviewSerializer(serializers.ModelSerializer):
 class Meta:model=Review;fields='__all__';read_only_fields=['tourist']
