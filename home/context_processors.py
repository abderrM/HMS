from .models import Notification, HotelBooking
from django.utils import timezone

def unread_notifications(request):
    if request.user.is_authenticated:
        # Forcer le rafraîchissement des données
        unread_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).count()
        
        # Mettre à jour la session avec le nombre de notifications non lues
        request.session['unread_notifications_count'] = unread_count
        
        return {
            'unread_notifications_count': unread_count
        }
    return {} 