from django import template

register = template.Library()

@register.filter
def unread_count(notifications):
    return notifications.filter(is_read=False).count() 