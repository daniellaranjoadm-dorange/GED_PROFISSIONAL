from django import forms
from .models import SolicitarAcesso

class SolicitarAcessoForm(forms.ModelForm):
    class Meta:
        model = SolicitarAcesso
        fields = ["nome", "email", "setor", "motivo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "setor": forms.TextInput(attrs={"class": "form-control"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean_motivo(self):
        motivo = self.cleaned_data.get("motivo", "").strip()
        if len(motivo) < 10:
            raise forms.ValidationError("O motivo deve ter ao menos 10 caracteres.")
        return motivo