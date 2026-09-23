from datetime import time
from django.core.management.base import BaseCommand
from core.models import AvailabilityRule, Destination, GuideCoverage, GuideProfile, GuideService, User


class Command(BaseCommand):
    help='Give the existing local demo Guide a usable profile, coverage, services and weekly schedule.'

    def handle(self,*args,**options):
        user=User.objects.filter(email='guide@wanderlust.local',role='GUIDE').first()
        if not user:
            self.stdout.write('Demo Guide account not found; nothing changed.')
            return
        guide=GuideProfile.objects.get(user=user)
        if guide.timezone!='Asia/Kolkata':guide.timezone='Asia/Kolkata';guide.save(update_fields=['timezone'])
        if not guide.onboarding_complete:
            guide.bio='I lead relaxed walks through local heritage, architecture and food streets.'
            guide.languages=['English','Hindi']
            guide.specialties=['Heritage','Local food']
            guide.years_experience=4
            guide.onboarding_complete=True
            guide.save()
        for name in ('Gwalior','Udaipur'):
            destination=Destination.objects.filter(name=name,country='India').first()
            if not destination:continue
            coverage,_=GuideCoverage.objects.get_or_create(guide=guide,level='CITY',destination=destination,label=name)
            GuideService.objects.get_or_create(guide=guide,coverage=coverage,title=f'{name} heritage walk',defaults={'description':'A guided introduction to the best-known historic places and local stories.','duration_minutes':180,'price':1800,'pricing_type':'NEGOTIABLE','max_group_size':6,'specialties':['Heritage'],'active':True})
        for weekday in range(7):
            AvailabilityRule.objects.get_or_create(guide=guide,weekday=weekday,start_time=time(9),end_time=time(19))
        self.stdout.write(self.style.SUCCESS('Demo Guide is ready. Use a future-dated trip to request a tour.'))
