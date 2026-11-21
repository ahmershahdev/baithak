from django.urls import path

from apps.chat import message_views, views

app_name = "channels"

urlpatterns = [
    path("", views.ChannelListView.as_view(), name="list"),
    path("<int:channel_id>/", views.ChannelDetailView.as_view(), name="detail"),
    path("<int:channel_id>/join/", views.ChannelJoinView.as_view(), name="join"),
    path("<int:channel_id>/leave/", views.ChannelLeaveView.as_view(), name="leave"),
    path("<int:channel_id>/read/", views.ChannelReadView.as_view(), name="read"),
    path("<int:channel_id>/members/", views.ChannelMembersView.as_view(), name="members"),
    path("<int:channel_id>/messages/", message_views.MessageListView.as_view(), name="messages"),
    path(
        "<int:channel_id>/messages/<int:seq>/",
        message_views.MessageDetailView.as_view(),
        name="message",
    ),
    path(
        "<int:channel_id>/messages/<int:seq>/replies/",
        message_views.ThreadView.as_view(),
        name="thread",
    ),
    path(
        "<int:channel_id>/messages/<int:seq>/replies/<int:thread_seq>/",
        message_views.ReplyDetailView.as_view(),
        name="reply",
    ),
]
