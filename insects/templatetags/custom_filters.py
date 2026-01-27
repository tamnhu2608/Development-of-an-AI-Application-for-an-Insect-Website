from django import template

register = template.Library()

@register.filter(name='format_status')
def format_status(value):
    if value == 'pending':
        return 'Chờ xét duyệt'
    if value == 'verified':
        return 'Cv đã duyệt'
    if value == 'accepted':
        return 'Admin đã duyệt'
    if value == 'rejected':
        return 'Đã bị từ chối'
    return value.capitalize()




# Thêm các filter mới
@register.filter(name='get_species_name')
def get_species_name(species_id):
    """Lấy tên loài từ ID"""
    try:
        species = Species.objects.get(insects_id=species_id)
        return species.name
    except Species.DoesNotExist:
        return "Không xác định"

@register.filter(name='get_region_name')
def get_region_name(region_id):
    """Lấy tên khu vực từ ID"""
    try:
        region = AdministrativeRegion.objects.get(id=region_id)
        return region.name
    except AdministrativeRegion.DoesNotExist:
        return "Không xác định"

@register.filter(name='has_group')
def has_group(user, group_name):
    """Kiểm tra user có thuộc group không"""
    return user.groups.filter(name=group_name).exists()

@register.filter(name='format_coordinate')
def format_coordinate(value):
    """Định dạng tọa độ"""
    try:
        return f"{float(value):.4f}"
    except (ValueError, TypeError):
        return value

@register.filter(name='truncate_note')
def truncate_note(value, length=30):
    """Rút gọn ghi chú"""
    if len(value) > length:
        return value[:length] + '...'
    return value

@register.filter(name='get_status_badge')
def get_status_badge(status):
    """Tạo badge cho trạng thái"""
    badge_classes = {
        'pending': 'bg-info',
        'admin_approved': 'bg-success', 
        'expert_approved': 'bg-warning',
        'rejected': 'bg-danger'
    }
    badge_texts = {
        'pending': 'Chờ duyệt',
        'admin_approved': 'Đã duyệt',
        'expert_approved': 'Chờ admin',
        'rejected': 'Từ chối'
    }
    
    badge_class = badge_classes.get(status, 'bg-secondary')
    badge_text = badge_texts.get(status, status)
    
    return f'<span class="badge {badge_class}">{badge_text}</span>'