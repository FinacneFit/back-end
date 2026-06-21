from rest_framework import serializers
from .models import Comment, Post


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.nickname', read_only=True)
    author_id = serializers.IntegerField(source='author.id', read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'author', 'author_id', 'text', 'created_at')


class PostListSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.nickname', read_only=True)
    author_id = serializers.IntegerField(source='author.id', read_only=True)
    likes = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ('id', 'title', 'content', 'author', 'author_id', 'risk_type',
                  'likes', 'liked', 'comment_count', 'created_at')

    def get_likes(self, obj):
        return obj.likes_set.count()

    def get_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes_set.filter(user=request.user).exists()
        return False

    def get_comment_count(self, obj):
        return obj.comments.count()


class PostDetailSerializer(PostListSerializer):
    comments = CommentSerializer(many=True, read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = ('id', 'title', 'content', 'author', 'author_id', 'risk_type',
                  'likes', 'liked', 'comments', 'created_at')


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ('title', 'content', 'risk_type')

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('제목을 입력해주세요.')
        return value

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('내용을 입력해주세요.')
        return value
