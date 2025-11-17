// 工具函数 - 减少重复代码

const Utils = {
    // 确认对话框
    confirm: function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    },
    
    // 显示通知
    showNotification: function(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // 自动关闭
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    },
    
    // 获取CSRF令牌
    getCsrfToken: function() {
        // 首先尝试从cookie获取
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        if (cookieValue) {
            return cookieValue.split('=')[1];
        }
        
        // 如果cookie中没有，尝试从DOM获取
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            return csrfToken.value;
        }
        
        return null;
    },
    
    // AJAX请求
    ajax: function(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        };
        
        const finalOptions = { ...defaultOptions, ...options };
        
        // 如果是POST请求，添加CSRF令牌
        if (finalOptions.method.toUpperCase() === 'POST') {
            const csrfToken = this.getCsrfToken();
            if (csrfToken) {
                finalOptions.headers['X-CSRFToken'] = csrfToken;
            }
        }
        
        return fetch(url, finalOptions)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .catch(error => {
                this.showNotification('请求失败，请重试', 'error');
                throw error;
            });
    },
    
    // 创建CSRF表单
    createCsrfForm: function() {
        const form = document.createElement('form');
        form.method = 'POST';
        form.style.display = 'none';
        
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'csrfmiddlewaretoken';
            hiddenInput.value = csrfToken.value;
            form.appendChild(hiddenInput);
        }
        
        return form;
    },
    
    // 通用状态更新函数
    updateStatus: function(url, data, successMessage) {
        const form = this.createCsrfForm();
        
        // 添加数据到表单
        for (const [key, value] of Object.entries(data)) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            form.appendChild(input);
        }
        
        document.body.appendChild(form);
        
        return this.ajax(url, {
            method: 'POST',
            body: new FormData(form)
        }).then(response => {
            if (response.success) {
                this.showNotification(successMessage, 'success');
                location.reload();
            } else {
                this.showNotification(response.error || '操作失败', 'error');
            }
            return response;
        });
    },
    
    // 更新购物车徽章
    updateCartBadge: function(count) {
        const cartBadge = document.querySelector('.cart-badge');
        if (cartBadge) {
            cartBadge.textContent = count;
            cartBadge.style.display = count > 0 ? 'inline' : 'none';
        }
    },
    
    // 添加到购物车
    addToCart: function(productId, quantity = 1, callback) {
        return this.ajax(`/products/cart/add/${productId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ quantity: quantity })
        }).then(response => {
            if (response.success) {
                this.updateCartBadge(response.cart_count);
                this.showNotification('商品已添加到购物车', 'success');
            } else {
                this.showNotification(response.error || '添加失败', 'error');
            }
            if (callback) callback(response.success);
            return response;
        }).catch(error => {
            this.showNotification('添加失败，请重试', 'error');
            if (callback) callback(false);
            throw error;
        });
    }
};