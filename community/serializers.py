from copy import deepcopy

from rest_framework import serializers
from deposits.models import SavedDeposit
from portfolio.models import PortfolioHolding
from .models import Comment, Post


def build_portfolio_snapshot(
    user,
    include_stocks=False,
    include_deposits=False,
    show_returns=True,
):
    snapshot = {}

    if include_stocks:
        holdings = PortfolioHolding.objects.filter(user=user).select_related('stock')
        items = []
        total_invested = 0
        total_value = 0
        for holding in holdings:
            invested = holding.buy_price * holding.qty
            value = holding.stock.price * holding.qty
            total_invested += invested
            total_value += value
            items.append({
                'name': holding.stock.name,
                'code': holding.stock.code,
                'category': holding.stock.category,
                'qty': holding.qty,
                'buy_price': holding.buy_price,
                'current_price': holding.stock.price,
                'value': value,
            })
        if items:
            snapshot['stocks'] = {
                'items': items,
                'show_returns': show_returns,
                'total_invested': total_invested,
                'total_value': total_value,
                'return_rate': round(
                    (total_value - total_invested) / total_invested * 100, 2
                ) if total_invested else 0,
            }

    if include_deposits:
        saved_deposits = (
            SavedDeposit.objects.filter(user=user)
            .select_related('product')
            .prefetch_related('product__options')
        )
        items = []
        total_amount = 0
        for saved in saved_deposits:
            total_amount += saved.amount
            best_option = max(
                saved.product.options.all(),
                key=lambda option: (option.intr_rate2 or 0, option.intr_rate or 0),
                default=None,
            )
            items.append({
                'bank_name': saved.product.kor_co_nm,
                'product_name': saved.product.fin_prdt_nm,
                'product_type': saved.product.product_type,
                'amount': saved.amount,
                'rate': saved.final_rate or (
                    (best_option.intr_rate2 or best_option.intr_rate or 0) if best_option else 0
                ),
                'term': best_option.save_trm if best_option else None,
                'memo': saved.memo,
            })
        if items:
            snapshot['deposits'] = {'items': items, 'total_amount': total_amount}

    return snapshot


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.nickname', read_only=True)
    author_id = serializers.IntegerField(source='author.id', read_only=True)
    parent_id = serializers.IntegerField(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ('id', 'author', 'author_id', 'parent_id', 'text', 'created_at', 'replies')

    def get_replies(self, obj):
        return CommentSerializer(obj.replies.all(), many=True).data


class PostListSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.nickname', read_only=True)
    author_id = serializers.IntegerField(source='author.id', read_only=True)
    likes = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ('id', 'title', 'content', 'author', 'author_id', 'risk_type',
                  'portfolio_snapshot', 'likes', 'liked', 'comment_count', 'created_at')

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
    comments = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = ('id', 'title', 'content', 'author', 'author_id', 'risk_type',
                  'portfolio_snapshot', 'likes', 'liked', 'comments', 'created_at')

    def get_comments(self, obj):
        comments = obj.comments.filter(parent__isnull=True)
        return CommentSerializer(comments, many=True).data


class PostCreateSerializer(serializers.ModelSerializer):
    attach_stock_portfolio = serializers.BooleanField(write_only=True, required=False, default=False)
    attach_deposit_portfolio = serializers.BooleanField(write_only=True, required=False, default=False)
    show_portfolio_returns = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = Post
        fields = ('title', 'content', 'risk_type',
                  'attach_stock_portfolio', 'attach_deposit_portfolio',
                  'show_portfolio_returns')

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('제목을 입력해주세요.')
        return value

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('내용을 입력해주세요.')
        return value

    def create(self, validated_data):
        include_stocks = validated_data.pop('attach_stock_portfolio', False)
        include_deposits = validated_data.pop('attach_deposit_portfolio', False)
        show_returns = validated_data.pop('show_portfolio_returns', True)
        user = self.context['request'].user
        validated_data['portfolio_snapshot'] = build_portfolio_snapshot(
            user,
            include_stocks=include_stocks,
            include_deposits=include_deposits,
            show_returns=show_returns,
        )
        return Post.objects.create(author=user, **validated_data)

    def update(self, instance, validated_data):
        attachment_fields = {
            'attach_stock_portfolio',
            'attach_deposit_portfolio',
            'show_portfolio_returns',
        }
        should_update_snapshot = any(field in validated_data for field in attachment_fields)
        include_stocks = validated_data.pop('attach_stock_portfolio', False)
        include_deposits = validated_data.pop('attach_deposit_portfolio', False)
        show_returns = validated_data.pop('show_portfolio_returns', True)

        if should_update_snapshot:
            # 기존에 첨부된 자산은 작성 당시 스냅샷을 보존한다.
            snapshot = deepcopy(instance.portfolio_snapshot or {})
            if include_stocks:
                if 'stocks' not in snapshot:
                    stocks = build_portfolio_snapshot(
                        self.context['request'].user,
                        include_stocks=True,
                        show_returns=show_returns,
                    ).get('stocks')
                    if stocks:
                        snapshot['stocks'] = stocks
                else:
                    snapshot['stocks']['show_returns'] = show_returns
            else:
                snapshot.pop('stocks', None)

            if include_deposits:
                if 'deposits' not in snapshot:
                    deposits = build_portfolio_snapshot(
                        self.context['request'].user,
                        include_deposits=True,
                    ).get('deposits')
                    if deposits:
                        snapshot['deposits'] = deposits
            else:
                snapshot.pop('deposits', None)

            instance.portfolio_snapshot = snapshot

        for field, value in validated_data.items():
            setattr(instance, field, value)
        update_fields = list(validated_data.keys())
        if should_update_snapshot:
            update_fields.append('portfolio_snapshot')
        instance.save(update_fields=update_fields)
        return instance
