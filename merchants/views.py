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
    from products.models import ProductImage
    
    # 处理主图
    main_image = request.FILES.get('main_image')
    if main_image:
        ProductImage.objects.create(
            product=product,
            image=main_image,
            alt_text=product.name,
            is_primary=True
        )
    
    # 处理附加图片
    additional_images = request.FILES.getlist('additional_images')
    for i, image in enumerate(additional_images):
        # 如果已经有主图，附加图片不设为主图
        is_primary = (i == 0 and not product.images.filter(is_primary=True).exists() and not main_image)
        ProductImage.objects.create(
            product=product,
            image=image,
            alt_text=product.name,
            is_primary=is_primary
        )


def _get_base_stats(user):
    """获取基础统计数据"""
    return {
        'total_products': Product.objects.filter(merchant=user).count(),
        'pending_orders': Order.objects.filter(
            order_items__product__merchant=user,
            status__in=['pending', 'confirmed']
        ).distinct().count(),
        'completed_orders': Order.objects.filter(
            order_items__product__merchant=user,
            status='delivered'
        ).distinct().count(),
    }


def _get_sales_stats(user, days=30):
    """获取销售统计"""
    return OrderItem.objects.filter(
        product__merchant=user,
        order__status='delivered',
        order__created_at__gte=timezone.now() - timedelta(days=days)
    ).aggregate(
        total_amount=Sum('price_at_purchase'),
        total_quantity=Sum('quantity')
    )


def _get_daily_sales(user, days=7):
    """获取每日销售数据"""
    sales_data = {'labels': [], 'sales': [], 'orders': []}
    
    for i in range(days-1, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        day_start, day_end = _get_date_range(i)
        
        day_orders = Order.objects.filter(
            order_items__product__merchant=user,
            created_at__gte=day_start,
            created_at__lt=day_end
        ).distinct()
        
        day_sales = OrderItem.objects.filter(
            order__in=day_orders,
            product__merchant=user,
            order__status='delivered'
        ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
        
        sales_data['labels'].append(date.strftime('%m-%d'))
        sales_data['sales'].append(float(day_sales))
        sales_data['orders'].append(day_orders.count())
    
    return sales_data


def _get_category_data(user):
    """获取商品分类数据"""
    category_data = Product.objects.filter(
        merchant=user
    ).values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')[:6]
    
    # 安全处理分类名称，确保UTF-8编码
    labels = []
    for item in category_data:
        category_name = item['category__name']
        if category_name:
            # 确保字符串是有效的UTF-8编码
            if isinstance(category_name, str):
                try:
                    # 尝试编码为UTF-8，如果失败则使用默认值
                    category_name.encode('utf-8')
                    labels.append(category_name)
                except UnicodeEncodeError:
                    labels.append('分类')
            else:
                labels.append('分类')
        else:
            labels.append('未分类')
    
    return {
        'labels': labels,
        'data': [item['count'] for item in category_data]
    }


def _get_customer_stats(user, customers):
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
            orders__order_items__product__merchant=user,
            orders__created_at__gte=thirty_days_ago
        ).distinct().count(),
        'new': new_customers,
        'churned': customers.exclude(
            orders__order_items__product__merchant=user,
            orders__created_at__gte=timezone.now() - timedelta(days=90)
        ).distinct().count(),
        'growth': round(customer_growth, 1)
    }


def _process_customer_data(customer, user):
    """处理客户数据，添加统计信息"""
    # 计算订单统计
    customer.total_orders = Order.objects.filter(
        customer=customer,
        order_items__product__merchant=user
    ).distinct().count()
    
    # 计算消费统计
    customer.total_spent = OrderItem.objects.filter(
        order__customer=customer,
        product__merchant=user,
        order__status='delivered'
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 计算平均订单价值
    customer.avg_order_value = customer.total_spent / customer.total_orders if customer.total_orders > 0 else 0
    
    # 获取最近订单日期
    last_order = Order.objects.filter(
        customer=customer,
        order_items__product__merchant=user
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
        order__status='delivered',
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
        order__status='delivered',
        order__created_at__gte=month_start,
        order__created_at__lt=month_end
    ).aggregate(
        total=Sum('price_at_purchase'),
        count=Count('id')
    )
    
    # 生成图表数据并转换为JSON字符串
    sales_chart_data = json.dumps(_get_daily_sales(request.user), ensure_ascii=False)
    category_chart_data = json.dumps(_get_category_data(request.user), ensure_ascii=False)
    
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
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    products = Product.objects.filter(merchant=request.user).order_by('-created_at')
    
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
    
    # 获取所有分类（包括商家已使用的分类和系统分类）
    categories = Category.objects.filter(
        Q(products__merchant=request.user) | Q(products__isnull=True)
    ).distinct()
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,  # 为了兼容模板，同时传递products
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
            # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）
            product.merchant = request.user
            product.save()
            
            # 处理商品图片
            _get_product_images(request, product)
            
            messages.success(request, '商品添加成功！')
            return redirect('merchants:product_list')
        else:
            messages.error(request, '商品信息有误，请检查后重试。')
    else:
        form = ProductForm(merchant=merchant)
    
    # 获取所有分类数据传递给模板
    categories = Category.objects.all()
    
    return render(request, 'merchant/product_add.html', {
        'form': form,
        'categories': categories
    })


@login_required
def edit_product(request, product_id):
    """编辑商品"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    product = get_object_or_404(Product, id=product_id, merchant=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, merchant=merchant)
        if form.is_valid():
            form.save()
            
            # 处理新的图片
            _get_product_images(request, product)
            
            messages.success(request, '商品更新成功！')
            return redirect('merchants:product_list')
        else:
            messages.error(request, '商品信息有误，请检查后重试。')
    else:
        form = ProductForm(instance=product, merchant=merchant)
    
    # 获取所有分类数据传递给模板
    categories = Category.objects.all()
    
    context = {
        'form': form,
        'product': product,
        'categories': categories,
    }
    
    return render(request, 'merchant/product_edit.html', context)


@login_required
def delete_product(request, product_id):
    """删除商品"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    product = get_object_or_404(Product, id=product_id, merchant=request.user)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, '商品删除成功！')
    
    return redirect('merchants:product_list')


@login_required
def order_management(request):
    """订单管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取该商家的所有订单
    orders = Order.objects.filter(
        order_items__product__merchant=request.user
    ).distinct().order_by('-created_at')
    
    # 计算订单统计
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'processing': orders.filter(status='processing').count(),
        'shipped': orders.filter(status='shipped').count(),
        'delivered': orders.filter(status='delivered').count(),
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
        'orders': page_obj,  # 使用分页后的订单对象
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
        Order.objects.filter(order_items__product__merchant=request.user).distinct(),
        id=order_id
    )
    
    order_items = order.order_items.filter(product__merchant=request.user)
    
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
def order_ship(request, order_id):
    """订单发货"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    order = get_object_or_404(
        Order.objects.filter(order_items__product__merchant=request.user).distinct(),
        id=order_id
    )
    
    if request.method == 'POST':
        # 处理发货表单提交
        tracking_number = request.POST.get('tracking_number')
        shipping_company = request.POST.get('shipping_company')
        
        if tracking_number and shipping_company:
            order.tracking_number = tracking_number
            order.shipping_company = shipping_company
            order.status = 'shipped'
            order.shipped_at = timezone.now()
            order.save()
            
            messages.success(request, '订单发货成功！')
            return redirect('merchants:order_detail', order_id=order_id)
        else:
            messages.error(request, '请填写完整的发货信息！')
    
    # 如果是GET请求，显示发货表单
    context = {
        'order': order,
    }
    
    return render(request, 'merchant/order_ship.html', context)


@login_required
def customer_management(request):
    """客户管理"""
    merchant = _get_merchant_or_redirect(request.user)
    if not merchant:
        return redirect('home')
    
    # 获取购买过该商家商品的客户
    customers = CustomUser.objects.filter(
        orders__order_items__product__merchant=request.user
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
    customer_stats = _get_customer_stats(request.user, customers)
    
    # 为每个客户计算统计信息
    processed_customers = [_process_customer_data(customer, request.user) for customer in customers]
    
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
        product__merchant=request.user,
        order__status='delivered'
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 今日收入
    today_start, today_end = _get_date_range(0)
    today_revenue = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='delivered',
        order__created_at__gte=today_start,
        order__created_at__lt=today_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 昨日收入对比
    yesterday_start, yesterday_end = _get_date_range(1)
    yesterday_revenue = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='delivered',
        order__created_at__gte=yesterday_start,
        order__created_at__lt=yesterday_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    today_revenue_change = 0
    if yesterday_revenue > 0:
        today_revenue_change = ((today_revenue - yesterday_revenue) / yesterday_revenue) * 100
    
    # 本月收入
    month_start, month_end = _get_monthly_date_range(0)
    monthly_revenue_value = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='delivered',
        order__created_at__gte=month_start,
        order__created_at__lt=month_end
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 上月收入对比
    last_month_start, last_month_end = _get_monthly_date_range(1)
    last_month_revenue = OrderItem.objects.filter(
        product__merchant=request.user,
        order__status='delivered',
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
        product__merchant=request.user,
        order__status='delivered',
        order__created_at__date__gte=seven_days_ago
    ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    # 月度收入趋势数据
    monthly_revenue = []
    for i in range(12):
        month_start, month_end = _get_monthly_date_range(i)
        
        month_sales = OrderItem.objects.filter(
            product__merchant=request.user,
            order__status='delivered',
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
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    products = Product.objects.filter(merchant=request.user).order_by('stock_quantity')
    
    # 库存统计
    total_products = products.count()
    out_of_stock = products.filter(stock_quantity=0).count()
    low_stock = products.filter(stock_quantity__gt=0, stock_quantity__lt=10).count()
    sufficient_stock = products.filter(stock_quantity__gte=10).count()
    
    # 库存预警
    low_stock_products = products.filter(stock_quantity__lt=10)
    
    # 获取所有分类数据传递给模板
    categories = Category.objects.all()
    
    context = {
        'inventory_items': products,
        'total_products': total_products,
        'sufficient_stock': sufficient_stock,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'low_stock_products': low_stock_products,
        'categories': categories,
    }
    
    return render(request, 'merchant/inventory_management.html', context)


@login_required
def update_inventory(request, product_id):
    """更新库存"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    product = get_object_or_404(Product, id=product_id, merchant=request.user)
    
    if request.method == 'POST':
        try:
            new_stock = request.POST.get('new_stock')
            reason = request.POST.get('reason', '')
            
            if not new_stock:
                return JsonResponse({'success': False, 'message': '请填写库存数量'})
            
            try:
                new_stock = int(new_stock)
                if new_stock < 0:
                    return JsonResponse({'success': False, 'message': '库存数量不能为负数'})
                
                # 更新库存
                product.stock_quantity = new_stock
                product.save()
                
                return JsonResponse({'success': True, 'message': '库存更新成功'})
                
            except ValueError:
                return JsonResponse({'success': False, 'message': '无效的库存数量格式'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'更新失败：{str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


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
            order_items__product__merchant=request.user,  # 修复：使用 request.user
            created_at__gte=day_start,
            created_at__lt=day_end,
            status__in=['delivered']
        ).distinct()
        
        day_revenue = OrderItem.objects.filter(
            order__in=day_orders,
            product__merchant=request.user  # 修复：使用 request.user
        ).aggregate(total=Sum('price_at_purchase'))['total'] or 0
        
        sales_data.append({
            'date': day_start.strftime('%m-%d'),
            'revenue': day_revenue,
            'orders': day_orders.count(),
        })
    
    # 热门商品
    popular_products = Product.objects.filter(
        merchant=request.user,  # 修复：使用 request.user
        orderitem__order__created_at__gte=thirty_days_ago,
        orderitem__order__status='delivered'
    ).annotate(
        total_sold=Sum('orderitem__quantity'),
        total_revenue=Sum('orderitem__price_at_purchase')
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
    
    # 修复：使用 request.user（CustomUser）而不是 merchant（MerchantProfile）来查询商品
    products = Product.objects.filter(merchant=request.user)
    
    # 基于销售数据推荐采购
    recommended_products = []
    for product in products:
        # 计算最近30天的平均销量
        recent_sales = OrderItem.objects.filter(
            product=product,
            order__created_at__gte=timezone.now() - timedelta(days=30),
            order__status='delivered'
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
            'products_count': Product.objects.filter(merchant=request.user, status='active').count()  # 修复：使用 request.user
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


@login_required
def batch_ship(request):
    """批量发货"""
    if not hasattr(request.user, 'merchant_profile'):
        return redirect('home')
    
    order_ids = request.GET.get('ids', '')
    if not order_ids:
        messages.error(request, '没有选择订单')
        return redirect('merchants:order_management')
    
    order_ids = [int(id) for id in order_ids.split(',') if id.isdigit()]
    
    # 获取属于当前商家的订单
    orders = Order.objects.filter(
        id__in=order_ids,
        orderitem__product__merchant=request.user,
        status__in=['confirmed', 'processing']
    ).distinct()
    
    if request.method == 'POST':
        # 处理批量发货
        tracking_numbers = request.POST.getlist('tracking_number')
        shipping_companies = request.POST.getlist('shipping_company')
        
        success_count = 0
        for i, order in enumerate(orders):
            if i < len(tracking_numbers) and tracking_numbers[i]:
                # 更新订单状态为已发货
                order.status = 'shipped'
                order.save()
                
                # 创建物流信息（简化处理）
                # 实际应该创建物流记录
                success_count += 1
        
        messages.success(request, f'成功发货 {success_count} 个订单')
        return redirect('merchants:order_management')
    
    context = {
        'orders': orders,
        'shipping_companies': ['顺丰速运', '圆通快递', '中通快递', '申通快递', '韵达快递', '百世汇通']
    }
    
    return render(request, 'merchant/batch_ship.html', context)


@login_required
def order_export(request):
    """导出订单"""
    if not hasattr(request.user, 'merchant_profile'):
        return redirect('home')
    
    # 获取筛选参数
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # 查询当前商家的订单
    orders = Order.objects.filter(
        orderitem__product__merchant=request.user
    ).distinct().order_by('-created_at')
    
    # 应用筛选条件
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
    
    # 创建CSV响应
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    # 添加BOM以支持Excel正确显示中文
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow(['订单号', '客户', '总金额', '状态', '支付方式', '创建时间', '发货时间', '完成时间'])
    
    for order in orders:
        writer.writerow([
            order.order_number,
            order.customer.username,
            order.total_amount,
            order.get_status_display(),
            order.payment_method,
            order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            order.shipped_at.strftime('%Y-%m-%d %H:%M:%S') if order.shipped_at else '',
            order.completed_at.strftime('%Y-%m-%d %H:%M:%S') if order.completed_at else ''
        ])
    
    return response


@login_required
def order_status_update(request):
    """订单状态更新检查"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'error': '没有权限'})
    
    # 获取最近更新的订单（简化实现）
    # 实际应该检查物流API或其他状态更新源
    updated_orders = []
    
    # 模拟一些状态更新
    recent_orders = Order.objects.filter(
        order_items__product__merchant=request.user,
        status='shipped',
        shipped_at__gte=timezone.now() - timedelta(hours=1)
    ).distinct()[:5]
    
    for order in recent_orders:
        # 模拟状态更新为已送达
        if order.status == 'shipped' and order.shipped_at < timezone.now() - timedelta(hours=2):
            order.status = 'delivered'
            order.save()
            updated_orders.append({
                'id': order.id,
                'status': 'delivered',
                'status_display': order.get_status_display()
            })
    
    return JsonResponse({
        'updated_orders': updated_orders,
        'new_orders_count': 0
    })


@login_required
def new_orders_check(request):
    """检查新订单"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'error': '没有权限'})
    
    # 获取最近1小时内的新订单
    new_orders = Order.objects.filter(
        order_items__product__merchant=request.user,
        status='pending',
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).distinct()
    
    new_orders_count = new_orders.count()
    
    return JsonResponse({
        'new_orders_count': new_orders_count,
        'play_sound': new_orders_count > 0  # 如果有新订单，播放提示音
    })


@login_required
def order_cancel(request, order_id):
    """取消订单"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    order = get_object_or_404(Order, pk=order_id)
    
    # 检查订单是否属于当前商家
    if not order.order_items.filter(product__merchant=request.user).exists():
        return JsonResponse({'success': False, 'message': '订单不属于您的店铺'})
    
    # 检查订单状态是否可以取消
    if order.status not in ['pending', 'confirmed']:
        return JsonResponse({'success': False, 'message': '当前订单状态无法取消'})
    
    # 取消订单
    order.status = 'cancelled'
    order.save()
    
    messages.success(request, '订单已取消')
    return redirect('merchants:order_detail', order_id=order_id)


@login_required
def order_print(request, order_id):
    """打印订单"""
    if not hasattr(request.user, 'merchant_profile'):
        messages.error(request, '无权限访问')
        return redirect('accounts:login')
    
    order = get_object_or_404(Order, pk=order_id)
    
    # 检查订单是否属于当前商家
    if not order.order_items.filter(product__merchant=request.user).exists():
        messages.error(request, '订单不属于您的店铺')
        return redirect('merchants:order_list')
    
    # 渲染打印模板
    context = {
        'order': order,
        'merchant': request.user.merchant_profile,
    }
    return render(request, 'merchant/order_print.html', context)


@login_required
def order_message(request, order_id):
    """订单消息"""
    if not hasattr(request.user, 'merchant_profile'):
        messages.error(request, '无权限访问')
        return redirect('accounts:login')
    
    order = get_object_or_404(Order, pk=order_id)
    
    # 检查订单是否属于当前商家
    if not order.order_items.filter(product__merchant=request.user).exists():
        messages.error(request, '订单不属于您的店铺')
        return redirect('merchants:order_list')
    
    if request.method == 'POST':
        message_content = request.POST.get('message', '').strip()
        if message_content:
            # 这里应该创建订单消息记录
            # 简化处理，直接显示成功消息
            messages.success(request, '消息已发送')
            return redirect('merchants:order_detail', order_id=order_id)
    
    context = {
        'order': order,
    }
    return render(request, 'merchant/order_message.html', context)


@login_required
def stock_history(request, product_id):
    """库存历史"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    product = get_object_or_404(Product, id=product_id, merchant=request.user)
    
    # 这里应该查询库存历史记录
    # 简化处理，返回模拟数据
    history_data = [
        {'date': '2025-01-15', 'type': '入库', 'quantity': 100, 'current_stock': 150},
        {'date': '2025-01-10', 'type': '出库', 'quantity': -20, 'current_stock': 50},
        {'date': '2025-01-05', 'type': '入库', 'quantity': 70, 'current_stock': 70},
    ]
    
    return JsonResponse({'success': True, 'history': history_data})


@login_required
def export_inventory(request):
    """导出库存"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    # 获取筛选参数
    category = request.GET.get('category', '')
    stock_status = request.GET.get('stock_status', '')
    
    # 查询商品库存
    products = Product.objects.filter(merchant=request.user)
    
    if category:
        products = products.filter(category__name=category)
    
    if stock_status == 'low':
        products = products.filter(stock__lte=10)
    elif stock_status == 'out':
        products = products.filter(stock=0)
    
    # 创建CSV响应
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['商品名称', 'SKU', '分类', '库存', '价格', '状态'])
    
    for product in products:
        writer.writerow([
            product.name,
            product.sku or '',
            product.category.name if product.category else '',
            product.stock,
            product.price,
            '有货' if product.stock > 0 else '缺货'
        ])
    
    return response


@login_required
def download_inventory_template(request):
    """下载库存模板"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    # 创建CSV模板
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="inventory_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['商品名称', 'SKU', '分类', '库存', '价格', '描述'])
    writer.writerow(['示例商品', 'SKU001', '电子产品', '100', '99.99', '商品描述'])
    
    return response


@login_required
def bulk_add_customer_tags(request):
    """批量添加客户标签"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        customer_ids = request.POST.getlist('customer_ids[]')
        tags = request.POST.get('tags', '').strip()
        
        if not customer_ids or not tags:
            return JsonResponse({'success': False, 'message': '请选择客户并输入标签'})
        
        # 这里应该实现批量添加标签的逻辑
        # 简化处理，直接返回成功
        return JsonResponse({'success': True, 'message': f'已为 {len(customer_ids)} 个客户添加标签'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def customer_export(request):
    """导出客户"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    # 获取筛选参数
    registration_date = request.GET.get('registration_date', '')
    order_count_min = request.GET.get('order_count_min', '')
    total_spent_min = request.GET.get('total_spent_min', '')
    
    # 这里应该查询客户数据
    # 简化处理，返回空CSV
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="customers_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['客户姓名', '邮箱', '电话', '注册时间', '订单数', '总消费'])
    
    return response


@login_required
def withdrawal_request(request):
    """提现申请"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        amount = request.POST.get('amount', '')
        bank_account = request.POST.get('bank_account', '')
        
        if not amount or not bank_account:
            return JsonResponse({'success': False, 'message': '请填写完整的提现信息'})
        
        try:
            amount = float(amount)
            if amount <= 0:
                return JsonResponse({'success': False, 'message': '提现金额必须大于0'})
            
            # 这里应该创建提现申请记录
            # 简化处理，直接返回成功
            return JsonResponse({'success': True, 'message': '提现申请已提交'})
            
        except ValueError:
            return JsonResponse({'success': False, 'message': '无效的金额格式'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def transaction_detail(request):
    """交易详情"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    transaction_id = request.GET.get('id')
    if not transaction_id:
        return JsonResponse({'success': False, 'message': '缺少交易ID'})
    
    # 这里应该查询交易详情
    # 简化处理，返回模拟数据
    transaction_data = {
        'id': transaction_id,
        'type': '订单收入',
        'amount': 299.99,
        'date': '2025-01-15 14:30:25',
        'status': '已完成',
        'description': '订单 #202501150001 收入',
        'balance_after': 1299.99
    }
    
    return JsonResponse({'success': True, 'transaction': transaction_data})


@login_required
def financial_export(request):
    """导出财务数据"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    # 获取筛选参数
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    transaction_type = request.GET.get('transaction_type', '')
    
    # 这里应该查询财务数据
    # 简化处理，返回空CSV
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="financial_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['交易时间', '交易类型', '金额', '余额', '描述'])
    
    return response


@login_required
def purchase_order_detail(request):
    """采购订单详情"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    order_id = request.GET.get('id')
    if not order_id:
        return JsonResponse({'success': False, 'message': '缺少订单ID'})
    
    # 这里应该查询采购订单详情
    # 简化处理，返回模拟数据
    order_data = {
        'id': order_id,
        'order_number': f'PO{order_id}',
        'supplier': '示例供应商',
        'total_amount': 1500.00,
        'status': '已确认',
        'created_at': '2025-01-10 10:00:00',
        'items': [
            {'product_name': '商品A', 'quantity': 50, 'unit_price': 10.00, 'subtotal': 500.00},
            {'product_name': '商品B', 'quantity': 100, 'unit_price': 10.00, 'subtotal': 1000.00}
        ]
    }
    
    return JsonResponse({'success': True, 'order': order_data})


@login_required
def batch_update_stock(request):
    """批量更新库存"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        item_ids = request.POST.get('item_ids', '').split(',')
        update_type = request.POST.get('update_type', '')
        quantity = request.POST.get('quantity', '0')
        reason = request.POST.get('reason', '')
        
        if not item_ids or not update_type or not quantity:
            return JsonResponse({'success': False, 'message': '请填写完整的更新信息'})
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                return JsonResponse({'success': False, 'message': '数量不能为负数'})
            
            # 批量更新库存
            for item_id in item_ids:
                if item_id:
                    try:
                        product = Product.objects.get(id=item_id, merchant=request.user)
                        if update_type == 'set':
                            product.stock_quantity = quantity
                        elif update_type == 'add':
                            product.stock_quantity += quantity
                        elif update_type == 'subtract':
                            product.stock_quantity = max(0, product.stock_quantity - quantity)
                        product.save()
                    except Product.DoesNotExist:
                        continue
            
            return JsonResponse({'success': True, 'message': '批量库存更新成功'})
            
        except ValueError:
            return JsonResponse({'success': False, 'message': '无效的数量格式'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def batch_update_price(request):
    """批量更新价格"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        item_ids = request.POST.get('item_ids', '').split(',')
        update_type = request.POST.get('update_type', '')
        value = request.POST.get('value', '0')
        reason = request.POST.get('reason', '')
        
        if not item_ids or not update_type or not value:
            return JsonResponse({'success': False, 'message': '请填写完整的更新信息'})
        
        try:
            value = float(value)
            if value <= 0:
                return JsonResponse({'success': False, 'message': '价格必须大于0'})
            
            # 批量更新价格
            for item_id in item_ids:
                if item_id:
                    try:
                        product = Product.objects.get(id=item_id, merchant=request.user)
                        if update_type == 'set':
                            product.price = value
                        elif update_type == 'increase_percent':
                            product.price = product.price * (1 + value / 100)
                        elif update_type == 'decrease_percent':
                            product.price = product.price * (1 - value / 100)
                        elif update_type == 'increase_fixed':
                            product.price += value
                        elif update_type == 'decrease_fixed':
                            product.price = max(0, product.price - value)
                        product.save()
                    except Product.DoesNotExist:
                        continue
            
            return JsonResponse({'success': True, 'message': '批量价格更新成功'})
            
        except ValueError:
            return JsonResponse({'success': False, 'message': '无效的价格格式'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def generate_stock_alert(request):
    """生成库存预警"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        # 获取库存不足的商品
        low_stock_products = Product.objects.filter(
            merchant=request.user,
            stock_quantity__lt=10
        ).order_by('stock_quantity')
        
        # 生成预警报告
        alert_data = []
        for product in low_stock_products:
            alert_data.append({
                'product_name': product.name,
                'current_stock': product.stock_quantity,
                'safety_stock': 10,  # 默认安全库存
                'recommended_quantity': max(0, 50 - product.stock_quantity)  # 建议补货到50
            })
        
        return JsonResponse({'success': True, 'message': f'已生成 {len(alert_data)} 个库存预警', 'alerts': alert_data})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def import_inventory(request):
    """导入库存"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        import_type = request.POST.get('import_type', '')
        file = request.FILES.get('file')
        
        if not import_type or not file:
            return JsonResponse({'success': False, 'message': '请选择导入类型和文件'})
        
        try:
            import csv
            import io
            
            # 读取CSV文件
            file_content = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_content))
            
            success_count = 0
            error_count = 0
            
            for row in csv_reader:
                try:
                    # 根据SKU查找商品
                    sku = row.get('SKU', '')
                    product_name = row.get('商品名称', '')
                    stock_quantity = row.get('库存', '')
                    price = row.get('价格', '')
                    
                    if sku:
                        product = Product.objects.filter(sku=sku, merchant=request.user).first()
                    elif product_name:
                        product = Product.objects.filter(name=product_name, merchant=request.user).first()
                    else:
                        continue
                    
                    if product:
                        if stock_quantity and stock_quantity.isdigit():
                            product.stock_quantity = int(stock_quantity)
                        if price and price.replace('.', '').isdigit():
                            product.price = float(price)
                        product.save()
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    continue
            
            return JsonResponse({
                'success': True, 
                'message': f'导入完成！成功 {success_count} 条，失败 {error_count} 条',
                'success_count': success_count
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'导入失败：{str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def create_purchase_order(request):
    """创建采购单"""
    if not hasattr(request.user, 'merchant_profile'):
        return JsonResponse({'success': False, 'message': '无权限访问'})
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            
            if not item_id:
                return JsonResponse({'success': False, 'message': '缺少商品ID'})
            
            # 查找商品
            product = Product.objects.filter(id=item_id, merchant=request.user).first()
            if not product:
                return JsonResponse({'success': False, 'message': '商品不存在'})
            
            # 计算建议采购数量（补货到50）
            recommended_quantity = max(0, 50 - product.stock_quantity)
            
            # 创建采购单（模拟）
            purchase_order_id = f"PO{int(time.time())}"
            
            return JsonResponse({
                'success': True, 
                'message': '采购单创建成功',
                'purchase_order_id': purchase_order_id,
                'recommended_quantity': recommended_quantity
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的请求数据'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'创建失败：{str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})
