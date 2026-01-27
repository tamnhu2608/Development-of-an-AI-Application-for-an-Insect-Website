# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
import os

from django.utils.timezone import now


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Liên kết với user
    otp = models.CharField(max_length=6)  # Lưu OTP (mã xác thực)
    created_at = models.DateTimeField(auto_now_add=True)  # Thời gian tạo OTP

    def __str__(self):
        return f"{self.user.username} - {self.otp}"

class Class(models.Model):
    class_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    phylum = models.ForeignKey('Phylum', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'class'
        verbose_name_plural = "Class (Lớp)"

    def __str__(self):
        return self.ename


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Family(models.Model):
    family_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    order = models.ForeignKey('Order', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'family'
        verbose_name_plural = "Family (Họ)"

    def __str__(self):
        return self.ename


class Genus(models.Model):
    genus_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    family = models.ForeignKey(Family, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'genus'
        verbose_name_plural = "Genus (Chi)"

    def __str__(self):
        return self.ename
    

class InsectsBbox(models.Model):
    box_id = models.AutoField(primary_key=True)
    x = models.FloatField()
    y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()
    # img = models.ForeignKey('InsectsImage', models.DO_NOTHING, blank=True, null=True)
    img = models.ForeignKey('InsectsImage', on_delete=models.CASCADE, related_name='bboxes')

    class Meta:
        managed = False
        db_table = 'insects_bbox'
        verbose_name_plural = "Nhãn"


class InsectsImage(models.Model):
    img_id = models.CharField(primary_key=True, max_length=255)
    url = models.CharField(max_length=255, blank=True, null=True)
    desc= models.TextField(blank=True, null=True, default=None)
    insects = models.ForeignKey('Species', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'insects_image_detect_15k'
        verbose_name_plural = "Hình ảnh"

    def get_absolute_url(self):
        return os.path.join(settings.MEDIA_URL, self.url)
    
    def __str__(self):
        return self.url


class Kingdom(models.Model):
    kingdom_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'kingdom'
        verbose_name_plural = "Kingdom (Giới)"

    def __str__(self):
        return self.ename


class Order(models.Model):
    order_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    class_field = models.ForeignKey(Class, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.

    class Meta:
        managed = False
        db_table = 'order'
        verbose_name_plural = "Order (Bộ)"

    def __str__(self):
        return self.ename


class Phylum(models.Model):
    phylum_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    kingdom = models.ForeignKey(Kingdom, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'phylum'
        verbose_name_plural = "Phylum (Ngành)"
    
    def __str__(self):
        return self.ename

User = get_user_model()
class Request(models.Model):
    request_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    species_name = models.CharField(max_length=200)
    eng_name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    morphologic_feature = models.TextField()
    distribution = models.TextField()
    characteristic = models.TextField()
    behavior = models.TextField()
    protection_method = models.TextField()
    thumbnail = models.CharField(max_length=255, blank=True, null=True)
    genus = models.ForeignKey(Genus, models.DO_NOTHING, blank=True, null=True)
    status = models.CharField(max_length=8, blank=True, null=True)
    verification_count = models.IntegerField(blank=True, null=True)
    # user = models.ForeignKey(AuthUser, models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    #created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'request'


class RequestDesc(models.Model):
    request_desc_id = models.AutoField(primary_key=True)
    desc =models.TextField()
    status = models.CharField(max_length=8, blank=True, null=True)
    verification_count = models.IntegerField(blank=True, null=True)
    # user = models.ForeignKey(AuthUser, models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    img = models.ForeignKey(InsectsImage, on_delete=models.SET_NULL, max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)  # Ngày gửi mô tả
    # approved_at = models.DateTimeField(blank=True, null=True)  # Ngày duyệt mô tả

    class Meta:
        managed = False
        db_table = 'request_desc'


class Species(models.Model):
    insects_id = models.AutoField(primary_key=True)
    ename = models.CharField(db_column='eName', max_length=100)  # Field name made lowercase.
    name = models.CharField(max_length=100)
    species_name = models.CharField(max_length=200)
    eng_name = models.CharField(max_length=100)
    vi_name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    morphologic_feature = models.TextField()
    distribution = models.TextField()
    characteristic = models.TextField()
    behavior = models.TextField()
    protection_method = models.TextField()
    thumbnail = models.CharField(max_length=255, blank=True, null=True)
    genus = models.ForeignKey(Genus, models.DO_NOTHING, blank=True, null=True)
    is_new = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        verbose_name_plural = "Species (Loài)"
        db_table = 'species'

    def __str__(self):
        return self.ename


class Document(models.Model):
    doc_id = models.AutoField(primary_key=True)
    doc_name = models.CharField(max_length=255)
    url = models.CharField(max_length=500)

    class Meta:
        managed = False
        db_table = 'document'
        verbose_name_plural = "Tài liệu"

    def __str__(self):
        return self.url

# Crawler
class InsectsCrawler(models.Model):
    crawler_id  = models.AutoField(primary_key=True)
    insects_id = models.ForeignKey('Species', on_delete=models.CASCADE, null=True, db_column='insects_id')
    user_id = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, db_column='user_id')  # Liên kết đến bảng User
    img_url = models.URLField(null=True, db_column='img_url')  # URL của hình ảnh
    img_id = models.CharField(max_length=50, null=True, db_column='img_id')
    crawl_time = models.DateTimeField(default=timezone.now)  # Thời gian cào, sử dụng timezone.now
    status = models.CharField(max_length=20, choices=[('success', 'Success'), ('failed', 'Failed'), ('processing', 'Processing')], default='processing')

    class Meta:
        db_table = 'insects_crawler'

    def __str__(self):
        return f"Image ID: {self.img_id} - {self.status}"

#Request_image
class RequestImage(models.Model):
    request_img_id = models.AutoField(primary_key=True)
    insects_id = models.ForeignKey('Species', on_delete=models.CASCADE, null=True, db_column='insects_id')
    user_id = models.ForeignKey('auth.User', on_delete=models.CASCADE, null=True, db_column='user_id')
    url = models.URLField(null=True, db_column='url')
    request_time = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=8, blank=True, null=True)
    verification_count = models.IntegerField(blank=True, null=True)
    #desc = models.TextField()
    desc = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "request_image"

    def __str__(self):
        return f"Request by User {self.user_id} for Species {self.insects_id}"

class VerificationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    request_type = models.CharField(
        max_length=20,
        choices=[
            ('desc', 'Mô tả ảnh'),
            ('image', 'Ảnh côn trùng mới'),
            ('species', 'Đề xuất loài mới'),
        ]
    )
    object_id = models.PositiveIntegerField()
    verified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'verification_log'
        unique_together = ('user', 'request_type', 'object_id')
        managed = False



#=====================================================================================================
# Bản đồ phân bố
class AdministrativeRegion(models.Model):
    LEVEL_CHOICES = [
        ('country', 'Quốc gia'),
        ('province', 'Tỉnh'),
        ('district', 'Huyện'),
        ('commune', 'Xã'),
    ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)

    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children'
    )

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        db_table = 'administrative_region'

class InsectDistribution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Chờ duyệt'),
        ('expert_approved', 'Chuyên gia duyệt'),
        ('admin_approved', 'Admin duyệt'),
        ('rejected', 'Từ chối'),
    ]

    id = models.AutoField(primary_key=True)

    species = models.ForeignKey(
        Species,
        on_delete=models.PROTECT,
        db_column='insects_id',
        related_name='distributions'
    )

    region = models.ForeignKey(
        AdministrativeRegion,
        on_delete=models.PROTECT,
        null=True,  # THÊM NULLABLE
        blank=True   # THÊM BLANK
    )

    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    observation_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    observation_image = models.ImageField(
        upload_to='distribution_images/',
        null=True,
        blank=True
    )
    
    # THÊM FIELD NÀY
    gps_from_image = models.BooleanField(default=False, verbose_name="GPS từ ảnh")
    
    # THÊM FIELD NÀY (tùy chọn)
    image_credit = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nguồn ảnh")

    class Meta:
        db_table = 'insect_distribution'
        
    def __str__(self):
        return f"{self.species.name} - {self.latitude}, {self.longitude}"

class DistributionReviewLog(models.Model):
    ROLE_CHOICES = [
        ('expert', 'Chuyên gia'),
        ('admin', 'Admin'),
    ]

    ACTION_CHOICES = [
        ('approve', 'Đồng ý'),
        ('reject', 'Từ chối'),
        ('edit_bbox', 'Chỉnh sửa bounding box'),
    ]

    id = models.AutoField(primary_key=True)

    distribution = models.ForeignKey(
        InsectDistribution,
        on_delete=models.CASCADE,
        related_name='review_logs'
    )

    reviewer = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'distribution_review_log'




class Crop(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    scientific_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    economic_value = models.TextField(
            blank=True,
            null=True,
            verbose_name="Giá trị kinh tế"
        )

    morphology = models.TextField(
        blank=True,
        null=True,
        verbose_name="Đặc điểm hình thái"
    )

    cultivation_area = models.TextField(
        blank=True,
        null=True,
        verbose_name="Vùng trồng phổ biến"
    )
    class Meta:
        db_table = 'crop'


class InsectCropDamage(models.Model):
    DAMAGE_LEVELS = [
        ('low', 'Nhẹ'),
        ('medium', 'Trung bình'),
        ('high', 'Nặng'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Chờ duyệt'),
        ('expert_approved', 'Chuyên gia duyệt'),
        ('admin_approved', 'Admin duyệt'),
        ('rejected', 'Từ chối'),
    ]

    id = models.AutoField(primary_key=True)

    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT)

    damage_level = models.CharField(max_length=20, choices=DAMAGE_LEVELS)
    description = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'insect_crop_damage'

class DistributionBoundingBox(models.Model):
    id = models.AutoField(primary_key=True)

    distribution = models.ForeignKey(
        InsectDistribution,
        on_delete=models.CASCADE,
        related_name='bboxes'
    )

    x = models.FloatField()
    y = models.FloatField()
    width = models.FloatField()
    height = models.FloatField()

    confidence = models.FloatField(default=0)
    label = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'distribution_bbox'
