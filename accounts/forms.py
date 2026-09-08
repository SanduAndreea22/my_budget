import re

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(help_text='Enter a valid email address.', required=True)

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'currency', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'].help_text = "You can change this later in your profile."

    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    @staticmethod
    def _unique_username_from_email(email):
        """Sign-up is email-only — username is kept internally (profile URLs,
        avatar folder, admin) but never typed by the user, so derive one
        from the email's local part and de-dupe with a numeric suffix."""
        User = get_user_model()
        base = re.sub(r'[^\w.@+-]', '', email.split('@')[0]).lower() or 'user'
        username = base
        suffix = 1
        while User.objects.filter(username__iexact=username).exists():
            suffix += 1
            username = f"{base}{suffix}"
        return username

    def save(self, commit=True):
        user = super(UserRegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self._unique_username_from_email(user.email)
        if commit:
            user.save()
        return user

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(
        attrs={'class': 'form-control', 'placeholder': 'you@example.com', 'autofocus': True}),
        label="Email*")

    password = forms.CharField(widget=forms.PasswordInput(
        attrs={'class': 'form-control', 'placeholder': 'Password'}))

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'image', 'description', "currency"]
