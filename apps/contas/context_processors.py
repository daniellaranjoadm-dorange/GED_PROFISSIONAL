from .models import UserConfig

def user_config(request):
    if request.user.is_authenticated:
        cfg, _ = UserConfig.objects.get_or_create(user=request.user)
        return {"user_config": cfg}
    return {"user_config": None}
