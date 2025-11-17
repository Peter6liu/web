from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from orders.models import Order, OrderItem, Cart, CartItem, OrderStatusHistory
from accounts.models import Address, CustomerProfile

class Command(BaseCommand):
    help = '清空订单数据并删除admin用户和测试用户'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='模拟运行，不实际删除数据',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        User = get_user_model()
        
        self.stdout.write('开始清理数据...')
        
        # 1. 清空订单相关数据
        self.stdout.write('1. 清空订单相关数据...')
        
        # 先删除订单项，因为外键约束
        order_item_count = OrderItem.objects.count()
        cart_item_count = CartItem.objects.count()
        order_status_history_count = OrderStatusHistory.objects.count()
        
        if not dry_run:
            OrderItem.objects.all().delete()
            CartItem.objects.all().delete()
            OrderStatusHistory.objects.all().delete()
        
        self.stdout.write(f'   删除订单项: {order_item_count} 条')
        self.stdout.write(f'   删除购物车项: {cart_item_count} 条')
        self.stdout.write(f'   删除订单状态历史: {order_status_history_count} 条')
        
        # 删除订单和购物车
        order_count = Order.objects.count()
        cart_count = Cart.objects.count()
        
        if not dry_run:
            Order.objects.all().delete()
            Cart.objects.all().delete()
        
        self.stdout.write(f'   删除订单: {order_count} 条')
        self.stdout.write(f'   删除购物车: {cart_count} 条')
        
        # 2. 删除地址数据
        self.stdout.write('2. 清空地址数据...')
        address_count = Address.objects.count()
        
        if not dry_run:
            Address.objects.all().delete()
        
        self.stdout.write(f'   删除地址: {address_count} 条')
        
        # 3. 删除客户资料
        self.stdout.write('3. 清空客户资料...')
        customer_profile_count = CustomerProfile.objects.count()
        
        if not dry_run:
            CustomerProfile.objects.all().delete()
        
        self.stdout.write(f'   删除客户资料: {customer_profile_count} 条')
        
        # 4. 删除指定的用户
        self.stdout.write('4. 删除指定的用户...')
        
        # 定义要删除的用户名模式
        users_to_delete = [
            'admin',
            'administrator',
            'test',
            'testuser',
            'demo',
            'demo_user'
        ]
        
        deleted_users = []
        for username_pattern in users_to_delete:
            # 查找匹配的用户（不区分大小写）
            users = User.objects.filter(username__icontains=username_pattern)
            user_count = users.count()
            
            if user_count > 0:
                usernames = list(users.values_list('username', flat=True))
                self.stdout.write(f'   找到匹配用户 "{username_pattern}": {user_count} 个')
                self.stdout.write(f'   用户名: {usernames}')
                
                if not dry_run:
                    users.delete()
                    deleted_users.extend(usernames)
        
        # 5. 检查是否还有其他测试用户（用户名包含test、demo等）
        self.stdout.write('5. 检查其他可能的测试用户...')
        
        # 查找包含测试关键词的用户
        test_keywords = ['test', 'demo', 'temp', '临时', '测试']
        for keyword in test_keywords:
            users = User.objects.filter(username__icontains=keyword)
            user_count = users.count()
            
            if user_count > 0:
                usernames = list(users.values_list('username', flat=True))
                self.stdout.write(f'   找到包含 "{keyword}" 的用户: {user_count} 个')
                self.stdout.write(f'   用户名: {usernames}')
                
                if not dry_run:
                    users.delete()
                    deleted_users.extend(usernames)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n模拟运行完成，没有实际删除数据'))
            self.stdout.write('如果要实际删除数据，请移除 --dry-run 参数')
        else:
            self.stdout.write(self.style.SUCCESS('\n数据清理完成！'))
            if deleted_users:
                self.stdout.write(f'已删除的用户: {deleted_users}')
            else:
                self.stdout.write('没有找到要删除的用户')
            
            # 显示剩余的用户统计
            remaining_users = User.objects.count()
            self.stdout.write(f'剩余用户总数: {remaining_users}')
            
            # 显示剩余用户列表
            if remaining_users > 0:
                remaining_usernames = list(User.objects.values_list('username', flat=True))
                self.stdout.write(f'剩余用户: {remaining_usernames}')

    def get_user_count_by_type(self, user_type):
        """获取指定类型的用户数量"""
        User = get_user_model()
        return User.objects.filter(user_type=user_type).count()