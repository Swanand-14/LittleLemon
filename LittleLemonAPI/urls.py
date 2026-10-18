from django.urls import path

from . import views

urlpatterns = [
    path("menu-items", views.MenuItemsView.as_view()),
    path("menu-items/<int:pk>", views.SingleMenuItemView.as_view()),
    path("groups/manager/users", views.ManagerUsersView.as_view()),
    path("groups/manager/users/<int:pk>", views.ManagerSingleUserView.as_view()),
    path("groups/delivery-crew/users", views.DeliveryCrewUsersView.as_view()),
    path("groups/delivery-crew/users/<int:pk>", views.DeliveryCrewSingleUserView.as_view()),
    path("cart/menu-items", views.CartView.as_view()),
    path("orders", views.OrdersView.as_view()),
    path("orders/<int:pk>", views.SingleOrderView.as_view()),
]