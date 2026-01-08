from django import forms
from .models import SolicitacaoAcesso, UserConfig


# -----------------------------------------------------------
# 🔧 FORM DE CONFIGURAÇÕES DO USUÁRIO
# -----------------------------------------------------------
class UserConfigForm(forms.ModelForm):
    class Meta:
        model = UserConfig
        fields = ["tema", "animacoes", "notificacoes_email", "dashboard_expandido"]

        widgets = {
            "tema": forms.Select(attrs={"class": "form-select"}),
            "animacoes": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notificacoes_email": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "dashboard_expandido": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


# -----------------------------------------------------------
# 📩 FORM DE SOLICITAÇÃO DE ACESSO (PÚBLICO)
# -----------------------------------------------------------
class SolicitacaoAcessoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoAcesso
        fields = ["nome", "email", "departamento", "mensagem"]

        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Seu nome completo",
                "autocomplete": "name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Seu e-mail corporativo",
                "autocomplete": "email",
            }),
            "departamento": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Setor / Departamento",
            }),
            "mensagem": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Por que você precisa de acesso ao GED?",
            }),
        }
