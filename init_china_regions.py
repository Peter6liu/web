# 中国省份数据初始化脚本
# 运行方式: python manage.py shell < init_china_regions.py

from merchants.models import Province, City, District

# 省份数据
provinces_data = [
    ('110000', '北京市'),
    ('120000', '天津市'),
    ('130000', '河北省'),
    ('140000', '山西省'),
    ('150000', '内蒙古自治区'),
    ('210000', '辽宁省'),
    ('220000', '吉林省'),
    ('230000', '黑龙江省'),
    ('310000', '上海市'),
    ('320000', '江苏省'),
    ('330000', '浙江省'),
    ('340000', '安徽省'),
    ('350000', '福建省'),
    ('360000', '江西省'),
    ('370000', '山东省'),
    ('410000', '河南省'),
    ('420000', '湖北省'),
    ('430000', '湖南省'),
    ('440000', '广东省'),
    ('450000', '广西壮族自治区'),
    ('460000', '海南省'),
    ('500000', '重庆市'),
    ('510000', '四川省'),
    ('520000', '贵州省'),
    ('530000', '云南省'),
    ('540000', '西藏自治区'),
    ('610000', '陕西省'),
    ('620000', '甘肃省'),
    ('630000', '青海省'),
    ('640000', '宁夏回族自治区'),
    ('650000', '新疆维吾尔自治区'),
    ('710000', '台湾省'),
    ('810000', '香港特别行政区'),
    ('820000', '澳门特别行政区'),
]

# 创建省份
for code, name in provinces_data:
    province, created = Province.objects.get_or_create(
        code=code,
        defaults={'name': name}
    )
    if created:
        print(f'创建省份: {name}')

# 为北京、上海、天津、重庆创建一些示例城市
beijing = Province.objects.get(code='110000')
shanghai = Province.objects.get(code='310000')
guangdong = Province.objects.get(code='440000')

# 北京市的城市
cities_data = [
    (beijing, '110100', '北京市'),
    (shanghai, '310100', '上海市'),
    (guangdong, '440100', '广州市'),
    (guangdong, '440300', '深圳市'),
]

for province, code, name in cities_data:
    city, created = City.objects.get_or_create(
        code=code,
        defaults={'name': name, 'province': province}
    )
    if created:
        print(f'创建城市: {name}')

# 为示例城市创建一些区县
districts_data = [
    ('110100', '110101', '东城区'),
    ('110100', '110102', '西城区'),
    ('110100', '110105', '朝阳区'),
    ('110100', '110106', '丰台区'),
    ('310100', '310101', '黄浦区'),
    ('310100', '310104', '徐汇区'),
    ('310100', '310105', '长宁区'),
    ('310100', '310106', '静安区'),
    ('440100', '440103', '荔湾区'),
    ('440100', '440104', '越秀区'),
    ('440100', '440105', '海珠区'),
    ('440100', '440106', '天河区'),
    ('440300', '440303', '罗湖区'),
    ('440300', '440304', '福田区'),
    ('440300', '440305', '南山区'),
    ('440300', '440306', '宝安区'),
]

for city_code, district_code, district_name in districts_data:
    try:
        city = City.objects.get(code=city_code)
        district, created = District.objects.get_or_create(
            code=district_code,
            defaults={'name': district_name, 'city': city}
        )
        if created:
            print(f'创建区县: {district_name}')
    except City.DoesNotExist:
        print(f'城市代码 {city_code} 不存在，跳过区县 {district_name}')

print('中国地区数据初始化完成！')