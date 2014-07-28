from django.contrib import admin

from affiliates.base.admin import BaseModelAdmin
from affiliates.links.models import FraudAction, Link


class LinkAdmin(BaseModelAdmin):
    list_display = ('banner', 'banner_type', 'banner_variation', 'user_name', 'user_email',
                    'link_clicks', 'created')
    search_fields = ('id', 'user__userprofile__display_name', 'user__email')

    def user_name(self, link):
        return link.user.display_name

    def user_email(self, link):
        return link.user.email

    def banner_type(self, link):
        if link.is_image_link:
            return 'Image Link'
        elif link.is_text_link:
            return 'Text Link'
        elif link.is_upgrade_link:
            return 'Upgrade Link'
        else:
            return 'Unknown'

    def banner_variation(self, link):
        return link.banner_variation
    banner_variation.allow_tags = True


class FraudActionAdmin(BaseModelAdmin):
    list_display = ('banner_name', 'user_name', 'action_description', 'executed_on', 'reason',
                    'reversed_on')
    readonly_fields = ('datapoint', 'count', 'metric', 'reason', 'executed_on', 'reversed_on')
    actions = ['reverse_actions']

    def banner_name(self, action):
        return action.datapoint.link.banner.name

    def user_name(self, action):
        return action.datapoint.link.user.display_name

    def action_description(self, action):
        return unicode(action.count) + ' ' + action.metric

    def reverse_actions(self, request, queryset):
        for action in queryset:
            try:
                action.reverse()
            except RuntimeError:
                msg = 'Error reversing action {0}: It has already been reversed.'.format(action.id)
                self.message_user(request, msg, 'error')
        self.message_user(request, 'Actions have been reversed.', 'info')
    reverse_actions.short_description = 'Reverse selected actions'


admin.site.register(Link, LinkAdmin)
admin.site.register(FraudAction, FraudActionAdmin)
