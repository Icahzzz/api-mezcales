from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(
        TokenObtainPairSerializer
):


    def validate(self, attrs):

        data = super().validate(attrs)


        data['rol'] = self.user.rol

        data['username'] = self.user.username


        return data
