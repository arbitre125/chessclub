from django.contrib import admin
from .models import news, event, album, image, simul, htmlobject
from tinymce.widgets import TinyMCE
from django import forms
from functools import update_wrapper
from .forms import LichessEventForm
from league.utils import create_arena_event
import datetime
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth import get_permission_codename



# Register your models here.


from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.contrib.auth.models import User


class HtmlObjectAdminForm(forms.ModelForm):
    title = forms.CharField(max_length=50)
    body = forms.CharField(max_length= 10000, widget = TinyMCE(attrs = {'rows' : '30', 'cols' : '100', 'content_style' : "color:#FFFF00", 'body_class': 'review', 'body_id': 'review',}), label='News')

    class Meta:
        fields = ('title', 'body')
        model = news

class HtmlObjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'body']
    search_fields = [ 'title' ]
    form = HtmlObjectAdminForm

class ImageInline(admin.TabularInline):
    model = image

class AlbumAdmin(admin.ModelAdmin):
    list_display = ['title', 'description']
    inlines = [ImageInline]

class EventAdmin(admin.ModelAdmin):
    change_list_template = 'change_list.html'
    manage_view_template = 'create_lichess.html'
    def get_readonly_fields(self, request, obj=None):
        return []
        
    def get_urls(self):
        from django.conf.urls import url
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urls = [url(r'^lichess/$', wrap(self.lichess_view),name='%s_%s_lichess' % info)]
        super_urls = super(EventAdmin, self).get_urls()

        return urls + super_urls
    
    def lichess_view(self, request ):
        opts = event._meta
        event_form = LichessEventForm()
        if request.POST:
            date = request.POST.get('datetime_0')
            time = request.POST.get('datetime_1')
            tournament_datetime = datetime.datetime.strptime('%s %s'%(date,time), '%Y-%m-%d %H:%M:%S')
            tournament = create_arena_event(request.POST.get('name'), tournament_datetime, time = request.POST.get('time'), increment = request.POST.get('increment'),
            duration = request.POST.get('duration'))
            lichess_event = event(title=tournament['fullName'],date=tournament_datetime,link='https://lichess.org/tournament/'+tournament['id'], location='Lichess Online')
            lichess_event.save()
            self.message_user(request, "Created tournament at <a href='%s'>%s</a> "%(lichess_event.link, lichess_event.link))

        if not self.has_change_permission(request):
            raise PermissionDenied

        # do cool management stuff here

        preserved_filters = self.get_preserved_filters(request)
        form_url = request.build_absolute_uri()
        form_url = request.META.get('PATH_INFO', None)

        context = {
            'title': 'Create Lichess Tournament',
            'has_change_permission': self.has_change_permission(request),
            'opts': opts,
            #'errors': form.errors,
            'app_label': opts.app_label,
            #'original': obj,
            'form_url' : form_url,
            'event_form' : event_form,
        }

        return render(request, self.manage_view_template, context)



    

class NewsAdminForm(forms.ModelForm):
    title = forms.CharField(max_length=50)
    text = forms.CharField(max_length= 10000, widget = TinyMCE(attrs = {'rows' : '30', 'cols' : '100', 'content_style' : "color:#FFFF00", 'body_class': 'review', 'body_id': 'review',}), label='News')
    #synopsis = forms.CharField(max_length= 1000, widget = forms.Textarea(attrs = {'rows' : '1', 'cols' : '90'}))

    class Meta:
        fields = ('title', 'text', 'image')
        model = news

class NewsChangeAdminForm(forms.ModelForm):
    title = forms.CharField(max_length=50)
    text = forms.CharField(max_length= 10000, widget = TinyMCE(attrs = {'rows' : '30', 'cols' : '100', 'content_style' : "color:#FFFF00", 'body_class': 'review', 'body_id': 'review',}), label='News')
    author = forms.ModelChoiceField(queryset=User.objects.all())
    #synopsis = forms.CharField(max_length= 1000, widget = forms.Textarea(attrs = {'rows' : '1', 'cols' : '90'}))

    class Meta:
        fields = ('title', 'text', 'image')
        model = news

class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'author']
    list_filter = [ 'status' ]
    search_fields = [ 'title' ]

    actions = ['make_published']
    
    form = NewsAdminForm
    change_form = NewsChangeAdminForm

    def make_published(self, request, queryset):
        rows_updated = queryset.update(status='p')
        for obj in queryset:
            obj.status='p'
            obj.published_date = timezone.now()
            obj.save()
        if rows_updated == 1:
            message_bit = "1 news item was"
        else:
            message_bit = "%s news items were" % rows_updated
        self.message_user(request, "%s successfully marked as published." % message_bit)
    make_published.short_description = "Mark selected news items as published"
    make_published.allowed_permissions = ['publish']



    def has_publish_permission(self, request):
        """Does the user have the publish permission?"""
        opts = self.opts
        codename = get_permission_codename('publish', opts)
        return request.user.has_perm('%s.%s' % (opts.app_label, codename))

    def get_form(self, request, obj=None, **kwargs):
        """
        Use special form during foo creation
        """
        defaults = {}
        if obj is not None:
            defaults['form'] = self.change_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    def get_readonly_fields(self, request, obj=None):
        return []

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
            email_message = '''
            The news item %s by %s is awaiting approval
            -----------------
            %s
            -----------------
            Visit <a href="%s">%s</a> to approve
            '''%(obj.title, obj.author, obj.text, "link", "link")
            send_mail('%s awaiting approval'%(obj.title), email_message, 'contact@wallaseychessclub.uk', ['contact@wallaseychessclub.uk'], fail_silently=False)
        
        super(NewsAdmin, self).save_model(request, obj, form, change)


admin.site.register(htmlobject, HtmlObjectAdmin)
admin.site.register(news, NewsAdmin)
admin.site.register(event, EventAdmin)
admin.site.register(album, AlbumAdmin)
admin.site.register(simul)