from django import template
from datetime import datetime

register = template.Library()

@register.filter
def days(end_date, start_date):
    """Calculate the number of days between two dates"""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    delta = end_date - start_date
    return delta.days 