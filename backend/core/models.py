from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models,transaction
from django.db.models import Q
from uuid import uuid4

def profile_photo_path(instance,filename):
 return f'profiles/{instance.pk}/{uuid4().hex}.{filename.rsplit(".",1)[-1].lower()}'

class User(AbstractUser):
 class Role(models.TextChoices): TOURIST='TOURIST';GUIDE='GUIDE'
 role=models.CharField(max_length=10,choices=Role.choices,default=Role.TOURIST)
 email=models.EmailField(unique=True)
 phone=models.CharField(max_length=30,blank=True)
 profile_photo=models.FileField(upload_to=profile_photo_path,blank=True)

class TouristProfile(models.Model):
 user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='tourist_profile')
 bio=models.TextField(blank=True)
 home_city=models.CharField(max_length=120,blank=True)
 travel_style=models.CharField(max_length=120,blank=True)
 interests=models.JSONField(default=list)

class GuideProfile(models.Model):
 user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='guide_profile')
 bio=models.TextField(blank=True);photo_url=models.URLField(blank=True);languages=models.JSONField(default=list);specialties=models.JSONField(default=list);years_experience=models.PositiveSmallIntegerField(default=0);accepting_bookings=models.BooleanField(default=True);onboarding_complete=models.BooleanField(default=False);timezone=models.CharField(max_length=64,default='UTC')

class Destination(models.Model):
 name=models.CharField(max_length=160);country=models.CharField(max_length=120);latitude=models.FloatField();longitude=models.FloatField();provider_id=models.CharField(max_length=200,blank=True,db_index=True);image_url=models.URLField(blank=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['name','country'],name='unique_destination')]

class Place(models.Model):
 destination=models.ForeignKey(Destination,on_delete=models.CASCADE,related_name='places');name=models.CharField(max_length=200);description=models.TextField(blank=True);category=models.CharField(max_length=80,blank=True);latitude=models.FloatField();longitude=models.FloatField();rating=models.DecimalField(max_digits=3,decimal_places=1,null=True,blank=True);image_url=models.URLField(blank=True);provider_id=models.CharField(max_length=200,blank=True,db_index=True)

class GuideCoverage(models.Model):
 class Level(models.TextChoices): CITY='CITY';REGION='REGION';AREA='AREA';PLACE='PLACE'
 guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='coverage');level=models.CharField(max_length=10,choices=Level.choices);destination=models.ForeignKey(Destination,on_delete=models.CASCADE,null=True,blank=True);place=models.ForeignKey(Place,on_delete=models.CASCADE,null=True,blank=True);label=models.CharField(max_length=180)
 def clean(self):
  if self.level==self.Level.PLACE and not self.place_id: raise ValidationError('Place coverage requires a place.')

class GuideService(models.Model):
 class Pricing(models.TextChoices): FIXED='FIXED';NEGOTIABLE='NEGOTIABLE'
 guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='services');title=models.CharField(max_length=160);description=models.TextField();coverage=models.ForeignKey(GuideCoverage,on_delete=models.PROTECT);duration_minutes=models.PositiveIntegerField();price=models.DecimalField(max_digits=10,decimal_places=2);pricing_type=models.CharField(max_length=12,choices=Pricing.choices);max_group_size=models.PositiveSmallIntegerField(default=1);specialties=models.JSONField(default=list);active=models.BooleanField(default=True)

class AvailabilityRule(models.Model):
 guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='availability_rules');weekday=models.PositiveSmallIntegerField();start_time=models.TimeField();end_time=models.TimeField();active=models.BooleanField(default=True)
 class Meta: constraints=[models.CheckConstraint(condition=Q(end_time__gt=models.F('start_time')),name='availability_positive_interval')]

class AvailabilityException(models.Model):
 guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='availability_exceptions');start=models.DateTimeField();end=models.DateTimeField();available=models.BooleanField(default=False);reason=models.CharField(max_length=180,blank=True)
 class Meta: constraints=[models.CheckConstraint(condition=Q(end__gt=models.F('start')),name='exception_positive_interval')];indexes=[models.Index(fields=['guide','start','end'])]

class Trip(models.Model):
 tourist=models.ForeignKey(User,on_delete=models.CASCADE,related_name='trips');destination=models.ForeignKey(Destination,on_delete=models.PROTECT);title=models.CharField(max_length=180);start_date=models.DateField();end_date=models.DateField();notes=models.TextField(blank=True);created_at=models.DateTimeField(auto_now_add=True);updated_at=models.DateTimeField(auto_now=True)

class TripDay(models.Model):
 trip=models.ForeignKey(Trip,on_delete=models.CASCADE,related_name='days');date=models.DateField();position=models.PositiveSmallIntegerField()
 class Meta: ordering=['position'];constraints=[models.UniqueConstraint(fields=['trip','position'],name='unique_trip_day_position')]

class TripStop(models.Model):
 day=models.ForeignKey(TripDay,on_delete=models.CASCADE,related_name='stops');place=models.ForeignKey(Place,on_delete=models.PROTECT);position=models.PositiveSmallIntegerField();arrival_time=models.TimeField(null=True,blank=True);duration_minutes=models.PositiveIntegerField(default=90);distance_from_previous_km=models.FloatField(null=True,blank=True);manually_edited=models.BooleanField(default=False)
 class Meta: ordering=['position'];constraints=[models.UniqueConstraint(fields=['day','position'],name='unique_stop_position')]

class GuideRequest(models.Model):
 class Status(models.TextChoices): PENDING='PENDING';NEGOTIATING='NEGOTIATING';ACCEPTED='ACCEPTED';DECLINED='DECLINED';CONFIRMED='CONFIRMED';CANCELLED='CANCELLED';COMPLETED='COMPLETED'
 tourist=models.ForeignKey(User,on_delete=models.CASCADE,related_name='guide_requests');guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='requests');trip=models.ForeignKey(Trip,on_delete=models.CASCADE);service=models.ForeignKey(GuideService,on_delete=models.PROTECT);start=models.DateTimeField();end=models.DateTimeField();people=models.PositiveSmallIntegerField();message=models.TextField(blank=True);status=models.CharField(max_length=12,choices=Status.choices,default=Status.PENDING);created_at=models.DateTimeField(auto_now_add=True)
 ALLOWED={'PENDING':{'NEGOTIATING','ACCEPTED','DECLINED','CANCELLED'},'NEGOTIATING':{'ACCEPTED','DECLINED','CANCELLED'},'ACCEPTED':{'CONFIRMED','CANCELLED'},'CONFIRMED':{'COMPLETED','CANCELLED'},'DECLINED':set(),'CANCELLED':set(),'COMPLETED':set()}
 def transition(self,status):
  if status not in self.ALLOWED[self.status]: raise ValidationError(f'Cannot transition {self.status} to {status}')
  self.status=status;self.save(update_fields=['status'])

class NegotiationOffer(models.Model):
 request=models.ForeignKey(GuideRequest,on_delete=models.CASCADE,related_name='offers');sender=models.ForeignKey(User,on_delete=models.CASCADE);amount=models.DecimalField(max_digits=10,decimal_places=2);created_at=models.DateTimeField(auto_now_add=True);accepted_at=models.DateTimeField(null=True,blank=True)

class Conversation(models.Model):
 request=models.OneToOneField(GuideRequest,on_delete=models.CASCADE,related_name='conversation');participants=models.ManyToManyField(User,related_name='conversations');created_at=models.DateTimeField(auto_now_add=True)

class Message(models.Model):
 conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages');sender=models.ForeignKey(User,on_delete=models.CASCADE);body=models.TextField();created_at=models.DateTimeField(auto_now_add=True);read_at=models.DateTimeField(null=True,blank=True)

class Booking(models.Model):
 class Status(models.TextChoices): CONFIRMED='CONFIRMED';CANCELLED='CANCELLED';COMPLETED='COMPLETED'
 request=models.OneToOneField(GuideRequest,on_delete=models.PROTECT,related_name='booking');tourist=models.ForeignKey(User,on_delete=models.PROTECT,related_name='bookings');guide=models.ForeignKey(GuideProfile,on_delete=models.PROTECT,related_name='bookings');trip=models.ForeignKey(Trip,on_delete=models.PROTECT);service=models.ForeignKey(GuideService,on_delete=models.PROTECT);start=models.DateTimeField();end=models.DateTimeField();destination=models.ForeignKey(Destination,on_delete=models.PROTECT);original_price=models.DecimalField(max_digits=10,decimal_places=2);final_price=models.DecimalField(max_digits=10,decimal_places=2);status=models.CharField(max_length=12,choices=Status.choices,default=Status.CONFIRMED);created_at=models.DateTimeField(auto_now_add=True)
 class Meta: indexes=[models.Index(fields=['guide','start','end','status'])];constraints=[models.CheckConstraint(condition=Q(end__gt=models.F('start')),name='booking_positive_interval')]
 @classmethod
 def confirm(cls,request,final_price):
  with transaction.atomic():
   if final_price<=0:raise ValidationError('Booking price must be positive.')
   guide=GuideProfile.objects.select_for_update().get(pk=request.guide_id)
   if request.status!='ACCEPTED': raise ValidationError('Only accepted requests can be confirmed.')
   from .services import AvailabilityService
   if not AvailabilityService.contains(guide,request.start,request.end): raise ValidationError('Guide is unavailable during that time.')
   conflict=cls.objects.filter(guide=request.guide,status='CONFIRMED',start__lt=request.end,end__gt=request.start).exists()
   if conflict: raise ValidationError('This guide is already booked during that time.')
   booking=cls.objects.create(request=request,tourist=request.tourist,guide=request.guide,trip=request.trip,service=request.service,start=request.start,end=request.end,destination=request.trip.destination,original_price=request.service.price,final_price=final_price)
   request.status='CONFIRMED';request.save(update_fields=['status']);return booking

class Review(models.Model):
 booking=models.OneToOneField(Booking,on_delete=models.CASCADE,related_name='review');tourist=models.ForeignKey(User,on_delete=models.CASCADE);guide=models.ForeignKey(GuideProfile,on_delete=models.CASCADE,related_name='reviews');rating=models.PositiveSmallIntegerField();text=models.TextField(blank=True);created_at=models.DateTimeField(auto_now_add=True)
 def clean(self):
  if self.booking.status!='COMPLETED' or self.booking.tourist_id!=self.tourist_id: raise ValidationError('Only the tourist on a completed booking may review.')
  if not 1<=self.rating<=5: raise ValidationError('Rating must be 1–5.')

class Notification(models.Model):
 user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='notifications');kind=models.CharField(max_length=40);title=models.CharField(max_length=180);body=models.TextField(blank=True);read_at=models.DateTimeField(null=True,blank=True);created_at=models.DateTimeField(auto_now_add=True)
