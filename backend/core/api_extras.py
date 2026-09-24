from decimal import Decimal
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated,BasePermission
from rest_framework.response import Response
from .models import (AvailabilityException, AvailabilityRule, Booking, Conversation,
                     GuideCoverage, GuideProfile, GuideRequest, GuideService,
                     Message, NegotiationOffer, Notification, Review, Trip)
from .serializers import (AvailabilityExceptionSerializer, AvailabilityRuleSerializer,
                          ConversationSerializer, GuideCoverageSerializer,
                          GuideServiceSerializer, MessageSerializer,
                          NegotiationOfferSerializer, NotificationSerializer,
                          ReviewSerializer)
from .services import AvailabilityService,AIService


def guide_for(user):
    if user.role != 'GUIDE':
        return None
    return GuideProfile.objects.filter(user=user).first()

class GuideOnly(BasePermission):
    def has_permission(self,request,view):return request.user.is_authenticated and request.user.role=='GUIDE'


class GuideOwnedViewSet(viewsets.ModelViewSet):
    permission_classes = [GuideOnly]
    def get_queryset(self):
        guide = guide_for(self.request.user)
        return super().get_queryset().filter(guide=guide) if guide else super().get_queryset().none()
    def perform_create(self, serializer):
        guide = guide_for(self.request.user)
        if not guide:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Guide account required.')
        serializer.save(guide=guide)


class CoverageViewSet(GuideOwnedViewSet):
    queryset = GuideCoverage.objects.all()
    serializer_class = GuideCoverageSerializer
    def destroy(self,request,*args,**kwargs):
        item=self.get_object()
        if item.guideservice_set.exists():return Response({'detail':'Remove or reassign services using this coverage first.'},status=409)
        return super().destroy(request,*args,**kwargs)


class ServiceViewSet(GuideOwnedViewSet):
    queryset = GuideService.objects.all()
    serializer_class = GuideServiceSerializer
    def perform_create(self, serializer):
        guide = guide_for(self.request.user)
        if not guide or serializer.validated_data['coverage'].guide_id != guide.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Choose one of your coverage areas.')
        serializer.save(guide=guide)
    def perform_update(self, serializer):
        guide = guide_for(self.request.user)
        coverage = serializer.validated_data.get('coverage')
        if coverage and coverage.guide_id != guide.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Choose one of your coverage areas.')
        serializer.save()
    def destroy(self,request,*args,**kwargs):
        item=self.get_object()
        if item.guiderequest_set.exists():return Response({'detail':'This service has requests; deactivate it instead.'},status=409)
        return super().destroy(request,*args,**kwargs)


class RuleViewSet(GuideOwnedViewSet):
    queryset = AvailabilityRule.objects.all()
    serializer_class = AvailabilityRuleSerializer


class ExceptionViewSet(GuideOwnedViewSet):
    queryset = AvailabilityException.objects.all()
    serializer_class = AvailabilityExceptionSerializer


class GuideAccountViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    @action(detail=False, methods=['get', 'patch'])
    def mine(self, request):
        from .serializers import GuideProfileSerializer
        guide = guide_for(request.user)
        if not guide:
            return Response({'detail':'Guide account required.'}, status=403)
        if request.method == 'PATCH':
            allowed = ('bio','photo_url','languages','specialties','years_experience','accepting_bookings','onboarding_complete','timezone')
            if 'timezone' in request.data:
                try:ZoneInfo(request.data['timezone'])
                except (ZoneInfoNotFoundError,TypeError):return Response({'detail':'Enter a valid IANA timezone.'},status=400)
            for key in allowed:
                if key in request.data:
                    setattr(guide,key,request.data[key])
            try:guide.full_clean()
            except ValidationError as exc:return Response({'detail':str(exc)},status=400)
            guide.save()
        return Response(GuideProfileSerializer(guide).data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        guide = guide_for(request.user)
        if not guide:
            return Response({'detail':'Guide account required.'},status=403)
        return Response({'upcoming_bookings':Booking.objects.filter(guide=guide,status='CONFIRMED',end__gte=timezone.now()).count(),
                         'new_requests':GuideRequest.objects.filter(guide=guide,status='PENDING').count(),
                         'active_services':GuideService.objects.filter(guide=guide,active=True).count(),
                         'unread_messages':Message.objects.filter(conversation__request__guide=guide,read_at__isnull=True).exclude(sender=request.user).count(),
                         'accepting_bookings':guide.accepting_bookings})

    @action(detail=False, methods=['get'])
    def slots(self, request):
        from datetime import date
        guide_id = request.query_params.get('guide')
        guide = get_object_or_404(GuideProfile,pk=guide_id) if guide_id else guide_for(request.user)
        if not guide:
            return Response({'detail':'Guide account required.'},status=403)
        try:day=date.fromisoformat(request.query_params['date'])
        except (KeyError,ValueError):return Response({'detail':'Provide a valid date.'},status=400)
        return Response({'date':day.isoformat(),'accepting_bookings':guide.accepting_bookings,
                         'slots':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in AvailabilityService.slots(guide,day)] if guide.accepting_bookings else []})


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user).select_related('request__tourist','request__guide__user','request__service').distinct().order_by('-created_at','-id')
    @action(detail=True,methods=['get','post'])
    def messages(self,request,pk=None):
        conversation=self.get_object()
        if request.method=='GET':
            items=conversation.messages.select_related('sender').order_by('created_at')
            items.exclude(sender=request.user).filter(read_at__isnull=True).update(read_at=timezone.now())
            return Response(MessageSerializer(items,many=True).data)
        body=str(request.data.get('body','')).strip()
        if not body:return Response({'detail':'Message cannot be empty.'},status=400)
        item=Message.objects.create(conversation=conversation,sender=request.user,body=body)
        other=conversation.participants.exclude(pk=request.user.pk).first()
        if other:Notification.objects.create(user=other,kind='NEW_MESSAGE',title='New message',body=body[:180])
        return Response(MessageSerializer(item).data,status=201)


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=NegotiationOfferSerializer
    permission_classes=[IsAuthenticated]
    def get_queryset(self):
        user=self.request.user
        return NegotiationOffer.objects.filter(Q(request__tourist=user)|Q(request__guide__user=user)).distinct()
    def create(self,request):
        guide_request=get_object_or_404(GuideRequest,pk=request.data.get('request'))
        if request.user.id not in (guide_request.tourist_id,guide_request.guide.user_id):return Response({'detail':'Not a participant.'},status=403)
        if guide_request.service.pricing_type!='NEGOTIABLE' or guide_request.status not in ('PENDING','NEGOTIATING'):
            return Response({'detail':'Negotiation is closed.'},status=400)
        try:amount=Decimal(str(request.data['amount']))
        except (KeyError,ValueError):return Response({'detail':'Enter an amount.'},status=400)
        if amount<=0:return Response({'detail':'Amount must be positive.'},status=400)
        offer=NegotiationOffer.objects.create(request=guide_request,sender=request.user,amount=amount)
        guide_request.status='NEGOTIATING';guide_request.save(update_fields=['status'])
        other=guide_request.guide.user if request.user.id==guide_request.tourist_id else guide_request.tourist
        Notification.objects.create(user=other,kind='NEW_OFFER',title='New price offer',body=f'{request.user.get_full_name()}: ₹{amount}')
        return Response(self.get_serializer(offer).data,status=201)
    @action(detail=True,methods=['post'])
    def accept(self,request,pk=None):
        offer=self.get_object();req=offer.request
        if request.user.id not in (req.tourist_id,req.guide.user_id) or offer.sender_id==request.user.id:
            return Response({'detail':'Only the other participant can accept this offer.'},status=403)
        if req.status!='NEGOTIATING':return Response({'detail':'Negotiation is closed.'},status=400)
        if req.offers.order_by('-created_at','-id').first().id!=offer.id:return Response({'detail':'Only the latest offer can be accepted.'},status=409)
        offer.accepted_at=timezone.now();offer.save(update_fields=['accepted_at'])
        req.status='ACCEPTED';req.save(update_fields=['status'])
        Notification.objects.create(user=offer.sender,kind='DEAL_ACCEPTED',title='Offer accepted')
        return Response(self.get_serializer(offer).data)


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=ReviewSerializer
    permission_classes=[IsAuthenticated]
    def get_queryset(self):return Review.objects.filter(Q(tourist=self.request.user)|Q(guide__user=self.request.user)).distinct().order_by('-created_at','-id')
    def create(self,request):
        booking=get_object_or_404(Booking,pk=request.data.get('booking'))
        if booking.tourist_id!=request.user.id or booking.status!='COMPLETED':return Response({'detail':'Only the tourist on a completed booking can review.'},status=403)
        if Review.objects.filter(booking=booking).exists():return Response({'detail':'This booking is already reviewed.'},status=409)
        serializer=self.get_serializer(data=request.data);serializer.is_valid(raise_exception=True)
        review=serializer.save(tourist=request.user,guide=booking.guide)
        review.full_clean()
        return Response(self.get_serializer(review).data,status=201)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=NotificationSerializer
    permission_classes=[IsAuthenticated]
    def get_queryset(self):return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    @action(detail=True,methods=['post'])
    def read(self,request,pk=None):
        item=self.get_object();item.read_at=timezone.now();item.save(update_fields=['read_at'])
        return Response(self.get_serializer(item).data)


class AssistantViewSet(viewsets.ViewSet):
    permission_classes=[IsAuthenticated]
    @action(detail=False,methods=['post'])
    def ask(self,request):
        question=str(request.data.get('question','')).strip()
        if not question:return Response({'detail':'Ask a question first.'},status=400)
        if len(question)>2000:return Response({'detail':'Question is too long.'},status=400)
        context=''
        if request.data.get('trip_id'):
            trip=get_object_or_404(Trip.objects.prefetch_related('days__stops__place').select_related('destination'),pk=request.data['trip_id'],tourist=request.user)
            context=f'Trip: {trip.destination.name}, {trip.destination.country}; {trip.start_date} to {trip.end_date}. '
            context+=' '.join(f'Day {day.position}: '+', '.join(stop.place.name for stop in day.stops.all()) for day in trip.days.all())
        elif request.user.role=='GUIDE':
            guide=guide_for(request.user)
            context='Guide profile: '+', '.join(c.label for c in guide.coverage.all())+'; services: '+', '.join(s.title for s in guide.services.filter(active=True))
        try:
            return Response(AIService().advise(context,question))
        except AIService.Unavailable as exc:
            return Response({'detail':str(exc)},status=503)
