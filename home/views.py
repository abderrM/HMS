from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, logout, login
from django.contrib import messages
from django.contrib.auth.models import User
from .models import *
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
import json
from django.conf import settings
import stripe
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest
import uuid
from django.views.decorators.csrf import csrf_exempt


def check_booking(uid, room_count, start_date, end_date):
    qs = HotelBooking.objects.filter(hotel__uid=uid)
    # qs1 = qs.filter(
    #     start_date__gte=start_date,
    #     end_date__lte=end_date,
    # )
    # qs2 = qs.filter(
    #     start_date__lte=start_date,
    #     end_date__gte=end_date,
    # )

    qs = qs.filter(
        Q(start_date__gte=start_date,
          end_date__lte=end_date)
        | Q(start_date__lte=start_date,
            end_date__gte=end_date)
    )
    # qs = qs1|qs2

    if len(qs) >= room_count:
        return False
    return True


def index(request):
    amenities = Amenities.objects.all()
    hotels = Hotel.objects.all()
    total_hotels = len(hotels)  
    selected_amenities = request.GET.getlist('selectAmenity')
    sort_by = request.GET.get('sortSelect')
    search = request.GET.get('searchInput')
    startdate = request.GET.get('startDate')
    enddate = request.GET.get('endDate')
    price = request.GET.get('price')

    if selected_amenities != []:
        hotels = hotels.filter(
            amenities__amenity_name__in=selected_amenities).distinct()
    if search:
        hotels = hotels.filter(Q(hotel_name__icontains=search)
                               | Q(description__icontains=search) | Q(amenities__amenity_name__contains=search))
        
    if sort_by:
        if sort_by == 'low_to_high':
            hotels = hotels.order_by('hotel_price')
        elif sort_by == 'high_to_low':
            hotels = hotels.order_by('-hotel_price')
    if price:
        hotels = hotels.filter(hotel_price__lte=int(price))

    if startdate and enddate:
        unbooked_hotels = []
        for i in hotels:
            valid = check_booking(i.uid, i.room_count, startdate, enddate)
            if valid:
                unbooked_hotels.append(i)
        hotels = unbooked_hotels
    hotels = hotels.distinct()

    date = datetime.today().strftime('%Y-%m-%d')

    context = {
        'amenities': amenities, 
        'hotels': hotels, 
        'sort_by': sort_by,
        'search': search, 
        'selected_amenities': selected_amenities, 
        'max_price': price, 
        'startdate': startdate, 
        "enddate": enddate, 
        "date": date,
        'total_hotels': total_hotels
    }
    return render(request, 'home/index.html', context)


def signout(request):
    logout(request)
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('/')


def hotel_detail(request, hotel_uid):
    hotel = Hotel.objects.get(uid=hotel_uid)
    context = {'hotel': hotel}
    context['date'] = datetime.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        checkin = request.POST.get('startDate')
        checkout = request.POST.get('endDate')
        context['startdate'] = checkin
        context['enddate'] = checkout

        try:
            # Vérifier la disponibilité
            valid = check_booking(hotel.uid, hotel.room_count, checkin, checkout)
            if not valid:
                messages.error(request, 'Booking for these days are full')
                return render(request, 'home/hotel.html', context)

            # Calculer le montant total
            start_date = datetime.strptime(checkin, '%Y-%m-%d').date()
            end_date = datetime.strptime(checkout, '%Y-%m-%d').date()
            days = (end_date - start_date).days
            total_amount = days * hotel.hotel_price

            print(f"Debug - Création réservation:")
            print(f"Date début: {start_date}")
            print(f"Date fin: {end_date}")
            print(f"Nombre de jours: {days}")
            print(f"Prix par nuit: {hotel.hotel_price}")
            print(f"Montant total: {total_amount}")

            # Créer la réservation
            booking = HotelBooking.objects.create(
                hotel=hotel, 
                user=request.user, 
                start_date=start_date,
                end_date=end_date, 
                booking_type='Pre Paid',
                total_amount=total_amount,
                status='pending',
                payment_status='pending'
            )

            # Créer une notification pour l'administrateur
            Notification.objects.create(
                user=request.user,
                title='Nouvelle réservation',
                message=f'Votre réservation pour {hotel.hotel_name} a été créée et est en attente de confirmation.',
                notification_type='booking_created'
            )

            messages.success(request, f'Réservation créée avec succès! Vous recevrez une notification une fois la réservation confirmée.')
            return redirect('booking_detail', booking_uid=booking.uid)
            
        except Exception as e:
            print(f"Erreur lors de la création de la réservation: {str(e)}")
            messages.error(request, 'Une erreur est survenue lors de la réservation. Veuillez réessayer.')
            return render(request, 'home/hotel.html', context)
        
    return render(request, 'home/hotel.html', context)


def aboutus(request):
    return render(request, 'home/about_us.html')


@login_required
def contactus(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        if name and email and subject and message:
            Contact.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message
            )
            messages.success(request, 'Votre message a été envoyé avec succès. Nous vous répondrons dans les plus brefs délais.')
            return redirect('contactus')
        else:
            messages.error(request, 'Veuillez remplir tous les champs du formulaire.')
    
    # Pré-remplir les informations de l'utilisateur
    context = {
        'subject_choices': Contact.SUBJECT_CHOICES,
        'user_full_name': request.user.get_full_name() or request.user.username,
        'user_email': request.user.email
    }
    return render(request, 'home/contactus.html', context)


def booking(request, hotel_uid):
    hotel = Hotel.objects.get(uid=hotel_uid)
    context = {'hotel': hotel}
    context['date'] = datetime.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        checkin = request.POST.get('startDate')
        checkout = request.POST.get('endDate')
        context['startdate'] = checkin
        context['enddate'] = checkout

        try:
            valid = check_booking(hotel.uid, hotel.room_count, checkin, checkout)
            if not valid:
                messages.error(request, 'Booking for these days are full')
                return render(request, 'home/booking.html', context)
        except:
            messages.error(request, 'Please Enter Valid Date Data')
            return render(request, 'home/booking.html', context)
        
        HotelBooking.objects.create(
            hotel=hotel, 
            user=request.user, 
            start_date=checkin,
            end_date=checkout, 
            booking_type='Pre Paid'
        )
        messages.success(request, f'{hotel.hotel_name} Booked successfully!')
        return render(request, 'home/booking.html', context)
    return render(request, 'home/booking.html', context)


def booking_detail(request, booking_uid):
    booking = HotelBooking.objects.get(uid=booking_uid)
    context = {'booking': booking}
    return render(request, 'home/booking_detail.html', context)


@login_required
def notifications(request):
    try:
        # Forcer le rechargement des données de l'utilisateur
        request.user.refresh_from_db()
        
        # Récupérer toutes les notifications de l'utilisateur avec les relations
        user_notifications = Notification.objects.select_related(
            'booking', 
            'booking__hotel'
        ).filter(
            user=request.user
        ).order_by('-created_at')
        
        # Calculer le nombre de notifications non lues
        unread_count = user_notifications.filter(is_read=False).count()
        
        context = {
            'notifications': user_notifications,
            'unread_count': unread_count
        }
        return render(request, 'home/notifications.html', context)
    except Exception as e:
        messages.error(request, "Une erreur s'est produite lors du chargement de vos notifications.")
        return redirect('index')


@login_required
def mark_notification_as_read(request, notification_id):
    notification = Notification.objects.get(id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('notifications')


@login_required
def mark_all_notifications_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')


def is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
@user_passes_test(is_admin)
def manage_bookings(request):
    bookings = HotelBooking.objects.all().select_related('hotel', 'user', 'verified_by').order_by('-created_at')
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        bookings = bookings.filter(status=status)
    
    # Filter by booking type
    booking_type = request.GET.get('booking_type')
    if booking_type:
        bookings = bookings.filter(booking_type=booking_type)
    
    # Filter by verification status
    verified = request.GET.get('verified')
    if verified:
        bookings = bookings.filter(room_verified=(verified == 'true'))
    
    # Handle bulk actions
    if request.method == 'POST':
        action = request.POST.get('action')
        selected_bookings = request.POST.getlist('selected_bookings')
        
        if selected_bookings:
            if action == 'verify':
                HotelBooking.objects.filter(uid__in=selected_bookings).update(
                    room_verified=True,
                    verified_by=request.user,
                    verification_date=timezone.now()
                )
                messages.success(request, 'Selected bookings have been verified.')
            elif action == 'confirm':
                HotelBooking.objects.filter(uid__in=selected_bookings).update(
                    status='confirmed',
                    room_verified=True,
                    verified_by=request.user,
                    verification_date=timezone.now()
                )
                messages.success(request, 'Selected bookings have been confirmed and verified.')
            elif action == 'cancel':
                HotelBooking.objects.filter(uid__in=selected_bookings).update(status='cancelled')
                messages.success(request, 'Selected bookings have been cancelled.')
            elif action == 'complete':
                HotelBooking.objects.filter(uid__in=selected_bookings).update(status='completed')
                messages.success(request, 'Selected bookings have been marked as completed.')
    
    context = {
        'bookings': bookings,
        'status_choices': HotelBooking.BOOKING_STATUS,
        'booking_type_choices': [('Pre Paid', 'Pre Paid'), ('Post Paid', 'Post Paid')],
        'current_status': status,
        'current_booking_type': booking_type,
        'current_verified': verified,
    }
    
    return render(request, 'home/manage_bookings.html', context)

@login_required
def user_bookings(request):
    try:
        # Forcer le rechargement des données de l'utilisateur
        request.user.refresh_from_db()
        
        # Récupérer toutes les réservations de l'utilisateur avec les relations
        user_bookings = HotelBooking.objects.select_related(
            'hotel', 
            'verified_by'
        ).prefetch_related(
            'hotel__images'
        ).filter(
            user=request.user
        ).order_by('-created_at')
        
        context = {
            'user_bookings': user_bookings,
            'today': datetime.today().date()
        }
        return render(request, 'home/user_bookings.html', context)
    except Exception as e:
        messages.error(request, "Une erreur s'est produite lors du chargement de vos réservations.")
        return redirect('index')

@login_required
def cancel_booking(request, booking_uid):
    if request.method == 'POST':
        try:
            booking = HotelBooking.objects.get(uid=booking_uid, user=request.user)
            if booking.status == 'pending' and not booking.room_verified:
                booking.status = 'cancelled'
                booking.save()
                messages.success(request, 'Réservation annulée avec succès.')
                return JsonResponse({'success': True})
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Cette réservation ne peut plus être annulée.'
                })
        except HotelBooking.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Réservation non trouvée.'
            })
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'})

@login_required
def update_booking(request, booking_uid):
    if request.method == 'POST':
        try:
            booking = HotelBooking.objects.get(uid=booking_uid, user=request.user)
            
            if not booking.status == 'pending' or booking.room_verified:
                return JsonResponse({
                    'success': False,
                    'error': 'Cette réservation ne peut plus être modifiée.'
                })

            data = json.loads(request.body)
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()

            # Vérifier la disponibilité pour les nouvelles dates
            if not check_booking(booking.hotel.uid, booking.hotel.room_count, start_date, end_date):
                return JsonResponse({
                    'success': False,
                    'error': 'Ces dates ne sont pas disponibles.'
                })

            # Calculer le nouveau montant total
            days = (end_date - start_date).days
            total_amount = days * booking.hotel.hotel_price

            booking.start_date = start_date
            booking.end_date = end_date
            booking.total_amount = total_amount
            booking.save()

            messages.success(request, 'Dates de réservation mises à jour avec succès.')
            return JsonResponse({'success': True})

        except HotelBooking.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Réservation non trouvée.'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Données invalides.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'})

# Configuration PayPal
paypal_client_id = settings.PAYPAL_CLIENT_ID
paypal_client_secret = settings.PAYPAL_CLIENT_SECRET
environment = SandboxEnvironment(client_id=paypal_client_id, client_secret=paypal_client_secret)
paypal_client = PayPalHttpClient(environment)

# Configuration Stripe (Mastercard)
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def process_payment(request, booking_uid):
    booking = get_object_or_404(HotelBooking, uid=booking_uid, user=request.user)
    if not booking.room_verified:
        messages.error(request, 'La réservation doit être vérifiée avant le paiement.')
        return redirect('booking_detail', booking_uid=booking_uid)
    if booking.payment_status == 'completed':
        messages.info(request, 'Cette réservation a déjà été payée.')
        return redirect('booking_detail', booking_uid=booking_uid)
    # Recalculer le montant total
    start_date = booking.start_date
    end_date = booking.end_date
    days = (end_date - start_date).days
    if days <= 0:
        messages.error(request, "La date de départ doit être postérieure à la date d'arrivée.")
        return redirect('booking_detail', booking_uid=booking_uid)
    booking.total_amount = days * booking.hotel.hotel_price
    booking.save()
    print(f"Debug - Calcul du montant:")
    print(f"Prix par nuit: {booking.hotel.hotel_price}")
    print(f"Nombre de nuits: {days}")
    print(f"Montant total: {booking.total_amount}")
    context = {
        'booking': booking,
        'paypal_client_id': paypal_client_id,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        'days': days,
        'price_per_night': booking.hotel.hotel_price
    }
    return render(request, 'home/payment.html', context)

@login_required
def create_paypal_order(request, booking_uid):
    booking = get_object_or_404(HotelBooking, uid=booking_uid, user=request.user)
    
    order_request = OrdersCreateRequest()
    order_request.prefer('return=representation')
    
    order_request.request_body({
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(booking.uid),
            "amount": {
                "currency_code": "EUR",
                "value": str(booking.total_amount)
            },
            "description": f"Réservation pour {booking.hotel.hotel_name}"
        }],
        "application_context": {
            "return_url": request.build_absolute_uri(f'/payment-success/{booking.uid}/paypal/'),
            "cancel_url": request.build_absolute_uri(f'/payment-cancel/{booking.uid}/')
        }
    })
    
    try:
        response = paypal_client.execute(order_request)
        return JsonResponse({
            'order_id': response.result.id,
            'approval_url': next(link.href for link in response.result.links if link.rel == "approve")
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def create_stripe_session(request, booking_uid):
    booking = get_object_or_404(HotelBooking, uid=booking_uid, user=request.user)
    
    if not booking.room_verified:
        return JsonResponse({
            'error': 'La réservation doit être vérifiée avant le paiement.'
        }, status=400)
    
    if booking.payment_status == 'completed':
        return JsonResponse({
            'error': 'Cette réservation a déjà été payée.'
        }, status=400)
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'unit_amount': int(float(booking.total_amount) * 100),  # Stripe utilise les centimes
                    'product_data': {
                        'name': f'Réservation - {booking.hotel.hotel_name}',
                        'description': f'Du {booking.start_date} au {booking.end_date}',
                        'images': [request.build_absolute_uri(image.images.url) for image in booking.hotel.images.all()[:1]],
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.build_absolute_uri(f'/payment-success/{booking.uid}/stripe/'),
            cancel_url=request.build_absolute_uri(f'/payment-cancel/{booking.uid}/'),
            client_reference_id=str(booking.uid),
            customer_email=request.user.email,
            metadata={
                'booking_id': str(booking.uid),
                'hotel_name': booking.hotel.hotel_name,
                'check_in': str(booking.start_date),
                'check_out': str(booking.end_date),
            }
        )
        return JsonResponse({'session_id': checkout_session.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def payment_success(request, booking_uid, provider):
    booking = get_object_or_404(HotelBooking, uid=booking_uid, user=request.user)
    
    if provider == 'paypal':
        order_id = request.GET.get('token')
        if order_id:
            capture_request = OrdersCaptureRequest(order_id)
            try:
                paypal_client.execute(capture_request)
                booking.payment_status = 'completed'
                booking.payment_method = 'paypal'
                booking.transaction_id = order_id
                booking.save()
                messages.success(request, 'Paiement PayPal effectué avec succès!')
            except Exception as e:
                messages.error(request, f'Erreur lors de la capture du paiement PayPal: {str(e)}')
    
    elif provider == 'stripe':
        session_id = request.GET.get('session_id')
        if session_id:
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                if session.payment_status == 'paid':
                    # Mettre à jour la réservation
                    booking.status = 'completed'
                    booking.payment_status = 'completed'
                    booking.payment_method = 'mastercard'
                    booking.transaction_id = session.payment_intent
                    booking.save()
                    
                    # Créer une notification
                    Notification.objects.create(
                        user=booking.user,
                        title='Paiement confirmé',
                        message=f'Votre paiement pour la réservation à {booking.hotel.hotel_name} a été confirmé.',
                        notification_type='booking_status',
                        booking=booking
                    )
                    
                    messages.success(request, 'Paiement effectué avec succès!')
            except Exception as e:
                messages.error(request, f'Erreur lors de la vérification du paiement: {str(e)}')
    
    return redirect('booking_detail', booking_uid=booking_uid)

@login_required
def payment_cancel(request, booking_uid):
    messages.warning(request, 'Le paiement a été annulé.')
    return redirect('booking_detail', booking_uid=booking_uid)

@login_required
@user_passes_test(is_admin)
def update_booking_status(request, booking_uid):
    if request.method == 'POST':
        try:
            booking = HotelBooking.objects.get(uid=booking_uid)
            new_status = request.POST.get('status')
            
            if new_status in dict(HotelBooking.BOOKING_STATUS):
                old_status = booking.status
                booking.status = new_status
                
                if new_status == 'confirmed':
                    booking.room_verified = True
                    booking.verified_by = request.user
                    booking.verification_date = timezone.now()
                
                booking.save()

                # Créer une notification pour l'utilisateur
                message = {
                    'confirmed': 'Votre réservation a été confirmée et vérifiée. Vous pouvez maintenant procéder au paiement.',
                    'completed': 'Votre réservation a été marquée comme payée.',
                    'cancelled': 'Votre réservation a été annulée.',
                }
                
                if new_status in message:
                    Notification.objects.create(
                        user=booking.user,
                        title=f'Statut de réservation mis à jour',
                        message=message[new_status],
                        notification_type='booking_status',
                        booking=booking
                    )

                return JsonResponse({
                    'success': True,
                    'message': f'Statut mis à jour de {old_status} à {new_status}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Statut invalide'
                })
        except HotelBooking.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Réservation non trouvée'
            })
    return JsonResponse({
        'success': False,
        'error': 'Méthode non autorisée'
    })

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        
        if event.type == 'checkout.session.completed':
            session = event.data.object
            booking_uid = session.client_reference_id
            
            try:
                booking = HotelBooking.objects.get(uid=booking_uid)
                booking.status = 'completed'
                booking.payment_status = 'completed'
                booking.payment_method = 'mastercard'
                booking.transaction_id = session.payment_intent
                booking.save()
                
                Notification.objects.create(
                    user=booking.user,
                    title='Paiement confirmé',
                    message=f'Votre paiement pour la réservation à {booking.hotel.hotel_name} a été confirmé.',
                    notification_type='booking_status',
                    booking=booking
                )
            except HotelBooking.DoesNotExist:
                return HttpResponse(status=404)
                
        return HttpResponse(status=200)
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
