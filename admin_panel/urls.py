from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # 管理员仪表板
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    # 用户管理
    path('users/', views.user_management, name='user_management'),
    path('users/customer/', views.customer_management, name='customer_management'),
    path('users/merchant/', views.merchant_management, name='merchant_management'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/status/', views.update_user_status, name='update_user_status'),
    
    # 商品管理
    path('products/', views.product_management, name='product_management'),
    path('products/pending/', views.pending_products, name='pending_products'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    path('products/<int:product_id>/approve/', views.approve_product, name='approve_product'),
    path('products/<int:product_id>/reject/', views.reject_product, name='reject_product'),
    path('products/<int:product_id>/suspend/', views.suspend_product, name='suspend_product'),
    path('products/<int:product_id>/activate/', views.activate_product, name='activate_product'),
    
    # 订单管理
    path('orders/', views.order_management, name='order_management'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('orders/disputes/', views.dispute_management, name='dispute_management'),
    path('orders/disputes/<int:dispute_id>/', views.dispute_detail, name='dispute_detail'),
    
    # 系统管理
    path('categories/', views.category_management, name='category_management'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    
    # 财务管理
    path('finances/', views.financial_management, name='financial_management'),
    path('finances/transactions/', views.transaction_management, name='transaction_management'),
    path('finances/payouts/', views.payout_management, name='payout_management'),
    path('finances/reports/', views.financial_reports, name='financial_reports'),
    
    # 系统设置
    path('settings/', views.system_settings, name='system_settings'),
    path('settings/general/', views.general_settings, name='general_settings'),
    path('settings/payment/', views.payment_settings, name='payment_settings'),
    path('settings/shipping/', views.shipping_settings, name='shipping_settings'),
    path('settings/commission/', views.commission_settings, name='commission_settings'),
    
    # 系统日志和监控
    path('logs/', views.system_logs, name='system_logs'),
    path('reports/', views.system_reports, name='system_reports'),
    path('analytics/', views.system_analytics, name='system_analytics'),
    
    # 营销管理
    path('promotions/', views.promotion_management, name='promotion_management'),
    path('promotions/add/', views.add_promotion, name='add_promotion'),
    path('promotions/<int:promotion_id>/edit/', views.edit_promotion, name='edit_promotion'),
    path('promotions/<int:promotion_id>/delete/', views.delete_promotion, name='delete_promotion'),
    
    # 内容和媒体管理
    path('content/', views.content_management, name='content_management'),
    path('media/', views.media_management, name='media_management'),
    path('pages/', views.page_management, name='page_management'),
]