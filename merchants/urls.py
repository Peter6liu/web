from django.urls import path
from . import views

app_name = 'merchants'

urlpatterns = [
    # 商家仪表板
    path('', views.merchant_dashboard, name='dashboard'),
    
    # 商品管理
    path('products/', views.product_management, name='product_list'),
    path('products/add/', views.add_product, name='product_add'),
    path('products/<int:pk>/edit/', views.edit_product, name='product_edit'),
    path('products/<int:pk>/delete/', views.delete_product, name='product_delete'),
    # path('products/<int:pk>/toggle-status/', views.toggle_product_status, name='product_toggle_status'),
    

    

    
    # 客户管理
    path('customers/', views.customer_management, name='customer_management'),
    
    # 商家信息管理
    path('profile/', views.merchant_profile, name='merchant_profile'),
    path('info/', views.merchant_info, name='merchant_info'),
    path('info/update/', views.merchant_info_update, name='merchant_info_update'),
    path('api/cities/', views.get_cities, name='get_cities'),
    path('api/districts/', views.get_districts, name='get_districts'),
    
    # 财务管理
    path('financial/', views.financial_management, name='financial_management'),
    
    # 库存管理
    path('inventory/', views.inventory_management, name='inventory_management'),
    path('inventory/update/<int:product_id>/', views.update_inventory, name='update_inventory'),
    
    # 采购管理
    path('purchases/', views.purchase_management, name='purchase_management'),
    
    # 数据分析
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # 订单管理
    path('orders/', views.order_management, name='order_management'),
    path('orders/list/', views.order_management, name='order_list'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/ship/', views.order_ship, name='order_ship'),
    
    # 促销活动
    path('promotions/', views.promotions, name='promotions'),
]