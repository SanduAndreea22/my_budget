from django import forms

from .models import FeedbackMessage


class ContactForm(forms.ModelForm):
    # Honeypot: real people never see or fill this; bots usually do.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = FeedbackMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 80}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "message": forms.Textarea(attrs={"rows": 6, "maxlength": 2000}),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write a little more, at least 10 characters.")
        return message
