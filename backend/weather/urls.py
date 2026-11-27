from django.urls import path

from weather import views

urlpatterns = [
    path("weather/", views.list_weather, name="weather-list"),
    path("weather/refresh/", views.RefreshView.as_view(), name="weather-refresh"),
    path("weather/export/", views.ExportView.as_view(), name="weather-export"),
    path("dashboard-data/", views.dashboard_data, name="dashboard-data"),
    path("cities/search/", views.search_cities, name="cities-search"),
    path("chat/messages/", views.ChatMessagesView.as_view(), name="chat-messages"),
]
