from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

User = get_user_model()


class Province(models.Model):
    """省份模型"""
    code = models.CharField(max_length=10, primary_key=True, verbose_name='省份代码')
    name = models.CharField(max_length=50, verbose_name='省份名称')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = '省份'
        verbose_name_plural = '省份'


class City(models.Model):
    """城市模型"""
    code = models.CharField(max_length=10, primary_key=True, verbose_name='城市代码')
    name = models.CharField(max_length=50, verbose_name='城市名称')
    province = models.ForeignKey(Province, on_delete=models.CASCADE, verbose_name='所属省份')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = '城市'
        verbose_name_plural = '城市'


class District(models.Model):
    """区县模型"""
    code = models.CharField(max_length=10, primary_key=True, verbose_name='区县代码')
    name = models.CharField(max_length=50, verbose_name='区县名称')
    city = models.ForeignKey(City, on_delete=models.CASCADE, verbose_name='所属城市')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = '区县'
        verbose_name_plural = '区县'


class MerchantProfile(models.Model):
    """商家资料模型"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='merchant_profile')
    company_name = models.CharField(max_length=200, verbose_name='公司名称')
    business_license = models.CharField(max_length=100, blank=True, verbose_name='营业执照号码')
    company_address = models.TextField(blank=True, verbose_name='公司地址')
    company_phone = models.CharField(max_length=20, blank=True, verbose_name='公司电话')
    company_email = models.EmailField(blank=True, verbose_name='公司邮箱')
    description = models.TextField(blank=True, verbose_name='公司描述')
    is_approved = models.BooleanField(default=False, verbose_name='是否审核通过')
    approval_date = models.DateTimeField(blank=True, null=True, verbose_name='审核日期')
    
    # 店铺基本信息
    store_name = models.CharField(max_length=100, verbose_name='店铺名称', blank=True)
    store_description = models.TextField(max_length=500, verbose_name='店铺简介', blank=True)
    store_logo = models.ImageField(upload_to='merchant_logos/', verbose_name='店铺Logo', blank=True, null=True)
    contact_name = models.CharField(max_length=50, verbose_name='联系人姓名', blank=True)
    contact_phone = models.CharField(max_length=20, verbose_name='联系电话', blank=True)
    contact_email = models.EmailField(verbose_name='联系邮箱', blank=True)
    
    # 营业信息
    BUSINESS_STATUS_CHOICES = [
        ('open', '营业中'),
        ('closed', '休息中'),
        ('vacation', '休假中'),
    ]
    business_status = models.CharField(max_length=20, choices=BUSINESS_STATUS_CHOICES, default='open', verbose_name='营业状态')
    business_hours = models.CharField(max_length=50, default='09:00-18:00', verbose_name='营业时间', blank=True)
    rest_days = models.CharField(max_length=100, default='周六,周日', verbose_name='休息日', blank=True)
    shipping_time = models.IntegerField(default=2, verbose_name='发货时间(天)', blank=True)
    shipping_methods = models.JSONField(default=list, verbose_name='支持配送方式', blank=True)
    
    # 地址信息
    province = models.CharField(max_length=20, verbose_name='省份代码', blank=True)
    city = models.CharField(max_length=20, verbose_name='城市代码', blank=True)
    district = models.CharField(max_length=20, verbose_name='区县代码', blank=True)
    address = models.CharField(max_length=200, verbose_name='详细地址', blank=True)
    postal_code = models.CharField(max_length=10, verbose_name='邮政编码', blank=True)
    
    def __str__(self):
        return f"商家资料: {self.company_name}"
    
    class Meta:
        verbose_name = '商家资料'
        verbose_name_plural = '商家资料'
