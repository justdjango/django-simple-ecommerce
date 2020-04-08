from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.StaffView.as_view(), name='staff'),
]
