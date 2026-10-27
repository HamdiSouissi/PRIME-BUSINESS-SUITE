"""ViewSets de base appliquant l'isolation des données par entreprise."""

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from apps.core.permissions import active_company


class CompanyScopedViewSet(viewsets.ModelViewSet):
    """Filtre tout queryset sur l'entreprise active et l'injecte à la création.

    Un utilisateur sans entreprise active ne voit rien : l'isolation est
    garantie côté serveur, jamais côté client.
    """

    def _model_has_company(self):
        return any(
            getattr(f, "name", None) == "company" and f.many_to_one
            for f in self.queryset.model._meta.get_fields()
        )

    def _company(self):
        return active_company(self.request)

    def get_queryset(self):
        queryset = super().get_queryset()
        company = self._company()
        if self._model_has_company():
            if company is None:
                return queryset.none()
            return queryset.filter(company=company)
        return queryset

    def perform_create(self, serializer):
        if self._model_has_company():
            company = self._company()
            if company is None:
                raise PermissionDenied("Aucune entreprise active sélectionnée.")
            # L'entreprise est toujours celle du contexte serveur.
            # Une éventuelle valeur client est ignorée/recouverte.
            serializer.save(company=company)
        else:
            serializer.save()
