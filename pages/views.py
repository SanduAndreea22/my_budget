from django.shortcuts import render, redirect

def home_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")  # /app/
    return render(request, "pages/home.html")


def privacy_view(request):
    return render(request, "pages/privacy.html")
