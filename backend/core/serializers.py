from rest_framework import serializers
from .models import Destination,Place,Trip,TripDay,TripStop,GuideProfile,GuideService,GuideRequest,Booking,Message,Review
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
 class Meta:model=Trip;fields='__all__';read_only_fields=['tourist']
class GuideServiceSerializer(serializers.ModelSerializer):
 class Meta:model=GuideService;fields='__all__';read_only_fields=['guide']
class GuideProfileSerializer(serializers.ModelSerializer):
 services=GuideServiceSerializer(many=True,read_only=True)
 class Meta:model=GuideProfile;fields='__all__'
class GuideRequestSerializer(serializers.ModelSerializer):
 class Meta:model=GuideRequest;fields='__all__';read_only_fields=['tourist','status']
class BookingSerializer(serializers.ModelSerializer):
 class Meta:model=Booking;fields='__all__';read_only_fields='__all__'.split()
class MessageSerializer(serializers.ModelSerializer):
 class Meta:model=Message;fields='__all__';read_only_fields=['sender']
class ReviewSerializer(serializers.ModelSerializer):
 class Meta:model=Review;fields='__all__';read_only_fields=['tourist']

