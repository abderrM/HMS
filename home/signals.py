from django.db.models.signals import post_save, pre_save
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import HotelBooking, Notification
from django.contrib import messages

@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Signal to handle user logout"""
    if request:
        messages.success(request, 'log out successfully.')

@receiver(pre_save, sender=HotelBooking)
def store_old_values(sender, instance, **kwargs):
    if instance.pk:  # Only for existing instances
        try:
            old_instance = HotelBooking.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            instance._old_room_verified = old_instance.room_verified
        except HotelBooking.DoesNotExist:
            pass

@receiver(post_save, sender=HotelBooking)
def create_booking_status_notification(sender, instance, created, **kwargs):
    if not created:  # Only send notification for status changes, not new bookings
        old_status = instance._old_status if hasattr(instance, '_old_status') else None
        old_room_verified = instance._old_room_verified if hasattr(instance, '_old_room_verified') else None
        
        # Handle room verification notification
        if old_room_verified != instance.room_verified and instance.room_verified:
            Notification.objects.create(
                user=instance.user,
                title=f"Chambre vérifiée - {instance.hotel.hotel_name}",
                message=f"Votre chambre à l'hôtel {instance.hotel.hotel_name} a été vérifiée par l'administrateur. Votre réservation est maintenant confirmée. Vous pouvez procéder au paiement.",
                notification_type='booking_status',
                booking=instance
            )
        
        # Handle status change notification
        if old_status != instance.status:
            status_messages = {
                'pending': "Votre réservation est en attente de confirmation par l'administrateur.",
                'confirmed': "Votre réservation a été confirmée. Vous pouvez maintenant procéder au paiement.",
                'completed': "Votre réservation a été marquée comme payée et complétée. Merci de votre confiance!",
                'cancelled': "Votre réservation a été annulée. Contactez le support si vous avez des questions."
            }
            
            Notification.objects.create(
                user=instance.user,
                title=f"Statut de réservation mis à jour - {instance.hotel.hotel_name}",
                message=f"Le statut de votre réservation à l'hôtel {instance.hotel.hotel_name} a été modifié de '{old_status}' à '{instance.status}'. {status_messages.get(instance.status, '')}",
                notification_type='booking_status',
                booking=instance
            )

            # If the booking is cancelled or completed, notify other users about room availability
            if instance.status in ['cancelled', 'completed']:
                # Get all pending bookings for the same hotel and date range
                pending_bookings = HotelBooking.objects.filter(
                    hotel=instance.hotel,
                    status='pending',
                    start_date__gte=instance.start_date,
                    end_date__lte=instance.end_date
                ).exclude(user=instance.user)

                for booking in pending_bookings:
                    Notification.objects.create(
                        user=booking.user,
                        title=f"Chambre disponible - {instance.hotel.hotel_name}",
                        message=f"Une chambre est devenue disponible pour les dates que vous avez demandées ({booking.start_date} au {booking.end_date}). Votre réservation pourrait être confirmée prochainement.",
                        notification_type='room_available',
                        booking=booking
                    ) 