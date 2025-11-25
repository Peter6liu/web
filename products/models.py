from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    name = models.CharField(max_length=100)
    name_zh = models.CharField(max_length=100, blank=True)  # 中文名称
    description = models.TextField(blank=True)
    description_zh = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def slug(self):
        """返回基于名称的slug"""
        from django.utils.text import slugify
        return slugify(self.name)


class Product(models.Model):
    name = models.CharField(max_length=200)
    name_zh = models.CharField(max_length=200, blank=True)  # 中文名称
    subtitle = models.CharField(max_length=100, blank=True)  # 副标题
    description = models.TextField()
    description_zh = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # 原价
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # 成本价
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # 批发价
    currency = models.CharField(max_length=3, default='USD')
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)  # 库存预警阈值
    min_order_quantity = models.PositiveIntegerField(default=1)  # 最小起订量
    sku = models.CharField(max_length=50, unique=True)
    brand = models.CharField(max_length=50, blank=True)  # 品牌
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    merchant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products', limit_choices_to={'user_type': 'merchant'})
    
    # 商品状态
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # 物流信息
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    shipping_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # 配送重量
    dimensions = models.CharField(max_length=100, blank=True)  # 尺寸
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # 长
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # 宽
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # 高
    origin_country = models.CharField(max_length=100, blank=True)  # 原产国
    
    # SEO信息
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)  # SEO关键词
    
    # 其他字段
    tags = models.CharField(max_length=200, blank=True)  # 商品标签
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # 是否在售
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def is_in_stock(self):
        return self.stock_quantity > 0
    
    @property
    def slug(self):
        """返回基于名称的slug"""
        from django.utils.text import slugify
        return slugify(self.name)
    
    def get_absolute_url(self):
        """返回商品的绝对URL"""
        from django.urls import reverse
        return reverse('products:product_detail', args=[self.pk])
    
    @property
    def status_color(self):
        """返回状态对应的颜色类"""
        color_map = {
            'draft': 'secondary',
            'active': 'success',
            'inactive': 'danger',
        }
        return color_map.get(self.status, 'secondary')
    
    @property
    def stock(self):
        """兼容性属性，返回库存数量"""
        return self.stock_quantity
    
    @property
    def average_rating(self):
        """计算平均评分"""
        from django.db.models import Avg
        avg = self.reviews.aggregate(avg=Avg('rating'))['avg']
        return avg or 0
    
    @property
    def variant_info(self):
        """变体信息（兼容性属性）"""
        if self.variants.exists():
            return ', '.join([f"{v.name}: {v.value}" for v in self.variants.all()[:3]])
        return ''
    
    @property
    def purchase_price(self):
        """进货价（兼容性属性，默认使用商品价格）"""
        from decimal import Decimal
        return self.price * Decimal('0.6')  # 假设进货价为销售价的60%
    
    @property
    def selling_price(self):
        """销售价（兼容性属性）"""
        return self.price
    
    @property
    def safety_stock(self):
        """安全库存（兼容性属性）"""
        return 10  # 默认安全库存为10
    
    @property
    def current_stock(self):
        """当前库存（兼容性属性）"""
        return self.stock_quantity
    
    @property
    def image_url(self):
        """主图片URL（兼容性属性）"""
        if self.images.filter(is_primary=True).exists():
            return self.images.filter(is_primary=True).first().image.url
        elif self.images.exists():
            return self.images.first().image.url
        return None
    
    def get_stock_status_display(self):
        """返回库存状态显示文本"""
        if self.stock_quantity == 0:
            return '缺货'
        elif self.stock_quantity < 10:
            return '库存不足'
        else:
            return '库存充足'
    
    @property
    def get_stock_status_color(self):
        """返回库存状态对应的颜色"""
        if self.stock_quantity == 0:
            return 'danger'
        elif self.stock_quantity < 10:
            return 'warning'
        else:
            return 'success'


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100)  # 例如：颜色、尺寸
    value = models.CharField(max_length=100)  # 例如：红色、XL
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"


class Review(models.Model):
    RATING_CHOICES = (
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'customer'})
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    images = models.ManyToManyField('ReviewImage', blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['product', 'customer']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review for {self.product.name} by {self.customer.username}"


class ReviewImage(models.Model):
    image = models.ImageField(upload_to='review_images/')
    alt_text = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review Image {self.id}"


class Wishlist(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'customer'})
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['customer', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.username}'s wishlist item: {self.product.name}"
