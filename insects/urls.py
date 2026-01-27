from django.urls import path, register_converter
from . import views
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.urlpatterns import format_suffix_patterns
from .views import ImageUploadAPI


class SlugWithParenthesesConverter:
    regex = '[\w-]+(\([\w\s]+\))?'

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return str(value)

register_converter(SlugWithParenthesesConverter, 'customslug')


#URL Configurations
urlpatterns = [
    #path('', views.home_view, name='home_view'),
    path('', views.home_page, name='home_page'),
    path("get_species_options/", views.get_species_options, name="get_species_options"),
    path('show_insect_images/', views.show_insect_images, name='show_insect_images'),
    path('load_more_images/', views.load_more_images, name='load_more_images'),
    path('detail/<customslug:slug>/', views.detail, name='detail'),
    path('detail/<customslug:slug>/load_more_images/', views.load_more_insect_images, name='load_more_insect_images'),
    path('3d_model/<customslug:slug>/', views.threed_model, name='3d_model'),
    path('search/', views.search_species, name='search_species'),
    path('search_suggestions/', views.search_suggestions, name='search_suggestions'),
    path('image_search/', views.image_search, name='image_search'),
    path('search_by_image/', views.search_by_image, name='search_by_image'),
    path('export_data/', views.export_data, name='export_data'),
    # document
    path('document/', views.document_list, name='document_list'),
    path('upload_document/', views.upload_document, name='upload_document'),
    path('view_document/<int:doc_id>/', views.view_document, name='view_document'),
    path('download/<int:doc_id>/', views.download_document, name='download_document'),
    path("delete_document/<int:doc_id>/", views.delete_document, name="delete_document"),
    # manage insect
    path('manage_insect/', views.manage_insect, name='manage_insect'),
    path('manage_insect/add_class/', views.add_class, name='add_class'),
    path('manage_insect/add_order/', views.add_order, name='add_order'),
    path('manage_insect/add_family/', views.add_family, name='add_family'),
    path('manage_insect/add_genus/', views.add_genus, name='add_genus'),
    path('manage_insect/add_species/', views.add_species, name='add_species'),
    path('manage_insect/delete_class/<int:class_id>/', views.delete_class, name='delete_class'),
    path('manage_insect/delete_order/<int:order_id>/', views.delete_order, name='delete_order'),
    path('manage_insect/delete_family/<int:family_id>/', views.delete_family, name='delete_family'),
    path('manage_insect/delete_genus/<int:genus_id>/', views.delete_genus, name='delete_genus'),
    path('manage_insect/delete_species/<int:insects_id>/', views.delete_species, name='delete_species'),
    path('manage_insect/edit_species/<int:insects_id>/', views.edit_species, name='edit_species'),
    path('manage_insect/edit_class/<int:class_id>/', views.edit_class, name='edit_class'),
    path('manage_insect/edit_order/<int:order_id>/', views.edit_order, name='edit_order'),
    path('manage_insect/edit_family/<int:family_id>/', views.edit_family, name='edit_family'),
    path('manage_insect/edit_genus/<int:genus_id>/', views.edit_genus, name='edit_genus'),

    #manage_image
    path("manage_image/", views.manage_image, name="manage_image"),
    path("manage_label_n_bbox/", views.manage_label_n_bbox, name="manage_label_n_bbox"),
    path("manage_image_desc/", views.manage_image_desc, name="manage_image_desc"),
    path("delete_image/<str:img_id>/", views.delete_image, name="delete_image"),
    
    #manage_account
    path('account_info/', views.account_info, name='account_info'),
    path('edit_account/', views.edit_account, name='edit_account'),
    path('change_password/', views.change_password, name='change_password'),
    #manage user
    path('manage_user/', views.manage_user, name='manage_user'),
    path('manage_user/add/', views.add_user, name='add_user'),
    path('manage_user/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('manage_user/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    # import data
    path('import_data/', views.import_data, name='import_data'),
    path('upload_handler/', views.upload_handler, name='upload_handler'),
    # login
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # sign up
    path('sign_up/', views.sign_up, name='sign_up'),
    # forgot password
    path("password_reset_otp/", views.send_reset_otp, name="password_reset_otp"),
    path("verify_otp/", views.verify_otp, name="verify_otp"),
    path("reset_password/", views.reset_password, name="reset_password"),
    # folder upload
    path('upload_folder_zip/', views.upload_folder_zip, name='upload_folder_zip'),
    # statistics
    path('statistics/', views.statistics_view, name='shop-statistics'),  # new
    path('chart/image_by_species/', views.get_species_img_chart, name='get_species_chart'),
    path('chart/user_by_group/', views.user_by_group_chart, name='user_by_group_chart'),
    path('chart/order_by_class/', views.order_by_class_chart, name='order_by_class_chart'),
    path('chart/family_by_order/', views.family_by_order_chart, name='family_by_order_chart'),
    path('chart/genus_by_family/', views.genus_by_family_chart, name='genus_by_family_chart'),
    path('chart/species_by_genus/', views.species_by_genus_chart, name='species_by_genus_chart'),

    path('species_list/', views.species_list, name='species_list'),
    path('load_specie_image/', views.load_specie_image, name='load_specie_image'),




    # crawler
    # path('data_crawler/', views.data_crawler, name='data_crawler'),
    # path('upload_crawled_images/', views.upload_crawled_images, name='upload_crawled_images'),
    # path('cancel_crawled_images/', views.cancel_crawled_images, name='cancel_crawled_images'),
    # path('ajax/crawl_images/', views.ajax_crawl_images, name='crawl_images'),
    path('data_crawler/', views.data_crawler, name='data_crawler'),
    path('cancel_crawling/', views.cancel_crawling, name='cancel_crawling'),

    # annotations
    path('Labelling/', views.labelling, name='Labelling'),
    path('get_image_data/', views.get_image_data, name='get_image_data'),
    path('save_bboxes/', views.save_bboxes, name='save_bboxes'),
    path('annotation/', views.annotation, name='annotation'),
    # download
    path('download_images/', views.download_folder, name='download_folder'),
    # append insect
    path('append_insect/', views.append_insect, name='append_insect'),
    path('append_insect_handler/', views.append_insect_handler, name='append_insect_handler'),

    #verify insects
    path('cv_verify/', views.cv_verify, name='cv_verify'),
    path('admin_verify/', views.admin_verify, name='admin_verify'),
    path('verify_request/<int:request_id>/', views.verify_request, name='verify_request'),
    path('accept_request/<int:request_id>/', views.accept_request, name='accept_request'),

    ## Description
    path('cv_desc_verify/', views.cv_desc_verify, name='cv_desc_verify'),
    path('add_desc/', views.add_desc, name='add_desc'),  # new
    path('add_desc_step2/', views.add_desc_step2, name='add_desc_step2'),
    path('add_desc_handler/<str:img_id>/', views.add_desc_handler, name='append_desc_handler'),
    path('admin_desc_verify/', views.admin_desc_verify, name='admin_desc_verify'),
    path('verify_desc_request/<int:request_desc_id>/', views.verify_desc_request, name='verify_desc_request'),
    path('accept_desc_request/<int:request_desc_id>/', views.accept_desc_request, name='accept_desc_request'),

    # APIs
    path('api/species_list/', views.species_list),
    path('api/species_details/<str:lookup>/', views.species_details),
    path('api/image_details/<str:img_id>/', views.image_details),
    path('api/insect_images/<str:lookup>/', views.get_insect_images, name='get_insect_images'),
    path('api/upload_images/', ImageUploadAPI.as_view(), name='upload_images'),
    path('api/species_images/<str:lookup>/', views.species_images),
    path('api/species_images_bbox/<int:id>/', views.species_images_bbox),
    path('api/bbox_details/<str:img_id>/', views.bbox_details, name='bbox_details'),

    # Rquest_img
    path('request_image/', views.request_image, name='request_image'),
    path('contrib_image/', views.contrib_image, name='contrib_image'),
    path('cv_verify_new_image/', views.cv_verify_new_image, name='cv_verify_new_image'),
    path('verify_new_image_request/<int:request_img_id>/', views.verify_new_image_request, name='verify_new_image_request'),
    path('save_bbox/<int:request_img_id>/', views.save_bbox_verify, name='save_bbox'),
    path('save_bbox_verify/<int:request_img_id>/', views.save_bbox_verify, name='save_bbox_verify'),
    path('admin_verify_new_image/', views.admin_verify_new_image, name='admin_verify_new_image'),
    path('accept_new_image/<int:request_img_id>/', views.accept_new_image, name='accept_new_image'),
    path('api/auto-detect/<int:request_img_id>/', views.auto_detect_image, name='auto_detect_image'),

    # crawl_img
    path('crawl_images/', views.crawl_images, name='crawl_images'),
    path('upload_image/', views.upload_image, name='upload_image'),
    path('save_bbox/', views.save_bbox, name='save_bbox'),




    # detect_by_img
    path('detect_insect/', views.detect, name='detect_insect'),
  
 # ========== BẢN ĐỒ PHÂN BỐ==========
    path('distribution-map/', views.distribution_map_view, name='distribution_map'),
    path('contribute-distribution/', views.contribute_distribution, name='contribute_distribution'),
    path('contribute-distribution-image/', views.contribute_distribution_with_image, name='contribute_distribution_with_image'),
    path('expert-review-distribution/', views.expert_review_distribution, name='expert_review_distribution'),
    path('admin-review-distribution/', views.admin_review_distribution, name='admin_review_distribution'),
    path('api/distribution-map/', views.distribution_map_api, name='distribution_map_api'),
    path('api/regions/', views.get_regions_api, name='get_regions_api'),
    path('api/crops/', views.get_crops_api, name='get_crops_api'),
    path('crop-damage/', views.crop_damage_list, name='crop_damage_list'),
    path('crop-damage/<int:crop_id>/', views.crop_damage_detail, name='crop_damage_detail'),
    path('insect-damage/<int:insects_id>/', views.insect_damage_detail, name='insect_damage_detail'),
    path('contribute-crop-damage/', views.contribute_crop_damage, name='contribute_crop_damage'),
    path('crop/<int:crop_id>/', views.crop_detail, name='crop_detail'),
    #path('api/predict-species/', views.predict_species_from_image, name='predict_species'),
    path('my-distribution-history/', views.my_distribution_history,name='my_distribution_history'),
    path('expert-review-distribution/<int:id>/', views.expert_review_distribution_detail, name='expert_review_distribution_detail'),
    path('expert-review-distribution/<int:id>/save-bbox/',views.expert_save_bboxes,name='expert_save_bboxes'),
    path('expert/review-distribution/', views.expert_review_distribution, name='expert_review_distribution'),
    path('expert/review-distribution/<int:id>/', views.expert_review_distribution_detail, name='expert_review_distribution_detail'),
    path('expert/save-bboxes/<int:id>/', views.expert_save_bboxes, name='expert_save_bboxes'),
    
 # ========== QUẢN LÝ VỊ TRÍ CÔN TRÙNG - CHUYÊN GIA ==========
   
   path('expert_manage_distribution/', views.expert_manage_distribution, name='expert_manage_distribution'),
 # ========== QUẢN LÝ VỊ TRÍ CÔN TRÙNG - QUẢN TRỊ VIÊN ==========
   path('admin_review_distribution/', views.admin_review_distribution, name='admin_review_distribution'),
   path('admin_review_distribution/<int:id>/', views.admin_review_distribution_detail, name='admin_review_distribution_detail'),
   path('admin_save_distribution/<int:id>/', views.admin_save_distribution, name='admin_save_distribution'),
   path('admin_manage_approved_locations/', views.admin_manage_approved_locations, name='admin_manage_approved_locations'),
   path('admin_delete_approved_location/<int:id>/', views.admin_delete_approved_location, name='admin_delete_approved_location'),
# ========== QUẢN LÝ CÔN TRÙNG ==========
    path('expert_manage_crop/',views.expert_manage_crop,name='expert_manage_crop'),
  
    path('expert/add-crop/', views.expert_add_crop, name='expert_add_crop'),
    path('expert/edit-crop/<int:crop_id>/', views.expert_edit_crop, name='expert_edit_crop'),
    path('expert/delete-crop/<int:crop_id>/', views.expert_delete_crop, name='expert_delete_crop'),
    path('expert/add-damage/', views.expert_add_damage, name='expert_add_damage'),
    path('expert/edit-damage/<int:damage_id>/', views.expert_edit_damage, name='expert_edit_damage'),
    path('expert/delete-damage/<int:damage_id>/', views.expert_delete_damage, name='expert_delete_damage'),
# ========== ADMIN DUYỆT CÂY TRỒNG ==========
    path('admin_manage_crops/', views.admin_manage_crops, name='admin_manage_crops'),
    path('admin_approve_damage/<int:damage_id>/', views.admin_approve_damage, name='admin_approve_damage'),
    path('admin_approve_crop/<int:crop_id>/', views.admin_approve_crop, name='admin_approve_crop'),
    path('admin_delete_damage/<int:damage_id>/', views.admin_delete_damage, name='admin_delete_damage'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)