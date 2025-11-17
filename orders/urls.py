from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # 购物车相关
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # 订单相关
    path('checkout/', views.checkout, name='checkout'),
    path('create/', views.create_order, name='create_order'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order-list/', views.my_orders, name='order_list'),  # 为兼容性添加别名
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    
    # 订单状态跟踪
    path('order/<int:order_id>/track/', views.track_order, name='track_order'),
    
    # 订单评价
    path('order/<int:order_id>/review/', views.order_review, name='order_review'),
]