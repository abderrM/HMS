from django.contrib.auth.models import User
from django.db import models
import uuid


class BaseModel(models.Model):
    uid = models.UUIDField(default=uuid.uuid4   , editable=False , primary_key=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering=['uid']
class Amenities(BaseModel):
    amenity_name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.amenity_name

class Hotel(BaseModel):
    hotel_name= models.CharField(max_length=100)
    hotel_price = models.IntegerField()
    description = models.TextField()
    amenities = models.ManyToManyField(Amenities)
    room_count = models.IntegerField(default=10)

    def __str__(self) -> str:
        return self.hotel_name


class HotelImages(BaseModel):
    hotel= models.ForeignKey(Hotel ,related_name="images", on_delete=models.CASCADE)
    images = models.ImageField(upload_to="hotels")



class HotelBooking(BaseModel):
    BOOKING_STATUS = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmé'),
        ('completed', 'Payé et Confirmé'),
        ('cancelled', 'Annulé')
    )
    
    PAYMENT_STATUS = (
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé')
    )

    PAYMENT_METHODS = (
        ('paypal', 'PayPal'),
        ('mastercard', 'Mastercard')
    )
    
    hotel = models.ForeignKey(Hotel, related_name="hotel_bookings", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="user_bookings", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    booking_type = models.CharField(max_length=100, choices=[('Pre Paid', 'Pre Paid'), ('Post Paid', 'Post Paid')])
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    room_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_bookings')
    verification_date = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.hotel.hotel_name} - {self.status}"

    def can_be_modified(self):
        return self.status == 'pending'

    def can_be_paid(self):
        return self.status == 'confirmed'

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('booking_status', 'Booking Status Change'),
        ('room_available', 'Room Available'),
        ('general', 'General Notification')
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    booking = models.ForeignKey(HotelBooking, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class Contact(models.Model):
    SUBJECT_CHOICES = [
        ('GENERAL', 'Question générale'),
        ('BOOKING', 'Problème de réservation'),
        ('PAYMENT', 'Problème de paiement'),
        ('TECHNICAL', 'Problème technique'),
        ('OTHER', 'Autre'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nom")
    email = models.EmailField(verbose_name="Email")
    subject = models.CharField(max_length=20, choices=SUBJECT_CHOICES, default='GENERAL', verbose_name="Sujet")
    message = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d'envoi")
    is_read = models.BooleanField(default=False, verbose_name="Lu")

    class Meta:
        verbose_name = "Message de contact"
        verbose_name_plural = "Messages de contact"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_subject_display()} - {self.created_at.strftime('%d/%m/%Y')}"