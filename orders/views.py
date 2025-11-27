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
    """订单结算页面 - 使用session-based购物车"""
    # 获取session中的购物车数据
    cart_data = request.session.get('cart', {})
    
    if not cart_data:
        messages.warning(request, '购物车为空，无法进行结算')
        return redirect('products:cart')
    
    # 获取购物车商品信息
    cart_items = []
    subtotal = 0
    
    for product_id, quantity in cart_data.items():
        try:
            product = Product.objects.get(id=product_id, status='active')
            
            # 检查库存
            if quantity > product.stock_quantity:
                messages.error(request, f'商品 "{product.name}" 库存不足')
                return redirect('products:cart')
            
            item_subtotal = product.price * quantity
            subtotal += item_subtotal
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': product.price,
                'subtotal': item_subtotal
            })
            
        except Product.DoesNotExist:
            # 如果商品不存在或状态不活跃，从session中移除
            del cart_data[product_id]
            request.session['cart'] = cart_data
            messages.warning(request, f'商品 ID {product_id} 已下架，已从购物车移除')
            return redirect('products:cart')
    
    # 更新session
    request.session['cart'] = cart_data
    
    # 计算价格
    shipping_cost = Decimal('5.99')  # 默认运费
    tax_rate = Decimal('0.08')  # 8%税率
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + shipping_cost + tax_amount
    
    # 获取用户地址
    addresses = Address.objects.filter(user=request.user)
    
    if request.method == 'POST':
        # 处理表单数据
        address_id = request.POST.get('address')
        payment_method = request.POST.get('payment_method', 'credit_card')
        shipping_method = request.POST.get('shipping_method', 'standard')
        
        # 验证必填字段
        if not address_id:
            messages.error(request, '请选择收货地址')
            return render(request, 'orders/checkout.html', {
                'cart_items': cart_items,
                'subtotal': subtotal,
                'shipping_cost': shipping_cost,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
                'addresses': addresses,
                'error_message': '请选择收货地址'
            })
        
        try:
            shipping_address = Address.objects.get(id=address_id, user=request.user)
        except Address.DoesNotExist:
            messages.error(request, '选择的收货地址无效')
            return render(request, 'orders/checkout.html', {
                'cart_items': cart_items,
                'subtotal': subtotal,
                'shipping_cost': shipping_cost,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
                'addresses': addresses,
                'error_message': '选择的收货地址无效'
            })
        
        # 根据配送方式更新运费
        shipping_costs = {
            'standard': Decimal('5.99'),
            'express': Decimal('12.99'),
            'overnight': Decimal('24.99')
        }
        shipping_cost = shipping_costs.get(shipping_method, Decimal('5.99'))
        total_amount = subtotal + shipping_cost + tax_amount
        
        # 创建订单
        order = Order.objects.create(
            customer=request.user,
            status='pending',
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            total_amount=total_amount,
            shipping_address=shipping_address,
            billing_address=shipping_address,  # 使用收货地址作为账单地址
            payment_method=payment_method,
            shipping_method=shipping_method,
            notes=request.POST.get('notes', '')
        )
        
        # 创建订单项
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                price_at_purchase=item['price'],
                product_name=item['product'].name,
                product_sku=item['product'].sku,
            )
            # 更新商品库存
            item['product'].stock_quantity -= item['quantity']
            item['product'].save()
        
        # 清空session中的购物车
        request.session['cart'] = {}
        
        # 创建订单状态历史
        OrderStatusHistory.objects.create(
            order=order,
            status='pending',
            changed_by=request.user,
            notes='订单创建'
        )
        
        # 重定向到订单确认页面
        messages.success(request, f'订单 #{order.id} 提交成功！商家将尽快处理您的订单。')
        return redirect('orders:order_detail', order_id=order.id)
    
    context = {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        'addresses': addresses
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
        subtotal = sum(item.get_total_price() for item in cart_items)
        order = Order.objects.create(
            customer=request.user,
            status='pending',
            shipping_address_id=request.POST.get('shipping_address'),
            notes=request.POST.get('notes', ''),
            subtotal=subtotal,
            total_amount=subtotal + Decimal('10.00') + subtotal * Decimal('0.1'),
            shipping_cost=Decimal('10.00'),
            tax_amount=subtotal * Decimal('0.1'),
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
    if status_filter and status_filter != 'all':
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


@login_required
def order_payment(request, order_id):
    """订单支付页面"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # 检查订单状态，只有待支付的订单才能进入支付页面
    if order.payment_status != 'pending':
        messages.info(request, '订单已支付或无需支付')
        return redirect('orders:order_detail', order_id=order_id)
    
    context = {
        'order': order,
    }
    
    return render(request, 'orders/order_payment.html', context)


@login_required
def process_payment(request, order_id):
    """处理支付请求"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # 检查订单状态
    if order.payment_status != 'pending':
        return JsonResponse({
            'success': False,
            'message': '订单已支付或无需支付'
        })
    
    try:
        # 解析JSON请求体
        # 检查请求体是否为空
        if not request.body:
            return JsonResponse({
                'success': False,
                'message': '请求数据为空'
            })
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False,
                'message': f'JSON数据格式错误: {str(e)}'
            })
        
        payment_method = data.get('payment_method', 'credit_card')
        
        # 模拟支付处理（实际项目中应集成真实的支付网关）
        import time
        time.sleep(2)  # 模拟支付处理时间
        
        # 模拟支付成功
        order.payment_status = 'paid'
        order.status = 'confirmed'  # 更新订单状态为已确认
        order.save()
        
        # 创建支付记录
        OrderStatusHistory.objects.create(
            order=order,
            status='confirmed',
            changed_by=request.user,
            notes=f'支付成功 - {payment_method}'
        )
        
        return JsonResponse({
            'success': True,
            'message': '支付成功！',
            'redirect_url': reverse('orders:order_detail', kwargs={'order_id': order.id})
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'支付失败：{str(e)}'
        })


@login_required
def confirm_delivery(request, order_id):
    """确认收货"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        # 检查订单状态是否允许确认收货
        if order.status != 'shipped':
            return JsonResponse({
                'error': '只有已发货的订单才能确认收货',
                'current_status': order.status
            }, status=400)
        
        # 更新订单状态为已送达
        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()
        
        # 创建状态历史
        OrderStatusHistory.objects.create(
            order=order,
            status='delivered',
            changed_by=request.user,
            notes='用户确认收货'
        )
        
        return JsonResponse({
            'success': True,
            'message': '收货确认成功',
            'order_id': order.id,
            'new_status': order.status
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'error': '订单不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)