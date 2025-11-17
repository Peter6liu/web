from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.urls import reverse
from datetime import datetime, timedelta
import json
from decimal import Decimal

from products.models import Product, Category
from orders.models import Order, OrderItem
from .models import MerchantProfile, Province, City, District
from .forms import ProductForm, MerchantProfileForm, OrderStatusForm, InventoryUpdateForm
from accounts.models import CustomUser


def _get_merchant_or_redirect(user):
    """获取商家档案或重定向"""
    return getattr(user, 'merchant_profile', None)


def _get_date_range(days_ago=0):
    """获取日期范围"""
    date = timezone.now() - timedelta(days=days_ago)
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _get_monthly_date_range(months_ago=0):
    """获取月度日期范围"""
    now = timezone.now()
    if months_ago == 0:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = now
    else:
        month_start = (now.replace(day=1) - timedelta(days=30*months_ago)).replace(day=1)
        next_month = month_start + timedelta(days=32)
        month_end = next_month.replace(day=1)
    return month_start, month_end


def _get_sales_data(user, days=7):
    """获取销售数据"""
    sales_data = []
    for i in range(days):
        day_start, day_end = _get_date_range(i)
        
        day_sales = OrderItem.objects.filter(
            product__merchant=user,
            order__status='completed',
            order__created_at__gte=day_start,
            order__created_at__lt=day_end
        ).aggregate(total=Sum('price_at_purchase'))
        
        sales_data.append({
            'date': day_start.strftime('%m-%d'),
            'sales': day_sales['total'] or 0
        })
    
    sales_data.reverse()
    return sales_data


def _get_product_images(request, product):
    """处理商品图片"""
    images = request.FILES.getlist('images') if 'images' in request.FILES else request.FILES.getlist('new_images')
    for i, image in enumerate(images):
        from products.models import ProductImage
        ProductImage.objects.create(
            product=product,
            image=image,
            alt_text=product.name,
            is_primary=(i == 0 and not product.images.filter(is_primary=True).exists())
        )


def _get_base_stats(merchant):
    """获取基础统计数据"""
    return {
        'total_products': Product.objects.filter(merchant=merchant).count(),
        'pending_orders': Order.objects.filter(
            order_items__product__merchant=merchant,
            status__in=['pending', 'confirmed']
        ).distinct().count(),
        'completed_orders': Order.objects.filter(
            order_items__product__merchant=merchant,
            status='completed'
        ).count(),
    }


def _get_sales_stats(merchant, days=30):
    """获取销售统计"""
    return OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__gte=timezone.now() - timedelta(days=days)
    ).aggregate(
        total_amount=Sum('price_at_purchase'),
        total_quantity=Sum('quantity')
    )


def _get_daily_sales(merchant, days=7):
    """获取每日销售数据"""
    sales_data = {'labels': [], 'sales': [], 'orders': []}
    
    for i in range(days-1, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        day_start, day_end = _get_date_range(i)
        
        day_orders = Order.objects.filter(
            order_items__product__merchant=merchant,
            created_at__gte=day_start,
            created_at__lt=day_end
        ).distinct()
        
        day_sales = OrderItem.objects.filter(
            order__in=day_orders,
            product__merchant=merchant,
            order__status='completed'
        ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
        
        sales_data['labels'].append(date.strftime('%m-%d'))
        sales_data['sales'].append(float(day_sales))
        sales_data['orders'].append(day_orders.count())
    
    return sales_data


def _get_category_data(merchant):
    """获取商品分类数据"""
    category_data = Product.objects.filter(
        merchant=merchant
    ).values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')[:6]
    
    return {
        'labels': [item['category__name'] or '未分类' for item in category_data],
        'data': [item['count'] for item in category_data]
    }


def _get_customer_stats(merchant, customers):
    """获取客户统计信息"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = current_month - timedelta(days=30)
    
    new_customers = customers.filter(date_joined__gte=current_month).count()
    last_month_customers = customers.filter(
        date_joined__gte=last_month,
        date_joined__lt=current_month
    ).count()
    
    customer_growth = 0
    if last_month_customers > 0:
        customer_growth = ((new_customers - last_month_customers) / last_month_customers) * 100
    
    return {
        'total': customers.count(),
        'active': customers.filter(
            orders__order_items__product__merchant=merchant,
            orders__created_at__gte=thirty_days_ago
        ).distinct().count(),
        'new': new_customers,
        'churned': customers.exclude(
            orders__order_items__product__merchant=merchant,
            orders__created_at__gte=timezone.now() - timedelta(days=90)
        ).distinct().count(),
        'growth': round(customer_growth, 1)
    }


def _process_customer_data(customer, merchant):
    """处理客户数据，添加统计信息"""
    # 计算订单统计
    customer.total_orders = Order.objects.filter(
        customer=customer,
        order_items__product__merchant=merchant
    ).distinct().count()
    
    # 计算消费统计
    customer.total_spent = OrderItem.objects.filter(
        order__customer=customer,
        product__merchant=merchant,
        order__status='completed'
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 计算平均订单价值
    customer.avg_order_value = customer.total_spent / customer.total_orders if customer.total_orders > 0 else 0
    
    # 获取最近订单日期
    last_order = Order.objects.filter(
        customer=customer,
        order_items__product__merchant=merchant
    ).order_by('-created_at').first()
    customer.last_order_date = last_order.created_at if last_order else None
    
    # 客户类型和状态
    if customer.total_spent > 1000:
        customer.customer_type = 'vip'
        customer.customer_type_display = 'VIP客户'
        customer.customer_type_color = 'warning'
    elif customer.total_orders > 5:
        customer.customer_type = 'regular'
        customer.customer_type_display = '老客户'
        customer.customer_type_color = 'success'
    else:
        customer.customer_type = 'new'
        customer.customer_type_display = '新客户'
        customer.customer_type_color = 'info'
    
    # 客户状态
    if customer.last_order_date:
        days_since_last_order = (timezone.now() - customer.last_order_date).days
        if days_since_last_order > 90:
            customer.status = 'inactive'
            customer.status_display = '流失'
            customer.status_color = 'secondary'
        elif days_since_last_order > 30:
            customer.status = 'dormant'
            customer.status_display = '休眠'
            customer.status_color = 'warning'
        else:
            customer.status = 'active'
            customer.status_display = '活跃'
            customer.status_color = 'success'
    else:
        customer.status = 'new'
        customer.status_display = '新注册'
        customer.status_color = 'primary'
    
    return customer


def _get_customer_chart_data(customers):
    """获取客户图表数据"""
    # 客户类型分布数据
    customer_type_stats = {}
    for customer in customers:
        customer_type = customer.customer_type_display
        customer_type_stats[customer_type] = customer_type_stats.get(customer_type, 0) + 1
    
    # 客户增长趋势数据（最近6个月）
    growth_labels = []
    growth_data = []
    
    for i in range(5, -1, -1):
        month_start, month_end = _get_monthly_date_range(i)
        
        month_new_customers = customers.filter(
            date_joined__gte=month_start,
            date_joined__lt=month_end
        ).count()
        
        growth_labels.append(month_start.strftime('%Y-%m'))
        growth_data.append(month_new_customers)
    
    return {
        'customer_type_labels': list(customer_type_stats.keys()),
        'customer_type_data': list(customer_type_stats.values()),
        'growth_labels': growth_labels,
        'growth_data': growth_data
    }


@login_required
def merchant_dashboard(request):
    """商家仪表板首页"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        messages.error(request, '您不是商家用户，无法访问商家后台。')
        return redirect('home')
    
    # 获取统计数据
    base_stats = _get_base_stats(request.user)
    recent_sales = _get_sales_stats(request.user)
    
    # 最近7天的销售数据
    sales_data = json.dumps(_get_sales_data(request.user))
    
    # 最近订单
    recent_orders = Order.objects.filter(
        order_items__product__merchant=request.user
    ).distinct().order_by('-created_at')[:10]
    
    # 获取热销商品
    hot_products = Product.objects.filter(
        merchant=request.user,
        status='active'
    ).annotate(
        sales_count=Sum('orderitem__quantity')
    ).order_by('-sales_count')[:5]
    
    # 获取今日销售数据
    today_start, today_end = _get_date_range(0)
    today_sales = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='completed',
        order__created_at__gte=today_start,
        order__created_at__lt=today_end
    ).aggregate(
        total=Sum('price_at_purchase'),
        count=Count('id')
    )
    
    # 获取本月销售数据
    month_start, month_end = _get_monthly_date_range(0)
    month_sales = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='completed',
        order__created_at__gte=month_start,
        order__created_at__lt=month_end
    ).aggregate(
        total=Sum('price_at_purchase'),
        count=Count('id')
    )
    
    # 生成图表数据
    sales_chart_data = _get_daily_sales(request.user)
    category_chart_data = _get_category_data(request.user)
    
    # 获取活跃商品数量
    active_products = Product.objects.filter(merchant=request.user, status='active').count()
    
    # 创建stats字典供模板使用
    stats = {
        'today_sales': today_sales['total'] or 0,
        'today_orders': today_sales['count'] or 0,
        'month_sales': month_sales['total'] or 0,
        'month_orders': month_sales['count'] or 0,
        'pending_orders': base_stats['pending_orders'],
        'total_products': base_stats['total_products'],
        'active_products': active_products,
    }
    
    context = {
        'stats': stats,
        'sales_data': sales_data,
        'recent_orders': recent_orders,
        'hot_products': hot_products,
        'sales_chart_data': sales_chart_data,
        'category_chart_data': category_chart_data,
        'recent_sales': recent_sales,
    }
    
    return render(request, 'merchant/dashboard.html', context)


@login_required
def product_management(request):
    """商品管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    products = Product.objects.filter(merchant=merchant).order_by('-created_at')
    
    # 搜索和筛选
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(name_zh__icontains=search_query) |
            Q(sku__icontains=search_query)
        )
    
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    if status_filter:
        products = products.filter(status=status_filter)
    
    # 分页
    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    categories = Category.objects.filter(
        Q(merchant=merchant) | Q(merchant__isnull=True)
    )
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'merchant/product_list.html', context)


@login_required
def add_product(request):
    """添加商品"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, merchant=merchant)
        if form.is_valid():
            product = form.save(commit=False)
            product.merchant = merchant
            product.save()
            
            # 处理商品图片
            _get_product_images(request, product)
            
            messages.success(request, '商品添加成功！')
            return redirect('merchants:product_management')
        else:
            messages.error(request, '商品信息有误，请检查后重试。')
    else:
        form = ProductForm(merchant=merchant)
    
    return render(request, 'merchant/product_add.html', {'form': form})


@login_required
def edit_product(request, product_id):
    """编辑商品"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id, merchant=merchant)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, merchant=merchant)
        if form.is_valid():
            form.save()
            
            # 处理新的图片
            _get_product_images(request, product)
            
            messages.success(request, '商品更新成功！')
            return redirect('merchants:product_management')
        else:
            messages.error(request, '商品信息有误，请检查后重试。')
    else:
        form = ProductForm(instance=product, merchant=merchant)
    
    context = {
        'form': form,
        'product': product,
    }
    
    return render(request, 'merchant/product_edit.html', context)


@login_required
def delete_product(request, product_id):
    """删除商品"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id, merchant=merchant)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, '商品删除成功！')
    
    return redirect('merchants:product_management')


@login_required
def order_management(request):
    """订单管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取该商家的所有订单
    orders = Order.objects.filter(
        order_items__product__merchant=merchant
    ).distinct().order_by('-created_at')
    
    # 计算订单统计
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'processing': orders.filter(status='processing').count(),
        'shipped': orders.filter(status='shipped').count(),
        'delivered': orders.filter(status='delivered').count(),
        'completed': orders.filter(status='completed').count(),
        'cancelled': orders.filter(status='cancelled').count(),
    }
    
    # 筛选
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date=filter_date)
        except ValueError:
            pass
    
    # 分页
    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'orders': orders,
        'page_obj': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'merchant/order_list.html', context)


@login_required
def order_detail(request, order_id):
    """订单详情"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    order = get_object_or_404(
        Order.objects.filter(order_items__product__merchant=merchant).distinct(),
        id=order_id
    )
    
    order_items = order.order_items.filter(product__merchant=merchant)
    
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, '订单状态更新成功！')
            return redirect('merchants:order_detail', order_id=order_id)
    else:
        form = OrderStatusForm(instance=order)
    
    context = {
        'order': order,
        'order_items': order_items,
        'form': form,
    }
    
    return render(request, 'merchant/order_detail.html', context)


@login_required
def customer_management(request):
    """客户管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取购买过该商家商品的客户
    customers = CustomUser.objects.filter(
        orders__order_items__product__merchant=merchant
    ).distinct()
    
    # 搜索
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query)
        )
    
    # 获取客户统计信息
    customer_stats = _get_customer_stats(merchant, customers)
    
    # 为每个客户计算统计信息
    processed_customers = [_process_customer_data(customer, merchant) for customer in customers]
    
    # 按消费金额排序
    processed_customers.sort(key=lambda x: x.total_spent, reverse=True)
    
    # 分页
    paginator = Paginator(processed_customers, 20)
    customers_page = paginator.get_page(request.GET.get('page'))
    
    # 生成图表数据
    chart_data = _get_customer_chart_data(customers)
    
    context = {
        'customers': customers_page,
        'search_query': search_query,
        'total_customers': customer_stats['total'],
        'active_customers': customer_stats['active'],
        'new_customers': customer_stats['new'],
        'churned_customers': customer_stats['churned'],
        'customer_growth': customer_stats['growth'],
        # 图表数据
        'customer_type_labels': json.dumps(chart_data['customer_type_labels']),
        'customer_type_data': json.dumps(chart_data['customer_type_data']),
        'growth_labels': json.dumps(chart_data['growth_labels']),
        'growth_data': json.dumps(chart_data['growth_data']),
    }
    
    return render(request, 'merchant/customer_management.html', context)


@login_required
def merchant_profile(request):
    """商家信息管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    if request.method == 'POST':
        form = MerchantProfileForm(request.POST, instance=merchant)
        if form.is_valid():
            form.save()
            messages.success(request, '商家信息更新成功！')
            return redirect('merchants:merchant_profile')
    else:
        form = MerchantProfileForm(instance=merchant)
    
    return render(request, 'merchant/profile.html', {'form': form})


@login_required
def merchant_info(request):
    """商家信息页面"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取省份数据
    provinces = Province.objects.all()
    
    # 获取当前商家对应的城市和区县数据
    cities = []
    districts = []
    
    if merchant.province:
        cities = City.objects.filter(province__code=merchant.province)
    
    if merchant.city:
        districts = District.objects.filter(city__code=merchant.city)
    
    context = {
        'merchant': merchant,
        'provinces': provinces,
        'cities': cities,
        'districts': districts,
    }
    
    return render(request, 'merchant/merchant_info.html', context)


@login_required
def merchant_info_update(request):
    """更新商家信息"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '用户没有商家资料'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '只支持POST请求'})
    
    merchant = request.user.merchant_profile
    
    try:
        # 更新基本信息
        merchant.store_name = request.POST.get('store_name', merchant.store_name)
        merchant.store_description = request.POST.get('store_description', merchant.store_description)
        merchant.contact_name = request.POST.get('contact_name', merchant.contact_name)
        merchant.contact_phone = request.POST.get('contact_phone', merchant.contact_phone)
        merchant.contact_email = request.POST.get('contact_email', merchant.contact_email)
        
        # 更新营业信息
        merchant.business_status = request.POST.get('business_status', merchant.business_status)
        merchant.business_hours = request.POST.get('business_hours', merchant.business_hours)
        merchant.rest_days = request.POST.get('rest_days', merchant.rest_days)
        merchant.shipping_time = int(request.POST.get('shipping_time', merchant.shipping_time))
        
        # 处理配送方式
        shipping_methods = request.POST.getlist('shipping_methods')
        merchant.shipping_methods = shipping_methods
        
        # 更新地址信息
        merchant.province = request.POST.get('province', merchant.province)
        merchant.city = request.POST.get('city', merchant.city)
        merchant.district = request.POST.get('district', merchant.district)
        merchant.address = request.POST.get('address', merchant.address)
        merchant.postal_code = request.POST.get('postal_code', merchant.postal_code)
        
        # 处理店铺Logo上传
        if 'store_logo' in request.FILES:
            merchant.store_logo = request.FILES['store_logo']
        
        merchant.save()
        
        return JsonResponse({
            'success': True, 
            'message': '商家信息更新成功！',
            'redirect_url': reverse('merchants:merchant_info')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'更新失败：{str(e)}'
        })


@login_required
def get_cities(request):
    """获取城市列表"""
    province_code = request.GET.get('province_code')
    if not province_code:
        return JsonResponse({'cities': []})
    
    cities = City.objects.filter(province__code=province_code).values('code', 'name')
    return JsonResponse({'cities': list(cities)})


@login_required
def get_districts(request):
    """获取区县列表"""
    city_code = request.GET.get('city_code')
    if not city_code:
        return JsonResponse({'districts': []})
    
    districts = District.objects.filter(city__code=city_code).values('code', 'name')
    return JsonResponse({'districts': list(districts)})


@login_required
def financial_management(request):
    """财务管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取财务数据
    total_revenue = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed'
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 今日收入
    today_start, today_end = _get_date_range(0)
    today_revenue = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__gte=today_start,
        order__created_at__lt=today_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 昨日收入对比
    yesterday_start, yesterday_end = _get_date_range(1)
    yesterday_revenue = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__gte=yesterday_start,
        order__created_at__lt=yesterday_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    today_revenue_change = 0
    if yesterday_revenue > 0:
        today_revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue) * 100
    
    # 本月收入
    month_start, month_end = _get_monthly_date_range(0)
    monthly_revenue_value = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__gte=month_start,
        order__created_at__lt=month_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 上月收入对比
    last_month_start, last_month_end = _get_monthly_date_range(1)
    last_month_revenue = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__gte=last_month_start,
        order__created_at__lt=last_month_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    month_revenue_change = 0
    if last_month_revenue > 0:
        month_revenue_change = ((monthly_revenue_value - last_month_revenue) / last_month_revenue) * 100
    
    # 可提现余额（简化计算：总收入的90%）
    available_balance = total_revenue * 0.9
    frozen_balance = total_revenue * 0.1  # 10%作为保证金
    
    # 待结算金额（最近7天的收入）
    seven_days_ago = timezone.now() - timedelta(days=7)
    pending_settlement = OrderItem.objects.filter(
        product__merchant=merchant,
        order__status='completed',
        order__created_at__date__gte=seven_days_ago
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 月度收入趋势数据
    monthly_revenue = []
    for i in range(12):
        month_start, month_end = _get_monthly_date_range(i)
        
        month_sales = OrderItem.objects.filter(
            product__merchant=merchant,
            order__status='completed',
            order__created_at__gte=month_start,
            order__created_at__lt=month_end
        ).aggregate(total=Sum('price_at_purchase'))
        
        monthly_revenue.append({
            'month': month_start.strftime('%Y-%m'),
            'revenue': month_sales['total'] or 0
        })
    
    monthly_revenue.reverse()
    
    context = {
        'total_revenue': total_revenue,
        'monthly_revenue': json.dumps(monthly_revenue),
        'today_revenue': today_revenue,
        'today_revenue_change': round(today_revenue_change, 1),
        'monthly_revenue_value': monthly_revenue_value,
        'month_revenue_change': round(month_revenue_change, 1),
        'available_balance': available_balance,
        'frozen_balance': frozen_balance,
        'pending_settlement': pending_settlement,
        'transactions': [],  # 简化处理，实际应该有Transaction模型
    }
    
    return render(request, 'merchant/financial_management.html', context)


@login_required
def inventory_management(request):
    """库存管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    products = Product.objects.filter(merchant=merchant).order_by('stock_quantity')
    
    # 库存统计
    total_products = products.count()
    out_of_stock = products.filter(stock_quantity=0).count()
    low_stock = products.filter(stock_quantity__gt=0, stock_quantity__lt=10).count()
    sufficient_stock = products.filter(stock_quantity__gte=10).count()
    
    # 库存预警
    low_stock_products = products.filter(stock_quantity__lt=10)
    
    context = {
        'inventory_items': products,
        'total_products': total_products,
        'sufficient_stock': sufficient_stock,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'low_stock_products': low_stock_products,
    }
    
    return render(request, 'merchant/inventory_management.html', context)


@login_required
def update_inventory(request, product_id):
    """更新库存"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id, merchant=merchant)
    
    if request.method == 'POST':
        form = InventoryUpdateForm(request.POST)
        if form.is_valid():
            product.stock_quantity = form.cleaned_data['stock_quantity']
            product.save()
            messages.success(request, '库存更新成功！')
            return redirect('merchants:inventory_management')
    else:
        form = InventoryUpdateForm(initial={'stock_quantity': product.stock_quantity})
    
    return render(request, 'merchant/inventory_management.html', {
        'product': product,
        'form': form
    })


@login_required
def analytics_dashboard(request):
    """数据分析面板"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 30天数据
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # 销售趋势
    sales_data = []
    for i in range(30):
        day_start, day_end = _get_date_range(i)
        
        day_orders = Order.objects.filter(
            order_items__product__merchant=merchant,
            created_at__gte=day_start,
            created_at__lt=day_end,
            status__in=['completed']
        ).distinct()
        
        day_revenue = OrderItem.objects.filter(
            order__in=day_orders,
            product__merchant=merchant
        ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
        
        sales_data.append({
            'date': day_start.strftime('%m-%d'),
            'revenue': day_revenue,
            'orders': day_orders.count(),
        })
    
    # 热门商品
    popular_products = Product.objects.filter(
        merchant=merchant,
        order_items__order__created_at__gte=thirty_days_ago,
        order_items__order__status='completed'
    ).annotate(
        total_sold=Sum('order_items__quantity'),
        total_revenue=Sum('order_items__price_at_purchase')
    ).order_by('-total_sold')[:10]
    
    context = {
        'sales_data': sales_data,
        'popular_products': popular_products,
    }
    
    return render(request, 'merchant/analytics_dashboard.html', context)


@login_required
def purchase_management(request):
    """采购管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    products = Product.objects.filter(merchant=merchant)
    
    # 基于销售数据推荐采购
    recommended_products = []
    for product in products:
        # 计算最近30天的平均销量
        recent_sales = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=timezone.now() - timedelta(days=30),
            order__status='completed'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        avg_daily_sales = recent_sales / 30
        current_stock = product.stock_quantity
        
        # 如果库存少于7天销量，建议采购
        if current_stock < avg_daily_sales * 7:
            recommended_products.append({
                'product': product,
                'avg_daily_sales': avg_daily_sales,
                'current_stock': current_stock,
                'recommended_quantity': int(avg_daily_sales * 30)  # 建议采购30天库存
            })
    
    context = {
        'recommended_products': recommended_products,
    }
    
    return render(request, 'merchant/purchase_management.html', context)


@login_required
def promotions(request):
    """促销活动管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 模拟一些促销活动数据
    promotions_data = [
        {
            'id': 1,
            'name': '新品上市8折优惠',
            'description': '所有新品享受8折优惠',
            'discount_type': 'percentage',
            'discount_value': 20,
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() + timedelta(days=7),
            'is_active': True,
            'products_count': Product.objects.filter(merchant=merchant, status='active').count()
        },
        {
            'id': 2,
            'name': '满100减20',
            'description': '订单满100元减20元',
            'discount_type': 'fixed',
            'discount_value': 20,
            'min_order_amount': 100,
            'start_date': timezone.now().date() - timedelta(days=3),
            'end_date': timezone.now().date() + timedelta(days=14),
            'is_active': True,
            'products_count': 0  # 适用于全店
        }
    ]
    
    context = {
        'promotions': promotions_data,
    }
    
    return render(request, 'merchant/promotions.html', context)
