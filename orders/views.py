from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime
import json

from products.models import Product, ProductImage
from accounts.models import CustomUser, Address
from .models import Order, OrderItem, Cart, CartItem, OrderStatusHistory
from .forms import CheckoutForm


def _get_or_create_cart(user):
    """获取或创建用户购物车"""
    return Cart.objects.get_or_create(user=user)


def _calculate_cart_totals(cart_items):
    """计算购物车总价和相关费用"""
    total_amount = sum(item.get_total_price() for item in cart_items)
    total_items = sum(item.quantity for item in cart_items)
    
    return {
        'total_amount': total_amount,
        'total_items': total_items,
    }


def _parse_json_data(request):
    """解析JSON请求数据"""
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


@login_required
def cart_view(request):
    """购物车页面"""
    cart, created = _get_or_create_cart(request.user)
    cart_items = cart.cart_items.all()
    
    # 为每个购物车项计算小计并添加subtotal属性
    for item in cart_items:
        item.subtotal = item.get_total_price()
    
    totals = _calculate_cart_totals(cart_items)
    
    # 计算运费和税费
    shipping_cost = Decimal('10.00')  # 固定运费
    tax_amount = totals['total_amount'] * Decimal('0.1')  # 10%税率
    total_amount = totals['total_amount'] + shipping_cost + tax_amount
    
    context = {
        'cart_items': cart_items,
        'cart': cart,
        'shipping_cost': shipping_cost,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        **totals,
    }
    
    return render(request, 'products/cart.html', context)


@login_required
def add_to_cart(request, product_id):
    """添加商品到购物车"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        product = get_object_or_404(Product, id=product_id, status='active')
        
        # 检查库存
        if product.stock_quantity < 1:
            return JsonResponse({'error': '商品库存不足'}, status=400)
        
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            return JsonResponse({'error': '数量必须大于0'}, status=400)
        
        if quantity > product.stock_quantity:
            return JsonResponse({'error': f'库存不足，最多只能购买{product.stock_quantity}件'}, status=400)
        
        # 获取或创建购物车
        cart, created = _get_or_create_cart(request.user)
        
        # 检查是否已经在购物车中
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            # 如果已存在，更新数量
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock_quantity:
                return JsonResponse({'error': f'库存不足，最多只能购买{product.stock_quantity}件'}, status=400)
            cart_item.quantity = new_quantity
            cart_item.save()
        
        # 返回成功响应
        return JsonResponse({
            'success': True,
            'message': '商品已添加到购物车',
            'cart_items_count': cart.cart_items.count(),
            'cart_count': cart.cart_items.count()  # 为了兼容性，同时返回两个字段
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': '商品不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def update_cart_item(request, item_id):
    """更新购物车商品数量"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity < 1:
            cart_item.delete()
            message = '商品已从购物车移除'
        else:
            if quantity > cart_item.product.stock_quantity:
                return JsonResponse({'error': f'库存不足，最多只能购买{cart_item.product.stock_quantity}件'}, status=400)
            
            cart_item.quantity = quantity
            cart_item.save()
            message = '购物车已更新'
        
        # 重新计算购物车总价
        cart = cart_item.cart
        cart_items = cart.cart_items.all()
        total_amount = sum(item.get_total_price() for item in cart_items)
        total_items = sum(item.quantity for item in cart_items)
        
        return JsonResponse({
            'success': True,
            'message': message,
            'item_total': cart_item.get_total_price() if quantity > 0 else 0,
            'cart_total': total_amount,
            'cart_items_count': total_items
        })
        
    except CartItem.DoesNotExist:
        return JsonResponse({'error': '商品不在购物车中'}, status=404)


@login_required
def remove_from_cart(request, item_id):
    """从购物车移除商品"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        
        # 重新计算购物车信息
        cart = cart_item.cart
        cart_items = cart.cart_items.all()
        total_amount = sum(item.get_total_price() for item in cart_items)
        total_items = sum(item.quantity for item in cart_items)
        
        return JsonResponse({
            'success': True,
            'message': '商品已从购物车移除',
            'cart_total': total_amount,
            'cart_items_count': total_items
        })
        
    except CartItem.DoesNotExist:
        return JsonResponse({'error': '商品不在购物车中'}, status=404)


@login_required
def clear_cart(request):
    """清空购物车"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart.cart_items.all().delete()
        
        return JsonResponse({
            'success': True,
            'message': '购物车已清空'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def checkout(request):
    """订单结算页面"""
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.cart_items.all()
    
    if not cart_items:
        messages.warning(request, '购物车为空，无法进行结算')
        return redirect('orders:cart')
    
    # 检查商品库存
    for item in cart_items:
        if item.quantity > item.product.stock_quantity:
            messages.error(request, f'商品 "{item.product.name}" 库存不足')
            return redirect('orders:cart')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                # 创建订单
                order = Order.objects.create(
                    customer=request.user,
                    status='pending',
                    shipping_address=form.cleaned_data['shipping_address'],
                    billing_address=form.cleaned_data.get('billing_address', form.cleaned_data['shipping_address']),
                    notes=form.cleaned_data.get('notes', ''),
                    total_amount=sum(item.get_total_price() for item in cart_items),
                    shipping_cost=Decimal('10.00'),  # 固定运费，可根据实际需求调整
                    tax_amount=sum(item.get_total_price() for item in cart_items) * Decimal('0.1'),  # 10%税率
                )
                
                # 创建订单项
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price_at_purchase=cart_item.product.price,
                        product_name=cart_item.product.name,
                        product_sku=cart_item.product.sku,
                    )
                    
                    # 更新商品库存
                    cart_item.product.stock_quantity -= cart_item.quantity
                    cart_item.product.save()
                
                # 清空购物车
                cart.cart_items.all().delete()
                
                # 创建订单状态历史
                OrderStatusHistory.objects.create(
                    order=order,
                    status='pending',
                    changed_by=request.user,
                    notes='订单创建'
                )
                
                messages.success(request, '订单创建成功！')
                return redirect('orders:order_detail', order_id=order.id)
                
            except Exception as e:
                messages.error(request, f'订单创建失败：{str(e)}')
    else:
        # 获取用户的默认地址
        default_address = Address.objects.filter(user=request.user, is_default=True).first()
        initial_data = {}
        if default_address:
            initial_data['shipping_address'] = default_address.id
        
        form = CheckoutForm(initial=initial_data)
    
    context = {
        'cart_items': cart_items,
        'total_amount': sum(item.get_total_price() for item in cart_items),
        'shipping_cost': Decimal('10.00'),
        'tax_amount': sum(item.get_total_price() for item in cart_items) * Decimal('0.1'),
        'final_total': sum(item.get_total_price() for item in cart_items) + Decimal('10.00') + sum(item.get_total_price() for item in cart_items) * Decimal('0.1'),
        'form': form,
    }
    
    return render(request, 'orders/checkout.html', context)


@login_required
def create_order(request):
    """创建订单（AJAX）"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.cart_items.all()
    
    if not cart_items:
        return JsonResponse({'error': '购物车为空'}, status=400)
    
    try:
        # 检查库存
        for item in cart_items:
            if item.quantity > item.product.stock_quantity:
                return JsonResponse({'error': f'商品 "{item.product.name}" 库存不足'}, status=400)
        
        # 创建订单
        order = Order.objects.create(
            customer=request.user,
            status='pending',
            shipping_address_id=request.POST.get('shipping_address'),
            notes=request.POST.get('notes', ''),
            total_amount=sum(item.get_total_price() for item in cart_items),
            shipping_cost=Decimal('10.00'),
            tax_amount=sum(item.get_total_price() for item in cart_items) * Decimal('0.1'),
        )
        
        # 创建订单项
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price_at_purchase=cart_item.product.price,
                product_name=cart_item.product.name,
                product_sku=cart_item.product.sku,
            )
            
            # 更新库存
            cart_item.product.stock_quantity -= cart_item.quantity
            cart_item.product.save()
        
        # 清空购物车
        cart.cart_items.all().delete()
        
        # 创建状态历史
        OrderStatusHistory.objects.create(
            order=order,
            status='pending',
            changed_by=request.user,
            notes='订单创建'
        )
        
        return JsonResponse({
            'success': True,
            'message': '订单创建成功',
            'order_id': order.id
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def my_orders(request):
    """我的订单列表"""
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    
    # 筛选
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # 分页
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,  # Changed from 'page_obj' to 'orders' to match template
        'status_filter': status_filter,
    }
    
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail(request, order_id):
    """订单详情"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    order_items = order.order_items.all()
    
    # 获取订单状态历史
    status_history = OrderStatusHistory.objects.filter(order=order).order_by('-created_at')
    
    context = {
        'order': order,
        'order_items': order_items,
        'status_history': status_history,
    }
    
    return render(request, 'orders/order_detail.html', context)


@login_required
def cancel_order(request, order_id):
    """取消订单"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status not in ['pending', 'confirmed']:
        messages.error(request, '该订单无法取消')
        return redirect('orders:order_detail', order_id=order_id)
    
    if request.method == 'POST':
        try:
            # 更新订单状态
            order.status = 'cancelled'
            order.save()
            
            # 创建状态历史
            OrderStatusHistory.objects.create(
                order=order,
                status='cancelled',
                changed_by=request.user,
                notes='用户取消订单'
            )
            
            # 恢复商品库存
            for item in order.order_items.all():
                item.product.stock_quantity += item.quantity
                item.product.save()
            
            messages.success(request, '订单已成功取消')
            return redirect('orders:my_orders')
            
        except Exception as e:
            messages.error(request, f'取消订单失败：{str(e)}')
    
    return render(request, 'orders/cancel_order.html', {'order': order})


@login_required
def track_order(request, order_id):
    """订单跟踪"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    status_history = OrderStatusHistory.objects.filter(order=order).order_by('-created_at')
    
    context = {
        'order': order,
        'status_history': status_history,
    }
    
    return render(request, 'orders/track_order.html', context)


@login_required
def order_review(request, order_id):
    """订单评价"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # 检查订单状态是否允许评价
    if not order.can_be_reviewed:
        if order.is_reviewed:
            messages.info(request, '您已经评价过此订单')
        else:
            messages.error(request, '只有已完成的订单才能进行评价')
        return redirect('orders:order_detail', order_id=order_id)
    
    order_items = order.order_items.all()
    
    if request.method == 'POST':
        try:
            # 获取评价数据
            ratings = {}
            comments = {}
            service_rating = int(request.POST.get('service_rating', 0))
            service_comment = request.POST.get('service_comment', '')
            
            # 收集每个商品的评价
            for item in order_items:
                item_id = str(item.id)
                rating = int(request.POST.get(f'rating_{item_id}', 0))
                comment = request.POST.get(f'review_text_{item_id}', '')
                
                if rating > 0:
                    ratings[item_id] = rating
                    comments[item_id] = comment.strip()
            
            # 验证评价数据
            if not ratings:
                messages.error(request, '请至少为一个商品评分')
                return render(request, 'orders/order_review.html', {
                    'order': order,
                    'order_items': order_items,
                })
            
            if service_rating == 0:
                messages.error(request, '请为服务评分')
                return render(request, 'orders/order_review.html', {
                    'order': order,
                    'order_items': order_items,
                })
            
            # 处理图片上传
            images = request.FILES.getlist('review_images')
            if len(images) > 5:
                messages.error(request, '最多只能上传5张图片')
                return render(request, 'orders/order_review.html', {
                    'order': order,
                    'order_items': order_items,
                })
            
            # 保存评价数据到数据库
            # 更新每个订单项的评价
            for item_id, rating in ratings.items():
                order_item = order_items.get(id=item_id)
                if order_item:
                    order_item.rating = rating
                    order_item.review_comment = comments.get(item_id, '')
                    order_item.save()
            
            # 更新订单的整体评价
            order.is_reviewed = True
            order.service_rating = service_rating
            order.service_comment = service_comment.strip()
            
            # 计算平均评分
            if ratings:
                avg_rating = sum(ratings.values()) / len(ratings)
                order.review_rating = round(avg_rating, 2)
            
            order.save()
            
            messages.success(request, '评价提交成功！感谢您的反馈！')
            return redirect('orders:order_detail', order_id=order_id)
            
        except ValueError as e:
            messages.error(request, '评分数据格式错误')
        except Exception as e:
            messages.error(request, f'评价提交失败：{str(e)}')
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    
    return render(request, 'orders/order_review.html', context)
