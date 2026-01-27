import hashlib
import random
import re
import shutil
from tempfile import NamedTemporaryFile
import time
import glob
from urllib.request import urlopen
from datetime import datetime, timedelta
from django.db.models.manager import BaseManager
from django.utils import timezone
from django.db import transaction
from itertools import groupby

from pygbif import occurrences
import cv2
import numpy as np
from django.core.mail import send_mail
from django.core.mail import EmailMessage
from django.shortcuts import redirect
from django.conf import settings
from django.utils.crypto import get_random_string
from pandas.core.interchange.from_dataframe import set_nulls
import requests
from ultralytics import YOLO
import urllib
from django.utils.safestring import mark_safe
from .models import InsectsImage, Species, InsectsBbox, Genus, RequestDesc, Document, Class, Family, Order, Phylum, \
    PasswordResetOTP, RequestImage, InsectsCrawler, VerificationLog
from insects.templatetags.forms import UserEditForm, ClassesEditForm, SpeciesEditForm, OrderEditForm, FamilyEditForm, \
    GenusEditForm, InsectsImageForm
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password
from PIL import Image
import json
import zipfile
from django.contrib.auth import authenticate, login as django_login, logout, update_session_auth_hash
from .serializers import SpeciesSerializer, ImageSerializer, ImageBoxSerializer, BoundingBoxSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from django.shortcuts import render, get_object_or_404
import os
# from .excel_export import export_species_data_to_csv
from .excel_export_1 import export_species_data_to_csv
from django.core.files.storage import default_storage, FileSystemStorage
from django.http import JsonResponse, HttpResponseBadRequest
from .crawler import download_images, delete_tmp_images, save_images_to_database
from django.db.models import Q, OuterRef, Subquery
import uuid
from unidecode import unidecode
# NQA
from django.db.models import Count


# from .utils import translate_text
#bản đồ
from .models import Species, InsectDistribution, AdministrativeRegion
#from regions.models import AdministrativeRegion
from .models import Species, InsectDistribution
# End NQA

def convert_yolo_to_pixel(x, y, width, height, img_width, img_height):
    # Convert the center coordinates from relative to absolute pixel values
    x_center = x * img_width
    y_center = y * img_height

    # Convert the width and height from relative to absolute pixel values
    box_width = width * img_width
    box_height = height * img_height

    # Calculate the top left corner coordinates
    x_top_left = x_center - (box_width / 2)
    y_top_left = y_center - (box_height / 2)

    return x_top_left, y_top_left, box_width, box_height


# annotations section
def labelling(request):
    insect_id = request.GET.get('insectId')
    if insect_id:
        # Handle AJAX request
        images = InsectsImage.objects.filter(insects_id=insect_id).prefetch_related('bboxes')
        images_data = []
        for image in images:
            img_path = os.path.join(settings.MEDIA_ROOT, image.url)
            with Image.open(img_path) as img:
                img_width, img_height = img.size

            bboxes_data = []
            for bbox in image.bboxes.all():
                x_top_left, y_top_left, box_width, box_height = convert_yolo_to_pixel(
                    bbox.x, bbox.y, bbox.width, bbox.height, img_width, img_height)
                converted_bbox = {
                    'x': x_top_left, 'y': y_top_left,
                    'width': box_width, 'height': box_height
                }
                bboxes_data.append(converted_bbox)

            images_data.append({
                'img_id': image.img_id,  # Make sure this id exists and matches the model field
                'url': settings.MEDIA_URL + image.url,
                'width': img_width,
                'height': img_height,
                'insectsId': image.insects_id,
                'insectsName': image.insects.name,
                'bboxes': bboxes_data,
            })

        return JsonResponse({'images': images_data})

    # Handle non-AJAX request
    species_list = Species.objects.all()
    return render(request, 'Labelling.html', {'species_list': species_list})


def get_image_data(request):
    img_id = request.GET.get('imgId')
    image = InsectsImage.objects.filter(img_id=img_id).first()
    if image:
        # Construct the full path to the image file
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)

        # Open the image to obtain its size
        try:
            with Image.open(img_path) as img:
                width, height = img.size
        except IOError:
            return JsonResponse({'error': 'Failed to open image file.'}, status=500)

        # Construct bounding boxes list
        bboxes = list(image.bboxes.values('x', 'y', 'width', 'height'))

        # Return all necessary data, including the image's width and height
        return JsonResponse({
            'url': image.get_absolute_url(),
            'bboxes': bboxes,
            'width': width,
            'height': height
        })
    else:
        return JsonResponse({'error': 'Image not found'}, status=404)


# def get_image_data(request):
#     img_id = request.GET.get('imgId')
#     image = InsectsImage.objects.filter(img_id=img_id).first()
#     if image:
#         bboxes = list(image.bboxes.values('x', 'y', 'width', 'height'))
#         return JsonResponse({'url': image.get_absolute_url(), 'bboxes': bboxes})
#     return JsonResponse({'error': 'Image not found'}, status=404)

@csrf_exempt
@require_POST
def save_bboxes(request):
    try:
        img_id = request.GET.get('imgId')
        data = json.loads(request.body)
        bboxes_data = data.get('bboxes', [])

        image = InsectsImage.objects.get(img_id=img_id)  # Ensure this matches your model's field name

        # Consider updating existing boxes rather than deleting
        InsectsBbox.objects.filter(img=image).delete()  # Caution: This deletes existing boxes!

        for bbox in bboxes_data:
            InsectsBbox.objects.create(
                x=bbox['x'],
                y=bbox['y'],
                width=bbox['width'],
                height=bbox['height'],
                img=image
            )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def annotation(request):
    img_id = request.GET.get('imgId')

    if not img_id:
        return redirect('labelling')

    image = InsectsImage.objects.filter(img_id=img_id).first()
    if not image:
        return JsonResponse({'error': 'Image not found'}, status=404)

    img_url = image.get_absolute_url()
    bboxes = list(image.bboxes.values('x', 'y', 'width', 'height'))

    context = {
        'img_id': img_id,
        'img_url': img_url,
        'bboxes': bboxes,
    }

    return render(request, 'annotation.html', context)


# home.html section
def show_insect_images(request):
    page_number = request.GET.get('page', 1)  # Get the page number from the request
    images = InsectsImage.objects.all().prefetch_related('bboxes')
    paginator = Paginator(images, 20)  # Create a Paginator object with 20 images per page
    images = paginator.get_page(page_number)  # Get the images for the requested page

    # Convert the bounding box coordinates for each image
    for image in images:
        # Open the image and get its size
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        with Image.open(img_path) as img:
            img_width, img_height = img.size

        image.width = img_width
        image.height = img_height

        for bbox in image.bboxes.all():
            bbox.x, bbox.y, bbox.width, bbox.height = convert_yolo_to_pixel(bbox.x, bbox.y, bbox.width, bbox.height,
                                                                            img_width, img_height)

    return render(request, 'home.html', {'images': images, 'MEDIA_URL': settings.MEDIA_URL})


def load_more_images(request):
    page_number = request.GET.get('page', 1)  # Get the page number from the request
    images = InsectsImage.objects.all().prefetch_related('bboxes', 'insects')  # Include the 'insects' related object
    paginator = Paginator(images, 20)  # Create a Paginator object with 20 images per page
    images = paginator.page(page_number).object_list  # Get the images for the requested page

    # Convert the images to a list of dictionaries
    images_data = []
    for image in images:
        # Open the image and get its size
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        with Image.open(img_path) as img:
            img_width, img_height = img.size

        # Convert the bounding box coordinates for each image
        bboxes_data = []
        for bbox in image.bboxes.all():
            bbox.x, bbox.y, bbox.width, bbox.height = convert_yolo_to_pixel(bbox.x, bbox.y, bbox.width, bbox.height,
                                                                            img_width, img_height)
            bboxes_data.append({'x': bbox.x, 'y': bbox.y, 'width': bbox.width, 'height': bbox.height})

        image_data = {
            'url': image.url,
            'width': img_width,
            'height': img_height,
            'bboxes': bboxes_data,
            'insects': {
                'ename': image.insects.name,
                'slug': image.insects.slug
            },
        }
        images_data.append(image_data)

    return JsonResponse(images_data, safe=False)


# def search_species(request):
#     if request.method == 'GET':
#         species = Species.objects.values_list('insects_id', 'name', 'slug', 'ename')
#         return JsonResponse(list(species), safe=False)


# image search
def image_search(request):
    return render(request, 'image_search.html')


from .predict import predict_image


# def search_by_image(request):
#     context = {}
#     if request.method == 'POST' and request.FILES.get('insectImage'):
#         image_file = request.FILES['insectImage']
#         # Save the uploaded image temporarily
#         file_path = default_storage.save('tmp/' + image_file.name, image_file)
#         full_file_path = os.path.join(default_storage.base_location, file_path)
#
#         # Get predicted class name from the image
#         predicted_class_name = predict_image(full_file_path)
#
#         # Remove the temporary file after use
#         os.remove(full_file_path)
#
#         # Filter Species by name using case-insensitive partial match
#         species = Species.objects.filter(name__icontains=predicted_class_name).first()
#
#         if species:
#             context['species'] = species
#         else:
#             context['error'] = "No matching species found."
#
#     return render(request, 'image_search.html', context)

def search_by_image(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('insectImage'):
        image_file = request.FILES['insectImage']
        # Save the uploaded image temporarily
        file_path = default_storage.save('tmp/' + image_file.name, image_file)
        full_file_path = os.path.join(default_storage.base_location, file_path)
        try:
            result_img_url, predicted_class_name = predict_image(full_file_path)
            context['result_img'] = result_img_url
            context['predicted_class'] = predicted_class_name
            os.remove(full_file_path)
            species = Species.objects.filter(name__icontains=predicted_class_name).first()
            if species:
                context['species'] = species
            else:
                context['error'] = "Không tìm thấy loài khớp với ảnh."
        except Exception as e:
            context['error'] = f"Lỗi khi tải ảnh: {str(e)}"
    return render(request, 'image_search.html', context)


# detail.html section
def detail(request, slug):
    species = Species.objects.filter(slug=slug).first()
    if not species:
        raise Http404("Không tìm thấy loài")

    images = InsectsImage.objects.filter(insects_id=species.insects_id).prefetch_related('bboxes')[:50]

    # Convert the bounding box coordinates for each image
    for image in images:
        # Open the image and get its size - THÊM KIỂM TRA FILE TỒN TẠI
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        
        # KIỂM TRA FILE CÓ TỒN TẠI KHÔNG
        if not os.path.exists(img_path):
            print(f"Warning: Image file not found: {img_path}")
            image.width = 0
            image.height = 0
            continue  # Bỏ qua ảnh này và tiếp tục với ảnh khác
            
        try:
            with Image.open(img_path) as img:
                img_width, img_height = img.size

            image.width = img_width
            image.height = img_height

            for bbox in image.bboxes.all():
                bbox.x, bbox.y, bbox.width, bbox.height = convert_yolo_to_pixel(
                    bbox.x, bbox.y, bbox.width, bbox.height, img_width, img_height
                )
        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
            image.width = 0
            image.height = 0

    return render(request, 'detail.html', {'species': species, 'images': images, 'MEDIA_URL': settings.MEDIA_URL})

def load_more_insect_images(request, slug):
    page_number = request.GET.get('page', 1)
    species = Species.objects.filter(slug=slug).first()
    if not species:
        return JsonResponse({'error': 'Species not found'}, status=404)
    
    images = InsectsImage.objects.filter(insects_id=species.insects_id).prefetch_related('bboxes')
    paginator = Paginator(images, 50)
    images = paginator.get_page(page_number)

    # Convert the images to a list of dictionaries
    images_data = []
    for image in images:
        # Open the image and get its size - THÊM KIỂM TRA
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        
        if not os.path.exists(img_path):
            print(f"Warning: Image file not found: {img_path}")
            continue  # Bỏ qua ảnh này
            
        try:
            with Image.open(img_path) as img:
                img_width, img_height = img.size

            # Convert the bounding box coordinates for each image
            bboxes_data = []
            for bbox in image.bboxes.all():
                bbox.x, bbox.y, bbox.width, bbox.height = convert_yolo_to_pixel(
                    bbox.x, bbox.y, bbox.width, bbox.height, img_width, img_height
                )
                bboxes_data.append({
                    'x': bbox.x, 'y': bbox.y, 
                    'width': bbox.width, 'height': bbox.height
                })

            image_data = {
                'url': image.url,
                'width': img_width,
                'height': img_height,
                'bboxes': bboxes_data,
                'insects': {
                    'id': image.insects.insects_id,
                    'slug': image.insects.slug,
                    'ename': image.insects.name,
                },
                'desc': image.desc if image.desc else "",
            }
            images_data.append(image_data)
        except Exception as e:
            print(f"Error processing image {img_path}: {e}")
            continue

    return JsonResponse(images_data, safe=False)


# 3d model
def threed_model(request, slug):
    species = Species.objects.filter(slug=slug).first()  # Use filter() and first() to handle multiple objects
    if not species:
        raise Http404("Không tìm thấy loài")

    return render(request, '3d_model.html', {'species': species, 'MEDIA_URL': settings.MEDIA_URL})


# login.html section
def login(request):
    context = {'error': False}
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            context['error'] = True
            context['message'] = "Tên đăng nhập và mật khẩu không được để trống!"
        else:
            try:
                user = User.objects.get(username=username)
                if check_password(password, user.password):
                    if user.is_active:
                        django_login(request, user)
                        return redirect('/')
                    else:
                        context['error'] = True
                        context['message'] = "Tài khoản của bạn đã bị khóa, hãy liên hệ Admin để được hỗ trợ!"
                else:
                    context['error'] = True
                    context['message'] = "Tên đăng nhập hoặc mật khẩu không đúng!"
            except User.DoesNotExist:
                context['error'] = True
                context['message'] = "Có lỗi trong quá trình đăng nhập"

    return render(request, 'login.html', context)


def sign_up(request):
    message = None
    message_type = None

    if request.method == 'POST':
        lastname = request.POST.get('lastname')
        firstname = request.POST.get('firstname')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        repassword = request.POST.get('repassword')

        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

        if not username or not password or not lastname or not firstname or not email or not repassword:
            message = "Các trường không được để trống!"
            message_type = 'error'
        elif User.objects.filter(username=username).exists():
            message = "Tên đăng nhập đã được đăng ký!"
            message_type = 'error'
        elif not re.match(email_regex, email):
            message = "Email không hợp lệ!"
            message_type = 'error'
        elif User.objects.filter(email=email).exists():
            message = "Email đã được một tài khoản khác đăng ký!"
            message_type = 'error'
        elif password != repassword:
            message = "Mật khẩu xác nhận không khớp!"
            message_type = 'error'
        else:
            # Create new user
            user = User.objects.create(
                username=username,
                password=make_password(password),
                first_name=firstname,
                last_name=lastname,
                email=email,
                is_staff=False,
                is_active=True
            )

            # Get or create the "Users" group
            group, created = Group.objects.get_or_create(name="Users")
            group.user_set.add(user)

            message = "Đăng ký thành công!"
            message_type = 'success'
            return render(request, 'sign_up.html', {'message': message, 'message_type': message_type})

    return render(request, 'sign_up.html', {'message': message, 'message_type': message_type})


# def login(request):
#     if request.method == "POST":
#         # Use .get to avoid MultiValueDictKeyError
#         username = request.POST.get('username')
#         password = request.POST.get('password')
#         if not username or not password:  # Check if either field is empty
#             return HttpResponse("Username and password are required.")

#         user = authenticate(request, username=username, password=password)
#         if user is not None:
#             django_login(request, user)  # Use the imported login function with a different name
#             return redirect('/')  # Redirect to homepage or dashboard
#         else:
#             return HttpResponse("Invalid username or password.")
#     return render(request, 'login.html')

@login_required
def auth_user(request):
    is_admin = request.user.groups.filter(name="Admins").exists()
    # Add other context data as needed
    return render(request, 'template.html', {'is_admin': is_admin})


@login_required
def logout_view(request):
    logout(request)
    # Redirect to homepage or login page after logout
    return redirect('login')


def send_reset_otp(request):
    error_message = None

    if request.method == "POST":
        email = request.POST["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            error_message = "Email chưa được đăng ký. Vui lòng kiểm tra lại."
        else:
            otp = random.randint(100000, 999999)
            PasswordResetOTP.objects.update_or_create(user=user, defaults={"otp": otp})
            request.session["reset_email"] = email

            subject = "Mã OTP đặt lại mật khẩu"
            message = (
                f"- Mã OTP để đặt lại mật khẩu của bạn là: {otp}.\n- Vui lòng không cung cấp mã OTP này cho bất kì ai.\n\n"
                f"Trân trọng,\nHệ thống quản lý côn trùng"
            )
            from_email = "no-reply@yourdomain.com"
            send_mail(subject, message, from_email, [email], fail_silently=True)

            return redirect("verify_otp")

    return render(request, "password_reset_otp.html", {"error_message": error_message})


def verify_otp(request):
    email = request.session.get("reset_email")  # Lấy email từ session
    error_message = None  # Biến lưu lỗi để hiển thị modal

    if not email:
        messages.error(request, "Không tìm thấy email. Vui lòng thử lại.")
        return redirect("send_reset_otp")

    if request.method == "POST":
        otp = request.POST["otp"]

        try:
            user = User.objects.get(email=email)  # Lấy user từ email
            record = PasswordResetOTP.objects.filter(user=user, otp=otp).first()  # Truy vấn bằng user
        except User.DoesNotExist:
            return redirect("send_reset_otp")

        if record:
            messages.success(request, "OTP chính xác. Hãy đặt lại mật khẩu.")
            request.session["verified_user"] = user.id  # Lưu user ID vào session
            return redirect("reset_password")  # Chuyển qua trang đặt lại mật khẩu
        else:
            error_message = "OTP không chính xác. Vui lòng thử lại."

    return render(request, "verify_otp.html", {"error_message": error_message})


def reset_password(request):
    user_id = request.session.get("verified_user")  # Lấy user ID từ session

    if not user_id:
        return render(request, "reset_password.html", {"error_message": "Không tìm thấy tài khoản. Vui lòng thử lại."})

    try:
        user = User.objects.get(id=user_id)  # Lấy user từ ID
    except User.DoesNotExist:
        return render(request, "reset_password.html", {"error_message": "Tài khoản không tồn tại."})

    if request.method == "POST":
        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if password != confirm_password:
            return render(request, "reset_password.html",
                          {"error_message": "Mật khẩu không trùng khớp! Vui lòng thử lại."})

        # Cập nhật mật khẩu cho user
        user.set_password(password)
        user.save()

        # Xóa session sau khi đặt lại mật khẩu thành công
        del request.session["verified_user"]
        del request.session["reset_email"]

        return render(request, "reset_password.html",
                      {"success_message": "Đặt lại mật khẩu thành công! Hãy đăng nhập lại.", "redirect_url": "login"})

    return render(request, "reset_password.html")


# import_data.html section
def import_data(request):
    species_list = Species.objects.all()
    return render(request, 'import_data.html', {'species_list': species_list})


# add_insect.html section
@login_required
def append_insect(request):
    genus_list = Genus.objects.all()
    request_insect = Request.objects.filter(user=request.user).order_by('-request_id')
    success = request.GET.get('success', False)
    return render(request, 'append_insect.html',
                  {'genus_list': genus_list, 'request_insect': request_insect, "MEDIA_URL": settings.MEDIA_URL,
                   "success": success})

@login_required
def append_insect_handler(request):
    if request.method == 'POST':
        # Xử lý thumbnail
        if request.FILES.get('thumbnail'):
            thumbnail = request.FILES['thumbnail']
            file_path = f'thumbnails/{thumbnail.name}'
            handle_uploaded_file1(thumbnail)  # Lưu file
        else:
            file_path = ''

        # Tạo request mới
        new_request = Request(
            ename=request.POST.get('insectEname'),
            name=request.POST.get('insectName'),
            species_name=request.POST.get('insectSpecies'),
            eng_name=request.POST.get('insectName'),
            #vi_name=request.POST.get('insectVNName'),
            slug="insect_" + slugify(request.POST.get('insectName').replace(' ', '_')),
            morphologic_feature=request.POST.get('feature'),
            distribution=request.POST.get('distribution'),
            characteristic=request.POST.get('characteristic'),
            behavior=request.POST.get('behavior'),
            protection_method=request.POST.get('method'),
            thumbnail=file_path,
            genus_id=request.POST.get('insectGenus'),
            user=request.user,
            status='pending',
            verification_count=0
        )
        new_request.save()

        try:
            cv_group = Group.objects.get(name="CVs")
            experts = cv_group.user_set.all()
            expert_emails = [expert.email for expert in experts if expert.email]

            if expert_emails:
                subject = "Thông báo: Có đóng góp đề xuất loài côn trùng mới"
                message = (
                    f"Xin chào chuyên gia,\n\n"
                    f"- Người dùng {request.user.username} vừa đề xuất loài côn trùng mới.\n- Chuyên gia có thể truy cập vào hệ thống để xét duyệt côn trùng.\n"
                    #f"- Thời gian: {timezone.localtime(new_request.created_at).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                    f"- Người dùng {request.user.username} vừa đề xuất loài côn trùng mới.\n- Chuyên gia có thể truy cập vào hệ thống để xét duyệt côn trùng.\n\n"
                    f"Trân trọng,\nHệ thống quản lý côn trùng"
                )
                from_email = "no-reply@yourdomain.com"
                send_mail(subject, message, from_email, expert_emails, fail_silently=True)
                print(f"Email sent to: {expert_emails}")
            else:
                print("Không có chuyên gia nào trong nhóm 'CVs' có email!")
        except Group.DoesNotExist:
            print("Nhóm 'CVs' không tồn tại trong cơ sở dữ liệu!")

        # Redirect về trang form và thông báo thành công
        from django.urls import reverse
        return redirect(f"{reverse('append_insect')}?success=True")
    else:
        return redirect('append_insect')


def handle_uploaded_file1(f):
    path = os.path.join(settings.MEDIA_ROOT, 'thumbnails', f.name)
    with open(path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
def cv_verify(request):
    # Fetch requests and include related user data
    requests = Request.objects.select_related('user', 'genus').filter(status='pending')

    return render(request, 'cv_verify.html', {'requests': requests, "MEDIA_URL": settings.MEDIA_URL})


@login_required
def admin_verify(request):
    # Fetch requests with status 'Verified' and include related user data
    requests = Request.objects.select_related('user').filter(status='verified')

    return render(request, 'admin_verify.html', {'requests': requests, "MEDIA_URL": settings.MEDIA_URL})


# def verify_request(request, request_id):
#     request_item = get_object_or_404(Request, request_id=request_id)
#     return render(request, 'append_verify.html', {'request_item': request_item})
import math
from django.contrib import messages


@login_required
def verify_request(request, request_id):
    request_item = get_object_or_404(Request, pk=request_id)
    genus_list = Genus.objects.all()
    has_verified = VerificationLog.objects.filter(
        user=request.user,
        request_type='insect',
        object_id=request_id
    ).exists()

    if request.method == 'POST':
        request_item.ename = request.POST.get('insectEname', request_item.ename)
        request_item.name = request.POST.get('insectName', request_item.name)
        request_item.species_name = request.POST.get('speciesName', request_item.species_name)
        request_item.vi_name = request.POST.get('insectVNName', request_item.name)
        request_item.behavior = request.POST.get('behavior', request_item.behavior)
        request_item.morphologic_feature = request.POST.get('morphologicFeature', request_item.morphologic_feature)
        request_item.distribution = request.POST.get('distribution', request_item.distribution)
        request_item.characteristic = request.POST.get('characteristic', request_item.characteristic)
        request_item.protection_method = request.POST.get('protectionMethod', request_item.protection_method)
        request_item.genus = request.POST.get('genus', request_item.genus)

        if 'thumbnail' in request.FILES:
            request_item.thumbnail = request.FILES['thumbnail']

        request_item.verification_count = (request_item.verification_count or 0) + 1

        VerificationLog.objects.get_or_create(
            user=request.user,
            request_type='insect',
            object_id=request_id
        )

        # cvs_group = Group.objects.get(name='CVs')
        # cvs_user_count = User.objects.filter(groups=cvs_group).count()
        # threshold = math.ceil(0.8 * cvs_user_count)

        if request_item.verification_count >= 3:
            request_item.status = 'verified'

        request_item.save()
        messages.success(request, 'Xác thực thành công!')

        # Trả về template với biến `show_modal`
        return render(request, 'append_verify.html',
                      {'request_item': request_item, 'has_verified': has_verified, "MEDIA_URL": settings.MEDIA_URL,
                       'genus_list': genus_list, 'show_modal': True})

    return render(request, 'append_verify.html',
                  {'request_item': request_item, 'genus_list': genus_list, 'has_verified': has_verified,
                   "MEDIA_URL": settings.MEDIA_URL})


@login_required
def accept_request(request, request_id):
    request_item = get_object_or_404(Request, pk=request_id)
    genus_list = Genus.objects.all()

    if request.method == 'POST':
        # Create a new Species object
        new_species = Species(
            ename=request.POST.get('insectEname', request_item.ename),
            name=request.POST.get('insectName', request_item.name),
            species_name=request.POST.get('speciesName', request_item.species_name),
            eng_name=request.POST.get('engName', request_item.name),  # Set eng_name as name
            vi_name=request.POST.get('viName', request_item.name),
            slug=f"insect_{request.POST.get('speciesName', request_item.species_name).replace(' ', '_')}",
            morphologic_feature=request.POST.get('morphologicFeature', request_item.morphologic_feature),
            distribution=request.POST.get('distribution', request_item.distribution),
            characteristic=request.POST.get('characteristic', request_item.characteristic),
            genus=request.POST.get('genus', request_item.genus),
            behavior=request.POST.get('behavior', request_item.behavior),
            protection_method=request.POST.get('protectionMethod', request_item.protection_method),
            is_new=True,  # Set is_new to True
        )

        if 'thumbnail' in request.FILES:
            new_species.thumbnail = request.FILES['thumbnail']

        new_species.save()

        action = request.POST.get('action')
        if action == 'accept':
            request_item.status = 'Accepted'
            request_item.save()
            messages.success(request, 'Đề xuất côn trùng đã được chấp nhận và thêm vào CSDL.')
        elif action == 'reject':
            request_item.status = 'Rejected'
            request_item.save()
            messages.warning(request, 'Đề xuất côn trùng đã bị từ chối')

        # request_item.delete()  # If want to remove the request upon acceptance

        return render(request, 'accept_insect.html',
                      {'request_item': request_item, "MEDIA_URL": settings.MEDIA_URL, 'genus_list': genus_list,
                       'show_modal': True})  # Redirect to a success page or another relevant page

    # For GET request, show the existing data
    return render(request, 'accept_insect.html',
                  {'request_item': request_item, "MEDIA_URL": settings.MEDIA_URL, 'genus_list': genus_list, })


from .models import Request, AuthUserGroups, AuthGroup


def upload_handler(request):
    if request.method == 'POST':
        insect_id = request.POST.get('insectSelect')
        image_only = 'imageOnly' in request.POST  # Check if the image only checkbox was checked

        try:
            insect = Species.objects.get(insects_id=insect_id)
        except Species.DoesNotExist:
            return HttpResponseBadRequest("Insect ID is not valid.")

        image_files = request.FILES.getlist('insectImage')
        if not image_files:
            return HttpResponseBadRequest("Image files are required.")

        for image_file in image_files:
            img_id_without_extension, _ = os.path.splitext(image_file.name)
            file_path = os.path.join(settings.MEDIA_ROOT, 'images', image_file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
            InsectsImage.objects.create(
                img_id=img_id_without_extension,
                url=os.path.join('images', image_file.name).replace('\\', '/'),
                insects=insect
            )

        if not image_only:
            label_files = request.FILES.getlist('insectLabel')
            if not label_files:
                return HttpResponseBadRequest("Cần phải nhập ảnh khi nhập cả ảnh và nhãn.")

            for label_file in label_files:
                img_id_without_extension, _ = os.path.splitext(label_file.name)
                try:
                    image_entry = InsectsImage.objects.get(img_id=img_id_without_extension)
                    label_file_path = os.path.join(settings.MEDIA_ROOT, 'images', label_file.name)

                    with open(label_file_path, 'wb+') as destination:
                        for chunk in label_file.chunks():
                            destination.write(chunk)

                    with open(label_file_path, 'r') as file:
                        label_data = file.read().strip().split('\n')

                    for line in label_data:
                        parts = line.split()
                        if len(parts) == 5:
                            _, x, y, width, height = map(float, parts)
                            InsectsBbox.objects.create(
                                x=x, y=y, width=width, height=height,
                                img=image_entry
                            )

                except InsectsImage.DoesNotExist:
                    return JsonResponse({'success': False,
                                         'message': f"InsectsImage does not exist for img_id: {img_id_without_extension}"})

        return JsonResponse({'success': True, 'message': "Upload thành công!"})

    else:
        return JsonResponse({'success': False, 'message': "Invalid request method."})


# import_folder.html section
def upload_folder_zip(request):
    if request.method == "POST":
        species_id = request.POST.get("insectSelect")
        files = request.FILES.getlist("insectImage")

        for f in files:
            if zipfile.is_zipfile(f):
                with zipfile.ZipFile(f) as z:
                    for filename in z.namelist():
                        if filename.endswith(('.png', '.jpg', '.jpeg', '.txt')):
                            with z.open(filename) as file_content:
                                handle_uploaded_file(filename, file_content, species_id)
            else:
                handle_uploaded_file(f.name, f, species_id)

        return JsonResponse({"success": True})

    else:
        species_list = Species.objects.all()
        return render(request, 'import_folder.html', {'species_list': species_list})


def handle_uploaded_file(filename, file_content, species_id):
    species = Species.objects.get(pk=species_id)
    base_name = os.path.basename(filename)
    name, ext = os.path.splitext(base_name)
    file_path = f'images/{base_name}'

    # Save the file in storage
    content = file_content.read() if not isinstance(file_content, ContentFile) else file_content
    save_file_to_storage(file_path, content)

    if ext.lower() in ['.png', '.jpg', '.jpeg']:
        InsectsImage.objects.update_or_create(
            img_id=name,
            defaults={'url': file_path, 'insects': species}
        )

    elif ext.lower() == '.txt':
        # Assuming content needs decoding
        content_str = content.decode('utf-8') if isinstance(content, bytes) else content
        lines = content_str.strip().split('\n')
        try:
            img = InsectsImage.objects.get(img_id=name)
            for line in lines:
                # Split the line and map to float, skipping the class identifier
                parts = line.split()
                if len(parts) == 5:
                    x, y, width, height = map(float, parts[1:])  # Correctly unpack the 4 values
                    InsectsBbox.objects.create(x=x, y=y, width=width, height=height, img=img)
        except InsectsImage.DoesNotExist:
            print(f"No matching image found for label: {name}. Label not imported.")


def save_file_to_storage(file_path, file_content):
    # Ensure reading the content if it's not already in bytes format
    content = file_content if isinstance(file_content, bytes) else file_content.read()
    file = ContentFile(content)
    default_storage.save(file_path, file)


# def handle_uploaded_file(filename, file_content, species_id):
#     base_name, ext = os.path.splitext(filename)
#     species = Species.objects.get(pk=species_id)

#     if ext.lower() in ['.png', '.jpg', '.jpeg']:
#         # Handling image file
#         image_path = f'images/{filename}'
#         image_file = ContentFile(file_content.read())
#         default_storage.save(image_path, image_file)

#         # Create InsectsImage record
#         InsectsImage.objects.create(
#             img_id=base_name,
#             url=image_path,
#             insects=species
#         )

#     elif ext.lower() == '.txt':
#         # Handling label file
#         content = file_content.read().decode('utf-8')
#         lines = content.strip().split('\n')
#         for line in lines:
#             _, x, y, width, height = map(float, line.split())
#             try:
#                 img = InsectsImage.objects.get(img_id=base_name)
#                 InsectsBbox.objects.create(x=x, y=y, width=width, height=height, img=img)
#             except InsectsImage.DoesNotExist:
#                 print(f"Image {base_name} not found for bbox import.")


# crawl.html
def data_crawler(request):
    if request.method == 'POST':
        insect_id = request.POST.get('insectSelect')
        quantity = int(request.POST.get('quantity', 1))

        # Get insect details
        insect = Species.objects.get(insects_id=insect_id)

        # Download images
        images = download_images(insect.ename, quantity)

        # Save images to database
        save_images_to_database(images, insect_id)

        # Fetch saved images
        images = InsectsImage.objects.filter(insects_id=insect_id)

        data = {
            'success': True,
            'images': [{
                'url': image.get_absolute_url(),
                'img_id': image.img_id,
            } for image in images]
        }
        return JsonResponse(data)
    else:
        species_list = Species.objects.all()
        return render(request, 'crawler.html', {'species_list': species_list})


def cancel_crawling(request):
    delete_tmp_images()
    return JsonResponse({'success': True})


# def data_crawler(request):
#     species_list = Species.objects.all()
#     context = {'species_list': species_list}

#     # Include flags based on session values or other conditions
#     if 'upload_success' in request.session:
#         context['upload_success'] = True
#         del request.session['upload_success']
#     elif 'cancelled' in request.session:
#         context['cancelled'] = True
#         del request.session['cancelled']

#     return render(request, 'crawler.html', context)


# def upload_crawled_images(request):
#     if request.method == 'POST':
#         # Logic to handle images upload
#         return JsonResponse({'success': True})
#     return JsonResponse({'success': False}, status=400)


# def cancel_crawled_images(request):
#     if request.method == 'POST':
#         # Logic to delete temporary images
#         return JsonResponse({'success': True})
#     return JsonResponse({'success': False}, status=400)


# def ajax_crawl_images(request):
#     if request.method == 'POST':
#         ename = request.POST.get('ename')
#         quantity = int(request.POST.get('quantity'))
#         unique_id = crawl_images(ename, quantity)
#         image_urls = get_image_urls(unique_id)  # Implement this function to return the list of image URLs from tmp_crawler

#         return JsonResponse({'image_urls': image_urls})

#     return JsonResponse({'error': 'This method is not allowed'}, status=405)
# download folder


from django.http import StreamingHttpResponse, HttpResponseNotFound


def iter_file(file_path, chunk_size=8192):
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk


def download_folder(request):
    # Construct the full path to the zip file
    zip_path = os.path.join(settings.MEDIA_ROOT, 'images.zip')

    # Check if the zip file exists before attempting to serve it
    if not os.path.exists(zip_path):
        return HttpResponseNotFound("The requested zip file does not exist.")

    # Create a StreamingHttpResponse with the iter_file generator, set the appropriate content type
    response = StreamingHttpResponse(iter_file(zip_path), content_type='application/zip')

    # Set the Content-Disposition header to prompt a download dialog in the browser
    response['Content-Disposition'] = 'attachment; filename="images.zip"'

    return response


# Serializers

# Species API
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def species_list(request, format=None):
    if request.method == 'GET':
        species = Species.objects.all()
        serializer = SpeciesSerializer(species, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = SpeciesSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response({"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['GET', 'PUT', 'DELETE'])
def species_details(request, lookup):
    # Attempt to distinguish between ID and name based on the lookup's data type
    try:
        lookup_as_int = int(lookup)
        # If conversion succeeds, lookup by pk
        species = get_object_or_404(Species, pk=lookup_as_int)
    except ValueError:
        # If conversion fails, it's a name or slug
        species = get_object_or_404(Species, Q(name=lookup) | Q(slug=lookup))

    if request.method == "GET":
        serializer = SpeciesSerializer(species)
        return Response(serializer.data)
    elif request.method == "PUT":
        serializer = SpeciesSerializer(species, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == "DELETE":
        species.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Insects_Image API
@api_view(['GET', 'PUT', 'DELETE'])
def image_details(request, img_id):
    try:
        image = InsectsImage.objects.get(img_id=img_id)
    except InsectsImage.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ImageSerializer(image)
        return Response(serializer.data)
    elif request.method == 'PUT':
        serializer = ImageSerializer(image, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def get_insect_images(request, lookup):
    # Attempt to distinguish between ID and name based on the lookup's data type
    try:
        lookup_as_int = int(lookup)
        species = get_object_or_404(Species, pk=lookup_as_int)
    except ValueError:
        # If conversion fails, it's a name or slug
        species = get_object_or_404(Species, Q(name=lookup) | Q(ename=lookup) | Q(slug=lookup))

    images = InsectsImage.objects.filter(insects=species)
    serializer = ImageSerializer(images, many=True)
    return Response(serializer.data)


@api_view(['GET', 'PUT', 'DELETE'])
def species_images(request, lookup):
    try:
        # Attempt to distinguish between ID and name based on the lookup's data type
        lookup_as_int = int(lookup)
        species = get_object_or_404(Species, pk=lookup_as_int)
    except ValueError:
        # If conversion fails, it's a name or slug
        species = get_object_or_404(Species, Q(name=lookup) | Q(ename=lookup))

    images = InsectsImage.objects.filter(insects=species)
    context = {'request': request}
    serializer = ImageBoxSerializer(images, many=True, context=context)
    return Response(serializer.data)


class ImageUploadAPI(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        insects_id = request.data.get('insects_id')  # Get the insects_id from the request

        if not file:
            return JsonResponse({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Extract filename without extension for img_id
        file_name, file_extension = os.path.splitext(file.name)
        img_id = file_name

        # Validate the insects_id
        if insects_id:
            try:
                species_instance = Species.objects.get(insects_id=insects_id)
            except Species.DoesNotExist:
                return JsonResponse({'error': 'Species with the given ID does not exist'},
                                    status=status.HTTP_404_NOT_FOUND)
        else:
            species_instance = None

        # Save the file to the media folder
        storage_path = f"images/{uuid.uuid4()}_{file.name}"  # Keep the UUID to ensure unique paths
        path = default_storage.save(storage_path, file)

        # Create a new instance of InsectsImage with species_instance
        img_instance = InsectsImage(
            img_id=img_id,
            url=path,
            insects=species_instance  # Link the image to the species
        )
        img_instance.save()

        # Serialize and return the new image instance
        serializer = ImageSerializer(img_instance)
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
def species_images_bbox(request, id):
    try:
        species = Species.objects.get(pk=id)
    except Species.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        images = InsectsImage.objects.filter(insects=species)
        serializer = ImageBoxSerializer(images, many=True)
        return Response(serializer.data)


@api_view(['GET', 'PUT', 'DELETE'])
def bbox_details(request, img_id):
    try:
        image = InsectsImage.objects.get(img_id=img_id)
    except InsectsImage.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        bboxes = InsectsBbox.objects.filter(img=image)
        # Pass 'request' in the serializer context
        serializer = BoundingBoxSerializer(bboxes, many=True, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'PUT':
        # Assuming you send bbox data as a list of bbox objects to update
        # This part needs a more complex logic to match and update each bbox
        # Here is a simplistic approach just for demonstration
        data = request.data
        for bbox_data in data:
            bbox_id = bbox_data.get('box_id')
            bbox = InsectsBbox.objects.get(pk=bbox_id, img=image)
            serializer = BoundingBoxSerializer(bbox, data=bbox_data)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Bounding boxes updated."})

    elif request.method == 'DELETE':
        # This will delete all bboxes associated with the image
        InsectsBbox.objects.filter(img=image).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Misc

def export_data(request):
    # Call the function to generate and export the CSV file
    file_path = export_species_data_to_csv()  # Make sure this matches your updated function name

    # Open the file for reading in binary mode
    with open(file_path, 'rb') as file:
        # Set the content type for CSV and specify the file name
        response = HttpResponse(file.read(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="IP102_data.csv"'

        # Cleanup if necessary
        # os.remove(file_path)

    return response


def home_view(request):
    return render(request, "template_v2.html", {"MEDIA_URL": settings.MEDIA_URL})


def home_page(request):
    #return render(request, "home_page.html")
    home_view(request)

    classification = request.GET.get("classification", "")
    species_id = request.GET.get("species", "")

    species_lst = Species.objects.all()

    if classification and species_id:
        if classification == "class":
            species_lst = species_lst.filter(genus__family__order__class_field__class_id=species_id)
        elif classification == "order":
            species_lst = species_lst.filter(genus__family__order__order_id=species_id)
        elif classification == "family":
            species_lst = species_lst.filter(genus__family__family_id=species_id)
        elif classification == "genus":
            species_lst = species_lst.filter(genus__genus_id=species_id)

    for spc in species_lst:
        if spc.thumbnail is None:
            spc.thumbnail = os.path.join(settings.MEDIA_ROOT, "thumbnails", "noimage.jpg")
        spc.width = 40
        spc.height = 40

    return render(request, "home_page.html", {
        "species_lst": species_lst,
        "MEDIA_URL": settings.MEDIA_URL,
    })


def search_species(request):
    keyword = request.GET.get("keyword", "").strip()

    if keyword:
        exact_matches = Species.objects.filter(
            Q(ename__iexact=keyword) |
            Q(vi_name__iexact=keyword) |
            Q(eng_name__iexact=keyword) |
            Q(name__iexact=keyword) |
            Q(species_name__iexact=keyword)
        )

        if exact_matches.count() == 1:
            return redirect('detail', slug=exact_matches.first().slug)
        elif exact_matches.exists():
            species_lst = exact_matches
        else:
            species_lst = Species.objects.filter(
                Q(ename__icontains=keyword) |
                Q(vi_name__icontains=keyword) |
                Q(eng_name__icontains=keyword) |
                Q(name__icontains=keyword) |
                Q(species_name__icontains=keyword)
            )
    else:
        species_lst = Species.objects.all()

    for spc in species_lst:
        if spc.thumbnail is None:
            spc.thumbnail = os.path.join(settings.MEDIA_ROOT, "thumbnails", "noimage.jpg")
        spc.width = 40
        spc.height = 40

    return render(request, "home_page.html", {
        "species_lst": species_lst,
        "MEDIA_URL": settings.MEDIA_URL,
    })


def search_suggestions(request):
    keyword = request.GET.get("keyword", "").strip()

    results = []

    if keyword:
        species = Species.objects.filter(
            Q(ename__icontains=keyword) |
            Q(vi_name__icontains=keyword) |
            Q(eng_name__icontains=keyword) |
            Q(name__icontains=keyword) |
            Q(species_name__icontains=keyword)
        ).distinct()[:10]

        for spc in species:
            matched_field = ""

            # Xác định field nào match
            if keyword.lower() in (spc.vi_name or "").lower():
                matched_field = spc.vi_name
            elif keyword.lower() in (spc.ename or "").lower():
                matched_field = spc.ename
            elif keyword.lower() in (spc.eng_name or "").lower():
                matched_field = spc.eng_name
            elif keyword.lower() in (spc.species_name or "").lower():
                matched_field = spc.species_name
            elif keyword.lower() in (spc.name or "").lower():
                matched_field = spc.name

            results.append({
                "name": matched_field,
                "slug": spc.slug,
                "thumbnail": settings.MEDIA_URL + (spc.thumbnail if spc.thumbnail else "thumbnails/noimage.jpg")
            })

    return JsonResponse(results, safe=False)


def get_species_options(request):
    species_type = request.GET.get("type", "")

    data = []
    if species_type == "class":
        data = list(Class.objects.values("class_id", "ename"))
    elif species_type == "order":
        data = list(Order.objects.values("order_id", "ename"))
    elif species_type == "family":
        data = list(Family.objects.values("family_id", "ename"))
    elif species_type == "genus":
        data = list(Genus.objects.values("genus_id", "ename"))

    return JsonResponse({"data": data})


# Description #
# annotations section
def add_desc(request):
    insect_id = request.GET.get('insectId')
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 20))  # Mặc định mỗi lần load 20 ảnh

    request_desc = RequestDesc.objects.filter(user=request.user).order_by('-created_at')

    if insect_id:
        images = InsectsImage.objects.filter(insects_id=insect_id).prefetch_related('bboxes')[offset:offset + limit]
        total_images = InsectsImage.objects.filter(insects_id=insect_id).count()

        images_data = []
        for image in images:
            img_path = os.path.join(settings.MEDIA_ROOT, image.url)
            with Image.open(img_path) as img:
                img_width, img_height = img.size

            bboxes_data = []
            for bbox in image.bboxes.all():
                x_top_left, y_top_left, box_width, box_height = convert_yolo_to_pixel(
                    bbox.x, bbox.y, bbox.width, bbox.height, img_width, img_height)
                bboxes_data.append({
                    'x': x_top_left, 'y': y_top_left,
                    'width': box_width, 'height': box_height
                })

            images_data.append({
                'img_id': image.img_id,
                'url': settings.MEDIA_URL + image.url,
                'width': img_width,
                'height': img_height,
                'insectsId': image.insects_id,
                'insectsName': image.insects.name,
                'bboxes': bboxes_data,
            })

        # Kiểm tra còn ảnh để load không
        has_more = offset + limit < total_images

        return JsonResponse({'images': images_data, 'has_more': has_more})

    species_list = Species.objects.all()
    return render(request, 'add_desc.html', {'species_list': species_list, 'request_desc': request_desc})


def add_desc_step2(request):
    img_id = request.GET.get('img_id')
    if not img_id:
        return HttpResponseBadRequest("Thiếu img_id!")  # Sửa lỗi thiếu img_id

    try:
        image = InsectsImage.objects.get(img_id=img_id)
        request_desc = RequestDesc.objects.filter(img_id=img_id, user=request.user).order_by('-created_at')
    except InsectsImage.DoesNotExist:
        return HttpResponseNotFound("Không tìm thấy hình ảnh!")  # Sửa lỗi không tìm thấy hình ảnh

    specie = Species.objects.filter(insects_id=image.insects_id).first()

    return render(request, 'add_desc_step2.html', {
        'img_info': image,
        'specie': specie,
        'MEDIA_URL': settings.MEDIA_URL,
        'request_desc': request_desc
    })


## add desc
def add_desc_handler(request, img_id):
    try:
        image = InsectsImage.objects.get(img_id=img_id)
    except InsectsImage.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'POST':
        new_desc = request.POST.get('new_desc', '').strip()
        if not new_desc:
            messages.error(request, 'Mô tả không được để trống!')
            return redirect(f"/add_desc_step2/?img_id={img_id}")  # Giữ nguyên trang nếu lỗi

        request_desc = RequestDesc.objects.create(
            img=image,
            desc=new_desc,
            user=request.user,
            status='pending',
            verification_count=0
        )
        try:
            cv_group = Group.objects.get(name="CVs")
            experts = cv_group.user_set.all()
            expert_emails = [expert.email for expert in experts if expert.email]

            if expert_emails:
                subject = "Thông báo: Có đóng góp mô tả hình ảnh mới"
                message = (
                    f"Xin chào chuyên gia,\n\n"
                    f"- Người dùng {request.user.username} vừa đóng góp một mô tả hình ảnh mới.\n- Chuyên gia có thể truy cập vào hệ thống để xét duyệt mô tả ảnh.\n"
                    f"- Thời gian: {timezone.localtime(request_desc.created_at).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                    f"Trân trọng,\nHệ thống quản lý côn trùng"
                )
                from_email = "no-reply@yourdomain.com"
                send_mail(subject, message, from_email, expert_emails, fail_silently=True)
                print(f"Email sent to: {expert_emails}")
            else:
                print("Không có chuyên gia nào trong nhóm 'CVs' có email!")
        except Group.DoesNotExist:
            print("Nhóm 'CVs' không tồn tại trong cơ sở dữ liệu!")

        return redirect(f"/add_desc_step2/?img_id={img_id}&success=true")


def cv_desc_verify(request):
    # Fetch requests and include related user data
    requests = RequestDesc.objects.select_related('user', 'img').filter(status='pending')

    for index, request_item in enumerate(requests, start=1):
        request_item.index = index

    return render(request, 'cv_desc_verify.html', {'requests': requests, 'MEDIA_URL': settings.MEDIA_URL})


def verify_desc_request(request, request_desc_id):
    request_item = get_object_or_404(RequestDesc.objects.select_related('user'), pk=request_desc_id)
    image = InsectsImage.objects.get(img_id=request_item.img_id)
    specie = Species.objects.filter(insects_id=image.insects_id).first()
    has_verified = VerificationLog.objects.filter(
        user=request.user,
        request_type='desc',
        object_id=request_desc_id
    ).exists()

    if request.method == 'POST':
        request_item.verification_count = (request_item.verification_count or 0) + 1

        VerificationLog.objects.get_or_create(
            user=request.user,
            request_type='desc',
            object_id=request_desc_id
        )

        # cvs_group = Group.objects.get(name='CVs')
        # cvs_user_count = cvs_group.user_set.count()
        # threshold = math.ceil(0.8 * cvs_user_count)

        # Compare verification count with the calculated threshold
        if request_item.verification_count >= 3:
            request_item.status = 'verified'

        request_item.save()
        messages.success(request, 'Xác thực thành công!')

        # Chuyển hướng về cùng trang để modal hiển thị
        return redirect(request.path)

    return render(request, 'add_desc_verify.html', {
        'request_item': request_item,
        'img_info': image,
        'specie': specie,
        'has_verified': has_verified,
        'MEDIA_URL': settings.MEDIA_URL
    })


def admin_desc_verify(request):
    # Fetch requests and include related user data
    requests = RequestDesc.objects.select_related('user', 'img').filter(status='verified')

    for index, request_item in enumerate(requests, start=1):
        request_item.index = index

    return render(request, 'admin_desc_verify.html', {'requests': requests, 'MEDIA_URL': settings.MEDIA_URL})


def accept_desc_request(request, request_desc_id):
    request_item = get_object_or_404(RequestDesc.objects.select_related('user'), pk=request_desc_id)
    image = get_object_or_404(InsectsImage, img_id=request_item.img_id)
    specie = Species.objects.filter(insects_id=image.insects_id).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            request_item.status = 'Accepted'
            request_item.save()
            image.desc = request_item.desc
            image.save()
            messages.success(request, 'Mô tả đã được chấp nhận và thêm vào ảnh.')
            return redirect(request.path)
        elif action == 'reject':
            request_item.status = 'Rejected'
            request_item.save()
            messages.warning(request, 'Mô tả đã bị từ chối.')
            return redirect(request.path)

    return render(request, 'accept_desc.html', {
        'request_item': request_item,
        'img_info': image,
        'specie': specie,
        'MEDIA_URL': settings.MEDIA_URL
    })


def species_list(request):
    # page_number = request.GET.get('page', 1)  # Get the page number from the request
    species_lst = Species.objects.all()
    # paginator = Paginator(species_lst, 20)  # Create a Paginator object with 20 images per page
    # species_lst = paginator.get_page(page_number)  # Get the images for the requested page
    # print('thum',species_lst[1].thumbnail)
    for spc in species_lst:
        # Open the image and get its size
        if spc.thumbnail is None:
            spc.thumbnail = os.path.join("thumbnails", "noimage.jpg")
            # img_path = os.path.join(settings.MEDIA_ROOT,os.path.normpath(spc.thumbnail))
            # with Image.open(img_path) as img:
            #    img_width, img_height = img.size

        spc.width = 40
        spc.height = 40
    return render(request, 'species_list.html', {'species_lst': species_lst, 'MEDIA_URL': settings.MEDIA_URL})


def load_specie_image(request):
    page_number = request.GET.get('page', 1)  # Get the page number from the request
    spc_id = request.GET.get('specie_id', None)
    # print("spc_id",spc_id)
    images = InsectsImage.objects.filter(insects_id=spc_id).prefetch_related('bboxes')
    specie_info = Species.objects.filter(insects_id=spc_id).first()
    paginator = Paginator(images, 20)  # Create a Paginator object with 20 images per page
    page_obj = paginator.get_page(page_number)  # Get the images for the requested page
    # print("page_obj len",len(page_obj))
    # Convert the bounding box coordinates for each image
    for image in page_obj:
        # Open the image and get its size
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        with Image.open(img_path) as img:
            img_width, img_height = img.size

        image.width = img_width
        image.height = img_height
        image.desc = image.desc

        for bbox in image.bboxes.all():
            bbox.x, bbox.y, bbox.width, bbox.height = convert_yolo_to_pixel(bbox.x, bbox.y, bbox.width, bbox.height,
                                                                            img_width, img_height)

    return render(request, 'load_specie_image.html',
                  {'page_obj': page_obj, 'specie_id': spc_id, 'specie_info': specie_info,
                   'MEDIA_URL': settings.MEDIA_URL})


# document
def document_list(request):
    search_query = request.GET.get('search', '').strip()  # Lấy từ khóa tìm kiếm từ request
    documents = Document.objects.all()

    if search_query:
        documents = documents.filter(doc_name__icontains=search_query)  # Lọc theo tên tài liệu

    return render(request, 'document.html', {'documents': documents, 'search_query': search_query})


def view_document(request, doc_id):
    document = get_object_or_404(Document, doc_id=doc_id)
    return render(request, 'view_document.html', {'document': document, 'MEDIA_URL': settings.MEDIA_URL})


def download_document(request, doc_id):
    document = get_object_or_404(Document, pk=doc_id)
    file_path = os.path.join(settings.MEDIA_ROOT, str(document.url))

    return FileResponse(open(file_path, 'rb'), as_attachment=True)


def normalize_filename(filename):
    name, ext = os.path.splitext(filename)
    name = unidecode(name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
    return f"{name}{ext}"


def upload_document(request):
    if request.method == "POST" and request.FILES.get("doc_file"):
        doc_name = request.POST.get("doc_name")
        doc_file = request.FILES["doc_file"]

        if not doc_file.name.endswith(".pdf"):
            return JsonResponse({"success": False, "message": "Chỉ chấp nhận file PDF."})

        try:
            normalized_filename = doc_file.name.replace(" ", "_")  # Chuẩn hóa tên file
            file_name = f"documents/{normalized_filename}"
            file_path = default_storage.save(file_name, ContentFile(doc_file.read()))

            Document.objects.create(doc_name=doc_name, url=file_path)

            return JsonResponse({"success": True, "message": "Tải lên tài liệu thành công!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": f"Lỗi: {str(e)}"})

    return JsonResponse({"success": False, "message": "Tải lên thất bại."})


def delete_document(request, doc_id):
    if request.method == "POST":
        document = get_object_or_404(Document, doc_id=doc_id)

        if document.url:
            file_path = os.path.join(default_storage.location, document.url)
            if os.path.exists(file_path):
                os.remove(file_path)

        document.delete()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "message": "Phương thức không hợp lệ!"})


# account_info
@login_required()
def account_info(request):
    user = request.user
    context = {
        "username": user.username,
        "last_name": user.last_name,
        "first_name": user.first_name,
        "email": user.email,
        "last_login": user.last_login,
        "groups": user.groups.all(),
    }
    # print(context)
    return render(request, "account_info.html", context)


@login_required
def edit_account(request):
    if request.method == "POST":
        user = request.user
        user.username = request.POST["username"]
        user.last_name = request.POST["last_name"]
        user.first_name = request.POST["first_name"]
        user.email = request.POST["email"]
        user.save()
        success_message = "Cập nhật thông tin thành công!"
        return render(request, "account_info.html", {
            "success_message": success_message,
            "username": user.username,
            "last_name": user.last_name,
            "first_name": user.first_name,
            "email": user.email,
            "last_login": user.last_login,
            "groups": user.groups.all(),
        })
    return redirect("account_info")



@login_required
def change_password(request):
    if request.method == "POST":
        user = request.user
        old_password = request.POST["old_password"]
        new_password = request.POST["new_password"]
        confirm_password = request.POST["confirm_password"]

        if not user.check_password(old_password):
            return render(request, "account_info.html", {
                "success_message": "Mật khẩu cũ không chính xác!",
                "username": user.username,
                "last_name": user.last_name,
                "first_name": user.first_name,
                "email": user.email,
                "last_login": user.last_login,
                "groups": user.groups.all(),
            })
        if new_password != confirm_password:
            return render(request, "account_info.html", {
                "success_message": "Mật khẩu mới không khớp!",
                "username": user.username,
                "last_name": user.last_name,
                "first_name": user.first_name,
                "email": user.email,
                "last_login": user.last_login,
                "groups": user.groups.all(),
            })

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)  # Giữ người dùng đăng nhập
        return render(request, "account_info.html", {
            "success_message": "Thay đổi mật khẩu thành công!",
            "username": user.username,
            "last_name": user.last_name,
            "first_name": user.first_name,
            "email": user.email,
            "last_login": user.last_login,
            "groups": user.groups.all(),
        })

    return redirect("account_info")


# trang thong ke
@login_required()
def statistics_view(request):
    total_image = InsectsImage.objects.count()
    total_user = User.objects.count()
    total_class = Class.objects.count()
    total_order = Order.objects.count()
    total_family = Family.objects.count()
    total_genus = Genus.objects.count()
    total_species = Species.objects.count()

    user_groups = Group.objects.annotate(user_count=Count('user'))
    order_class = Class.objects.annotate(order_count=Count('order'))
    family_order = Order.objects.annotate(family_count=Count('family'))
    genus_family = Family.objects.annotate(genus_count=Count('genus'))
    species_genus = Genus.objects.annotate(species_count=Count('species'))
    img_species = Species.objects.annotate(img_count=Count('insectsimage'))

    return render(request, "statistics.html", {
        'total_image': total_image,
        'total_user': total_user,
        'user_groups': user_groups,
        'total_class': total_class,
        'total_order': total_order,
        'total_family': total_family,
        'total_genus': total_genus,
        'total_species': total_species,
        'order_class': order_class,
        'family_order': family_order,
        'genus_family': genus_family,
        'species_genus': species_genus,
        'img_species': img_species,
    })


# thong ke anh con trung
@login_required()
def get_species_img_chart(request):
    Images_by_species = InsectsImage.objects.values('insects__name').annotate(count=Count('img_id')).order_by('-count')
    species_dict = {s['insects__name']: s['count'] for s in Images_by_species}

    colorPrimary = "#79aec8"

    response_data = {
        "title": "Số lượng ảnh của từng loài",
        "data": {
            "labels": list(species_dict.keys()),
            "datasets": [{
                "label": "Số lượng ảnh",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": list(species_dict.values())
            }]
        }
    }
    return JsonResponse(response_data)


# thong ke nguoi dung
@login_required()
def user_by_group_chart(request):
    groups = Group.objects.all()
    labels = []
    data = []

    for group in groups:
        labels.append(group.name)
        data.append(group.user_set.count())

    response_data = {
        "title": "Thống kê số lượng tài khoản theo nhóm",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Số lượng người dùng",
                "data": data,
                "backgroundColor": [
                    "#FF6384", "#36A2EB", "#FFCE56", "#4CAF50", "#9C27B0"
                ]
            }]
        }
    }
    return JsonResponse(response_data)


@login_required()
def order_by_class_chart(request):
    classes = Class.objects.annotate(count=Count('order')).order_by('-count')
    labels = []
    data = []

    for cls in classes:
        labels.append(cls.name)
        data.append(cls.count)

    response_data = {
        "title": "Thống kê số lượng bộ theo lớp",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Số lượng bộ",
                "data": data,
                "backgroundColor": "#4BC0C0"
            }]
        }
    }
    return JsonResponse(response_data)


@login_required()
def family_by_order_chart(request):
    orders = Order.objects.annotate(count=Count('family')).order_by('-count')
    labels = []
    data = []

    for order in orders:
        labels.append(order.name)
        data.append(order.count)

    response_data = {
        "title": "Thống kê số lượng họ theo bộ",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Số lượng họ",
                "data": data,
                "backgroundColor": "#FF9F40"
            }]
        }
    }
    return JsonResponse(response_data)


@login_required()
def genus_by_family_chart(request):
    families = Family.objects.annotate(count=Count('genus')).order_by('-count')
    labels = []
    data = []

    for family in families:
        labels.append(family.name)
        data.append(family.count)

    response_data = {
        "title": "Thống kê số lượng chi theo họ",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Số lượng chi",
                "data": data,
                "backgroundColor": "#36A2EB"
            }]
        }
    }
    return JsonResponse(response_data)


@login_required()
def species_by_genus_chart(request):
    genera = Genus.objects.annotate(count=Count('species')).order_by('-count')
    labels = []
    data = []

    for genus in genera:
        labels.append(genus.name)
        data.append(genus.count)

    response_data = {
        "title": "Thống kê số lượng loài theo chi",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Số lượng loài",
                "data": data,
                "backgroundColor": "#9966FF"
            }]
        }
    }
    return JsonResponse(response_data)


# Manage user
@login_required()
def manage_user(request):
    users = User.objects.exclude(id=request.user.id)
    groups = Group.objects.all()

    # Xử lý tìm kiếm
    search_query = request.GET.get('search', '').strip()
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    # Xử lý sắp xếp
    sort_by = request.GET.get('sort', 'username')  # Mặc định sắp xếp theo username
    sort_order = request.GET.get('order', 'asc')

    if sort_by == "group":
        subquery = Group.objects.filter(user=OuterRef('id')).values('name')[:1]
        users = users.annotate(group_name=Subquery(subquery))  # Lấy tên nhóm đầu tiên
        sort_by = "group_name"

    if sort_order == 'desc':
        users = users.order_by(f'-{sort_by}')
    else:
        users = users.order_by(sort_by)

    # Xử lý lọc
    filter_group = request.GET.get('group', '')
    if filter_group:
        users = users.filter(groups__name=filter_group)

    filter_last_login = request.GET.get('last_login', '')
    if filter_last_login:
        users = users.filter(last_login__date=filter_last_login)

    return render(request, 'manage_user.html', {
        'users': users,
        'groups': groups,
        'search_query': search_query,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'filter_group': filter_group,
        'filter_last_login': filter_last_login
    })


@login_required()
def add_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        user_group = request.POST.get("user_group")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Người dùng đã tồn tại!")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Email đã được người dùng khác đăng ký!")
        else:
            user = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=make_password(password),
                is_active=True
            )

            if user_group:
                group = Group.objects.get(name=user_group)
                user.groups.add(group)
                if group.name == "Admins":
                    user.is_staff = True
                    user.save()

            messages.success(request, "Thêm người dùng thành công!")
        return redirect("add_user")

        # Lấy danh sách group để hiển thị trong form
    groups = Group.objects.all()
    return render(request, "add_user.html", {"groups": groups})


@login_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    success = False

    if request.method == "POST":
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            user.groups.clear()

            if form.cleaned_data['groups']:
                selected_group = form.cleaned_data['groups']
                user.groups.set([selected_group])
                if selected_group.name == "Admins":
                    user.is_staff = True
                else:
                    user.is_staff = False

            user.is_active = form.cleaned_data['is_active']

            user.save()
            success = True
    else:
        form = UserEditForm(instance=user)

    return render(request, 'edit_user.html', {'form': form, 'user': user, 'success': success})


@login_required()
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user.delete()
        messages.success(request, f"Đã xóa người dùng {user.username} thành công!")

    return redirect('manage_user')


# manage insect
@login_required()
def manage_insect(request):
    classes = Class.objects.all()
    order = Order.objects.all()
    family = Family.objects.all()
    genus = Genus.objects.all()
    species = Species.objects.all()

    search_class_query = request.GET.get('search_class', '').strip()
    if search_class_query:
        classes = classes.filter(
            Q(ename__icontains=search_class_query) |
            Q(name__icontains=search_class_query)
        )

    search_order_query = request.GET.get('search_order', '').strip()
    if search_order_query:
        order = order.filter(
            Q(ename__icontains=search_order_query) |
            Q(name__icontains=search_order_query)
        )

    search_family_query = request.GET.get('search_family', '').strip()
    if search_family_query:
        family = family.filter(
            Q(ename__icontains=search_family_query) |
            Q(name__icontains=search_family_query)
        )

    search_genus_query = request.GET.get('search_genus', '').strip()
    if search_genus_query:
        genus = genus.filter(
            Q(ename__icontains=search_genus_query) |
            Q(name__icontains=search_genus_query)
        )

    search_species_query = request.GET.get('search_species', '').strip()
    if search_species_query:
        species = species.filter(
            Q(ename__icontains=search_species_query) |
            Q(name__icontains=search_species_query) |
            Q(species_name__icontains=search_species_query) |
            Q(eng_name__icontains=search_species_query) |
            Q(vi_name__icontains=search_species_query)
        )

    return render(request, 'manage_insect.html', {
        'classes': classes,
        'orders': order,
        'family': family,
        'genus': genus,
        'species': species,
        'search_class_query': search_class_query,
        'search_order_query': search_order_query,
        'search_family_query': search_family_query,
        'search_genus_query': search_genus_query,
        'search_species_query': search_species_query,
        'MEDIA_URL': settings.MEDIA_URL
    })


# =======Add=======
# Add class
@login_required()
def add_class(request):
    if request.method == "POST":
        ename = request.POST.get("ename")
        name = request.POST.get("name")
        phylum_id = request.POST.get("phylum")

        if Class.objects.filter(ename=ename).exists():
            messages.error(request, "Lớp đã tồn tại!")
        else:
            try:
                phy = Phylum.objects.get(pk=phylum_id)
            except Phylum.DoesNotExist:
                messages.error(request, "Ngành không tồn tại!")
                return redirect("add_class")

            slug = f"class_{ename.replace(' ', '_')}"

            classes = Class.objects.create(
                ename=ename,
                name=name,
                slug=slug,
                phylum=phy,
            )

            messages.success(request, "Thêm lớp thành công!")
        return redirect("add_class")

    phylum = Phylum.objects.all()
    return render(request, "add_class.html", {"phylum": phylum})


# ======================Add=========================
# Add order
@login_required()
def add_order(request):
    if request.method == "POST":
        ename = request.POST.get("ename")
        name = request.POST.get("name")
        class_id = request.POST.get("classes")

        if Order.objects.filter(ename=ename).exists():
            messages.error(request, "Bộ đã tồn tại!")
        else:
            try:
                classes = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                messages.error(request, "Lớp không tồn tại!")
                return redirect("add_order")

            slug = f"order_{ename.replace(' ', '_')}"

            order = Order.objects.create(
                ename=ename,
                name=name,
                slug=slug,
                class_field=classes,
            )

            messages.success(request, "Thêm bộ thành công!")
        return redirect("add_order")

    classes = Class.objects.all()
    return render(request, "add_order.html", {"classes": classes})


# Add family
@login_required()
def add_family(request):
    if request.method == "POST":
        ename = request.POST.get("ename")
        name = request.POST.get("name")
        order_id = request.POST.get("order")

        if Family.objects.filter(ename=ename).exists():
            messages.error(request, "Họ đã tồn tại!")
        else:
            try:
                order = Order.objects.get(pk=order_id)
            except Order.DoesNotExist:
                messages.error(request, "Bộ không tồn tại!")
                return redirect("add_family")

            slug = f"family_{ename.replace(' ', '_')}"

            family = Family.objects.create(
                ename=ename,
                name=name,
                slug=slug,
                order=order,
            )

            messages.success(request, "Thêm họ thành công!")
        return redirect("add_family")

    order = Order.objects.all()
    return render(request, "add_family.html", {"order": order})


# Add genus
@login_required()
def add_genus(request):
    if request.method == "POST":
        ename = request.POST.get("ename")
        name = request.POST.get("name")
        family_id = request.POST.get("family")

        if Genus.objects.filter(ename=ename).exists():
            messages.error(request, "Chi đã tồn tại!")
        else:
            try:
                family = Family.objects.get(pk=family_id)
            except Family.DoesNotExist:
                messages.error(request, "Họ không tồn tại!")
                return redirect("add_family")

            slug = f"genus_{ename.replace(' ', '_')}"

            genus = Genus.objects.create(
                ename=ename,
                name=name,
                slug=slug,
                family=family,
            )

            messages.success(request, "Thêm chi thành công!")
        return redirect("add_family")

    family = Family.objects.all()
    return render(request, "add_genus.html", {"family": family})


# Add species
@login_required()
def add_species(request):
    if request.method == "POST":
        ename = request.POST.get("ename")
        name = request.POST.get("name")
        species_name = request.POST.get("speciesName")
        eng_name = request.POST.get("engName")
        vi_name = request.POST.get("viName")
        morphologic_feature = request.POST.get("morphologicFeature")
        distribution = request.POST.get("distribution")
        characteristic = request.POST.get("characteristic")
        behavior = request.POST.get("behavior")
        protection_method = request.POST.get("protectionMethod")
        genus_id = request.POST.get("genus")

        if Species.objects.filter(ename=ename).exists():
            messages.error(request, "Loài đã tồn tại!")
        else:
            try:
                genus = Genus.objects.get(pk=genus_id)
            except Genus.DoesNotExist:
                messages.error(request, "Chi không tồn tại!")
                return redirect("add_species")

            slug = f"insect_{ename.replace(' ', '_')}"

            thumbnail = None  # Định nghĩa biến từ đầu
            if request.FILES.get("thumbnail"):  # Nếu có file ảnh
                file = request.FILES["thumbnail"]
                fs = FileSystemStorage(location="media/thumbnails/")
                filename = fs.save(file.name, file)
                thumbnail = f"thumbnails/{filename}"

            species = Species.objects.create(
                ename=ename,
                name=name,
                species_name=species_name,
                eng_name=eng_name,
                vi_name=vi_name,
                slug=slug,
                morphologic_feature=morphologic_feature,
                distribution=distribution,
                characteristic=characteristic,
                behavior=behavior,
                protection_method=protection_method,
                genus=genus,
                thumbnail=thumbnail,
                is_new=True
            )

            messages.success(request, "Thêm loài thành công!")
        return redirect("add_species")

    genus = Genus.objects.all()
    return render(request, "add_species.html", {"genus": genus})


# ======Delete=====
# Delete class
@login_required()
def delete_class(request, class_id):
    classes = get_object_or_404(Class, class_id=class_id)

    if Order.objects.filter(class_field=classes).exists():
        messages.error(request,
                       f"Không thể xóa lớp {classes.ename}! Hãy xóa các bộ thuộc lớp {classes.ename} trước khi xóa lớp này!")
        return redirect("manage_insect")

    if request.method == "POST":
        classes.delete()
        messages.success(request, f"Đã xóa lớp {classes.ename} thành công!")

    return redirect('manage_insect')


# Delete class
@login_required()
def delete_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if Family.objects.filter(order=order).exists():
        messages.error(request,
                       f"Không thể xóa bộ {order.ename}! Hãy xóa các họ thuộc bộ {order.ename} trước khi xóa bộ này!")
        return redirect("manage_insect")

    if request.method == "POST":
        order.delete()
        messages.success(request, f"Đã xóa bộ {order.ename} thành công!")

    return redirect('manage_insect')


# Delete family
@login_required()
def delete_family(request, family_id):
    family = get_object_or_404(Family, family_id=family_id)

    if Genus.objects.filter(family=family).exists():
        messages.error(request,
                       f"Không thể xóa họ {family.ename}! Hãy xóa các chi thuộc họ {family.ename} trước khi xóa họ này!")
        return redirect("manage_insect")

    if request.method == "POST":
        family.delete()
        messages.success(request, f"Đã xóa họ {family.ename} thành công!")

    return redirect('manage_insect')


# Delete genus
@login_required()
def delete_genus(request, genus_id):
    genus = get_object_or_404(Genus, genus_id=genus_id)

    if Species.objects.filter(genus=genus).exists():
        messages.error(request,
                       f"Không thể xóa chi {genus.ename}! Hãy xóa các loài thuộc chi {genus.ename} trước khi xóa chi này!")
        return redirect("manage_insect")

    if request.method == "POST":
        genus.delete()
        messages.success(request, f"Đã xóa chi {genus.ename} thành công!")

    return redirect('manage_insect')


# Delete species
@login_required()
def delete_species(request, insects_id):
    species = get_object_or_404(Species, insects_id=insects_id)

    if InsectsImage.objects.filter(insects=species).exists():
        messages.error(request, f"Không thể xóa loài {species.ename}!")
        return redirect("manage_insect")

    if species.thumbnail:
        thumbnail_path = os.path.join(settings.MEDIA_ROOT, species.thumbnail)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

    if request.method == "POST":
        species.delete()
        messages.success(request, f"Đã xóa loài {species.ename} thành công!")

    return redirect('manage_insect')


# =========================Edit=========================
# Edit class
@login_required()
def edit_class(request, class_id):
    classes = get_object_or_404(Class, class_id=class_id)
    success = False

    if request.method == "POST":
        form = ClassesEditForm(request.POST, instance=classes)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = ClassesEditForm(instance=classes)

    return render(request, 'edit_class.html', {'form': form, 'success': success})


# Edit order
@login_required()
def edit_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    success = False

    if request.method == "POST":
        form = OrderEditForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = OrderEditForm(instance=order)

    return render(request, 'edit_order.html', {'form': form, 'success': success})


# Edit order
@login_required()
def edit_family(request, family_id):
    family = get_object_or_404(Family, family_id=family_id)
    success = False

    if request.method == "POST":
        form = FamilyEditForm(request.POST, instance=family)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = FamilyEditForm(instance=family)

    return render(request, 'edit_family.html', {'form': form, 'success': success})


# Edit genus
@login_required()
def edit_genus(request, genus_id):
    genus = get_object_or_404(Genus, genus_id=genus_id)
    success = False

    if request.method == "POST":
        form = GenusEditForm(request.POST, instance=genus)
        if form.is_valid():
            form.save()
            success = True
    else:
        form = GenusEditForm(instance=genus)

    return render(request, 'edit_genus.html', {'form': form, 'success': success})


# Edit species
@login_required()
def edit_species(request, insects_id):
    species = get_object_or_404(Species, insects_id=insects_id)
    old_thumbnail = species.thumbnail
    success = False
    if request.method == "POST":
        form = SpeciesEditForm(request.POST, request.FILES, instance=species)
        if form.is_valid():
            instance = form.save(commit=False)
            if request.FILES.get("thumbnail"):
                file = request.FILES["thumbnail"]
                fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "thumbnails/"))
                filename = fs.save(file.name, file)
                instance.thumbnail = f"thumbnails/{filename}"

                if old_thumbnail:
                    old_thumbnail_path = os.path.join(settings.MEDIA_ROOT, old_thumbnail)
                    if os.path.exists(old_thumbnail_path):
                        os.remove(old_thumbnail_path)

            else:
                instance.thumbnail = old_thumbnail

            instance.save()
            success = True
    else:
        form = SpeciesEditForm(instance=species)

    return render(request, 'edit_species.html', {'form': form, 'success': success})


# Manage insect image desc
@login_required()
def manage_image_desc(request):
    images_list = InsectsImage.objects.select_related("insects").all()
    species_filter = request.GET.get("species", "")

    if species_filter:
        images_list = images_list.filter(insects__insects_id=species_filter)

    paginator = Paginator(images_list, 30)
    page_number = request.GET.get("page")
    images = paginator.get_page(page_number)

    species_list = Species.objects.all()

    success = False

    if request.method == "POST":
        img_id = request.POST.get("img_id")
        image = get_object_or_404(InsectsImage, img_id=img_id)
        form = InsectsImageForm(request.POST, instance=image)

        if form.is_valid():
            form.save()
            success = True

    else:
        form = InsectsImageForm()

    return render(request, 'manage_image_desc.html', {
        'images': images,
        'form': form,
        'success': success,
        'species_list': species_list,
        'selected_species': species_filter,
    })


@login_required
def manage_label_n_bbox(request):
    # Lấy danh sách loài
    species_list = Species.objects.all()

    # Lọc hình ảnh chưa có bounding box cho tab "Gán nhãn"
    images_without_bbox = InsectsImage.objects.select_related("insects").filter(bboxes__isnull=True).order_by("img_id",
                                                                                                              "pk")
    selected_species_add = request.GET.get("species_add", "")
    if selected_species_add:
        images_without_bbox = images_without_bbox.filter(insects__insects_id=selected_species_add)

    # Phân trang hình ảnh chưa có bounding box
    paginator_images = Paginator(images_without_bbox, 30)
    page_number_images = request.GET.get("page_images")
    images_without_bbox_paginated = paginator_images.get_page(page_number_images)

    # Lọc hình ảnh có bounding boxes cho tab "Chỉnh sửa nhãn"
    images_with_bbox = InsectsImage.objects.filter(bboxes__isnull=False).distinct().order_by("img_id")

    selected_species_edit = request.GET.get("species_edit", "")
    if selected_species_edit:
        images_with_bbox = images_with_bbox.filter(insects__insects_id=selected_species_edit)

    # Phân trang theo hình ảnh (mỗi trang 30 ảnh)
    paginator_bbox_images = Paginator(images_with_bbox, 30)
    page_number_bbox = request.GET.get("page_bbox")
    bboxes_images_paginated = paginator_bbox_images.get_page(page_number_bbox)

    # Lấy danh sách bounding box theo hình ảnh sau khi phân trang
    bbox_list = InsectsBbox.objects.select_related("img__insects").filter(img__in=bboxes_images_paginated).order_by(
        "img__img_id", "box_id")

    # Nhóm bounding box theo hình ảnh
    grouped_bboxes = {}
    for img, boxes in groupby(bbox_list, key=lambda x: x.img):
        grouped_bboxes[img] = list(boxes)

    return render(request, 'manage_label_n_bbox.html', {
        'bboxes_grouped': grouped_bboxes,
        'species_list': species_list,
        'selected_species_add': selected_species_add,
        'selected_species_edit': selected_species_edit,
        'images_without_bbox': images_without_bbox_paginated,
        'bboxes_images_paginated': bboxes_images_paginated,
    })


def manage_image(request):
    species_list = Species.objects.all()

    species_filter = request.GET.get("species_filter", "")

    if species_filter:
        images = InsectsImage.objects.filter(insects__insects_id=species_filter)
    else:
        images = InsectsImage.objects.all()

    images = images.order_by("img_id")

    paginator_images = Paginator(images, 30)
    page_number_images = request.GET.get("page_images")
    images = paginator_images.get_page(page_number_images)

    return render(request, 'manage_image.html', {
        'images': images,
        'species_list': species_list,
        'selected_species_filter': species_filter,
    })


def delete_image(request, img_id):
    if request.method == "POST":
        try:
            image = get_object_or_404(InsectsImage, img_id=img_id)
            image_path = os.path.join(settings.MEDIA_ROOT, image.url)

            image.delete()

            if os.path.exists(image_path):
                os.remove(image_path)

            return JsonResponse({"success": True, "message": "Ảnh đã được xóa thành công!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": f"Lỗi khi xóa ảnh: {str(e)}"})

    return JsonResponse({"success": False, "message": "Lỗi! Không thể xóa ảnh."}, status=400)


# ==========================================================
# def image_search(request):
#     return render(request, 'detect_insect.html')

# Phát hiện côn trùng sơ bộ
def detect_insect_by_yolo(image_path):
    model_path = os.path.join(settings.MEDIA_ROOT, 'model', 'best_yolo11n_ip103.pt')
    model = YOLO(model_path)
    image = cv2.imread(image_path)
    results = model(image)  # Chạy mô hình YOLO để dự đoán các đối tượng trong ảnh
    predictions = results[0].boxes

    insects_detected = []
    if predictions:
        for box in predictions:
            x_min, y_min, x_max, y_max = map(int, box.xyxy[0])  # Tọa độ bounding box
            conf = box.conf[0]  # Độ tin cậy
            class_id = int(box.cls)  # Chỉ số lớp

            # Tra cứu tên lớp từ cơ sở dữ liệu Species
            try:
                species = Species.objects.get(insects_id=class_id + 1)
                class_name = species.name
            except Species.DoesNotExist:
                print(f"Warning: class_id {class_id} out of range for class_names")
                class_name = 'Unknown'
            print(
                f"Detected: {class_name} with confidence {conf:.2f}, bounding box: {x_min}, {y_min}, {x_max}, {y_max}")

            # Nếu là côn trùng (class_name chứa từ 'insect'), lưu lại thông tin
            insects_detected.append({
                'class_name': class_name,
                'confidence': conf,
                'bounding_box': (x_min, y_min, x_max, y_max),
                'class_id': class_id
            })

    return insects_detected


# Size
def compare_image_size(image_path_1, image_path_2):
    """
    So sánh kích thước của hai ảnh (chiều rộng và chiều cao).
    Trả về True nếu kích thước giống nhau, False nếu khác nhau.
    """
    try:
        # Mở ảnh đầu tiên và lấy kích thước
        with Image.open(image_path_1) as img1:
            img1_w, img1_h = img1.size

        # Mở ảnh thứ hai và lấy kích thước
        with Image.open(image_path_2) as img2:
            img2_w, img2_h = img2.size

        # So sánh kích thước ảnh
        if img1_w == img2_w and img1_h == img2_h:
            return True
        else:
            return False
    except Exception as e:
        print(f"Error comparing image sizes: {e}")
        return False

# RMSE
def compare_rmse(query_img, db_img_path):
    db_img = cv2.imread(db_img_path)
    if db_img is None:
        return float('inf')  # Nếu ảnh lỗi, bỏ qua

    # Resize ảnh về cùng kích thước để so sánh
    query_resized = cv2.resize(query_img, (128, 128))
    db_resized = cv2.resize(db_img, (128, 128))

    # Tính toán RMSE
    diff = np.subtract(query_resized.astype(np.float32), db_resized.astype(np.float32))
    mse = np.mean(np.square(diff))
    rmse = np.sqrt(mse)

    return rmse

# Vẽ bbox
def visualize_insects(image_path, insects_detected, unique_id=None, save_output=True):
    image = cv2.imread(image_path)
    image_height, image_width = image.shape[:2]

    # Dictionary lưu các dòng bbox theo class_id
    bbox_dict = {}
    if not unique_id:
        unique_id = uuid.uuid4().hex[:8]

    for insect in insects_detected:
        x_min, y_min, x_max, y_max = insect['bounding_box']
        conf = insect['confidence']
        class_name = insect['class_name']
        class_id = insect['class_id']

        # Vẽ bounding box
        label = f"{class_name} {conf:.2f}"
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        cv2.putText(image, label, (x_min + 5, y_min + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Tọa độ YOLO (0-1)
        x_center = ((x_min + x_max) / 2) / image_width
        y_center = ((y_min + y_max) / 2) / image_height
        bbox_width = (x_max - x_min) / image_width
        bbox_height = (y_max - y_min) / image_height

        bbox_line = f'{class_id} {x_center:.6f} {y_center:.6f} {bbox_width:.6f} {bbox_height:.6f}'

        # Thêm dòng bbox vào dict theo class_id
        if class_id not in bbox_dict:
            bbox_dict[class_id] = []
        bbox_dict[class_id].append(bbox_line)

    # Lưu các file bbox theo class_id
    result_paths = {}
    if save_output:
        for class_id, lines in bbox_dict.items():
            bbox_filename = f'bbox_{class_id + 1}_{unique_id}.txt'
            bbox_file_path = os.path.join(settings.MEDIA_ROOT, 'tmp', bbox_filename)
            with open(bbox_file_path, 'w') as f:
                f.write('\n'.join(lines))

        # Lưu ảnh đã vẽ bbox
        output_image_name = f"bbox_output_{unique_id}.jpg"
        output_image_path = os.path.join(settings.MEDIA_ROOT, 'tmp', output_image_name)
        cv2.imwrite(output_image_path, image)
        result_paths['output_image'] = os.path.join(settings.MEDIA_URL, 'tmp', output_image_name)

        return result_paths

    return None


def clear_files_in_folder(folder_path):
    if os.path.exists(folder_path):
        for file_name in os.listdir(folder_path):  # Lấy thông tin các tệp có trong thư mục
            file_path = os.path.join(folder_path, file_name)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Đã xóa file: {file_path}")
            except Exception as e:
                print(f"Lỗi khi xóa file {file_path}: {e}")


# Lưu một file tải lên vào thư mục 'folder_name'
def save_file(uploaded_file, folder_name='tmp', prefix='upload'):
    folder_path = os.path.join(settings.MEDIA_ROOT, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Tạo tên file mới theo định dạng: input_<uuid>.ext
    unique_id = uuid.uuid4().hex[:8]
    new_filename = f"{prefix}_{unique_id}.jpg"

    file_path = os.path.join(folder_path, new_filename)

    with default_storage.open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    return file_path, unique_id


def detect(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('insectImage')
        if not uploaded_file:
            return render(request, 'detect_insect.html', {'error': 'Vui lòng tải lên một hình ảnh.'})

        tmp_folder_path = os.path.join(settings.MEDIA_ROOT, 'tmp')
        # Xóa các file cũ trong thư mục tmp
        clear_files_in_folder(tmp_folder_path)

        # Lưu file tạm thời
        temp_file_path, unique_id = save_file(uploaded_file, folder_name='tmp')

        # Đọc kích thước ảnh nhanh bằng Pillow
        try:
            with Image.open(temp_file_path) as img:
                query_img = cv2.imread(temp_file_path)
        except:
            os.remove(temp_file_path)
            return render(request, 'detect_insect.html', {'error': 'Không thể đọc hình ảnh tải lên.'})

        # Giai đoạn 1: Phát hiện loài côn trùng sơ bộ
        insects_detected = detect_insect_by_yolo(temp_file_path)
        if not insects_detected:
            return render(request, 'detect_insect.html', {'error': 'Không phát hiện được côn trùng trong ảnh.'})

        # Giai đoạn 2: Tìm côn trùng trong cơ sở dữ liệu
        best_match = None
        for insect in insects_detected:
            detected_class_name = insect['class_name']  # Lấy tên lớp của mỗi đối tượng phát hiện
            for insect_img in InsectsImage.objects.filter(
                    insects__name__icontains=detected_class_name):  # Lấy đối tượng img tương ứng thông qua name của / contains khong phân biệt chữ hoa chữ thường
                db_img_path = os.path.join(settings.MEDIA_ROOT, str(insect_img.url))

                # So sánh kích thước ảnh
                if compare_image_size(temp_file_path, db_img_path):
                    # So sánh RMSE
                    rmse_score = compare_rmse(query_img, db_img_path)
                    print('RMSE', rmse_score)
                    if rmse_score < 15:  # Ngưỡng 15 để tăng độ chính xác
                        best_match = insect_img
                        break
            if best_match:  # Thoát vòng lặp nếu đã tìm thấy kết quả
                break

        # Giai đoạn 3: Dư đoán bằng YOLO
        if not best_match:
            # Vẽ bounding box cho tất cả đối tượng phát hiện
            result = visualize_insects(temp_file_path, insects_detected, unique_id=unique_id)  # <- result là dict

            output_image_path = result.get('output_image')  # Đường dẫn ảnh có bbox
            bbox_files = {k: v for k, v in result.items() if k.startswith('class_')}  # Các file bbox

            species_list = {}
            for insect in insects_detected:
                detected_class_name = insect['class_name']
                species = Species.objects.filter(name__icontains=detected_class_name)
                for sp in species:
                    if sp.insects_id not in species_list:
                        species_list[sp.insects_id] = sp
            unique_species_list = list(species_list.values())

            return render(request, 'detect_insect.html', {
                'error': 'Ảnh chưa có trong cơ sở dữ liệu.',
                'output_image_path': output_image_path,
                'bbox_files': bbox_files,  # Gửi danh sách các file bbox ra template
                'species_detect': unique_species_list,
                'upload_image': temp_file_path.replace(settings.MEDIA_ROOT, 'media'),
            })

        upload_img = os.path.normpath(temp_file_path).replace(settings.MEDIA_ROOT, 'media')
        print(upload_img)
        # Nếu tìm thấy ảnh trùng khớp trong cơ sở dữ liệu
        species = best_match.insects  # Truy xuất Species từ InsectsImage
        if species and species.slug:
            return render(request, 'detect_insect.html', {
                'species_img': species,
                'upload_image': temp_file_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL),
                'matched_image_path': db_img_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
            })

    return render(request, 'detect_insect.html')


# ============================================Cào ảnh====================================================
def generate_unique_id(url, insect_id):
    hash_value = hashlib.sha256(url.encode()).hexdigest()[:10]
    return f"{insect_id}_{hash_value[:10]}"


# Hàm cào dữ liệu từ GBIF và lấy hình ảnh
# def get_images_from_gbif(species_name, limit, insect_id):
#     # Tìm kiếm dữ liệu quan sát của loài
#     data = occurrences.search(scientificName=species_name, limit=limit)
#     print('spectes_name: ', species_name)
#     print("Dữ liệu trả về:", data)  # In ra dữ liệu để kiểm tra
#     images = []
#
#     # Lấy danh sách hình ảnh từ kết quả
#     for record in data.get("results", []):
#         if "media" in record and record["media"]:
#             for media in record["media"]:
#                 if media.get("type") == "StillImage":
#                     img_url = media.get("identifier")
#                     img_id = generate_unique_id(img_url, insect_id)  # Tạo ID mới từ URL
#
#                     # Kiểm tra ảnh đã có trong CSDL chưa
#                     if InsectsCrawler.objects.filter(img_id=img_id).exists():
#                         continue  # Bỏ qua ảnh đã tồn tại
#
#                     images.append({
#                         "img_id": img_id,  # ID mới
#                         "url": img_url,
#                         "created_date": media.get("created", "unknown"),  # Ngày đăng bức ảnh
#                     })
#     return images

def get_images_from_gbif(species_name, limit, insect_id):
    images = []
    offset = 0
    batch_size = max(limit, 300)  # GBIF thường giới hạn 100-300 bản ghi mỗi lần
    max_attempts = 5  # Số lần thử tối đa để tránh lặp vô hạn

    while len(images) < limit and max_attempts > 0:
        try:
            data = occurrences.search(scientificName=species_name, limit=batch_size, offset=offset)
            if not data.get("results"):
                break  # Không còn dữ liệu
        except Exception as e:
            print(f"Error fetching GBIF data: {e}")
            break

        img_ids_to_check = []
        temp_images = []

        for record in data.get("results", []):
            if "media" in record and record["media"]:
                for media in record["media"]:
                    if media.get("type") == "StillImage":
                        img_url = media.get("identifier")
                        if not img_url:
                            continue
                        img_id = generate_unique_id(img_url, insect_id)
                        img_ids_to_check.append(img_id)
                        temp_images.append({
                            "img_id": img_id,
                            "url": img_url,
                            "created_date": media.get("created", None),
                        })

        # Kiểm tra trùng lặp
        existing_ids = set(InsectsCrawler.objects.filter(img_id__in=img_ids_to_check).values_list("img_id", flat=True))
        new_images = [img for img in temp_images if img["img_id"] not in existing_ids]
        images.extend(new_images[:limit - len(images)])  # Chỉ lấy đủ số lượng cần

        offset += batch_size
        max_attempts -= 1
        if len(data.get("results", [])) < batch_size:
            break  # Không còn bản ghi để lấy

        print(f"Collected {len(images)} images for species {species_name}")
    return images

# Xử lý form cào ảnh
def crawl_images(request):
    """
       Hàm xử lý cho việc cào dữ liệu hình ảnh từ giao diện người dùng.
    """
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        insect_id = request.POST.get('insectSelect')
        quantity = int(request.POST.get('quantity', 1))

        # Lấy thông tin loài dựa trên ID
        species = get_object_or_404(Species, insects_id=insect_id)
        species_name = species.ename  # Tên khoa học

        # Cào hình ảnh từ GBIF
        images = get_images_from_gbif(species_name, quantity, insect_id)

        # Nếu không có hình ảnh, trả về thông báo lỗi
        if not images:
            return JsonResponse({
                "success": False,
                "error": f"Không tìm thấy hình ảnh nào cho loài '{species_name}'."
            })

        # Trả về danh sách hình ảnh đã cào
        return JsonResponse({
            "success": True,
            "images": images
        })
    # Xử lý yêu cầu GET (hiển thị giao diện)
    species_list = Species.objects.all()
    return render(request, 'crawler.html', {'species_list': species_list})

def download_image_requests(img_url, local_path, timeout=5, max_size_mb=5):
    """Tải ảnh từ URL về local path, có timeout và giới hạn dung lượng"""
    try:
        response = requests.get(img_url, stream=True, timeout=timeout)
        response.raise_for_status()
        downloaded = 0
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                downloaded += len(chunk)
                if downloaded > max_size_mb * 1024 * 1024:
                    raise Exception("Ảnh vượt quá dung lượng tối đa cho phép.")
                f.write(chunk)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Lỗi khi tải ảnh: {e}")


@csrf_exempt
def upload_image(request):
    if request.method == 'POST':
        # Lấy dữ liệu từ POST
        img_url = request.POST.get('img_url')
        species_id = request.POST.get('species_id')
        id_crawler = request.POST.get('id_crawler')

        # Kiểm tra đầu vào
        if not img_url:
            return JsonResponse({'error': 'Thiếu đường dẫn ảnh'}, status=400)
        if not species_id:
            return JsonResponse({'error': 'Thiếu species_id'}, status=400)

        tmp_folder_path = os.path.join(settings.MEDIA_ROOT, 'tmp')
        clear_files_in_folder(tmp_folder_path)

        try:
            # Tạo tên file duy nhất
            unique_id = uuid.uuid4().hex[:8]
            filename = f"upload_{unique_id}.jpg"
            local_path = os.path.join(tmp_folder_path, filename)

            # Tải ảnh
            download_image_requests(img_url, local_path)
            print('local_path', local_path)

            # Phát hiện bounding boxes
            insects_detected = detect_insect_by_yolo(local_path)
            result = visualize_insects(local_path, insects_detected, unique_id=unique_id, save_output=True)

            # Đọc bbox_data
            bbox_file_path = os.path.join(tmp_folder_path, f'bbox_{species_id}_{unique_id}.txt')
            bbox_data = []
            if os.path.exists(bbox_file_path):
                with open(bbox_file_path, 'r') as file:
                    bbox_data = [line.strip() for line in file if line.strip()]
            else:
                print(f"File bbox không tồn tại: {bbox_file_path}")

            query_img = cv2.imread(local_path)
            is_duplicate = False
            duplicate_message = None
            for existing in RequestImage.objects.filter(insects_id=species_id):
                existing_url = existing.url
                existing_path = os.path.join(settings.MEDIA_ROOT, existing_url.lstrip('/'))
                print('existing_path: ', existing_path)
                if os.path.exists(existing_path):
                    print(f"Ảnh tồn tại, so sánh kích thước: {existing_path}")
                    if compare_image_size(local_path, existing_path):
                        rmse = compare_rmse(query_img, existing_path)
                        print(f"So sánh với {existing.url}, RMSE: {rmse}")
                        if rmse < 15:
                            is_duplicate = True
                            break

            for existing in InsectsImage.objects.filter(insects_id=species_id):
                existing_url = existing.url
                existing_path = os.path.join(settings.MEDIA_ROOT, existing_url.lstrip('/'))
                print('existing_path: ', existing_path)
                if os.path.exists(existing_path):
                    print(f"Ảnh tồn tại, so sánh kích thước: {existing_path}")
                    if compare_image_size(local_path, existing_path):
                        rmse = compare_rmse(query_img, existing_path)
                        print(f"So sánh với {existing.url}, RMSE: {rmse}")
                        if rmse < 15:
                            is_duplicate = True
                            break

            if is_duplicate:
                print('Ảnh đã tồn tại')
                return JsonResponse({'success': False, 'message': 'Ảnh trùng với ảnh đã có trong CSDL.'})

            response_data = {
                'success': True,
                'img_download': f'{settings.MEDIA_URL}tmp/{filename}',
                'bbox_image_url': result['output_image'],
                'bbox_data': bbox_data,
                'local_path': local_path,
                'id_crawler': id_crawler,
                'species_id': species_id
            }
            if is_duplicate:
                response_data['warning'] = duplicate_message

            return JsonResponse(response_data)

        except Species.DoesNotExist:
            return JsonResponse({'error': 'Không tìm thấy loài côn trùng'}, status=400)
        except Exception as e:
            print(f"Lỗi trong detect_insect_view: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Chỉ hỗ trợ phương thức POST'}, status=405)


@csrf_exempt
def clear_temp_files(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        local_path = data.get('local_path', '')
        if local_path and os.path.exists(local_path):
            unique_id = os.path.basename(local_path).replace("upload_", "").replace(".jpg", "")
            bbox_path = os.path.join(settings.MEDIA_ROOT, 'tmp', f'bbox_{data.get("species_id", "")}_{unique_id}.txt')
            if os.path.exists(local_path):
                os.remove(local_path)
            if os.path.exists(bbox_path):
                os.remove(bbox_path)
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)


# ==============================================================================

# ==========================ĐÓNG GÓP HÌNH ẢNH MỚI==============================
def extract_bbox(species_id, image_path):
    filename = os.path.basename(image_path)
    if filename.startswith("upload_") and filename.endswith(".jpg"):
        unique_id = filename.replace("upload_", "").replace(".jpg", "")
        bbox_filename = f"bbox_{species_id}_{unique_id}.txt"
        bbox_path = os.path.join(settings.MEDIA_ROOT, 'tmp', bbox_filename)
        if os.path.exists(bbox_path):
            with open(bbox_path, 'r') as file:
                lines = file.readlines()
                if lines:
                    data = lines[0].strip().split()  # Lấy dòng đầu tiên
                    if len(data) == 5:
                        return {
                            'filename': bbox_filename,
                            'class_id': int(data[0]),
                            'x': float(data[1]),
                            'y': float(data[2]),
                            'width': float(data[3]),
                            'height': float(data[4]),
                        }
    return None


def save_bbox(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_bbox_lines = data.get('bbox_lines', [])
            species_id = data.get('species_id', '')
            description = data.get('description', '')
            local_path = data.get('local_path', '')
            id_crawler = data.get('id_crawler', '')

            if not local_path or not os.path.exists(local_path):
                return JsonResponse({'status': 'error', 'error': 'Đường dẫn ảnh tạm không hợp lệ'}, status=400)
            if not id_crawler:
                return JsonResponse({'status': 'error', 'error': 'Thiếu id_crawler'}, status=400)
            if not species_id:
                return JsonResponse({'status': 'error', 'error': 'Thiếu species_id'}, status=400)

            # Lưu bbox vào file tmp
            unique_id = os.path.basename(local_path).replace("upload_", "").replace(".jpg", "")
            bbox_tmp_path = os.path.join(settings.MEDIA_ROOT, 'tmp', f'bbox_{species_id}_{unique_id}.txt')
            if new_bbox_lines:
                with open(bbox_tmp_path, 'w') as file:
                    for line in new_bbox_lines:
                        file.write(line + '\n')
            else:
                if os.path.exists(bbox_tmp_path):
                    os.remove(bbox_tmp_path)

            # Gọi request_image để tạo đóng góp
            result = request_image(request, image_path=local_path, species_id=species_id, id_crawler=id_crawler, description=description)
            # Kiểm tra phản hồi từ request_image
            if isinstance(result, JsonResponse):
                result_data = json.loads(result.content)
                if result_data.get('status') == 'success':
                    return JsonResponse(
                        {'status': 'success', 'message': result_data.get('message', 'Đóng góp thành công')})
                else:
                    error_msg = result_data.get('error', 'Lỗi không xác định từ request_image')
                    return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
            else:
                error_msg = "Phản hồi không hợp lệ từ request_image"
                return JsonResponse({'status': 'error', 'error': error_msg}, status=500)

        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)

def move_image_to_images_folder(image_path, species_id):
    filename = os.path.basename(image_path)  # ví dụ: input_abc12345.jpg
    unique_id = None
    if filename.startswith("upload_") and filename.endswith(".jpg"):
        unique_id = filename.replace("upload_", "").replace(".jpg", "")
    else:
        # Nếu không đúng định dạng thì không thể tìm bbox tương ứng
        unique_id = ""

    new_file_name = f"IP{int(species_id):03d}_{timezone.now().strftime('%d%m%y%H%M%S')}"
    new_path = os.path.join(settings.MEDIA_ROOT, 'add_desc_image', f"{new_file_name}.jpg")

    # Đường dẫn file bbox với unique_id
    bbox_file_name = f"bbox_{species_id}_{unique_id}.txt"
    bbox_file_path = os.path.join(settings.MEDIA_ROOT, 'tmp', bbox_file_name)
    new_bbox_path = os.path.join(settings.MEDIA_ROOT, 'add_desc_image', f"{new_file_name}.txt")

    # Di chuyển file ảnh và bbox
    if not os.path.exists(new_path):
        shutil.move(image_path, new_path)
    if os.path.exists(bbox_file_path):
        shutil.move(bbox_file_path, new_bbox_path)

    return f"add_desc_image/{new_file_name}.jpg"

def request_image(request, image_path=None, species_id=None, id_crawler=None, description=None):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    is_from_save_bbox = image_path is not None

    # Nếu gọi từ POST
    if request.method == 'POST' and image_path is None:
        image_path = request.POST.get('image_path')
        species_id = request.POST.get('species_id')
        id_crawler = request.POST.get('id_crawler')
        description = request.POST.get('description', '')

    if not image_path or not species_id:
        error_msg = "Thiếu thông tin hình ảnh hoặc loài!"
        if is_ajax or is_from_save_bbox:
            return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('detect_insect')

    try:
        species_instance = Species.objects.get(insects_id=species_id)
    except Species.DoesNotExist:
        error_msg = "Không tìm thấy loài với ID đã cung cấp!"
        if is_ajax or is_from_save_bbox:
            return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('detect_insect')

    if request.user.is_authenticated:
        bbox_info = extract_bbox(int(species_id), image_path)

        if bbox_info:
            imgs = RequestImage.objects.filter(insects_id=species_id, status__in=['pending', 'verified'])
            for img in imgs:
                db_img = os.path.join(settings.MEDIA_ROOT, img.url.lstrip('/'))
                if compare_image_size(image_path, db_img):
                    if compare_rmse(cv2.imread(image_path), db_img) < 15:
                        error_msg = "Ảnh đã được đóng góp"
                        if is_ajax or is_from_save_bbox:
                            return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
                        messages.error(request, error_msg)
                        return redirect('detect_insect')

            try:
                new_image_path = move_image_to_images_folder(image_path, int(species_id))
                request_item = RequestImage.objects.create(
                    insects_id=species_instance,
                    user_id=request.user,
                    url=new_image_path,
                    desc=description or '',
                    status='pending',
                    verification_count=0  # Bắt đầu với 1 vì đã xác nhận
                )

                # Tạo InsectsCrawler
                InsectsCrawler.objects.create(
                    insects_id=species_instance,
                    user_id=request.user,
                    img_url=new_image_path,
                    img_id=id_crawler or uuid.uuid4().hex[:8],
                    crawl_time=timezone.now(),
                    status='success'
                )

                # Gửi email đến chuyên gia
                try:
                    cv_group = Group.objects.get(name="CVs")
                    experts = cv_group.user_set.all()
                    expert_emails = [expert.email for expert in experts if expert.email]
                    if expert_emails:
                        species_info = f"{species_instance.name} (ID: {species_id})"
                        request_time = request_item.request_time
                        subject = "Thông báo: Có đóng góp hình ảnh mới"
                        message = (
                            f"Xin chào chuyên gia,\n\n"
                            f"- Người dùng {request.user.username} vừa đóng góp một ảnh mới.\n"
                            f"- Tên loài: {species_info}.\n"
                            f"- Mô tả: {description or 'Không có mô tả'}\n"
                            f"- Thời gian: {timezone.localtime(request_time).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                            f"Trân trọng,\nHệ thống quản lý côn trùng"
                        )
                        from_email = "no-reply@yourdomain.com"
                        send_mail(subject, message, from_email, expert_emails, fail_silently=True)
                    else:
                        print("Không có chuyên gia nào trong nhóm 'CVs' có email!")
                except Group.DoesNotExist:
                    print("Nhóm 'CVs' không tồn tại trong cơ sở dữ liệu!")

                success_msg = "Đã đóng góp hình ảnh thành công!"
                if is_ajax or is_from_save_bbox:
                    return JsonResponse({'status': 'success', 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('detect_insect')
            except Exception as e:
                error_msg = f"Lỗi khi lưu hình ảnh: {str(e)}"
                if is_ajax or is_from_save_bbox:
                    return JsonResponse({'status': 'error', 'error': error_msg}, status=500)
                messages.error(request, error_msg)
                return redirect('detect_insect')
        else:
            error_msg = "Không tìm thấy file bbox phù hợp!"
            if is_ajax or is_from_save_bbox:
                return JsonResponse({'status': 'error', 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('detect_insect')
    else:
        error_msg = "Vui lòng đăng nhập để đóng góp hình ảnh!"
        if is_ajax or is_from_save_bbox:
            return JsonResponse({'status': 'error', 'error': error_msg}, status=401)
        messages.error(request, error_msg)
        return redirect('detect_insect')

    return redirect('contrib_image')

# ==================================================================================================
# =======================THÔNG TIN ĐÓNG GÓP USER=========================================================
def contrib_image(request):
    """ Xem trạng thái đóng góp hình ảnh của người dùng """
    if request.user.is_authenticated:
        contributed_images = RequestImage.objects.filter(user_id=request.user.id).order_by('-request_time')
        # Thêm đường dẫn đầy đủ cho ảnh
        for image in contributed_images:
            image.full_url = request.build_absolute_uri(settings.MEDIA_URL + str(image.url))
    else:
        contributed_images = []

    if request.method == 'POST':
        uploaded_file = request.FILES.get('insectImage')
        if not uploaded_file:
            return render(request, 'contrib_image.html', {'error': 'Vui lòng tải lên một hình ảnh.'})

        tmp_folder_path = os.path.join(settings.MEDIA_ROOT, 'tmp')
        # Xóa các file cũ trong thư mục tmp
        clear_files_in_folder(tmp_folder_path)

        # Lưu file tạm thời
        temp_file_path, unique_id = save_file(uploaded_file, folder_name='tmp')

        # Đọc kích thước ảnh nhanh bằng Pillow
        try:
            with Image.open(temp_file_path) as img:
                query_img = cv2.imread(temp_file_path)
        except:
            os.remove(temp_file_path)
            return render(request, 'contrib_image.html', {'error': 'Không thể đọc hình ảnh tải lên.'})

        # Giai đoạn 1: Phát hiện loài côn trùng sơ bộ
        insects_detected = detect_insect_by_yolo(temp_file_path)
        if not insects_detected:
            return render(request, 'contrib_image.html', {'error': 'Không phát hiện được côn trùng trong ảnh.'})

        # Giai đoạn 2: Tìm côn trùng trong cơ sở dữ liệu
        best_match = None
        for insect in insects_detected:
            detected_class_name = insect['class_name']  # Lấy tên lớp của mỗi đối tượng phát hiện
            for insect_img in InsectsImage.objects.filter(
                    insects__name__icontains=detected_class_name):  # Lấy đối tượng img tương ứng thông qua name của / contains khong phân biệt chữ hoa chữ thường
                db_img_path = os.path.join(settings.MEDIA_ROOT, str(insect_img.url))

                # So sánh kích thước ảnh
                if compare_image_size(temp_file_path, db_img_path):
                    # So sánh RMSE
                    rmse_score = compare_rmse(query_img, db_img_path)
                    print('RMSE', rmse_score)
                    if rmse_score < 15:  # Ngưỡng 15 để tăng độ chính xác
                        best_match = insect_img
                        break
            if best_match:  # Thoát vòng lặp nếu đã tìm thấy kết quả
                break

        # Giai đoạn 3: Dư đoán bằng YOLO
        if not best_match:
            # Vẽ bounding box cho tất cả đối tượng phát hiện
            result = visualize_insects(temp_file_path, insects_detected, unique_id=unique_id)  # <- result là dict

            output_image_path = result.get('output_image')  # Đường dẫn ảnh có bbox
            bbox_files = {k: v for k, v in result.items() if k.startswith('class_')}  # Các file bbox

            species_list = {}
            for insect in insects_detected:
                detected_class_name = insect['class_name']
                species = Species.objects.filter(name__icontains=detected_class_name)
                for sp in species:
                    if sp.insects_id not in species_list:
                        species_list[sp.insects_id] = sp
            unique_species_list = list(species_list.values())

            return render(request, 'contrib_image.html', {
                'error': 'Ảnh chưa có trong cơ sở dữ liệu.',
                'output_image_path': output_image_path,
                'bbox_files': bbox_files,  # Gửi danh sách các file bbox ra template
                'species_detect': unique_species_list,
                'upload_image': temp_file_path.replace(settings.MEDIA_ROOT, 'media'),
            })

        upload_img = os.path.normpath(temp_file_path).replace(settings.MEDIA_ROOT, 'media')
        print(upload_img)
        # Nếu tìm thấy ảnh trùng khớp trong cơ sở dữ liệu
        species = best_match.insects  # Truy xuất Species từ InsectsImage
        if species and species.slug:
            return render(request, 'contrib_image.html', {
                'error': 'Ảnh đã tồn tại trong cơ sở dữ liệu vui lòng chọn ảnh khác.',
                'species_img': species,
                'upload_image': temp_file_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL),
                'matched_image_path': db_img_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
            })

    return render(request, 'contrib_image.html', {'contributed_images': contributed_images, })

# =========================================================================================================
# ==========================THÔNG TIN ĐÓNG GÓP CV==========================================================
def cv_verify_new_image(request):
    """ Xem danh sách ảnh đóng góp của người dùng """
    if request.user.is_authenticated:
        requests = RequestImage.objects.select_related('user_id', 'insects_id').filter(status='pending').order_by(
            '-request_time')

        for index, request_item in enumerate(requests, start=1):
            request_item.index = index  # Thêm số thứ tự

    else:
        requests = []

    return render(request, 'cv_verify_new_image.html', {'requests': requests, 'MEDIA_URL': settings.MEDIA_URL})

@login_required # mới thêm
def verify_new_image_request(request, request_img_id):
    """ Chấp nhận hoặc từ chối yêu cầu xác minh mô tả """
    result = None
    request_item = get_object_or_404(RequestImage, pk=request_img_id)
    specie = request_item.insects_id
    species_list = Species.objects.all()
    
    # SỬA: Chỉ lấy đường dẫn tương đối từ database
    img_url = str(request_item.url)
    
    # KIỂM TRA: In ra để debug
    print(f"DEBUG: Image URL from database: {img_url}")
    print(f"DEBUG: MEDIA_URL: {settings.MEDIA_URL}")
    
    # Tạo đường dẫn đầy đủ để hiển thị trong template
    full_img_url = request.build_absolute_uri(settings.MEDIA_URL + img_url)
    print(f"DEBUG: Full image URL: {full_img_url}")
    
    img_path = os.path.join(settings.MEDIA_ROOT, img_url)
    
    # Kiểm tra ảnh tồn tại trong MEDIA_ROOT
    if not os.path.exists(img_path):
        print(f"DEBUG: Image path does not exist: {img_path}")
        messages.error(request, "Ảnh không tồn tại trong hệ thống!")
        return redirect('cv_verify_new_image')
    
    # Đọc dữ liệu bbox từ file txt
    bbox_data = []
    try:
        # Tìm file txt tương ứng
        txt_path = os.path.splitext(img_path)[0] + '.txt'
        print(f"DEBUG: Looking for bbox file at: {txt_path}")
        
        if os.path.exists(txt_path):
            with open(txt_path, 'r') as f:
                bbox_data = [line.strip() for line in f if line.strip()]
            print(f"DEBUG: Found {len(bbox_data)} bbox lines")
        else:
            print(f"DEBUG: Bbox file not found, creating default")
            # Nếu không có file txt, tạo bbox mặc định cho toàn bộ ảnh
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    # Tạo bbox mặc định cho toàn bộ ảnh với class_id = species_id - 1
                    class_id = max(0, int(specie.insects_id) - 1)
                    x_center = 0.5
                    y_center = 0.5
                    bbox_width = 1.0
                    bbox_height = 1.0
                    bbox_data = [f"{class_id} {x_center} {y_center} {bbox_width} {bbox_height}"]
                    print(f"DEBUG: Created default bbox: {bbox_data}")
            except Exception as e:
                print(f"Error reading image: {e}")
                bbox_data = []
    except Exception as e:
        print(f"Error reading bbox file: {e}")
        bbox_data = []
    
    has_verified = VerificationLog.objects.filter(
        user=request.user,
        request_type='image',
        object_id=request_img_id
    ).exists()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept":
            if request_item.verification_count >= 3:
                messages.warning(request, "Yêu cầu này đã đủ số chuyên gia chấp nhận!")
            else:
                description = request.POST.get("description", "").strip()
                insects_id = request.POST.get("species_id")

                try:
                    species_infor = Species.objects.get(insects_id=insects_id)
                except Species.DoesNotExist:
                    messages.error(request, "Loài côn trùng không tồn tại!")
                    return redirect('cv_verify_new_image')

                request_item.verification_count = (request_item.verification_count or 0) + 1
                request_item.desc = description

                if request_item.verification_count >= 3:
                    request_item.status = "verified"
                    messages.success(request, "Mô tả đã được xác thực thành công!")
                    result = "verified"
                else:
                    messages.info(request,
                                  f"Hiện có {request_item.verification_count}/3 chuyên gia chấp nhận. Cần thêm {3 - request_item.verification_count} chuyên gia nữa!")
                    result = "pending"
                request_item.save()

        elif action == "reject":
            request_item.status = "rejected"
            request_item.save()
            result = "rejected"
            messages.error(request, "Mô tả đã bị từ chối!")

        VerificationLog.objects.get_or_create(
            user=request.user,
            request_type='image',
            object_id=request_img_id
        )

        return redirect('cv_verify_new_image')

    context = {
        'request_item': request_item,
        'species_list': species_list,
        'specie': specie,
        # SỬA QUAN TRỌNG: Chỉ truyền đường dẫn tương đối, không phải đường dẫn đầy đủ
        'img_url': img_url,  # Đây là đường dẫn tương đối từ database
        'bbox_data': json.dumps(bbox_data) if bbox_data else '[]',
        'has_verified': has_verified,
        'verify_result': result or '',
        'MEDIA_URL': settings.MEDIA_URL
    }
    return render(request, 'verify_new_image_request.html', context)
@csrf_exempt
@login_required
def auto_detect_image(request, request_img_id):
    """Endpoint cho chức năng nhận dạng tự động bằng YOLO"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)
    
    try:
        # Lấy RequestImage
        request_item = get_object_or_404(RequestImage, pk=request_img_id)
        img_path = os.path.join(settings.MEDIA_ROOT, str(request_item.url))
        
        if not os.path.exists(img_path):
            return JsonResponse({'status': 'error', 'error': 'Image file not found'}, status=404)
        
        # Parse JSON data
        data = json.loads(request.body)
        species_id = data.get('species_id', '')
        
        if not species_id:
            return JsonResponse({'status': 'error', 'error': 'Missing species_id'}, status=400)
        
        # Gọi hàm detect_insect_by_yolo (đã có trong views.py)
        insects_detected = detect_insect_by_yolo(img_path)
        
        if not insects_detected:
            return JsonResponse({
                'status': 'success',
                'bboxes': [],
                'message': 'No insects detected'
            })
        
        # Convert to YOLO format
        bboxes_data = []
        for insect in insects_detected:
            x_min, y_min, x_max, y_max = insect['bounding_box']
            conf = insect['confidence']
            
            # Mở ảnh để lấy kích thước
            with Image.open(img_path) as img:
                img_width, img_height = img.size
            
            # Chuyển sang YOLO format
            x_center = ((x_min + x_max) / 2) / img_width
            y_center = ((y_min + y_max) / 2) / img_height
            bbox_width = (x_max - x_min) / img_width
            bbox_height = (y_max - y_min) / img_height
            
            bboxes_data.append({
                'classId': int(species_id) - 1,  # YOLO class IDs start from 0
                'x': x_center,
                'y': y_center,
                'width': bbox_width,
                'height': bbox_height,
                'confidence': float(conf)
            })
        
        return JsonResponse({
            'status': 'success',
            'bboxes': bboxes_data,
            'message': f'Detected {len(bboxes_data)} bounding boxes'
        })
        
    except Exception as e:
        print(f"Error in auto_detect_image: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

@csrf_exempt
def save_bbox_verify(request, request_img_id):
    """Lưu bounding boxes khi xác minh ảnh mới"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)

    try:
        # Parse JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'error': 'Invalid JSON data'}, status=400)
        
        new_bbox_lines = data.get('bbox_lines', [])
        species_id = data.get('species_id', '')
        description = data.get('description', '')

        if not species_id:
            return JsonResponse({'status': 'error', 'error': 'Thiếu species_id'}, status=400)

        # Lấy RequestImage
        try:
            request_item = RequestImage.objects.get(request_img_id=request_img_id)
        except RequestImage.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': 'Không tìm thấy yêu cầu hình ảnh'}, status=404)

        # Cập nhật species_id và description
        try:
            species = Species.objects.get(insects_id=species_id)
            request_item.insects_id = species
        except Species.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': 'Không tìm thấy loài côn trùng'}, status=400)

        request_item.desc = description
        request_item.verification_count += 1
        
        if request_item.verification_count >= 3:
            request_item.status = 'verified'
            message = "Hình ảnh đã được xét duyệt thành công!"
        else:
            message = f"Hiện có {request_item.verification_count}/3 chuyên gia chấp nhận. Cần thêm {3 - request_item.verification_count} chuyên gia nữa!"
        
        request_item.save()

        # Lưu bbox vào file .txt - QUAN TRỌNG: Lưu cùng thư mục với ảnh
        img_path = os.path.join(settings.MEDIA_ROOT, str(request_item.url))
        txt_filename = os.path.splitext(os.path.basename(img_path))[0] + '.txt'
        txt_dir = os.path.dirname(img_path)
        txt_path = os.path.join(txt_dir, txt_filename)
        
        if new_bbox_lines:
            with open(txt_path, 'w') as file:
                for line in new_bbox_lines:
                    file.write(line + '\n')
            print(f"Saved {len(new_bbox_lines)} bounding boxes to {txt_path}")
        else:
            if os.path.exists(txt_path):
                os.remove(txt_path)

        return JsonResponse({
            'status': 'success', 
            'message': 'Lưu bbox và xét duyệt thành công',
            'verification_count': request_item.verification_count,
            'status_text': request_item.status
        })

    except Exception as e:
        print(f"Error in save_bbox_verify: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
# =========================================================================================================
# =========================THÔNG TIN ĐÓNG GÓP ADMIN========================================================
def admin_verify_new_image(request):
    """ Xem danh sách ảnh đóng góp của người dùng """
    if request.user.is_authenticated:
        requests = RequestImage.objects.filter(status='verified').order_by('-request_time')

        for index, request_item in enumerate(requests, start=1):
            request_item.index = index  # Thêm số thứ tự

    else:
        requests = []

    return render(request, 'admin_verify_new_image.html', {'requests': requests, 'MEDIA_URL': settings.MEDIA_URL})

def readfile_boundingbox(file_path):
    """
    Đọc file bounding box từ đường dẫn file.
    """
    try:
        with open(file_path, 'r') as file_obj:
            data = file_obj.read()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        # Trả về bounding box mặc định nếu file không tồn tại
        return {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100}
    
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    
    xs, ys = [], []
    for line in data.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            try:
                x, y = float(parts[0]), float(parts[1])
                xs.append(x)
                ys.append(y)
            except ValueError:
                continue  # Bỏ qua dòng không hợp lệ
    
    if not xs:
        # Nếu không có dữ liệu hợp lệ, trả về bounding box mặc định
        return {"min_x": 0, "min_y": 0, "max_x": 100, "max_y": 100}
    
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys)
    }
def accept_new_image(request, request_img_id):
    """ Chấp nhận hoặc từ chối yêu cầu xác minh mô tả """
    request_item = get_object_or_404(RequestImage, pk=request_img_id)
    species = request_item.insects_id
    
    # Lấy đường dẫn ảnh
    img_url = str(request_item.url)  # Đường dẫn tương đối
    img_path = os.path.join(settings.MEDIA_ROOT, img_url)
    
    # KIỂM TRA tồn tại
    if not os.path.exists(img_path):
        messages.error(request, "Ảnh không tồn tại trong hệ thống!")
        return redirect('admin_verify_new_image')
    
    # TÌM FILE TXT CHỨA BOUNDING BOX - FIXED PATH
    txt_filename = os.path.splitext(os.path.basename(img_path))[0] + '.txt'
    txt_dir = os.path.dirname(img_path)
    txt_path = os.path.join(txt_dir, txt_filename)
    
    # ĐỌC DỮ LIỆU BBOX TỪ FILE TXT - GIỮ NGUYÊN KHÔNG XỬ LÝ
    bbox_data = []
    if os.path.exists(txt_path):
        with open(txt_path, 'r') as f:
            bbox_data = [line.strip() for line in f if line.strip()]
        print(f"DEBUG: Found bbox file at: {txt_path}")
        print(f"DEBUG: Bbox data: {bbox_data}")
    else:
        print(f"DEBUG: Bbox file not found at: {txt_path}")
        # Nếu không có file txt, tạo bbox mặc định
        try:
            with Image.open(img_path) as img:
                width, height = img.size
                # Sử dụng insects_id của request_item để tạo class_id
                class_id = max(0, int(species.insects_id) - 1)
                bbox_data = [f"{class_id} 0.5 0.5 1.0 1.0"]
        except Exception as e:
            print(f"Error creating default bbox: {e}")
            bbox_data = ["0 0.5 0.5 1.0 1.0"]
    
    # QUAN TRỌNG: Lấy tên loài từ request_item (giống chuyên gia)
    # Khi chuyên gia xác nhận, họ đã chọn loài cho ảnh này
    # Chúng ta hiển thị TÊN KHOẢ HỌC (ename) của loài đó
    species_display_name = species.ename  # Tên khoa học
    
    # CHUYỂN ĐỔI SANG FORMAT ĐƠN GIẢN - GIỐNG NHƯ TRONG TRANG CHUYÊN GIA
    processed_bboxes = []
    for line in bbox_data:
        parts = line.strip().split()
        if len(parts) >= 5:
            try:
                class_id = float(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
                
                # QUAN TRỌNG: Giữ nguyên class_id từ file txt
                # Nhưng hiển thị tên loài từ request_item (giống chuyên gia)
                processed_bboxes.append({
                    'classId': int(class_id),
                    'x': x_center,
                    'y': y_center,
                    'width': width,
                    'height': height,
                    'species_name': species_display_name,  # Tên loài để hiển thị
                })
            except ValueError as e:
                print(f"Error parsing bbox line '{line}': {e}")
                continue
    
    # CHUYỂN ĐỔI THÀNH JSON
    bbox_json = json.dumps(processed_bboxes)
    print(f"DEBUG: Processed bboxes: {processed_bboxes}")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept":
            try:
                # Tạo tên file mới
                new_filename = generate_image_name(species.pk) + ".jpg"
                new_folder = os.path.join(settings.MEDIA_ROOT, "images")
                os.makedirs(new_folder, exist_ok=True)
                new_img_path = os.path.join(new_folder, new_filename)

                # Tạo instance Species
                species_instance = Species.objects.get(insects_id=species.insects_id)
                
                # Tạo ảnh mới trong database
                new_image = InsectsImage.objects.create(
                    img_id=new_filename[:-4],
                    insects=species_instance,
                    url=f"images/{new_filename}",
                    desc=request_item.desc
                )

                # Sao chép ảnh
                shutil.copy2(img_path, new_img_path)

                # Xử lý file bbox
                bbox_file_new = os.path.join(new_folder, os.path.splitext(new_filename)[0] + '.txt')
                
                if os.path.exists(txt_path):
                    shutil.copy2(txt_path, bbox_file_new)
                    
                    # Đọc và lưu bbox vào database
                    with open(bbox_file_new, "r") as f:
                        for line in f.readlines():
                            parts = line.strip().split()
                            if len(parts) == 5:
                                try:
                                    class_id, x, y, w, h = map(float, parts)
                                    InsectsBbox.objects.create(
                                        img=new_image,
                                        x=x,
                                        y=y,
                                        width=w,
                                        height=h
                                    )
                                except ValueError:
                                    continue

                # Cập nhật trạng thái
                request_item.status = "accepted"
                request_item.save()

                messages.success(request, "Hình ảnh đã được chấp nhận và lưu vào hệ thống!")
                
            except Exception as e:
                print(f"Error accepting image: {str(e)}")
                messages.error(request, f"Lỗi khi lưu hình ảnh: {str(e)}")

        elif action == "reject":
            request_item.status = "rejected"
            request_item.save()
            messages.error(request, "Hình ảnh đã bị từ chối!")

        return redirect('admin_verify_new_image')

    context = {
        'request_item': request_item,
        'species': species,
        'bbox_img_url': settings.MEDIA_URL + img_url,  # Đường dẫn đầy đủ
        'bbox_json': bbox_json,  # JSON không dùng mark_safe
        'MEDIA_URL': settings.MEDIA_URL
    }
    return render(request, 'accept_new_image.html', context)

def generate_image_name(species_id):
    """ Tạo tên file ảnh mới theo định dạng IP(ID loài)(Mã số) """
    latest_image = InsectsImage.objects.filter(insects_id=species_id).order_by('-img_id').first()

    if latest_image:
        latest_id = latest_image.img_id[-6:]  # Lấy 6 số cuối
        next_id = int(latest_id) + 1
    else:
        next_id = 1  # Nếu chưa có ảnh nào

    if int(species_id) > 30:
        return f"IP{int(species_id):03d}{next_id:06d}"
    return f"IP{int(species_id) - 1:03d}{next_id:06d}"
# ==================================================================================================
# Thêm function này vào views.py, có thể đặt trước hàm check_missing_images()
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .predict import predict_image
import os
from django.core.files.storage import default_storage

@csrf_exempt
def predict_species_from_image(request):
    """API nhận diện loài côn trùng từ ảnh"""
    if request.method == 'POST':
        try:
            if 'image' not in request.FILES:
                return JsonResponse({
                    'success': False,
                    'error': 'Không tìm thấy ảnh trong yêu cầu'
                }, status=400)
            
            image_file = request.FILES['image']
            
            # Lưu file tạm
            file_path = default_storage.save('tmp/predict_' + image_file.name, image_file)
            full_file_path = os.path.join(default_storage.base_location, file_path)
            
            try:
                # Gọi hàm predict_image từ predict.py
                result_img_url, predicted_class_name = predict_image(full_file_path)
                
                # Tìm loài côn trùng trong database
                species = Species.objects.filter(name__icontains=predicted_class_name).first()
                
                if species:
                    response_data = {
                        'success': True,
                        'predicted_class': predicted_class_name,
                        'species': {
                            'id': species.insects_id,
                            'name': species.name,
                            'scientific_name': species.ename,
                            'slug': species.slug,
                            'thumbnail': settings.MEDIA_URL + str(species.thumbnail) if species.thumbnail else None
                        },
                        'result_image': result_img_url
                    }
                else:
                    response_data = {
                        'success': True,
                        'predicted_class': predicted_class_name,
                        'species': None,
                        'result_image': result_img_url,
                        'message': 'Không tìm thấy loài khớp với ảnh trong cơ sở dữ liệu'
                    }
                
                # Xóa file tạm
                if os.path.exists(full_file_path):
                    os.remove(full_file_path)
                    
                return JsonResponse(response_data)
                
            except Exception as e:
                # Xóa file tạm nếu có lỗi
                if os.path.exists(full_file_path):
                    os.remove(full_file_path)
                    
                return JsonResponse({
                    'success': False,
                    'error': f'Lỗi khi nhận diện ảnh: {str(e)}'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Lỗi xử lý yêu cầu: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Phương thức không được hỗ trợ'
    }, status=405)

# Thêm function này nếu chưa có
def get_image_for_prediction(request):
    """Lấy ảnh mẫu cho nhận diện"""
    # Implement logic của bạn ở đây
    pass
# Thêm vào cuối views.py và chạy tạm thời
def check_missing_images():
    from insects.models import InsectsImage
    from django.conf import settings
    import os
    
    missing_count = 0
    for image in InsectsImage.objects.all():
        img_path = os.path.join(settings.MEDIA_ROOT, image.url)
        if not os.path.exists(img_path):
            print(f"Missing: {img_path} for image ID: {image.img_id}")
            missing_count += 1
    
    print(f"Total missing images: {missing_count}")





# =========================================BẢN ĐỒ PHÂN BỐ=========================================================


# Thêm vào phần imports
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_GET
from .models import DistributionReviewLog
from .models import InsectCropDamage, Crop
# =========================================BẢN ĐỒ PHÂN BỐ=========================================================
from django.shortcuts import render
from .models import (
    Species,
    Crop,
    AdministrativeRegion,
    InsectDistribution
)
from django.conf import settings


def distribution_map_view(request):
    """
    Hiển thị bản đồ phân bố + lọc theo tỉnh/thành Việt Nam
    """

    # Danh sách loài & cây trồng
    species_list = Species.objects.all().order_by('name')
    crops = Crop.objects.all().order_by('name')

    # CHỈ LẤY TỈNH/THÀNH CỦA VIỆT NAM
    provinces = AdministrativeRegion.objects.filter(
        level='province',
        parent__level='country',
        parent__name='Việt Nam'
    ).order_by('name')

    # Nhận filter từ GET
    province_id = request.GET.get('province')
    species_id = request.GET.get('species')

    # Chỉ hiển thị điểm đã được duyệt
    distributions = InsectDistribution.objects.filter(
        status='admin_approved'
    )

    if province_id:
        distributions = distributions.filter(region_id=province_id)

    if species_id:
        distributions = distributions.filter(species_id=species_id)

    return render(request, 'distribution_map.html', {
        'species_list': species_list,
        'crops': crops,
        'provinces': provinces,
        'distributions': distributions,
        'selected_province': province_id,
        'selected_species': species_id,
        'MEDIA_URL': settings.MEDIA_URL
    })
import json
from .models import DistributionBoundingBox
@login_required
def contribute_distribution(request):
    """View để người dùng đóng góp vị trí côn trùng"""
    species_list = Species.objects.all()
    regions = AdministrativeRegion.objects.filter(
        Q(level='province') | Q(name='Khác')
    ).order_by('name')

    
    if request.method == 'POST':
        try:
            # Lấy dữ liệu từ form
            species_id = request.POST['species']
            region_id = request.POST['region']
            latitude = request.POST['latitude']
            longitude = request.POST['longitude']
            observation_date = request.POST.get('observation_date')
            note = request.POST.get('note', '')
            bbox_raw = request.POST.get('bbox_data')
            bboxes = []

            if bbox_raw:
                try:
                    bboxes = json.loads(bbox_raw)
                except json.JSONDecodeError:
                    bboxes = []
            # Kiểm tra dữ liệu
            if not latitude or not longitude:
                messages.error(request, "Vui lòng cung cấp tọa độ địa lý!")
                return render(request, 'contribute_distribution.html', {
                    'species_list': species_list,
                    'regions': regions
                })
            with transaction.atomic():
            # Tạo bản ghi phân bố mới
                distribution = InsectDistribution.objects.create(
                    species_id=species_id,
                    region_id=region_id,
                    latitude=latitude,
                    longitude=longitude,
                    observation_date=observation_date if observation_date else None,
                    note=note,
                    created_by=request.user,
                    status='pending'
                )
                for box in bboxes:
                    DistributionBoundingBox.objects.create(
                        distribution=distribution,
                        x=box.get('x'),
                        y=box.get('y'),
                        width=box.get('width'),
                        height=box.get('height'),
                        confidence=box.get('confidence', 0),
                        label=box.get('class', '')
                    )
            
            # Gửi email thông báo cho chuyên gia
            try:
                cv_group = Group.objects.get(name="CVs")
                experts = cv_group.user_set.all()
                expert_emails = [expert.email for expert in experts if expert.email]
                
                if expert_emails:
                    species = Species.objects.get(insects_id=species_id)
                    region = AdministrativeRegion.objects.get(id=region_id)
                    
                    subject = "Thông báo: Có đóng góp vị trí phân bố mới"
                    message = (
                        f"Xin chào chuyên gia,\n\n"
                        f"- Người dùng {request.user.username} vừa đóng góp vị trí phân bố mới.\n"
                        f"- Loài: {species.name}\n"
                        f"- Khu vực: {region.name}\n"
                        f"- Tọa độ: {latitude}, {longitude}\n"
                        f"- Thời gian: {observation_date if observation_date else 'Không có'}\n"
                        f"- Ghi chú: {note if note else 'Không có'}\n\n"
                        f"Chuyên gia có thể truy cập vào hệ thống để xét duyệt.\n\n"
                        f"Trân trọng,\nHệ thống quản lý côn trùng"
                    )
                    from_email = "no-reply@yourdomain.com"
                    send_mail(subject, message, from_email, expert_emails, fail_silently=True)
            except Group.DoesNotExist:
                print("Nhóm 'CVs' không tồn tại trong cơ sở dữ liệu!")
            
            messages.success(request, "Đóng góp vị trí phân bố thành công! Vui lòng chờ xét duyệt.")
            return redirect('distribution_map')
            
        except Exception as e:
            messages.error(request, f"Lỗi khi đóng góp: {str(e)}")
    
    return render(request, 'contribute_distribution.html', {
        'species_list': species_list,
        'regions': regions
    })

@login_required
def contribute_distribution_with_image(request):
    species_list = Species.objects.all()
    regions = AdministrativeRegion.objects.filter(
        Q(level='province') | Q(name='Khác')
    ).order_by('name')


    if request.method == 'POST':
        if request.user.is_superuser:
            messages.error(request, "Admin không được đóng góp dữ liệu như người dùng.")
            return redirect('distribution_map')
        try:
            species_id = request.POST.get('species')
            region_id = request.POST.get('region')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            observation_date = request.POST.get('observation_date')
            note = request.POST.get('note', '')
            '''
            image_file = request.FILES.get('observation_image')
            image_url = None
            if image_file:
                image_url = default_storage.save(
                    f'observation_images/{image_file.name}',
                    image_file
                )

            # ✅ 1. Tạo distribution trước
            distribution = InsectDistribution.objects.create(
                species_id=species_id,
                region_id=region_id or None,
                latitude=latitude,
                longitude=longitude,
                observation_date=observation_date or None,
                note=note,
                observation_image=image_url,
                created_by=request.user,
                status='pending'
            )
            '''
            image_file = request.FILES.get('observation_image')

            distribution = InsectDistribution.objects.create(
                species_id=species_id,
                region_id=region_id or None,
                latitude=latitude,
                longitude=longitude,
                observation_date=observation_date or None,
                note=note,
                observation_image=image_file,  # ✅ ĐÚNG CHUẨN DJANGO
                created_by=request.user,
                status='pending'
            )


            # ✅ 2. LẤY bbox_data
            bbox_raw = request.POST.get('bbox_data')
            if bbox_raw:
                bboxes = json.loads(bbox_raw)

                for box in bboxes:
                    '''
                    DistributionBoundingBox.objects.create(
                        distribution=distribution,
                        x=box['x'],
                        y=box['y'],
                        width=box['width'],
                        height=box['height'],
                        confidence=box.get('confidence'),
                        label=box.get('class')
                    )
                    '''
                    img = distribution.observation_image
                    img.open()

                    natural_width = img.width
                    natural_height = img.height

                    display_width = float(box.get('imageWidth'))
                    display_height = float(box.get('imageHeight'))

                    scale_x = natural_width / display_width
                    scale_y = natural_height / display_height

                    DistributionBoundingBox.objects.create(
                        distribution=distribution,
                        x=box['x'] * scale_x,
                        y=box['y'] * scale_y,
                        width=box['width'] * scale_x,
                        height=box['height'] * scale_y,
                        confidence=box.get('confidence', 1),
                        label=box.get('class', '')
                    )

            messages.success(request, "Đóng góp thành công!")
            return redirect('distribution_map')

        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")

    return render(request, 'contribute_distribution_with_image.html', {
        'species_list': species_list,
        'regions': regions
    })
import json
import os
from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction

@user_passes_test(lambda u: u.groups.filter(name='CVs').exists())
def expert_review_distribution(request):
    """Chuyên gia xét duyệt đóng góp phân bố"""
    # Chỉ lấy các đóng góp chưa được chuyên gia hiện tại duyệt
    distributions = InsectDistribution.objects.filter(status='pending')
    
    # Lọc ra những đóng góp mà chuyên gia hiện tại đã duyệt
    reviewed_ids = DistributionReviewLog.objects.filter(
        reviewer=request.user,
        role='expert'
    ).values_list('distribution_id', flat=True)
    
    # Phân loại đóng góp
    distributions_to_review = distributions.exclude(id__in=reviewed_ids)
    distributions_reviewed = distributions.filter(id__in=reviewed_ids)
    
    if request.method == 'POST':
        try:
            dist = get_object_or_404(
                InsectDistribution,
                id=request.POST['distribution_id']
            )
            
            action = request.POST['action']
            if action == 'approve':
                dist.status = 'expert_approved'
                messages.success(request, f"Đã phê duyệt đóng góp từ {dist.created_by.username}")
            else:
                dist.status = 'expert_rejected'
                messages.warning(request, f"Đã từ chối đóng góp từ {dist.created_by.username}")
            
            dist.save()
            
            # Ghi log xét duyệt
            DistributionReviewLog.objects.create(
                distribution=dist,
                reviewer=request.user,
                role='expert',
                action=action,
                comment=request.POST.get('comment', '')
            )
            
        except Exception as e:
            messages.error(request, f"Lỗi khi xét duyệt: {str(e)}")
    
    context = {
        'distributions_to_review': distributions_to_review,
        'distributions_reviewed': distributions_reviewed,
        'MEDIA_URL': settings.MEDIA_URL
    }
    
    return render(request, 'expert_review_distribution.html', context)

@user_passes_test(lambda u: u.groups.filter(name='CVs').exists())
def expert_review_distribution_detail(request, id):
    """Chi tiết đóng góp phân bố cho chuyên gia xét duyệt"""
    dist = get_object_or_404(InsectDistribution, id=id)
    
    # Lấy bounding boxes từ database
    bboxes = DistributionBoundingBox.objects.filter(distribution=dist)
    
    # Kiểm tra xem chuyên gia hiện tại đã duyệt chưa
    already_reviewed = DistributionReviewLog.objects.filter(
        distribution=dist,
        reviewer=request.user,
        role='expert'
    ).exists()
    
    # Lấy thông tin duyệt trước đó nếu có
    previous_review = None
    if already_reviewed:
        previous_review = DistributionReviewLog.objects.filter(
            distribution=dist,
            reviewer=request.user,
            role='expert'
        ).first()
    
    if request.method == 'POST':
        # Kiểm tra nếu đã duyệt rồi
        if already_reviewed:
            messages.warning(request, "Bạn đã xét duyệt đóng góp này rồi.")
            return redirect('expert_review_distribution')
        
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()
        
        if action == 'reject' and not comment:
            messages.error(request, "Phải nhập lý do khi từ chối.")
            return redirect(request.path)
        
        # Ghi log xét duyệt
        DistributionReviewLog.objects.create(
            distribution=dist,
            reviewer=request.user,
            role='expert',
            action=action,
            comment=comment
        )
        
        # Đếm số chuyên gia đã phê duyệt
        approved_count = DistributionReviewLog.objects.filter(
            distribution=dist,
            role='expert',
            action='approve'
        ).values('reviewer').distinct().count()
        
        # Nếu đủ 3 chuyên gia phê duyệt thì chuyển trạng thái
        if approved_count >= 3:
            dist.status = 'expert_approved'
            dist.save()
            messages.success(request, "✅ Đã đủ 3 chuyên gia phê duyệt. Chuyển sang chờ admin xét duyệt.")
        else:
            remaining = 3 - approved_count
            messages.success(request, f"✅ Đã ghi nhận xét duyệt. Cần thêm {remaining} chuyên gia nữa để hoàn thành.")
        
        return redirect('expert_review_distribution')
    
    # Xử lý bbox data
    bbox_data = []
    img_width = 0
    img_height = 0
    
    if dist.observation_image and hasattr(dist.observation_image, 'url'):
        try:
            # Lấy đường dẫn ảnh
            img_path = dist.observation_image.path if hasattr(dist.observation_image, 'path') else \
                      os.path.join(settings.MEDIA_ROOT, dist.observation_image.name)
            
            # Lấy kích thước ảnh
            if os.path.exists(img_path):
                with Image.open(img_path) as img:
                    img_width, img_height = img.size
            
            # Xử lý bounding boxes từ database
            for bbox in bboxes:
                try:
                    # Chuẩn hóa coordinates về [0, 1]
                    if img_width > 0 and img_height > 0:
                        # Nếu đã là normalized (< 1), giữ nguyên
                        if bbox.x < 1 and bbox.y < 1 and bbox.width < 1 and bbox.height < 1:
                            normalized_x = float(bbox.x)
                            normalized_y = float(bbox.y)
                            normalized_width = float(bbox.width)
                            normalized_height = float(bbox.height)
                        else:
                            # Convert pixel to normalized
                            normalized_x = float(bbox.x) / img_width
                            normalized_y = float(bbox.y) / img_height
                            normalized_width = float(bbox.width) / img_width
                            normalized_height = float(bbox.height) / img_height
                    else:
                        # Nếu không có kích thước ảnh, giả sử đã normalized
                        normalized_x = float(bbox.x)
                        normalized_y = float(bbox.y)
                        normalized_width = float(bbox.width)
                        normalized_height = float(bbox.height)
                    
                    # Đảm bảo giá trị trong [0, 1]
                    normalized_x = max(0, min(1, normalized_x))
                    normalized_y = max(0, min(1, normalized_y))
                    normalized_width = max(0, min(1, normalized_width))
                    normalized_height = max(0, min(1, normalized_height))
                    
                    bbox_info = {
                        'x': normalized_x,
                        'y': normalized_y,
                        'width': normalized_width,
                        'height': normalized_height,
                        'label': str(bbox.label) if bbox.label else f"BBox {len(bbox_data) + 1}",
                        'confidence': float(bbox.confidence) if bbox.confidence else 1.0,
                        'type': 'rect'
                    }
                    
                    bbox_data.append(bbox_info)
                    
                except (ValueError, TypeError):
                    continue
            
        except Exception:
            pass
    
    # Xử lý URL ảnh
    image_url = ''
    if dist.observation_image and hasattr(dist.observation_image, 'url'):
        try:
            image_url = request.build_absolute_uri(dist.observation_image.url)
        except Exception:
            image_url = settings.MEDIA_URL + str(dist.observation_image)
    
    # Đếm số chuyên gia đã phê duyệt
    approved_count = DistributionReviewLog.objects.filter(
        distribution=dist,
        role='expert',
        action='approve'
    ).values('reviewer').distinct().count()
    
    # Đếm tổng số chuyên gia đã duyệt (cả approve và reject)
    total_reviewed = DistributionReviewLog.objects.filter(
        distribution=dist,
        role='expert'
    ).values('reviewer').distinct().count()
    
    context = {
        'distribution': dist,
        'bboxes_json': json.dumps(bbox_data, ensure_ascii=False) if bbox_data else '[]',
        'has_image': bool(dist.observation_image),
        'image_url': image_url,
        'image_width': img_width,
        'image_height': img_height,
        'bbox_count': len(bbox_data),
        'already_reviewed': already_reviewed,
        'previous_review': previous_review,
        'approved_count': approved_count,
        'total_reviewed': total_reviewed,
        'remaining_needed': max(0, 3 - approved_count),
        'MEDIA_URL': settings.MEDIA_URL,
    }
    
    return render(request, 'expert_review_distribution_detail.html', context)

@csrf_exempt
@user_passes_test(lambda u: u.groups.filter(name='CVs').exists())
def expert_save_bboxes(request, id):
    """API để chuyên gia lưu bounding boxes"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        # Parse JSON data
        data = json.loads(request.body)
        bboxes = data.get('bboxes', [])
        
        print(f"DEBUG: Saving bboxes for distribution {id}")
        print(f"DEBUG: Received {len(bboxes)} bboxes")
        
        # Get distribution
        distribution = get_object_or_404(InsectDistribution, id=id)
        
        # Kiểm tra xem chuyên gia đã duyệt chưa
        already_reviewed = DistributionReviewLog.objects.filter(
            distribution=distribution,
            reviewer=request.user,
            role='expert'
        ).exists()
        
        if already_reviewed:
            return JsonResponse({
                'error': 'Bạn đã duyệt đóng góp này rồi, không thể chỉnh sửa bounding boxes.'
            }, status=403)
        
        # Delete old bboxes
        deleted_count, _ = DistributionBoundingBox.objects.filter(distribution=distribution).delete()
        print(f"DEBUG: Deleted {deleted_count} old bboxes")
        
        # Save new bboxes
        saved_count = 0
        for bbox in bboxes:
            # Validate bbox data
            if 'x' not in bbox or 'y' not in bbox or 'width' not in bbox or 'height' not in bbox:
                print(f"DEBUG: Skipping invalid bbox: {bbox}")
                continue
                
            DistributionBoundingBox.objects.create(
                distribution=distribution,
                x=float(bbox.get('x', 0)),
                y=float(bbox.get('y', 0)),
                width=float(bbox.get('width', 0)),
                height=float(bbox.get('height', 0)),
                confidence=float(bbox.get('confidence', 1.0)),
                label=str(bbox.get('label', ''))
            )
            saved_count += 1
        
        print(f"DEBUG: Saved {saved_count} new bboxes")
        
        # Log the edit action
        DistributionReviewLog.objects.create(
            distribution=distribution,
            reviewer=request.user,
            role='expert',
            action='edit_bbox',
            comment=f'Chuyên gia chỉnh sửa {saved_count} bounding box(es)'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Đã lưu {saved_count} bounding box(es)',
            'count': saved_count
        })
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {e}")
        return JsonResponse({'error': 'Invalid JSON data: ' + str(e)}, status=400)
    except Exception as e:
        print(f"DEBUG: Error saving bboxes: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@require_GET
def distribution_map_api(request):
   
    """API trả về dữ liệu phân bố dạng JSON"""
    species_id = request.GET.get('species')
    region_id = request.GET.get('region')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    crop_id = request.GET.get('crop')
    
    # Debug: In ra các tham số để kiểm tra
    print(f"API Called with params: species={species_id}, region={region_id}, start_date={start_date}, end_date={end_date}, crop={crop_id}")
    
    # Lấy dữ liệu đã được phê duyệt bởi admin
    #qs = InsectDistribution.objects.filter(status='admin_approved')
    #qs = InsectDistribution.objects.all()
    qs = InsectDistribution.objects.filter(status='admin_approved')
    # Debug: In số lượng bản ghi ban đầu
    print(f"Initial queryset count: {qs.count()}")
    
    # Áp dụng các bộ lọc
    if species_id:
        qs = qs.filter(species_id=species_id)
        print(f"After species filter: {qs.count()}")
    
    if region_id:
        qs = qs.filter(region_id=region_id)
        print(f"After region filter: {qs.count()}")
    
    if start_date:
        qs = qs.filter(observation_date__gte=start_date)
        print(f"After start_date filter: {qs.count()}")
    
    if end_date:
        qs = qs.filter(observation_date__lte=end_date)
        print(f"After end_date filter: {qs.count()}")
    
    # Lọc theo cây trồng nếu có
    if crop_id:
        # Lấy các loài gây hại cho cây trồng này
        crop_damages = InsectCropDamage.objects.filter(
            crop_id=crop_id, 
            status='admin_approved'
        ).values_list('species_id', flat=True)
        qs = qs.filter(species_id__in=crop_damages)
        print(f"After crop filter: {qs.count()}")
    
    # Chỉ lấy các trường cần thiết để tối ưu
    qs = qs.select_related('species', 'region', 'created_by')
    
    # Debug: In số lượng kết quả cuối cùng
    print(f"Final queryset count: {qs.count()}")
    
    # Tạo dữ liệu trả về
    data = []
    for d in qs:
        try:
            # Xử lý float để tránh lỗi
            lat = float(d.latitude) if d.latitude else 0
            lng = float(d.longitude) if d.longitude else 0
            
            item = {
                'id': d.id,
                'lat': lat,
                'lng': lng,
                'species': {
                    'id': d.species.insects_id,
                    'name': d.species.name or 'Không rõ',
                    'scientific_name': d.species.ename or '',
                    'slug': d.species.slug or '',
                } if d.species else {},
                'region': {
                    'id': d.region.id if d.region else 0,
                    'name': d.region.name if d.region else 'Không rõ',
                    'level': d.region.level if d.region else '',
                } if d.region else {},
                'date': d.observation_date.strftime('%Y-%m-%d') if d.observation_date else '',
                'note': d.note or '',
                'created_by': d.created_by.username if d.created_by else 'Ẩn danh',
                'created_at': d.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'observation_image': request.build_absolute_uri(d.observation_image.url) if d.observation_image else None,

            }
            data.append(item)
        except Exception as e:
            print(f"Error processing distribution {d.id}: {e}")
            continue
    
    print(f"Returning {len(data)} data points")
    return JsonResponse(data, safe=False)

def crop_damage_list(request):
    """Danh sách cây trồng bị hại"""
    search_query = request.GET.get('search', '').strip()
    crop_filter = request.GET.get('crop', '')
    species_filter = request.GET.get('species', '')
    
    # Lấy danh sách cây trồng
    crops = Crop.objects.all()
    
    # Lấy danh sách thiệt hại đã được phê duyệt
    crop_damages = InsectCropDamage.objects.filter(status='admin_approved')
    
    # Áp dụng bộ lọc
    if search_query:
        crop_damages = crop_damages.filter(
            Q(crop__name__icontains=search_query) |
            Q(species__name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if crop_filter:
        crop_damages = crop_damages.filter(crop_id=crop_filter)
    
    if species_filter:
        crop_damages = crop_damages.filter(species_id=species_filter)
    
    # Phân trang
    paginator = Paginator(crop_damages, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'crop_damage_list.html', {
        'page_obj': page_obj,
        'crops': crops,
        'species_list': Species.objects.all(),
        'search_query': search_query,
        'crop_filter': crop_filter,
        'species_filter': species_filter,
        'MEDIA_URL': settings.MEDIA_URL
    })


def crop_damage_detail(request, crop_id):
    """Chi tiết thiệt hại của một cây trồng"""
    crop = get_object_or_404(Crop, id=crop_id)
    
    # Lấy tất cả loài gây hại cho cây trồng này
    damages = InsectCropDamage.objects.filter(
        crop=crop, 
        status='admin_approved'
    ).select_related('species')
    
    # Nhóm theo mức độ thiệt hại
    damages_by_level = {
        'low': [],
        'medium': [],
        'high': []
    }
    
    for damage in damages:
        damages_by_level[damage.damage_level].append(damage)
    
    return render(request, 'crop_damage_detail.html', {
        'crop': crop,
        'damages_by_level': damages_by_level,
        'MEDIA_URL': settings.MEDIA_URL
    })


from django.shortcuts import get_object_or_404, render
from .models import Species, InsectCropDamage


def insect_damage_detail(request, insects_id):
    """
    Hiển thị danh sách cây trồng bị hại bởi một loài côn trùng
    """
    species = get_object_or_404(Species, insects_id=insects_id)

    damages = (
        InsectCropDamage.objects
        .select_related('crop')
        .filter(
            species=species,
            status__in=['expert_approved', 'admin_approved']
        )
        .order_by('crop__name')
    )

    return render(
        request,
        'insect_damage_detail.html',
        {
            'species': species,
            'damages': damages
        }
        )

from django.http import JsonResponse
from .models import AdministrativeRegion


def get_regions_api(request):
    """
    API trả danh sách khu vực theo cấp (Việt Nam)
    """
    level = request.GET.get('level')

    qs = AdministrativeRegion.objects.all()

    # CHỈ LẤY KHU VỰC THUỘC VIỆT NAM
    try:
        vn = AdministrativeRegion.objects.get(
            level='country',
            name='Việt Nam'
        )
    except AdministrativeRegion.DoesNotExist:
        return JsonResponse([], safe=False)

    if level == 'country':
        qs = AdministrativeRegion.objects.filter(
            level='country',
            name__in=['Việt Nam', 'Khác']
        )

    elif level == 'province':
        qs = AdministrativeRegion.objects.filter(
            level='province',
            parent=vn
        )

    else:
        qs = AdministrativeRegion.objects.none()

    data = [{
        'id': r.id,
        'name': r.name,
        'level': r.level
    } for r in qs.order_by('name')]

    return JsonResponse(data, safe=False)


def get_crops_api(request):
    """API trả về danh sách cây trồng"""
    search = request.GET.get('search', '')
    
    crops = Crop.objects.all()
    
    if search:
        crops = crops.filter(name__icontains=search)
    
    data = [{
        'id': c.id,
        'name': c.name,
        'scientific_name': c.scientific_name,
        'description': c.description
    } for c in crops]
    
    return JsonResponse(data, safe=False)


@login_required
def contribute_crop_damage(request):
    """Đóng góp thông tin cây trồng bị hại"""
    species_list = Species.objects.all()
    crops = Crop.objects.all()
    
    if request.method == 'POST':
        try:
            species_id = request.POST['species']
            crop_id = request.POST['crop']
            damage_level = request.POST['damage_level']
            description = request.POST.get('description', '')
            
            damage = InsectCropDamage.objects.create(
                species_id=species_id,
                crop_id=crop_id,
                damage_level=damage_level,
                description=description,
                created_by=request.user,
                status='pending'
            )
            
            messages.success(request, "Đóng góp thông tin cây trồng bị hại thành công!")
            return redirect('crop_damage_list')
            
        except Exception as e:
            messages.error(request, f"Lỗi khi đóng góp: {str(e)}")
    
    return render(request, 'contribute_crop_damage.html', {
        'species_list': species_list,
        'crops': crops,
        'damage_levels': InsectCropDamage.DAMAGE_LEVELS
    })

# Thêm vào views.py hoặc tạo file mới
def add_sample_distribution_data():
    """Thêm dữ liệu mẫu để kiểm tra"""
    from django.contrib.auth.models import User
    import random
    
    try:
        # Lấy user admin
        admin_user = User.objects.filter(is_superuser=True).first()
        
        # Lấy một số loài
        species_list = Species.objects.all()[:5]
        
        # Lấy một số khu vực
        regions = AdministrativeRegion.objects.all()[:5]
        
        # Thêm dữ liệu mẫu
        for i in range(20):
            species = random.choice(species_list)
            region = random.choice(regions)
            
            # Tạo tọa độ ngẫu nhiên trong Việt Nam
            lat = 16 + random.uniform(-2, 2)
            lng = 107 + random.uniform(-2, 2)
            
            InsectDistribution.objects.create(
                species=species,
                region=region,
                latitude=lat,
                longitude=lng,
                observation_date=timezone.now().date(),
                note=f"Quan sát mẫu #{i+1}",
                status='admin_approved',
                created_by=admin_user
            )
        
        print("Đã thêm 20 bản ghi mẫu")
    except Exception as e:
        print(f"Lỗi khi thêm dữ liệu mẫu: {e}")

@login_required
def my_distribution_history(request):
    distributions = (
        InsectDistribution.objects
        .filter(created_by=request.user)
        .prefetch_related('review_logs', 'review_logs__reviewer')
        .order_by('-created_at')
    )

    return render(request, 'my_distribution_history.html', {
        'distributions': distributions
    })
# =========================================CÂY TRỒNG BỊ HẠI=========================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
import json

from .models import Crop, Species, InsectCropDamage

def is_expert(user):
    return user.groups.filter(name="CVs").exists() or user.is_superuser

@login_required
@user_passes_test(is_expert)
def expert_manage_crop(request):
    """
    Trang quản lý cây trồng và mối quan hệ gây hại với côn trùng
    """
    crops = Crop.objects.all().order_by("name")
    species_list = Species.objects.all().order_by("ename")
    
    # Lấy tất cả mối quan hệ gây hại (bao gồm cả pending)
    damages = (
        InsectCropDamage.objects
        .select_related("crop", "species", "created_by")
        .order_by("-created_at")
    )
    
    # Thêm thống kê cho chuyên gia xem
    stats = {
        'total': damages.count(),
        'pending': damages.filter(status='pending').count(),
        'expert_approved': damages.filter(status='expert_approved').count(),
        'admin_approved': damages.filter(status='admin_approved').count(),
        'rejected': damages.filter(status='rejected').count(),
    }
    
    context = {
        "crops": crops,
        "species_list": species_list,
        "damages": damages,
        "stats": stats,  # Thêm stats vào context
        'MEDIA_URL': settings.MEDIA_URL
    }
    
    return render(request, "expert_manage_crop.html", context)

@login_required
@user_passes_test(is_expert)
def expert_add_crop(request):
    """API thêm cây trồng mới"""
    if request.method == "POST":
        try:
            name = request.POST.get("name")
            scientific_name = request.POST.get("scientific_name", "")
            description = request.POST.get("description", "")
            economic_value = request.POST.get("economic_value", "")
            morphology = request.POST.get("morphology", "")
            cultivation_area = request.POST.get("cultivation_area", "")
            
            if not name:
                return JsonResponse({"success": False, "error": "Tên cây trồng là bắt buộc"})
            
            crop = Crop.objects.create(
                name=name,
                scientific_name=scientific_name,
                description=description,
                economic_value=economic_value,
                morphology=morphology,
                cultivation_area=cultivation_area
            )
            
            return JsonResponse({
                "success": True,
                "message": "Đã thêm cây trồng thành công",
                "crop": {
                    "id": crop.id,
                    "name": crop.name,
                    "scientific_name": crop.scientific_name
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

@login_required
@user_passes_test(is_expert)
def expert_edit_crop(request, crop_id):
    """API sửa cây trồng"""
    if request.method == "POST":
        try:
            crop = get_object_or_404(Crop, id=crop_id)
            
            crop.name = request.POST.get("name", crop.name)
            crop.scientific_name = request.POST.get("scientific_name", crop.scientific_name)
            crop.description = request.POST.get("description", crop.description)
            crop.economic_value = request.POST.get("economic_value", crop.economic_value)
            crop.morphology = request.POST.get("morphology", crop.morphology)
            crop.cultivation_area = request.POST.get("cultivation_area", crop.cultivation_area)
            
            crop.save()
            
            return JsonResponse({
                "success": True,
                "message": "Đã cập nhật cây trồng thành công",
                "crop": {
                    "id": crop.id,
                    "name": crop.name,
                    "scientific_name": crop.scientific_name
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

@login_required
@user_passes_test(is_expert)
def expert_delete_crop(request, crop_id):
    """API xóa cây trồng"""
    if request.method == "POST":
        try:
            crop = get_object_or_404(Crop, id=crop_id)
            
            # Kiểm tra xem cây trồng có mối quan hệ gây hại không
            if InsectCropDamage.objects.filter(crop=crop).exists():
                return JsonResponse({
                    "success": False, 
                    "error": "Không thể xóa cây trồng vì có mối quan hệ gây hại tồn tại"
                })
            
            crop.delete()
            
            return JsonResponse({
                "success": True,
                "message": "Đã xóa cây trồng thành công"
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

@login_required
@user_passes_test(is_expert)
def expert_add_damage(request):
    """API thêm mối quan hệ gây hại"""
    if request.method == "POST":
        try:
            crop_id = request.POST.get("crop_id")
            species_id = request.POST.get("species_id")
            damage_level = request.POST.get("damage_level")
            description = request.POST.get("description", "")
            
            if not all([crop_id, species_id, damage_level]):
                return JsonResponse({"success": False, "error": "Vui lòng điền đầy đủ thông tin bắt buộc"})
            
            # Kiểm tra xem mối quan hệ đã tồn tại chưa
            if InsectCropDamage.objects.filter(crop_id=crop_id, species_id=species_id).exists():
                return JsonResponse({
                    "success": False, 
                    "error": "Mối quan hệ gây hại này đã tồn tại"
                })
            
            damage = InsectCropDamage.objects.create(
                crop_id=crop_id,
                species_id=species_id,
                damage_level=damage_level,
                description=description,
                created_by=request.user,
                status="pending"  # <-- SỬA THÀNH 'pending' ĐỂ ADMIN DUYỆT
            )
            
            return JsonResponse({
                "success": True,
                "message": "Đã thêm mối quan hệ gây hại thành công. Vui lòng chờ admin duyệt.",
                "damage": {
                    "id": damage.id,
                    "crop_name": damage.crop.name,
                    "species_name": damage.species.ename,
                    "damage_level": damage.get_damage_level_display(),
                    "description": damage.description,
                    "created_by": damage.created_by.username,
                    "created_at": damage.created_at.strftime("%d/%m/%Y %H:%M"),
                    "status": "pending"  # <-- SỬA THÀNH 'pending'
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

@login_required
@user_passes_test(is_expert)
def expert_edit_damage(request, damage_id):
    """API sửa mối quan hệ gây hại"""
    if request.method == "POST":
        try:
            damage = get_object_or_404(InsectCropDamage, id=damage_id)
            
            damage.damage_level = request.POST.get("damage_level", damage.damage_level)
            damage.description = request.POST.get("description", damage.description)
            
            damage.save()
            
            return JsonResponse({
                "success": True,
                "message": "Đã cập nhật mối quan hệ gây hại thành công",
                "damage": {
                    "id": damage.id,
                    "damage_level": damage.get_damage_level_display(),
                    "description": damage.description
                }
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

@login_required
@user_passes_test(is_expert)
def expert_delete_damage(request, damage_id):
    """API xóa mối quan hệ gây hại"""
    if request.method == "POST":
        try:
            damage = get_object_or_404(InsectCropDamage, id=damage_id)
            damage.delete()
            
            return JsonResponse({
                "success": True,
                "message": "Đã xóa mối quan hệ gây hại thành công"
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid method"})

def crop_detail(request, crop_id):
    """
    Trang thông tin cây trồng bị côn trùng gây hại
    """
    crop = get_object_or_404(Crop, id=crop_id)

    damages = (
        InsectCropDamage.objects
        .select_related('species')
        .filter(
            crop=crop,
            status__in=['expert_approved', 'admin_approved']
        )
        .order_by('-damage_level')
    )

    context = {
        'crop': crop,
        'damages': damages,
        'MEDIA_URL': settings.MEDIA_URL
    }

    return render(request, 'crop_detail.html', context)
# ==================== ADMIN DUYỆT CÂY TRỒNG ====================

# Thêm các import cần thiết
import threading
from django.db import transaction
from django.db.models import Count
import time

# Cache đơn giản dùng dictionary (in-memory)
_admin_cache = {
    'stats': None,
    'stats_timestamp': 0,
    'cache_duration': 30  # 30 giây
}

# ==================== ADMIN DUYỆT CÂY TRỒNG ====================
@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_manage_crops(request):
    current_time = time.time()

    # ===== 1. CACHE CHỈ CHO STATS =====
    if (
        _admin_cache['stats'] is None or
        current_time - _admin_cache['stats_timestamp'] > _admin_cache['cache_duration']
    ):
        stats = {
            'total_crops': Crop.objects.count(),
            'pending_crops': Crop.objects.count(),
            'pending_damages': InsectCropDamage.objects.filter(status='pending').count(),
            'expert_approved_damages': InsectCropDamage.objects.filter(status='expert_approved').count(),
            'admin_approved_damages': InsectCropDamage.objects.filter(status='admin_approved').count(),
        }
        _admin_cache['stats'] = stats
        _admin_cache['stats_timestamp'] = current_time
    else:
        stats = _admin_cache['stats']

    # ===== 2. LUÔN LUÔN LẤY QUERYSET MỚI =====
    pending_crops = Crop.objects.all().prefetch_related('insectcropdamage_set')

    pending_damages = InsectCropDamage.objects.filter(
        status='pending'
    ).select_related('crop', 'species', 'created_by').order_by('-created_at')

    approved_damages = InsectCropDamage.objects.filter(
        status='admin_approved'
    ).select_related('crop', 'species').order_by('-created_at')

    return render(request, 'admin_manage_crops.html', {
        'pending_crops': pending_crops,
        'pending_damages': pending_damages,
        'approved_damages': approved_damages,
        'stats': stats,
        'MEDIA_URL': settings.MEDIA_URL
    })

# Hàm gửi email trong thread riêng để không block
def send_email_async(subject, message, from_email, recipient_list):
    """Gửi email bất đồng bộ"""
    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=True)
    except Exception as e:
        print(f"Error sending email in background: {e}")

@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_approve_damage(request, damage_id):
    """Admin chấp nhận mối quan hệ gây hại - TỐI ƯU TỐC ĐỘ"""
    if request.method == 'POST':
        start_time = time.time()
        
        try:
            # Lấy object với tối ưu query
            damage = InsectCropDamage.objects.select_related(
                'crop', 'species', 'created_by'
            ).get(id=damage_id)
            
            action = request.POST.get('action')
            reason = request.POST.get('reason', 'Không có lý do cụ thể')
            
            if action == 'approve':
                # Cập nhật trực tiếp, không cần transaction nếu chỉ 1 field
                InsectCropDamage.objects.filter(id=damage_id).update(status='admin_approved')
                
                # Gửi email trong background (không block)
                if damage.created_by.email:
                    email_thread = threading.Thread(
                        target=send_email_async,
                        args=(
                            "Thông báo: Mối quan hệ gây hại của bạn đã được duyệt",
                            f"Xin chào {damage.created_by.username},\n\nMối quan hệ gây hại bạn đóng góp đã được admin chấp nhận.\n• Cây trồng: {damage.crop.name}\n• Côn trùng: {damage.species.name}\n• Mức độ: {damage.get_damage_level_display()}\n• Thời gian: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\nTrân trọng,\nHệ thống quản lý côn trùng",
                            "no-reply@yourdomain.com",
                            [damage.created_by.email]
                        )
                    )
                    email_thread.daemon = True
                    email_thread.start()
                
                messages.success(request, f"Đã chấp nhận mối quan hệ gây hại {damage_id}")
                
            elif action == 'reject':
                # Cập nhật trực tiếp
                InsectCropDamage.objects.filter(id=damage_id).update(status='rejected')
                
                # Gửi email trong background
                if damage.created_by.email:
                    email_thread = threading.Thread(
                        target=send_email_async,
                        args=(
                            "Thông báo: Mối quan hệ gây hại của bạn đã bị từ chối",
                            f"Xin chào {damage.created_by.username},\n\nRất tiếc, mối quan hệ gây hại bạn đóng góp đã bị từ chối.\n• Cây trồng: {damage.crop.name}\n• Côn trùng: {damage.species.name}\n• Lý do: {reason}\n• Thời gian: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\nTrân trọng,\nHệ thống quản lý côn trùng",
                            "no-reply@yourdomain.com",
                            [damage.created_by.email]
                        )
                    )
                    email_thread.daemon = True
                    email_thread.start()
                
                messages.warning(request, f"Đã từ chối mối quan hệ gây hại {damage_id}")
            
            # Xóa cache thống kê
            _admin_cache['stats'] = None
            
            print(f"DEBUG: Duyệt xong trong {time.time() - start_time:.3f} giây")
            
            # Redirect nhanh
            return redirect('admin_manage_crops')
                
        except InsectCropDamage.DoesNotExist:
            messages.error(request, "Không tìm thấy mối quan hệ gây hại")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)[:100]}")
    
    return redirect('admin_manage_crops')


@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_approve_crop(request, crop_id):
    """Admin chấp nhận/xóa cây trồng """
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            
            if action == 'delete':
                # Xóa trực tiếp bằng ID (nhanh hơn)
                deleted_count, _ = Crop.objects.filter(id=crop_id).delete()
                
                if deleted_count > 0:
                    messages.success(request, f"Đã xóa cây trồng")
                    # Xóa cache thống kê
                    _admin_cache['stats'] = None
                else:
                    messages.warning(request, "Không tìm thấy cây trồng để xóa")
            
            # Redirect ngay lập tức
            return redirect('admin_manage_crops')
                
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)[:100]}")
    
    return redirect('admin_manage_crops')

@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_damage_detail(request, damage_id):
    damage = get_object_or_404(
        InsectCropDamage.objects.select_related('crop', 'species', 'created_by'),
        id=damage_id,
        status='admin_approved'
    )

    return render(request, 'admin_damage_detail.html', {
        'damage': damage
    })
@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_delete_damage(request, damage_id):
    if request.method == 'POST':
        damage = get_object_or_404(
            InsectCropDamage,
            id=damage_id,
            status='admin_approved'
        )
        damage.delete()

        # Xóa cache stats
        _admin_cache['stats'] = None

        messages.success(request, "Đã xóa mối quan hệ gây hại")
    
    return redirect('admin_manage_crops')
#=============================== Chấp nhận vị trí=======================
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_review_distribution(request):
    """Admin xét duyệt đóng góp phân bố - Trang danh sách"""
    # Lấy các tham số tìm kiếm
    species_id = request.GET.get('species', '')
    region_id = request.GET.get('region', '')
    status_filter = request.GET.get('status', 'expert_approved')
    search_query = request.GET.get('search', '')
    
    # Lấy danh sách phân bố theo filter
    distributions = InsectDistribution.objects.select_related('species', 'region', 'created_by')
    
    # Áp dụng bộ lọc
    if status_filter:
        distributions = distributions.filter(status=status_filter)
    
    if species_id:
        distributions = distributions.filter(species_id=species_id)
    
    if region_id:
        distributions = distributions.filter(region_id=region_id)
    
    if search_query:
        distributions = distributions.filter(
            Q(species__name__icontains=search_query) |
            Q(species__ename__icontains=search_query) |
            Q(region__name__icontains=search_query) |
            Q(note__icontains=search_query) |
            Q(created_by__username__icontains=search_query)
        )
    
    # Lấy danh sách loài và khu vực cho dropdown filter
    species_list = Species.objects.all().order_by('name')
    regions = AdministrativeRegion.objects.filter(level='province').order_by('name')
    
    # Phân trang
    paginator = Paginator(distributions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Thống kê
    stats = {
        'pending': InsectDistribution.objects.filter(status='pending').count(),
        'expert_approved': InsectDistribution.objects.filter(status='expert_approved').count(),
        'admin_approved': InsectDistribution.objects.filter(status='admin_approved').count(),
        'rejected': InsectDistribution.objects.filter(status='rejected').count(),
        'with_image': InsectDistribution.objects.filter(observation_image__isnull=False).count(),
    }
    
    # Xử lý POST request để duyệt/từ chối trực tiếp từ danh sách
    if request.method == 'POST':
        try:
            dist = get_object_or_404(
                InsectDistribution,
                id=request.POST['distribution_id']
            )
            
            action = request.POST['action']
            comment = request.POST.get('comment', '')
            
            if action == 'approve':
                dist.status = 'admin_approved'
                dist.approved_at = timezone.now()
                dist.save()
                
                # Gửi email thông báo
                try:
                    if dist.created_by.email:
                        subject = "Thông báo: Vị trí phân bố của bạn đã được chấp nhận"
                        message = (
                            f"Xin chào {dist.created_by.username},\n\n"
                            f"- Vị trí phân bố bạn đóng góp đã được admin chấp nhận.\n"
                            f"- Loài: {dist.species.name}\n"
                            f"- Tọa độ: {dist.latitude}, {dist.longitude}\n"
                            f"- Khu vực: {dist.region.name if dist.region else 'Không xác định'}\n"
                            f"- Thời gian phê duyệt: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                            f"Vị trí này sẽ được hiển thị trên bản đồ phân bố.\n\n"
                            f"Trân trọng,\nHệ thống quản lý côn trùng"
                        )
                        from_email = "no-reply@yourdomain.com"
                        send_mail(subject, message, from_email, [dist.created_by.email], fail_silently=True)
                except Exception as e:
                    print(f"Error sending email: {e}")
                
                messages.success(request, f"Đã chấp nhận vị trí #{dist.id} từ {dist.created_by.username}")
                
            elif action == 'reject':
                dist.status = 'rejected'
                dist.save()
                
                # Gửi email thông báo từ chối
                try:
                    if dist.created_by.email:
                        subject = "Thông báo: Vị trí phân bố của bạn đã bị từ chối"
                        message = (
                            f"Xin chào {dist.created_by.username},\n\n"
                            f"- Rất tiếc, vị trí phân bố bạn đóng góp đã bị từ chối.\n"
                            f"- Loài: {dist.species.name}\n"
                            f"- Tọa độ: {dist.latitude}, {dist.longitude}\n"
                            f"- Lý do: {comment}\n"
                            f"- Thời gian: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                            f"Trân trọng,\nHệ thống quản lý côn trùng"
                        )
                        from_email = "no-reply@yourdomain.com"
                        send_mail(subject, message, from_email, [dist.created_by.email], fail_silently=True)
                except Exception as e:
                    print(f"Error sending email: {e}")
                
                messages.warning(request, f"Đã từ chối vị trí #{dist.id}")
            
            # Ghi log xét duyệt
            DistributionReviewLog.objects.create(
                distribution=dist,
                reviewer=request.user,
                role='admin',
                action=action,
                comment=comment
            )
            
        except Exception as e:
            messages.error(request, f"Lỗi khi xét duyệt: {str(e)}")
        
        return redirect(request.path)
    
    return render(request, 'admin_review_distribution.html', {
        'page_obj': page_obj,
        'distributions': page_obj,
        'species_list': species_list,
        'regions': regions,
        'selected_species': species_id,
        'selected_region': region_id,
        'selected_status': status_filter,
        'search_query': search_query,
        'stats': stats,
        'MEDIA_URL': settings.MEDIA_URL
    })

@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_review_distribution_detail(request, id):
    """Admin xét duyệt chi tiết một vị trí phân bố"""
    distribution = get_object_or_404(InsectDistribution, id=id)
    bboxes = DistributionBoundingBox.objects.filter(distribution=distribution)
    
    # Kiểm tra xem admin đã duyệt chưa
    already_reviewed = DistributionReviewLog.objects.filter(
        distribution=distribution,
        reviewer=request.user,
        role='admin'
    ).exists()
    
    # Lấy lịch sử xét duyệt
    review_logs = DistributionReviewLog.objects.filter(
        distribution=distribution
    ).select_related('reviewer').order_by('created_at')
    
    # Xử lý POST request
    if request.method == 'POST':
        action = request.POST.get('action')
        comment = request.POST.get('comment', '').strip()
        
        if action == 'reject' and not comment:
            messages.error(request, "Phải nhập lý do khi từ chối.")
            return redirect(request.path)
        
        if already_reviewed:
            messages.warning(request, "Bạn đã xét duyệt vị trí này rồi.")
            return redirect('admin_review_distribution')
        
        # Lưu log xét duyệt
        DistributionReviewLog.objects.create(
            distribution=distribution,
            reviewer=request.user,
            role='admin',
            action=action,
            comment=comment
        )
        
        if action == 'approve':
            distribution.status = 'admin_approved'
            distribution.approved_at = timezone.now()
            distribution.save()
            
            # Gửi email thông báo
            try:
                if distribution.created_by.email:
                    subject = "Thông báo: Vị trí phân bố của bạn đã được chấp nhận"
                    message = (
                        f"Xin chào {distribution.created_by.username},\n\n"
                        f"- Vị trí phân bố bạn đóng góp đã được admin chấp nhận.\n"
                        f"- Loài: {distribution.species.name}\n"
                        f"- Tọa độ: {distribution.latitude}, {distribution.longitude}\n"
                        f"- Khu vực: {distribution.region.name if distribution.region else 'Không xác định'}\n"
                        f"- Thời gian phê duyệt: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                        f"Vị trí này sẽ được hiển thị trên bản đồ phân bố.\n\n"
                        f"Trân trọng,\nHệ thống quản lý côn trùng"
                    )
                    from_email = "no-reply@yourdomain.com"
                    send_mail(subject, message, from_email, [distribution.created_by.email], fail_silently=True)
            except Exception as e:
                print(f"Error sending email: {e}")
            
            messages.success(request, "Đã chấp nhận vị trí phân bố!")
            return redirect('admin_review_distribution')
            
        else:
            distribution.status = 'rejected'
            distribution.save()
            
            # Gửi email thông báo từ chối
            try:
                if distribution.created_by.email:
                    subject = "Thông báo: Vị trí phân bố của bạn đã bị từ chối"
                    message = (
                        f"Xin chào {distribution.created_by.username},\n\n"
                        f"- Rất tiếc, vị trí phân bố bạn đóng góp đã bị từ chối.\n"
                        f"- Loài: {distribution.species.name}\n"
                        f"- Tọa độ: {distribution.latitude}, {distribution.longitude}\n"
                        f"- Lý do: {comment}\n"
                        f"- Thời gian: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                        f"Trân trọng,\nHệ thống quản lý côn trùng"
                    )
                    from_email = "no-reply@yourdomain.com"
                    send_mail(subject, message, from_email, [distribution.created_by.email], fail_silently=True)
            except Exception as e:
                print(f"Error sending email: {e}")
            
            messages.error(request, "Đã từ chối vị trí phân bố!")
            return redirect('admin_review_distribution')
    
    # Xử lý bbox data cho template
    bbox_data = []
    img_width = 0
    img_height = 0
    
    if distribution.observation_image:
        try:
            img_path = os.path.join(settings.MEDIA_ROOT, distribution.observation_image.name)
            if os.path.exists(img_path):
                with Image.open(img_path) as img:
                    img_width, img_height = img.size
                    
                    for bbox in bboxes:
                        try:
                            if bbox.x < 1 and bbox.y < 1 and bbox.width < 1 and bbox.height < 1:
                                normalized_x = float(bbox.x)
                                normalized_y = float(bbox.y)
                                normalized_width = float(bbox.width)
                                normalized_height = float(bbox.height)
                            else:
                                normalized_x = float(bbox.x) / img_width
                                normalized_y = float(bbox.y) / img_height
                                normalized_width = float(bbox.width) / img_width
                                normalized_height = float(bbox.height) / img_height
                            
                            bbox_data.append({
                                'x': normalized_x,
                                'y': normalized_y,
                                'width': normalized_width,
                                'height': normalized_height,
                                'label': str(bbox.label) if bbox.label else '',
                                'confidence': float(bbox.confidence) if bbox.confidence else 0.0,
                            })
                        except (ValueError, TypeError):
                            continue
        except Exception as e:
            print(f"Error processing image: {e}")
    
    context = {
        'distribution': distribution,
        'bboxes_json': json.dumps(bbox_data, ensure_ascii=False),
        'has_image': bool(distribution.observation_image),
        
        'image_url': request.build_absolute_uri(distribution.observation_image.url) if distribution.observation_image else '',
        'image_width': img_width,
        'image_height': img_height,
        'review_logs': review_logs,
        'already_reviewed': already_reviewed,
        #'species_scientific_name': distribution.species.ename,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    
    return render(request, 'admin_review_distribution_detail.html', context)


@csrf_exempt
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_save_distribution(request, id):
    """API để admin lưu bounding boxes"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    try:
        data = json.loads(request.body)
        bboxes = data.get('bboxes', [])
        
        distribution = get_object_or_404(InsectDistribution, id=id)
        
        # Xóa bboxes cũ
        DistributionBoundingBox.objects.filter(distribution=distribution).delete()
        
        # Lưu bboxes mới
        for bbox in bboxes:
            DistributionBoundingBox.objects.create(
                distribution=distribution,
                x=bbox.get('x', 0),
                y=bbox.get('y', 0),
                width=bbox.get('width', 0),
                height=bbox.get('height', 0),
                confidence=bbox.get('confidence', 0),
                label=bbox.get('label', '')
            )
        
        # Ghi log
        DistributionReviewLog.objects.create(
            distribution=distribution,
            reviewer=request.user,
            role='admin',
            action='edit_bbox',
            comment='Admin chỉnh sửa bounding box'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Đã lưu {len(bboxes)} bounding box(es)',
            'count': len(bboxes)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import InsectDistribution, Species, AdministrativeRegion
# ========== QUẢN LÝ VỊ TRÍ ĐÃ DUYỆT ==========

@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_manage_approved_locations(request):
    """Trang quản lý tất cả vị trí đã được admin duyệt"""
    
    # Lấy tất cả vị trí đã được admin duyệt
    locations = InsectDistribution.objects.filter(status='admin_approved')
    
    # Lấy danh sách loài và khu vực cho filter - SỬA: AdministrativeRegion
    species_list = Species.objects.all().order_by('name')
    region_list = AdministrativeRegion.objects.all().order_by('name')
    
    # Xử lý tìm kiếm và filter
    search_query = request.GET.get('search', '')
    species_id = request.GET.get('species', '')
    region_id = request.GET.get('region', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Áp dụng bộ lọc
    if search_query:
        locations = locations.filter(
            Q(species__name__icontains=search_query) |
            Q(species__ename__icontains=search_query) |
            Q(species__eng_name__icontains=search_query) |
            Q(region__name__icontains=search_query) |
            Q(created_by__username__icontains=search_query) |
            Q(note__icontains=search_query)
        )
    
    if species_id and species_id != 'all':
        locations = locations.filter(species_id=species_id)
    
    if region_id and region_id != 'all':
        locations = locations.filter(region_id=region_id)
    
    if date_from:
        try:
            locations = locations.filter(created_at__date__gte=date_from)
        except:
            pass
    
    if date_to:
        try:
            locations = locations.filter(created_at__date__lte=date_to)
        except:
            pass
    
    # Thống kê
    total_count = locations.count()
    today_count = locations.filter(created_at__date=timezone.now().date()).count()
    species_stats = locations.values('species__name', 'species__eng_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Phân trang
    paginator = Paginator(locations.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'species_list': species_list,
        'region_list': region_list,
        'search_query': search_query,
        'selected_species': species_id,
        'selected_region': region_id,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
        'today_count': today_count,
        'species_stats': species_stats,
    }
    
    return render(request, 'admin_manage_approved_locations.html', context)

@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admins').exists())
def admin_delete_approved_location(request, id):
    """Admin xóa vị trí đã được duyệt"""
    if request.method == 'POST':
        location = get_object_or_404(InsectDistribution, id=id, status='admin_approved')
        
        # Lưu thông tin để gửi email thông báo
        user_email = location.created_by.email if location.created_by.email else None
        species_name = location.species.name
        coordinates = f"{location.latitude}, {location.longitude}"
        reason = request.POST.get('reason', 'Vi phạm quy định hệ thống')
        
        # Gửi email thông báo trước khi xóa
        if user_email:
            try:
                subject = "Thông báo: Vị trí phân bố của bạn đã bị xóa"
                message = (
                    f"Xin chào {location.created_by.username},\n\n"
                    f"Thông báo quan trọng về vị trí phân bố bạn đã đóng góp:\n\n"
                    f"• Loài: {species_name}\n"
                    f"• Tọa độ: {coordinates}\n"
                    f"• Ngày đóng góp: {location.created_at.strftime('%d/%m/%Y')}\n"
                    f"• Lý do xóa: {reason}\n"
                    f"• Thời gian xóa: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                    f"Lưu ý: Vị trí này đã bị xóa vĩnh viễn khỏi hệ thống và sẽ không hiển thị trên bản đồ phân bố nữa.\n\n"
                    f"Nếu bạn cho rằng đây là nhầm lẫn, vui lòng liên hệ với quản trị viên.\n\n"
                    f"Trân trọng,\nHệ thống quản lý côn trùng"
                )
                from_email = settings.DEFAULT_FROM_EMAIL
                send_mail(subject, message, from_email, [user_email], fail_silently=True)
            except Exception as e:
                print(f"Error sending email: {e}")
        
        # Ghi log trước khi xóa (nếu có model SystemLog)
        try:
            from .models import SystemLog
            SystemLog.objects.create(
                user=request.user,
                action='delete_location',
                details=f"Deleted location #{id} - {species_name} at {coordinates}. Reason: {reason}"
            )
        except:
            pass  # Bỏ qua nếu không có model SystemLog
        
        # Xóa vị trí
        location.delete()
        
        messages.success(request, f"Đã xóa vị trí #{id} thành công! Đã gửi email thông báo cho người đóng góp.")
        return redirect('admin_manage_approved_locations')
    
    messages.error(request, "Phương thức không hợp lệ!")
    return redirect('admin_manage_approved_locations')
#=============================== quản lý vị trí -CV=======================
@login_required
def expert_manage_distribution(request):
    
    #Trang quản lý vị trí côn trùng đơn giản
    
    # Kiểm tra quyền (CVs hoặc Admin)
    if not (request.user.groups.filter(name='CVs').exists() or request.user.is_superuser):
        return redirect('home')
    
    # Lấy dữ liệu
    species_list = Species.objects.all().order_by('name')
    regions = AdministrativeRegion.objects.all()
    
    selected_species_id = request.GET.get('species', '')
    distributions = InsectDistribution.objects.select_related('species', 'region')
    
    if selected_species_id:
        distributions = distributions.filter(species_id=selected_species_id)
    
    # Đếm số vị trí có ảnh
    distributions_with_image = distributions.filter(observation_image__isnull=False).count()
    
    # Xử lý POST requests
    if request.method == 'POST':
        action = request.POST.get('action')
        add_type = request.POST.get('add_type', 'manual')  # Lấy loại thêm
        
        if action == 'add':
            # Thêm mới
            try:
                if add_type == 'image':
                    # THÊM TỪ ẢNH - CÓ UPLOAD FILE
                    distribution = InsectDistribution(
                        species_id=request.POST.get('species_id'),
                        latitude=request.POST.get('latitude'),
                        longitude=request.POST.get('longitude'),
                        region_id=request.POST.get('region_id') or None,
                        note=request.POST.get('note', ''),
                        created_by=request.user,
                        status='expert_approved',  # Để expert_approved cho form từ ảnh
                        observation_image=request.FILES.get('observation_image'),  # QUAN TRỌNG: Lấy file
                        gps_from_image=True  # Đánh dấu GPS từ ảnh
                    )
                    distribution.save()
                    messages.success(request, 'Đã thêm vị trí từ ảnh thành công!')
                    
                else:
                    # THÊM THỦ CÔNG
                    distribution = InsectDistribution.objects.create(
                        species_id=request.POST.get('species_id'),
                        latitude=request.POST.get('latitude'),
                        longitude=request.POST.get('longitude'),
                        region_id=request.POST.get('region_id') or None,
                        note=request.POST.get('note', ''),
                        created_by=request.user,
                        status='admin_approved'  # Thủ công thì admin_approved
                    )
                    messages.success(request, 'Đã thêm vị trí mới!')
                    
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')
                print(f"Lỗi khi thêm vị trí: {e}")  # Debug
                
        elif action == 'update':
            # Cập nhật
            try:
                distribution = InsectDistribution.objects.get(
                    id=request.POST.get('distribution_id')
                )
                distribution.latitude = request.POST.get('latitude')
                distribution.longitude = request.POST.get('longitude')
                distribution.region_id = request.POST.get('region_id') or None
                distribution.note = request.POST.get('note', '')
                distribution.save()
                messages.success(request, 'Đã cập nhật vị trí!')
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')
                
        elif action == 'delete':
            # Xóa
            try:
                distribution = InsectDistribution.objects.get(
                    id=request.POST.get('distribution_id')
                )
                distribution.delete()
                messages.success(request, 'Đã xóa vị trí!')
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')
        
        return redirect(f"{request.path}?species={selected_species_id}")
    
    context = {
        'species_list': species_list,
        'regions': regions,
        'distributions': distributions,
        'selected_species_id': selected_species_id,
        'distributions_with_image': distributions_with_image,  # Thêm số lượng có ảnh
        'MEDIA_URL': settings.MEDIA_URL
    }
    
    return render(request, 'expert_manage_distribution.html', context)