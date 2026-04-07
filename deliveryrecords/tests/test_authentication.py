import jwt
from django.conf import settings
from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed

from deliveryrecords.authentication import JWTAuthentication


class JWTAuthenticationTests(SimpleTestCase):
    def setUp(self) -> None:
        self.authentication = JWTAuthentication()
        self.factory = RequestFactory()

    def test_authenticate_rejects_non_utf8_authorization_header(self) -> None:
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = b"\xff"

        with self.assertRaisesMessage(AuthenticationFailed, "Invalid authorization header."):
            self.authentication.authenticate(request)

    def test_authenticate_rejects_token_without_subject(self) -> None:
        request = self.factory.get("/")
        token = jwt.encode(
            {
                "type": "access",
                "email": "admin@example.com",
                "role": "admin",
                "aud": settings.JWT_AUDIENCE,
                "iss": settings.JWT_ISSUER,
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        with self.assertRaisesMessage(AuthenticationFailed, "Invalid token payload."):
            self.authentication.authenticate(request)
