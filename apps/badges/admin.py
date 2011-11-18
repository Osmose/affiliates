from django.contrib import admin

from funfactory.admin import site
from badges.models import BadgePreview, Category, Subcategory


class CategoryAdmin(admin.ModelAdmin):
    change_list_template = 'smuggler/change_list.html'
site.register(Category, CategoryAdmin)


class SubcategoryAdmin(admin.ModelAdmin):
    change_list_template = 'smuggler/change_list.html'
site.register(Subcategory, SubcategoryAdmin)


class BadgePreviewInline(admin.TabularInline):
    model = BadgePreview
    extra = 0
