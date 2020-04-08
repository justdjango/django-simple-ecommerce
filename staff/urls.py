from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.StaffView.as_view(), name='staff'),
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/<pk>/delete/',
         views.ProductDeleteView.as_view(), name='product-delete'),
]
