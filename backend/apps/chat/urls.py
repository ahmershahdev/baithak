from django.urls import path

from apps.chat import views

app_name = "channels"

urlpatterns = [
    path("", views.ChannelListView.as_view(), name="list"),
    path("<int:channel_id>/", views.ChannelDetailView.as_view(), name="detail"),
    path("<int:channel_id>/join/", views.ChannelJoinView.as_view(), name="join"),
    path("<int:channel_id>/leave/", views.ChannelLeaveView.as_view(), name="leave"),
    path("<int:channel_id>/members/", views.ChannelMembersView.as_view(), name="members"),
]
