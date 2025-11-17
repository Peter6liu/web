from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('confirmed', '已确认'),
        ('processing', '处理中'),
        ('shipped', '已发货'),
        ('delivered', '已送达'),
        ('cancelled', '已取消'),
        ('refunded', '已退款'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', '待支付'),
        ('paid', '已支付'),
        ('failed', '支付失败'),
        ('refunded', '已退款'),
    )
    
    order_number = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders', limit_choices_to={'user_type': 'customer'}, verbose_name='客户')
    
    # 订单状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='订单状态')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name='支付状态')
    
    # 金额信息
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='小计')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='运费')
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='税费')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总计')
    currency = models.CharField(max_length=3, default='USD', verbose_name='货币')
    
    # 收货地址 - 使用外键关联到Address模型
    shipping_address = models.ForeignKey('accounts.Address', on_delete=models.PROTECT, related_name='shipping_orders', verbose_name='收货地址')
    billing_address = models.ForeignKey('accounts.Address', on_delete=models.PROTECT, related_name='billing_orders', blank=True, null=True, verbose_name='账单地址')
    
    # 物流信息
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name='跟踪号')
    carrier = models.CharField(max_length=100, blank=True, verbose_name='承运商')
    estimated_delivery = models.DateField(blank=True, null=True, verbose_name='预计送达时间')
    
    # 订单备注
    notes = models.TextField(blank=True, verbose_name='订单备注')
    customer_note = models.TextField(blank=True, verbose_name='客户备注')
    merchant_note = models.TextField(blank=True, verbose_name='商家备注')
    
    # 评价相关字段
    is_reviewed = models.BooleanField(default=False, verbose_name='已评价')
    review_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, verbose_name='评价评分')
    review_comment = models.TextField(blank=True, verbose_name='评价内容')
    service_rating = models.IntegerField(null=True, blank=True, verbose_name='服务评分')
    service_comment = models.TextField(blank=True, verbose_name='服务评价')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = '订单'
        verbose_name_plural = '订单'
    
    def __str__(self):
        return f"订单 {self.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        # 计算总价
        self.total_amount = self.subtotal + self.shipping_cost + self.tax_amount
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        import uuid
        timestamp = timezone.now().strftime('%Y%m%d')
        return f"ORD-{timestamp}-{uuid.uuid4().hex[:8].upper()}"
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
    
    @property
    def can_be_reviewed(self):
        """检查订单是否可以被评价"""
        return self.status in ['delivered'] and not self.is_reviewed
    
    @property
    def shipping_fee(self):
        """运费（兼容性属性）"""
        return self.shipping_cost
    
    @property
    def status_color(self):
        """返回状态对应的颜色类"""
        color_map = {
            'pending': 'warning',
            'confirmed': 'info',
            'processing': 'primary',
            'shipped': 'secondary',
            'delivered': 'success',
            'cancelled': 'danger',
            'refunded': 'dark',
        }
        return color_map.get(self.status, 'secondary')


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items', verbose_name='订单')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, verbose_name='商品')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name='数量')
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='购买时价格')
    
    # 为了兼容性，保留一些字段的别名
    product_name = models.CharField(max_length=255, verbose_name='商品名称')  # 冗余字段，方便显示
    product_sku = models.CharField(max_length=100, verbose_name='商品SKU')  # 冗余字段，方便显示
    
    # 商品评价相关字段
    rating = models.IntegerField(null=True, blank=True, verbose_name='商品评分')
    review_comment = models.TextField(blank=True, verbose_name='商品评价')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '订单项'
        verbose_name_plural = '订单项'
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} (订单: {self.order.order_number})"
    
    def save(self, *args, **kwargs):
        # 保存时自动填充商品名称和SKU
        if not self.product_name:
            self.product_name = self.product.name
        if not self.product_sku:
            self.product_sku = self.product.sku
        super().save(*args, **kwargs)
    
    @property
    def unit_price(self):
        """单价（兼容性方法）"""
        return self.price_at_purchase
    
    @property
    def total_price(self):
        """总价（兼容性方法）"""
        return self.unit_price * self.quantity
    
    def get_total_price(self):
        """获取总价"""
        return self.total_price


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart', verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '购物车'
        verbose_name_plural = '购物车'
    
    def __str__(self):
        return f"购物车 - {self.user.username}"
    
    @property
    def cart_items(self):
        """兼容性属性"""
        return self.items.all()
    
    def get_total_amount(self):
        """获取购物车总金额"""
        return sum(item.get_total_price() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name='购物车')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, verbose_name='商品')
    quantity = models.PositiveIntegerField(default=1, verbose_name='数量')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')
    
    class Meta:
        verbose_name = '购物车项'
        verbose_name_plural = '购物车项'
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    @property
    def unit_price(self):
        """单价"""
        return self.product.price
    
    def get_total_price(self):
        """获取总价"""
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history', verbose_name='订单')
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, verbose_name='状态')
    notes = models.TextField(blank=True, verbose_name='备注')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '订单状态历史'
        verbose_name_plural = '订单状态历史'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.status} ({self.created_at})"
