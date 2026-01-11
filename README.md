# Development of an AI Application for an Insect Website



# PHÁT TRIỂN ỨNG DỤNG AI TRONG XÂY DỰNG WEBSITE CÔN TRÙNG
InsectDatabaseWebsite

**📋 GIỚI THIỆU**

InsectDatabaseWebsite là một hệ thống web toàn diện được phát triển với mục tiêu trở thành nền tảng tra cứu, nhận dạng và quản lý thông tin về côn trùng, đặc biệt tập trung vào các loài gây hại trong nông nghiệp. Hệ thống kết hợp trí tuệ nhân tạo (AI) và hệ thống thông tin địa lý (GIS) để cung cấp giải pháp quản lý dịch hại thông minh.
___

**🎯 MỤC TIÊU CHÍNH**

Xây dựng cơ sở dữ liệu không gian-thời gian về côn trùng

Phát triển module bản đồ phân bố tương tác

Triển khai cơ chế đóng góp thông tin từ cộng đồng

Ứng dụng AI (YOLO) cho nhận dạng hình ảnh côn trùng
___

**✨ TÍNH NĂNG NỔI BẬT**

**_🔍 Tra cứu và nhận dạng_**

Tra cứu thông tin 102 loài côn trùng từ bộ dữ liệu IP102

Nhận dạng tự động bằng AI (YOLOv11) qua hình ảnh tải lên

Tìm kiếm đa dạng theo tên, phân loại khoa học, đặc điểm

**_🗺️ Hệ thống bản đồ thông minh_**

Bản đồ phân bố trực quan hiển thị vị trí phát hiện côn trùng

Bộ lọc thông minh theo loài, khu vực, thời gian

Tích hợp GIS với Leaflet.js và OpenStreetMap

**_👥 Hệ thống đóng góp cộng đồng_**

Đề xuất loài mới với cơ chế xét duyệt 2 cấp (Chuyên gia + Admin)

Đóng góp hình ảnh và mô tả cho các loài có sẵn

Chia sẻ vị trí phát hiện kết hợp GPS và chụp ảnh trực tiếp

**_👨‍💼 Phân quyền người dùng_**

Người dùng phổ thông: Tra cứu, đóng góp thông tin

Chuyên gia (CV): Xét duyệt đóng góp, quản lý dữ liệu

Quản trị viên (Admin): Quản lý hệ thống, chấp nhận đề xuất cuối cùng

___

**🛠️ CÔNG NGHỆ SỬ DỤNG**

**_Backend_**

-Framework: Django 4.2+

-Ngôn ngữ: Python 3.8+

-Database: MySQL 8.0+ với hỗ trợ dữ liệu không gian

-AI Model: YOLOv11 cho nhận dạng hình ảnh

**_Frontend_**

-Bản đồ: Leaflet.js với OpenStreetMap

-Giao diện: HTML5, CSS3, JavaScript

-API: Django REST Framework 

**_Công cụ phát triển_**

-Xử lý ảnh: OpenCV, Pillow

-Phân tích dữ liệu: FiftyOne cho đánh giá dataset

-Quản lý môi trường: Virtual Environment
___

**🚀 CÀI ĐẶT VÀ TRIỂN KHAI**
#### **Bước 1: Clone repository**
```bash
git clone https://github.com/username/InsectDatabaseWebsite.git
cd InsectDatabaseWebsite
```
#### **Bước 2: Tạo và kích hoạt môi trường ảo**
```bash
python -m venv venv

#Windows
venv\Scripts\activate
#Linux/Mac
source venv/bin/activate
```
#### **Bước 3: Cài đặt dependencies**
```bash
pip install -r requirements.txt
```

#### **Bước 4: Tạo database trong MySQL**
```bash
#Cập nhật thông tin kết nối database trong .env
DB_NAME=insect_database
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306

#Khởi tạo database
python manage.py makemigrations
python manage.py migrate
```
#### **Bước 5: Khởi động server**
```bash
python manage.py runserver
```
**👥 TÁC GIẢ**

PGS.TS Đoàn Thanh Nghị - Giảng viên hướng dẫn

Nguyễn Hồng Tâm Như - Sinh viên thực hiện

Đơn vị: Trường Đại học An Giang - Khoa Công nghệ Thông tin
