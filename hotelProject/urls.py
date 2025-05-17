"""hotel URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from home import views


   

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('home.urls')),
     path('accounts/', include('allauth.urls')),
    path('auth/', include('allauth.socialaccount.urls')),
    path('mes-reservations/', views.user_bookings, name='user_bookings'),
    path('cancel-booking/<str:booking_uid>/', views.cancel_booking, name='cancel_booking'),
    path('update-booking/<str:booking_uid>/', views.update_booking, name='update_booking'),
    path('update-booking-status/<str:booking_uid>/', views.update_booking_status, name='update_booking_status'),
    path('process-payment/<str:booking_uid>/', views.process_payment, name='process_payment'),
    path('create-paypal-order/<str:booking_uid>/', views.create_paypal_order, name='create_paypal_order'),
    path('create-stripe-session/<str:booking_uid>/', views.create_stripe_session, name='create_stripe_session'),
    path('payment-success/<str:booking_uid>/<str:provider>/', views.payment_success, name='payment_success'),
    path('payment-cancel/<str:booking_uid>/', views.payment_cancel, name='payment_cancel'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "Administration Hôtel"
admin.site.site_title = "Portail Administrateur"
admin.site.index_title = "Bienvenue dans le portail d'administration"
