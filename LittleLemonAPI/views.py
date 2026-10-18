from datetime import date

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, MenuItem, Order, OrderItem
from .permissions import IsCustomer, IsManager, in_group
from .serializers import (
    CartSerializer,
    MenuItemSerializer,
    OrderSerializer,
    UserSerializer,
)


class StandardPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "perpage"  # e.g. ?perpage=10&page=2
    max_page_size = 50


# ---------------------------------------------------------------- menu items
class MenuItemsView(generics.ListCreateAPIView):
    queryset = MenuItem.objects.select_related("category").all().order_by("id")
    serializer_class = MenuItemSerializer
    pagination_class = StandardPagination
    filterset_fields = {"category": ["exact"], "featured": ["exact"], "price": ["gte", "lte"]}
    ordering_fields = ["price", "title", "category"]
    search_fields = ["title", "category__title"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [IsManager()]


class SingleMenuItemView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [IsManager()]

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


# ---------------------------------------------------------- group management
class GroupUsersView(APIView):
    permission_classes = [IsManager]
    group_name = None

    def get(self, request):
        users = User.objects.filter(groups__name=self.group_name)
        return Response(UserSerializer(users, many=True).data)

    def post(self, request):
        username = request.data.get("username")
        if not username:
            return Response({"message": "username is required"}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(User, username=username)
        group, _ = Group.objects.get_or_create(name=self.group_name)
        group.user_set.add(user)
        return Response({"message": f"{username} added to {self.group_name}"}, status=status.HTTP_201_CREATED)


class GroupSingleUserView(APIView):
    permission_classes = [IsManager]
    group_name = None

    def delete(self, request, pk):
        group, _ = Group.objects.get_or_create(name=self.group_name)
        user = get_object_or_404(group.user_set, pk=pk)
        group.user_set.remove(user)
        return Response({"message": f"{user.username} removed from {self.group_name}"}, status=status.HTTP_200_OK)


class ManagerUsersView(GroupUsersView):
    group_name = "Manager"


class ManagerSingleUserView(GroupSingleUserView):
    group_name = "Manager"


class DeliveryCrewUsersView(GroupUsersView):
    group_name = "Delivery crew"


class DeliveryCrewSingleUserView(GroupSingleUserView):
    group_name = "Delivery crew"


# ---------------------------------------------------------------------- cart
class CartView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsCustomer]
    pagination_class = None

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).select_related("menuitem")

    def create(self, request, *args, **kwargs):
        menuitem = get_object_or_404(MenuItem, pk=request.data.get("menuitem"))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data["quantity"]

        cart, created = Cart.objects.get_or_create(
            user=request.user,
            menuitem=menuitem,
            defaults={"quantity": quantity, "unit_price": menuitem.price, "price": menuitem.price * quantity},
        )
        if not created:  # item already in cart -> add to the quantity
            cart.quantity += quantity
            cart.unit_price = menuitem.price
            cart.price = cart.unit_price * cart.quantity
            cart.save()
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        self.get_queryset().delete()
        return Response({"message": "Cart cleared"}, status=status.HTTP_200_OK)


# -------------------------------------------------------------------- orders
class OrdersView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    pagination_class = StandardPagination
    filterset_fields = ["status", "delivery_crew", "date"]
    ordering_fields = ["total", "date", "status"]
    search_fields = ["user__username"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.prefetch_related("order_items__menuitem").order_by("id")
        if in_group(user, "Manager"):
            return qs
        if in_group(user, "Delivery crew"):
            return qs.filter(delivery_crew=user)
        return qs.filter(user=user)

    def create(self, request, *args, **kwargs):
        cart_items = list(Cart.objects.filter(user=request.user))
        if not cart_items:
            return Response({"message": "Your cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total=sum(item.price for item in cart_items),
                date=date.today(),
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        menuitem=item.menuitem,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        price=item.price,
                    )
                    for item in cart_items
                ]
            )
            Cart.objects.filter(user=request.user).delete()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class SingleOrderView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.prefetch_related("order_items__menuitem")
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsManager()]
        return [IsAuthenticated()]

    def get_object(self):
        order = super().get_object()  # 404 if it doesn't exist
        user = self.request.user
        if in_group(user, "Manager"):
            return order
        if in_group(user, "Delivery crew"):
            if order.delivery_crew_id != user.id:
                raise PermissionDenied("This order is not assigned to you.")
            return order
        if order.user_id != user.id:
            raise PermissionDenied("This order does not belong to you.")
        return order

    def update(self, request, *args, **kwargs):
        user = request.user
        if in_group(user, "Manager"):
            pass  # may set delivery_crew and status
        elif in_group(user, "Delivery crew"):
            if request.method != "PATCH":
                raise PermissionDenied("Delivery crew can only PATCH the order status.")
            if set(request.data.keys()) - {"status"}:
                raise PermissionDenied("Delivery crew can only update the status.")
        else:
            raise PermissionDenied("You are not allowed to update orders.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)