from django import forms

from .models import FeedbackMessage


class ContactForm(forms.ModelForm):
    # Honeypot: real people never see or fill this; bots usually do.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = FeedbackMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Your name (optional)", "maxlength": 80}),
            "email": forms.EmailInput(attrs={"placeholder": "Your email, only if you want a reply"}),
            "message": forms.Textarea(attrs={"placeholder": "What's on your mind? A bug, an idea, a question…", "rows": 6, "maxlength": 2000}),
        }

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError("Please write at least a few words (10 characters).")
        return message
