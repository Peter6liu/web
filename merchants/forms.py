from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from products.models import Product, Category, ProductImage
from orders.models import Order, OrderStatusHistory
from .models import MerchantProfile


class ProductForm(forms.ModelForm):
    # 添加模板中使用的额外字段
    subtitle = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    brand = forms.CharField(
        max_length=50, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    original_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    cost_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    wholesale_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    low_stock_threshold = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    min_order_quantity = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'data-role': 'tagsinput'})
    )
    
    # 为status字段添加选择选项并设置默认值
    status = forms.ChoiceField(
        choices=Product.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='active'  # 设置默认值为'active'，让商品立即显示
    )
    
    # 为currency字段添加选择选项并设置默认值
    currency = forms.ChoiceField(
        choices=[('USD', 'USD'), ('CNY', 'CNY'), ('EUR', 'EUR'), ('GBP', 'GBP')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='USD'  # 设置默认值为'USD'
    )
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'stock_quantity', 'sku', 'category', 'weight', 
                 'dimensions', 'origin_country', 'meta_title', 'meta_description', 'is_featured',
                 'status', 'currency']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-control'}),
            'origin_country': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        merchant = kwargs.pop('merchant', None)
        super().__init__(*args, **kwargs)
        
        # 限制只能选择自己的分类或创建新分类
        if merchant:
            # 获取该商家的商品分类和系统分类
            # merchant是MerchantProfile实例，merchant.user是CustomUser实例
            self.fields['category'].queryset = Category.objects.filter(
                Q(products__merchant=merchant.user) | Q(products__isnull=True)
            ).distinct()


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'alt_text': forms.TextInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MerchantProfileForm(forms.ModelForm):
    class Meta:
        model = MerchantProfile
        fields = ['company_name', 'business_license', 'company_address', 'company_phone', 
                 'company_email', 'description']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_license': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class InventoryUpdateForm(forms.Form):
    stock_quantity = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '库存变更说明'})
    )


@login_required
def check_merchant_approval(user):
    """检查商家是否通过审核"""
    if user.user_type != 'merchant':
        return False
    
    try:
        profile = user.merchant_profile
        return profile.is_approved
    except MerchantProfile.DoesNotExist:
        return False


@login_required
def dashboard(request):
    """商家仪表板"""
    if not request.user.user_type == 'merchant':
        messages.error(request, '您没有访问此页面的权限。')
        return redirect('accounts:home')
    
    if not check_merchant_approval(request.user):
        messages.warning(request, '您的商家账户还未审核通过，请耐心等待。')
        return redirect('accounts:home')
    
    # 获取统计数据
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    
    # 商品统计
    total_products = Product.objects.filter(merchant=request.user).count()
    active_products = Product.objects.filter(merchant=request.user, status='active').count()
    
    # 订单统计
    total_orders = Order.objects.filter(merchant=request.user).count()
    recent_orders = Order.objects.filter(merchant=request.user, created_at__gte=week_start).count()
    pending_orders = Order.objects.filter(merchant=request.user, status='pending').count()
    
    # 销售统计
    monthly_sales = Order.objects.filter(
        merchant=request.user,
        created_at__gte=month_start,
        status__in=['delivered', 'processing']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    recent_sales = Order.objects.filter(
        merchant=request.user,
        created_at__gte=week_start,
        status__in=['delivered', 'processing']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # 最近订单
    recent_order_list = Order.objects.filter(
        merchant=request.user
    ).select_related('customer').order_by('-created_at')[:10]
    
    # 热门商品
    popular_products = Product.objects.filter(
        merchant=request.user,
        order_items__order__created_at__gte=month_start
    ).annotate(
        total_sold=Sum('order_items__quantity')
    ).order_by('-total_sold')[:5]
    
    context = {
        'active_tab': 'dashboard',
        'total_products': total_products,
        'active_products': active_products,
        'total_orders': total_orders,
        'recent_orders': recent_orders,
        'pending_orders': pending_orders,
        'monthly_sales': monthly_sales,
        'recent_sales': recent_sales,
        'recent_order_list': recent_order_list,
        'popular_products': popular_products,
    }
    
    return render(request, 'merchant/dashboard.html', context)


@login_required
def product_list(request):
    """商品管理列表"""
    if not request.user.user_type == 'merchant':
        messages.error(request, '您没有访问此页面的权限。')
        return redirect('accounts:home')
    
    if not check_merchant_approval(request.user):
        messages.warning(request, '您的商家账户还未审核通过，请耐心等待。')
        return redirect('accounts:home')
    
    products = Product.objects.filter(merchant=request.user).select_related('category')
    
    # 搜索和筛选
    search = request.GET.get('search')
    status_filter = request.GET.get('status')
    category_filter = request.GET.get('category')
    
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(sku__icontains=search) |
            Q(description__icontains=search)
        )
    
    if status_filter:
        products = products.filter(status=status_filter)
    
    if category_filter:
        products = products.filter(category__pk=category_filter)
    
    context = {
        'active_tab': 'products',
        'products': products,
        'categories': Category.objects.all(),
    }
    
    return render(request, 'merchant/product_list.html', context)