from django.contrib import admin
from .models import (
    Product, OrderItem, Order, ColourVariation,
    SizeVariation, Address, Payment, Category, StripePayment
)


class AddressAdmin(admin.ModelAdmin):
    list_display = [
        'address_line_1',
        'address_line_2',
        'city',
        'zip_code',
        'address_type',
    ]


admin.site.register(Category)
admin.site.register(Address, AddressAdmin)
admin.site.register(ColourVariation)
admin.site.register(Product)
admin.site.register(OrderItem)
admin.site.register(Order)
admin.site.register(SizeVariation)
admin.site.register(Payment)
admin.site.register(StripePayment)
