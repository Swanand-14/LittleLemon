from rest_framework.permissions import BasePermission


def in_group(user, name):
    return user.is_authenticated and user.groups.filter(name=name).exists()


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return in_group(request.user, "Manager")


class IsDeliveryCrew(BasePermission):
    def has_permission(self, request, view):
        return in_group(request.user, "Delivery crew")


class IsCustomer(BasePermission):
    """Any logged-in user who is NOT a manager or delivery crew."""

    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and not in_group(user, "Manager")
            and not in_group(user, "Delivery crew")
        )