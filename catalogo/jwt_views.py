from rest_framework_simplejwt.views import TokenObtainPairView

from .jwt_serializer import CustomTokenObtainPairSerializer



class CustomTokenObtainPairView(
        TokenObtainPairView
):

    serializer_class = (
        CustomTokenObtainPairSerializer
    )
