import logging

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile

logger = logging.getLogger(__name__)
User = get_user_model()


class AlwaysCSRFSession(SessionAuthentication):
    """Enforce the CSRF check even for not-yet-signed-in requests (login CSRF)."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return None


def serialize_user(user):
    profile = getattr(user, "profile", None)
    return {
        "id": user.pk,
        "email": user.email,
        "name": user.get_full_name() or user.email or user.get_username(),
        "first_name": user.first_name,
        "picture": profile.picture if profile else "",
    }


def verify_google_credential(credential):
    """Verify a Google ID token (signature, expiry, audience). Raises ValueError if invalid."""
    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
    )


def _unique_username(email):
    base = (email.split("@")[0] or "reader")[:120]
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}{n}"
    return username


class AuthConfigView(APIView):
    """GET /api/auth/config/ — tells the frontend which Google client id to use."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"google_client_id": settings.GOOGLE_CLIENT_ID or None})


class MeView(APIView):
    """GET /api/auth/me/ — the signed-in user, or {"user": null}."""

    permission_classes = [AllowAny]

    def get(self, request):
        if request.user.is_authenticated:
            return Response({"user": serialize_user(request.user)})
        return Response({"user": None})


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/  {"credential": "<Google ID token>"}

    The ID token is verified server-side against GOOGLE_CLIENT_ID. Nothing the browser
    says about *who* the user is is trusted except the verified token's claims.
    """

    authentication_classes = [AlwaysCSRFSession]
    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {"detail": "Google sign-in is not configured on the server (GOOGLE_CLIENT_ID is empty)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        credential = request.data.get("credential")
        if not credential or not isinstance(credential, str):
            return Response({"detail": "Missing Google credential."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            claims = verify_google_credential(credential)
        except ValueError:
            return Response({"detail": "Google credential could not be verified."}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:  # network / certificate fetch problems
            logger.exception("Google token verification failed unexpectedly")
            return Response({"detail": "Could not reach Google to verify sign-in. Try again."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
            return Response({"detail": "Invalid token issuer."}, status=status.HTTP_401_UNAUTHORIZED)
        email = (claims.get("email") or "").lower()
        if not email or not claims.get("email_verified"):
            return Response({"detail": "Your Google email address is not verified."},
                            status=status.HTTP_401_UNAUTHORIZED)

        sub = claims["sub"]
        profile = Profile.objects.select_related("user").filter(google_sub=sub).first()
        if profile:
            user = profile.user
        else:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(
                    username=_unique_username(email), email=email,
                    first_name=(claims.get("given_name") or "")[:150],
                    last_name=(claims.get("family_name") or "")[:150],
                )
                user.set_unusable_password()
                user.save(update_fields=["password"])
            profile = Profile.objects.create(user=user, google_sub=sub)

        picture = claims.get("picture") or ""
        if profile.picture != picture:
            profile.picture = picture
            profile.save(update_fields=["picture"])

        if not user.is_active:
            return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"user": serialize_user(user)})


class LogoutView(APIView):
    """POST /api/auth/logout/"""

    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
