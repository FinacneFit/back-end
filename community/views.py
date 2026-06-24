from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Comment, Like, Post
from .serializers import (
    CommentSerializer,
    PostCreateSerializer,
    PostDetailSerializer,
    PostListSerializer,
)


class PostListCreateView(APIView):
    def get(self, request):
        posts = Post.objects.select_related('author').prefetch_related('likes_set', 'comments')
        risk_type = request.query_params.get('risk_type')
        if risk_type:
            posts = posts.filter(risk_type=risk_type)
        serializer = PostListSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = PostCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            post = serializer.save()
            return Response(
                PostDetailSerializer(post, context={'request': request}).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyPostListView(APIView):
    def get(self, request):
        posts = Post.objects.filter(author=request.user).select_related('author').prefetch_related('likes_set', 'comments')
        serializer = PostListSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)


class PostDetailView(APIView):
    def get_object(self, post_id):
        return get_object_or_404(
            Post.objects.select_related('author').prefetch_related(
                'likes_set', 'comments__author', 'comments__replies__author'
            ),
            pk=post_id,
        )

    def get(self, request, post_id):
        post = self.get_object(post_id)
        serializer = PostDetailSerializer(post, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, post_id):
        post = self.get_object(post_id)
        if post.author != request.user:
            return Response({'detail': '수정 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        if post.risk_type != request.user.investment_type:
            return Response(
                {'detail': '현재 투자 성향이 변경되어 이 게시글을 수정할 수 없습니다.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = PostCreateSerializer(
            post,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if serializer.is_valid():
            post = serializer.save()
            return Response(PostDetailSerializer(post, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, post_id):
        post = self.get_object(post_id)
        if post.author != request.user:
            return Response({'detail': '삭제 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostLikeView(APIView):
    def post(self, request, post_id):
        post = get_object_or_404(Post, pk=post_id)
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({'liked': liked, 'likes': post.likes_set.count()})


class CommentListCreateView(APIView):
    def post(self, request, post_id):
        post = get_object_or_404(Post, pk=post_id)
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': '댓글 내용을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

        parent = None
        parent_id = request.data.get('parent_id')
        if parent_id is not None:
            parent = get_object_or_404(Comment, pk=parent_id, post=post)
            if parent.parent_id is not None:
                return Response(
                    {'detail': '답글에는 다시 답글을 작성할 수 없습니다.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        comment = Comment.objects.create(
            post=post,
            author=request.user,
            parent=parent,
            text=text,
        )
        return Response(
            CommentSerializer(comment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentReplyCreateView(APIView):
    def post(self, request, post_id, comment_id):
        post = get_object_or_404(Post, pk=post_id)
        parent = get_object_or_404(
            Comment,
            pk=comment_id,
            post=post,
            parent__isnull=True,
        )
        text = request.data.get('text', '').strip()
        if not text:
            return Response(
                {'detail': '답글 내용을 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reply = Comment.objects.create(
            post=post,
            author=request.user,
            parent=parent,
            text=text,
        )
        return Response(
            CommentSerializer(reply, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentDetailView(APIView):
    def patch(self, request, post_id, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
        if comment.author != request.user:
            return Response({'detail': '수정 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        text = request.data.get('text', '').strip()
        if not text:
            return Response({'detail': '댓글 내용을 입력해주세요.'}, status=status.HTTP_400_BAD_REQUEST)
        comment.text = text
        comment.save(update_fields=['text'])
        return Response(CommentSerializer(comment, context={'request': request}).data)

    def delete(self, request, post_id, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
        if comment.author != request.user:
            return Response({'detail': '삭제 권한이 없습니다.'}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
