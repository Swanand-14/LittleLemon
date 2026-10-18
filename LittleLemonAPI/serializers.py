from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Cart, MenuItem, Order, OrderItem


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class MenuItemSerializer(serializers.ModelSerializer):
    category_title = serializers.CharField(source="category.title", read_only=True)

    class Meta:
        model = MenuItem
        fields = ["id", "title", "price", "featured", "category", "category_title"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value


class CartSerializer(serializers.ModelSerializer):
    menuitem_title = serializers.CharField(source="menuitem.title", read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "menuitem", "menuitem_title", "quantity", "unit_price", "price"]
        read_only_fields = ["unit_price", "price"]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    menuitem_title = serializers.CharField(source="menuitem.title", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "menuitem", "menuitem_title", "quantity", "unit_price", "price"]


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    delivery_crew = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(groups__name="Delivery crew"),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Order
        fields = ["id", "user", "delivery_crew", "status", "total", "date", "order_items"]
        read_only_fields = ["user", "total", "date"]