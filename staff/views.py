from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cart.models import Order
from .mixins import StaffUserMixin


class StaffView(LoginRequiredMixin, StaffUserMixin, generic.ListView):
    template_name = 'staff/staff.html'
    queryset = Order.objects.filter(ordered=True).order_by('-ordered_date')
    paginate_by = 20
    context_object_name = 'orders'
