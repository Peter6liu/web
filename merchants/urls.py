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
    path('customers/bulk-add-tags/', views.bulk_add_customer_tags, name='bulk_add_customer_tags'),
    path('customers/export/', views.customer_export, name='customer_export'),
    
    # 商家信息管理
    path('profile/', views.merchant_profile, name='merchant_profile'),
    path('info/', views.merchant_info, name='merchant_info'),
    path('info/update/', views.merchant_info_update, name='merchant_info_update'),
    path('api/cities/', views.get_cities, name='get_cities'),
    path('api/districts/', views.get_districts, name='get_districts'),
    
    # 财务管理
    path('financial/', views.financial_management, name='financial_management'),
    path('financial/withdrawal/', views.withdrawal_request, name='withdrawal_request'),
    path('financial/transaction-detail/', views.transaction_detail, name='transaction_detail'),
    path('financial/export/', views.financial_export, name='financial_export'),
    
    # 库存管理
    path('inventory/', views.inventory_management, name='inventory_management'),
    path('inventory/update/<int:product_id>/', views.update_inventory, name='update_inventory'),
    path('inventory/history/<int:product_id>/', views.stock_history, name='stock_history'),
    path('inventory/export/', views.export_inventory, name='export_inventory'),
    path('inventory/download-template/', views.download_inventory_template, name='download_inventory_template'),
    path('inventory/batch-update-stock/', views.batch_update_stock, name='batch_update_stock'),
    path('inventory/batch-update-price/', views.batch_update_price, name='batch_update_price'),
    path('inventory/generate-stock-alert/', views.generate_stock_alert, name='generate_stock_alert'),
    path('inventory/import/', views.import_inventory, name='import_inventory'),
    
    # 采购管理
    path('purchases/', views.purchase_management, name='purchase_management'),
    path('purchases/order-detail/', views.purchase_order_detail, name='purchase_order_detail'),
    path('purchases/create-order/', views.create_purchase_order, name='create_purchase_order'),
    
    # 数据分析
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # 订单管理
    path('orders/', views.order_management, name='order_management'),
    path('orders/list/', views.order_management, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/ship/', views.order_ship, name='order_ship'),
    path('orders/batch-ship/', views.batch_ship, name='batch_ship'),
    path('orders/export/', views.order_export, name='order_export'),
    path('orders/status-update/', views.order_status_update, name='order_status_update'),
    path('orders/new-orders-check/', views.new_orders_check, name='new_orders_check'),
    path('orders/<int:order_id>/cancel/', views.order_cancel, name='order_cancel'),
    path('orders/<int:order_id>/print/', views.order_print, name='order_print'),
    path('orders/<int:order_id>/message/', views.order_message, name='order_message'),
    
    # 促销活动
    path('promotions/', views.promotions, name='promotions'),
]