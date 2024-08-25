from django import forms
from apps.sims.models import Sims

class AddSims(forms.Form):
        class Meta:
            model = Sims
            fields = ['__all__']