import os
import resend
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from .decorators import ratelimit_post, user_not_authenticated
from .emails import send_email_async
from .forms import PasswordResetRequestForm, UserRegistrationForm, UserLoginForm, UserUpdateForm
from .tokens import account_activation_token

User = get_user_model()

resend.api_key = os.environ.get('RESEND_API_KEY')
EMAIL_ENABLED = bool(resend.api_key)

@user_not_authenticated(redirect_url='dashboard')
@ratelimit_post('register', limit=5, period_seconds=3600)
def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            try:
                user.save()
            except IntegrityError:
                # Someone else registered the same email (or the same
                # derived username) in the tiny window between the form's
                # own uniqueness check and this save.
                form.add_error('email', 'An account with this email already exists.')
                return render(request, 'accounts/register.html', {'form': form})

            current_site = get_current_site(request)
            mail_subject = 'Welcome to MyBudget'


            html_message = render_to_string('accounts/activation_email.html', {
                'user': user,
                'domain': current_site.domain,
                'scheme': 'https' if request.is_secure() else 'http',
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })

            # NOTE: "onboarding@resend.dev" is Resend's shared sandbox sender
            # — it only reaches the account's own verified address, not real
            # users. Sending real activation email in production needs a
            # verified sending domain + a real RESEND_API_KEY, which is a
            # Resend account/config change, not something fixable from this
            # codebase alone.
            send_email_async(user.email, mail_subject, html_message)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.username}! Your account is ready.')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

@user_not_authenticated(redirect_url='dashboard')
@ratelimit_post('login', limit=10, period_seconds=300)
def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome, {user.username}!')
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials or inactive account.')
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form, 'password_reset_available': EMAIL_ENABLED})

@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, 'You have successfully logged out!')
    return redirect('accounts:login')

@login_required
def profile_view(request, username):
    if request.user.username != username:
        messages.error(request, "You can't view someone else's profile.")
        return redirect('accounts:profile', username=request.user.username)

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('accounts:profile', username=request.user.username)
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, "Your account has been activated and you are now logged in!")
        return redirect('accounts:profile', username=user.username)
    else:
        messages.error(request, "Activation link is invalid!")
        return redirect('accounts:login')

@user_not_authenticated(redirect_url='dashboard')
@ratelimit_post('password_reset', limit=5, period_seconds=3600)
def password_reset_request_view(request):
    if not EMAIL_ENABLED:
        messages.error(request, "Password reset by email isn't set up yet — contact us directly for help.")
        return redirect('accounts:login')

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                current_site = get_current_site(request)
                html_message = render_to_string('accounts/password_reset_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'scheme': 'https' if request.is_secure() else 'http',
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                })
                send_email_async(user.email, 'Reset your MyBudget password', html_message)

            # Same message whether or not the email is registered, so this
            # page can't be used to check which emails have an account.
            messages.success(request, "If that email is registered, we've sent a password reset link.")
            return redirect('accounts:login')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'accounts/password_reset.html', {'form': form})

def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "This password reset link is invalid or has expired.")
        return redirect('accounts:password_reset')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your password has been reset. You can log in now.")
            return redirect('accounts:login')
    else:
        form = SetPasswordForm(user)

    return render(request, 'accounts/password_reset_confirm.html', {'form': form})
