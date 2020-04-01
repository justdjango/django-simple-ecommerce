from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={
        'placeholder': "Your name"
    }))
    email = forms.EmailField(widget=forms.TextInput(attrs={
        'placeholder': "Your e-mail"
    }))
    message = forms.CharField(widget=forms.Textarea(attrs={
        'placeholder': 'Your message'
    }))
