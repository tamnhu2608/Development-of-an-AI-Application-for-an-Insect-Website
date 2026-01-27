from django.core.management.base import BaseCommand
from insects.models import InsectDistribution, Species, AdministrativeRegion, User
from datetime import date

class Command(BaseCommand):
    help = 'Giả lập dữ liệu phân bố 10 loài ở Việt Nam với tọa độ chính xác'

    def handle(self, *args, **kwargs):
        user = User.objects.get(pk=1)  # admin user

        # Lấy 10 loài đầu tiên
        species_list = Species.objects.all()[:10]

        # Danh sách tỉnh + tọa độ chính xác
        locations = [
            {"name": "Hà Nội", "lat": 21.0285, "lon": 105.8542},
            {"name": "Hồ Chí Minh", "lat": 10.7769, "lon": 106.7009},
            {"name": "Đà Nẵng", "lat": 16.0544, "lon": 108.2022},
            {"name": "Huế", "lat": 16.4637, "lon": 107.5909},
            {"name": "Hải Phòng", "lat": 20.8449, "lon": 106.6881},
            {"name": "Cần Thơ", "lat": 10.0452, "lon": 105.7469},
            {"name": "Nha Trang", "lat": 12.2388, "lon": 109.1967},
            {"name": "Vinh", "lat": 18.6796, "lon": 105.6813},
            {"name": "Thanh Hóa", "lat": 19.8069, "lon": 105.7880},
            {"name": "Buôn Ma Thuột", "lat": 12.6660, "lon": 108.0500},
        ]

        for species, loc in zip(species_list, locations):
            # Lấy region tương ứng theo tên tỉnh nếu có
            try:
                region = AdministrativeRegion.objects.get(name=loc["name"])
            except AdministrativeRegion.DoesNotExist:
                region = AdministrativeRegion.objects.first()  # fallback

            dist = InsectDistribution(
                species=species,
                region=region,
                latitude=loc["lat"],
                longitude=loc["lon"],
                observation_date=date.today(),
                note="Giả lập dữ liệu phân bố IP102 - Việt Nam",
                status="pending",
                created_by=user
            )
            dist.save()
            self.stdout.write(self.style.SUCCESS(
                f'Added {species.name} at {loc["name"]} ({loc["lat"]}, {loc["lon"]})'
            ))

        self.stdout.write(self.style.SUCCESS('Đã tạo xong 10 bản ghi giả lập chính xác ở Việt Nam.'))
