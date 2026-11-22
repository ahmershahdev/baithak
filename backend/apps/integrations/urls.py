from django.urls import path

from apps.integrations import views

app_name = "integrations"

urlpatterns = [
    path("webhooks/", views.WebhookListView.as_view(), name="webhooks"),
    path("webhooks/<int:webhook_id>/", views.WebhookDetailView.as_view(), name="webhook"),
    path(
        "webhooks/<int:webhook_id>/deliveries/",
        views.DeliveryListView.as_view(),
        name="deliveries",
    ),
]
