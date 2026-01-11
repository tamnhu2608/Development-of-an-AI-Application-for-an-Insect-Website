
#from django import template
#from django.contrib.auth.models import Group

#register = template.Library()

#@register.filter
#def has_group(user, group_name):
#   return Group.objects.filter(name=group_name).exists() and user.groups.filter(name=group_name).exists()
from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter
def has_group(user, group_name):
    if user.is_authenticated:
        return user.groups.filter(name=group_name).exists()
    return False