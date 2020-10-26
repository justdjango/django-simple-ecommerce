from django.http import HttpResponse
import datetime
import json
import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, reverse, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from .forms import AddToCartForm, AddressForm, StripePaymentForm
from .models import Product, OrderItem, Address, Payment, Order, Category, StripePayment
from .utils import get_or_set_order_session

stripe.api_key = settings.STRIPE_SECRET_KEY


class ProductListView(generic.ListView):
    template_name = 'cart/product_list.html'

    def get_queryset(self):
        qs = Product.objects.all()
        category = self.request.GET.get('category', None)
        if category:
            qs = qs.filter(Q(primary_category__name=category) |
                           Q(secondary_categories__name=category)).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(ProductListView, self).get_context_data(**kwargs)
        context.update({
            "categories": Category.objects.values("name")
        })
        return context


class ProductDetailView(generic.FormView):
    template_name = 'cart/product_detail.html'
    form_class = AddToCartForm

    def get_object(self):
        return get_object_or_404(Product, slug=self.kwargs["slug"])

    def get_success_url(self):
        return reverse("cart:summary")

    def get_form_kwargs(self):
        kwargs = super(ProductDetailView, self).get_form_kwargs()
        kwargs["product_id"] = self.get_object().id
        return kwargs

    def form_valid(self, form):
        order = get_or_set_order_session(self.request)
        product = self.get_object()

        item_filter = order.items.filter(
            product=product,
            colour=form.cleaned_data['colour'],
            size=form.cleaned_data['size'],
        )

        if item_filter.exists():
            item = item_filter.first()
            item.quantity += int(form.cleaned_data['quantity'])
            item.save()

        else:
            new_item = form.save(commit=False)
            new_item.product = product
            new_item.order = order
            new_item.save()

        return super(ProductDetailView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(ProductDetailView, self).get_context_data(**kwargs)
        context['product'] = self.get_object()
        return context


class CartView(generic.TemplateView):
    template_name = "cart/cart.html"

    def get_context_data(self, **kwargs):
        context = super(CartView, self).get_context_data(**kwargs)
        context["order"] = get_or_set_order_session(self.request)
        return context


class IncreaseQuantityView(generic.View):
    def get(self, request, *args, **kwargs):
        order_item = get_object_or_404(OrderItem, id=kwargs['pk'])
        order_item.quantity += 1
        order_item.save()
        return redirect("cart:summary")


class DecreaseQuantityView(generic.View):
    def get(self, request, *args, **kwargs):
        order_item = get_object_or_404(OrderItem, id=kwargs['pk'])
        if order_item.quantity <= 1:
            order_item.delete()
        else:
            order_item.quantity -= 1
            order_item.save()
        return redirect("cart:summary")


class RemoveFromCartView(generic.View):
    def get(self, request, *args, **kwargs):
        order_item = get_object_or_404(OrderItem, id=kwargs['pk'])
        order_item.delete()
        return redirect("cart:summary")


class CheckoutView(LoginRequiredMixin, generic.FormView):
    template_name = 'cart/checkout.html'
    form_class = AddressForm

    def get_success_url(self):
        return reverse("cart:payment")

    def form_valid(self, form):
        order = get_or_set_order_session(self.request)
        selected_shipping_address = form.cleaned_data.get(
            'selected_shipping_address')
        selected_billing_address = form.cleaned_data.get(
            'selected_billing_address')

        if selected_shipping_address:
            order.shipping_address = selected_shipping_address
        else:
            address = Address.objects.create(
                address_type='S',
                user=self.request.user,
                address_line_1=form.cleaned_data['shipping_address_line_1'],
                address_line_2=form.cleaned_data['shipping_address_line_2'],
                zip_code=form.cleaned_data['shipping_zip_code'],
                city=form.cleaned_data['shipping_city'],
            )
            order.shipping_address = address

        if selected_billing_address:
            order.billing_address = selected_billing_address
        else:
            address = Address.objects.create(
                address_type='B',
                user=self.request.user,
                address_line_1=form.cleaned_data['billing_address_line_1'],
                address_line_2=form.cleaned_data['billing_address_line_2'],
                zip_code=form.cleaned_data['billing_zip_code'],
                city=form.cleaned_data['billing_city'],
            )
            order.billing_address = address

        order.save()
        messages.info(
            self.request, "You have successfully added your addresses")
        return super(CheckoutView, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CheckoutView, self).get_form_kwargs()
        kwargs["user_id"] = self.request.user.id
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(CheckoutView, self).get_context_data(**kwargs)
        context["order"] = get_or_set_order_session(self.request)
        return context


class PaymentView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'cart/payment.html'

    def get_context_data(self, **kwargs):
        context = super(PaymentView, self).get_context_data(**kwargs)
        context["PAYPAL_CLIENT_ID"] = settings.PAYPAL_CLIENT_ID
        context['order'] = get_or_set_order_session(self.request)
        context['CALLBACK_URL'] = self.request.build_absolute_uri(
            reverse("cart:thank-you"))
        return context


class StripePaymentView(LoginRequiredMixin, generic.FormView):
    template_name = 'cart/stripe_payment.html'
    form_class = StripePaymentForm

    def form_valid(self, form):
        payment_method = form.cleaned_data["selectedCard"]
        print(payment_method)
        if payment_method != "newCard":
            try:
                order = get_or_set_order_session(self.request)
                payment_intent = stripe.PaymentIntent.create(
                    amount=order.get_raw_total(),
                    currency='usd',
                    customer=self.request.user.customer.stripe_customer_id,
                    payment_method=payment_method,
                    off_session=True,
                    confirm=True,
                )
                payment_record, created = StripePayment.objects.get_or_create(
                    order=order
                )
                payment_record.payment_intent_id = payment_intent["id"]
                payment_record.amount = order.get_total()
                payment_record.save()
            except stripe.error.CardError as e:
                err = e.error
                # Error code will be authentication_required if authentication is needed
                print("Code is: %s" % err.code)
                payment_intent_id = err.payment_intent['id']
                payment_intent = stripe.PaymentIntent.retrieve(
                    payment_intent_id)
                messages.warning(self.request, "Code is: %s" % err.code)
        return redirect("/")

    def get_context_data(self, **kwargs):
        user = self.request.user
        if not user.customer.stripe_customer_id:
            stripe_customer = stripe.Customer.create(email=user.email)
            user.customer.stripe_customer_id = stripe_customer["id"]
            user.customer.save()

        order = get_or_set_order_session(self.request)

        payment_intent = stripe.PaymentIntent.create(
            amount=order.get_raw_total(),
            currency='usd',
            customer=user.customer.stripe_customer_id,
        )

        payment_record, created = StripePayment.objects.get_or_create(
            order=order
        )
        payment_record.payment_intent_id = payment_intent["id"],
        payment_record.amount = order.get_total()
        payment_record.save()

        cards = stripe.PaymentMethod.list(
            customer=user.customer.stripe_customer_id,
            type="card",
        )
        payment_methods = []
        for card in cards:
            payment_methods.append({
                "last4": card["card"]["last4"],
                "brand": card["card"]["brand"],
                "exp_month": card["card"]["exp_month"],
                "exp_year": card["card"]["exp_year"],
                "pm_id": card["id"]
            })

        context = super(StripePaymentView, self).get_context_data(**kwargs)
        context["STRIPE_PUBLIC_KEY"] = settings.STRIPE_PUBLIC_KEY
        context["client_secret"] = payment_intent["client_secret"]
        context["payment_methods"] = payment_methods
        return context


class ConfirmOrderView(generic.View):
    def post(self, request, *args, **kwargs):
        order = get_or_set_order_session(request)
        body = json.loads(request.body)
        payment = Payment.objects.create(
            order=order,
            successful=True,
            raw_response=json.dumps(body),
            amount=float(body["purchase_units"][0]["amount"]["value"]),
            payment_method='PayPal'
        )
        order.ordered = True
        order.ordered_date = datetime.date.today()
        order.save()
        return JsonResponse({"data": "Success"})


class ThankYouView(generic.TemplateView):
    template_name = 'cart/thanks.html'


class OrderDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = 'order.html'
    queryset = Order.objects.all()
    context_object_name = 'order'


# If you are testing your webhook locally with the Stripe CLI you
# can find the endpoint's secret by running `stripe listen`
# Otherwise, find your endpoint's secret in your webhook settings in the Developer Dashboard

@csrf_exempt
def stripe_webhook_view(request):
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        print(event)
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object  # contains a stripe.PaymentIntent
        stripe_payment = StripePayment.objects.get(
            payment_intent_id=payment_intent["id"],
        )
        stripe_payment.successful = True
        stripe_payment.save()
        order = stripe_payment.order
        order.ordered = True
        order.ordered_date = timezone.now()
        order.save()
    else:
        # Unexpected event type
        return HttpResponse(status=400)

    return HttpResponse(status=200)
