from django.contrib import admin
from .models import Product, OrderItem, Order


admin.site.register(Product)
admin.site.register(OrderItem)
admin.site.register(Order)
