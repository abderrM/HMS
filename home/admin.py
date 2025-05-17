from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from .models import Hotel, HotelImages, HotelBooking, Contact
from django.utils import timezone

class HotelImagesInline(admin.TabularInline):
    model = HotelImages
    extra = 5  # Augmenter le nombre de formulaires d'images vides
    max_num = 10  # Limiter le nombre maximum d'images
    fields = ('images',)  # Simplifier les champs affichés
    can_delete = True  # Permettre la suppression des images

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('hotel_name', 'hotel_price', 'room_count', 'created_at', 'updated_at')
    search_fields = ('hotel_name', 'description')
    list_filter = ('hotel_price', 'room_count', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [HotelImagesInline]
    
    # Organiser les champs du formulaire
    fieldsets = (
        ('Informations de base', {
            'fields': ('hotel_name', 'hotel_price', 'room_count', 'description')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(HotelImages)
class HotelImagesAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('hotel__hotel_name',)

@admin.register(HotelBooking)
class HotelBookingAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'user', 'start_date', 'end_date', 'booking_type', 'status', 'room_verified', 'verified_by', 'verification_date', 'created_at')
    list_display_links = ('hotel', 'user')
    search_fields = ('hotel__hotel_name', 'user__username', 'user__email')
    list_filter = (
        'status',
        'booking_type',
        'room_verified',
        ('start_date', admin.DateFieldListFilter),
        ('end_date', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    )
    readonly_fields = ('created_at', 'updated_at', 'verification_date', 'verified_by')
    list_editable = ('status', 'room_verified')
    actions = ['mark_as_verified', 'mark_as_confirmed', 'mark_as_cancelled', 'mark_as_completed']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('hotel', 'user', 'start_date', 'end_date', 'booking_type', 'status')
        }),
        ('Verification Details', {
            'fields': ('room_verified', 'verified_by', 'verification_date'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(
            room_verified=True,
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{updated} bookings were marked as verified.')
    mark_as_verified.short_description = "Mark selected bookings as verified"
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(
            status='confirmed',
            room_verified=True,
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{updated} bookings were marked as confirmed and verified.')
    mark_as_confirmed.short_description = "Mark selected bookings as confirmed"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} bookings were marked as cancelled.')
    mark_as_cancelled.short_description = "Mark selected bookings as cancelled"
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} bookings were marked as completed.')
    mark_as_completed.short_description = "Mark selected bookings as completed"
    
    def save_model(self, request, obj, form, change):
        if change:  # Only for existing objects
            # If status is being changed to confirmed
            if 'status' in form.changed_data:
                if obj.status == 'confirmed':
                    obj.room_verified = True
                    obj.verified_by = request.user
                    obj.verification_date = timezone.now()
                elif obj.status in ['pending', 'cancelled']:
                    obj.room_verified = False
                    obj.verified_by = None
                    obj.verification_date = None
            
            # If room_verified is being changed
            if 'room_verified' in form.changed_data:
                if obj.room_verified:
                    obj.status = 'confirmed'
                    obj.verified_by = request.user
                    obj.verification_date = timezone.now()
                else:
                    obj.status = 'pending'
                    obj.verified_by = None
                    obj.verification_date = None
        
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hotel', 'user', 'verified_by')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at', 'is_read')
    list_filter = ('subject', 'is_read', 'created_at')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Marquer comme lu"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Marquer comme non lu"
    
    actions = ['mark_as_read', 'mark_as_unread']