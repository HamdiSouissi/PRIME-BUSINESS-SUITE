"""Authentification JWT, gestion des utilisateurs et limitation des tentatives."""

import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from apps.core.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import HasRole, Roles, user_role

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    MembershipSerializer,
    UserCreateSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


def _cache_key(request, email: str) -> str:
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
    ip = ip.split(",")[0].strip()
    return f"login-attempts:{ip}:{email.lower()}"


class LoginThrottleTokenSerializer(TokenObtainPairSerializer):
    """Ajoute le rôle et l'entreprise au jeton pour information (les
    contrôles sont toujours refaits côté serveur)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        membership = user.memberships.filter(is_active=True).first()
        if membership:
            token["company_id"] = membership.company_id
            token["role"] = membership.role
        return token


class LoginView(TokenObtainPairView):
    """Connexion avec blocage temporaire après N échecs."""

    serializer_class = LoginThrottleTokenSerializer

    def post(self, request, *args, **kwargs):
        from django.conf import settings

        email = request.data.get("email", "")
        key = _cache_key(request, email)
        attempts = cache.get(key, 0)
        if attempts >= settings.LOGIN_MAX_ATTEMPTS:
            return Response(
                {
                    "detail": "Trop de tentatives. Réessayez dans quelques minutes.",
                    "code": "login_locked",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            # Échec d'authentification (exception DRF) → incrémente le compteur
            cache.set(key, attempts + 1, timeout=settings.LOGIN_LOCK_MINUTES * 60)
            raise
        if response.status_code == 200:
            cache.delete(key)
        else:
            cache.set(key, attempts + 1, timeout=settings.LOGIN_LOCK_MINUTES * 60)
        return response


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        serializer = UserSerializer(request.user)
        memberships = MembershipSerializer(request.user.memberships.filter(is_active=True), many=True)
        company = getattr(request, "company", None)
        return Response(
            {
                "user": serializer.data,
                "memberships": memberships.data,
                "active_company": company.id if company else None,
                "active_company_name": company.name if company else "",
                "role": user_role(request),
            }
        )

    def post(self, request):
        """Changement de mot de passe."""
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"detail": "Ancien mot de passe incorrect.", "code": "bad_password"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        logger.info("Mot de passe modifié pour %s", request.user.email)
        return Response({"detail": "Mot de passe modifié."})


class UserViewSet(viewsets.ModelViewSet):
    """Administration des utilisateurs de l'entreprise active."""

    queryset = User.objects.all().order_by("email")
    permission_classes = (IsAuthenticated, HasRole.of(Roles.ADMIN, Roles.DIRECTION, Roles.RH))
    filterset_fields = ("is_active",)
    search_fields = ("email", "first_name", "last_name")

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        queryset = super().get_queryset()
        if company is None or self.request.user.is_superuser:
            return queryset
        return queryset.filter(memberships__company=company).distinct()

    @action(detail=True, methods=["post"], url_path="role")
    def set_role(self, request, pk=None):
        """Modifie le rôle d'un utilisateur dans l'entreprise active."""
        user = self.get_object()
        role = request.data.get("role")
        if role not in dict(Roles.CHOICES):
            return Response({"detail": "Rôle inconnu."}, status=400)
        company = getattr(request, "company", None)
        membership = user.memberships.filter(company=company).first()
        if membership is None:
            return Response({"detail": "Utilisateur hors de l'entreprise active."}, status=400)
        membership.role = role
        membership.save(update_fields=["role", "updated_at"])
        return Response(MembershipSerializer(membership).data)
