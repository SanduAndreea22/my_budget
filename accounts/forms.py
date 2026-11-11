import re

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm

class UserRegistrationForm(UserCreationForm):
    # Django reads this message from the FORM, not from the password2 field.
    error_messages = {**UserCreationForm.error_messages, "password_mismatch": "The two passwords don't match."}

    email = forms.EmailField(required=True, error_messages={'required': 'Enter your email address.', 'invalid': 'That email address doesn\'t look right.'})

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'currency', 'password1', 'password2']

    # Essentials first; the optional name fields come last.
    field_order = ['email', 'password1', 'password2', 'currency', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'].help_text = "You can change this later in your profile."
        self.fields['first_name'].label = "First name (optional)"
        self.fields['last_name'].label = "Last name (optional)"
        self.fields['password1'].error_messages['required'] = "Choose a password."
        self.fields['password2'].label = "Confirm password"
        self.fields['password2'].help_text = ""
        self.fields['password2'].error_messages['required'] = "Type the password again."
        self.fields['currency'].error_messages['required'] = "Choose a currency."

    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in instead.")
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

class UserLoginForm(forms.Form):
    """Not based on AuthenticationForm — that form's field is hardcoded to
    be named/id'd "username" internally (Django framework requirement),
    which would leak into the rendered HTML even with the label changed to
    "Email". Login here is by email only, so the field is genuinely named
    "email" end to end."""

    email = forms.EmailField(widget=forms.EmailInput(
        attrs={'class': 'form-control', 'placeholder': 'you@example.com', 'autofocus': True}),
        label="Email", error_messages={'required': 'Enter your email address.'})

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        error_messages={'required': 'Enter your password.'})

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("That email and password don't match.", code='invalid_login')
        return cleaned_data

    def get_user(self):
        return self.user_cache

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'image', 'description', "currency"]
        labels = {'first_name': 'First name (optional)', 'last_name': 'Last name (optional)', 'image': 'Photo (optional)', 'description': 'About you (optional)'}
