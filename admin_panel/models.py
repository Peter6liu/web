from django.db import models
from django.conf import settings
from django.utils import timezone

class SystemSettings(models.Model):
    """系统设置模型"""
    site_name = models.CharField(max_length=100, default='跨境电商平台', verbose_name='站点名称')
    site_description = models.TextField(blank=True, verbose_name='站点描述')
    site_logo = models.ImageField(upload_to='system/', blank=True, null=True, verbose_name='站点Logo')
    
    # 支付设置
    default_currency = models.CharField(max_length=3, default='USD', verbose_name='默认货币')
    payment_gateway_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.03, verbose_name='支付网关费率')
    
    # 佣金设置
    merchant_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.05, verbose_name='商家佣金费率')
    referral_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.01, verbose_name='推荐佣金费率')
    
    # 物流设置
    default_shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, verbose_name='默认运费')
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=100.00, verbose_name='免运费门槛')
    
    # 系统设置
    maintenance_mode = models.BooleanField(default=False, verbose_name='维护模式')
    allow_registration = models.BooleanField(default=True, verbose_name='允许注册')
    require_email_verification = models.BooleanField(default=True, verbose_name='需要邮箱验证')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '系统设置'
        verbose_name_plural = '系统设置'
    
    def __str__(self):
        return f'系统设置 - {self.site_name}'


class CategoryManagement(models.Model):
    """分类管理日志"""
    ACTION_CHOICES = (
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('approve', '审核通过'),
        ('reject', '审核拒绝'),
    )
    
    category_name = models.CharField(max_length=100, verbose_name='分类名称')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作类型')
    description = models.TextField(blank=True, verbose_name='操作描述')
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')
    
    class Meta:
        verbose_name = '分类管理日志'
        verbose_name_plural = '分类管理日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.category_name} - {self.get_action_display()}'


class Promotion(models.Model):
    """促销活动"""
    PROMOTION_TYPES = (
        ('discount', '折扣'),
        ('coupon', '优惠券'),
        ('flash_sale', '闪购'),
        ('bundle', '套餐'),
    )
    
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('active', '进行中'),
        ('paused', '暂停'),
        ('ended', '已结束'),
    )
    
    name = models.CharField(max_length=100, verbose_name='活动名称')
    description = models.TextField(verbose_name='活动描述')
    promotion_type = models.CharField(max_length=20, choices=PROMOTION_TYPES, verbose_name='促销类型')
    
    # 折扣设置
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='折扣百分比')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='折扣金额')
    
    # 适用范围
    applicable_products = models.ManyToManyField('products.Product', blank=True, verbose_name='适用商品')
    applicable_categories = models.ManyToManyField('products.Category', blank=True, verbose_name='适用分类')
    
    # 条件设置
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最低订单金额')
    maximum_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大折扣金额')
    
    # 时间设置
    start_date = models.DateTimeField(verbose_name='开始时间')
    end_date = models.DateTimeField(verbose_name='结束时间')
    
    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    is_active = models.BooleanField(default=False, verbose_name='是否激活')
    
    # 使用统计
    usage_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name='使用限制')
    usage_count = models.PositiveIntegerField(default=0, verbose_name='已使用次数')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '促销活动'
        verbose_name_plural = '促销活动'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def is_valid(self):
        """检查促销是否有效"""
        now = timezone.now()
        return (self.status == 'active' and 
                self.is_active and 
                self.start_date <= now <= self.end_date and
                (self.usage_limit is None or self.usage_count < self.usage_limit))


class SystemLog(models.Model):
    """系统日志"""
    LOG_LEVELS = (
        ('info', '信息'),
        ('warning', '警告'),
        ('error', '错误'),
        ('critical', '严重'),
    )
    
    level = models.CharField(max_length=20, choices=LOG_LEVELS, verbose_name='日志级别')
    message = models.TextField(verbose_name='日志消息')
    module = models.CharField(max_length=100, verbose_name='模块')
    function = models.CharField(max_length=100, verbose_name='函数')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='用户')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='用户代理')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '系统日志'
        verbose_name_plural = '系统日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.level.upper()} - {self.message[:50]}'