from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/customer/', views.customer_register, name='customer_register'),
    path('register/merchant/', views.merchant_register, name='merchant_register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.user_profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/<int:pk>/edit/', views.edit_address, name='edit_address'),
    path('addresses/<int:pk>/delete/', views.delete_address, name='delete_address'),
]