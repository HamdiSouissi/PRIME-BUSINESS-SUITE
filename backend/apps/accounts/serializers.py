from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.core.permissions import Roles

from .models import CompanyMembership, User


class MembershipSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = CompanyMembership
        fields = ("id", "company", "company_name", "role", "role_label", "is_active")
        read_only_fields = ("id",)


class UserSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "is_staff",
            "memberships",
            "date_joined",
        )
        read_only_fields = ("id", "is_staff", "date_joined")


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=Roles.CHOICES, default=Roles.SALARIE)

    class Meta:
        model = User
        fields = ("id", "email", "username", "first_name", "last_name", "phone", "password", "role")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        role = validated_data.pop("role", Roles.SALARIE)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        request = self.context.get("request")
        company = getattr(request, "company", None)
        if company is not None:
            CompanyMembership.objects.get_or_create(
                user=user, company=company, defaults={"role": role}
            )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value, user=self.context["request"].user)
        return value
