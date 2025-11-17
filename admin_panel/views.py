from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta

from accounts.models import CustomUser, Address
from products.models import Product, Category, Review
from orders.models import Order, OrderItem


def admin_required(user):
    """检查用户是否为管理员"""
    return user.is_authenticated and user.user_type == 'admin'


@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    """管理员仪表板"""
    # 获取统计数据
    total_users = CustomUser.objects.count()
    total_customers = CustomUser.objects.filter(user_type='customer').count()
    total_merchants = CustomUser.objects.filter(user_type='merchant').count()
    
    # 待审核商家统计（已激活但未审核通过的商家）
    pending_merchants = len([merchant for merchant in CustomUser.objects.filter(user_type='merchant', is_active=True) 
                           if hasattr(merchant, 'merchant_profile') and not merchant.merchant_profile.is_approved])
    
    total_products = Product.objects.count()
    pending_products = Product.objects.filter(status='pending').count()
    
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    completed_orders = Order.objects.filter(status='delivered').count()
    
    # 计算总收入（近30天）
    last_30_days = timezone.now() - timedelta(days=30)
    revenue_data = Order.objects.filter(
        created_at__gte=last_30_days,
        status='delivered'
    ).aggregate(
        total_revenue=Sum('total_amount'),
        order_count=Count('id'),
        avg_order_value=Avg('total_amount')
    )
    
    # 每日订单趋势（最近7天）
    daily_orders = []
    for i in range(6, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        count = Order.objects.filter(created_at__date=date).count()
        daily_orders.append({
            'date': date.strftime('%m-%d'),
            'count': count
        })
    
    # 商品分类统计
    category_stats = Category.objects.annotate(
        product_count=Count('products')
    ).values('name', 'product_count')[:10]
    
    # 最新订单
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:10]
    
    # 最新注册用户
    recent_users = CustomUser.objects.filter(
        created_at__gte=last_30_days
    ).order_by('-created_at')[:10]
    
    context = {
        'total_users': total_users,
        'total_customers': total_customers,
        'total_merchants': total_merchants,
        'pending_merchants': pending_merchants,
        'total_products': total_products,
        'pending_products': pending_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'revenue_data': revenue_data,
        'daily_orders': daily_orders,
        'category_stats': category_stats,
        'recent_orders': recent_orders,
        'recent_users': recent_users,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@user_passes_test(admin_required)
def user_management(request):
    """用户管理"""
    users = CustomUser.objects.all().order_by('-created_at')
    
    # 筛选
    user_type = request.GET.get('user_type', '')
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    if user_type:
        users = users.filter(user_type=user_type)
    if status:
        users = users.filter(is_active=(status == 'active'))
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # 分页
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_type': user_type,
        'status': status,
        'search': search,
    }
    
    return render(request, 'admin_panel/user_management.html', context)


@login_required
@user_passes_test(admin_required)
def customer_management(request):
    """客户管理"""
    customers = CustomUser.objects.filter(user_type='customer').order_by('-created_at')
    
    # 筛选
    search = request.GET.get('search', '')
    if search:
        customers = customers.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search)
        )
    
    # 分页
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'admin_panel/customer_management.html', context)


@login_required
@user_passes_test(admin_required)
def merchant_management(request):
    """商家管理"""
    merchants = CustomUser.objects.filter(user_type='merchant').order_by('-created_at')
    
    # 筛选
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    
    if search:
        merchants = merchants.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    if status:
        merchants = merchants.filter(is_active=(status == 'active'))
    
    # 分页
    paginator = Paginator(merchants, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 统计数据
    total_merchants = CustomUser.objects.filter(user_type='merchant').count()
    active_merchants = CustomUser.objects.filter(user_type='merchant', is_active=True).count()
    # 正确统计待审核商家：已激活但未审核通过的商家
    pending_merchants_count = len([merchant for merchant in CustomUser.objects.filter(user_type='merchant', is_active=True) 
                                  if hasattr(merchant, 'merchant_profile') and not merchant.merchant_profile.is_approved])
    inactive_merchants_count = total_merchants - active_merchants
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'total_merchants': total_merchants,
        'active_merchants': active_merchants,
        'pending_merchants_count': pending_merchants_count,
        'inactive_merchants_count': inactive_merchants_count,
    }
    
    return render(request, 'admin_panel/merchant_management.html', context)


@login_required
@user_passes_test(admin_required)
def pending_merchants(request):
    """待审核商家"""
    # 获取待审核的商家（已激活但未审核通过的商家）
    pending_merchants = CustomUser.objects.filter(
        user_type='merchant',
        is_active=True
    ).order_by('-created_at')
    
    # 进一步筛选：只显示未审核通过的商家
    pending_merchants = [merchant for merchant in pending_merchants 
                        if hasattr(merchant, 'merchant_profile') and 
                           not merchant.merchant_profile.is_approved]
    
    # 筛选
    search = request.GET.get('search', '')
    if search:
        # 由于pending_merchants现在是列表，我们需要手动过滤
        pending_merchants = [merchant for merchant in pending_merchants 
                           if (search.lower() in merchant.username.lower() or
                               search.lower() in merchant.email.lower() or
                               search.lower() in (merchant.first_name or '').lower() or
                               search.lower() in (merchant.last_name or '').lower())]
    
    # 分页
    paginator = Paginator(pending_merchants, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'admin_panel/pending_merchants.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def approve_merchant(request, merchant_id):
    """审核通过商家"""
    merchant = get_object_or_404(CustomUser, id=merchant_id, user_type='merchant')
    
    try:
        # 激活用户账户
        merchant.is_active = True
        merchant.save()
        
        # 更新商家资料的审核状态
        if hasattr(merchant, 'merchant_profile'):
            merchant.merchant_profile.is_approved = True
            merchant.merchant_profile.approval_date = timezone.now()
            merchant.merchant_profile.save()
        
        messages.success(request, f'商家 "{merchant.username}" 已审核通过')
        return redirect('admin_panel:pending_merchants')
        
    except Exception as e:
        messages.error(request, f'审核失败：{str(e)}')
        return redirect('admin_panel:pending_merchants')


@login_required
@user_passes_test(admin_required)
@require_POST
def reject_merchant(request, merchant_id):
    """拒绝商家申请"""
    merchant = get_object_or_404(CustomUser, id=merchant_id, user_type='merchant')
    reason = request.POST.get('reason', '')
    
    try:
        # 这里可以添加拒绝理由记录逻辑
        # 暂时只返回消息
        messages.success(request, f'商家 "{merchant.username}" 的申请已被拒绝')
        return redirect('admin_panel:pending_merchants')
        
    except Exception as e:
        messages.error(request, f'操作失败：{str(e)}')
        return redirect('admin_panel:pending_merchants')


@login_required
@user_passes_test(admin_required)
def user_detail(request, user_id):
    """用户详情"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if user.user_type == 'customer':
        orders = Order.objects.filter(customer=user).order_by('-created_at')[:10]
        context = {
            'user_obj': user,
            'orders': orders,
            'user_type': 'customer'
        }
    elif user.user_type == 'merchant':
        products = Product.objects.filter(merchant=user).order_by('-created_at')[:10]
        orders = Order.objects.filter(
            order_items__product__merchant=user
        ).distinct().order_by('-created_at')[:10]
        context = {
            'user_obj': user,
            'products': products,
            'orders': orders,
            'user_type': 'merchant'
        }
    else:
        context = {
            'user_obj': user,
            'user_type': 'admin'
        }
    
    return render(request, 'admin_panel/user_detail.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def update_user_status(request, user_id):
    """更新用户状态"""
    user = get_object_or_404(CustomUser, id=user_id)
    action = request.POST.get('action')
    
    try:
        if action == 'activate':
            user.is_active = True
            message = '用户已激活'
        elif action == 'deactivate':
            user.is_active = False
            message = '用户已停用'
        else:
            return JsonResponse({'error': '无效的操作'}, status=400)
        
        user.save()
        return JsonResponse({
            'success': True,
            'message': message,
            'new_status': 'active' if user.is_active else 'inactive'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(admin_required)
def product_management(request):
    """商品管理"""
    products = Product.objects.select_related('merchant', 'category').order_by('-created_at')
    
    # 筛选
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    search = request.GET.get('search', '')
    
    if status:
        products = products.filter(status=status)
    if category:
        products = products.filter(category_id=category)
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(merchant__username__icontains=search)
        )
    
    categories = Category.objects.all()
    
    # 分页
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'category': category,
        'search': search,
        'categories': categories,
    }
    
    return render(request, 'admin_panel/product_management.html', context)


@login_required
@user_passes_test(admin_required)
def pending_products(request):
    """待审核商品"""
    products = Product.objects.filter(status='pending').select_related('merchant', 'category').order_by('-created_at')
    
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(merchant__username__icontains=search)
        )
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'admin_panel/pending_products.html', context)


@login_required
@user_passes_test(admin_required)
def product_detail(request, product_id):
    """商品详情"""
    product = get_object_or_404(Product.objects.select_related('merchant', 'category'), id=product_id)
    reviews = Review.objects.filter(product=product).order_by('-created_at')[:10]
    
    context = {
        'product': product,
        'reviews': reviews,
    }
    
    return render(request, 'admin_panel/product_detail.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def approve_product(request, product_id):
    """审核通过商品"""
    product = get_object_or_404(Product, id=product_id)
    
    try:
        product.status = 'active'
        product.save()
        
        messages.success(request, f'商品 "{product.name}" 已审核通过')
        return redirect('admin_panel:product_detail', product_id=product_id)
        
    except Exception as e:
        messages.error(request, f'审核失败：{str(e)}')
        return redirect('admin_panel:product_detail', product_id=product_id)


@login_required
@user_passes_test(admin_required)
@require_POST
def reject_product(request, product_id):
    """拒绝商品"""
    product = get_object_or_404(Product, id=product_id)
    reason = request.POST.get('reason', '')
    
    try:
        product.status = 'rejected'
        product.save()
        
        messages.success(request, f'商品 "{product.name}" 已拒绝审核')
        return redirect('admin_panel:product_detail', product_id=product_id)
        
    except Exception as e:
        messages.error(request, f'操作失败：{str(e)}')
        return redirect('admin_panel:product_detail', product_id=product_id)


@login_required
@user_passes_test(admin_required)
@require_POST
def suspend_product(request, product_id):
    """暂停商品"""
    product = get_object_or_404(Product, id=product_id)
    
    try:
        product.status = 'suspended'
        product.save()
        
        return JsonResponse({'success': True, 'message': '商品已暂停'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(admin_required)
@require_POST
def activate_product(request, product_id):
    """激活商品"""
    product = get_object_or_404(Product, id=product_id)
    
    try:
        product.status = 'active'
        product.save()
        
        return JsonResponse({'success': True, 'message': '商品已激活'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@user_passes_test(admin_required)
def order_management(request):
    """订单管理"""
    orders = Order.objects.select_related('customer').order_by('-created_at')
    
    # 筛选
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status:
        orders = orders.filter(status=status)
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(customer__username__icontains=search) |
            Q(customer__email__icontains=search)
        )
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'admin_panel/order_management.html', context)


@login_required
@user_passes_test(admin_required)
def order_detail(request, order_id):
    """订单详情"""
    order = get_object_or_404(Order.objects.select_related('customer'), id=order_id)
    order_items = order.order_items.select_related('product').all()
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    
    return render(request, 'admin_panel/order_detail.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def update_order_status(request, order_id):
    """更新订单状态"""
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status')
    
    try:
        order.status = new_status
        order.save()
        
        return JsonResponse({'success': True, 'message': '订单状态已更新'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# 简化实现 - 其他管理功能
@login_required
@user_passes_test(admin_required)
def category_management(request):
    """分类管理"""
    categories = Category.objects.all().order_by('name')
    return render(request, 'admin_panel/category_management.html', {'categories': categories})


@login_required
@user_passes_test(admin_required)
def financial_management(request):
    """财务管理"""
    # 简化实现
    total_revenue = Order.objects.filter(status='delivered').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    monthly_revenue = Order.objects.filter(
        status='delivered',
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    context = {
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
    }
    
    return render(request, 'admin_panel/financial_management.html', context)


@login_required
@user_passes_test(admin_required)
def system_settings(request):
    """系统设置"""
    return render(request, 'admin_panel/system_settings.html')


# 简化的占位视图函数
@login_required
@user_passes_test(admin_required)
def dispute_management(request):
    return render(request, 'admin_panel/dispute_management.html')


@login_required
@user_passes_test(admin_required)
def dispute_detail(request, dispute_id):
    return render(request, 'admin_panel/dispute_detail.html', {'dispute_id': dispute_id})


@login_required
@user_passes_test(admin_required)
def add_category(request):
    return redirect('admin_panel:category_management')


@login_required
@user_passes_test(admin_required)
def edit_category(request, category_id):
    return redirect('admin_panel:category_management')


@login_required
@user_passes_test(admin_required)
def delete_category(request, category_id):
    return redirect('admin_panel:category_management')


@login_required
@user_passes_test(admin_required)
def transaction_management(request):
    return render(request, 'admin_panel/transaction_management.html')


@login_required
@user_passes_test(admin_required)
def payout_management(request):
    return render(request, 'admin_panel/payout_management.html')


@login_required
@user_passes_test(admin_required)
def financial_reports(request):
    return render(request, 'admin_panel/financial_reports.html')


@login_required
@user_passes_test(admin_required)
def general_settings(request):
    return render(request, 'admin_panel/general_settings.html')


@login_required
@user_passes_test(admin_required)
def payment_settings(request):
    return render(request, 'admin_panel/payment_settings.html')


@login_required
@user_passes_test(admin_required)
def shipping_settings(request):
    return render(request, 'admin_panel/shipping_settings.html')


@login_required
@user_passes_test(admin_required)
def commission_settings(request):
    return render(request, 'admin_panel/commission_settings.html')


@login_required
@user_passes_test(admin_required)
def system_logs(request):
    return render(request, 'admin_panel/system_logs.html')


@login_required
@user_passes_test(admin_required)
def system_reports(request):
    return render(request, 'admin_panel/system_reports.html')


@login_required
@user_passes_test(admin_required)
def system_analytics(request):
    return render(request, 'admin_panel/system_analytics.html')


@login_required
@user_passes_test(admin_required)
def promotion_management(request):
    return render(request, 'admin_panel/promotion_management.html')


@login_required
@user_passes_test(admin_required)
def add_promotion(request):
    return redirect('admin_panel:promotion_management')


@login_required
@user_passes_test(admin_required)
def edit_promotion(request, promotion_id):
    return render(request, 'admin_panel/edit_promotion.html', {'promotion_id': promotion_id})


@login_required
@user_passes_test(admin_required)
def delete_promotion(request, promotion_id):
    return redirect('admin_panel:promotion_management')


@login_required
@user_passes_test(admin_required)
def content_management(request):
    return render(request, 'admin_panel/content_management.html')


@login_required
@user_passes_test(admin_required)
def media_management(request):
    return render(request, 'admin_panel/media_management.html')


@login_required
@user_passes_test(admin_required)
def page_management(request):
    return render(request, 'admin_panel/page_management.html')
