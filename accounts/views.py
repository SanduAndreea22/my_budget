from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from budget.starter import create_starter_data
from .decorators import ratelimit_post, user_not_authenticated
from .demo import cleanup_old_demo_users, create_demo_user, end_demo_session
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
                form.add_error('email', 'An account with this email already exists. Try logging in instead.')
                return render(request, 'accounts/register.html', {'form': form})

            create_starter_data(user)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.first_name}! Your account is ready.' if user.first_name else 'Welcome! Your account is ready.')
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
            messages.success(request, f'Welcome back, {user.first_name}!' if user.first_name else 'Welcome back!')
            return redirect('dashboard')
    else:
        form = UserLoginForm()
    return render(request, 'accounts/login.html', {'form': form})

@require_POST
def logout_view(request):
    was_demo = request.user.is_authenticated and request.user.is_demo
    if was_demo:
        end_demo_session(request)
        messages.success(request, 'Demo ended. The example data was deleted.')
        return redirect('home')
    logout(request)
    messages.success(request, 'You are logged out.')
    return redirect('accounts:login')


@ratelimit_post('demo', limit=20, period_seconds=3600)
def demo_start_view(request):
    """Create a temporary account with example data and sign the visitor in."""
    if request.method != 'POST':
        return redirect('home')
    if request.user.is_authenticated:
        return redirect('dashboard')
    cleanup_old_demo_users()
    user = create_demo_user()
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, "Welcome to the demo.")
    return redirect('dashboard')

@login_required
def profile_view(request, username):
    if request.user.username != username:
        messages.error(request, "You can't view someone else's profile.")
        return redirect('accounts:profile', username=request.user.username)

    if request.method == 'POST' and request.user.is_demo:
        messages.error(request, "Profile changes are turned off in the demo. Create an account to set up your own.")
        return redirect('accounts:profile', username=request.user.username)

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile', username=request.user.username)
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
@ratelimit_post('delete_account', limit=5, period_seconds=3600)
def delete_account_view(request):
    """Self-service account deletion: the account and everything in it, after confirming the password."""
    user = request.user
    if user.is_demo:
        messages.info(request, "Demo accounts are deleted automatically when you leave.")
        return redirect('dashboard')

    if request.method == 'POST':
        if user.check_password(request.POST.get('password', '')):
            if user.image:
                user.image.delete(save=False)  # the uploaded avatar file too
            logout(request)
            user.delete()  # CustomUser.delete() clears protected rows, then cascades the rest
            messages.success(request, "Your account and all its data were deleted.")
            return redirect('home')
        messages.error(request, "That password isn't right, so nothing was deleted.")
    return render(request, 'accounts/delete_account.html')
