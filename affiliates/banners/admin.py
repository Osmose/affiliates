from django.contrib import admin
from django.db.models import ImageField

from form_utils.widgets import ImageWidget
from mptt.admin import MPTTModelAdmin

from affiliates.banners import models
from affiliates.base.admin import BaseModelAdmin


class CategoryModelAdmin(MPTTModelAdmin):
    list_display = ('name', 'link_clicks')


class ImageVariationInline(admin.TabularInline):
    model = models.ImageBannerVariation
    fields = ('color', 'locale', 'image')
    extra = 0


class ImageBannerModelAdmin(BaseModelAdmin):
    list_display = ('name', 'category', 'destination', 'visible')
    fields = ('name', 'category', 'destination', 'visible', 'created', 'modified')
    readonly_fields = ('created', 'modified')
    search_fields = ('name', 'destination', 'category__name')
    inlines = (ImageVariationInline,)


class TextVariationInline(admin.TabularInline):
    model = models.TextBannerVariation
    fields = ('locale', 'text')
    extra = 0


class TextBannerModelAdmin(BaseModelAdmin):
    list_display = ('name', 'category', 'visible', 'destination')
    fields = ('name', 'category', 'visible', 'destination', 'created', 'modified')
    readonly_fields = ('created', 'modified')
    search_fields = ('name', 'destination', 'category__name')
    inlines = (TextVariationInline,)


class FirefoxUpgradeBannerVariationInline(admin.TabularInline):
    model = models.FirefoxUpgradeBannerVariation
    fields = ('color', 'locale', 'image', 'upgrade_image')
    formfield_overrides = {ImageField: {'widget': ImageWidget}}
    extra = 0


class FirefoxUpgradeBannerModelAdmin(BaseModelAdmin):
    list_display = ('name', 'category', 'destination', 'visible')
    fields = ('name', 'category', 'destination', 'visible', 'created', 'modified')
    readonly_fields = ('created', 'modified')
    search_fields = ('name', 'destination', 'category__name')
    inlines = (FirefoxUpgradeBannerVariationInline,)


admin.site.register(models.Category, CategoryModelAdmin)
admin.site.register(models.ImageBanner, ImageBannerModelAdmin)
admin.site.register(models.TextBanner, TextBannerModelAdmin)
admin.site.register(models.FirefoxUpgradeBanner, FirefoxUpgradeBannerModelAdmin)
