from rest_framework import serializers
from deposits.models import SavedDeposit
from portfolio.models import PortfolioHolding
from .models import Comment, Post


def build_portfolio_snapshot(user, include_stocks=False, include_deposits=False):
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
    comments = CommentSerializer(many=True, read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = ('id', 'title', 'content', 'author', 'author_id', 'risk_type',
                  'portfolio_snapshot', 'likes', 'liked', 'comments', 'created_at')


class PostCreateSerializer(serializers.ModelSerializer):
    attach_stock_portfolio = serializers.BooleanField(write_only=True, required=False, default=False)
    attach_deposit_portfolio = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Post
        fields = ('title', 'content', 'risk_type',
                  'attach_stock_portfolio', 'attach_deposit_portfolio')

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
        user = self.context['request'].user
        validated_data['portfolio_snapshot'] = build_portfolio_snapshot(
            user,
            include_stocks=include_stocks,
            include_deposits=include_deposits,
        )
        return Post.objects.create(author=user, **validated_data)
