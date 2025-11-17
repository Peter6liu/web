from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser, CustomerProfile
from merchants.models import MerchantProfile
from orders.models import Cart
from products.models import Product, Category
from .forms import CustomerRegistrationForm, MerchantRegistrationForm, LoginForm, UserProfileForm, CustomerProfileForm


def home(request):
    """首页视图"""
    # 获取精选商品（状态为active且标记为精选的商品）
    featured_products = Product.objects.filter(
        status='active',
        is_featured=True
    ).select_related('category').prefetch_related('images')[:8]
    
    # 获取热门分类（活跃的分类）
    popular_categories = Category.objects.filter(
        is_active=True
    )[:4]
    
    context = {
        'featured_products': featured_products,
        'popular_categories': popular_categories,
    }
    
    return render(request, 'accounts/home.html', context)


def _create_user_profile(user, user_type, form_data):
    """创建用户档案"""
    try:
        if user_type == 'customer':
            customer_profile = CustomerProfile.objects.create(
                user=user,
                preferred_language=form_data.get('preferred_language', 'en'),
                preferred_currency=form_data.get('preferred_currency', 'USD')
            )
            
            # 创建购物车
            from orders.models import Cart
            cart = Cart.objects.create(user=user)
            
        elif user_type == 'merchant':
            merchant_profile = MerchantProfile.objects.create(
                user=user,
                company_name=form_data['company_name'],
                business_license=form_data.get('business_license', ''),
                company_address=form_data.get('company_address', ''),
                company_phone=form_data.get('company_phone', ''),
                company_email=form_data.get('company_email', ''),
                description=form_data.get('description', '')
            )
    except Exception as e:
        import traceback
        traceback.print_exc()


def customer_register(request):
    """客户注册"""
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=True)
            _create_user_profile(user, 'customer', form.cleaned_data)
            messages.success(request, '注册成功！请登录。')
            return redirect('accounts:login')
        else:
            # 可以在这里添加表单错误的调试信息
            pass  # 保留用于后续调试
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'accounts/customer_register.html', {'form': form})


def merchant_register(request):
    """商家注册"""
    if request.method == 'POST':
        form = MerchantRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=True)
            _create_user_profile(user, 'merchant', form.cleaned_data)
            messages.success(request, '商家注册成功！请等待审核。')
            return redirect('accounts:login')
        else:
            # 可以在这里添加表单错误的调试信息
            pass
    else:
        form = MerchantRegistrationForm()
    
    return render(request, 'accounts/merchant_register.html', {'form': form})


def _get_user_redirect_url(user):
    """根据用户类型获取重定向URL"""
    if user.user_type == 'admin':
        return redirect('admin_panel:dashboard')
    elif user.user_type == 'merchant':
        return redirect('merchants:dashboard')
    else:
        return redirect('products:product_list')


def user_login(request):
    """用户登录"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.user_type == 'merchant' and hasattr(user, 'merchant_profile'):
                    if not user.merchant_profile.is_approved:
                        messages.error(request, '您的商家账户还未审核通过，请耐心等待。')
                        return redirect('accounts:login')
                
                login(request, user)
                messages.success(request, f'欢迎回来，{user.username}！')
                return _get_user_redirect_url(user)
            else:
                messages.error(request, '用户名或密码错误。')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def user_logout(request):
    """用户登出"""
    logout(request)
    messages.success(request, '您已成功登出。')
    return redirect('accounts:home')


@login_required
def user_profile(request):
    """用户个人资料"""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def edit_profile(request):
    """编辑个人资料"""
    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        
        if request.user.user_type == 'customer':
            profile_form = CustomerProfileForm(request.POST, instance=request.user.customer_profile)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, '个人资料更新成功！')
                return redirect('accounts:profile')
        else:
            if user_form.is_valid():
                user_form.save()
                messages.success(request, '个人资料更新成功！')
                return redirect('accounts:profile')
    else:
        user_form = UserProfileForm(instance=request.user)
        profile_form = CustomerProfileForm(instance=request.user.customer_profile) if request.user.user_type == 'customer' else None
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def address_list(request):
    """地址列表"""
    return render(request, 'accounts/address_list.html', {'addresses': request.user.addresses.all()})


@login_required
def add_address(request):
    """添加地址"""
    from .forms import AddressForm
    
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, '地址添加成功！')
            return redirect('accounts:address_list')
    else:
        form = AddressForm()
    
    return render(request, 'accounts/add_address.html', {'form': form})


@login_required
def edit_address(request, pk):
    """编辑地址"""
    from .forms import AddressForm
    address = get_object_or_404(request.user.addresses, pk=pk)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, '地址更新成功！')
            return redirect('accounts:address_list')
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'accounts/edit_address.html', {'form': form, 'address': address})


@login_required
def delete_address(request, pk):
    """删除地址"""
    address = get_object_or_404(request.user.addresses, pk=pk)
    
    if request.method == 'POST':
        address.delete()
        messages.success(request, '地址删除成功！')
        return redirect('accounts:address_list')
    
    return render(request, 'accounts/delete_address.html', {'address': address})
