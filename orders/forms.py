from django import forms
from django.contrib.auth import get_user_model
from accounts.models import Address
from .models import Order, CartItem


User = get_user_model()


class CheckoutForm(forms.Form):
    """结算表单"""
    shipping_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        label='收货地址',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    billing_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        label='账单地址',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        required=False,
        label='订单备注',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '如有特殊要求请在此说明...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # 获取用户的地址
            self.fields['shipping_address'].queryset = Address.objects.filter(
                user=user,
                is_active=True
            )
            self.fields['billing_address'].queryset = Address.objects.filter(
                user=user,
                is_active=True
            )
            
            # 如果只有一个地址，设为默认
            if self.fields['shipping_address'].queryset.count() == 1:
                address = self.fields['shipping_address'].queryset.first()
                self.fields['shipping_address'].initial = address.id


class OrderStatusUpdateForm(forms.ModelForm):
    """订单状态更新表单"""
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 只显示可用的状态选项
        status_choices = [
            ('pending', '待处理'),
            ('confirmed', '已确认'),
            ('processing', '处理中'),
            ('shipped', '已发货'),
            ('delivered', '已送达'),
            ('cancelled', '已取消'),
        ]
        self.fields['status'].choices = status_choices


class OrderNoteForm(forms.ModelForm):
    """订单备注表单"""
    class Meta:
        model = Order
        fields = ['merchant_note', 'customer_note']
        widgets = {
            'merchant_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '商家备注...'
            }),
            'customer_note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '客户备注...'
            })
        }


class CartItemUpdateForm(forms.ModelForm):
    """购物车项更新表单"""
    class Meta:
        model = CartItem
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 99
            })
        }


class OrderSearchForm(forms.Form):
    """订单搜索表单"""
    order_number = forms.CharField(
        required=False,
        label='订单号',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '输入订单号...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        label='订单状态',
        choices=[
            ('', '全部状态'),
            ('pending', '待处理'),
            ('confirmed', '已确认'),
            ('processing', '处理中'),
            ('shipped', '已发货'),
            ('delivered', '已送达'),
            ('cancelled', '已取消'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        label='开始日期',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    min_amount = forms.DecimalField(
        required=False,
        label='最小金额',
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00'
        })
    )
    
    max_amount = forms.DecimalField(
        required=False,
        label='最大金额',
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '99999.99'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        # 验证日期范围
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError('开始日期不能晚于结束日期')
        
        # 验证金额范围
        if min_amount and max_amount and min_amount > max_amount:
            raise forms.ValidationError('最小金额不能大于最大金额')
        
        return cleaned_data