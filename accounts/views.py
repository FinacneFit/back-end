from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Follow, User
from .serializers import (
    FollowUserSerializer,
    SignupSerializer,
    UserDetailSerializer,
    UserSerializer,
)


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'user': UserSerializer(user).data, 'token': token.key},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'non_field_errors': ['이메일과 비밀번호를 입력해주세요.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, email=email, password=password)
    if user is None:
        return Response(
            {'non_field_errors': ['이메일 또는 비밀번호가 올바르지 않습니다.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({'user': UserSerializer(user).data, 'token': token.key})


@api_view(['POST'])
def logout_view(request):
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({'detail': '로그아웃 되었습니다.'})


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        serializer = UserDetailSerializer(user, context={'request': request})
        return Response(serializer.data)


class FollowersView(APIView):
    def get(self, request):
        followers = [f.follower for f in Follow.objects.filter(following=request.user).select_related('follower')]
        serializer = FollowUserSerializer(followers, many=True, context={'request': request})
        return Response(serializer.data)


class FollowingView(APIView):
    def get(self, request):
        following = [f.following for f in Follow.objects.filter(follower=request.user).select_related('following')]
        serializer = FollowUserSerializer(following, many=True, context={'request': request})
        return Response(serializer.data)


class FollowView(APIView):
    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        if target == request.user:
            return Response({'detail': '자기 자신을 팔로우할 수 없습니다.'}, status=status.HTTP_400_BAD_REQUEST)
        _, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if not created:
            return Response({'detail': '이미 팔로우 중입니다.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': '팔로우했습니다.', 'is_following': True})

    def delete(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        Follow.objects.filter(follower=request.user, following=target).delete()
        return Response({'detail': '언팔로우했습니다.', 'is_following': False})
