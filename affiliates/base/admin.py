from django.contrib import admin
from django.db import models

from django_browserid.admin import BrowserIDAdminSite
from form_utils.widgets import ImageWidget

from affiliates.base.models import NewsItem, NewsItemTranslation


class AffiliatesAdminSite(BrowserIDAdminSite):
    include_password_form = True


class BaseModelAdmin(admin.ModelAdmin):
    """Base class for ModelAdmins used across the site."""
    formfield_overrides = {models.ImageField: {'widget': ImageWidget}}


class NewsItemTranslationInline(admin.TabularInline):
    model = NewsItemTranslation
    fields = ('locale', 'title', 'html')
    extra = 0


class NewsItemModelAdmin(BaseModelAdmin):
    list_display = ('title', 'author', 'visible', 'created', 'modified')
    fields = ('title', 'visible', 'created', 'modified', 'html')
    readonly_fields = ('author', 'created', 'modified')
    search_fields = ('title', 'html')
    inlines = (NewsItemTranslationInline,)

    def save_model(self, request, obj, form, change):
        """Record the author when a news item is created."""
        if obj.pk is None:
            obj.author = request.user
        super(NewsItemModelAdmin, self).save_model(request, obj, form, change)


admin_site = AffiliatesAdminSite()
admin_site.register(NewsItem, NewsItemModelAdmin)
