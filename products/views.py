from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Avg
from django.core.paginator import Paginator
import json
from .models import Product, Category, Review, Wishlist
from orders.models import OrderItem
from .forms import ReviewForm, CartAddProductForm


def product_list(request):
    """商品列表页面"""
    # 获取查询参数
    category_slug = request.GET.get('category')
    search_query = request.GET.get('search')
    sort_by = request.GET.get('sort', 'created_at')
    
    # 基础查询
    products = Product.objects.filter(status='active')
    
    # 分类筛选
    if category_slug:
        # 由于slug是属性而不是数据库字段，我们需要通过名称来查找分类
        try:
            categories = Category.objects.filter(is_active=True)
            category = None
            for cat in categories:
                if cat.slug == category_slug:
                    category = cat
                    break
            if not category:
                raise Http404("分类不存在")
            products = products.filter(category=category)
        except Exception as e:
            raise Http404("分类不存在")
    
    # 搜索功能
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )
    
    # 排序
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'rating':
        products = products.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:  # 默认按创建时间
        products = products.order_by('-created_at')
    
    # 分页
    paginator = Paginator(products, 12)  # 每页12个商品
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 获取分类列表
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'current_category': category_slug,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    
    return render(request, 'products/product_list.html', context)


def product_detail(request, pk):
    """商品详情页面"""
    product = get_object_or_404(Product, pk=pk, status='active')
    
    # 获取相关商品
    related_products = Product.objects.filter(
        category=product.category,
        status='active'
    ).exclude(pk=product.pk)[:4]
    
    # 获取评价
    reviews = product.reviews.filter(is_verified_purchase=True).order_by('-created_at')
    
    # 计算平均评分
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # 购物车表单
    cart_product_form = CartAddProductForm()
    
    # 评价表单
    if request.user.is_authenticated and request.user.user_type == 'customer':
        review_form = ReviewForm()
        has_purchased = OrderItem.objects.filter(
            product=product,
            order__customer=request.user,
            order__status='delivered'
        ).exists()
        existing_review = reviews.filter(customer=request.user).first()
    else:
        review_form = None
        has_purchased = False
        existing_review = None
    
    context = {
        'product': product,
        'related_products': related_products,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'cart_product_form': cart_product_form,
        'review_form': review_form,
        'has_purchased': has_purchased,
        'existing_review': existing_review,
    }
    
    return render(request, 'products/product_detail.html', context)


@login_required
def add_review(request, pk):
    """添加评价"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.customer = request.user
            review.save()
            messages.success(request, '评价添加成功！')
            return redirect('products:product_detail', pk=pk)
    
    return redirect('products:product_detail', pk=pk)





@login_required
def wishlist_toggle(request, pk):
    """切换心愿单"""
    product = get_object_or_404(Product, pk=pk)
    
    wishlist_item, created = Wishlist.objects.get_or_create(
        customer=request.user,
        product=product
    )
    
    if not created:
        wishlist_item.delete()
        messages.success(request, '已从心愿单移除。')
    else:
        messages.success(request, '已添加到心愿单。')
    
    return redirect('products:product_detail', pk=pk)


@login_required
def wishlist(request):
    """心愿单页面"""
    wishlist_items = Wishlist.objects.filter(customer=request.user).select_related('product')
    
    context = {
        'wishlist_items': wishlist_items,
    }
    
    return render(request, 'products/wishlist.html', context)


def search_suggestions(request):
    """搜索建议"""
    query = request.GET.get('q', '')
    suggestions = []
    
    if len(query) >= 2:
        products = Product.objects.filter(
            name__icontains=query,
            status='active'
        )[:5]
        
        suggestions = [{
            'name': product.name,
            'price': str(product.price),
            'image': product.images.first().image.url if product.images.first() else '',
            'url': product.get_absolute_url(),
        } for product in products]
    
    return render(request, 'products/search_suggestions.html', {
        'suggestions': suggestions
    })


@csrf_exempt
def cart_add(request, product_id):
    """添加商品到购物车 - 使用orders应用的数据库模型（简化版，无需认证）"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        product = get_object_or_404(Product, id=product_id, status='active')
        
        # 处理AJAX JSON请求
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                quantity = int(data.get('quantity', 1))
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({'error': '无效的数据格式'}, status=400)
        else:
            # 处理表单提交
            quantity = int(request.POST.get('quantity', 1))
        
        # 检查库存
        if product.stock_quantity < 1:
            return JsonResponse({'error': '商品库存不足'}, status=400)
        
        if quantity < 1:
            return JsonResponse({'error': '数量必须大于0'}, status=400)
        
        if quantity > product.stock_quantity:
            return JsonResponse({'error': f'库存不足，最多只能购买{product.stock_quantity}件'}, status=400)
        
        # 使用session-based购物车（无需用户登录）
        cart = request.session.get('cart', {})
        
        # 添加或更新商品数量
        product_key = str(product_id)
        if product_key in cart:
            cart[product_key] += quantity
        else:
            cart[product_key] = quantity
        
        # 保存购物车到session
        request.session['cart'] = cart
        
        # 计算购物车商品总数
        cart_items_count = sum(cart.values())
        
        # 返回JSON响应
        return JsonResponse({
            'success': True,
            'message': f'已添加 {product.name} 到购物车！',
            'cart_count': cart_items_count
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': '商品不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def cart_detail(request):
    """购物车详情页面 - 使用session-based购物车"""
    cart_data = request.session.get('cart', {})
    cart_items = []
    total_price = 0
    
    # 获取商品信息
    for product_id, quantity in cart_data.items():
        try:
            product = Product.objects.get(id=product_id, status='active')
            subtotal = product.price * quantity
            total_price += subtotal
            cart_items.append({
                'product_id': product.id,
                'name': product.name,
                'price': product.price,
                'image': product.images.first().image.url if product.images.first() else None,
                'description': product.description,
                'stock': product.stock_quantity,
                'quantity': quantity,
                'subtotal': subtotal,
            })
        except Product.DoesNotExist:
            # 如果商品不存在，从购物车中移除
            del cart_data[product_id]
    
    # 更新session中的购物车
    request.session['cart'] = cart_data
    
    # 运费设置
    shipping_fee = 0 if total_price >= 88 else 10
    
    context = {
        'cart_items': cart_items,
        'total_amount': total_price,
        'shipping_fee': shipping_fee,
        'cart_items_count': sum(cart_data.values()),
    }
    
    return render(request, 'products/cart.html', context)


@csrf_exempt
def cart_remove(request, product_id):
    """从购物车移除商品 - session-based"""
    cart = request.session.get('cart', {})
    product_key = str(product_id)
    
    if product_key in cart:
        del cart[product_key]
        request.session['cart'] = cart
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '商品已从购物车移除',
                'cart_count': sum(cart.values())
            })
    
    return redirect('products:cart')


@csrf_exempt
def cart_clear(request):
    """清空购物车 - session-based"""
    if request.method == 'POST':
        request.session['cart'] = {}
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '购物车已清空',
                'cart_count': 0
            })
    
    return redirect('products:cart')


@csrf_exempt
def cart_update(request, product_id):
    """更新购物车商品数量 - session-based"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        # 首先检查商品是否存在
        product = Product.objects.get(id=product_id, status='active')
        
        # 处理AJAX JSON请求
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                quantity = int(data.get('quantity', 1))
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({'error': '无效的数据格式'}, status=400)
        else:
            # 处理表单提交
            quantity = int(request.POST.get('quantity', 1))
        
        if quantity < 1:
            return JsonResponse({'error': '数量必须大于0'}, status=400)
        
        if quantity > product.stock_quantity:
            return JsonResponse({
                'error': f'库存不足，最多只能购买{product.stock_quantity}件'
            }, status=400)
        
        cart = request.session.get('cart', {})
        product_key = str(product_id)
        
        # 直接更新或添加商品到购物车（不再检查是否存在）
        cart[product_key] = quantity
        request.session['cart'] = cart
        
        # 计算总价
        total_price = 0
        for pid, qty in cart.items():
            try:
                p = Product.objects.get(id=pid, status='active')
                total_price += p.price * qty
            except:
                pass
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': '购物车已更新',
                'cart_count': sum(cart.values()),
                'total_price': float(total_price)
            })
        else:
            return redirect('products:cart')
        
    except Product.DoesNotExist:
        return JsonResponse({'error': '商品不存在'}, status=404)
    except ValueError:
        return JsonResponse({'error': '无效的数量'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
