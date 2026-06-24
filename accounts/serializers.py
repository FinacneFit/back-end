from rest_framework import serializers
from django.core.files.storage import default_storage
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
        fields = ('id', 'email', 'nickname', 'bio', 'profile_image', 'investment_type', 'risk_score',
                  'follower_count', 'following_count', 'post_count')
        read_only_fields = ('id', 'email', 'investment_type', 'risk_score')

    def validate_profile_image(self, image):
        if image is None:
            return image
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('프로필 이미지는 5MB 이하여야 합니다.')
        if image.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise serializers.ValidationError('JPEG, PNG, WebP 이미지만 업로드할 수 있습니다.')
        return image

    def update(self, instance, validated_data):
        old_image_name = instance.profile_image.name if instance.profile_image else None
        image_changed = 'profile_image' in validated_data
        instance = super().update(instance, validated_data)
        new_image_name = instance.profile_image.name if instance.profile_image else None
        if image_changed and old_image_name and old_image_name != new_image_name:
            default_storage.delete(old_image_name)
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    follower_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    post_count = serializers.IntegerField(read_only=True)
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'nickname', 'bio', 'profile_image', 'investment_type',
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
        fields = ('id', 'nickname', 'bio', 'profile_image', 'investment_type',
                  'follower_count', 'following_count', 'post_count', 'is_following')

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.follower_set.filter(follower=request.user).exists()
        return False
