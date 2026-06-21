from rest_framework import serializers
from .models import User


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ('email', 'nickname', 'password')
        extra_kwargs = {
            'email':    {'validators': []},
            'nickname': {'validators': []},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('이미 사용 중인 이메일입니다.')
        return value

    def validate_nickname(self, value):
        if User.objects.filter(nickname=value).exists():
            raise serializers.ValidationError('이미 사용 중인 닉네임입니다.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'nickname', 'bio', 'investment_type', 'risk_score',
                  'follower_count', 'following_count', 'post_count')
        read_only_fields = ('id', 'email', 'investment_type', 'risk_score')


class UserDetailSerializer(serializers.ModelSerializer):
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    post_count = serializers.IntegerField(read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'nickname', 'bio', 'investment_type',
                  'follower_count', 'following_count', 'post_count', 'is_following')

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.follower_set.filter(follower=request.user).exists()
        return False


class FollowUserSerializer(serializers.ModelSerializer):
    follower_count  = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    post_count      = serializers.IntegerField(read_only=True)
    is_following    = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'nickname', 'bio', 'investment_type',
                  'follower_count', 'following_count', 'post_count', 'is_following')

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.follower_set.filter(follower=request.user).exists()
        return False
