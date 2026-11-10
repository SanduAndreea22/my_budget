from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from budget.starter import create_starter_data
from .decorators import ratelimit_post, user_not_authenticated
from .forms import UserRegistrationForm, UserLoginForm, UserUpdateForm

User = get_user_model()


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

            create_starter_data(user)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.first_name or user.username}! Your account is ready.')
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
            messages.success(request, f'Welcome, {user.first_name or user.username}!')
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials or inactive account.')
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

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
