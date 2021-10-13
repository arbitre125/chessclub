from django.contrib import admin
from django.db import models
from django.db.models import Q
from django.db.models.signals import m2m_changed
from django.forms import TextInput, Textarea, IntegerField, CharField
from .models import League, Schedule, Standings, Player, Season, STANDINGS_ORDER, POINTS
from django.utils import timezone
from django.urls import resolve, reverse
from django.utils.safestring import mark_safe
from django import forms
from datetime import datetime
from .utils import standings_save, standings_update

from tinymce.widgets import TinyMCE

from django.forms import BaseInlineFormSet
import requests

from .views import create_round_robin_view, create_round_view, manage_league_view, manage_schedule_view, download_league_pdf, make_table_pdf, add_club_night_view

class LimitModelFormset(BaseInlineFormSet):
    """ Base Inline formset to limit inline Model query results. """
    def __init__(self, *args, **kwargs):
        super(LimitModelFormset, self).__init__(*args, **kwargs)
        _kwargs = {self.fk.name: kwargs['instance']}
        self.queryset = kwargs['queryset'].filter(**_kwargs).order_by('-id')[:20]

def get_parent_object_from_request(self, request):
    """
    Returns the parent object from the request or None.

    Note that this only works for Inlines, because the `parent_model`
    is not available in the regular admin.ModelAdmin as an attribute.
    """
    resolved = resolve(request.path_info)
    if resolved.args:
        return self.parent_model.objects.get(id=resolved.kwargs['object_id'])
    return None


class ScheduleInline(admin.TabularInline):
    model = Schedule
    fields = ('round','date','white','black','result')
    formfield_overrides = {
        models.IntegerField: {'widget': TextInput(attrs={'style':'width: 20px;'})},
    }
    show_change_link = True
    formset = LimitModelFormset
    max_num = 25
    extra = 5

    def get_extra (self, request, obj=None, **kwargs):
        """Dynamically sets the number of extra forms. 0 if the related object
        already exists or the extra configuration otherwise."""
        if obj:
            # Don't add any extra forms if the related object already exists.
            return 0
        return self.extra

    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if 'object_id' in kwargs:
            league = League.objects.get(id=resolve(request.path_info).kwargs['object_id'])
            if league is not None:
                # for ease of adding in the django admin, make it so that only
                # the players in the league are visible
                players = [p.pk for p in league.players.all()]
                # but... need this in case someone is not in the league but has
                # already played, maybe they should be added to the league automatically
                games = Schedule.objects.filter(league = league.pk)
                for g in games:
                    if g.white.pk not in players:
                        players += [ g.white.pk ]
                    if g.black not in players:
                        players += [ g.black.pk]
                kwargs["queryset"] = Player.objects.filter(pk__in = players)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
class StandingsInline(admin.TabularInline):
    model = Standings

    def get_parent_object_from_request(self, request):
        """
        Returns the parent object from the request or None.

        Note that this only works for Inlines, because the `parent_model`
        is not available in the regular admin.ModelAdmin as an attribute.
        """
        resolved = resolve(request.path_info)
        if resolved.args:
            return self.parent_model.objects.get(pk=resolved.args[0])
        return None
    ordering = ('position', '-points')
    exclude = ('matches', 'win', 'lost', 'draws', 'score', 'score_lost')
    max_num=3
    actions = []
    readonly_fields = ('player',)
    fields = ('points', 'position')



from functools import update_wrapper
from django.contrib import admin
from django.contrib.admin import ModelAdmin


class LeagueAdminForm(forms.ModelForm):

    class Meta:
        model = League
        fields = '__all__'
        exclude = []
        
        widgets = {
            'description': TinyMCE(attrs = {'rows' : '30', 'cols' : '100', 'content_style' : "color:#FFFF00", 'body_class': 'review', 'body_id': 'review',})
        }

from matplotlib.backends.backend_pdf import PdfPages
from django.http import HttpResponse
from io import BytesIO

class LeagueAdmin(ModelAdmin):
    change_form_template = 'change_form.html'
    manage_view_template = 'manage_form.html'
    create_round_template = 'create_round.html'
    create_round_robin_template = 'create_round_robin.html'

    form = LeagueAdminForm
    inlines = [
        #StandingsInline, 
        ScheduleInline,
    ]

    def link(self, obj):
        url = reverse('league',args = {obj.slug})
        return mark_safe("<a href='%s'>Go</a>" % url)

    prepopulated_fields = {'slug': ('name', 'season',), }
    actions=['update_standings', 'make_pdf', 'update_ratings']
    list_display = ('name','link')
    def update_standings(self,request,queryset):
        for obj in queryset:
            standings_save(obj)
            standings_update(obj)
            self.message_user(request, "league standings updated")

    def update_ratings(self,request,queryset):
        for obj in queryset:
            standings = Standings.objects.filter(league=obj)
            for s in standings:
                s.rating = s.player.rating
                s.save()
            self.message_user(request, "Ratings of players in league updated")


    def make_pdf(self, request, queryset):
        response = HttpResponse(content_type='application/pdf')
        filename = 'league_tables'
        response['Content-Disposition'] = 'attachement; filename={0}.pdf'.format(filename)
        buffer = BytesIO()
        with PdfPages(buffer) as pdf:
            for obj in queryset:
                fig = make_table_pdf(obj)
                pdf.savefig()

        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response

    def save_model(self, request, obj, form, change):
        obj.save()
        form.save_m2m()
        standings_save(obj)
        standings_update(obj)

    
    def get_urls(self):
        from django.conf.urls import url
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, self, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urls = [url(r'^(.+)/manage/$', wrap(manage_league_view),name='%s_%s_manage' % info)]
        urls += [url(r'^(.+)/create_round/$', wrap(create_round_view),
        name='%s_%s_create_round' % info)]
        urls += [url(r'^(.+)/create_round_robin/$', wrap(create_round_robin_view),
        name='%s_%s_create_round_robin' % info)]
        urls += [url(r'^(.+)/download_pdf/$', wrap(download_league_pdf),
        name='%s_%s_download_pdf' % info)]

        super_urls = super(LeagueAdmin, self).get_urls()
        return urls + super_urls
    

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'surename')
    list_filter = ('name',)

    actions = ['update_ratings']
    def update_ratings(self, request, queryset):
        for p in queryset:
            if p.ecf == None: continue
            url = 'https://www.ecfrating.org.uk/v2/new/api.php?v2/ratings/Standard/%s/%s'%(p.ecf, datetime.today().date())
            grade = requests.get(url)
            if grade:
                grade = grade.json()
                self.message_user(request, '%s rating updated from %i to %i'%(p, p.rating, grade['revised_rating']))
                p.rating = grade['revised_rating']
                p.save()

class ScheduleAdmin(admin.ModelAdmin):
    change_list_template = 'change_game_list.html'
    change_form_template = 'change_game_form.html'
    manage_view_template = 'manage_game_form.html'
    add_clubnight_template = 'add_club_night.html'
    list_filter = ('league',)

    def get_urls(self):
        from django.conf.urls import url
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, self, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name
        urls = [url(r'^addclubnight/', wrap(add_club_night_view),name='%s_%s_addclubnight' % info)]
        super_urls = super(ScheduleAdmin, self).get_urls()
        return urls + super_urls


    

admin.site.register(League, LeagueAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Schedule, ScheduleAdmin)
admin.site.register(Season)
    
# Register your models here.
