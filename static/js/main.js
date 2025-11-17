// 主要JavaScript文件
document.addEventListener('DOMContentLoaded', function() {
    
    // 初始化所有组件
    initSidebar();
    initTooltips();
    initDropdowns();
    initModals();
    initTables();
    initForms();
    initAlerts();
    

});

// 侧边栏功能
function initSidebar() {
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.admin-sidebar');
    const main = document.querySelector('.admin-main');
    
    if (sidebarToggle && sidebar && main) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
            main.classList.toggle('expanded');
        });
    }
    
    // 当前页面高亮
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href && currentPath.startsWith(href)) {
            item.classList.add('active');
        }
    });
}

// 工具提示
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// 下拉菜单
function initDropdowns() {
    const dropdownToggleList = [].slice.call(document.querySelectorAll('.dropdown-toggle'));
    dropdownToggleList.map(function(dropdownToggleEl) {
        return new bootstrap.Dropdown(dropdownToggleEl);
    });
}

// 模态框
function initModals() {
    const modalElements = document.querySelectorAll('.modal');
    modalElements.forEach(modal => {
        const modalInstance = new bootstrap.Modal(modal);
        
        // 清理数据
        modal.addEventListener('hidden.bs.modal', function() {
            const inputs = modal.querySelectorAll('input, textarea, select');
            inputs.forEach(input => {
                if (input.type !== 'hidden') {
                    input.value = '';
                }
            });
        });
    });
}

// 表格功能
function initTables() {
    // 表格排序
    const sortableHeaders = document.querySelectorAll('.sortable');
    sortableHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const table = this.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            const column = this.cellIndex;
            const isAscending = this.classList.contains('asc');
            
            rows.sort((a, b) => {
                const aVal = a.cells[column].textContent.trim();
                const bVal = b.cells[column].textContent.trim();
                
                if (isAscending) {
                    return aVal.localeCompare(bVal);
                } else {
                    return bVal.localeCompare(aVal);
                }
            });
            
            // 更新排序图标
            sortableHeaders.forEach(h => h.classList.remove('asc', 'desc'));
            this.classList.add(isAscending ? 'desc' : 'asc');
            
            // 重新排列行
            rows.forEach(row => tbody.appendChild(row));
        });
    });
    
    // 表格选择
    const selectAll = document.querySelector('.select-all');
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');
    
    if (selectAll && rowCheckboxes.length > 0) {
        selectAll.addEventListener('change', function() {
            rowCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateBulkActions();
        });
        
        rowCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', updateBulkActions);
        });
    }
}

// 更新批量操作按钮
function updateBulkActions() {
    const selectedRows = document.querySelectorAll('.row-checkbox:checked');
    const bulkActions = document.querySelector('.bulk-actions');
    
    if (bulkActions) {
        if (selectedRows.length > 0) {
            bulkActions.style.display = 'block';
            bulkActions.querySelector('.selected-count').textContent = selectedRows.length;
        } else {
            bulkActions.style.display = 'none';
        }
    }
}

// 表单验证
function initForms() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                e.stopPropagation();
            }
            this.classList.add('was-validated');
        });
        
        // 实时验证
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
        });
    });
}

// 验证单个字段 - 使用Utils工具类
function validateField(field) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // 检查必填字段
    if (field.hasAttribute('required') && !value) {
        isValid = false;
        errorMessage = '此字段为必填项';
    }
    
    // 检查邮箱格式
    if (field.type === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            isValid = false;
            errorMessage = '请输入有效的邮箱地址';
        }
    }
    
    // 检查手机号格式
    if (field.name === 'phone' && value) {
        const phoneRegex = /^1[3-9]\d{9}$/;
        if (!phoneRegex.test(value)) {
            isValid = false;
            errorMessage = '请输入有效的手机号码';
        }
    }
    
    // 显示错误信息
    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        if (isValid) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
            feedback.textContent = '';
        } else {
            field.classList.remove('is-valid');
            field.classList.add('is-invalid');
            feedback.textContent = errorMessage;
        }
    }
    
    return isValid;
}

// 表单验证 - 使用Utils工具类
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    return isValid;
}

// 提示消息
function initAlerts() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        // 自动关闭
        if (alert.classList.contains('alert-dismissible')) {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 5000);
        }
    });
}

// 文件上传预览 - 使用Utils工具类
function initFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();
                const preview = this.parentNode.querySelector('.file-preview');
                
                if (preview) {
                    if (file.type.startsWith('image/')) {
                        reader.onload = function(e) {
                            preview.innerHTML = `<img src="${e.target.result}" style="max-width: 200px; max-height: 200px;">`;
                        };
                        reader.readAsDataURL(file);
                    } else {
                        preview.innerHTML = `<div class="file-info">文件: ${file.name} (${file.size} bytes)</div>`;
                    }
                }
            }
        });
    });
}

// 搜索功能 - 使用Utils工具类
function initSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const query = this.value.trim();
            const url = this.getAttribute('data-search-url');
            
            if (query.length > 2) {
                // 实时搜索功能可以在这里实现
            }
        });
    });
}

// 搜索和过滤 - 使用Utils工具类
function initSearchFilters() {
    const searchInputs = document.querySelectorAll('.search-input');
    const filterSelects = document.querySelectorAll('.filter-select');
    
    searchInputs.forEach(input => {
        input.addEventListener('input', debounce(function() {
            performSearch();
        }, 300));
    });
    
    filterSelects.forEach(select => {
        select.addEventListener('change', performSearch);
    });
}

// 执行搜索
function performSearch() {
    const searchInput = document.querySelector('.search-input');
    const filterSelects = document.querySelectorAll('.filter-select');
    const table = document.querySelector('.data-table table');
    
    if (!table) return;
    
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    const filters = {};
    
    filterSelects.forEach(select => {
        if (select.value) {
            filters[select.name] = select.value;
        }
    });
    
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        let showRow = true;
        
        // 文本搜索
        if (searchTerm) {
            const text = row.textContent.toLowerCase();
            if (!text.includes(searchTerm)) {
                showRow = false;
            }
        }
        
        // 过滤器
        for (const [column, value] of Object.entries(filters)) {
            // 这里需要根据实际的表格结构来调整
            const cell = row.cells[getColumnIndex(column)];
            if (cell && cell.textContent.trim() !== value) {
                showRow = false;
                break;
            }
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 获取列索引
function getColumnIndex(columnName) {
    const headers = document.querySelectorAll('.data-table th');
    for (let i = 0; i < headers.length; i++) {
        if (headers[i].dataset.column === columnName || headers[i].textContent.includes(columnName)) {
            return i;
        }
    }
    return 0;
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initFileUpload();
    initSearchFilters();
});

// 导出功能 - 使用Utils工具类
function exportTable(tableId, filename = 'export.csv') {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [];
        const cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let cellText = cols[j].textContent.trim().replace(/"/g, '""');
            row.push('"' + cellText + '"');
        }
        
        csv.push(row.join(','));
    }
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}