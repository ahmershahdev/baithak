from django.urls import path

from apps.integrations import views

app_name = "hooks"

urlpatterns = [
    path("github/<str:token>/", views.GitHubDeliveryView.as_view(), name="github"),
    path("incoming/<str:token>/", views.IncomingDeliveryView.as_view(), name="incoming"),
]
