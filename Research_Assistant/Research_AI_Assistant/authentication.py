import logging
import os
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from clerk_backend_api import authenticate_request, AuthenticateRequestOptions
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class ClerkAuthentication(BaseAuthentication):
    def authenticate(self, request):
        django_request = request._request

        request_state = authenticate_request(
            django_request,
            AuthenticateRequestOptions(
                authorized_parties=settings.CLERK_AUTHORIZED_PARTIES,
                secret_key=settings.CLERK_SECRET_KEY,
            ),
        )

        if not request_state.is_signed_in:
            logger.warning(
                "Clerk auth rejected %s %s: %s",
                django_request.method,
                django_request.path,
                request_state.reason,
            )
            raise AuthenticationFailed(f"Clerk auth failed: {request_state.reason}")

        payload = request_state.payload
        clerk_user_id = payload.get("sub")

        if not clerk_user_id:
            logger.error("Clerk token verified but has no 'sub' claim")
            raise AuthenticationFailed("No user ID in Clerk token")

        user, _ = User.objects.get_or_create(
            clerk_id=clerk_user_id,
            defaults={"is_active": True},
        )

        return (user, None)
